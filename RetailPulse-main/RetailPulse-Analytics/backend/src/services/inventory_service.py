from typing import Literal

from fastapi import HTTPException, Request, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from src.models.category import Category
from src.models.inventory import (
    Inventory,
    InventoryMovement,
    InventoryMovementType,
    InventoryNotification,
    InventoryNotificationType,
    StockStatus,
)
from src.models.product import Product
from src.models.user import User
from src.schemas.inventory import InventoryAdjustmentCreate, InventoryReorderLevelUpdate
from src.services.audit_service import AuditAction, create_audit_log


def _resolve_stock_status(available_stock: int, reorder_level: int) -> StockStatus:
    if available_stock <= 0:
        return StockStatus.OUT_OF_STOCK
    if available_stock <= reorder_level:
        return StockStatus.LOW_STOCK
    return StockStatus.IN_STOCK


def _normalize_stock_values(inventory: Inventory) -> None:
    inventory.current_stock = max(inventory.current_stock, 0)
    inventory.reserved_stock = max(inventory.reserved_stock, 0)
    inventory.available_stock = max(inventory.current_stock - inventory.reserved_stock, 0)
    inventory.stock_status = _resolve_stock_status(inventory.available_stock, inventory.reorder_level)


def _ensure_inventory_for_product(db: Session, product: Product) -> Inventory:
    inventory = db.scalar(
        select(Inventory).where(and_(Inventory.company_id == product.company_id, Inventory.product_id == product.id))
    )
    if inventory:
        _normalize_stock_values(inventory)
        return inventory

    inventory = Inventory(
        company_id=product.company_id,
        product_id=product.id,
        current_stock=max(product.stock_quantity, 0),
        reserved_stock=0,
        available_stock=max(product.stock_quantity, 0),
        reorder_level=5,
        stock_status=_resolve_stock_status(max(product.stock_quantity, 0), 5),
    )
    db.add(inventory)
    db.flush()
    return inventory


def ensure_inventory_for_product(db: Session, product: Product) -> Inventory:
    inventory = _ensure_inventory_for_product(db, product)
    _normalize_stock_values(inventory)
    return inventory


def _inventory_payload(inventory: Inventory) -> dict:
    product = inventory.product
    return {
        "id": inventory.id,
        "productId": product.id,
        "productName": product.name,
        "sku": product.sku,
        "category": product.category.name,
        "brand": product.brand,
        "currentStock": inventory.current_stock,
        "reservedStock": inventory.reserved_stock,
        "availableStock": inventory.available_stock,
        "reorderLevel": inventory.reorder_level,
        "stockStatus": inventory.stock_status.value if hasattr(inventory.stock_status, "value") else inventory.stock_status,
        "updatedAt": inventory.updated_at,
    }


def _movement_payload(movement: InventoryMovement) -> dict:
    inventory = movement.inventory
    product = inventory.product
    performer = movement.user.name if movement.user else None
    return {
        "id": movement.id,
        "inventoryId": movement.inventory_id,
        "productId": product.id,
        "productName": product.name,
        "sku": product.sku,
        "movementType": movement.movement_type.value if hasattr(movement.movement_type, "value") else movement.movement_type,
        "previousQuantity": movement.previous_quantity,
        "updatedQuantity": movement.updated_quantity,
        "quantityChanged": movement.quantity_changed,
        "reason": movement.reason,
        "remarks": movement.remarks,
        "performedBy": performer,
        "createdAt": movement.created_at,
    }


def _create_notification(
    db: Session,
    *,
    company_id: int,
    product_id: int,
    notification_type: InventoryNotificationType,
    message: str,
    created_by: int | None,
) -> None:
    db.add(
        InventoryNotification(
            company_id=company_id,
            product_id=product_id,
            notification_type=notification_type,
            message=message,
            created_by=created_by,
        )
    )


