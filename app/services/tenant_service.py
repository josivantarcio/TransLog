"""Serviço de gestão de Tenants.

Responsabilidades:
- Criar tenant + admin user inicial (onboarding)
- Consultar, atualizar, suspender e ativar tenants
- Validar unicidade de slug
"""

import re
import unicodedata
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.tenant import Tenant, TenantStatus
from app.models.user import User, UserRole
from app.schemas.tenant import TenantCreate, TenantOnboard, TenantUpdate


def _slugify(text: str) -> str:
    """Converte texto para slug (lowercase, apenas letras, dígitos e hífens)."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:100]


class TenantService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def onboard(self, payload: TenantOnboard) -> tuple[Tenant, User]:
        """Cria tenant + primeiro usuário ADMIN.

        Raises:
            ValueError: slug já em uso, email do admin já cadastrado.
        """
        slug = payload.slug or _slugify(payload.name)

        # Unicidade do slug
        existing = await self.db.execute(select(Tenant).where(Tenant.slug == slug))
        if existing.scalar_one_or_none():
            raise ValueError(f"Slug '{slug}' já está em uso.")

        tenant = Tenant(
            name=payload.name,
            slug=slug,
            email=payload.email,
            document=payload.document,
            phone=payload.phone,
            plan=payload.plan,
        )
        self.db.add(tenant)
        await self.db.flush()  # obtém tenant.id

        admin = User(
            tenant_id=tenant.id,
            email=payload.admin_email,
            hashed_password=hash_password(payload.admin_password),
            full_name=payload.admin_name,
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=False,
        )
        self.db.add(admin)
        await self.db.flush()

        return tenant, admin

    async def create(self, payload: TenantCreate) -> Tenant:
        """Cria tenant sem admin (uso interno / testes)."""
        existing = await self.db.execute(select(Tenant).where(Tenant.slug == payload.slug))
        if existing.scalar_one_or_none():
            raise ValueError(f"Slug '{payload.slug}' já está em uso.")

        tenant = Tenant(
            name=payload.name,
            slug=payload.slug,
            email=payload.email,
            document=payload.document,
            phone=payload.phone,
            plan=payload.plan,
        )
        self.db.add(tenant)
        await self.db.flush()
        return tenant

    async def get_by_id(self, tenant_id: UUID) -> Tenant:
        result = await self.db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise ValueError("Tenant não encontrado.")
        return tenant

    async def get_by_slug(self, slug: str) -> Tenant:
        result = await self.db.execute(select(Tenant).where(Tenant.slug == slug))
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise ValueError("Tenant não encontrado.")
        return tenant

    async def update(self, tenant_id: UUID, payload: TenantUpdate) -> Tenant:
        tenant = await self.get_by_id(tenant_id)
        data = payload.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(tenant, field, value)
        await self.db.flush()
        return tenant

    async def suspend(self, tenant_id: UUID) -> Tenant:
        tenant = await self.get_by_id(tenant_id)
        if tenant.status == TenantStatus.CANCELLED:
            raise ValueError("Tenant cancelado não pode ser suspenso.")
        tenant.status = TenantStatus.SUSPENDED
        await self.db.flush()
        return tenant

    async def activate(self, tenant_id: UUID) -> Tenant:
        tenant = await self.get_by_id(tenant_id)
        if tenant.status == TenantStatus.CANCELLED:
            raise ValueError("Tenant cancelado não pode ser ativado.")
        tenant.status = TenantStatus.ACTIVE
        await self.db.flush()
        return tenant

    async def list_all(self, page: int = 1, page_size: int = 20) -> tuple[list[Tenant], int]:
        offset = (page - 1) * page_size
        result = await self.db.execute(
            select(Tenant).order_by(Tenant.created_at.desc()).offset(offset).limit(page_size)
        )
        tenants = list(result.scalars().all())
        count_result = await self.db.execute(select(func.count()).select_from(Tenant))
        total = count_result.scalar_one()
        return tenants, total
