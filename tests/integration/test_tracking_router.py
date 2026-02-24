"""Testes de integração para o router de Rastreamento GPS."""

import json
from uuid import uuid4

import pytest

from app.core.security import create_access_token, hash_password
from app.models.delivery import Delivery, DeliveryStatus
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
        name=f"Tracking SA {uid}",
        slug=f"tracking-{uid}",
        email=f"tracking-{uid}@sa.com",
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
        email=f"admin-trk-{uid}@track.com",
        hashed_password=hash_password("Admin@1234"),
        full_name="Admin Track",
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
        email=f"driver-trk-{uid}@track.com",
        hashed_password=hash_password("Driver@1234"),
        full_name="Motorista Track",
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
async def in_transit_delivery(db_session, active_tenant, driver_user):
    from app.services.otp_service import OTPService
    otp_secret = OTPService().generate_secret()
    tracking = f"TL-TRACK-{uuid4().hex[:6].upper()}"
    d = Delivery(
        tenant_id=active_tenant.id,
        tracking_code=tracking,
        otp_secret=otp_secret,
        qr_code_data=json.dumps({"tracking_code": tracking}),
        status=DeliveryStatus.IN_TRANSIT,
        origin_address="Rua Origem, 10",
        destination_address="Rua Destino, 20",
        recipient_name="Cliente GPS",
        recipient_email="cliente@gps.com",
        driver_id=driver_user.id,
        destination_lat=-23.5505,
        destination_lng=-46.6333,
    )
    db_session.add(d)
    await db_session.flush()
    return d


@pytest.fixture
async def pending_delivery(db_session, active_tenant):
    from app.services.otp_service import OTPService
    otp_secret = OTPService().generate_secret()
    tracking = f"TL-PEND-{uuid4().hex[:6].upper()}"
    d = Delivery(
        tenant_id=active_tenant.id,
        tracking_code=tracking,
        otp_secret=otp_secret,
        qr_code_data=json.dumps({"tracking_code": tracking}),
        status=DeliveryStatus.PENDING,
        origin_address="Rua A, 1",
        destination_address="Rua B, 2",
        recipient_name="Cliente",
        recipient_email="c@c.com",
    )
    db_session.add(d)
    await db_session.flush()
    return d


# ---------------------------------------------------------------------------
# POST /tracking — registrar evento GPS
# ---------------------------------------------------------------------------