def _create_stock_transition_records(
    db: Session,
    *,
    company_id: int,
    user: User | None,
    request: Request | None,
    product: Product,
    previous_status: StockStatus,
    next_status: StockStatus,
) -> list[dict]:
    notifications: list[dict] = []
    if previous_status == next_status:
        return notifications

    if next_status == StockStatus.LOW_STOCK:
        message = f"Product '{product.name}' has reached low stock"
        create_audit_log(
            db,
            company_id=company_id,
            user_id=user.id if user else None,
            performed_by=user.name if user else None,
            entity_type="Product",
            entity_name=product.name,
            action=AuditAction.PRODUCT_REACHED_LOW_STOCK,
            request=request,
        )
        _create_notification(
            db,
            company_id=company_id,
            product_id=product.id,
            notification_type=InventoryNotificationType.LOW_STOCK,
            message=message,
            created_by=user.id if user else None,
        )
        notifications.append({"type": "low-stock", "message": message})

    if next_status == StockStatus.OUT_OF_STOCK:
        message = f"Product '{product.name}' is now out of stock"
        create_audit_log(
            db,
            company_id=company_id,
            user_id=user.id if user else None,
            performed_by=user.name if user else None,
            entity_type="Product",
            entity_name=product.name,
            action=AuditAction.PRODUCT_BECAME_OUT_OF_STOCK,
            request=request,
        )
        _create_notification(
            db,
            company_id=company_id,
            product_id=product.id,
            notification_type=InventoryNotificationType.OUT_OF_STOCK,
            message=message,
            created_by=user.id if user else None,
        )
        notifications.append({"type": "out-of-stock", "message": message})

    return notifications


