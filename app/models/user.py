import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    DRIVER = "driver"
    CLIENT = "client"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))

    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"),
        default=UserRole.CLIENT,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relacionamentos
    tenant: Mapped["Tenant"] = relationship(back_populates="users")  # type: ignore[name-defined]  # noqa: F821
    deliveries_as_driver: Mapped[list["Delivery"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="driver",
        foreign_keys="Delivery.driver_id",
        lazy="noload",
    )
    deliveries_as_client: Mapped[list["Delivery"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="client",
        foreign_keys="Delivery.client_id",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<User {self.email} [{self.role}]>"
