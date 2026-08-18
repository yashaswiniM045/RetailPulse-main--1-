from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.user import User


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.scalar(select(User).where(User.id == user_id))


def get_company_users(db: Session, company_id: int) -> list[User]:
    return list(db.scalars(select(User).where(User.company_id == company_id).order_by(User.created_at.desc())).all())
