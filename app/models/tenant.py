import enum
import uuid

from sqlalchemy import Boolean, Enum, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class TenantPlan(str, enum.Enum):
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class TenantStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    TRIAL = "trial"


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    document: Mapped[str | None] = mapped_column(String(20))  # CNPJ/CPF
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))

    plan: Mapped[TenantPlan] = mapped_column(
        Enum(TenantPlan, name="tenant_plan"),
        default=TenantPlan.FREE,
        nullable=False,
    )
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, name="tenant_status"),
        default=TenantStatus.TRIAL,
        nullable=False,
    )

    # Integração Asaas
    asaas_customer_id: Mapped[str | None] = mapped_column(String(100))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    settings: Mapped[str | None] = mapped_column(Text)  # JSON com configurações do tenant

    # Relacionamentos
    users: Mapped[list["User"]] = relationship(back_populates="tenant", lazy="noload")  # type: ignore[name-defined]  # noqa: F821
    deliveries: Mapped[list["Delivery"]] = relationship(back_populates="tenant", lazy="noload")  # type: ignore[name-defined]  # noqa: F821
    vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="tenant", lazy="noload")  # type: ignore[name-defined]  # noqa: F821

    def __repr__(self) -> str:
        return f"<Tenant {self.slug}>"
