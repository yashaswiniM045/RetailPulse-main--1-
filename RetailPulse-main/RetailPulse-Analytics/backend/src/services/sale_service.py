from datetime import datetime, time
from typing import Literal
import csv
import io

from fastapi import HTTPException, Request, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from src.models.company import Company
from src.models.customer import Customer, CustomerStatus
from src.models.product import Product, ProductStatus
from src.models.sale import PaymentMethod, PaymentStatus, Sale, SaleItem, SalesChannel
from src.models.user import User
from src.schemas.sale import SaleUpsert
from src.services.audit_service import AuditAction, create_audit_log
from src.services.customer_service import sync_customer_purchase_summary
from src.services.forecast_service import refresh_forecasts_for_company
from src.services.inventory_service import apply_sale_stock_change


def _sale_base_query(company_id: int):
    return (
        select(Sale)
        .options(
            joinedload(Sale.creator),
            joinedload(Sale.items).joinedload(SaleItem.product),
            joinedload(Sale.items).joinedload(SaleItem.category),
        )
        .where(Sale.company_id == company_id)
    )


def _sale_item_payload(item: SaleItem, remaining_stock: int) -> dict:
    return {
        "id": item.id,
        "productId": item.product_id,
        "productName": item.product.name,
        "sku": item.product.sku,
        "categoryId": item.category_id,
        "categoryName": item.category.name,
        "quantity": item.quantity,
        "unitPrice": float(item.unit_price),
        "discount": float(item.discount),
        "tax": float(item.tax),
        "total": float(item.total),
        "remainingStock": remaining_stock,
    }


def _sale_payload(sale: Sale, notifications: list[dict] | None = None) -> dict:
    notifications = notifications or []
    subtotal = sum(float(item.quantity) * float(item.unit_price) for item in sale.items)
    discount_total = sum(float(item.discount) for item in sale.items)
    tax_total = sum(float(item.tax) for item in sale.items)
    return {
        "id": sale.id,
        "customerId": sale.customer_id,
        "invoiceNumber": sale.invoice_number,
        "customerName": sale.customer_name,
        "saleDate": sale.sale_date,
        "salesChannel": sale.sales_channel.value if hasattr(sale.sales_channel, "value") else sale.sales_channel,
        "paymentMethod": sale.payment_method.value if hasattr(sale.payment_method, "value") else sale.payment_method,
        "paymentStatus": sale.payment_status.value if hasattr(sale.payment_status, "value") else sale.payment_status,
        "notes": sale.notes,
        "subtotal": subtotal,
        "discountTotal": float(sale.discount_total),
        "taxTotal": float(sale.tax_total),
        "totalAmount": float(sale.total_amount),
        "createdBy": sale.created_by,
        "createdByName": sale.creator.name,
        "createdAt": sale.created_at,
        "updatedAt": sale.updated_at,
        "items": [_sale_item_payload(item, item.product.stock_quantity) for item in sale.items],
        "notifications": notifications,
    }


def _sale_list_payload(sale: Sale) -> dict:
    return {
        "id": sale.id,
        "customerId": sale.customer_id,
        "invoiceNumber": sale.invoice_number,
        "customerName": sale.customer_name,
        "saleDate": sale.sale_date,
        "salesChannel": sale.sales_channel.value if hasattr(sale.sales_channel, "value") else sale.sales_channel,
        "paymentMethod": sale.payment_method.value if hasattr(sale.payment_method, "value") else sale.payment_method,
        "paymentStatus": sale.payment_status.value if hasattr(sale.payment_status, "value") else sale.payment_status,
        "totalAmount": float(sale.total_amount),
        "createdByName": sale.creator.name,
        "itemCount": len(sale.items),
    }


def _get_sale_for_company(db: Session, company_id: int, sale_id: int) -> Sale:
    sale = db.scalar(_sale_base_query(company_id).where(Sale.id == sale_id))
    if sale is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale record not found")
    return sale