class TestRecordTrackingEvent:
    async def test_driver_records_gps_event(
        self, client, db_session, driver_user, active_tenant, in_transit_delivery, driver_token
    ):
        await db_session.commit()
        response = await client.post(
            "/api/v1/tracking/",
            headers={"Authorization": f"Bearer {driver_token}"},
            json={
                "delivery_id": str(in_transit_delivery.id),
                "latitude": -23.5505,
                "longitude": -46.6333,
                "accuracy": 5.0,
                "speed": 30.0,
                "heading": 90.0,
                "event_description": "Em rota",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["delivery_id"] == str(in_transit_delivery.id)
        assert data["driver_id"] == str(driver_user.id)
        assert float(data["latitude"]) == pytest.approx(-23.5505, abs=1e-4)
        assert float(data["longitude"]) == pytest.approx(-46.6333, abs=1e-4)
        assert data["status_snapshot"] == "in_transit"
        assert data["event_description"] == "Em rota"

    async def test_admin_cannot_record_gps(
        self, client, db_session, admin_user, active_tenant, in_transit_delivery, admin_token
    ):
        await db_session.commit()
        response = await client.post(
            "/api/v1/tracking/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "delivery_id": str(in_transit_delivery.id),
                "latitude": -23.5505,
                "longitude": -46.6333,
            },
        )
        assert response.status_code == 403

    async def test_driver_cannot_track_pending_delivery(
        self, client, db_session, driver_user, active_tenant, pending_delivery, driver_token
    ):
        await db_session.commit()
        response = await client.post(
            "/api/v1/tracking/",
            headers={"Authorization": f"Bearer {driver_token}"},
            json={
                "delivery_id": str(pending_delivery.id),
                "latitude": -23.0,
                "longitude": -46.0,
            },
        )
        assert response.status_code == 400
        assert "trânsito" in response.json()["detail"]

    async def test_track_nonexistent_delivery_returns_400(
        self, client, db_session, driver_user, active_tenant, driver_token
    ):
        await db_session.commit()
        response = await client.post(
            "/api/v1/tracking/",
            headers={"Authorization": f"Bearer {driver_token}"},
            json={
                "delivery_id": str(uuid4()),
                "latitude": -23.0,
                "longitude": -46.0,
            },
        )
        assert response.status_code == 400

    async def test_invalid_latitude_returns_422(
        self, client, db_session, driver_user, active_tenant, in_transit_delivery, driver_token
    ):
        await db_session.commit()
        response = await client.post(
            "/api/v1/tracking/",
            headers={"Authorization": f"Bearer {driver_token}"},
            json={
                "delivery_id": str(in_transit_delivery.id),
                "latitude": 999.0,  # inválido (> 90)
                "longitude": -46.0,
            },
        )
        assert response.status_code == 422

    async def test_unauthenticated_returns_401(
        self, client, db_session, in_transit_delivery
    ):
        await db_session.commit()
        response = await client.post(
            "/api/v1/tracking/",
            json={
                "delivery_id": str(in_transit_delivery.id),
                "latitude": -23.0,
                "longitude": -46.0,
            },
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /tracking/{delivery_id}/live — posição ao vivo
# ---------------------------------------------------------------------------

class TestLiveTracking:
    async def test_no_live_data_returns_message(
        self, client, db_session, admin_user, active_tenant, in_transit_delivery, admin_token
    ):
        await db_session.commit()
        response = await client.get(
            f"/api/v1/tracking/{in_transit_delivery.id}/live",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        assert "message" in response.json()

    async def test_live_data_after_event(
        self, client, db_session, driver_user, admin_user, active_tenant,
        in_transit_delivery, driver_token, admin_token
    ):
        await db_session.commit()
        # Motorista envia posição
        await client.post(
            "/api/v1/tracking/",
            headers={"Authorization": f"Bearer {driver_token}"},
            json={
                "delivery_id": str(in_transit_delivery.id),
                "latitude": -23.5600,
                "longitude": -46.6400,
                "speed": 45.0,
            },
        )
        # Admin consulta posição ao vivo
        response = await client.get(
            f"/api/v1/tracking/{in_transit_delivery.id}/live",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "latitude" in data
        assert float(data["latitude"]) == pytest.approx(-23.5600, abs=1e-3)

    async def test_live_nonexistent_delivery_returns_404(
        self, client, db_session, admin_user, active_tenant, admin_token
    ):
        await db_session.commit()
        response = await client.get(
            f"/api/v1/tracking/{uuid4()}/live",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /tracking/{delivery_id} — histórico
# ---------------------------------------------------------------------------

class TestTrackingHistory:
    async def test_history_empty_initially(
        self, client, db_session, admin_user, active_tenant, in_transit_delivery, admin_token
    ):
        await db_session.commit()
        response = await client.get(
            f"/api/v1/tracking/{in_transit_delivery.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) == 0

    async def test_history_has_events_after_record(
        self, client, db_session, driver_user, admin_user, active_tenant,
        in_transit_delivery, driver_token, admin_token
    ):
        await db_session.commit()
        # Registra dois eventos
        for lat in [-23.5505, -23.5510]:
            await client.post(
                "/api/v1/tracking/",
                headers={"Authorization": f"Bearer {driver_token}"},
                json={
                    "delivery_id": str(in_transit_delivery.id),
                    "latitude": lat,
                    "longitude": -46.6333,
                },
            )
        # Admin consulta histórico
        response = await client.get(
            f"/api/v1/tracking/{in_transit_delivery.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2

    async def test_history_nonexistent_delivery_returns_404(
        self, client, db_session, admin_user, active_tenant, admin_token
    ):
        await db_session.commit()
        response = await client.get(
            f"/api/v1/tracking/{uuid4()}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404

    async def test_driver_can_see_own_history(
        self, client, db_session, driver_user, active_tenant, in_transit_delivery, driver_token
    ):
        await db_session.commit()
        response = await client.get(
            f"/api/v1/tracking/{in_transit_delivery.id}",
            headers={"Authorization": f"Bearer {driver_token}"},
        )
        assert response.status_code == 200
