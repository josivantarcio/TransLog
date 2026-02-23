import json
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.delivery_tracking import DeliveryTracking
from app.schemas.delivery_tracking import TrackingEventCreate

LIVE_TRACKING_KEY = "tracking:{delivery_id}"
LIVE_TRACKING_TTL = 3600  # 1 hora sem atualização expira


class TrackingService:
    def __init__(self, db: AsyncSession, redis: Redis) -> None:
        self.db = db
        self.redis = redis

    def _redis_key(self, delivery_id: UUID) -> str:
        return LIVE_TRACKING_KEY.format(delivery_id=str(delivery_id))

    async def record_event(
        self, driver_id: UUID, payload: TrackingEventCreate
    ) -> DeliveryTracking:
        # TODO:
        # 1. Salvar evento no Postgres (histórico)
        # 2. Atualizar posição ao vivo no Redis
        # 3. Publicar no canal pub/sub para WebSocket
        raise NotImplementedError

    async def get_live_position(self, delivery_id: UUID) -> dict | None:
        data = await self.redis.get(self._redis_key(delivery_id))
        if data:
            return json.loads(data)
        return None

    async def get_history(self, delivery_id: UUID, tenant_id: UUID) -> list[DeliveryTracking]:
        raise NotImplementedError
