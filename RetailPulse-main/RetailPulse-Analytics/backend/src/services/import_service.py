import csv
import io
import json
import logging
import math
import time
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import HTTPException, Request, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.category import Category
from src.models.customer import Customer
from src.models.import_history import ImportErrorRecord, ImportHistory, ImportJob, ImportStatus
from src.models.inventory import Inventory, InventoryMovement, InventoryMovementType, StockStatus
from src.models.product import Product
from src.models.sale import PaymentMethod, PaymentStatus, Sale, SaleItem, SalesChannel
from src.services.audit_service import AuditAction, create_audit_log
from src.services.notification_service import create_notification
from src.services.inventory_service import apply_sale_stock_change, ensure_inventory_for_product, evaluate_inventory_alerts
from src.services.data_quality_service import run_incremental_checks
from src.services.customer_service import sync_customer_purchase_summary
from src.models.user import User
from src.config.database import SessionLocal

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = {
    "products": ["Product Name", "SKU", "Category", "Unit Price", "Stock Quantity"],
    "inventory": ["SKU", "Quantity"],
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


def _whole_number(value: str) -> int:
    number = float(value)
    if not math.isfinite(number) or not number.is_integer():
        raise ValueError("Value must be a whole number")
    return int(number)


def parse_csv_upload(file: UploadFile, max_bytes: int = 5 * 1024 * 1024) -> tuple[list[dict[str, str]], list[str]]:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only CSV files are supported")
    if file.size is not None and file.size > max_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="CSV file is too large")

    raw = file.file.read()
    if len(raw) > max_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="CSV file is too large")
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV must use UTF-8 encoding") from exc
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""))
        fieldnames = reader.fieldnames
        if not fieldnames or any(not name or not name.strip() for name in fieldnames):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV must contain non-empty column names")
        if len({_normalize_column_name(name) for name in fieldnames}) != len(fieldnames):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV contains duplicate column names")
        rows = []
        for row in reader:
            if row is None:
                continue
            if None in row:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A CSV row contains more values than the header")
            if not any(_clean_value(value) for value in row.values()):
                continue
            rows.append({str(key): _clean_value(value) for key, value in row.items() if key is not None})
    except csv.Error as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV format is invalid") from exc
    return rows, [name.strip() for name in fieldnames]


def build_preview(rows: list[dict[str, str]], columns: list[str], max_rows: int = 8) -> list[dict[str, str]]:
    preview_rows = []
    for row in rows[:max_rows]:
        preview_row = {}
        for column in columns:
            preview_row[column] = row.get(column, "")
        preview_rows.append(preview_row)
    return preview_rows


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


def _issue(row_number: int | None, row: dict[str, str], message: str, error_type: str | None = None) -> dict:
    if error_type is None:
        error_type = "duplicate" if "duplicate" in message.lower() or "already exists" in message.lower() else "invalid"
    return {
        "rowNumber": row_number,
        "row": row,
        "message": message,
        "errorType": error_type,
    }


