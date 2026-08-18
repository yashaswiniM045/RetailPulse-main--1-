from datetime import date

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from src.dependencies.auth import require_roles
from src.dependencies.database import get_db
from src.models.customer import CustomerSegment, CustomerStatus
from src.models.user import User, UserRole
from src.schemas.customer import (
    CustomerAnalyticsRead,
    CustomerListRead,
    CustomerNotificationRead,
    CustomerProfileRead,
    CustomerRead,
    CustomerSortBy,
    CustomerSortDirection,
    CustomerStatusUpdate,
    CustomerTimelineRead,
    CustomerUpsert,
)
from src.services.audit_service import AuditAction, create_audit_log
from src.services.customer_service import (
    create_customer,
    delete_customer,
    export_customer_analytics_csv,
    export_customer_analytics_pdf,
    export_customer_top_customers_csv,
    export_customer_top_customers_pdf,
    export_customers_list_csv,
    export_customers_list_pdf,
    get_customer,
    get_customer_analytics,
    get_customer_profile,
    get_customer_purchase_history,
    list_customer_notifications,
    list_customer_options,
    list_customer_timeline,
    list_customers,
    update_customer,
    update_customer_status,
)

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=CustomerListRead)
def list_customers_route(
    search: str | None = None,
    customer_type: str | None = Query(default=None, alias="customerType"),
    segment_filter: CustomerSegment | None = Query(default=None, alias="segment"),
    status_filter: CustomerStatus | None = Query(default=None, alias="status"),
    city: str | None = None,
    state: str | None = None,
    country: str | None = None,
    registered_from: date | None = Query(default=None, alias="registeredFrom"),
    registered_to: date | None = Query(default=None, alias="registeredTo"),
    sort_by: CustomerSortBy = Query(default="customerSince", alias="sortBy"),
    sort_direction: CustomerSortDirection = Query(default="desc", alias="sortDirection"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100, alias="pageSize"),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return list_customers(
        db,
        current_user.company_id,
        search=search,
        customer_type=customer_type,
        segment_filter=segment_filter,
        status_filter=status_filter,
        city=city,
        state=state,
        country=country,
        registered_from=registered_from,
        registered_to=registered_to,
        sort_by=sort_by,
        sort_direction=sort_direction,
        page=page,
        page_size=page_size,
    )


@router.get("/options")
def list_customer_options_route(
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return list_customer_options(db, current_user.company_id)


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer_route(
    payload: CustomerUpsert,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return create_customer(db, current_user, payload, request)


@router.get("/analytics", response_model=CustomerAnalyticsRead)
def customer_analytics_route(
    start_date: date | None = Query(default=None, alias="startDate"),
    end_date: date | None = Query(default=None, alias="endDate"),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    payload = get_customer_analytics(db, current_user.company_id, start_date=start_date, end_date=end_date)
    db.commit()
    return payload


@router.get("/notifications", response_model=list[CustomerNotificationRead])
def customer_notifications_route(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN)),
    db: Session = Depends(get_db),
):
    return list_customer_notifications(db, current_user.company_id, limit)


@router.get("/id/{customer_id}", response_model=CustomerRead)
@router.get("/{customer_id}", response_model=CustomerRead)
def get_customer_route(
    customer_id: int,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return get_customer(db, current_user.company_id, customer_id)


@router.put("/id/{customer_id}", response_model=CustomerRead)
@router.put("/{customer_id}", response_model=CustomerRead)
def update_customer_route(
    customer_id: int,
    payload: CustomerUpsert,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return update_customer(db, current_user, customer_id, payload, request)


@router.patch("/id/{customer_id}/status", response_model=CustomerRead)
def update_customer_status_route(
    customer_id: int,
    payload: CustomerStatusUpdate,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return update_customer_status(db, current_user, customer_id, payload.status, request)


@router.delete("/id/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer_route(
    customer_id: int,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN)),
    db: Session = Depends(get_db),
):
    delete_customer(db, current_user, customer_id, request)


@router.get("/id/{customer_id}/profile", response_model=CustomerProfileRead)
def customer_profile_route(
    customer_id: int,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return get_customer_profile(db, current_user.company_id, customer_id)


@router.get("/id/{customer_id}/purchase-history")
def customer_purchase_history_route(
    customer_id: int,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return get_customer_purchase_history(db, current_user.company_id, customer_id)


@router.get("/id/{customer_id}/timeline", response_model=list[CustomerTimelineRead])
def customer_timeline_route(
    customer_id: int,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return list_customer_timeline(db, current_user.company_id, customer_id)


@router.get("/exports/list/csv")
def export_customer_list_csv_route(
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    create_audit_log(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        performed_by=current_user.name,
        entity_type="Customer",
        entity_name="Customer List",
        action=AuditAction.CUSTOMER_EXPORTED,
        request=request,
        export_type="csv",
    )
    db.commit()
    return Response(
        content=export_customers_list_csv(db, current_user.company_id),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="customers-list.csv"'},
    )


@router.get("/exports/list/pdf")
def export_customer_list_pdf_route(
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    create_audit_log(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        performed_by=current_user.name,
        entity_type="Customer",
        entity_name="Customer List",
        action=AuditAction.CUSTOMER_EXPORTED,
        request=request,
        export_type="pdf",
    )
    db.commit()
    return Response(
        content=export_customers_list_pdf(db, current_user.company_id),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="customers-list.pdf"'},
    )


@router.get("/exports/analytics/csv")
def export_customer_analytics_csv_route(
    request: Request,
    start_date: date | None = Query(default=None, alias="startDate"),
    end_date: date | None = Query(default=None, alias="endDate"),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    analytics = get_customer_analytics(db, current_user.company_id, start_date=start_date, end_date=end_date)
    create_audit_log(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        performed_by=current_user.name,
        entity_type="Customer",
        entity_name="Customer Analytics",
        action=AuditAction.CUSTOMER_EXPORTED,
        request=request,
        export_type="csv",
    )
    db.commit()
    return Response(
        content=export_customer_analytics_csv(analytics),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="customer-analytics.csv"'},
    )


@router.get("/exports/analytics/pdf")
def export_customer_analytics_pdf_route(
    request: Request,
    start_date: date | None = Query(default=None, alias="startDate"),
    end_date: date | None = Query(default=None, alias="endDate"),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    analytics = get_customer_analytics(db, current_user.company_id, start_date=start_date, end_date=end_date)
    create_audit_log(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        performed_by=current_user.name,
        entity_type="Customer",
        entity_name="Customer Analytics",
        action=AuditAction.CUSTOMER_EXPORTED,
        request=request,
        export_type="pdf",
    )
    db.commit()
    return Response(
        content=export_customer_analytics_pdf(analytics),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="customer-analytics.pdf"'},
    )


@router.get("/exports/top-customers/csv")
def export_customer_top_csv_route(
    request: Request,
    start_date: date | None = Query(default=None, alias="startDate"),
    end_date: date | None = Query(default=None, alias="endDate"),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    analytics = get_customer_analytics(db, current_user.company_id, start_date=start_date, end_date=end_date)
    create_audit_log(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        performed_by=current_user.name,
        entity_type="Customer",
        entity_name="Top Customers",
        action=AuditAction.CUSTOMER_EXPORTED,
        request=request,
        export_type="csv",
    )
    db.commit()
    return Response(
        content=export_customer_top_customers_csv(analytics),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="top-customers.csv"'},
    )


@router.get("/exports/top-customers/pdf")
def export_customer_top_pdf_route(
    request: Request,
    start_date: date | None = Query(default=None, alias="startDate"),
    end_date: date | None = Query(default=None, alias="endDate"),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    analytics = get_customer_analytics(db, current_user.company_id, start_date=start_date, end_date=end_date)
    create_audit_log(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        performed_by=current_user.name,
        entity_type="Customer",
        entity_name="Top Customers",
        action=AuditAction.CUSTOMER_EXPORTED,
        request=request,
        export_type="pdf",
    )
    db.commit()
    return Response(
        content=export_customer_top_customers_pdf(analytics),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="top-customers.pdf"'},
    )