def _get_product_for_company(db: Session, company_id: int, product_id: int) -> Product:
    product = db.scalar(
        select(Product)
        .options(joinedload(Product.category))
        .where(and_(Product.id == product_id, Product.company_id == company_id))
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


def _get_customer_for_company(db: Session, company_id: int, customer_id: int) -> Customer:
    customer = db.scalar(
        select(Customer).where(
            Customer.company_id == company_id,
            Customer.id == customer_id,
            Customer.is_deleted.is_(False),
        )
    )
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    if customer.status != CustomerStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Customer is inactive")
    return customer


def _generate_invoice_number(db: Session, company_id: int, sale_date: datetime) -> str:
    year = sale_date.year
    prefix = f"INV-{year}-"
    latest_invoice = db.scalar(
        select(Sale.invoice_number)
        .where(and_(Sale.company_id == company_id, Sale.invoice_number.like(f"{prefix}%")))
        .order_by(Sale.invoice_number.desc())
        .limit(1)
    )
    next_number = 1
    if latest_invoice:
        try:
            next_number = int(latest_invoice.rsplit("-", 1)[1]) + 1
        except (TypeError, ValueError):
            next_number = 1
    return f"{prefix}{next_number:06d}"


def _lock_company_for_invoice_generation(db: Session, company_id: int) -> None:
    db.scalar(select(Company.id).where(Company.id == company_id).with_for_update())


def _apply_sale_item_changes(
    *,
    db: Session,
    company_id: int,
    user: User,
    request: Request,
    sale: Sale,
    items: list,
) -> tuple[float, list[dict]]:
    total_amount = 0.0
    discount_total = 0.0
    tax_total = 0.0
    notifications: list[dict] = []

    for item_payload in items:
        product = _get_product_for_company(db, company_id, item_payload.product_id)
        if product.status != ProductStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product '{product.name}' is inactive and cannot be sold",
            )
        line_subtotal = item_payload.quantity * item_payload.unit_price
        if item_payload.discount > line_subtotal:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Discount cannot exceed total product value for '{product.name}'",
            )

        line_total = line_subtotal - item_payload.discount + item_payload.tax
        total_amount += line_total
        discount_total += item_payload.discount
        tax_total += item_payload.tax

        sale_item = SaleItem(
            sale_id=sale.id,
            product_id=product.id,
            category_id=product.category_id,
            quantity=item_payload.quantity,
            unit_price=item_payload.unit_price,
            discount=item_payload.discount,
            tax=item_payload.tax,
            total=line_total,
        )
        db.add(sale_item)

        movement_notifications = apply_sale_stock_change(
            db,
            company_id=company_id,
            user=user,
            request=request,
            product=product,
            quantity_delta=-item_payload.quantity,
            reason=f"Sale {sale.invoice_number}",
        )
        notifications.extend(movement_notifications)

    return total_amount, notifications, discount_total, tax_total


