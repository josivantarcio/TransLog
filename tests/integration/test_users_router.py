"""Testes de integração para o router de Usuários."""

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
        name="Empresa Users",
        slug=f"users-{uid}",
        email=f"users-{uid}@empresa.com",
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
        full_name="Admin Master",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def driver_user(db_session, active_tenant):
    uid = uuid4().hex[:6]
    user = User(
        tenant_id=active_tenant.id,
        email=f"driver-{uid}@empresa.com",
        hashed_password=hash_password("Driver@1234"),
        full_name="Motorista",
        role=UserRole.DRIVER,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
def admin_token(admin_user, active_tenant):
    return create_access_token(admin_user.id, active_tenant.id, "admin")


@pytest.fixture
def driver_token(driver_user, active_tenant):
    return create_access_token(driver_user.id, active_tenant.id, "driver")


# ---------------------------------------------------------------------------
# POST /users — criar usuário
# ---------------------------------------------------------------------------

class TestCreateUser:
    async def test_admin_can_create_user(self, client, db_session, admin_user, active_tenant, admin_token):
        await db_session.commit()
        uid = uuid4().hex[:6]
        response = await client.post(
            "/api/v1/users/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": f"novo-{uid}@empresa.com",
                "full_name": "Novo Usuário",
                "password": "Senha@1234",
                "role": "driver",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["role"] == "driver"
        assert data["is_active"] is True
        assert data["is_verified"] is False

    async def test_create_user_requires_admin(self, client, db_session, driver_user, active_tenant, driver_token):
        await db_session.commit()
        response = await client.post(
            "/api/v1/users/",
            headers={"Authorization": f"Bearer {driver_token}"},
            json={
                "email": "x@x.com",
                "full_name": "X",
                "password": "Senha@1234",
                "role": "driver",
            },
        )
        assert response.status_code == 403

    async def test_duplicate_email_returns_409(self, client, db_session, admin_user, active_tenant, admin_token):
        await db_session.commit()
        response = await client.post(
            "/api/v1/users/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": admin_user.email,  # já existe
                "full_name": "Duplicado",
                "password": "Senha@1234",
                "role": "client",
            },
        )
        assert response.status_code == 409

    async def test_weak_password_returns_422(self, client, db_session, admin_user, active_tenant, admin_token):
        await db_session.commit()
        uid = uuid4().hex[:6]
        response = await client.post(
            "/api/v1/users/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": f"weak-{uid}@x.com",
                "full_name": "Weak",
                "password": "abcd",  # muito curta
                "role": "client",
            },
        )
        assert response.status_code == 422

    async def test_create_user_unauthenticated_returns_401(self, client):
        response = await client.post(
            "/api/v1/users/",
            json={"email": "a@b.com", "full_name": "A", "password": "Senha@1234", "role": "client"},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /users — listar
# ---------------------------------------------------------------------------

class TestListUsers:
    async def test_admin_lists_users_of_own_tenant(self, client, db_session, admin_user, driver_user, active_tenant, admin_token):
        await db_session.commit()
        response = await client.get(
            "/api/v1/users/",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2  # admin + driver
        ids = [u["id"] for u in data["items"]]
        assert str(admin_user.id) in ids
        assert str(driver_user.id) in ids

    async def test_list_users_filter_by_role(self, client, db_session, admin_user, driver_user, active_tenant, admin_token):
        await db_session.commit()
        response = await client.get(
            "/api/v1/users/?role=driver",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        for user in response.json()["items"]:
            assert user["role"] == "driver"

    async def test_driver_cannot_list_users(self, client, db_session, driver_user, active_tenant, driver_token):
        await db_session.commit()
        response = await client.get(
            "/api/v1/users/",
            headers={"Authorization": f"Bearer {driver_token}"},
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /users/{id} — detalhe
# ---------------------------------------------------------------------------

class TestGetUser:
    async def test_admin_can_get_any_user(self, client, db_session, admin_user, driver_user, active_tenant, admin_token):
        await db_session.commit()
        response = await client.get(
            f"/api/v1/users/{driver_user.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        assert response.json()["id"] == str(driver_user.id)

    async def test_user_can_get_own_data(self, client, db_session, driver_user, active_tenant, driver_token):
        await db_session.commit()
        response = await client.get(
            f"/api/v1/users/{driver_user.id}",
            headers={"Authorization": f"Bearer {driver_token}"},
        )
        assert response.status_code == 200

    async def test_user_cannot_get_other_user_data(self, client, db_session, admin_user, driver_user, active_tenant, driver_token):
        await db_session.commit()
        response = await client.get(
            f"/api/v1/users/{admin_user.id}",
            headers={"Authorization": f"Bearer {driver_token}"},
        )
        assert response.status_code == 403

    async def test_nonexistent_user_returns_404(self, client, db_session, admin_user, active_tenant, admin_token):
        await db_session.commit()
        response = await client.get(
            f"/api/v1/users/{uuid4()}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /users/{id} — atualizar
# ---------------------------------------------------------------------------

class TestUpdateUser:
    async def test_admin_updates_any_user(self, client, db_session, admin_user, driver_user, active_tenant, admin_token):
        await db_session.commit()
        response = await client.patch(
            f"/api/v1/users/{driver_user.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"full_name": "Nome Novo"},
        )
        assert response.status_code == 200
        assert response.json()["full_name"] == "Nome Novo"

    async def test_user_updates_own_data(self, client, db_session, driver_user, active_tenant, driver_token):
        await db_session.commit()
        response = await client.patch(
            f"/api/v1/users/{driver_user.id}",
            headers={"Authorization": f"Bearer {driver_token}"},
            json={"full_name": "Meu Nome Novo"},
        )
        assert response.status_code == 200

    async def test_user_cannot_update_other_user(self, client, db_session, admin_user, driver_user, active_tenant, driver_token):
        await db_session.commit()
        response = await client.patch(
            f"/api/v1/users/{admin_user.id}",
            headers={"Authorization": f"Bearer {driver_token}"},
            json={"full_name": "Hackeado"},
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# DELETE /users/{id} — desativar
# ---------------------------------------------------------------------------

class TestDeactivateUser:
    async def test_admin_deactivates_driver(self, client, db_session, admin_user, driver_user, active_tenant, admin_token):
        await db_session.commit()
        response = await client.delete(
            f"/api/v1/users/{driver_user.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 204

    async def test_admin_cannot_deactivate_self(self, client, db_session, admin_user, active_tenant, admin_token):
        await db_session.commit()
        response = await client.delete(
            f"/api/v1/users/{admin_user.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 400
        assert "própria" in response.json()["detail"].lower()

    async def test_cannot_deactivate_last_admin(self, client, db_session):
        """Quando há apenas 1 admin ativo no tenant, ele não pode ser desativado por outro."""
        uid = uuid4().hex[:8]
        # Tenant com apenas 1 admin ativo
        tenant = Tenant(
            name=f"Tenant Solo {uid}",
            slug=f"solo-{uid}",
            email=f"solo-{uid}@x.com",
            plan=TenantPlan.FREE,
            status=TenantStatus.ACTIVE,
            is_active=True,
        )
        db_session.add(tenant)
        await db_session.flush()

        uid2 = uuid4().hex[:6]
        sole_admin = User(
            tenant_id=tenant.id,
            email=f"sole-{uid2}@x.com",
            hashed_password=hash_password("Admin@1234"),
            full_name="Único Admin",
            role=UserRole.ADMIN,
            is_active=True,
        )
        # Segundo admin (inativo desde criação) para fazer a requisição
        uid3 = uuid4().hex[:6]
        inactive_admin = User(
            tenant_id=tenant.id,
            email=f"inactive-{uid3}@x.com",
            hashed_password=hash_password("Admin@1234"),
            full_name="Admin Inativo",
            role=UserRole.ADMIN,
            is_active=False,  # inativo desde criação
        )
        db_session.add(sole_admin)
        await db_session.flush()
        db_session.add(inactive_admin)
        await db_session.commit()

        # inactive_admin usa seu token (JWT válido) para tentar desativar sole_admin
        token = create_access_token(inactive_admin.id, tenant.id, "admin")
        response = await client.delete(
            f"/api/v1/users/{sole_admin.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400
        assert "último" in response.json()["detail"].lower()

    async def test_driver_cannot_deactivate_user(self, client, db_session, admin_user, driver_user, active_tenant, driver_token):
        await db_session.commit()
        response = await client.delete(
            f"/api/v1/users/{admin_user.id}",
            headers={"Authorization": f"Bearer {driver_token}"},
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Change Password
# ---------------------------------------------------------------------------

class TestChangePassword:
    async def test_user_changes_own_password(self, client, db_session, driver_user, active_tenant, driver_token):
        await db_session.commit()
        response = await client.post(
            f"/api/v1/users/{driver_user.id}/change-password",
            headers={"Authorization": f"Bearer {driver_token}"},
            json={"current_password": "Driver@1234", "new_password": "Nova@5678"},
        )
        assert response.status_code == 204

    async def test_wrong_current_password_returns_400(self, client, db_session, driver_user, active_tenant, driver_token):
        await db_session.commit()
        response = await client.post(
            f"/api/v1/users/{driver_user.id}/change-password",
            headers={"Authorization": f"Bearer {driver_token}"},
            json={"current_password": "SenhaErrada@1", "new_password": "Nova@5678"},
        )
        assert response.status_code == 400

    async def test_cannot_change_other_users_password(self, client, db_session, admin_user, driver_user, active_tenant, driver_token):
        await db_session.commit()
        response = await client.post(
            f"/api/v1/users/{admin_user.id}/change-password",
            headers={"Authorization": f"Bearer {driver_token}"},
            json={"current_password": "Admin@1234", "new_password": "Nova@5678"},
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Reset Password (admin)
# ---------------------------------------------------------------------------

class TestResetPassword:
    async def test_admin_resets_user_password(self, client, db_session, admin_user, driver_user, active_tenant, admin_token):
        await db_session.commit()
        response = await client.post(
            f"/api/v1/users/{driver_user.id}/reset-password",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"new_password": "Resetada@9999"},
        )
        assert response.status_code == 204

    async def test_driver_cannot_reset_password(self, client, db_session, admin_user, driver_user, active_tenant, driver_token):
        await db_session.commit()
        response = await client.post(
            f"/api/v1/users/{admin_user.id}/reset-password",
            headers={"Authorization": f"Bearer {driver_token}"},
            json={"new_password": "Tentativa@1234"},
        )
        assert response.status_code == 403
