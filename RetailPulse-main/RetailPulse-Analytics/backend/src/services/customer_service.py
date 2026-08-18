import csv
import io
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from fastapi import HTTPException, Request, status
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.category import Category
from src.models.company import Company
from src.models.customer import (
    Customer,
    CustomerNotification,
    CustomerNotificationType,
    CustomerSegment,
    CustomerStatus,
    CustomerSegment,
    CustomerTimeline,
    CustomerTimelineType,
)
from src.models.product import Product
from src.models.sale import Sale, SaleItem
from src.models.user import User
from src.schemas.customer import CustomerSortBy, CustomerSortDirection, CustomerUpsert
from src.services.audit_service import AuditAction, create_audit_log


def _to_int(value: object) -> int:
    return int(value or 0)


def _to_float(value: object) -> float:
    return float(value or 0)


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _segment_from_summary(total_orders: int, total_revenue: float) -> CustomerSegment:
    if total_orders <= 1:
        return CustomerSegment.NEW
    if total_revenue >= 10000 or total_orders >= 20:
        return CustomerSegment.VIP
    if total_revenue >= 3000 or total_orders >= 8:
        return CustomerSegment.LOYAL
    return CustomerSegment.REGULAR


def _customer_payload(
    customer: Customer,
    *,
    total_orders: int = 0,
    total_spend: float = 0,
    last_purchase_date: datetime | None = None,
) -> dict:
    return {
        "id": customer.id,
        "customerId": customer.customer_code,
        "fullName": customer.full_name,
        "email": customer.email,
        "phoneNumber": customer.phone_number,
        "dateOfBirth": customer.date_of_birth,
        "gender": customer.gender,
        "addressLine1": customer.address_line1,
        "addressLine2": customer.address_line2,
        "city": customer.city,
        "state": customer.state,
        "country": customer.country,
        "postalCode": customer.postal_code,
        "customerType": customer.customer_type,
        "preferredSalesChannel": customer.preferred_sales_channel,
        "status": customer.status,
        "segment": customer.segment,
        "totalPurchases": total_orders,
        "totalSpend": round(total_spend, 2),
        "lastPurchaseDate": last_purchase_date,
        "customerSince": customer.created_at,
        "updatedAt": customer.updated_at,
    }


def _timeline_payload(item: CustomerTimeline) -> dict:
    return {
        "id": item.id,
        "eventType": item.event_type,
        "title": item.title,
        "description": item.description,
        "timestamp": item.created_at,
    }


def _append_timeline(
    db: Session,
    *,
    company_id: int,
    customer_id: int,
    event_type: CustomerTimelineType,
    title: str,
    description: str | None,
    user_id: int | None,
) -> None:
    db.add(
        CustomerTimeline(
            company_id=company_id,
            customer_id=customer_id,
            event_type=event_type,
            title=title,
            description=description,
            created_by=user_id,
        )
    )


def _create_customer_notification(
    db: Session,
    *,
    company_id: int,
    customer_id: int | None,
    notification_type: CustomerNotificationType,
    message: str,
    user_id: int | None,
) -> None:
    db.add(
        CustomerNotification(
            company_id=company_id,
            customer_id=customer_id,
            notification_type=notification_type,
            message=message,
            created_by=user_id,
        )
    )


def _lock_company_for_customer_code(db: Session, company_id: int) -> None:
    db.scalar(select(Company.id).where(Company.id == company_id).with_for_update())


def _generate_customer_code(db: Session, company_id: int, created_date: date) -> str:
    prefix = f"CUST-{created_date.year}-"
    latest_code = db.scalar(
        select(Customer.customer_code)
        .where(and_(Customer.company_id == company_id, Customer.customer_code.like(f"{prefix}%")))
        .order_by(Customer.customer_code.desc())
        .limit(1)
    )
    next_number = 1
    if latest_code:
        try:
            next_number = int(latest_code.rsplit("-", 1)[1]) + 1
        except (TypeError, ValueError):
            next_number = 1
    return f"{prefix}{next_number:06d}"


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
    return customer


def _assert_unique_customer_fields(
    db: Session,
    *,
    company_id: int,
    email: str,
    phone_number: str,
    exclude_customer_id: int | None = None,
) -> None:
    clauses = [Customer.company_id == company_id, Customer.is_deleted.is_(False)]
    if exclude_customer_id is not None:
        clauses.append(Customer.id != exclude_customer_id)

    duplicate_email = db.scalar(
        select(Customer.id).where(
            *clauses,
            func.lower(Customer.email) == email.lower(),
        )
    )
    if duplicate_email is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate email")

    duplicate_phone = db.scalar(
        select(Customer.id).where(
            *clauses,
            Customer.phone_number == phone_number,
        )
    )
    if duplicate_phone is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate phone number")