def list_sales(
    db: Session,
    company_id: int,
    *,
    search: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    category_id: int | None = None,
    sales_channel: SalesChannel | None = None,
    payment_method: PaymentMethod | None = None,
    payment_status: PaymentStatus | None = None,
    sort_by: Literal["date", "invoiceNumber", "totalAmount", "customerName"] = "date",
    sort_direction: Literal["asc", "desc"] = "desc",
    page: int = 1,
    page_size: int = 25,
) -> dict:
    statement = _sale_base_query(company_id)
    count_statement = select(func.count(Sale.id)).where(Sale.company_id == company_id)

    requires_item_join = bool(search or category_id)
    if requires_item_join:
        statement = statement.join(Sale.items).join(SaleItem.product)
        count_statement = (
            select(func.count(func.distinct(Sale.id)))
            .select_from(Sale)
            .join(Sale.items)
            .join(SaleItem.product)
            .where(Sale.company_id == company_id)
        )

    if search:
        term = f"%{search.strip()}%"
        search_clause = or_(Sale.invoice_number.ilike(term), Sale.customer_name.ilike(term), Product.name.ilike(term))
        statement = statement.where(search_clause)
        count_statement = count_statement.where(search_clause)
    if start_date:
        start_clause = Sale.sale_date >= datetime.combine(start_date.date(), time.min)
        statement = statement.where(start_clause)
        count_statement = count_statement.where(start_clause)
    if end_date:
        end_clause = Sale.sale_date <= datetime.combine(end_date.date(), time.max)
        statement = statement.where(end_clause)
        count_statement = count_statement.where(end_clause)
    if category_id:
        category_clause = SaleItem.category_id == category_id
        statement = statement.where(category_clause)
        count_statement = count_statement.where(category_clause)
    if sales_channel:
        channel_clause = Sale.sales_channel == sales_channel
        statement = statement.where(channel_clause)
        count_statement = count_statement.where(channel_clause)
    if payment_method:
        payment_clause = Sale.payment_method == payment_method
        statement = statement.where(payment_clause)
        count_statement = count_statement.where(payment_clause)
    if payment_status:
        payment_status_clause = Sale.payment_status == payment_status
        statement = statement.where(payment_status_clause)
        count_statement = count_statement.where(payment_status_clause)

    if requires_item_join:
        statement = statement.distinct()

    sort_desc = sort_direction == "desc"
    if sort_by == "invoiceNumber":
        statement = statement.order_by(Sale.invoice_number.desc() if sort_desc else Sale.invoice_number.asc())
    elif sort_by == "totalAmount":
        statement = statement.order_by(Sale.total_amount.desc() if sort_desc else Sale.total_amount.asc())
    elif sort_by == "customerName":
        statement = statement.order_by(Sale.customer_name.desc() if sort_desc else Sale.customer_name.asc())
    else:
        statement = statement.order_by(Sale.sale_date.desc() if sort_desc else Sale.sale_date.asc())

    total = int(db.scalar(count_statement) or 0)
    total_pages = (total + page_size - 1) // page_size if total else 0
    offset = (page - 1) * page_size

    sales = db.scalars(statement.offset(offset).limit(page_size)).unique().all()
    return {
        "items": [_sale_list_payload(sale) for sale in sales],
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": total_pages,
    }


def get_sale(db: Session, company_id: int, sale_id: int) -> dict:
    sale = _get_sale_for_company(db, company_id, sale_id)
    return _sale_payload(sale)


def create_sale(db: Session, current_user: User, payload: SaleUpsert, request: Request) -> dict:
    _lock_company_for_invoice_generation(db, current_user.company_id)

    customer_id: int | None = None
    customer_name = payload.customer_name.strip()
    if payload.customer_id:
        customer = _get_customer_for_company(db, current_user.company_id, payload.customer_id)
        customer_id = customer.id
        customer_name = customer.full_name

    sale = Sale(
        company_id=current_user.company_id,
        customer_id=customer_id,
        invoice_number=_generate_invoice_number(db, current_user.company_id, payload.sale_date),
        customer_name=customer_name,
        sale_date=payload.sale_date,
        sales_channel=payload.sales_channel,
        payment_method=payload.payment_method,
        payment_status=payload.payment_status,
        notes=payload.notes.strip() if payload.notes else None,
        discount_total=0,
        tax_total=0,
        total_amount=0,
        created_by=current_user.id,
    )
    db.add(sale)
    try:
        db.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not generate a unique invoice number. Please retry.",
        ) from exc

    total_amount, notifications, discount_total, tax_total = _apply_sale_item_changes(
        db=db,
        company_id=current_user.company_id,
        user=current_user,
        request=request,
        sale=sale,
        items=payload.items,
    )
    sale.total_amount = total_amount
    sale.discount_total = discount_total
    sale.tax_total = tax_total

    create_audit_log(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        performed_by=current_user.name,
        entity_type="Sale",
        entity_name=sale.invoice_number,
        action=AuditAction.SALE_CREATED,
        request=request,
    )

    if sale.customer_id:
        sync_customer_purchase_summary(
            db,
            company_id=current_user.company_id,
            customer_id=sale.customer_id,
            actor=current_user,
            request=request,
        )

    db.commit()
    refresh_forecasts_for_company(
        db,
        company_id=current_user.company_id,
        actor=current_user,
        request=request,
    )
    saved_sale = _get_sale_for_company(db, current_user.company_id, sale.id)
    return _sale_payload(saved_sale, notifications)


