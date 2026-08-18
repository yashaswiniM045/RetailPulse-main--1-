from fastapi import Request
from sqlalchemy.orm import Session

from src.models.audit_log import AuditLog


class AuditAction:
    COMPANY_REGISTERED = "Company Registered"
    USER_LOGIN = "User Login"
    USER_LOGOUT = "User Logout"
    PASSWORD_CHANGED = "Password Changed"
    CATEGORY_CREATED = "Category Created"
    CATEGORY_UPDATED = "Category Updated"
    CATEGORY_DELETED = "Category Deleted"
    PRODUCT_CREATED = "Product Created"
    PRODUCT_UPDATED = "Product Updated"
    PRODUCT_DELETED = "Product Deleted"
    PRODUCT_ACTIVATED = "Product Activated"
    PRODUCT_DEACTIVATED = "Product Deactivated"
    SALE_CREATED = "Sale Created"
    SALE_UPDATED = "Sale Updated"
    SALE_DELETED = "Sale Deleted"
    SALE_EXPORTED = "Sale Exported"
    INVENTORY_UPDATED = "Inventory Updated"
    PRODUCT_MARKED_OUT_OF_STOCK = "Product Marked Out of Stock"
    STOCK_ADDED = "Stock Added"
    STOCK_REMOVED = "Stock Removed"
    STOCK_ADJUSTED = "Stock Adjusted"
    REORDER_LEVEL_UPDATED = "Reorder Level Updated"
    PRODUCT_REACHED_LOW_STOCK = "Product Reached Low Stock"
    PRODUCT_BECAME_OUT_OF_STOCK = "Product Became Out of Stock"
    DASHBOARD_VIEWED = "Dashboard Viewed"
    DASHBOARD_FILTERS_APPLIED = "Dashboard Filters Applied"
    DASHBOARD_REPORT_EXPORTED = "Report Exported"
    CUSTOMER_CREATED = "Customer Created"
    CUSTOMER_UPDATED = "Customer Updated"
    CUSTOMER_DELETED = "Customer Deleted"
    CUSTOMER_ACTIVATED = "Customer Activated"
    CUSTOMER_DEACTIVATED = "Customer Deactivated"
    CUSTOMER_EXPORTED = "Customer Exported"
    CUSTOMER_STATUS_CHANGED = "Customer Status Changed"
    FORECAST_GENERATED = "Forecast Generated"
    FORECAST_EXPORTED = "Forecast Exported"
    FORECAST_REFRESHED = "Forecast Refreshed"
    INVENTORY_RECOMMENDATION_GENERATED = "Inventory Recommendation Generated"


def create_audit_log(
    db: Session,
    *,
    company_id: int,
    user_id: int | None,
    action: str,
    request: Request | None,
    performed_by: str | None = None,
    entity_type: str | None = None,
    entity_name: str | None = None,
    export_type: str | None = None,
) -> None:
    browser = request.headers.get("user-agent") if request else None
    ip_address = request.client.host if request and request.client else None
    db.add(
        AuditLog(
            company_id=company_id,
            user_id=user_id,
            performed_by=performed_by,
            entity_type=entity_type,
            entity_name=entity_name,
            export_type=export_type,
            action=action,
            ip_address=ip_address,
            browser=browser,
        )
    )
