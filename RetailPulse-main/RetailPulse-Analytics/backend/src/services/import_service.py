import csv
import io
import json
from collections import defaultdict
from datetime import datetime

from fastapi import HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.category import Category
from src.models.customer import Customer
from src.models.import_history import ImportErrorRecord, ImportHistory, ImportStatus, ImportType
from src.models.product import Product
from src.models.sale import Sale
from src.services.audit_service import AuditAction, create_audit_log
from src.models.user import User

REQUIRED_COLUMNS = {
    "products": ["Product Name", "SKU", "Category", "Unit Price", "Stock Quantity"],
    "customers": ["Name", "Email", "Phone"],
    "sales": ["Customer", "Product", "Quantity", "Unit Price", "Sale Date"],
}


def _normalize_column_name(value: str | None) -> str:
    return (value or "").strip().lower().replace("_", " ")


def _clean_value(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _canonicalize_row(row: dict[str, str]) -> dict[str, str]:
    canonical: dict[str, str] = {}
    for key, value in row.items():
        if key is None:
            continue
        canonical[_normalize_column_name(key)] = _clean_value(value)
    return canonical


def parse_csv_upload(file: UploadFile, max_bytes: int = 5 * 1024 * 1024) -> tuple[list[dict[str, str]], list[str]]:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only CSV files are supported")
    if file.size and file.size > max_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="CSV file is too large")

    raw = file.file.read()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV file does not contain a header row")

    rows = []
    for row in reader:
        if row is None:
            continue
        if not any(_clean_value(value) for value in row.values()):
            continue
        rows.append({str(key): _clean_value(value) for key, value in row.items() if key is not None})

    fieldnames = [name for name in reader.fieldnames if name is not None]
    return rows, fieldnames


def build_preview(rows: list[dict[str, str]], columns: list[str], max_rows: int = 8) -> list[dict[str, str]]:
    preview_rows = []
    for row in rows[:max_rows]:
        preview_row = {}
        for column in columns:
            preview_row[column] = row.get(column, "")
        preview_rows.append(preview_row)
    return preview_row if False else preview_rows


def _normalize_field_lookup(row: dict[str, str]) -> dict[str, str]:
    lookup = {}
    for key, value in row.items():
        lookup[_normalize_column_name(key)] = _clean_value(value)
    return lookup


def _get_column_value(row: dict[str, str], *names: str) -> str:
    for name in names:
        value = row.get(_normalize_column_name(name))
        if value is not None:
            return value
    return ""


def _issue(row_number: int | None, row: dict[str, str], message: str, error_type: str = "invalid") -> dict:
    return {
        "rowNumber": row_number,
        "row": row,
        "message": message,
        "errorType": error_type,
    }


