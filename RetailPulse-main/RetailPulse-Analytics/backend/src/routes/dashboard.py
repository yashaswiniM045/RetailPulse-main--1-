from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.dependencies.auth import require_roles
from src.dependencies.database import get_db
from src.models.sale import PaymentMethod, SalesChannel
from src.models.user import User
from src.models.user import UserRole
from src.schemas.dashboard import DashboardAnalyticsRead, DashboardFiltersRead, DashboardPaginatedRead, DashboardSummaryRead
from src.services.audit_service import AuditAction, create_audit_log
from src.services.dashboard_service import (
    export_dashboard_csv,
    export_dashboard_pdf,
    get_dashboard_analytics,
    get_dashboard_filters,
    get_dashboard_summary,
    list_dashboard_category_products,
    list_dashboard_kpi_records,
    list_dashboard_product_transactions,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryRead)
def dashboard_summary_route(
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return get_dashboard_summary(db, current_user.company_id)


@router.get("/filters", response_model=DashboardFiltersRead)
def dashboard_filters_route(
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return get_dashboard_filters(db, current_user.company_id)


@router.get("/analytics", response_model=DashboardAnalyticsRead)
def dashboard_analytics_route(
    request: Request,
    date_grain: Literal["daily", "weekly", "monthly"] = Query(default="daily", alias="dateGrain"),
    start_date: datetime | None = Query(default=None, alias="startDate"),
    end_date: datetime | None = Query(default=None, alias="endDate"),
    product_id: int | None = Query(default=None, alias="productId"),
    category_id: int | None = Query(default=None, alias="categoryId"),
    brand: str | None = None,
    sales_channel: SalesChannel | None = Query(default=None, alias="salesChannel"),
    payment_method: PaymentMethod | None = Query(default=None, alias="paymentMethod"),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    if any((start_date, end_date, product_id, category_id, brand, sales_channel, payment_method)):
        create_audit_log(
            db,
            company_id=current_user.company_id,
            user_id=current_user.id,
            performed_by=current_user.name,
            entity_type="Dashboard",
            entity_name="Filters",
            action=AuditAction.DASHBOARD_FILTERS_APPLIED,
            request=request,
        )
    else:
        create_audit_log(
            db,
            company_id=current_user.company_id,
            user_id=current_user.id,
            performed_by=current_user.name,
            entity_type="Dashboard",
            entity_name="Main",
            action=AuditAction.DASHBOARD_VIEWED,
            request=request,
        )

    payload = get_dashboard_analytics(
        db,
        current_user.company_id,
        date_grain=date_grain,
        start_date=start_date,
        end_date=end_date,
        product_id=product_id,
        category_id=category_id,
        brand=brand,
        sales_channel=sales_channel,
        payment_method=payment_method,
    )
    db.commit()
    return payload


@router.get("/drilldown/kpi", response_model=DashboardPaginatedRead)
def dashboard_kpi_drilldown_route(
    kpi_key: str = Query(alias="kpiKey"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100, alias="pageSize"),
    start_date: datetime | None = Query(default=None, alias="startDate"),
    end_date: datetime | None = Query(default=None, alias="endDate"),
    product_id: int | None = Query(default=None, alias="productId"),
    category_id: int | None = Query(default=None, alias="categoryId"),
    brand: str | None = None,
    sales_channel: SalesChannel | None = Query(default=None, alias="salesChannel"),
    payment_method: PaymentMethod | None = Query(default=None, alias="paymentMethod"),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return list_dashboard_kpi_records(
        db,
        current_user.company_id,
        kpi_key=kpi_key,
        page=page,
        page_size=page_size,
        start_date=start_date,
        end_date=end_date,
        product_id=product_id,
        category_id=category_id,
        brand=brand,
        sales_channel=sales_channel,
        payment_method=payment_method,
    )


@router.get("/drilldown/category/{category_id}/products", response_model=DashboardPaginatedRead)
def dashboard_category_drilldown_route(
    category_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100, alias="pageSize"),
    start_date: datetime | None = Query(default=None, alias="startDate"),
    end_date: datetime | None = Query(default=None, alias="endDate"),
    brand: str | None = None,
    sales_channel: SalesChannel | None = Query(default=None, alias="salesChannel"),
    payment_method: PaymentMethod | None = Query(default=None, alias="paymentMethod"),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return list_dashboard_category_products(
        db,
        current_user.company_id,
        category_id=category_id,
        page=page,
        page_size=page_size,
        start_date=start_date,
        end_date=end_date,
        brand=brand,
        sales_channel=sales_channel,
        payment_method=payment_method,
    )


@router.get("/drilldown/product/{product_id}/transactions", response_model=DashboardPaginatedRead)
def dashboard_product_drilldown_route(
    product_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100, alias="pageSize"),
    start_date: datetime | None = Query(default=None, alias="startDate"),
    end_date: datetime | None = Query(default=None, alias="endDate"),
    sales_channel: SalesChannel | None = Query(default=None, alias="salesChannel"),
    payment_method: PaymentMethod | None = Query(default=None, alias="paymentMethod"),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return list_dashboard_product_transactions(
        db,
        current_user.company_id,
        product_id=product_id,
        page=page,
        page_size=page_size,
        start_date=start_date,
        end_date=end_date,
        sales_channel=sales_channel,
        payment_method=payment_method,
    )


@router.get("/export/csv")
def dashboard_export_csv_route(
    request: Request,
    date_grain: Literal["daily", "weekly", "monthly"] = Query(default="daily", alias="dateGrain"),
    start_date: datetime | None = Query(default=None, alias="startDate"),
    end_date: datetime | None = Query(default=None, alias="endDate"),
    product_id: int | None = Query(default=None, alias="productId"),
    category_id: int | None = Query(default=None, alias="categoryId"),
    brand: str | None = None,
    sales_channel: SalesChannel | None = Query(default=None, alias="salesChannel"),
    payment_method: PaymentMethod | None = Query(default=None, alias="paymentMethod"),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    analytics = get_dashboard_analytics(
        db,
        current_user.company_id,
        date_grain=date_grain,
        start_date=start_date,
        end_date=end_date,
        product_id=product_id,
        category_id=category_id,
        brand=brand,
        sales_channel=sales_channel,
        payment_method=payment_method,
    )
    create_audit_log(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        performed_by=current_user.name,
        entity_type="Dashboard",
        entity_name="Analytics Report",
        action=AuditAction.DASHBOARD_REPORT_EXPORTED,
        request=request,
        export_type="csv",
    )
    db.commit()
    payload = export_dashboard_csv(analytics)
    return Response(
        content=payload,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="dashboard-report.csv"'},
    )


@router.get("/export/pdf")
def dashboard_export_pdf_route(
    request: Request,
    date_grain: Literal["daily", "weekly", "monthly"] = Query(default="daily", alias="dateGrain"),
    start_date: datetime | None = Query(default=None, alias="startDate"),
    end_date: datetime | None = Query(default=None, alias="endDate"),
    product_id: int | None = Query(default=None, alias="productId"),
    category_id: int | None = Query(default=None, alias="categoryId"),
    brand: str | None = None,
    sales_channel: SalesChannel | None = Query(default=None, alias="salesChannel"),
    payment_method: PaymentMethod | None = Query(default=None, alias="paymentMethod"),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    analytics = get_dashboard_analytics(
        db,
        current_user.company_id,
        date_grain=date_grain,
        start_date=start_date,
        end_date=end_date,
        product_id=product_id,
        category_id=category_id,
        brand=brand,
        sales_channel=sales_channel,
        payment_method=payment_method,
    )
    create_audit_log(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        performed_by=current_user.name,
        entity_type="Dashboard",
        entity_name="Analytics Report",
        action=AuditAction.DASHBOARD_REPORT_EXPORTED,
        request=request,
        export_type="pdf",
    )
    db.commit()
    payload = export_dashboard_pdf(analytics)
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="dashboard-report.pdf"'},
    )