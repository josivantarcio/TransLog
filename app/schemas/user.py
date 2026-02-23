from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: str | None = None
    role: UserRole = UserRole.CLIENT


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=255)
    phone: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None


class UserResponse(UserBase):
    model_config = {"from_attributes": True}

    id: UUID
    tenant_id: UUID
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime


class UserPasswordUpdate(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class EmailVerifyRequest(BaseModel):
    token: str


class EmailResendRequest(BaseModel):
    email: EmailStr