def validate_csv_rows(import_type: str, rows: list[dict[str, str]], db: Session | None = None, company_id: int | None = None, category_names: set[str] | None = None) -> dict:
    import_key = import_type.lower().strip()
    required_columns = REQUIRED_COLUMNS.get(import_key, [])
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

    available_keys = {_normalize_column_name(key) for key in rows[0].keys()}
    for column_name in required_columns:
        normalized_name = _normalize_column_name(column_name)
        if normalized_name not in available_keys:
            missing_columns.append(column_name)

    for row_index, row in enumerate(rows, start=2):
        normalized_row = _normalize_field_lookup(row)
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
            elif sku.lower() in seen_values["sku"]:
                row_errors.append("Duplicate SKU detected")
            else:
                seen_values["sku"].add(sku.lower())
            if category_name and category_names is not None and category_name.lower() not in {name.lower() for name in category_names}:
                row_errors.append("Category must match an existing category in this company")
            if not category_name:
                row_errors.append("Category is required")
            try:
                price_value = float(unit_price)
                if not math.isfinite(price_value):
                    row_errors.append("Unit Price must be a valid number")
                elif price_value <= 0:
                    row_errors.append("Price must be greater than zero")
            except ValueError:
                row_errors.append("Unit Price must be a valid number")
            try:
                stock_value = _whole_number(stock_quantity)
                if stock_value < 0:
                    row_errors.append("Stock quantity cannot be negative")
            except ValueError:
                row_errors.append("Stock Quantity must be a whole number")

            if db is not None and company_id is not None and sku:
                existing = db.scalar(
                    select(Product.id).where(
                        Product.company_id == company_id, func.lower(Product.sku) == sku.lower()
                    )
                )
                if existing is not None:
                    row_errors.append("SKU already exists in this company")

        elif import_key == "inventory":
            sku = _get_column_value(normalized_row, "SKU", "Product SKU")
            quantity = _get_column_value(normalized_row, "Quantity", "Current Stock", "Stock Quantity")
            reorder_level = _get_column_value(normalized_row, "Reorder Level", "Reorder Point")
            if not sku:
                row_errors.append("SKU is required")
            elif sku.lower() in seen_values["inventory_sku"]:
                row_errors.append("Duplicate inventory SKU detected")
            else:
                seen_values["inventory_sku"].add(sku.lower())
            try:
                quantity_value = _whole_number(quantity)
                if quantity_value < 0:
                    row_errors.append("Quantity cannot be negative")
            except ValueError:
                quantity_value = None
                row_errors.append("Quantity must be a whole number")
            if reorder_level:
                try:
                    if _whole_number(reorder_level) < 0:
                        row_errors.append("Reorder Level cannot be negative")
                except ValueError:
                    row_errors.append("Reorder Level must be a whole number")
            if db is not None and company_id is not None and sku:
                product = db.scalar(
                    select(Product).where(
                        Product.company_id == company_id, func.lower(Product.sku) == sku.lower()
                    )
                )
                if product is None:
                    row_errors.append("SKU must match an existing product in this company")
                elif quantity_value is not None:
                    inventory = db.scalar(
                        select(Inventory).where(
                            Inventory.company_id == company_id, Inventory.product_id == product.id
                        )
                    )
                    if inventory and quantity_value < inventory.reserved_stock:
                        row_errors.append("Quantity cannot be lower than reserved stock")

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
                    exists = db.scalar(
                        select(Customer.id).where(
                            Customer.company_id == company_id, func.lower(Customer.email) == email.lower()
                        )
                    )
                    if exists is not None:
                        row_errors.append("Customer email already exists in this company")
                if phone:
                    exists = db.scalar(
                        select(Customer.id).where(
                            Customer.company_id == company_id, func.lower(Customer.phone_number) == phone.lower()
                        )
                    )
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
                    qty = _whole_number(quantity)
                    if qty <= 0:
                        row_errors.append("Quantity must be greater than zero")
                except ValueError:
                    row_errors.append("Quantity must be a valid number")
            if not unit_price:
                row_errors.append("Unit Price is required")
            else:
                try:
                    price_value = float(unit_price)
                    if not math.isfinite(price_value):
                        row_errors.append("Unit Price must be a valid number")
                    elif price_value <= 0:
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
                if invoice_number.lower() in seen_values["invoice"]:
                    row_errors.append("Duplicate invoice number detected")
                else:
                    seen_values["invoice"].add(invoice_number.lower())
                if db is not None and company_id is not None:
                    existing = db.scalar(
                        select(Sale.id).where(
                            Sale.company_id == company_id, func.lower(Sale.invoice_number) == invoice_number.lower()
                        )
                    )
                    if existing is not None:
                        row_errors.append("Invoice number already exists in this company")
            if not invoice_number:
                fallback_key = f"{customer_name}|{product_name}|{sale_date}|{quantity}"
                if fallback_key.lower() in seen_values["sales_row"]:
                    row_errors.append("Duplicate sales row detected")
                else:
                    seen_values["sales_row"].add(fallback_key.lower())

        if row_errors:
            issues.extend([_issue(row_index, row, message) for message in row_errors])

    issue_rows = defaultdict(set)
    for issue in issues:
        issue_rows[issue["rowNumber"]].add(issue["errorType"])
    valid_count = sum(1 for row_number in range(2, len(rows) + 2) if row_number not in issue_rows)
    duplicate_count = sum(1 for kinds in issue_rows.values() if "duplicate" in kinds)
    invalid_count = sum(1 for kinds in issue_rows.values() if "invalid" in kinds and "duplicate" not in kinds)
    valid_rows = []
    for row_number, row in enumerate(rows, start=2):
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
        create_notification(
            db,
            company_id=current_user.company_id,
            event_key=f"import:{import_record.id}:failed",
            notification_type="import-failed",
            title="Import failed",
            message=f"{file_name} could not be imported because it contained no valid rows.",
            priority="high",
            resource_type="Import",
            resource_id=import_record.id,
            details={"importType": import_type_key, "filename": file_name, "totalRecords": validation["total_records"], "failedRecords": validation["invalid_count"]},
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
        imported_products: list[Product] = []
        imported_customers: list[Customer] = []
        imported_sales: list[Sale] = []
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
                imported_product = Product(
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
                db.add(imported_product)
                imported_products.append(imported_product)
            elif import_type_key == "customers":
                full_name = _get_column_value(row_map, "Name", "name", "customer name")
                email = _get_column_value(row_map, "Email", "email")
                phone = _get_column_value(row_map, "Phone", "phone")
                imported_customer = Customer(
                        company_id=current_user.company_id,
                        customer_code=f"CUST-{len(rows)}-{inserted + 1}",
                        full_name=full_name,
                        email=email,
                        phone_number=phone,
                        customer_type="retail",
                    )
                db.add(imported_customer)
                imported_customers.append(imported_customer)
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
                imported_sale = Sale(
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
                db.add(imported_sale)
                imported_sales.append(imported_sale)
            inserted += 1
        db.flush()
        for imported_product in imported_products:
            evaluate_inventory_alerts(db, imported_product)
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
        create_notification(
            db,
            company_id=current_user.company_id,
            event_key=f"import:{import_record.id}:completed",
            notification_type="import-completed",
            title="Import completed" if not validation["invalid_count"] else "Import completed with errors",
            message=f"{file_name}: {inserted} records imported, {validation['invalid_count']} failed.",
            priority="medium" if validation["invalid_count"] else "low",
            resource_type="Import",
            resource_id=import_record.id,
            details={"importType": import_type_key, "filename": file_name, "totalRecords": validation["total_records"], "successfulRecords": inserted, "failedRecords": validation["invalid_count"]},
        )
        db.commit()
        run_incremental_checks(
            db,
            current_user,
            sale_ids={sale.id for sale in imported_sales},
            product_ids={product.id for product in imported_products},
            customer_ids={customer.id for customer in imported_customers},
            request=request,
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
            description=f"Import of {import_type_key} from {file_name} failed and was rolled back",
            status="failed",
            after_values={"totalRecords": validation["total_records"], "successfulRecords": 0},
        )
        create_notification(
            db,
            company_id=current_user.company_id,
            event_key=f"import:{import_record.id}:failed",
            notification_type="import-failed",
            title="Import failed",
            message=f"{file_name} failed during processing; changes were rolled back.",
            priority="high",
            resource_type="Import",
            resource_id=import_record.id,
            details={"importType": import_type_key, "filename": file_name, "totalRecords": validation["total_records"]},
        )
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


def create_staged_import(
    db: Session,
    current_user: User,
    import_type: str,
    filename: str,
    rows: list[dict[str, str]],
    request: Request | None = None,
) -> tuple[ImportHistory, dict]:
    import_key = import_type.strip().lower()
    if import_key not in REQUIRED_COLUMNS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported import type")
    categories = None
    if import_key == "products":
        categories = {
            category.name
            for category in db.scalars(select(Category).where(Category.company_id == current_user.company_id)).all()
        }
    summary = validate_csv_rows(
        import_key, rows, db=db, company_id=current_user.company_id, category_names=categories
    )
    record = create_import_history(
        db,
        current_user,
        import_key,
        filename[:255],
        summary["total_records"],
        ImportStatus.UPLOADED.value,
        failed_records=summary["invalid_count"],
        duplicate_records=summary["duplicate_count"],
    )
    db.add(ImportJob(import_id=record.id, source_data=json.dumps(rows, ensure_ascii=False)))
    create_audit_log(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        performed_by=current_user.name,
        entity_type="Import",
        resource_id=record.id,
        entity_name=record.filename,
        action=AuditAction.IMPORT_FILE_UPLOADED,
        request=request,
        description=f"Uploaded {import_key} CSV for validation",
        after_values={"totalRecords": summary["total_records"]},
    )
    db.commit()
    return record, summary


def start_staged_import(
    db: Session,
    current_user: User,
    import_id: int,
    request: Request | None = None,
    *,
    commit: bool = True,
) -> ImportHistory:
    record = get_import_history_record(db, current_user.company_id, import_id)
    if record.status != ImportStatus.UPLOADED.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This import has already been started or cancelled")
    job = db.get(ImportJob, import_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Import data is no longer available")
    record.status = ImportStatus.VALIDATING.value
    job.started_at = datetime.now(timezone.utc)
    create_audit_log(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        performed_by=current_user.name,
        entity_type="Import",
        resource_id=record.id,
        entity_name=record.filename,
        action=AuditAction.IMPORT_STARTED,
        request=request,
        description=f"Started {record.import_type} import",
    )
    create_notification(
        db,
        company_id=current_user.company_id,
        event_key=f"import:{record.id}:started",
        notification_type="import-started",
        title="Import started",
        message=f"{record.filename} is being processed.",
        priority="low",
        resource_type="Import",
        resource_id=record.id,
        details={"importType": record.import_type, "filename": record.filename},
    )
    if commit:
        db.commit()
    return record


def _parse_sale_date(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        parsed = datetime.strptime(value, "%m/%d/%Y")
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _import_one_row(
    db: Session, user: User, import_type: str, row: dict[str, str], row_number: int, import_id: int
) -> tuple[set[int], set[int], set[int]]:
    fields = _normalize_field_lookup(row)
    sale_ids: set[int] = set()
    product_ids: set[int] = set()
    customer_ids: set[int] = set()
    if import_type == "products":
        category_name = _get_column_value(fields, "Category")
        category = db.scalar(
            select(Category).where(
                Category.company_id == user.company_id, func.lower(Category.name) == category_name.lower()
            )
        )
        if category is None:
            raise ValueError("Category must match an existing category in this company")
        quantity = _whole_number(_get_column_value(fields, "Stock Quantity", "Stock"))
        product = Product(
            company_id=user.company_id,
            category_id=category.id,
            name=_get_column_value(fields, "Product Name", "Name"),
            sku=_get_column_value(fields, "SKU"),
            unit_price=float(_get_column_value(fields, "Unit Price", "Price")),
            cost_price=float(_get_column_value(fields, "Unit Price", "Price")),
            stock_quantity=quantity,
            is_out_of_stock=quantity == 0,
            unit_of_measure=_get_column_value(fields, "Unit", "Unit of Measure") or "pcs",
        )
        db.add(product)
        db.flush()
        inventory = ensure_inventory_for_product(db, product)
        if quantity:
            db.add(
                InventoryMovement(
                    inventory_id=inventory.id,
                    movement_type=InventoryMovementType.STOCK_ADDITION,
                    quantity_changed=quantity,
                    previous_quantity=0,
                    updated_quantity=quantity,
                    reason=f"Import {import_id}",
                    performed_by=user.id,
                )
            )
        evaluate_inventory_alerts(db, product)
        product_ids.add(product.id)
    elif import_type == "customers":
        customer = Customer(
            company_id=user.company_id,
            customer_code=f"IMP-{user.company_id}-{import_id}-{row_number}",
            full_name=_get_column_value(fields, "Name", "Customer Name"),
            email=_get_column_value(fields, "Email").lower(),
            phone_number=_get_column_value(fields, "Phone"),
            customer_type="retail",
            created_by=user.id,
        )
        db.add(customer)
        db.flush()
        customer_ids.add(customer.id)
    elif import_type == "inventory":
        sku = _get_column_value(fields, "SKU", "Product SKU")
        product = db.scalar(
            select(Product).where(
                Product.company_id == user.company_id, func.lower(Product.sku) == sku.lower()
            )
        )
        if product is None:
            raise ValueError("SKU must match an existing product in this company")
        inventory = ensure_inventory_for_product(db, product)
        previous = inventory.current_stock
        quantity = _whole_number(_get_column_value(fields, "Quantity", "Current Stock", "Stock Quantity"))
        if quantity < inventory.reserved_stock:
            raise ValueError("Quantity cannot be lower than reserved stock")
        inventory.current_stock = quantity
        inventory.available_stock = max(quantity - inventory.reserved_stock, 0)
        if _get_column_value(fields, "Reorder Level", "Reorder Point"):
            inventory.reorder_level = _whole_number(
                _get_column_value(fields, "Reorder Level", "Reorder Point")
            )
        inventory.stock_status = (
            StockStatus.OUT_OF_STOCK
            if inventory.available_stock <= 0
            else StockStatus.LOW_STOCK
            if inventory.available_stock <= inventory.reorder_level
            else StockStatus.IN_STOCK
        )
        product.stock_quantity = quantity
        product.is_out_of_stock = quantity == 0
        if previous != quantity:
            delta = quantity - previous
            db.add(
                InventoryMovement(
                    inventory_id=inventory.id,
                    movement_type=InventoryMovementType.STOCK_ADDITION
                    if delta > 0
                    else InventoryMovementType.STOCK_REMOVAL,
                    quantity_changed=delta,
                    previous_quantity=previous,
                    updated_quantity=quantity,
                    reason=f"Import {import_id}",
                    performed_by=user.id,
                )
            )
        evaluate_inventory_alerts(db, product)
        product_ids.add(product.id)
    elif import_type == "sales":
        customer_name = _get_column_value(fields, "Customer", "Customer Name")
        product_name = _get_column_value(fields, "Product")
        customer = db.scalar(
            select(Customer).where(
                Customer.company_id == user.company_id,
                func.lower(Customer.full_name) == customer_name.lower(),
            )
        )
        product = db.scalar(
            select(Product).where(
                Product.company_id == user.company_id,
                func.lower(Product.name) == product_name.lower(),
            )
        )
        if customer is None or product is None:
            raise ValueError("Customer and product must exist in this company")
        quantity = _whole_number(_get_column_value(fields, "Quantity"))
        unit_price = float(_get_column_value(fields, "Unit Price", "Price"))
        invoice_number = _get_column_value(fields, "Invoice Number", "Invoice") or f"IMP-{import_id}-{row_number}"
        sale = Sale(
            company_id=user.company_id,
            customer_id=customer.id,
            customer_name=customer.full_name,
            invoice_number=invoice_number,
            sale_date=_parse_sale_date(_get_column_value(fields, "Sale Date", "Date")),
            sales_channel=SalesChannel.IN_STORE,
            payment_method=PaymentMethod.CASH,
            payment_status=PaymentStatus.PAID,
            total_amount=quantity * unit_price,
            created_by=user.id,
        )
        db.add(sale)
        db.flush()
        db.add(
            SaleItem(
                sale_id=sale.id,
                product_id=product.id,
                category_id=product.category_id,
                quantity=quantity,
                unit_price=unit_price,
                discount=0,
                tax=0,
                total=quantity * unit_price,
            )
        )
        apply_sale_stock_change(
            db,
            company_id=user.company_id,
            user=user,
            request=None,
            product=product,
            quantity_delta=-quantity,
            reason=f"Sale {sale.invoice_number}",
        )
        sale_ids.add(sale.id)
        product_ids.add(product.id)
        customer_ids.add(customer.id)
    return sale_ids, product_ids, customer_ids


def run_staged_import(import_id: int) -> None:
    db = SessionLocal()
    imported_sales: set[int] = set()
    imported_products: set[int] = set()
    imported_customers: set[int] = set()
    started = time.monotonic()
    try:
        record = db.get(ImportHistory, import_id)
        job = db.get(ImportJob, import_id)
        if record is None or job is None or record.status not in {
            ImportStatus.VALIDATING.value,
            ImportStatus.PROCESSING.value,
        }:
            return
        user = db.get(User, record.uploaded_by_id) if record.uploaded_by_id else None
        if user is None or user.company_id != record.company_id:
            raise RuntimeError("Import owner is no longer available")
        rows = json.loads(job.source_data)
        processed_ids = json.loads(job.processed_ids or "{}")
        imported_sales.update(processed_ids.get("sales", []))
        imported_products.update(processed_ids.get("products", []))
        imported_customers.update(processed_ids.get("customers", []))
        categories = None
        if record.import_type == "products":
            categories = {
                category.name
                for category in db.scalars(select(Category).where(Category.company_id == record.company_id)).all()
            }
        validation = validate_csv_rows(
            record.import_type,
            rows,
            db=db,
            company_id=record.company_id,
            category_names=categories,
        )
        if validation["missing_columns"]:
            missing_issue = _issue(
                None,
                {},
                f"Missing required columns: {', '.join(validation['missing_columns'])}",
            )
            store_import_errors(db, record, [missing_issue])
            record.status = ImportStatus.FAILED.value
            record.failed_records = len(rows)
            record.completed_at = datetime.now(timezone.utc)
            job.duration_seconds = int(time.monotonic() - started)
            job.processed_records = len(rows)
            job.source_data = "[]"
            create_audit_log(
                db,
                company_id=record.company_id,
                user_id=user.id,
                performed_by=user.name,
                entity_type="Import",
                resource_id=record.id,
                entity_name=record.filename,
                action=AuditAction.IMPORT_FAILED,
                request=None,
                description="Import failed validation because required columns were missing",
                status="failed",
            )
            create_notification(
                db,
                company_id=record.company_id,
                event_key=f"import:{record.id}:failed",
                notification_type="import-failed",
                title="Import failed validation",
                message=f"{record.filename} is missing required CSV columns. Download the error report for details.",
                priority="high",
                resource_type="Import",
                resource_id=record.id,
            )
            db.commit()
            return
        resuming = record.status == ImportStatus.PROCESSING.value
        if not resuming:
            record.total_records = len(rows)
            record.duplicate_records = validation["duplicate_count"]
            record.failed_records = validation["invalid_count"]
            store_import_errors(db, record, validation["issues"])
            job.processed_records = 0
            job.skipped_records = validation["duplicate_count"]
        record.status = ImportStatus.PROCESSING.value
        db.commit()

        rejected_rows = {issue["rowNumber"] for issue in validation["issues"]}
        for row_number, row in enumerate(rows, start=2):
            current = db.get(ImportHistory, import_id)
            if current is not None:
                db.refresh(current)
            if current is None or current.status == ImportStatus.CANCELLED.value:
                return
            if row_number - 1 <= job.processed_records:
                continue
            if row_number not in rejected_rows:
                try:
                    with db.begin_nested():
                        sale_ids, product_ids, customer_ids = _import_one_row(
                            db, user, record.import_type, row, row_number, import_id
                        )
                        db.flush()
                    imported_sales.update(sale_ids)
                    imported_products.update(product_ids)
                    imported_customers.update(customer_ids)
                    job.processed_ids = json.dumps(
                        {
                            "sales": sorted(imported_sales),
                            "products": sorted(imported_products),
                            "customers": sorted(imported_customers),
                        }
                    )
                    record.successful_records += 1
                except (ValueError, IntegrityError, HTTPException) as exc:
                    if isinstance(exc, HTTPException):
                        message = str(exc.detail)
                    elif isinstance(exc, ValueError):
                        message = str(exc)
                    else:
                        message = "Record conflicts with an existing record"
                    record.failed_records += 1
                    db.add(
                        ImportErrorRecord(
                            import_id=import_id,
                            row_number=row_number,
                            error_type="processing",
                            message=message,
                            row_data=json.dumps(row, ensure_ascii=False),
                        )
                    )
            job.processed_records = row_number - 1
            if job.processed_records % 25 == 0 or job.processed_records == len(rows):
                db.commit()

        if imported_sales:
            try:
                imported_customer_ids = db.scalars(
                    select(Sale.customer_id).where(
                        Sale.company_id == record.company_id,
                        Sale.id.in_(imported_sales),
                        Sale.customer_id.is_not(None),
                    )
                ).all()
                for customer_id in imported_customer_ids:
                    sync_customer_purchase_summary(
                        db,
                        company_id=record.company_id,
                        customer_id=customer_id,
                        actor=user,
                    )
                db.commit()
            except Exception:
                logger.exception("Customer purchase summaries failed after import %s", import_id)
                db.rollback()
                record = db.get(ImportHistory, import_id)
                job = db.get(ImportJob, import_id)
                user = db.get(User, record.uploaded_by_id) if record and record.uploaded_by_id else None
                if record is None or job is None or user is None:
                    return

        if imported_sales or imported_products or imported_customers:
            try:
                run_incremental_checks(
                    db,
                    user,
                    sale_ids=imported_sales,
                    product_ids=imported_products,
                    customer_ids=imported_customers,
                )
            except Exception:
                logger.exception("Data-quality checks failed after import %s", import_id)
                db.rollback()
                record = db.get(ImportHistory, import_id)
                job = db.get(ImportJob, import_id)
                user = db.get(User, record.uploaded_by_id) if record and record.uploaded_by_id else None
                if record is None or job is None or user is None:
                    return
        record.status = (
            ImportStatus.COMPLETED_WITH_ERRORS.value
            if record.failed_records or record.duplicate_records
            else ImportStatus.COMPLETED.value
        )
        record.completed_at = datetime.now(timezone.utc)
        job.duration_seconds = int(time.monotonic() - started)
        job.source_data = "[]"
        create_audit_log(
            db,
            company_id=record.company_id,
            user_id=user.id,
            performed_by=user.name,
            entity_type="Import",
            resource_id=record.id,
            entity_name=record.filename,
            action=AuditAction.IMPORT_COMPLETED,
            request=None,
            description=f"Completed {record.import_type} import",
            status="partial" if record.failed_records or record.duplicate_records else "success",
            after_values={
                "totalRecords": record.total_records,
                "successfulRecords": record.successful_records,
                "failedRecords": record.failed_records,
            },
        )
        event_suffix = "completed" if record.status == ImportStatus.COMPLETED.value else "completed-with-errors"
        create_notification(
            db,
            company_id=record.company_id,
            event_key=f"import:{record.id}:{event_suffix}",
            notification_type="import-completed",
            title="Import completed" if not record.failed_records else "Import completed with errors",
            message=(
                f"{record.filename}: {record.successful_records} imported, "
                f"{record.failed_records} failed, {record.duplicate_records} duplicates skipped."
            ),
            priority="low" if not record.failed_records and not record.duplicate_records else "medium",
            resource_type="Import",
            resource_id=record.id,
            details={"importType": record.import_type, "totalRecords": record.total_records},
        )
        db.commit()
    except Exception:
        logger.exception("Import job %s failed", import_id)
        db.rollback()
        record = db.get(ImportHistory, import_id)
        job = db.get(ImportJob, import_id)
        if record and record.status != ImportStatus.CANCELLED.value:
            user = db.get(User, record.uploaded_by_id) if record.uploaded_by_id else None
            processed_ids = json.loads(job.processed_ids or "{}") if job else {}
            if user:
                try:
                    run_incremental_checks(
                        db,
                        user,
                        sale_ids=set(processed_ids.get("sales", [])),
                        product_ids=set(processed_ids.get("products", [])),
                        customer_ids=set(processed_ids.get("customers", [])),
                    )
                except Exception:
                    logger.exception("Data-quality checks failed after failed import %s", import_id)
                    db.rollback()
                    record = db.get(ImportHistory, import_id)
                    job = db.get(ImportJob, import_id)
                    user = db.get(User, record.uploaded_by_id) if record and record.uploaded_by_id else None
                    if record is None or job is None:
                        return
            rows = json.loads(job.source_data) if job and job.source_data else []
            failed_index = job.processed_records if job else 0
            failed_row = rows[failed_index] if failed_index < len(rows) else {}
            db.add(
                ImportErrorRecord(
                    import_id=record.id,
                    row_number=failed_index + 2 if failed_row else None,
                    error_type="processing",
                    message="Import processing stopped unexpectedly; remaining records were not processed.",
                    row_data=json.dumps(failed_row, ensure_ascii=False),
                )
            )
            record.status = ImportStatus.FAILED.value
            skipped = job.skipped_records if job else 0
            record.failed_records = max(record.total_records - record.successful_records - skipped, 0)
            record.completed_at = datetime.now(timezone.utc)
            if job:
                job.processed_records = record.total_records
                job.duration_seconds = int(time.monotonic() - started)
                job.source_data = "[]"
            create_audit_log(
                db,
                company_id=record.company_id,
                user_id=record.uploaded_by_id,
                performed_by=record.uploaded_by,
                entity_type="Import",
                resource_id=record.id,
                entity_name=record.filename,
                action=AuditAction.IMPORT_FAILED,
                request=None,
                description="Import processing failed",
                status="failed",
            )
            create_notification(
                db,
                company_id=record.company_id,
                event_key=f"import:{record.id}:failed",
                notification_type="import-failed",
                title="Import failed",
                message=f"{record.filename} could not be processed. Review the import details and error report.",
                priority="high",
                resource_type="Import",
                resource_id=record.id,
            )
            db.commit()
    finally:
        db.close()


def process_next_import_job() -> bool:
    with SessionLocal() as db:
        import_id = db.scalar(
            select(ImportHistory.id)
            .join(ImportJob, ImportJob.import_id == ImportHistory.id)
            .where(
                ImportHistory.status.in_(
                    [ImportStatus.VALIDATING.value, ImportStatus.PROCESSING.value]
                ),
                ImportJob.source_data != "[]",
            )
            .order_by(ImportHistory.created_at, ImportHistory.id)
            .limit(1)
        )
    if import_id is None:
        return False
    run_staged_import(import_id)
    return True
