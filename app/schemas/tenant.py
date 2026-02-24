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


class TenantOnboard(TenantBase):
    """Payload de onboarding: cria tenant + primeiro admin."""
    slug: str | None = Field(
        None, min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$",
        description="Opcional — gerado automaticamente a partir do nome se omitido."
    )
    admin_name: str = Field(..., min_length=2, max_length=255)
    admin_email: EmailStr
    admin_password: str = Field(..., min_length=8)


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
    created_at: datetime
    updated_at: datetime


class TenantOnboardResponse(BaseModel):
    model_config = {"from_attributes": True}

    tenant: TenantResponse
    admin_user_id: UUID
    admin_email: str


class PaginatedTenants(BaseModel):
    items: list[TenantResponse]
    total: int
    page: int
    page_size: int
