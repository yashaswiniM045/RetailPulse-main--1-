from datetime import UTC, datetime

from fastapi import HTTPException, Request, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from src.config.jwt import create_access_token, create_refresh_token, decode_token
from src.core.security import hash_password, verify_password
from src.models.company import Company
from src.models.refresh_token import RefreshToken
from src.models.user import User, UserRole, UserStatus
from src.schemas.auth import AuthResponse, LoginRequest
from src.schemas.company import CompanyRegistration
from src.services.audit_service import AuditAction, create_audit_log
from src.services.user_service import get_user_by_email


def _get_user_with_company(db: Session, user_id: int) -> User:
    statement = select(User).options(selectinload(User.company)).where(User.id == user_id)
    user = db.scalar(statement)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _build_auth_response(db: Session, user: User) -> AuthResponse:
    access_token = create_access_token(str(user.id), user.company_id, user.role.value)
    refresh_token, expires_at = create_refresh_token(str(user.id), user.company_id, user.role.value)
    db.add(RefreshToken(user_id=user.id, token=refresh_token, expires_at=expires_at))
    db.commit()
    db.refresh(user)
    full_user = _get_user_with_company(db, user.id)
    return AuthResponse(accessToken=access_token, refreshToken=refresh_token, user=full_user)


def register_company(db: Session, payload: CompanyRegistration, request: Request) -> AuthResponse:
    if payload.password != payload.confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match")

    existing_company = db.scalar(
        select(Company).where(or_(Company.email == payload.company_email.lower(), Company.name == payload.company_name.strip()))
    )
    if existing_company is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Company already registered")

    if get_user_by_email(db, payload.owner_email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")

    company = Company(
        name=payload.company_name.strip(),
        industry=payload.industry.strip(),
        email=payload.company_email.lower(),
        address=payload.company_address.strip(),
        phone=payload.company_phone_number.strip(),
    )
    db.add(company)
    db.flush()

    admin_user = User(
        company_id=company.id,
        name=payload.owner_name.strip(),
        email=payload.owner_email.lower(),
        password=hash_password(payload.password),
        role=UserRole.COMPANY_ADMIN,
        status=UserStatus.ACTIVE,
    )
    db.add(admin_user)
    db.flush()
    create_audit_log(
        db,
        company_id=company.id,
        user_id=admin_user.id,
        performed_by=admin_user.name,
        entity_type="Company",
        entity_name=company.name,
        action=AuditAction.COMPANY_REGISTERED,
        request=request,
    )
    db.commit()
    return _build_auth_response(db, admin_user)


def login_user(db: Session, payload: LoginRequest, request: Request) -> AuthResponse:
    user = get_user_by_email(db, payload.email)
    if user is None or not verify_password(payload.password, user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")

    user.last_login = datetime.now(UTC)
    create_audit_log(
        db,
        company_id=user.company_id,
        user_id=user.id,
        performed_by=user.name,
        entity_type="User",
        entity_name=user.name,
        action=AuditAction.USER_LOGIN,
        request=request,
    )
    db.commit()
    return _build_auth_response(db, user)


def refresh_access_token(db: Session, refresh_token: str) -> AuthResponse:
    payload = decode_token(refresh_token, expected_type="refresh")
    persisted_token = db.scalar(
        select(RefreshToken).where(
            and_(RefreshToken.token == refresh_token, RefreshToken.expires_at >= datetime.now(UTC))
        )
    )
    if persisted_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired or revoked")

    user = _get_user_with_company(db, int(payload["sub"]))
    db.delete(persisted_token)
    db.commit()
    return _build_auth_response(db, user)


def logout_user(db: Session, user: User, refresh_token: str, request: Request) -> None:
    persisted_token = db.scalar(
        select(RefreshToken).where(
            and_(RefreshToken.token == refresh_token, RefreshToken.user_id == user.id)
        )
    )
    if persisted_token is not None:
        db.delete(persisted_token)
    create_audit_log(
        db,
        company_id=user.company_id,
        user_id=user.id,
        performed_by=user.name,
        entity_type="User",
        entity_name=user.name,
        action=AuditAction.USER_LOGOUT,
        request=request,
    )
    db.commit()


def change_password(db: Session, user: User, current_password: str, new_password: str, request: Request) -> None:
    if not verify_password(current_password, user.password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is invalid")
    if len(new_password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters")

    user.password = hash_password(new_password)
    create_audit_log(
        db,
        company_id=user.company_id,
        user_id=user.id,
        performed_by=user.name,
        entity_type="User",
        entity_name=user.name,
        action=AuditAction.PASSWORD_CHANGED,
        request=request,
    )
    db.commit()