def list_customers(
    db: Session,
    company_id: int,
    *,
    search: str | None,
    customer_type: str | None,
    segment_filter: CustomerSegment | None,
    status_filter: CustomerStatus | None,
    city: str | None,
    state: str | None,
    country: str | None,
    registered_from: date | None,
    registered_to: date | None,
    sort_by: CustomerSortBy,
    sort_direction: CustomerSortDirection,
    page: int,
    page_size: int,
) -> dict:
    summary_subquery = (
        select(
            Sale.customer_id.label("customer_id"),
            func.count(func.distinct(Sale.id)).label("total_orders"),
            func.coalesce(func.sum(Sale.total_amount), 0).label("total_spend"),
            func.max(Sale.sale_date).label("last_purchase"),
        )
        .where(Sale.company_id == company_id, Sale.customer_id.is_not(None))
        .group_by(Sale.customer_id)
        .subquery()
    )

    statement = (
        select(Customer, summary_subquery.c.total_orders, summary_subquery.c.total_spend, summary_subquery.c.last_purchase)
        .outerjoin(summary_subquery, summary_subquery.c.customer_id == Customer.id)
        .where(Customer.company_id == company_id, Customer.is_deleted.is_(False))
    )

    if search:
        term = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                Customer.full_name.ilike(term),
                Customer.customer_code.ilike(term),
                Customer.email.ilike(term),
                Customer.phone_number.ilike(term),
            )
        )
    if customer_type:
        statement = statement.where(Customer.customer_type == customer_type)
    if segment_filter:
        statement = statement.where(Customer.segment == segment_filter)
    if status_filter:
        statement = statement.where(Customer.status == status_filter)
    if city:
        statement = statement.where(func.lower(Customer.city) == city.strip().lower())
    if state:
        statement = statement.where(func.lower(Customer.state) == state.strip().lower())
    if country:
        statement = statement.where(func.lower(Customer.country) == country.strip().lower())
    if registered_from:
        statement = statement.where(func.date(Customer.created_at) >= registered_from)
    if registered_to:
        statement = statement.where(func.date(Customer.created_at) <= registered_to)

    desc = sort_direction == "desc"
    if sort_by == "totalSpend":
        statement = statement.order_by(summary_subquery.c.total_spend.desc() if desc else summary_subquery.c.total_spend.asc())
    elif sort_by == "totalOrders":
        statement = statement.order_by(summary_subquery.c.total_orders.desc() if desc else summary_subquery.c.total_orders.asc())
    elif sort_by == "lastPurchase":
        statement = statement.order_by(summary_subquery.c.last_purchase.desc() if desc else summary_subquery.c.last_purchase.asc())
    elif sort_by == "customerSince":
        statement = statement.order_by(Customer.created_at.desc() if desc else Customer.created_at.asc())
    else:
        statement = statement.order_by(Customer.full_name.desc() if desc else Customer.full_name.asc())

    total = _to_int(db.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    rows = db.execute(statement.offset((page - 1) * page_size).limit(page_size)).all()
    total_pages = (total + page_size - 1) // page_size if total else 0

    return {
        "items": [
            _customer_payload(
                customer,
                total_orders=_to_int(total_orders),
                total_spend=_to_float(total_spend),
                last_purchase_date=last_purchase,
            )
            for customer, total_orders, total_spend, last_purchase in rows
        ],
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": total_pages,
    }


def create_customer(db: Session, current_user: User, payload: CustomerUpsert, request: Request) -> dict:
    _assert_unique_customer_fields(
        db,
        company_id=current_user.company_id,
        email=payload.email,
        phone_number=payload.phone_number,
    )
    _lock_company_for_customer_code(db, current_user.company_id)

    customer = Customer(
        company_id=current_user.company_id,
        customer_code=_generate_customer_code(db, current_user.company_id, datetime.now(UTC).date()),
        full_name=payload.full_name,
        email=str(payload.email).lower(),
        phone_number=payload.phone_number,
        date_of_birth=payload.date_of_birth,
        gender=payload.gender,
        address_line1=payload.address_line1,
        address_line2=payload.address_line2,
        city=payload.city,
        state=payload.state,
        country=payload.country,
        postal_code=payload.postal_code,
        customer_type=payload.customer_type,
        preferred_sales_channel=payload.preferred_sales_channel,
        status=payload.status,
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    db.add(customer)
    try:
        db.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Could not create customer due to duplicate values") from exc

    _append_timeline(
        db,
        company_id=current_user.company_id,
        customer_id=customer.id,
        event_type=CustomerTimelineType.REGISTERED,
        title="Customer registered",
        description=f"{customer.full_name} was added as a customer",
        user_id=current_user.id,
    )
    _create_customer_notification(
        db,
        company_id=current_user.company_id,
        customer_id=customer.id,
        notification_type=CustomerNotificationType.NEW_REGISTRATION,
        message=f"New customer registered: {customer.full_name}",
        user_id=current_user.id,
    )
    create_audit_log(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        performed_by=current_user.name,
        entity_type="Customer",
        entity_name=customer.full_name,
        action=AuditAction.CUSTOMER_CREATED,
        request=request,
    )

    db.commit()
    db.refresh(customer)
    return _customer_payload(customer)


def update_customer(db: Session, current_user: User, customer_id: int, payload: CustomerUpsert, request: Request) -> dict:
    customer = _get_customer_for_company(db, current_user.company_id, customer_id)
    _assert_unique_customer_fields(
        db,
        company_id=current_user.company_id,
        email=payload.email,
        phone_number=payload.phone_number,
        exclude_customer_id=customer.id,
    )

    previous_status = customer.status
    customer.full_name = payload.full_name
    customer.email = str(payload.email).lower()
    customer.phone_number = payload.phone_number
    customer.date_of_birth = payload.date_of_birth
    customer.gender = payload.gender
    customer.address_line1 = payload.address_line1
    customer.address_line2 = payload.address_line2
    customer.city = payload.city
    customer.state = payload.state
    customer.country = payload.country
    customer.postal_code = payload.postal_code
    customer.customer_type = payload.customer_type
    customer.preferred_sales_channel = payload.preferred_sales_channel
    customer.status = payload.status
    customer.updated_by = current_user.id

    _append_timeline(
        db,
        company_id=current_user.company_id,
        customer_id=customer.id,
        event_type=CustomerTimelineType.PROFILE_UPDATED,
        title="Profile updated",
        description=f"Customer profile updated by {current_user.name}",
        user_id=current_user.id,
    )

    if previous_status != customer.status:
        if customer.status == CustomerStatus.ACTIVE:
            timeline_type = CustomerTimelineType.REACTIVATED
            action = AuditAction.CUSTOMER_ACTIVATED
        else:
            timeline_type = CustomerTimelineType.DEACTIVATED
            action = AuditAction.CUSTOMER_DEACTIVATED
        _append_timeline(
            db,
            company_id=current_user.company_id,
            customer_id=customer.id,
            event_type=timeline_type,
            title=f"Customer {customer.status.value}",
            description=f"Status changed from {previous_status.value} to {customer.status.value}",
            user_id=current_user.id,
        )
        create_audit_log(
            db,
            company_id=current_user.company_id,
            user_id=current_user.id,
            performed_by=current_user.name,
            entity_type="Customer",
            entity_name=customer.full_name,
            action=action,
            request=request,
        )

    create_audit_log(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        performed_by=current_user.name,
        entity_type="Customer",
        entity_name=customer.full_name,
        action=AuditAction.CUSTOMER_UPDATED,
        request=request,
    )

    db.commit()
    db.refresh(customer)
    return _customer_payload(customer)


def delete_customer(db: Session, current_user: User, customer_id: int, request: Request) -> None:
    customer = _get_customer_for_company(db, current_user.company_id, customer_id)
    customer.is_deleted = True
    customer.status = CustomerStatus.INACTIVE
    customer.updated_by = current_user.id

    create_audit_log(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        performed_by=current_user.name,
        entity_type="Customer",
        entity_name=customer.full_name,
        action=AuditAction.CUSTOMER_DELETED,
        request=request,
    )
    _append_timeline(
        db,
        company_id=current_user.company_id,
        customer_id=customer.id,
        event_type=CustomerTimelineType.STATUS_CHANGED,
        title="Customer deleted",
        description="Customer has been soft deleted",
        user_id=current_user.id,
    )
    db.commit()


def update_customer_status(
    db: Session,
    current_user: User,
    customer_id: int,
    status_value: CustomerStatus,
    request: Request,
) -> dict:
    customer = _get_customer_for_company(db, current_user.company_id, customer_id)
    previous_status = customer.status
    customer.status = status_value
    customer.updated_by = current_user.id

    if previous_status != status_value:
        event_type = CustomerTimelineType.REACTIVATED if status_value == CustomerStatus.ACTIVE else CustomerTimelineType.DEACTIVATED
        _append_timeline(
            db,
            company_id=current_user.company_id,
            customer_id=customer.id,
            event_type=event_type,
            title=f"Customer {status_value.value}",
            description=f"Status changed from {previous_status.value} to {status_value.value}",
            user_id=current_user.id,
        )

    create_audit_log(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        performed_by=current_user.name,
        entity_type="Customer",
        entity_name=customer.full_name,
        action=AuditAction.CUSTOMER_STATUS_CHANGED,
        request=request,
    )

    db.commit()
    db.refresh(customer)
    return _customer_payload(customer)


def get_customer(db: Session, company_id: int, customer_id: int) -> dict:
    customer = _get_customer_for_company(db, company_id, customer_id)
    return _customer_payload(customer)


def _compute_customer_purchase_summary(db: Session, company_id: int, customer_id: int) -> dict:
    summary_row = db.execute(
        select(
            func.count(func.distinct(Sale.id)).label("total_orders"),
            func.coalesce(func.sum(Sale.total_amount), 0).label("total_revenue"),
            func.coalesce(func.sum(SaleItem.quantity), 0).label("quantity_purchased"),
            func.min(Sale.sale_date).label("first_purchase"),
            func.max(Sale.sale_date).label("last_purchase"),
        )
        .select_from(Sale)
        .join(SaleItem, SaleItem.sale_id == Sale.id)
        .where(Sale.company_id == company_id, Sale.customer_id == customer_id)
    ).one()

    total_orders = _to_int(summary_row.total_orders)
    total_revenue = _to_float(summary_row.total_revenue)
    quantity_purchased = _to_int(summary_row.quantity_purchased)
    first_purchase = summary_row.first_purchase
    last_purchase = summary_row.last_purchase
    avg_order_value = total_revenue / total_orders if total_orders > 0 else 0

    frequency_days = 0.0
    if total_orders > 1 and first_purchase and last_purchase and last_purchase > first_purchase:
        frequency_days = (last_purchase - first_purchase).total_seconds() / 86400 / (total_orders - 1)

    favorite_product_row = db.execute(
        select(Product.id, Product.name, func.coalesce(func.sum(SaleItem.quantity), 0).label("qty"))
        .select_from(Sale)
        .join(SaleItem, SaleItem.sale_id == Sale.id)
        .join(Product, Product.id == SaleItem.product_id)
        .where(Sale.company_id == company_id, Sale.customer_id == customer_id)
        .group_by(Product.id, Product.name)
        .order_by(func.sum(SaleItem.quantity).desc(), Product.name.asc())
        .limit(1)
    ).first()

    favorite_category_row = db.execute(
        select(Category.id, Category.name, func.coalesce(func.sum(SaleItem.quantity), 0).label("qty"))
        .select_from(Sale)
        .join(SaleItem, SaleItem.sale_id == Sale.id)
        .join(Category, Category.id == SaleItem.category_id)
        .where(Sale.company_id == company_id, Sale.customer_id == customer_id)
        .group_by(Category.id, Category.name)
        .order_by(func.sum(SaleItem.quantity).desc(), Category.name.asc())
        .limit(1)
    ).first()

    frequent_products = db.execute(
        select(
            Product.id,
            Product.name,
            func.coalesce(func.sum(SaleItem.quantity), 0).label("quantity"),
            func.coalesce(func.sum(SaleItem.total), 0).label("revenue"),
        )
        .select_from(Sale)
        .join(SaleItem, SaleItem.sale_id == Sale.id)
        .join(Product, Product.id == SaleItem.product_id)
        .where(Sale.company_id == company_id, Sale.customer_id == customer_id)
        .group_by(Product.id, Product.name)
        .order_by(func.sum(SaleItem.quantity).desc(), Product.name.asc())
        .limit(10)
    ).all()

    recent_transactions = db.execute(
        select(Sale.id, Sale.invoice_number, Sale.sale_date, Sale.total_amount, Sale.sales_channel, Sale.payment_method)
        .where(Sale.company_id == company_id, Sale.customer_id == customer_id)
        .order_by(Sale.sale_date.desc())
        .limit(10)
    ).all()

    return {
        "totalOrders": total_orders,
        "totalRevenue": total_revenue,
        "quantityPurchased": quantity_purchased,
        "averageOrderValue": avg_order_value,
        "firstPurchaseDate": first_purchase,
        "lastPurchaseDate": last_purchase,
        "purchaseFrequencyDays": frequency_days,
        "favoriteProduct": {
            "id": favorite_product_row[0] if favorite_product_row else None,
            "name": favorite_product_row[1] if favorite_product_row else None,
        },
        "favoriteCategory": {
            "id": favorite_category_row[0] if favorite_category_row else None,
            "name": favorite_category_row[1] if favorite_category_row else None,
        },
        "frequentlyPurchasedProducts": [
            {
                "productId": product_id,
                "productName": product_name,
                "quantity": _to_int(quantity),
                "revenue": _to_float(revenue),
            }
            for product_id, product_name, quantity, revenue in frequent_products
        ],
        "recentTransactions": [
            {
                "saleId": sale_id,
                "invoiceNumber": invoice_number,
                "saleDate": sale_date,
                "totalAmount": _to_float(total_amount),
                "salesChannel": sales_channel,
                "paymentMethod": payment_method,
            }
            for sale_id, invoice_number, sale_date, total_amount, sales_channel, payment_method in recent_transactions
        ],
        "segment": _segment_from_summary(total_orders, total_revenue),
    }


def sync_customer_purchase_summary(
    db: Session,
    *,
    company_id: int,
    customer_id: int,
    actor: User | None = None,
    request: Request | None = None,
) -> None:
    customer = db.scalar(select(Customer).where(Customer.company_id == company_id, Customer.id == customer_id))
    if customer is None:
        return

    summary_data = _compute_customer_purchase_summary(db, company_id, customer_id)
    summary = customer.purchase_summary
    if summary is None:
        from src.models.customer import CustomerPurchaseSummary

        summary = CustomerPurchaseSummary(company_id=company_id, customer_id=customer_id)
        db.add(summary)

    previous_total_orders = _to_int(summary.total_orders)
    previous_segment = customer.segment

    summary.total_orders = summary_data["totalOrders"]
    summary.total_revenue = summary_data["totalRevenue"]
    summary.quantity_purchased = summary_data["quantityPurchased"]
    summary.average_order_value = summary_data["averageOrderValue"]
    summary.first_purchase_at = summary_data["firstPurchaseDate"]
    summary.last_purchase_at = summary_data["lastPurchaseDate"]
    summary.purchase_frequency_days = summary_data["purchaseFrequencyDays"]
    summary.favorite_product_id = summary_data["favoriteProduct"]["id"]
    summary.favorite_category_id = summary_data["favoriteCategory"]["id"]
    customer.segment = summary_data["segment"]

    if previous_total_orders == 0 and summary.total_orders > 0:
        _append_timeline(
            db,
            company_id=company_id,
            customer_id=customer_id,
            event_type=CustomerTimelineType.FIRST_PURCHASE,
            title="First purchase",
            description=f"{customer.full_name} completed first purchase",
            user_id=actor.id if actor else None,
        )
        _create_customer_notification(
            db,
            company_id=company_id,
            customer_id=customer_id,
            notification_type=CustomerNotificationType.FIRST_PURCHASE,
            message=f"First purchase recorded for {customer.full_name}",
            user_id=actor.id if actor else None,
        )

    if summary.total_orders > 0 and summary.average_order_value >= 1000:
        _append_timeline(
            db,
            company_id=company_id,
            customer_id=customer_id,
            event_type=CustomerTimelineType.LARGE_PURCHASE,
            title="Large purchase detected",
            description=f"Average order value reached {summary.average_order_value:.2f}",
            user_id=actor.id if actor else None,
        )

    if previous_segment != customer.segment and customer.segment == CustomerSegment.VIP:
        _create_customer_notification(
            db,
            company_id=company_id,
            customer_id=customer_id,
            notification_type=CustomerNotificationType.VIP_STATUS,
            message=f"Customer reached VIP status: {customer.full_name}",
            user_id=actor.id if actor else None,
        )


def get_customer_profile(db: Session, company_id: int, customer_id: int) -> dict:
    customer = _get_customer_for_company(db, company_id, customer_id)
    summary_data = _compute_customer_purchase_summary(db, company_id, customer_id)

    timeline_items = db.scalars(
        select(CustomerTimeline)
        .where(CustomerTimeline.company_id == company_id, CustomerTimeline.customer_id == customer_id)
        .order_by(CustomerTimeline.created_at.desc())
        .limit(100)
    ).all()

    return {
        "customer": _customer_payload(customer),
        "purchaseSummary": {
            **{k: v for k, v in summary_data.items() if k not in {"segment"}},
        },
        "timeline": [_timeline_payload(item) for item in timeline_items],
    }


def list_customer_timeline(db: Session, company_id: int, customer_id: int) -> list[dict]:
    _get_customer_for_company(db, company_id, customer_id)
    items = db.scalars(
        select(CustomerTimeline)
        .where(CustomerTimeline.company_id == company_id, CustomerTimeline.customer_id == customer_id)
        .order_by(CustomerTimeline.created_at.desc())
        .limit(200)
    ).all()
    return [_timeline_payload(item) for item in items]


def get_customer_purchase_history(db: Session, company_id: int, customer_id: int) -> dict:
    _get_customer_for_company(db, company_id, customer_id)
    summary_data = _compute_customer_purchase_summary(db, company_id, customer_id)
    return {k: v for k, v in summary_data.items() if k != "segment"}


def _emit_inactivity_notifications(db: Session, company_id: int) -> None:
    threshold = datetime.now(UTC) - timedelta(days=90)
    rows = db.execute(
        select(Customer.id, Customer.full_name)
        .join(Customer.purchase_summary)
        .where(
            Customer.company_id == company_id,
            Customer.is_deleted.is_(False),
            Customer.purchase_summary.has(),
            Customer.purchase_summary.has(),
        )
    ).all()

    for customer_id, full_name in rows:
        summary = db.scalar(
            select(func.max(Sale.sale_date)).where(Sale.company_id == company_id, Sale.customer_id == customer_id)
        )
        if summary is None or summary >= threshold:
            continue
        existing = db.scalar(
            select(CustomerNotification.id)
            .where(
                CustomerNotification.company_id == company_id,
                CustomerNotification.customer_id == customer_id,
                CustomerNotification.notification_type == CustomerNotificationType.INACTIVITY,
                CustomerNotification.created_at >= datetime.now(UTC) - timedelta(days=7),
            )
            .limit(1)
        )
        if existing is None:
            _create_customer_notification(
                db,
                company_id=company_id,
                customer_id=customer_id,
                notification_type=CustomerNotificationType.INACTIVITY,
                message=f"Customer inactive for over 90 days: {full_name}",
                user_id=None,
            )


def get_customer_analytics(
    db: Session,
    company_id: int,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    base_filters = [Customer.company_id == company_id, Customer.is_deleted.is_(False)]
    if start_date:
        base_filters.append(func.date(Customer.created_at) >= start_date)
    if end_date:
        base_filters.append(func.date(Customer.created_at) <= end_date)

    total_customers = _to_int(db.scalar(select(func.count(Customer.id)).where(*base_filters)) or 0)
    active_customers = _to_int(
        db.scalar(select(func.count(Customer.id)).where(*base_filters, Customer.status == CustomerStatus.ACTIVE)) or 0
    )

    new_cutoff = datetime.now(UTC) - timedelta(days=30)
    new_customers = _to_int(
        db.scalar(
            select(func.count(Customer.id)).where(
                *base_filters,
                Customer.created_at >= new_cutoff,
            )
        )
        or 0
    )

    returning_customers = _to_int(
        db.scalar(
            select(func.count(Customer.id))
            .join(Sale, and_(Sale.customer_id == Customer.id, Sale.company_id == company_id))
            .where(*base_filters)
            .group_by(Customer.id)
            .having(func.count(Sale.id) > 1)
            .subquery()
            .count()
        )
        or 0
    )

    sales_scope = select(Sale).where(Sale.company_id == company_id, Sale.customer_id.is_not(None))
    total_revenue_generated = _to_float(db.scalar(select(func.coalesce(func.sum(Sale.total_amount), 0)).select_from(sales_scope.subquery())) or 0)

    avg_customer_spend = total_revenue_generated / total_customers if total_customers > 0 else 0

    frequency_days = db.execute(
        select(
            func.avg(
                case(
                    (func.count(Sale.id) > 1, (func.extract("epoch", func.max(Sale.sale_date) - func.min(Sale.sale_date)) / 86400) / (func.count(Sale.id) - 1)),
                    else_=0,
                )
            )
        )
        .select_from(Sale)
        .where(Sale.company_id == company_id, Sale.customer_id.is_not(None))
        .group_by(Sale.customer_id)
    ).scalars().first()
    average_purchase_frequency = _to_float(frequency_days or 0)

    growth_rows = db.execute(
        select(func.date(Customer.created_at).label("period"), func.count(Customer.id))
        .where(*base_filters)
        .group_by(func.date(Customer.created_at))
        .order_by(func.date(Customer.created_at).asc())
    ).all()

    new_vs_returning_rows = db.execute(
        select(
            case((func.count(Sale.id) <= 1, "new"), else_="returning").label("label"),
            func.count(Customer.id).label("value"),
        )
        .select_from(Customer)
        .outerjoin(Sale, and_(Sale.customer_id == Customer.id, Sale.company_id == company_id))
        .where(*base_filters)
        .group_by(Customer.id)
    ).all()
    new_vs_returning = {"new": 0, "returning": 0}
    for label, value in new_vs_returning_rows:
        new_vs_returning[label] += _to_int(value)

    revenue_by_type_rows = db.execute(
        select(Customer.customer_type, func.coalesce(func.sum(Sale.total_amount), 0))
        .select_from(Customer)
        .outerjoin(Sale, and_(Sale.customer_id == Customer.id, Sale.company_id == company_id))
        .where(*base_filters)
        .group_by(Customer.customer_type)
    ).all()

    top_customers_rows = db.execute(
        select(Customer.id, Customer.full_name, Customer.customer_code, func.coalesce(func.sum(Sale.total_amount), 0).label("revenue"))
        .select_from(Customer)
        .outerjoin(Sale, and_(Sale.customer_id == Customer.id, Sale.company_id == company_id))
        .where(*base_filters)
        .group_by(Customer.id, Customer.full_name, Customer.customer_code)
        .order_by(func.sum(Sale.total_amount).desc(), Customer.full_name.asc())
        .limit(10)
    ).all()

    purchase_freq_rows = db.execute(
        select(
            Customer.id,
            func.count(Sale.id).label("orders"),
        )
        .select_from(Customer)
        .outerjoin(Sale, and_(Sale.customer_id == Customer.id, Sale.company_id == company_id))
        .where(*base_filters)
        .group_by(Customer.id)
    ).all()
    frequency_buckets = {"1": 0, "2-5": 0, "6-10": 0, "11+": 0}
    for _, orders in purchase_freq_rows:
        order_count = _to_int(orders)
        if order_count <= 1:
            frequency_buckets["1"] += 1
        elif order_count <= 5:
            frequency_buckets["2-5"] += 1
        elif order_count <= 10:
            frequency_buckets["6-10"] += 1
        else:
            frequency_buckets["11+"] += 1

    location_rows = db.execute(
        select(
            func.coalesce(Customer.city, "Unknown").label("city"),
            func.coalesce(Customer.country, "Unknown").label("country"),
            func.count(Customer.id).label("count"),
        )
        .where(*base_filters)
        .group_by(func.coalesce(Customer.city, "Unknown"), func.coalesce(Customer.country, "Unknown"))
        .order_by(func.count(Customer.id).desc())
        .limit(20)
    ).all()

    monthly_acq_rows = db.execute(
        select(func.date_trunc("month", Customer.created_at).label("month"), func.count(Customer.id))
        .where(*base_filters)
        .group_by(func.date_trunc("month", Customer.created_at))
        .order_by(func.date_trunc("month", Customer.created_at).asc())
    ).all()

    spending_distribution_rows = db.execute(
        select(Customer.id, func.coalesce(func.sum(Sale.total_amount), 0).label("spend"))
        .select_from(Customer)
        .outerjoin(Sale, and_(Sale.customer_id == Customer.id, Sale.company_id == company_id))
        .where(*base_filters)
        .group_by(Customer.id)
    ).all()
    spend_buckets = {"0-500": 0, "501-2000": 0, "2001-5000": 0, "5001+": 0}
    for _, spend in spending_distribution_rows:
        amount = _to_float(spend)
        if amount <= 500:
            spend_buckets["0-500"] += 1
        elif amount <= 2000:
            spend_buckets["501-2000"] += 1
        elif amount <= 5000:
            spend_buckets["2001-5000"] += 1
        else:
            spend_buckets["5001+"] += 1

    _emit_inactivity_notifications(db, company_id)

    return {
        "kpis": {
            "totalCustomers": total_customers,
            "activeCustomers": active_customers,
            "newCustomers": new_customers,
            "returningCustomers": returning_customers,
            "averageCustomerSpend": avg_customer_spend,
            "totalRevenueGenerated": total_revenue_generated,
            "averagePurchaseFrequency": average_purchase_frequency,
        },
        "customerGrowthTrend": [
            {"period": period.isoformat(), "value": _to_int(value)} for period, value in growth_rows
        ],
        "newVsReturning": [
            {"label": "new", "value": new_vs_returning["new"]},
            {"label": "returning", "value": new_vs_returning["returning"]},
        ],
        "revenueByCustomerType": [
            {
                "label": customer_type.value if hasattr(customer_type, "value") else str(customer_type),
                "value": _to_float(value),
            }
            for customer_type, value in revenue_by_type_rows
        ],
        "topCustomersByRevenue": [
            {
                "customerId": customer_id,
                "customerCode": customer_code,
                "customerName": customer_name,
                "revenue": _to_float(revenue),
            }
            for customer_id, customer_name, customer_code, revenue in top_customers_rows
        ],
        "purchaseFrequencyDistribution": [
            {"label": label, "value": value} for label, value in frequency_buckets.items()
        ],
        "locationDistribution": [
            {"city": city, "country": country, "value": _to_int(count)}
            for city, country, count in location_rows
        ],
        "monthlyCustomerAcquisition": [
            {"period": month.strftime("%Y-%m"), "value": _to_int(value)} for month, value in monthly_acq_rows
        ],
        "customerSpendingDistribution": [
            {"label": label, "value": value} for label, value in spend_buckets.items()
        ],
    }


def list_customer_notifications(db: Session, company_id: int, limit: int = 20) -> list[dict]:
    rows = db.execute(
        select(CustomerNotification, Customer.full_name)
        .outerjoin(Customer, Customer.id == CustomerNotification.customer_id)
        .where(CustomerNotification.company_id == company_id)
        .order_by(CustomerNotification.created_at.desc())
        .limit(limit)
    ).all()

    return [
        {
            "id": notification.id,
            "customerId": notification.customer_id,
            "customerName": customer_name,
            "notificationType": notification.notification_type.value
            if hasattr(notification.notification_type, "value")
            else str(notification.notification_type),
            "message": notification.message,
            "createdAt": notification.created_at,
        }
        for notification, customer_name in rows
    ]


def list_customer_options(db: Session, company_id: int) -> list[dict]:
    rows = db.execute(
        select(Customer.id, Customer.customer_code, Customer.full_name)
        .where(
            Customer.company_id == company_id,
            Customer.is_deleted.is_(False),
            Customer.status == CustomerStatus.ACTIVE,
        )
        .order_by(Customer.full_name.asc())
    ).all()
    return [
        {"id": customer_id, "customerId": customer_code, "fullName": full_name}
        for customer_id, customer_code, full_name in rows
    ]


def export_customers_list_csv(db: Session, company_id: int) -> bytes:
    rows = db.scalars(
        select(Customer)
        .where(Customer.company_id == company_id, Customer.is_deleted.is_(False))
        .order_by(Customer.created_at.desc())
    ).all()

    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["Customer ID", "Name", "Email", "Phone", "Type", "Status", "City", "State", "Country", "Segment"])
    for item in rows:
        writer.writerow(
            [
                item.customer_code,
                item.full_name,
                item.email,
                item.phone_number,
                item.customer_type.value,
                item.status.value,
                item.city or "",
                item.state or "",
                item.country or "",
                item.segment.value,
            ]
        )
    return stream.getvalue().encode("utf-8")


def export_customer_analytics_csv(analytics_payload: dict) -> bytes:
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["Customer Analytics Report"])
    writer.writerow([])
    writer.writerow(["KPI", "Value"])
    for key, value in analytics_payload["kpis"].items():
        writer.writerow([key, value])
    writer.writerow([])
    writer.writerow(["Top Customers"])
    writer.writerow(["Customer ID", "Customer Code", "Name", "Revenue"])
    for item in analytics_payload["topCustomersByRevenue"]:
        writer.writerow([item["customerId"], item["customerCode"], item["customerName"], item["revenue"]])
    return stream.getvalue().encode("utf-8")


def export_customer_top_customers_csv(analytics_payload: dict) -> bytes:
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["Top Customers by Revenue"])
    writer.writerow(["Customer ID", "Customer Code", "Name", "Revenue"])
    for item in analytics_payload["topCustomersByRevenue"]:
        writer.writerow([item["customerId"], item["customerCode"], item["customerName"], item["revenue"]])
    return stream.getvalue().encode("utf-8")


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