def validate_csv_rows(import_type: str, rows: list[dict[str, str]], db: Session | None = None, company_id: int | None = None, category_names: set[str] | None = None) -> dict:
    import_key = import_type.lower().strip()
    required_columns = REQUIRED_COLUMNS.get(import_key, [])
    normalized_rows = []
    issues = []
    seen_values = defaultdict(set)
    missing_columns = []

    if not required_columns:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported import type")

    if not rows:
        return {
            "total_records": 0,
            "valid_count": 0,
            "invalid_count": 0,
            "duplicate_count": 0,
            "missing_columns": [],
            "issues": [],
            "preview": [],
            "valid_rows": [],
        }

    column_names = set(_normalize_column_name(key) for key in rows[0].keys())
    available_keys = { _normalize_column_name(key) for row in rows for key in row.keys() }
    for column_name in required_columns:
        normalized_name = _normalize_column_name(column_name)
        if normalized_name not in available_keys:
            missing_columns.append(column_name)

    for row_index, row in enumerate(rows, start=2):
        normalized_row = _normalize_field_lookup(row)
        normalized_rows.append({**row, **normalized_row})
        row_errors = []
        if import_key == "products":
            product_name = _get_column_value(normalized_row, "Product Name", "product name", "name")
            sku = _get_column_value(normalized_row, "SKU", "sku")
            category_name = _get_column_value(normalized_row, "Category", "category")
            unit_price = _get_column_value(normalized_row, "Unit Price", "unit price", "price")
            stock_quantity = _get_column_value(normalized_row, "Stock Quantity", "stock quantity", "stock")

            if not product_name:
                row_errors.append("Product Name is required")
            if not sku:
                row_errors.append("SKU is required")
            elif sku in seen_values["sku"]:
                row_errors.append("Duplicate SKU detected")
            else:
                seen_values["sku"].add(sku)
            if category_name and category_names is not None and category_name.lower() not in {name.lower() for name in category_names}:
                row_errors.append("Category must match an existing category in this company")
            if not category_name:
                row_errors.append("Category is required")
            try:
                price_value = float(unit_price)
                if price_value <= 0:
                    row_errors.append("Price must be greater than zero")
            except ValueError:
                row_errors.append("Unit Price must be a valid number")
            try:
                stock_value = int(float(stock_quantity))
                if stock_value < 0:
                    row_errors.append("Stock quantity cannot be negative")
            except ValueError:
                row_errors.append("Stock Quantity must be a valid number")

            if db is not None and company_id is not None and sku:
                existing = db.scalar(select(Product.id).where(Product.company_id == company_id, Product.sku == sku))
                if existing is not None:
                    row_errors.append("SKU already exists in this company")

        elif import_key == "customers":
            name = _get_column_value(normalized_row, "Name", "name", "customer name")
            email = _get_column_value(normalized_row, "Email", "email")
            phone = _get_column_value(normalized_row, "Phone", "phone")

            if not name:
                row_errors.append("Name is required")
            if not email:
                row_errors.append("Email is required")
            else:
                try:
                    from email_validator import validate_email

                    validate_email(email)
                except Exception:
                    row_errors.append("Email is invalid")
            if not phone:
                row_errors.append("Phone is required")
            elif not phone.replace("+", "").replace("-", "").replace(" ", "").isdigit():
                row_errors.append("Phone is invalid")

            if email:
                email_key = email.lower()
                if email_key in seen_values["email"]:
                    row_errors.append("Duplicate email detected")
                else:
                    seen_values["email"].add(email_key)
            if phone:
                phone_key = phone.lower()
                if phone_key in seen_values["phone"]:
                    row_errors.append("Duplicate phone number detected")
                else:
                    seen_values["phone"].add(phone_key)

            if db is not None and company_id is not None:
                if email:
                    exists = db.scalar(select(Customer.id).where(Customer.company_id == company_id, Customer.email == email))
                    if exists is not None:
                        row_errors.append("Customer email already exists in this company")
                if phone:
                    exists = db.scalar(select(Customer.id).where(Customer.company_id == company_id, Customer.phone_number == phone))
                    if exists is not None:
                        row_errors.append("Customer phone number already exists in this company")

        elif import_key == "sales":
            customer_name = _get_column_value(normalized_row, "Customer", "customer", "customer name")
            product_name = _get_column_value(normalized_row, "Product", "product")
            quantity = _get_column_value(normalized_row, "Quantity", "quantity")
            unit_price = _get_column_value(normalized_row, "Unit Price", "unit price", "price")
            sale_date = _get_column_value(normalized_row, "Sale Date", "sale date", "date")
            invoice_number = _get_column_value(normalized_row, "Invoice Number", "invoice number", "invoice")

            if not customer_name:
                row_errors.append("Customer is required")
            if not product_name:
                row_errors.append("Product is required")
            if not quantity:
                row_errors.append("Quantity is required")
            else:
                try:
                    qty = int(float(quantity))
                    if qty <= 0:
                        row_errors.append("Quantity must be greater than zero")
                except ValueError:
                    row_errors.append("Quantity must be a valid number")
            if not unit_price:
                row_errors.append("Unit Price is required")
            else:
                try:
                    if float(unit_price) <= 0:
                        row_errors.append("Unit Price must be greater than zero")
                except ValueError:
                    row_errors.append("Unit Price must be a valid number")
            if not sale_date:
                row_errors.append("Sale Date is required")
            else:
                try:
                    datetime.fromisoformat(sale_date)
                except ValueError:
                    try:
                        datetime.strptime(sale_date, "%m/%d/%Y")
                    except ValueError:
                        row_errors.append("Sale Date is invalid")

            if db is not None and company_id is not None:
                customer = db.scalar(
                    select(Customer.id).where(Customer.company_id == company_id, Customer.full_name == customer_name)
                )
                if customer_name and customer is None:
                    row_errors.append("Customer must exist in this company")
                product = db.scalar(
                    select(Product.id).where(Product.company_id == company_id, Product.name == product_name)
                )
                if product_name and product is None:
                    row_errors.append("Product must exist in this company")
                if product_name and product is not None:
                    product_record = db.scalar(select(Product).where(Product.id == product))
                    if product_record and quantity:
                        try:
                            if int(float(quantity)) > product_record.stock_quantity:
                                row_errors.append("Quantity exceeds available stock")
                        except ValueError:
                            pass

            if invoice_number:
                duplicate_key = (invoice_number.lower(),)
                if invoice_number.lower() in seen_values["invoice"]:
                    row_errors.append("Duplicate invoice number detected")
                else:
                    seen_values["invoice"].add(invoice_number.lower())
            if not invoice_number:
                fallback_key = f"{customer_name}|{product_name}|{sale_date}|{quantity}"
                if fallback_key.lower() in seen_values["sales_row"]:
                    row_errors.append("Duplicate sales row detected")
                else:
                    seen_values["sales_row"].add(fallback_key.lower())

        if row_errors:
            issues.extend([_issue(row_index, row, message) for message in row_errors])

    valid_count = len(rows) - len({issue["rowNumber"] for issue in issues})
    duplicate_count = sum(1 for issue in issues if issue["message"].lower().startswith("duplicate") or "already exists" in issue["message"].lower())
    invalid_count = len(issues)
    valid_rows = []
    for row in rows:
        row_number = rows.index(row) + 2
        if not any(issue["rowNumber"] == row_number for issue in issues):
            valid_rows.append(row)

    return {
        "total_records": len(rows),
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "duplicate_count": duplicate_count,
        "missing_columns": missing_columns,
        "issues": issues,
        "preview": rows[:8],
        "valid_rows": valid_rows,
    }


