from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, tenant_id: UUID, payload: UserCreate) -> User:
        # TODO: verificar email único no tenant, hash senha, salvar
        raise NotImplementedError

    async def get_by_id(self, user_id: UUID, tenant_id: UUID) -> User:
        raise NotImplementedError

    async def get_by_email(self, email: str, tenant_id: UUID) -> User | None:
        raise NotImplementedError

    async def list(self, tenant_id: UUID) -> list[User]:
        raise NotImplementedError

    async def update(self, user_id: UUID, tenant_id: UUID, payload: UserUpdate) -> User:
        raise NotImplementedError

    async def change_password(
        self, user_id: UUID, tenant_id: UUID, current_password: str, new_password: str
    ) -> None:
        raise NotImplementedError
