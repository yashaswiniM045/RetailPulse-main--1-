from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.dependencies.auth import get_current_user, require_roles
from src.dependencies.database import get_db
from src.models.user import User, UserRole
from src.schemas.user import UserRead, UserSummary
from src.services.user_service import get_company_users

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def get_my_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("", response_model=list[UserSummary])
def list_company_users(
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return get_company_users(db, current_user.company_id)
