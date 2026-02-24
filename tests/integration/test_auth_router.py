"""Testes de integração para autenticação — login, refresh, logout, /me."""

import pytest
from uuid import uuid4

from app.core.security import create_access_token, hash_password
from app.models.tenant import Tenant, TenantPlan, TenantStatus
from app.models.user import User, UserRole


# ---------------------------------------------------------------------------
# Fixtures — slugs/emails únicos por teste para evitar UNIQUE constraint
# ---------------------------------------------------------------------------

@pytest.fixture
async def active_tenant(db_session):
    uid = uuid4().hex[:8]
    tenant = Tenant(
        name="Transportes SA",
        slug=f"transportes-{uid}",
        email=f"contato-{uid}@transportes.com",
        plan=TenantPlan.STARTER,
        status=TenantStatus.ACTIVE,
        is_active=True,
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest.fixture
async def suspended_tenant(db_session):
    uid = uuid4().hex[:8]
    tenant = Tenant(
        name="Suspensa Ltda",
        slug=f"suspensa-{uid}",
        email=f"x-{uid}@x.com",
        plan=TenantPlan.FREE,
        status=TenantStatus.SUSPENDED,
        is_active=True,
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest.fixture
async def admin_user(db_session, active_tenant):
    uid = uuid4().hex[:6]
    user = User(
        tenant_id=active_tenant.id,
        email=f"admin-{uid}@transportes.com",
        hashed_password=hash_password("Admin@1234"),
        full_name="Admin Teste",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def inactive_user(db_session, active_tenant):
    uid = uuid4().hex[:6]
    user = User(
        tenant_id=active_tenant.id,
        email=f"inativo-{uid}@transportes.com",
        hashed_password=hash_password("Qualquer1"),
        full_name="Inativo",
        role=UserRole.DRIVER,
        is_active=False,
    )
    db_session.add(user)
    await db_session.flush()
    return user


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

class TestAuthLogin:
    async def test_login_success(self, client, db_session, admin_user, active_tenant):
        await db_session.commit()
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": admin_user.email,
                "password": "Admin@1234",
                "tenant_slug": active_tenant.slug,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    async def test_login_wrong_password(self, client, db_session, admin_user, active_tenant):
        await db_session.commit()
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": admin_user.email,
                "password": "senha_errada",
                "tenant_slug": active_tenant.slug,
            },
        )
        assert response.status_code == 401
        assert "inválid" in response.json()["detail"].lower()

    async def test_login_wrong_email(self, client, db_session, active_tenant):
        await db_session.commit()
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "naoexiste@transportes.com",
                "password": "Admin@1234",
                "tenant_slug": active_tenant.slug,
            },
        )
        assert response.status_code == 401

    async def test_login_wrong_tenant_slug(self, client, db_session, admin_user):
        await db_session.commit()
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": admin_user.email,
                "password": "Admin@1234",
                "tenant_slug": "slug-que-nao-existe",
            },
        )
        assert response.status_code == 401

    async def test_login_suspended_tenant(self, client, db_session, suspended_tenant):
        uid = uuid4().hex[:6]
        user = User(
            tenant_id=suspended_tenant.id,
            email=f"u-{uid}@x.com",
            hashed_password=hash_password("Senha@123"),
            full_name="X",
            role=UserRole.ADMIN,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": user.email,
                "password": "Senha@123",
                "tenant_slug": suspended_tenant.slug,
            },
        )
        assert response.status_code == 401
        assert "suspensa" in response.json()["detail"].lower()

    async def test_login_inactive_user(self, client, db_session, inactive_user, active_tenant):
        await db_session.commit()
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": inactive_user.email,
                "password": "Qualquer1",
                "tenant_slug": active_tenant.slug,
            },
        )
        assert response.status_code == 401
        assert "desativado" in response.json()["detail"].lower()

    async def test_login_missing_tenant_slug(self, client):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "a@b.com", "password": "senha"},
        )
        assert response.status_code == 422

    async def test_login_invalid_email_format(self, client):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "nao_e_email", "password": "senha", "tenant_slug": "x"},
        )
        assert response.status_code == 422

    async def test_login_access_token_contains_correct_claims(
        self, client, db_session, admin_user, active_tenant
    ):
        await db_session.commit()
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": admin_user.email,
                "password": "Admin@1234",
                "tenant_slug": active_tenant.slug,
            },
        )
        from app.core.security import decode_token
        token_data = decode_token(response.json()["access_token"])
        assert token_data["role"] == "admin"
        assert token_data["tenant_id"] == str(active_tenant.id)
        assert token_data["type"] == "access"


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------

class TestAuthRefresh:
    async def test_refresh_with_valid_token(self, client, db_session, admin_user, active_tenant):
        await db_session.commit()
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": admin_user.email,
                "password": "Admin@1234",
                "tenant_slug": active_tenant.slug,
            },
        )
        refresh_token = login_resp.json()["refresh_token"]
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        assert "access_token" in response.json()

    async def test_refresh_with_invalid_token(self, client):
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "token.invalido.aqui"},
        )
        assert response.status_code == 401

    async def test_refresh_with_access_token_rejected(self, client, db_session, admin_user, active_tenant):
        await db_session.commit()
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": admin_user.email,
                "password": "Admin@1234",
                "tenant_slug": active_tenant.slug,
            },
        )
        access_token = login_resp.json()["access_token"]
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token},
        )
        assert response.status_code == 401

    async def test_refresh_missing_body(self, client):
        response = await client.post("/api/v1/auth/refresh", json={})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

class TestAuthLogout:
    async def test_logout_requires_authentication(self, client):
        response = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": "qualquer"},
        )
        assert response.status_code == 401

    async def test_logout_success(self, client, db_session, admin_user, active_tenant):
        await db_session.commit()
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": admin_user.email,
                "password": "Admin@1234",
                "tenant_slug": active_tenant.slug,
            },
        )
        tokens = login_resp.json()
        response = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert response.status_code == 204

    async def test_refresh_after_logout_rejected(self, client, db_session, admin_user, active_tenant):
        await db_session.commit()
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": admin_user.email,
                "password": "Admin@1234",
                "tenant_slug": active_tenant.slug,
            },
        )
        tokens = login_resp.json()
        await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            json={"refresh_token": tokens["refresh_token"]},
        )
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert response.status_code == 401
        assert "invalidado" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# /me
# ---------------------------------------------------------------------------

class TestAuthMe:
    async def test_me_requires_authentication(self, client):
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    async def test_me_with_invalid_token_returns_401(self, client):
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer token.invalido.aqui"},
        )
        assert response.status_code == 401

    async def test_me_returns_full_user_data(self, client, db_session, admin_user, active_tenant):
        await db_session.commit()
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": admin_user.email,
                "password": "Admin@1234",
                "tenant_slug": active_tenant.slug,
            },
        )
        access_token = login_resp.json()["access_token"]
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == admin_user.email
        assert data["full_name"] == "Admin Teste"
        assert data["role"] == "admin"
        assert data["is_verified"] is True
        assert "user_id" in data
        assert "tenant_id" in data

    async def test_me_with_nonexistent_user_returns_404(self, client):
        token = create_access_token(uuid4(), uuid4(), "admin")
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404
