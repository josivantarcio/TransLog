import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class EmailVerification(Base):
    """Token de verificação de email para novos usuários (role CLIENT).

    Fluxo:
    1. Usuário cliente é criado → token gerado e enviado por email
    2. Cliente clica no link → POST /users/verify-email?token=<token>
    3. token marcado como used=True, user.is_verified=True
    4. A partir daí o cliente pode receber a senha OTP de desbloqueio de entrega
    """

    __tablename__ = "email_verifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship()  # type: ignore[name-defined]  # noqa: F821

    def __repr__(self) -> str:
        return f"<EmailVerification user={self.user_id} used={self.used}>"
