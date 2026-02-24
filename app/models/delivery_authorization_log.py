"""Histórico de autorizações manuais de entrega.

Quando o GPS falha ou há impossibilidade de confirmação automática,
a Fornecedora pode autorizar a entrega manualmente. Este modelo registra
quem autorizou, como e quando — para auditoria completa.

Fluxo:
- Operador da Fornecedora (não-admin): clica em "Autorizar sem GPS"
  → precisa fornecer a senha OTP que o cliente recebeu
  → registro: authorized_by=operador, method=OPERATOR_OTP
- Administrador da Fornecedora: clica em "Autorizar sem GPS"
  → fornece a própria senha de acesso ao sistema
  → registro: authorized_by=admin, method=ADMIN_PASSWORD
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AuthorizationMethod(str, enum.Enum):
    # GPS ok + OTP correto — fluxo normal (não gera este log)
    GPS_OTP = "gps_otp"
    # GPS falhou; operador não-admin apresentou a senha OTP do cliente para liberar
    OPERATOR_OTP = "operator_otp"
    # GPS falhou; administrador usou a própria senha do sistema para liberar
    ADMIN_PASSWORD = "admin_password"


class DeliveryAuthorizationLog(Base):
    """Auditoria de cada autorização manual de entrega."""

    __tablename__ = "delivery_authorization_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    delivery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("deliveries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Usuário da Fornecedora que autorizou (operador ou admin)
    authorized_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        index=True,
    )
    method: Mapped[AuthorizationMethod] = mapped_column(
        Enum(AuthorizationMethod, name="authorization_method"),
        nullable=False,
    )
    # Motivo informado pelo autorizador (campo livre obrigatório)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    # Último GPS registrado no momento da autorização (pode ser None se nunca teve sinal)
    gps_lat_at_authorization: Mapped[float | None] = mapped_column(String(20))
    gps_lng_at_authorization: Mapped[float | None] = mapped_column(String(20))
    # IP da requisição (rastreabilidade)
    request_ip: Mapped[str | None] = mapped_column(String(45))

    authorized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    delivery: Mapped["Delivery"] = relationship()  # type: ignore[name-defined]  # noqa: F821
    authorized_by: Mapped["User"] = relationship(foreign_keys=[authorized_by_user_id])  # type: ignore[name-defined]  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<DeliveryAuthorizationLog delivery={self.delivery_id}"
            f" method={self.method} by={self.authorized_by_user_id}>"
        )
