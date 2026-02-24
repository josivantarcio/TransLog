"""Serviço de gestão de Usuários dentro de um Tenant.

Isolamento: todas as operações recebem tenant_id e filtram por ele.
"""

import re
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate


def _validate_password_strength(password: str) -> None:
    """Garante mínimo de segurança: 8 chars, 1 maiúscula, 1 número."""
    if len(password) < 8:
        raise ValueError("Senha deve ter no mínimo 8 caracteres.")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Senha deve conter ao menos uma letra maiúscula.")
    if not re.search(r"[0-9]", password):
        raise ValueError("Senha deve conter ao menos um número.")


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, tenant_id: UUID, payload: UserCreate) -> User:
        """Cria usuário dentro do tenant.

        Raises:
            ValueError: email já cadastrado no tenant, senha fraca.
        """
        _validate_password_strength(payload.password)

        existing = await self.db.execute(
            select(User).where(User.email == payload.email, User.tenant_id == tenant_id)
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Email '{payload.email}' já cadastrado neste tenant.")

        user = User(
            tenant_id=tenant_id,
            email=payload.email,
            hashed_password=hash_password(payload.password),
            full_name=payload.full_name,
            phone=payload.phone,
            role=payload.role,
            is_active=True,
            is_verified=False,
        )
        self.db.add(user)
        await self.db.flush()
        return user

    async def get_by_id(self, tenant_id: UUID, user_id: UUID) -> User:
        result = await self.db.execute(
            select(User).where(User.id == user_id, User.tenant_id == tenant_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("Usuário não encontrado.")
        return user

    async def get_by_email(self, tenant_id: UUID, email: str) -> User | None:
        result = await self.db.execute(
            select(User).where(User.email == email, User.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        tenant_id: UUID,
        role: UserRole | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[User], int]:
        query = select(User).where(User.tenant_id == tenant_id)
        if role is not None:
            query = query.where(User.role == role)

        count_q = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_q)
        total = count_result.scalar_one()

        offset = (page - 1) * page_size
        result = await self.db.execute(
            query.order_by(User.created_at.desc()).offset(offset).limit(page_size)
        )
        return list(result.scalars().all()), total

    async def update(self, tenant_id: UUID, user_id: UUID, payload: UserUpdate) -> User:
        user = await self.get_by_id(tenant_id, user_id)
        data = payload.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(user, field, value)
        await self.db.flush()
        return user

    async def deactivate(self, tenant_id: UUID, user_id: UUID, requesting_user_id: UUID) -> User:
        """Desativa (soft delete) um usuário.

        Raises:
            ValueError: usuário tentando desativar a si mesmo, ou último admin.
        """
        if user_id == requesting_user_id:
            raise ValueError("Você não pode desativar sua própria conta.")

        user = await self.get_by_id(tenant_id, user_id)

        if user.role == UserRole.ADMIN:
            count_result = await self.db.execute(
                select(func.count()).where(
                    User.tenant_id == tenant_id,
                    User.role == UserRole.ADMIN,
                    User.is_active.is_(True),
                )
            )
            if count_result.scalar_one() <= 1:
                raise ValueError("Não é possível desativar o último administrador do tenant.")

        user.is_active = False
        await self.db.flush()
        return user

    async def change_password(
        self,
        tenant_id: UUID,
        user_id: UUID,
        current_password: str,
        new_password: str,
    ) -> None:
        """Troca a senha do próprio usuário verificando a senha atual."""
        _validate_password_strength(new_password)
        user = await self.get_by_id(tenant_id, user_id)
        if not verify_password(current_password, user.hashed_password):
            raise ValueError("Senha atual incorreta.")
        user.hashed_password = hash_password(new_password)
        await self.db.flush()

    async def reset_password(
        self, tenant_id: UUID, user_id: UUID, new_password: str
    ) -> None:
        """Redefine a senha de um usuário (operação de ADMIN)."""
        _validate_password_strength(new_password)
        user = await self.get_by_id(tenant_id, user_id)
        user.hashed_password = hash_password(new_password)
        await self.db.flush()
