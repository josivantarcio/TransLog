from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUserDep, require_role
from app.schemas.tenant import (
    PaginatedTenants,
    TenantOnboard,
    TenantOnboardResponse,
    TenantResponse,
    TenantUpdate,
)
from app.services.tenant_service import TenantService

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post(
    "/onboard",
    response_model=TenantOnboardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar nova empresa (onboarding público)",
)
async def onboard_tenant(
    payload: TenantOnboard,
    db: AsyncSession = Depends(get_db),
):
    """Cria um novo tenant e o primeiro usuário ADMIN.

    Endpoint público — usado no fluxo de cadastro de novas empresas.
    """
    svc = TenantService(db)
    try:
        tenant, admin = await svc.onboard(payload)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    return TenantOnboardResponse(
        tenant=TenantResponse.model_validate(tenant),
        admin_user_id=admin.id,
        admin_email=admin.email,
    )


@router.get(
    "/me",
    response_model=TenantResponse,
    summary="Dados do tenant do usuário autenticado",
)
async def get_my_tenant(
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    """Retorna os dados do tenant do usuário logado."""
    svc = TenantService(db)
    try:
        tenant = await svc.get_by_id(current_user.tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return tenant


@router.patch(
    "/me",
    response_model=TenantResponse,
    dependencies=[require_role("admin")],
    summary="Atualizar dados do próprio tenant",
)
async def update_my_tenant(
    payload: TenantUpdate,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    """Atualiza dados do tenant. Requer role ADMIN."""
    svc = TenantService(db)
    try:
        tenant = await svc.update(current_user.tenant_id, payload)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return tenant


# ---------------------------------------------------------------------------
# Rotas administrativas (superadmin — role admin sem restrição de tenant)
# ---------------------------------------------------------------------------

@router.get(
    "/",
    response_model=PaginatedTenants,
    dependencies=[require_role("admin")],
    summary="Listar todos os tenants (admin global)",
)
async def list_tenants(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    svc = TenantService(db)
    tenants, total = await svc.list_all(page=page, page_size=page_size)
    return PaginatedTenants(items=tenants, total=total, page=page, page_size=page_size)


@router.get(
    "/{tenant_id}",
    response_model=TenantResponse,
    dependencies=[require_role("admin")],
    summary="Detalhe de tenant por ID (admin global)",
)
async def get_tenant(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    svc = TenantService(db)
    try:
        return await svc.get_by_id(tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/{tenant_id}/suspend",
    response_model=TenantResponse,
    dependencies=[require_role("admin")],
    summary="Suspender tenant (admin global)",
)
async def suspend_tenant(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    svc = TenantService(db)
    try:
        tenant = await svc.suspend(tenant_id)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return tenant


@router.post(
    "/{tenant_id}/activate",
    response_model=TenantResponse,
    dependencies=[require_role("admin")],
    summary="Ativar tenant (admin global)",
)
async def activate_tenant(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    svc = TenantService(db)
    try:
        tenant = await svc.activate(tenant_id)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return tenant