def update_sale(db: Session, current_user: User, sale_id: int, payload: SaleUpsert, request: Request) -> dict:
    sale = _get_sale_for_company(db, current_user.company_id, sale_id)
    previous_customer_id = sale.customer_id

    # Restore stock for old items before applying new item set.
    for old_item in sale.items:
        product = _get_product_for_company(db, current_user.company_id, old_item.product_id)
        apply_sale_stock_change(
            db,
            company_id=current_user.company_id,
            user=current_user,
            request=request,
            product=product,
            quantity_delta=old_item.quantity,
            reason=f"Sale {sale.invoice_number} update rollback",
        )

    for old_item in list(sale.items):
        db.delete(old_item)
    db.flush()

    customer_id: int | None = None
    customer_name = payload.customer_name.strip()
    if payload.customer_id:
        customer = _get_customer_for_company(db, current_user.company_id, payload.customer_id)
        customer_id = customer.id
        customer_name = customer.full_name

    sale.customer_id = customer_id
    sale.customer_name = customer_name
    sale.sale_date = payload.sale_date
    sale.sales_channel = payload.sales_channel
    sale.payment_method = payload.payment_method
    sale.payment_status = payload.payment_status
    sale.notes = payload.notes.strip() if payload.notes else None

    total_amount, notifications, discount_total, tax_total = _apply_sale_item_changes(
        db=db,
        company_id=current_user.company_id,
        user=current_user,
        request=request,
        sale=sale,
        items=payload.items,
    )
    sale.total_amount = total_amount
    sale.discount_total = discount_total
    sale.tax_total = tax_total

    create_audit_log(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        performed_by=current_user.name,
        entity_type="Sale",
        entity_name=sale.invoice_number,
        action=AuditAction.SALE_UPDATED,
        request=request,
    )

    if previous_customer_id:
        sync_customer_purchase_summary(
            db,
            company_id=current_user.company_id,
            customer_id=previous_customer_id,
            actor=current_user,
            request=request,
        )
    if sale.customer_id and sale.customer_id != previous_customer_id:
        sync_customer_purchase_summary(
            db,
            company_id=current_user.company_id,
            customer_id=sale.customer_id,
            actor=current_user,
            request=request,
        )
    if sale.customer_id and sale.customer_id == previous_customer_id:
        sync_customer_purchase_summary(
            db,
            company_id=current_user.company_id,
            customer_id=sale.customer_id,
            actor=current_user,
            request=request,
        )

    db.commit()
    refresh_forecasts_for_company(
        db,
        company_id=current_user.company_id,
        actor=current_user,
        request=request,
    )


