from datetime import date

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from src.dependencies.auth import require_roles
from src.dependencies.database import get_db
from src.models.forecast import ForecastPeriod
from src.models.user import User, UserRole
from src.schemas.forecast import (
    ForecastDashboardRead,
    ForecastFilterRead,
    ForecastGenerateRequest,
    ForecastListRead,
    ForecastNotificationRead,
    ForecastSortBy,
    ForecastSortDirection,
)
from src.services.audit_service import AuditAction, create_audit_log
from src.services.forecast_service import (
    export_category_forecast_csv,
    export_forecast_report_csv,
    export_product_forecast_pdf,
    generate_forecasts,
    get_forecast_dashboard,
    list_forecast_filters,
    list_forecast_notifications,
    list_forecasts,
)

router = APIRouter(prefix="/forecasts", tags=["forecasts"])


@router.get("/filters", response_model=ForecastFilterRead)
def forecast_filters_route(
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return list_forecast_filters(db, current_user.company_id)


@router.post("/generate", response_model=ForecastDashboardRead)
def generate_forecasts_route(
    payload: ForecastGenerateRequest,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return generate_forecasts(
        db,
        current_user,
        forecast_period=payload.forecast_period,
        custom_start_date=payload.custom_start_date,
        custom_end_date=payload.custom_end_date,
        force_refresh=payload.force_refresh,
        request=request,
    )


@router.get("/dashboard", response_model=ForecastDashboardRead)
def forecast_dashboard_route(
    forecast_period: ForecastPeriod = Query(default=ForecastPeriod.NEXT_30_DAYS, alias="forecastPeriod"),
    custom_start_date: date | None = Query(default=None, alias="customStartDate"),
    custom_end_date: date | None = Query(default=None, alias="customEndDate"),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return get_forecast_dashboard(
        db,
        current_user.company_id,
        forecast_period=forecast_period,
        custom_start_date=custom_start_date,
        custom_end_date=custom_end_date,
    )


@router.get("/products", response_model=ForecastListRead)
def forecast_products_route(
    forecast_period: ForecastPeriod = Query(default=ForecastPeriod.NEXT_30_DAYS, alias="forecastPeriod"),
    custom_start_date: date | None = Query(default=None, alias="customStartDate"),
    custom_end_date: date | None = Query(default=None, alias="customEndDate"),
    product_id: int | None = Query(default=None, alias="productId"),
    category_id: int | None = Query(default=None, alias="categoryId"),
    brand: str | None = None,
    search: str | None = None,
    sort_by: ForecastSortBy = Query(default="highestPredictedDemand", alias="sortBy"),
    sort_direction: ForecastSortDirection = Query(default="desc", alias="sortDirection"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100, alias="pageSize"),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return list_forecasts(
        db,
        current_user.company_id,
        forecast_period=forecast_period,
        custom_start_date=custom_start_date,
        custom_end_date=custom_end_date,
        product_id=product_id,
        category_id=category_id,
        brand=brand,
        search=search,
        sort_by=sort_by,
        sort_direction=sort_direction,
        page=page,
        page_size=page_size,
    )


@router.get("/notifications", response_model=list[ForecastNotificationRead])
def forecast_notifications_route(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return list_forecast_notifications(db, current_user.company_id, limit)


@router.get("/exports/demand-report/csv")
def export_demand_report_csv_route(
    request: Request,
    forecast_period: ForecastPeriod = Query(default=ForecastPeriod.NEXT_30_DAYS, alias="forecastPeriod"),
    custom_start_date: date | None = Query(default=None, alias="customStartDate"),
    custom_end_date: date | None = Query(default=None, alias="customEndDate"),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    payload = get_forecast_dashboard(
        db,
        current_user.company_id,
        forecast_period=forecast_period,
        custom_start_date=custom_start_date,
        custom_end_date=custom_end_date,
    )
    create_audit_log(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        performed_by=current_user.name,
        entity_type="Forecast",
        entity_name="Demand Forecast Report",
        action=AuditAction.FORECAST_EXPORTED,
        request=request,
        export_type="csv",
    )
    db.commit()
    return Response(
        content=export_forecast_report_csv(payload),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="demand-forecast-report.csv"'},
    )


@router.get("/exports/product-report/pdf")
def export_product_report_pdf_route(
    request: Request,
    forecast_period: ForecastPeriod = Query(default=ForecastPeriod.NEXT_30_DAYS, alias="forecastPeriod"),
    custom_start_date: date | None = Query(default=None, alias="customStartDate"),
    custom_end_date: date | None = Query(default=None, alias="customEndDate"),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    payload = get_forecast_dashboard(
        db,
        current_user.company_id,
        forecast_period=forecast_period,
        custom_start_date=custom_start_date,
        custom_end_date=custom_end_date,
    )
    create_audit_log(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        performed_by=current_user.name,
        entity_type="Forecast",
        entity_name="Product Forecast Report",
        action=AuditAction.FORECAST_EXPORTED,
        request=request,
        export_type="pdf",
    )
    db.commit()
    return Response(
        content=export_product_forecast_pdf(payload),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="product-forecast-report.pdf"'},
    )


@router.get("/exports/category-report/csv")
def export_category_report_csv_route(
    request: Request,
    forecast_period: ForecastPeriod = Query(default=ForecastPeriod.NEXT_30_DAYS, alias="forecastPeriod"),
    custom_start_date: date | None = Query(default=None, alias="customStartDate"),
    custom_end_date: date | None = Query(default=None, alias="customEndDate"),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    payload = get_forecast_dashboard(
        db,
        current_user.company_id,
        forecast_period=forecast_period,
        custom_start_date=custom_start_date,
        custom_end_date=custom_end_date,
    )
    create_audit_log(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        performed_by=current_user.name,
        entity_type="Forecast",
        entity_name="Category Forecast Report",
        action=AuditAction.FORECAST_EXPORTED,
        request=request,
        export_type="csv",
    )
    db.commit()
    return Response(
        content=export_category_forecast_csv(payload),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="category-forecast-report.csv"'},
    )