def export_customers_list_pdf(db: Session, company_id: int) -> bytes:
    rows = db.execute(
        select(Customer.customer_code, Customer.full_name, Customer.email, Customer.customer_type, Customer.status)
        .where(Customer.company_id == company_id, Customer.is_deleted.is_(False))
        .order_by(Customer.full_name.asc())
        .limit(120)
    ).all()
    lines = ["Customer List Report", ""]
    for code, name, email, customer_type, status_value in rows:
        lines.append(f"{code} | {name} | {email} | {customer_type.value} | {status_value.value}")
    return _build_simple_pdf(lines)


def export_customer_analytics_pdf(analytics_payload: dict) -> bytes:
    lines = ["Customer Analytics Report", "", "KPIs"]
    for key, value in analytics_payload["kpis"].items():
        lines.append(f"{key}: {value}")
    lines.append("")
    lines.append("Top Customers")
    for row in analytics_payload["topCustomersByRevenue"][:20]:
        lines.append(f"{row['customerCode']} | {row['customerName']} | {row['revenue']:.2f}")
    return _build_simple_pdf(lines)


def export_customer_top_customers_pdf(analytics_payload: dict) -> bytes:
    lines = ["Top Customers by Revenue", ""]
    for row in analytics_payload["topCustomersByRevenue"][:50]:
        lines.append(f"{row['customerCode']} | {row['customerName']} | {row['revenue']:.2f}")
    return _build_simple_pdf(lines)