def export_sale_invoice_csv(db: Session, company_id: int, sale_id: int) -> bytes:
    sale = _get_sale_for_company(db, company_id, sale_id)
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["Invoice Number", sale.invoice_number])
    writer.writerow(["Sale Date", sale.sale_date.isoformat()])
    writer.writerow(["Customer", sale.customer_name])
    writer.writerow(["Payment Method", sale.payment_method.value if hasattr(sale.payment_method, "value") else sale.payment_method])
    writer.writerow(["Payment Status", sale.payment_status.value if hasattr(sale.payment_status, "value") else sale.payment_status])
    writer.writerow(["Salesperson", sale.creator.name])
    writer.writerow([])
    writer.writerow(["Product", "SKU", "Category", "Quantity", "Unit Price", "Discount", "Tax", "Line Total"])
    for item in sale.items:
        writer.writerow([
            item.product.name,
            item.product.sku,
            item.category.name,
            item.quantity,
            float(item.unit_price),
            float(item.discount),
            float(item.tax),
            float(item.total),
        ])
    writer.writerow([])
    writer.writerow(["Subtotal", sum(float(item.quantity) * float(item.unit_price) for item in sale.items)])
    writer.writerow(["Discount", float(sale.discount_total)])
    writer.writerow(["Tax", float(sale.tax_total)])
    writer.writerow(["Grand Total", float(sale.total_amount)])
    return stream.getvalue().encode("utf-8")


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_simple_pdf(lines: list[str]) -> bytes:
    content_lines = []
    y = 800
    for line in lines:
        content_lines.append(f"BT /F1 10 Tf 50 {y} Td ({_escape_pdf_text(line)}) Tj ET")
        y -= 14
    content_stream = "\n".join(content_lines).encode("latin-1", errors="replace")

    objects: list[bytes] = []
    objects.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n")
    objects.append(b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n")
    objects.append(
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n"
    )
    objects.append(b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n")
    objects.append(
        f"5 0 obj << /Length {len(content_stream)} >> stream\n".encode("latin-1")
        + content_stream
        + b"\nendstream endobj\n"
    )

    payload = io.BytesIO()
    payload.write(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(payload.tell())
        payload.write(obj)
    xref_start = payload.tell()
    payload.write(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    payload.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        payload.write(f"{offset:010d} 00000 n \n".encode("latin-1"))
    payload.write(
        (
            "trailer\n"
            f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            "startxref\n"
            f"{xref_start}\n"
            "%%EOF"
        ).encode("latin-1")
    )
    return payload.getvalue()


def export_sale_invoice_pdf(db: Session, company_id: int, sale_id: int) -> bytes:
    sale = _get_sale_for_company(db, company_id, sale_id)
    lines = [
        "Invoice",
        f"Invoice Number: {sale.invoice_number}",
        f"Sale Date: {sale.sale_date.isoformat()}",
        f"Customer: {sale.customer_name}",
        f"Payment Method: {sale.payment_method.value if hasattr(sale.payment_method, 'value') else sale.payment_method}",
        f"Payment Status: {sale.payment_status.value if hasattr(sale.payment_status, 'value') else sale.payment_status}",
        f"Salesperson: {sale.creator.name}",
        "",
        "Items",
    ]
    for item in sale.items:
        lines.append(
            f"{item.product.name} | {item.product.sku} | Qty {item.quantity} | Unit {float(item.unit_price):.2f} | Total {float(item.total):.2f}"
        )
    lines.append("")
    lines.append(f"Subtotal: {sum(float(item.quantity) * float(item.unit_price) for item in sale.items):.2f}")
    lines.append(f"Discount: {float(sale.discount_total):.2f}")
    lines.append(f"Tax: {float(sale.tax_total):.2f}")
    lines.append(f"Grand Total: {float(sale.total_amount):.2f}")
    return _build_simple_pdf(lines)
    saved_sale = _get_sale_for_company(db, current_user.company_id, sale.id)
    return _sale_payload(saved_sale, notifications)


def delete_sale(db: Session, current_user: User, sale_id: int, request: Request) -> None:
    sale = _get_sale_for_company(db, current_user.company_id, sale_id)
    linked_customer_id = sale.customer_id

    for item in sale.items:
        product = _get_product_for_company(db, current_user.company_id, item.product_id)
        apply_sale_stock_change(
            db,
            company_id=current_user.company_id,
            user=current_user,
            request=request,
            product=product,
            quantity_delta=item.quantity,
            reason=f"Sale {sale.invoice_number} deleted",
        )

    create_audit_log(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        performed_by=current_user.name,
        entity_type="Sale",
        entity_name=sale.invoice_number,
        action=AuditAction.SALE_DELETED,
        request=request,
    )

    db.delete(sale)

    if linked_customer_id:
        sync_customer_purchase_summary(
            db,
            company_id=current_user.company_id,
            customer_id=linked_customer_id,
            actor=current_user,
            request=request,
        )

    db.commit()
    refresh_forecasts_for_company(
        db,
        company_id=current_user.company_id,
        actor=current_user,
        request=request,
    )
