from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.tenant import TenantPlan, TenantStatus


class TenantBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    document: str | None = None
    phone: str | None = None
    plan: TenantPlan = TenantPlan.FREE


class TenantCreate(TenantBase):
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")


class TenantUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    email: EmailStr | None = None
    document: str | None = None
    phone: str | None = None
    plan: TenantPlan | None = None
    status: TenantStatus | None = None


class TenantResponse(TenantBase):
    model_config = {"from_attributes": True}

    id: UUID
    slug: str
    status: TenantStatus
    is_active: bool
    asaas_customer_id: str | None = None
    created_at: datetime
    updated_at: datetime
