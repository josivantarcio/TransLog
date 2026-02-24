"""Testes de integração para o router de Veículos."""

import pytest
from uuid import uuid4

from app.core.security import create_access_token, hash_password
from app.models.tenant import Tenant, TenantPlan, TenantStatus
from app.models.user import User, UserRole
from app.models.vehicle import Vehicle, VehicleType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def active_tenant(db_session):
    uid = uuid4().hex[:8]
    tenant = Tenant(
        name="Frota Ltda",
        slug=f"frota-{uid}",
        email=f"frota-{uid}@x.com",
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
        email=f"admin-{uid}@frota.com",
        hashed_password=hash_password("Admin@1234"),
        full_name="Admin Frota",
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
        email=f"driver-{uid}@frota.com",
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


@pytest.fixture
async def vehicle(db_session, active_tenant):
    uid = uuid4().hex[:4]
    v = Vehicle(
        tenant_id=active_tenant.id,
        plate=f"ABC{uid[:2]}{uid[2:]}".upper()[:7],
        model="Titan 160",
        brand="Honda",
        year=2022,
        color="Preto",
        vehicle_type=VehicleType.MOTORCYCLE,
        is_active=True,
    )
    db_session.add(v)
    await db_session.flush()
    return v


# ---------------------------------------------------------------------------
# POST /vehicles — criar
# ---------------------------------------------------------------------------

class TestCreateVehicle:
    async def test_admin_creates_vehicle(self, client, db_session, admin_user, active_tenant, admin_token):
        await db_session.commit()
        uid = uuid4().hex[:4]
        plate = f"MTO{uid}".upper()[:7]
        response = await client.post(
            "/api/v1/vehicles/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "plate": plate,
                "model": "CG 160",
                "brand": "Honda",
                "year": 2023,
                "color": "Vermelho",
                "vehicle_type": "motorcycle",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["plate"] == plate.upper()
        assert data["is_active"] is True

    async def test_driver_cannot_create_vehicle(self, client, db_session, driver_user, active_tenant, driver_token):
        await db_session.commit()
        response = await client.post(
            "/api/v1/vehicles/",
            headers={"Authorization": f"Bearer {driver_token}"},
            json={"plate": "XYZ1234", "model": "X", "brand": "Y", "vehicle_type": "car"},
        )
        assert response.status_code == 403

    async def test_duplicate_plate_returns_409(self, client, db_session, admin_user, vehicle, active_tenant, admin_token):
        await db_session.commit()
        response = await client.post(
            "/api/v1/vehicles/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "plate": vehicle.plate,
                "model": "Outra",
                "brand": "Marca",
                "vehicle_type": "car",
            },
        )
        assert response.status_code == 409

    async def test_unauthenticated_returns_401(self, client):
        response = await client.post(
            "/api/v1/vehicles/",
            json={"plate": "ABC1234", "model": "X", "brand": "Y", "vehicle_type": "car"},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /vehicles — listar
# ---------------------------------------------------------------------------

class TestListVehicles:
    async def test_admin_lists_vehicles(self, client, db_session, admin_user, vehicle, active_tenant, admin_token):
        await db_session.commit()
        response = await client.get(
            "/api/v1/vehicles/",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert any(v["id"] == str(vehicle.id) for v in data["items"])

    async def test_driver_lists_vehicles(self, client, db_session, driver_user, vehicle, active_tenant, driver_token):
        await db_session.commit()
        response = await client.get(
            "/api/v1/vehicles/",
            headers={"Authorization": f"Bearer {driver_token}"},
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /vehicles/{id} — detalhe
# ---------------------------------------------------------------------------

class TestGetVehicle:
    async def test_get_existing_vehicle(self, client, db_session, admin_user, vehicle, active_tenant, admin_token):
        await db_session.commit()
        response = await client.get(
            f"/api/v1/vehicles/{vehicle.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        assert response.json()["plate"] == vehicle.plate

    async def test_get_nonexistent_vehicle_returns_404(self, client, db_session, admin_user, active_tenant, admin_token):
        await db_session.commit()
        response = await client.get(
            f"/api/v1/vehicles/{uuid4()}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /vehicles/{id} — atualizar
# ---------------------------------------------------------------------------

class TestUpdateVehicle:
    async def test_admin_updates_vehicle(self, client, db_session, admin_user, vehicle, active_tenant, admin_token):
        await db_session.commit()
        response = await client.patch(
            f"/api/v1/vehicles/{vehicle.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"color": "Azul", "year": 2024},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["color"] == "Azul"
        assert data["year"] == 2024


# ---------------------------------------------------------------------------
# DELETE /vehicles/{id} — desativar
# ---------------------------------------------------------------------------

class TestDeactivateVehicle:
    async def test_admin_deactivates_vehicle(self, client, db_session, admin_user, vehicle, active_tenant, admin_token):
        await db_session.commit()
        response = await client.delete(
            f"/api/v1/vehicles/{vehicle.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 204

    async def test_deactivated_vehicle_not_in_active_list(self, client, db_session, admin_user, vehicle, active_tenant, admin_token):
        await db_session.commit()
        await client.delete(
            f"/api/v1/vehicles/{vehicle.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        list_resp = await client.get(
            "/api/v1/vehicles/?only_active=true",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        ids = [v["id"] for v in list_resp.json()["items"]]
        assert str(vehicle.id) not in ids
