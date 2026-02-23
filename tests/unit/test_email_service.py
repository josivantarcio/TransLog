"""Testes unitários para EmailService usando pytest-mock.

pytest-mock é o equivalente ao Mockito do Java:
- mocker.patch() = Mockito.mock() / @Mock
- mocker.MagicMock() = Mockito.spy()
- assert_called_once_with() = verify(mock).method(args)
"""

import pytest
from unittest.mock import MagicMock, patch

from app.services.email_service import EmailService


@pytest.fixture
def email_service() -> EmailService:
    return EmailService()


class TestEmailServiceDev:
    """Testa envio em modo dev (DEBUG=True, sem SMTP_USER) — apenas loga."""

    def test_send_verification_email_dev_mode(self, email_service: EmailService, mocker):
        """Em dev, o email deve ser logado, não enviado via SMTP."""
        mock_settings = mocker.patch("app.services.email_service.settings")
        mock_settings.DEBUG = True
        mock_settings.SMTP_USER = ""
        mock_settings.EMAILS_FROM_NAME = "transLog"
        mock_settings.EMAILS_FROM_EMAIL = "noreply@translog.com.br"

        mock_logger = mocker.patch("app.services.email_service.logger")

        email_service.send_verification_email(
            to_email="cliente@example.com",
            full_name="João Silva",
            token="token_de_teste_123",
        )

        # Deve chamar logger.info, não SMTP
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0]
        assert "cliente@example.com" in call_args[1]

    def test_send_otp_email_dev_mode(self, email_service: EmailService, mocker):
        mock_settings = mocker.patch("app.services.email_service.settings")
        mock_settings.DEBUG = True
        mock_settings.SMTP_USER = ""
        mock_settings.EMAILS_FROM_NAME = "transLog"
        mock_settings.EMAILS_FROM_EMAIL = "noreply@translog.com.br"

        mock_logger = mocker.patch("app.services.email_service.logger")

        email_service.send_otp_email(
            to_email="cliente@example.com",
            full_name="João Silva",
            otp_code="123456",
            delivery_code="TL-ABC123",
        )

        mock_logger.info.assert_called_once()

    def test_send_password_reset_email_dev_mode(self, email_service: EmailService, mocker):
        mock_settings = mocker.patch("app.services.email_service.settings")
        mock_settings.DEBUG = True
        mock_settings.SMTP_USER = ""
        mock_settings.EMAILS_FROM_NAME = "transLog"
        mock_settings.EMAILS_FROM_EMAIL = "noreply@translog.com.br"

        mock_logger = mocker.patch("app.services.email_service.logger")

        email_service.send_password_reset_email(
            to_email="user@example.com",
            full_name="Maria",
            token="reset_token_xyz",
        )

        mock_logger.info.assert_called_once()


class TestEmailServiceSMTP:
    """Testa que o SMTP é chamado corretamente em produção."""

    def test_send_verification_email_calls_smtp(self, email_service: EmailService, mocker):
        """Verifica que smtplib.SMTP é invocado com as credenciais corretas."""
        mock_settings = mocker.patch("app.services.email_service.settings")
        mock_settings.DEBUG = False
        mock_settings.SMTP_USER = "user@gmail.com"
        mock_settings.SMTP_PASSWORD = "senha_app"
        mock_settings.SMTP_HOST = "smtp.gmail.com"
        mock_settings.SMTP_PORT = 587
        mock_settings.EMAILS_FROM_NAME = "transLog"
        mock_settings.EMAILS_FROM_EMAIL = "noreply@translog.com.br"

        mock_smtp_class = mocker.patch("app.services.email_service.smtplib.SMTP")
        mock_smtp_instance = MagicMock()
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp_instance)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        email_service.send_verification_email(
            to_email="novo@cliente.com",
            full_name="Carlos",
            token="tok123",
        )

        mock_smtp_class.assert_called_once_with("smtp.gmail.com", 587)
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with("user@gmail.com", "senha_app")
        mock_smtp_instance.sendmail.assert_called_once()

    def test_send_otp_email_subject_contains_delivery_code(
        self, email_service: EmailService, mocker
    ):
        """Garante que o assunto do email OTP contém o código da entrega."""
        mock_settings = mocker.patch("app.services.email_service.settings")
        mock_settings.DEBUG = True
        mock_settings.SMTP_USER = ""
        mock_settings.EMAILS_FROM_NAME = "transLog"
        mock_settings.EMAILS_FROM_EMAIL = "noreply@translog.com.br"

        captured_msgs = []

        def capture_log(fmt, *args, **kwargs):
            captured_msgs.append(fmt % args if args else fmt)

        mocker.patch("app.services.email_service.logger").info.side_effect = capture_log

        email_service.send_otp_email(
            to_email="recv@test.com",
            full_name="Ana",
            otp_code="654321",
            delivery_code="TL-XYZ999",
        )

        assert any("TL-XYZ999" in m for m in captured_msgs)

    def test_build_message_sets_correct_headers(self, email_service: EmailService, mocker):
        """Verifica os headers do MIMEMultipart."""
        mock_settings = mocker.patch("app.services.email_service.settings")
        mock_settings.EMAILS_FROM_NAME = "transLog"
        mock_settings.EMAILS_FROM_EMAIL = "noreply@translog.com.br"

        msg = email_service._build_message(
            to_email="dest@test.com",
            subject="Assunto Teste",
            html_body="<p>Corpo</p>",
        )

        assert msg["To"] == "dest@test.com"
        assert msg["Subject"] == "Assunto Teste"
        assert "transLog" in msg["From"]
        assert "noreply@translog.com.br" in msg["From"]
