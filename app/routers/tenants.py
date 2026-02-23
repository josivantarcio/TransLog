from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_role
from app.schemas.tenant import TenantCreate, TenantResponse, TenantUpdate

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    payload: TenantCreate,
    db: AsyncSession = Depends(get_db),
):
    """Cria um novo tenant (registro público / onboarding)."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: UUID,
    _=require_role("admin"),
    db: AsyncSession = Depends(get_db),
):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: UUID,
    payload: TenantUpdate,
    _=require_role("admin"),
    db: AsyncSession = Depends(get_db),
):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)
