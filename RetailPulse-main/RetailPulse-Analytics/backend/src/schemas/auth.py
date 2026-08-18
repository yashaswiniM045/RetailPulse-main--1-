from pydantic import BaseModel, EmailStr, Field

from .user import UserRead


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(alias="refreshToken")


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(alias="currentPassword", min_length=8)
    new_password: str = Field(alias="newPassword", min_length=8)


class TokenPayload(BaseModel):
    sub: str
    company_id: int
    role: str
    type: str


class AuthResponse(BaseModel):
    access_token: str = Field(alias="accessToken")
    refresh_token: str = Field(alias="refreshToken")
    user: UserRead
