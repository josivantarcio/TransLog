import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class DeliveryTracking(Base):
    """Histórico de rastreamento de uma entrega.

    Coordenadas ao vivo ficam no Redis (key: tracking:{delivery_id}).
    Este modelo armazena apenas os pontos persistidos no histórico.
    """

    __tablename__ = "delivery_tracking"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    delivery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("deliveries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    driver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )

    # Coordenadas GPS
    latitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    accuracy: Mapped[float | None] = mapped_column(Numeric(6, 2))   # metros
    speed: Mapped[float | None] = mapped_column(Numeric(6, 2))      # km/h
    heading: Mapped[float | None] = mapped_column(Numeric(5, 2))    # graus (0-360)
    altitude: Mapped[float | None] = mapped_column(Numeric(8, 2))   # metros

    # Status no momento do registro
    status_snapshot: Mapped[str | None] = mapped_column(String(50))

    # Mensagem/evento
    event_description: Mapped[str | None] = mapped_column(Text)

    # Timestamp do dispositivo (pode diferir do server_default)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relacionamentos
    delivery: Mapped["Delivery"] = relationship(back_populates="tracking_events")  # type: ignore[name-defined]  # noqa: F821

    def __repr__(self) -> str:
        return f"<DeliveryTracking delivery={self.delivery_id} lat={self.latitude} lng={self.longitude}>"
