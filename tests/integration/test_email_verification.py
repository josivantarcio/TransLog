"""Testes de integração para verificação de email.

Usa SQLite in-memory (conftest.py) e mock no envio de email.
"""

import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.email_verification import EmailVerification
from app.models.tenant import Tenant, TenantPlan, TenantStatus
from app.models.user import User, UserRole
from app.core.security import hash_password
from app.services.email_service import EmailVerificationService


@pytest.fixture
async def sample_tenant(db_session):
    tenant = Tenant(
        name="Empresa Teste",
        slug="empresa-teste",
        email="empresa@teste.com",
        plan=TenantPlan.FREE,
        status=TenantStatus.TRIAL,
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest.fixture
async def unverified_client_user(db_session, sample_tenant):
    user = User(
        tenant_id=sample_tenant.id,
        email="cliente@recebedor.com",
        hashed_password=hash_password("senha123"),
        full_name="Cliente Recebedor",
        role=UserRole.CLIENT,
        is_verified=False,
    )
    db_session.add(user)
    await db_session.flush()
    return user


class TestEmailVerificationService:
    async def test_create_and_send_creates_token(
        self, db_session, unverified_client_user, mocker
    ):
        """Verifica que o token é criado no banco ao chamar create_and_send."""
        # Mock do envio de email (equivalente ao Mockito.doNothing())
        mocker.patch(
            "app.services.email_service.EmailService.send_verification_email"
        )

        svc = EmailVerificationService(db_session)
        verification = await svc.create_and_send(unverified_client_user)

        assert verification.id is not None
        assert verification.user_id == unverified_client_user.id
        assert verification.used is False
        assert verification.expires_at > datetime.now(UTC)

    async def test_create_and_send_calls_email_service(
        self, db_session, unverified_client_user, mocker
    ):
        """Verifica que o email é enviado com os dados corretos."""
        mock_send = mocker.patch(
            "app.services.email_service.EmailService.send_verification_email"
        )

        svc = EmailVerificationService(db_session)
        await svc.create_and_send(unverified_client_user)

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        assert call_kwargs.kwargs["to_email"] == unverified_client_user.email
        assert call_kwargs.kwargs["full_name"] == unverified_client_user.full_name

    async def test_verify_token_marks_user_as_verified(
        self, db_session, unverified_client_user, mocker
    ):
        mocker.patch("app.services.email_service.EmailService.send_verification_email")

        svc = EmailVerificationService(db_session)
        verification = await svc.create_and_send(unverified_client_user)

        user = await svc.verify_token(verification.token)

        assert user.is_verified is True
        assert user.email_verified_at is not None

    async def test_verify_token_marks_token_as_used(
        self, db_session, unverified_client_user, mocker
    ):
        mocker.patch("app.services.email_service.EmailService.send_verification_email")

        svc = EmailVerificationService(db_session)
        verification = await svc.create_and_send(unverified_client_user)

        await svc.verify_token(verification.token)

        result = await db_session.execute(
            select(EmailVerification).where(EmailVerification.id == verification.id)
        )
        updated = result.scalar_one()
        assert updated.used is True

    async def test_verify_invalid_token_raises(self, db_session):
        svc = EmailVerificationService(db_session)
        with pytest.raises(ValueError, match="inválido"):
            await svc.verify_token("token_que_nao_existe")

    async def test_verify_already_used_token_raises(
        self, db_session, unverified_client_user, mocker
    ):
        mocker.patch("app.services.email_service.EmailService.send_verification_email")

        svc = EmailVerificationService(db_session)
        verification = await svc.create_and_send(unverified_client_user)

        await svc.verify_token(verification.token)  # primeira vez — OK

        # Segunda vez deve falhar
        with pytest.raises(ValueError, match="já utilizado"):
            await svc.verify_token(verification.token)

    async def test_verify_expired_token_raises(
        self, db_session, unverified_client_user, mocker
    ):
        mocker.patch("app.services.email_service.EmailService.send_verification_email")

        # Cria token já expirado diretamente
        expired_token = secrets.token_urlsafe(64)
        verification = EmailVerification(
            user_id=unverified_client_user.id,
            token=expired_token,
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        db_session.add(verification)
        await db_session.flush()

        svc = EmailVerificationService(db_session)
        with pytest.raises(ValueError, match="expirado"):
            await svc.verify_token(expired_token)


class TestEmailVerificationEndpoint:
    async def test_verify_email_endpoint_valid_token(
        self, client, db_session, unverified_client_user, mocker
    ):
        mocker.patch("app.services.email_service.EmailService.send_verification_email")

        svc = EmailVerificationService(db_session)
        verification = await svc.create_and_send(unverified_client_user)
        await db_session.commit()

        response = await client.get(
            f"/api/v1/users/verify-email?token={verification.token}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "confirmado" in data["message"].lower()
        assert data["email"] == unverified_client_user.email

    async def test_verify_email_endpoint_invalid_token(self, client):
        response = await client.get("/api/v1/users/verify-email?token=token_invalido")
        assert response.status_code == 400

    async def test_resend_verification_generic_response(self, client):
        """Endpoint não revela se email existe (segurança)."""
        response = await client.post(
            "/api/v1/users/resend-verification",
            json={"email": "naoexiste@test.com"},
        )
        assert response.status_code == 200
        assert "receberá" in response.json()["message"].lower()
