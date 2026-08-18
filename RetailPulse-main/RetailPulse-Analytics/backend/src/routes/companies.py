from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.dependencies.auth import get_current_user
from src.dependencies.database import get_db
from src.models.user import User
from src.schemas.company import CompanyRead
from src.services.company_service import get_company_by_id

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/me", response_model=CompanyRead)
def get_my_company(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_company_by_id(db, current_user.company_id)
