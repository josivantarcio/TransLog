"""Serviço de rastreamento de entregas em tempo real.

Arquitetura dual:
- Redis: posição ao vivo (key tracking:{delivery_id}), TTL 1 hora, broadcast via pub/sub
- Postgres: histórico persistido de todos os eventos GPS
"""

import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.delivery import Delivery, DeliveryStatus
from app.models.delivery_tracking import DeliveryTracking
from app.schemas.delivery_tracking import TrackingEventCreate

LIVE_TRACKING_KEY = "tracking:{delivery_id}"
PUBSUB_CHANNEL = "tracking_channel:{delivery_id}"
LIVE_TRACKING_TTL = 3600  # 1 hora sem atualização expira


class TrackingService:
    def __init__(self, db: AsyncSession, redis) -> None:
        self.db = db
        self.redis = redis

    def _redis_key(self, delivery_id: UUID) -> str:
        return LIVE_TRACKING_KEY.format(delivery_id=str(delivery_id))

    def _pubsub_channel(self, delivery_id: UUID) -> str:
        return PUBSUB_CHANNEL.format(delivery_id=str(delivery_id))

    async def record_event(
        self, tenant_id: UUID, driver_id: UUID, payload: TrackingEventCreate
    ) -> DeliveryTracking:
        """Registra evento GPS: persiste no Postgres, atualiza Redis e publica no canal pub/sub."""
        # Valida que a entrega existe e pertence ao tenant
        result = await self.db.execute(
            select(Delivery).where(
                Delivery.id == payload.delivery_id,
                Delivery.tenant_id == tenant_id,
            )
        )
        delivery = result.scalar_one_or_none()
        if not delivery:
            raise ValueError("Entrega não encontrada.")
        if delivery.status != DeliveryStatus.IN_TRANSIT:
            raise ValueError("Rastreamento disponível apenas para entregas em trânsito.")

        recorded_at = payload.recorded_at or datetime.now(UTC)

        # 1. Persiste no Postgres (histórico)
        event = DeliveryTracking(
            delivery_id=payload.delivery_id,
            driver_id=driver_id,
            latitude=payload.latitude,
            longitude=payload.longitude,
            accuracy=payload.accuracy,
            speed=payload.speed,
            heading=payload.heading,
            altitude=payload.altitude,
            status_snapshot=delivery.status.value,
            event_description=payload.event_description,
            recorded_at=recorded_at,
        )
        self.db.add(event)
        await self.db.flush()

        # 2. Atualiza posição ao vivo no Redis
        live_data = {
            "delivery_id": str(payload.delivery_id),
            "latitude": payload.latitude,
            "longitude": payload.longitude,
            "accuracy": payload.accuracy,
            "speed": payload.speed,
            "heading": payload.heading,
            "timestamp": recorded_at.isoformat(),
            "status": delivery.status.value,
        }
        await self.redis.setex(
            self._redis_key(payload.delivery_id),
            LIVE_TRACKING_TTL,
            json.dumps(live_data),
        )

        # 3. Publica no canal pub/sub para WebSocket (fire-and-forget — falha não crítica)
        try:
            await self.redis.publish(
                self._pubsub_channel(payload.delivery_id),
                json.dumps(live_data),
            )
        except Exception:
            pass  # WebSocket broadcast é best-effort

        return event

    async def get_live_position(self, tenant_id: UUID, delivery_id: UUID) -> dict | None:
        """Retorna posição ao vivo do Redis (None se sem dados recentes)."""
        # Valida que entrega existe no tenant
        result = await self.db.execute(
            select(Delivery).where(
                Delivery.id == delivery_id,
                Delivery.tenant_id == tenant_id,
            )
        )
        if not result.scalar_one_or_none():
            raise ValueError("Entrega não encontrada.")

        data = await self.redis.get(self._redis_key(delivery_id))
        if data:
            return json.loads(data)
        return None

    async def get_history(
        self,
        tenant_id: UUID,
        delivery_id: UUID,
        limit: int = 200,
    ) -> list[DeliveryTracking]:
        """Retorna histórico de eventos GPS do Postgres (mais recentes primeiro)."""
        # Valida que entrega existe no tenant
        result = await self.db.execute(
            select(Delivery).where(
                Delivery.id == delivery_id,
                Delivery.tenant_id == tenant_id,
            )
        )
        if not result.scalar_one_or_none():
            raise ValueError("Entrega não encontrada.")

        q = await self.db.execute(
            select(DeliveryTracking)
            .where(DeliveryTracking.delivery_id == delivery_id)
            .order_by(DeliveryTracking.recorded_at.desc())
            .limit(limit)
        )
        return list(q.scalars().all())
