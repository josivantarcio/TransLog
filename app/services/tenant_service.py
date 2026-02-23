from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant
from app.schemas.tenant import TenantCreate, TenantUpdate


class TenantService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, payload: TenantCreate) -> Tenant:
        # TODO: verificar slug único, criar tenant, registrar no Asaas
        raise NotImplementedError

    async def get_by_id(self, tenant_id: UUID) -> Tenant:
        raise NotImplementedError

    async def get_by_slug(self, slug: str) -> Tenant:
        raise NotImplementedError

    async def update(self, tenant_id: UUID, payload: TenantUpdate) -> Tenant:
        raise NotImplementedError
