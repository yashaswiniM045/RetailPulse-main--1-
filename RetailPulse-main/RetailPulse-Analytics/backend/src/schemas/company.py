from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CompanyRegistration(BaseModel):
    company_name: str = Field(min_length=2, max_length=255)
    industry: str = Field(min_length=2, max_length=255)
    company_email: EmailStr
    company_address: str = Field(min_length=5, max_length=255)
    company_phone_number: str = Field(min_length=5, max_length=50)
    owner_name: str = Field(min_length=2, max_length=255)
    owner_email: EmailStr
    password: str = Field(min_length=8)
    confirm_password: str = Field(min_length=8)


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    industry: str
    email: EmailStr
    address: str
    phone: str
    created_at: datetime
