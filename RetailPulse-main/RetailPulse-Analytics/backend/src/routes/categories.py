from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from src.dependencies.auth import require_roles
from src.dependencies.database import get_db
from src.models.category import CategoryStatus
from src.models.user import User, UserRole
from src.schemas.category import CategoryRead, CategoryUpsert
from src.services.category_service import create_category, delete_category, get_category, list_categories, update_category

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryRead])
def list_categories_route(
    search: str | None = None,
    status: CategoryStatus | None = None,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN)),
    db: Session = Depends(get_db),
):
    return list_categories(db, current_user.company_id, search=search, status_filter=status)


@router.get("/{category_id}", response_model=CategoryRead)
def get_category_route(
    category_id: int,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN)),
    db: Session = Depends(get_db),
):
    return get_category(db, current_user.company_id, category_id)


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category_route(
    payload: CategoryUpsert,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN)),
    db: Session = Depends(get_db),
):
    return create_category(db, current_user, payload, request)


@router.put("/{category_id}", response_model=CategoryRead)
def update_category_route(
    category_id: int,
    payload: CategoryUpsert,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN)),
    db: Session = Depends(get_db),
):
    return update_category(db, current_user, category_id, payload, request)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category_route(
    category_id: int,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN)),
    db: Session = Depends(get_db),
):
    delete_category(db, current_user, category_id, request)