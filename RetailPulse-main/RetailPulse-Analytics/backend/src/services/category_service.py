from fastapi import HTTPException, Request, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from src.models.category import Category, CategoryStatus
from src.models.product import Product
from src.models.user import User
from src.schemas.category import CategoryUpsert
from src.services.audit_service import AuditAction, create_audit_log


def _category_payload(category: Category, product_count: int) -> dict:
    return {
        "id": category.id,
        "name": category.name,
        "description": category.description,
        "status": category.status.value if hasattr(category.status, "value") else category.status,
        "productCount": product_count,
        "createdAt": category.created_at,
        "updatedAt": category.updated_at,
    }


def _get_category_for_company(db: Session, company_id: int, category_id: int) -> Category:
    category = db.scalar(select(Category).where(and_(Category.id == category_id, Category.company_id == company_id)))
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category


def _category_name_exists(db: Session, company_id: int, name: str, exclude_id: int | None = None) -> bool:
    statement = select(Category.id).where(
        and_(Category.company_id == company_id, func.lower(Category.name) == name.lower())
    )
    if exclude_id is not None:
        statement = statement.where(Category.id != exclude_id)
    return db.scalar(statement) is not None


def list_categories(
    db: Session,
    company_id: int,
    search: str | None = None,
    status_filter: CategoryStatus | None = None,
) -> list[dict]:
    statement = (
        select(Category, func.count(Product.id).label("product_count"))
        .outerjoin(Product, Product.category_id == Category.id)
        .where(Category.company_id == company_id)
        .group_by(Category.id)
        .order_by(Category.created_at.desc())
    )
    if search:
        statement = statement.where(Category.name.ilike(f"%{search.strip()}%"))
    if status_filter:
        statement = statement.where(Category.status == status_filter)

    rows = db.execute(statement).all()
    return [_category_payload(category, int(product_count)) for category, product_count in rows]


def get_category(db: Session, company_id: int, category_id: int) -> dict:
    category = _get_category_for_company(db, company_id, category_id)
    product_count = db.scalar(select(func.count(Product.id)).where(Product.category_id == category.id)) or 0
    return _category_payload(category, int(product_count))


def create_category(db: Session, current_user: User, payload: CategoryUpsert, request: Request) -> dict:
    name = payload.category_name.strip()
    if _category_name_exists(db, current_user.company_id, name):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Category name already exists")

    category = Category(
        company_id=current_user.company_id,
        name=name,
        description=payload.description.strip() or None,
        status=CategoryStatus(payload.status),
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    create_audit_log(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        performed_by=current_user.name,
        entity_type="Category",
        entity_name=category.name,
        action=AuditAction.CATEGORY_CREATED,
        request=request,
    )
    db.commit()
    return _category_payload(category, 0)


def update_category(db: Session, current_user: User, category_id: int, payload: CategoryUpsert, request: Request) -> dict:
    category = _get_category_for_company(db, current_user.company_id, category_id)
    name = payload.category_name.strip()
    if _category_name_exists(db, current_user.company_id, name, exclude_id=category.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Category name already exists")

    category.name = name
    category.description = payload.description.strip() or None
    category.status = CategoryStatus(payload.status)
    create_audit_log(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        performed_by=current_user.name,
        entity_type="Category",
        entity_name=category.name,
        action=AuditAction.CATEGORY_UPDATED,
        request=request,
    )
    db.commit()
    db.refresh(category)
    product_count = db.scalar(select(func.count(Product.id)).where(Product.category_id == category.id)) or 0
    return _category_payload(category, int(product_count))


def delete_category(db: Session, current_user: User, category_id: int, request: Request) -> None:
    category = _get_category_for_company(db, current_user.company_id, category_id)
    product_count = db.scalar(select(func.count(Product.id)).where(Product.category_id == category.id)) or 0
    if product_count:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category with products cannot be deleted")

    create_audit_log(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        performed_by=current_user.name,
        entity_type="Category",
        entity_name=category.name,
        action=AuditAction.CATEGORY_DELETED,
        request=request,
    )
    db.delete(category)
    db.commit()