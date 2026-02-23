import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class VehicleType(str, enum.Enum):
    MOTORCYCLE = "motorcycle"
    CAR = "car"
    VAN = "van"
    TRUCK = "truck"
    BICYCLE = "bicycle"


class Vehicle(Base, TimestampMixin):
    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    driver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    plate: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    brand: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer)
    color: Mapped[str | None] = mapped_column(String(50))

    vehicle_type: Mapped[VehicleType] = mapped_column(
        Enum(VehicleType, name="vehicle_type"),
        default=VehicleType.MOTORCYCLE,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relacionamentos
    tenant: Mapped["Tenant"] = relationship(back_populates="vehicles")  # type: ignore[name-defined]  # noqa: F821
    driver: Mapped["User | None"] = relationship(foreign_keys=[driver_id])  # type: ignore[name-defined]  # noqa: F821

    def __repr__(self) -> str:
        return f"<Vehicle {self.plate} [{self.vehicle_type}]>"
