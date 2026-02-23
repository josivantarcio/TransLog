import logging
import secrets
import smtplib
from datetime import UTC, datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.email_verification import EmailVerification
from app.models.user import User

logger = logging.getLogger(__name__)

EMAIL_VERIFICATION_EXPIRE_HOURS = 24


class EmailService:
    """Envio de emails transacionais via SMTP.

    Em ambiente de desenvolvimento (DEBUG=True e sem SMTP_USER configurado),
    o conteúdo do email é impresso no log em vez de enviado.
    """

    def _build_message(self, to_email: str, subject: str, html_body: str) -> MIMEMultipart:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        return msg

    def _send_smtp(self, to_email: str, msg: MIMEMultipart) -> None:
        if settings.DEBUG and not settings.SMTP_USER:
            # Dev: apenas loga o conteúdo
            logger.info(
                "[EMAIL DEV] Para: %s | Assunto: %s\n%s",
                to_email,
                msg["Subject"],
                msg.get_payload(0).get_payload(decode=True).decode(),  # type: ignore[union-attr]
            )
            return

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAILS_FROM_EMAIL, to_email, msg.as_string())

    def send_verification_email(self, to_email: str, full_name: str, token: str) -> None:
        """Envia o email de verificação de conta para o cliente (recebedor)."""
        verify_url = f"http://localhost:8000/api/v1/users/verify-email?token={token}"
        html = f"""
        <html><body>
        <h2>Olá, {full_name}!</h2>
        <p>Sua conta no <strong>transLog</strong> foi criada.</p>
        <p>Para confirmar seu email e poder receber a senha de desbloqueio das suas entregas,
        clique no botão abaixo:</p>
        <p>
          <a href="{verify_url}"
             style="background:#2563eb;color:#fff;padding:12px 24px;
                    border-radius:6px;text-decoration:none;font-weight:bold;">
            Confirmar meu email
          </a>
        </p>
        <p>Este link expira em <strong>24 horas</strong>.</p>
        <p>Se você não criou esta conta, ignore este email.</p>
        <hr>
        <small>transLog — Sistema de Gestão de Entregas</small>
        </body></html>
        """
        msg = self._build_message(to_email, "Confirme seu email — transLog", html)
        self._send_smtp(to_email, msg)

    def send_otp_email(self, to_email: str, full_name: str, otp_code: str, delivery_code: str) -> None:
        """Envia a senha OTP de desbloqueio de entrega para o cliente (recebedor)."""
        html = f"""
        <html><body>
        <h2>Olá, {full_name}!</h2>
        <p>Sua entrega <strong>{delivery_code}</strong> está a caminho!</p>
        <p>Quando o entregador chegar, informe a senha abaixo para confirmar o recebimento:</p>
        <div style="font-size:36px;font-weight:bold;letter-spacing:8px;
                    text-align:center;padding:20px;background:#f1f5f9;
                    border-radius:8px;margin:20px 0;">
          {otp_code}
        </div>
        <p><strong>Atenção:</strong> Esta senha é válida por <strong>30 segundos</strong>.
        Não a compartilhe com ninguém além do entregador.</p>
        <hr>
        <small>transLog — Sistema de Gestão de Entregas</small>
        </body></html>
        """
        msg = self._build_message(
            to_email, f"Senha de entrega #{delivery_code} — transLog", html
        )
        self._send_smtp(to_email, msg)

    def send_password_reset_email(self, to_email: str, full_name: str, token: str) -> None:
        """Envia email de redefinição de senha."""
        reset_url = f"http://localhost:8000/api/v1/auth/reset-password?token={token}"
        html = f"""
        <html><body>
        <h2>Olá, {full_name}!</h2>
        <p>Recebemos uma solicitação para redefinir sua senha no <strong>transLog</strong>.</p>
        <p>
          <a href="{reset_url}"
             style="background:#dc2626;color:#fff;padding:12px 24px;
                    border-radius:6px;text-decoration:none;font-weight:bold;">
            Redefinir senha
          </a>
        </p>
        <p>Este link expira em <strong>1 hora</strong>. Se não foi você, ignore este email.</p>
        <hr>
        <small>transLog — Sistema de Gestão de Entregas</small>
        </body></html>
        """
        msg = self._build_message(to_email, "Redefinição de senha — transLog", html)
        self._send_smtp(to_email, msg)


class EmailVerificationService:
    """Gerencia tokens de verificação de email no banco de dados."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.email_service = EmailService()

    def _generate_token(self) -> str:
        return secrets.token_urlsafe(64)

    async def create_and_send(self, user: User) -> EmailVerification:
        """Cria token, persiste no banco e envia o email de verificação."""
        token = self._generate_token()
        expires_at = datetime.now(UTC) + timedelta(hours=EMAIL_VERIFICATION_EXPIRE_HOURS)

        verification = EmailVerification(
            user_id=user.id,
            token=token,
            expires_at=expires_at,
        )
        self.db.add(verification)
        await self.db.flush()  # garante o id sem commit

        # Envia o email (pode lançar exceção; tratado no router)
        self.email_service.send_verification_email(
            to_email=user.email,
            full_name=user.full_name,
            token=token,
        )
        return verification

    async def verify_token(self, token: str) -> User:
        """Valida o token e marca o usuário como verificado.

        Raises:
            ValueError: token inválido, expirado ou já usado.
        """
        now = datetime.now(UTC)

        result = await self.db.execute(
            select(EmailVerification).where(EmailVerification.token == token)
        )
        verification = result.scalar_one_or_none()

        if not verification:
            raise ValueError("Token de verificação inválido.")
        if verification.used:
            raise ValueError("Token já utilizado.")
        if verification.expires_at.replace(tzinfo=UTC) < now:
            raise ValueError("Token expirado.")

        # Marca token como usado
        verification.used = True

        # Marca usuário como verificado
        result_user = await self.db.execute(
            select(User).where(User.id == verification.user_id)
        )
        user = result_user.scalar_one()
        user.is_verified = True
        user.email_verified_at = now

        await self.db.flush()
        return user

    async def resend(self, user_id: UUID) -> None:
        """Invalida tokens anteriores e envia um novo email de verificação."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("Usuário não encontrado.")
        if user.is_verified:
            raise ValueError("Email já verificado.")

        # Invalida tokens anteriores
        result_tokens = await self.db.execute(
            select(EmailVerification).where(
                EmailVerification.user_id == user_id,
                EmailVerification.used == False,  # noqa: E712
            )
        )
        for old_token in result_tokens.scalars().all():
            old_token.used = True

        await self.create_and_send(user)
