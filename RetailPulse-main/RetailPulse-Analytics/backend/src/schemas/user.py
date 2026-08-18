from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from src.models.user import UserRole, UserStatus
from .company import CompanyRead


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    role: UserRole
    status: UserStatus
    last_login: datetime | None
    created_at: datetime
    company: CompanyRead


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    role: UserRole
    status: UserStatus
    last_login: datetime | None
