"""Testes de integração para o router de Tenants."""

import pytest
from uuid import uuid4

from app.core.security import create_access_token, hash_password
from app.models.tenant import Tenant, TenantPlan, TenantStatus
from app.models.user import User, UserRole


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def active_tenant(db_session):
    uid = uuid4().hex[:8]
    tenant = Tenant(
        name="Empresa Teste",
        slug=f"empresa-{uid}",
        email=f"contato-{uid}@empresa.com",
        plan=TenantPlan.STARTER,
        status=TenantStatus.ACTIVE,
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
        email=f"admin-{uid}@empresa.com",
        hashed_password=hash_password("Admin@1234"),
        full_name="Admin",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
def admin_token(admin_user, active_tenant):
    return create_access_token(admin_user.id, active_tenant.id, "admin")


# ---------------------------------------------------------------------------
# Onboarding (público)
# ---------------------------------------------------------------------------

class TestTenantOnboard:
    async def test_onboard_creates_tenant_and_admin(self, client):
        uid = uuid4().hex[:8]
        response = await client.post(
            "/api/v1/tenants/onboard",
            json={
                "name": "Nova Empresa",
                "email": f"nova-{uid}@empresa.com",
                "plan": "free",
                "admin_name": "Admin Nova",
                "admin_email": f"admin-{uid}@nova.com",
                "admin_password": "Admin@1234",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "tenant" in data
        assert "admin_user_id" in data
        assert data["tenant"]["plan"] == "free"
        assert data["admin_email"] == f"admin-{uid}@nova.com"

    async def test_onboard_generates_slug_from_name(self, client):
        uid = uuid4().hex[:8]
        response = await client.post(
            "/api/v1/tenants/onboard",
            json={
                "name": f"Transportes São Paulo {uid}",
                "email": f"sp-{uid}@transp.com",
                "plan": "free",
                "admin_name": "Admin SP",
                "admin_email": f"admin-sp-{uid}@transp.com",
                "admin_password": "Admin@1234",
            },
        )
        assert response.status_code == 201
        slug = response.json()["tenant"]["slug"]
        assert slug  # slug gerado automaticamente
        assert " " not in slug

    async def test_onboard_duplicate_slug_returns_409(self, client, db_session, active_tenant):
        await db_session.commit()
        response = await client.post(
            "/api/v1/tenants/onboard",
            json={
                "name": "Outra Empresa",
                "slug": active_tenant.slug,  # mesmo slug
                "email": "outro@email.com",
                "plan": "free",
                "admin_name": "Admin",
                "admin_email": "admin@outro.com",
                "admin_password": "Admin@1234",
            },
        )
        assert response.status_code == 409

    async def test_onboard_invalid_slug_format_returns_422(self, client):
        response = await client.post(
            "/api/v1/tenants/onboard",
            json={
                "name": "Empresa",
                "slug": "Slug Inválido!",
                "email": "e@e.com",
                "plan": "free",
                "admin_name": "Admin",
                "admin_email": "a@a.com",
                "admin_password": "Admin@1234",
            },
        )
        assert response.status_code == 422

    async def test_onboard_weak_admin_password_returns_422(self, client):
        uid = uuid4().hex[:8]
        response = await client.post(
            "/api/v1/tenants/onboard",
            json={
                "name": "Empresa Fraca",
                "email": f"fraca-{uid}@x.com",
                "plan": "free",
                "admin_name": "Admin",
                "admin_email": f"a-{uid}@x.com",
                "admin_password": "curta",  # menos de 8 chars
            },
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /tenants/me
# ---------------------------------------------------------------------------

class TestTenantMe:
    async def test_get_my_tenant_requires_auth(self, client):
        response = await client.get("/api/v1/tenants/me")
        assert response.status_code == 401

    async def test_get_my_tenant_returns_data(self, client, db_session, active_tenant, admin_user, admin_token):
        await db_session.commit()
        response = await client.get(
            "/api/v1/tenants/me",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["slug"] == active_tenant.slug
        assert data["name"] == "Empresa Teste"


# ---------------------------------------------------------------------------
# PATCH /tenants/me
# ---------------------------------------------------------------------------

class TestTenantUpdate:
    async def test_update_my_tenant_name(self, client, db_session, active_tenant, admin_user, admin_token):
        await db_session.commit()
        response = await client.patch(
            "/api/v1/tenants/me",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Nome Atualizado"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Nome Atualizado"

    async def test_update_requires_admin_role(self, client, db_session, active_tenant, admin_user):
        await db_session.commit()
        driver_token = create_access_token(admin_user.id, active_tenant.id, "driver")
        response = await client.patch(
            "/api/v1/tenants/me",
            headers={"Authorization": f"Bearer {driver_token}"},
            json={"name": "Tentativa"},
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Suspend / Activate
# ---------------------------------------------------------------------------

class TestTenantSuspendActivate:
    async def test_suspend_tenant(self, client, db_session, active_tenant, admin_user, admin_token):
        await db_session.commit()
        response = await client.post(
            f"/api/v1/tenants/{active_tenant.id}/suspend",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "suspended"

    async def test_activate_tenant(self, client, db_session, active_tenant, admin_user, admin_token):
        await db_session.commit()
        # Suspende primeiro
        await client.post(
            f"/api/v1/tenants/{active_tenant.id}/suspend",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # Ativa
        response = await client.post(
            f"/api/v1/tenants/{active_tenant.id}/activate",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "active"
