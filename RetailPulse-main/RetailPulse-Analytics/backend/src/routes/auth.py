from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from src.dependencies.auth import get_current_user
from src.dependencies.database import get_db
from src.models.user import User
from src.schemas.auth import AuthResponse, ChangePasswordRequest, LoginRequest, RefreshTokenRequest
from src.schemas.company import CompanyRegistration
from src.services.auth_service import change_password, login_user, logout_user, refresh_access_token, register_company

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register-company", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register_company_route(payload: CompanyRegistration, request: Request, db: Session = Depends(get_db)):
    return register_company(db, payload, request)


@router.post("/login", response_model=AuthResponse)
def login_route(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    return login_user(db, payload, request)


@router.post("/refresh", response_model=AuthResponse)
def refresh_token_route(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    return refresh_access_token(db, payload.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout_route(payload: RefreshTokenRequest, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    logout_user(db, current_user, payload.refresh_token, request)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password_route(payload: ChangePasswordRequest, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    change_password(db, current_user, payload.current_password, payload.new_password, request)
