from uuid import UUID

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    tenant_slug: str  # identifica o tenant no login (multi-tenant)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # segundos


class RefreshRequest(BaseModel):
    refresh_token: str


class MeResponse(BaseModel):
    user_id: UUID
    tenant_id: UUID
    email: str
    full_name: str
    role: str
    is_verified: bool


class OTPVerifyRequest(BaseModel):
    delivery_id: str
    otp_code: str