def create_import_history(db: Session, current_user: User, import_type: str, file_name: str, total_records: int, status: str, successful_records: int = 0, failed_records: int = 0, duplicate_records: int = 0):
    import_record = ImportHistory(
        company_id=current_user.company_id,
        import_type=import_type,
        filename=file_name,
        uploaded_by=current_user.name,
        uploaded_by_id=current_user.id,
        total_records=total_records,
        successful_records=successful_records,
        failed_records=failed_records,
        duplicate_records=duplicate_records,
        status=status,
    )
    db.add(import_record)
    db.flush()
    return import_record


def store_import_errors(db: Session, import_record: ImportHistory, issues: list[dict]) -> None:
    for issue in issues:
        row_data = json.dumps(issue.get("row", {}), ensure_ascii=False)
        db.add(
            ImportErrorRecord(
                import_id=import_record.id,
                row_number=issue.get("rowNumber"),
                error_type=issue.get("errorType", "invalid"),
                message=issue.get("message", "Invalid record"),
                row_data=row_data,
            )
        )


def _resolve_category_name_by_product(db: Session, company_id: int, product_name: str) -> str | None:
    product = db.scalar(select(Product).where(Product.company_id == company_id, Product.name == product_name))
    return product.name if product else None


def process_import_rows(db: Session, current_user: User, import_type: str, rows: list[dict[str, str]], file_name: str, request: Request | None = None) -> dict:
    import_type_key = import_type.lower().strip()
    category_names = None
    if import_type_key == "products":
        category_names = {category.name for category in db.scalars(select(Category).where(Category.company_id == current_user.company_id)).all()}

    validation = validate_csv_rows(import_type_key, rows, db=db, company_id=current_user.company_id, category_names=category_names)
    if validation["missing_columns"]:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing required columns")

    import_record = create_import_history(
        db,
        current_user,
        import_type_key,
        file_name,
        validation["total_records"],
        status=ImportStatus.PENDING.value,
        successful_records=0,
        failed_records=validation["invalid_count"],
        duplicate_records=validation["duplicate_count"],
    )
    store_import_errors(db, import_record, validation["issues"])

    if validation["valid_count"] == 0:
        import_record.status = ImportStatus.FAILED.value
        import_record.completed_at = datetime.utcnow()
        db.commit()
        create_audit_log(
            db,
            company_id=current_user.company_id,
            user_id=current_user.id,
            performed_by=current_user.name,
            entity_type="Import",
            resource_id=import_record.id,
            entity_name=file_name,
            action=AuditAction.IMPORT_COMPLETED,
            request=request,
            description=f"Imported {import_type_key} from {file_name}; no valid rows",
            status="failed",
            after_values={"totalRecords": validation["total_records"], "successfulRecords": 0},
        )
        db.commit()
        return {
            "importId": import_record.id,
            "totalRecords": validation["total_records"],
            "successfullyAdded": 0,
            "failedRecords": validation["invalid_count"],
            "duplicateRecords": validation["duplicate_count"],
            "validationFailures": validation["invalid_count"],
            "status": import_record.status,
            "errors": validation["issues"],
        }

    try:
        import_record.status = ImportStatus.PROCESSING.value
        db.commit()
        inserted = 0
        for row in validation["valid_rows"]:
            row_map = _normalize_field_lookup(row)
            if import_type_key == "products":
                product_name = _get_column_value(row_map, "Product Name", "product name", "name")
                sku = _get_column_value(row_map, "SKU", "sku")
                category_name = _get_column_value(row_map, "Category", "category")
                unit_price = float(_get_column_value(row_map, "Unit Price", "unit price", "price"))
                stock_quantity = int(float(_get_column_value(row_map, "Stock Quantity", "stock quantity", "stock")))
                category = db.scalar(select(Category).where(Category.company_id == current_user.company_id, Category.name == category_name))
                if category is None:
                    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Category '{category_name}' not found")
                db.add(
                    Product(
                        company_id=current_user.company_id,
                        category_id=category.id,
                        name=product_name,
                        sku=sku,
                        unit_price=unit_price,
                        cost_price=unit_price,
                        stock_quantity=stock_quantity,
                        is_out_of_stock=stock_quantity == 0,
                        unit_of_measure="pcs",
                    )
                )
            elif import_type_key == "customers":
                full_name = _get_column_value(row_map, "Name", "name", "customer name")
                email = _get_column_value(row_map, "Email", "email")
                phone = _get_column_value(row_map, "Phone", "phone")
                db.add(
                    Customer(
                        company_id=current_user.company_id,
                        customer_code=f"CUST-{len(rows)}-{inserted + 1}",
                        full_name=full_name,
                        email=email,
                        phone_number=phone,
                        customer_type="retail",
                    )
                )
            elif import_type_key == "sales":
                customer_name = _get_column_value(row_map, "Customer", "customer", "customer name")
                product_name = _get_column_value(row_map, "Product", "product")
                quantity = int(float(_get_column_value(row_map, "Quantity", "quantity")))
                unit_price = float(_get_column_value(row_map, "Unit Price", "unit price", "price"))
                sale_date = _get_column_value(row_map, "Sale Date", "sale date", "date")
                customer = db.scalar(select(Customer).where(Customer.company_id == current_user.company_id, Customer.full_name == customer_name))
                product = db.scalar(select(Product).where(Product.company_id == current_user.company_id, Product.name == product_name))
                if customer is None or product is None:
                    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Customer or product does not exist")
                invoice_number = _get_column_value(row_map, "Invoice Number", "invoice number", "invoice") or f"INV-{current_user.company_id}-{inserted + 1}"
                db.add(
                    Sale(
                        company_id=current_user.company_id,
                        customer_id=customer.id,
                        customer_name=customer.full_name,
                        invoice_number=invoice_number,
                        sale_date=datetime.fromisoformat(sale_date) if "T" in sale_date else datetime.strptime(sale_date, "%Y-%m-%d"),
                        sales_channel="in-store",
                        payment_method="cash",
                        payment_status="paid",
                        total_amount=quantity * unit_price,
                        created_by=current_user.id,
                    )
                )
            inserted += 1
        db.commit()
        import_record.successful_records = inserted
        import_record.failed_records = validation["invalid_count"]
        import_record.duplicate_records = validation["duplicate_count"]
        import_record.status = ImportStatus.COMPLETED_WITH_ERRORS.value if validation["invalid_count"] else ImportStatus.COMPLETED.value
        import_record.completed_at = datetime.utcnow()
        db.commit()
        create_audit_log(
            db,
            company_id=current_user.company_id,
            user_id=current_user.id,
            performed_by=current_user.name,
            entity_type="Import",
            resource_id=import_record.id,
            entity_name=file_name,
            action=AuditAction.IMPORT_COMPLETED,
            request=request,
            description=f"Imported {import_type_key} from {file_name}",
            status="success" if not validation["invalid_count"] else "partial",
            after_values={"totalRecords": validation["total_records"], "successfulRecords": inserted, "failedRecords": validation["invalid_count"]},
        )
        db.commit()
        return {
            "importId": import_record.id,
            "totalRecords": validation["total_records"],
            "successfullyAdded": inserted,
            "failedRecords": validation["invalid_count"],
            "duplicateRecords": validation["duplicate_count"],
            "validationFailures": validation["invalid_count"],
            "status": import_record.status,
            "errors": validation["issues"],
        }
    except Exception as exc:
        db.rollback()
        import_record.status = ImportStatus.FAILED.value
        import_record.completed_at = datetime.utcnow()
        import_record.failed_records = validation["total_records"]
        db.commit()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Import failed and was rolled back") from exc


def list_import_history(db: Session, company_id: int) -> list[ImportHistory]:
    return db.scalars(select(ImportHistory).where(ImportHistory.company_id == company_id).order_by(ImportHistory.created_at.desc())).all()


def get_import_history_record(db: Session, company_id: int, import_id: int) -> ImportHistory:
    item = db.scalar(select(ImportHistory).where(ImportHistory.company_id == company_id, ImportHistory.id == import_id))
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import record not found")
    return item


def get_import_errors(db: Session, company_id: int, import_id: int) -> list[ImportErrorRecord]:
    import_record = get_import_history_record(db, company_id, import_id)
    return db.scalars(select(ImportErrorRecord).where(ImportErrorRecord.import_id == import_record.id)).all()
