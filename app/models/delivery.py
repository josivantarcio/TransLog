import enum
import uuid

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.models.base import Base, TimestampMixin


class DeliveryStatus(str, enum.Enum):
    PENDING = "pending"               # aguardando aceite do motorista
    ACCEPTED = "accepted"             # motorista aceitou
    PICKED_UP = "picked_up"           # coletado na origem
    IN_TRANSIT = "in_transit"         # em trânsito
    OUT_FOR_DELIVERY = "out_for_delivery"  # saiu para entrega
    DELIVERED = "delivered"           # entregue com sucesso
    FAILED = "failed"                 # falha na entrega
    RETURNED = "returned"             # devolvido
    CANCELLED = "cancelled"           # cancelado


class Delivery(Base, TimestampMixin):
    __tablename__ = "deliveries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tracking_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    # Partes envolvidas
    driver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    # Status
    status: Mapped[DeliveryStatus] = mapped_column(
        Enum(DeliveryStatus, name="delivery_status"),
        default=DeliveryStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Endereços
    origin_address: Mapped[str] = mapped_column(Text, nullable=False)
    origin_lat: Mapped[float | None] = mapped_column(Numeric(10, 7))
    origin_lng: Mapped[float | None] = mapped_column(Numeric(10, 7))

    destination_address: Mapped[str] = mapped_column(Text, nullable=False)
    destination_lat: Mapped[float | None] = mapped_column(Numeric(10, 7))
    destination_lng: Mapped[float | None] = mapped_column(Numeric(10, 7))

    # Detalhes da carga
    description: Mapped[str | None] = mapped_column(Text)
    weight_kg: Mapped[float | None] = mapped_column(Numeric(10, 2))
    value: Mapped[float | None] = mapped_column(Numeric(12, 2))

    # QR Code e OTP para confirmação de entrega
    qr_code_data: Mapped[str | None] = mapped_column(Text)       # payload do QR code
    otp_hash: Mapped[str | None] = mapped_column(String(255))    # hash do OTP enviado
    otp_secret: Mapped[str | None] = mapped_column(String(64))   # secret TOTP
    otp_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Timestamps de eventos
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    picked_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estimated_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Autorização manual (GPS falhou ou impossibilidade de confirmação automática)
    manually_authorized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    manually_authorized_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    # Notas
    delivery_notes: Mapped[str | None] = mapped_column(Text)
    failure_reason: Mapped[str | None] = mapped_column(Text)

    # Relacionamentos
    tenant: Mapped["Tenant"] = relationship(back_populates="deliveries")  # type: ignore[name-defined]  # noqa: F821
    driver: Mapped["User | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="deliveries_as_driver",
        foreign_keys=[driver_id],
    )
    client: Mapped["User | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="deliveries_as_client",
        foreign_keys=[client_id],
    )
    tracking_events: Mapped[list["DeliveryTracking"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="delivery",
        lazy="noload",
        order_by="DeliveryTracking.recorded_at",
    )

    def __repr__(self) -> str:
        return f"<Delivery {self.tracking_code} [{self.status}]>"
