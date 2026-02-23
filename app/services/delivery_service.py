import random
import string
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.delivery import Delivery
from app.schemas.delivery import DeliveryCreate, DeliveryUpdate


def generate_tracking_code(length: int = 12) -> str:
    """Gera código de rastreamento alfanumérico em maiúsculas."""
    chars = string.ascii_uppercase + string.digits
    return "TL-" + "".join(random.choices(chars, k=length))


class DeliveryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, tenant_id: UUID, created_by: UUID, payload: DeliveryCreate) -> Delivery:
        # TODO: gerar tracking_code único, salvar entrega
        raise NotImplementedError

    async def get_by_id(self, delivery_id: UUID, tenant_id: UUID) -> Delivery:
        raise NotImplementedError

    async def get_by_tracking_code(self, tracking_code: str) -> Delivery:
        raise NotImplementedError

    async def list(
        self,
        tenant_id: UUID,
        status_filter: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> list[Delivery]:
        raise NotImplementedError

    async def update(self, delivery_id: UUID, tenant_id: UUID, payload: DeliveryUpdate) -> Delivery:
        raise NotImplementedError
