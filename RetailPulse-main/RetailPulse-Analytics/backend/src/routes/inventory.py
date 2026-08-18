from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.dependencies.auth import require_roles
from src.dependencies.database import get_db
from src.models.inventory import InventoryMovementType, StockStatus
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
from src.services.inventory_service import (
    adjust_inventory_stock,
    get_inventory_dashboard,
    list_inventory_brands,
    list_inventory,
    list_inventory_movements,
    list_inventory_notifications,
    update_reorder_level,
)

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


@router.post("/adjustments", response_model=InventoryRead)
def adjust_inventory_route(
    payload: InventoryAdjustmentCreate,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN)),
    db: Session = Depends(get_db),
):
    return adjust_inventory_stock(db, current_user, payload, request)


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
