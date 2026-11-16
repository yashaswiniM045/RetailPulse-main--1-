from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.dependencies.auth import require_roles
from src.dependencies.database import get_db
from src.models.inventory import Inventory
from src.models.product import ProductStatus
from src.models.user import User, UserRole
from src.schemas.product import ProductListRead, ProductRead, ProductStatusUpdate, ProductUpsert
from src.services.product_service import (
    create_product,
    delete_product,
    get_product,
    list_products,
    set_product_status,
    update_product,
)
from src.services.workflow_service import workflow_requires_approval

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=ProductListRead)
def list_products_route(
    search: str | None = None,
    category_id: int | None = None,
    status: ProductStatus | None = None,
    sort_by: Literal["name", "price", "recentlyAdded"] = "recentlyAdded",
    sort_direction: Literal["asc", "desc"] = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100, alias="pageSize"),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN)),
    db: Session = Depends(get_db),
):
    return list_products(
        db,
        current_user.company_id,
        search=search,
        category_id=category_id,
        status_filter=status,
        sort_by=sort_by,
        sort_direction=sort_direction,
        page=page,
        page_size=page_size,
    )


@router.get("/{product_id}", response_model=ProductRead)
def get_product_route(
    product_id: int,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN)),
    db: Session = Depends(get_db),
):
    return get_product(db, current_user.company_id, product_id)


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product_route(
    payload: ProductUpsert,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN)),
    db: Session = Depends(get_db),
):
    return create_product(db, current_user, payload, request)


@router.put("/{product_id}", response_model=ProductRead)
def update_product_route(
    product_id: int,
    payload: ProductUpsert,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN)),
    db: Session = Depends(get_db),
):
    current = get_product(db, current_user.company_id, product_id)
    inventory_stock = db.scalar(
        select(Inventory.current_stock).where(
            Inventory.company_id == current_user.company_id,
            Inventory.product_id == product_id,
        )
    )
    needs_price_approval = (
        (
            float(payload.unit_price) != float(current["unitPrice"])
            or float(payload.cost_price) != float(current["costPrice"])
        )
        and workflow_requires_approval(db, current_user.company_id, "product-price-change")
    )
    needs_stock_approval = (
        payload.stock_quantity != (inventory_stock if inventory_stock is not None else current["stockQuantity"])
        and workflow_requires_approval(db, current_user.company_id, "stock-adjustment")
    )
    needs_deactivation_approval = (
        current["status"] != "inactive"
        and payload.status == "inactive"
        and workflow_requires_approval(db, current_user.company_id, "product-deactivation")
    )
    if needs_price_approval or needs_stock_approval or needs_deactivation_approval:
        raise HTTPException(
            status_code=409,
            detail="Price, stock, and deactivation changes require an approval request. Submit them from Workflows & Approvals.",
        )
    return update_product(db, current_user, product_id, payload, request)


@router.patch("/{product_id}/status", response_model=ProductRead)
def update_product_status_route(
    product_id: int,
    payload: ProductStatusUpdate,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN)),
    db: Session = Depends(get_db),
):
    current = get_product(db, current_user.company_id, product_id)
    if (
        current["status"] != "inactive"
        and payload.status == "inactive"
        and workflow_requires_approval(db, current_user.company_id, "product-deactivation")
    ):
        raise HTTPException(
            status_code=409,
            detail="Product deactivation requires an approval request. Submit it from Workflows & Approvals.",
        )
    return set_product_status(db, current_user, product_id, payload, request)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product_route(
    product_id: int,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN)),
    db: Session = Depends(get_db),
):
    delete_product(db, current_user, product_id, request)