def _get_product_for_company(db: Session, company_id: int, product_id: int) -> Product:
    product = db.scalar(
        select(Product)
        .options(joinedload(Product.category))
        .where(and_(Product.id == product_id, Product.company_id == company_id))
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


def _get_inventory_for_product(db: Session, company_id: int, product_id: int) -> Inventory:
    product = _get_product_for_company(db, company_id, product_id)
    inventory = _ensure_inventory_for_product(db, product)
    db.refresh(inventory)
    return inventory


def _apply_inventory_change(
    db: Session,
    *,
    inventory: Inventory,
    movement_type: InventoryMovementType,
    quantity_delta: int,
    reason: str,
    remarks: str | None,
    actor: User | None,
    request: Request | None,
) -> list[dict]:
    previous_quantity = inventory.current_stock
    updated_quantity = previous_quantity + quantity_delta
    if updated_quantity < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Stock quantity cannot become negative")

    if quantity_delta < 0 and abs(quantity_delta) > inventory.available_stock:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Stock out quantity cannot exceed available stock")

    previous_status = inventory.stock_status
    inventory.current_stock = updated_quantity
    _normalize_stock_values(inventory)

    product = inventory.product
    product.stock_quantity = inventory.current_stock
    product.is_out_of_stock = inventory.stock_status == StockStatus.OUT_OF_STOCK

    db.add(
        InventoryMovement(
            inventory_id=inventory.id,
            movement_type=movement_type,
            quantity_changed=quantity_delta,
            previous_quantity=previous_quantity,
            updated_quantity=updated_quantity,
            reason=reason.strip(),
            remarks=remarks.strip() if remarks else None,
            performed_by=actor.id if actor else None,
        )
    )

    if movement_type == InventoryMovementType.STOCK_ADDITION:
        action = AuditAction.STOCK_ADDED
    elif movement_type == InventoryMovementType.STOCK_REMOVAL:
        action = AuditAction.STOCK_REMOVED
    elif movement_type == InventoryMovementType.MANUAL_ADJUSTMENT:
        action = AuditAction.STOCK_ADJUSTED
    else:
        action = AuditAction.INVENTORY_UPDATED

    create_audit_log(
        db,
        company_id=inventory.company_id,
        user_id=actor.id if actor else None,
        performed_by=actor.name if actor else None,
        entity_type="Product",
        entity_name=product.name,
        action=action,
        request=request,
    )

    notifications = _create_stock_transition_records(
        db,
        company_id=inventory.company_id,
        user=actor,
        request=request,
        product=product,
        previous_status=previous_status,
        next_status=inventory.stock_status,
    )

    return notifications


def apply_sale_stock_change(
    db: Session,
    *,
    company_id: int,
    user: User,
    request: Request,
    product: Product,
    quantity_delta: int,
    reason: str,
) -> list[dict]:
    inventory = _ensure_inventory_for_product(db, product)
    return _apply_inventory_change(
        db,
        inventory=inventory,
        movement_type=InventoryMovementType.SALE,
        quantity_delta=quantity_delta,
        reason=reason,
        remarks=None,
        actor=user,
        request=request,
    )


def list_inventory(
    db: Session,
    company_id: int,
    *,
    search: str | None = None,
    category_id: int | None = None,
    brand: str | None = None,
    stock_status: StockStatus | None = None,
    sort_by: Literal["name", "currentStock", "recentlyUpdated"] = "recentlyUpdated",
    sort_direction: Literal["asc", "desc"] = "desc",
    page: int = 1,
    page_size: int = 25,
) -> dict:
    statement = (
        select(Inventory)
        .join(Inventory.product)
        .join(Product.category)
        .options(joinedload(Inventory.product).joinedload(Product.category))
        .where(Inventory.company_id == company_id)
    )

    count_statement = (
        select(func.count(Inventory.id))
        .select_from(Inventory)
        .join(Inventory.product)
        .join(Product.category)
        .where(Inventory.company_id == company_id)
    )

    if search:
        term = f"%{search.strip()}%"
        search_clause = or_(Product.name.ilike(term), Product.sku.ilike(term))
        statement = statement.where(search_clause)
        count_statement = count_statement.where(search_clause)

    if category_id:
        category_clause = Product.category_id == category_id
        statement = statement.where(category_clause)
        count_statement = count_statement.where(category_clause)

    if brand:
        brand_clause = Product.brand.ilike(f"%{brand.strip()}%")
        statement = statement.where(brand_clause)
        count_statement = count_statement.where(brand_clause)

    if stock_status:
        status_clause = Inventory.stock_status == stock_status
        statement = statement.where(status_clause)
        count_statement = count_statement.where(status_clause)

    sort_desc = sort_direction == "desc"
    if sort_by == "name":
        statement = statement.order_by(Product.name.desc() if sort_desc else Product.name.asc())
    elif sort_by == "currentStock":
        statement = statement.order_by(Inventory.current_stock.desc() if sort_desc else Inventory.current_stock.asc())
    else:
        statement = statement.order_by(Inventory.updated_at.desc() if sort_desc else Inventory.updated_at.asc())

    total = int(db.scalar(count_statement) or 0)
    total_pages = (total + page_size - 1) // page_size if total else 0
    offset = (page - 1) * page_size

    inventories = db.scalars(statement.offset(offset).limit(page_size)).all()
    return {
        "items": [_inventory_payload(inventory) for inventory in inventories],
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": total_pages,
    }


def list_inventory_movements(
    db: Session,
    company_id: int,
    *,
    product_id: int | None = None,
    movement_type: InventoryMovementType | None = None,
    page: int = 1,
    page_size: int = 25,
) -> dict:
    statement = (
        select(InventoryMovement)
        .join(InventoryMovement.inventory)
        .join(Inventory.product)
        .options(joinedload(InventoryMovement.inventory).joinedload(Inventory.product).joinedload(Product.category), joinedload(InventoryMovement.user))
        .where(Inventory.company_id == company_id)
    )

    count_statement = (
        select(func.count(InventoryMovement.id))
        .select_from(InventoryMovement)
        .join(InventoryMovement.inventory)
        .where(Inventory.company_id == company_id)
    )

    if product_id:
        product_clause = Inventory.product_id == product_id
        statement = statement.where(product_clause)
        count_statement = count_statement.where(product_clause)

    if movement_type:
        movement_clause = InventoryMovement.movement_type == movement_type
        statement = statement.where(movement_clause)
        count_statement = count_statement.where(movement_clause)

    statement = statement.order_by(InventoryMovement.created_at.desc())

    total = int(db.scalar(count_statement) or 0)
    total_pages = (total + page_size - 1) // page_size if total else 0
    offset = (page - 1) * page_size

    movements = db.scalars(statement.offset(offset).limit(page_size)).all()
    return {
        "items": [_movement_payload(movement) for movement in movements],
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": total_pages,
    }


def adjust_inventory_stock(db: Session, current_user: User, payload: InventoryAdjustmentCreate, request: Request) -> dict:
    inventory = _get_inventory_for_product(db, current_user.company_id, payload.product_id)

    quantity_delta = 0
    movement_type = InventoryMovementType.MANUAL_ADJUSTMENT
    remarks = payload.remarks.strip() if payload.remarks else None

    if payload.adjustment_type == "stock-addition":
        movement_type = InventoryMovementType.STOCK_ADDITION
        quantity_delta = int(payload.quantity or 0)
    elif payload.adjustment_type == "stock-removal":
        movement_type = InventoryMovementType.STOCK_REMOVAL
        quantity_delta = -int(payload.quantity or 0)
    else:
        target_quantity = int(payload.target_quantity or 0)
        quantity_delta = target_quantity - inventory.current_stock
        if quantity_delta == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Manual adjustment must change stock quantity")

    notifications = _apply_inventory_change(
        db,
        inventory=inventory,
        movement_type=movement_type,
        quantity_delta=quantity_delta,
        reason=payload.reason,
        remarks=remarks,
        actor=current_user,
        request=request,
    )

    _create_notification(
        db,
        company_id=current_user.company_id,
        product_id=inventory.product_id,
        notification_type=InventoryNotificationType.STOCK_ADJUSTED,
        message=f"Stock adjusted for '{inventory.product.name}' ({quantity_delta:+d})",
        created_by=current_user.id,
    )

    db.commit()
    db.refresh(inventory)
    result = _inventory_payload(inventory)
    result["notifications"] = notifications
    return result


def update_reorder_level(
    db: Session,
    current_user: User,
    product_id: int,
    payload: InventoryReorderLevelUpdate,
    request: Request,
) -> dict:
    inventory = _get_inventory_for_product(db, current_user.company_id, product_id)
    inventory.reorder_level = payload.reorder_level

    previous_status = inventory.stock_status
    _normalize_stock_values(inventory)

    create_audit_log(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        performed_by=current_user.name,
        entity_type="Product",
        entity_name=inventory.product.name,
        action=AuditAction.REORDER_LEVEL_UPDATED,
        request=request,
    )

    notifications = _create_stock_transition_records(
        db,
        company_id=current_user.company_id,
        user=current_user,
        request=request,
        product=inventory.product,
        previous_status=previous_status,
        next_status=inventory.stock_status,
    )

    db.commit()
    db.refresh(inventory)
    result = _inventory_payload(inventory)
    result["notifications"] = notifications
    return result


def get_inventory_dashboard(db: Session, company_id: int) -> dict:
    base_inventory = select(Inventory).where(Inventory.company_id == company_id).subquery()
    total_products = int(db.scalar(select(func.count(base_inventory.c.id))) or 0)
    total_inventory_quantity = int(db.scalar(select(func.coalesce(func.sum(base_inventory.c.current_stock), 0))) or 0)

    low_stock_products = int(
        db.scalar(
            select(func.count(base_inventory.c.id)).where(base_inventory.c.stock_status == StockStatus.LOW_STOCK.value)
        )
        or 0
    )
    out_of_stock_products = int(
        db.scalar(
            select(func.count(base_inventory.c.id)).where(base_inventory.c.stock_status == StockStatus.OUT_OF_STOCK.value)
        )
        or 0
    )

    category_rows = db.execute(
        select(
            Category.name,
            func.coalesce(func.sum(Inventory.current_stock), 0).label("total_quantity"),
            func.count(Inventory.id).label("product_count"),
        )
        .join(Product, Product.category_id == Category.id)
        .join(Inventory, Inventory.product_id == Product.id)
        .where(Inventory.company_id == company_id)
        .group_by(Category.name)
        .order_by(Category.name.asc())
    ).all()

    stock_status_rows = db.execute(
        select(Inventory.stock_status, func.count(Inventory.id).label("count"))
        .where(Inventory.company_id == company_id)
        .group_by(Inventory.stock_status)
    ).all()

    return {
        "totalProducts": total_products,
        "totalInventoryQuantity": total_inventory_quantity,
        "lowStockProducts": low_stock_products,
        "outOfStockProducts": out_of_stock_products,
        "inventoryByCategory": [
            {"category": category, "totalQuantity": int(total_quantity), "productCount": int(product_count)}
            for category, total_quantity, product_count in category_rows
        ],
        "stockStatusDistribution": [
            {
                "status": stock_status.value if hasattr(stock_status, "value") else stock_status,
                "count": int(count),
            }
            for stock_status, count in stock_status_rows
        ],
    }


def list_inventory_notifications(db: Session, company_id: int, limit: int = 20) -> list[dict]:
    rows = db.scalars(
        select(InventoryNotification)
        .options(joinedload(InventoryNotification.product))
        .where(InventoryNotification.company_id == company_id)
        .order_by(InventoryNotification.created_at.desc())
        .limit(limit)
    ).all()

    return [
        {
            "id": row.id,
            "productId": row.product_id,
            "productName": row.product.name if row.product else None,
            "notificationType": row.notification_type.value if hasattr(row.notification_type, "value") else row.notification_type,
            "message": row.message,
            "createdAt": row.created_at,
        }
        for row in rows
    ]


def list_inventory_brands(db: Session, company_id: int) -> list[str]:
    rows = db.scalars(
        select(Product.brand)
        .where(and_(Product.company_id == company_id, Product.brand.is_not(None), Product.brand != ""))
        .distinct()
        .order_by(Product.brand.asc())
    ).all()
    return [brand for brand in rows if brand]
