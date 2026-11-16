from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.dependencies.auth import require_roles
from src.dependencies.database import get_db
from src.models.inventory import Inventory, InventoryMovementType, StockStatus
from src.models.product import Product
from src.models.user import User, UserRole
from src.schemas.inventory import (
    InventoryAdjustmentCreate,
    InventoryDashboardRead,
    InventoryListRead,
    InventoryMovementListRead,
    InventoryNotificationRead,
    InventoryRead,
    InventoryReorderLevelUpdate,
)
from src.schemas.inventory_forecast import InventoryForecastRead, InventoryForecastRowRead
from src.services.inventory_service import (
    get_inventory_dashboard,
    list_inventory_brands,
    list_inventory,
    list_inventory_movements,
    list_inventory_notifications,
    update_reorder_level,
)
from src.services.inventory_forecast_service import get_inventory_forecast, list_inventory_forecasts
from src.schemas.workflow import ApprovalRequestCreate
from src.services.workflow_service import create_workflow_request

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("", response_model=InventoryListRead)
def list_inventory_route(
    search: str | None = None,
    category_id: int | None = Query(default=None, alias="categoryId"),
    brand: str | None = None,
    stock_status: StockStatus | None = Query(default=None, alias="stockStatus"),
    sort_by: Literal["name", "currentStock", "recentlyUpdated"] = Query(default="recentlyUpdated", alias="sortBy"),
    sort_direction: Literal["asc", "desc"] = Query(default="desc", alias="sortDirection"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100, alias="pageSize"),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return list_inventory(
        db,
        current_user.company_id,
        search=search,
        category_id=category_id,
        brand=brand,
        stock_status=stock_status,
        sort_by=sort_by,
        sort_direction=sort_direction,
        page=page,
        page_size=page_size,
    )


@router.get("/dashboard", response_model=InventoryDashboardRead)
def inventory_dashboard_route(
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return get_inventory_dashboard(db, current_user.company_id)


@router.get("/forecast", response_model=InventoryForecastRead)
def inventory_forecast_route(
    product_id: int | None = Query(default=None, alias="productId"),
    category_id: int | None = Query(default=None, alias="categoryId"),
    supplier: str | None = None,
    search: str | None = None,
    stock_risk: str | None = Query(default=None, alias="stockRisk"),
    reorder_required: bool | None = Query(default=None, alias="reorderRequired"),
    sort_by: Literal["currentStock", "forecastedDemand", "daysRemaining", "recommendedQuantity", "risk"] = Query(default="risk", alias="sortBy"),
    sort_direction: Literal["asc", "desc"] = Query(default="desc", alias="sortDirection"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100, alias="pageSize"),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return list_inventory_forecasts(
        db, current_user.company_id, product_id=product_id, category_id=category_id, supplier=supplier,
        search=search, stock_risk=stock_risk, reorder_required=reorder_required,
        sort_by=sort_by, sort_direction=sort_direction, page=page, page_size=page_size,
    )


@router.get("/recommendations", response_model=InventoryForecastRead)
def inventory_recommendations_route(
    reorder_required: bool = Query(default=True, alias="reorderRequired"),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return list_inventory_forecasts(db, current_user.company_id, reorder_required=reorder_required)


@router.get("/recommendations/{product_id}", response_model=InventoryForecastRowRead)
def inventory_recommendation_route(
    product_id: int,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return get_inventory_forecast(db, current_user.company_id, product_id)


@router.get("/brands", response_model=list[str])
def list_inventory_brands_route(
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return list_inventory_brands(db, current_user.company_id)


@router.get("/movements", response_model=InventoryMovementListRead)
def list_inventory_movements_route(
    product_id: int | None = Query(default=None, alias="productId"),
    movement_type: InventoryMovementType | None = Query(default=None, alias="movementType"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100, alias="pageSize"),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return list_inventory_movements(
        db,
        current_user.company_id,
        product_id=product_id,
        movement_type=movement_type,
        page=page,
        page_size=page_size,
    )


@router.post("/adjustments", status_code=202)
def adjust_inventory_route(
    payload: InventoryAdjustmentCreate,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN)),
    db: Session = Depends(get_db),
):
    product = db.scalar(
        select(Product).where(Product.id == payload.product_id, Product.company_id == current_user.company_id)
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    inventory = db.scalar(
        select(Inventory).where(
            Inventory.product_id == payload.product_id,
            Inventory.company_id == current_user.company_id,
        )
    )
    current_quantity = inventory.current_stock if inventory else product.stock_quantity
    available_quantity = inventory.available_stock if inventory else current_quantity
    target_quantity = current_quantity
    if payload.adjustment_type == "stock-addition":
        target_quantity += int(payload.quantity or 0)
    elif payload.adjustment_type == "stock-removal":
        quantity = int(payload.quantity or 0)
        if quantity > available_quantity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Stock out quantity cannot exceed available stock")
        target_quantity -= quantity
    else:
        target_quantity = int(payload.target_quantity or 0)
    if target_quantity == current_quantity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Manual adjustment must change stock quantity")
    return create_workflow_request(
        db,
        current_user,
        ApprovalRequestCreate(
            requestType="stock-adjustment",
            relatedRecordId=payload.product_id,
            requestedChanges={"targetQuantity": target_quantity},
            reason=payload.reason,
            priority="medium",
        ),
        request,
    )


@router.patch("/{product_id}/reorder-level", response_model=InventoryRead)
def update_reorder_level_route(
    product_id: int,
    payload: InventoryReorderLevelUpdate,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN)),
    db: Session = Depends(get_db),
):
    return update_reorder_level(db, current_user, product_id, payload, request)


@router.get("/notifications", response_model=list[InventoryNotificationRead])
def list_inventory_notifications_route(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN)),
    db: Session = Depends(get_db),
):
    return list_inventory_notifications(db, current_user.company_id, limit=limit)
