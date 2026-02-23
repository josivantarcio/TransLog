# Importa todos os modelos para que o Alembic autogenerate detecte as tabelas.
# A ordem importa: Base antes dos modelos, dependências antes de dependentes.
from app.models.base import Base, TimestampMixin  # noqa: F401
from app.models.tenant import Tenant, TenantPlan, TenantStatus  # noqa: F401
from app.models.user import User, UserRole  # noqa: F401
from app.models.vehicle import Vehicle, VehicleType  # noqa: F401
from app.models.delivery import Delivery, DeliveryStatus  # noqa: F401
from app.models.delivery_tracking import DeliveryTracking  # noqa: F401
from app.models.email_verification import EmailVerification  # noqa: F401

__all__ = [
    "Base",
    "TimestampMixin",
    "Tenant",
    "TenantPlan",
    "TenantStatus",
    "User",
    "UserRole",
    "Vehicle",
    "VehicleType",
    "Delivery",
    "DeliveryStatus",
    "DeliveryTracking",
    "EmailVerification",
]
