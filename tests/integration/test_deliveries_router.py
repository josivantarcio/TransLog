"""Testes de integração para o router de Entregas."""

import pytest
from uuid import uuid4

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
        name="Entregas SA",
        slug=f"entregas-{uid}",
        email=f"entregas-{uid}@sa.com",
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
        email=f"admin-{uid}@entregas.com",
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
async def driver_user(db_session, active_tenant):
    uid = uuid4().hex[:6]
    user = User(
        tenant_id=active_tenant.id,
        email=f"driver-{uid}@entregas.com",
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
async def vehicle(db_session, active_tenant):
    uid = uuid4().hex[:4]
    v = Vehicle(
        tenant_id=active_tenant.id,
        plate=f"ENT{uid}".upper()[:7],
        model="Titan",
        brand="Honda",
        vehicle_type=VehicleType.MOTORCYCLE,
        is_active=True,
    )
    db_session.add(v)
    await db_session.flush()
    return v


@pytest.fixture
def admin_token(admin_user, active_tenant):
    return create_access_token(admin_user.id, active_tenant.id, "admin")


@pytest.fixture
def driver_token(driver_user, active_tenant):
    return create_access_token(driver_user.id, active_tenant.id, "driver")


@pytest.fixture
async def pending_delivery(db_session, active_tenant):
    from app.services.otp_service import OTPService
    import json
    otp_secret = OTPService().generate_secret()
    tracking = f"TL-TEST-{uuid4().hex[:6].upper()}"
    d = Delivery(
        tenant_id=active_tenant.id,
        tracking_code=tracking,
        otp_secret=otp_secret,
        qr_code_data=json.dumps({"tracking_code": tracking}),
        status=DeliveryStatus.PENDING,
        origin_address="Rua A, 100",
        destination_address="Rua B, 200",
        recipient_name="Cliente Teste",
        recipient_email="cliente@teste.com",
    )
    db_session.add(d)
    await db_session.flush()
    return d


@pytest.fixture
async def in_transit_delivery(db_session, active_tenant, driver_user):
    from app.services.otp_service import OTPService
    import json
    otp_secret = OTPService().generate_secret()
    tracking = f"TL-TRANSIT-{uuid4().hex[:6].upper()}"
    d = Delivery(
        tenant_id=active_tenant.id,
        tracking_code=tracking,
        otp_secret=otp_secret,
        qr_code_data=json.dumps({"tracking_code": tracking}),
        status=DeliveryStatus.IN_TRANSIT,
        origin_address="Rua A, 100",
        destination_address="Rua B, 200",
        recipient_name="Cliente",
        recipient_email="cliente@teste.com",
        driver_id=driver_user.id,
        # Coordenadas próximas — facilita teste de GPS
        destination_lat=-23.5505,
        destination_lng=-46.6333,
    )
    db_session.add(d)
    await db_session.flush()
    return d


# ---------------------------------------------------------------------------
# POST /deliveries — criar
# ---------------------------------------------------------------------------

class TestCreateDelivery:
    async def test_admin_creates_delivery(self, client, db_session, admin_user, active_tenant, admin_token):
        await db_session.commit()
        response = await client.post(
            "/api/v1/deliveries/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "origin_address": "Rua A, 100",
                "destination_address": "Rua B, 200",
                "recipient_name": "João Silva",
                "recipient_email": "joao@cliente.com",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"
        assert data["tracking_code"].startswith("TL-")
        assert data["recipient_email"] == "joao@cliente.com"

    async def test_driver_cannot_create_delivery(self, client, db_session, driver_user, active_tenant, driver_token):
        await db_session.commit()
        response = await client.post(
            "/api/v1/deliveries/",
            headers={"Authorization": f"Bearer {driver_token}"},
            json={
                "origin_address": "A",
                "destination_address": "B",
                "recipient_name": "X",
                "recipient_email": "x@x.com",
            },
        )
        assert response.status_code == 403

    async def test_missing_recipient_email_returns_422(self, client, db_session, admin_user, active_tenant, admin_token):
        await db_session.commit()
        response = await client.post(
            "/api/v1/deliveries/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"origin_address": "A", "destination_address": "B", "recipient_name": "X"},
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /deliveries — listar
# ---------------------------------------------------------------------------

class TestListDeliveries:
    async def test_admin_lists_all_deliveries(self, client, db_session, admin_user, pending_delivery, active_tenant, admin_token):
        await db_session.commit()
        response = await client.get(
            "/api/v1/deliveries/",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        assert response.json()["total"] >= 1

    async def test_driver_lists_only_own_deliveries(self, client, db_session, driver_user, in_transit_delivery, active_tenant, driver_token):
        await db_session.commit()
        response = await client.get(
            "/api/v1/deliveries/",
            headers={"Authorization": f"Bearer {driver_token}"},
        )
        assert response.status_code == 200
        for d in response.json()["items"]:
            assert d["driver_id"] == str(driver_user.id)

    async def test_filter_by_status(self, client, db_session, admin_user, pending_delivery, active_tenant, admin_token):
        await db_session.commit()
        response = await client.get(
            "/api/v1/deliveries/?status=pending",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        for d in response.json()["items"]:
            assert d["status"] == "pending"


# ---------------------------------------------------------------------------
# GET /deliveries/{id} — detalhe
# ---------------------------------------------------------------------------

class TestGetDelivery:
    async def test_admin_gets_any_delivery(self, client, db_session, admin_user, pending_delivery, active_tenant, admin_token):
        await db_session.commit()
        response = await client.get(
            f"/api/v1/deliveries/{pending_delivery.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        assert response.json()["tracking_code"] == pending_delivery.tracking_code

    async def test_driver_gets_own_delivery(self, client, db_session, driver_user, in_transit_delivery, active_tenant, driver_token):
        await db_session.commit()
        response = await client.get(
            f"/api/v1/deliveries/{in_transit_delivery.id}",
            headers={"Authorization": f"Bearer {driver_token}"},
        )
        assert response.status_code == 200

    async def test_driver_cannot_get_other_delivery(self, client, db_session, driver_user, pending_delivery, active_tenant, driver_token):
        await db_session.commit()
        response = await client.get(
            f"/api/v1/deliveries/{pending_delivery.id}",
            headers={"Authorization": f"Bearer {driver_token}"},
        )
        assert response.status_code == 403

    async def test_nonexistent_returns_404(self, client, db_session, admin_user, active_tenant, admin_token):
        await db_session.commit()
        response = await client.get(
            f"/api/v1/deliveries/{uuid4()}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /deliveries/{id}/assign — atribuir motorista
# ---------------------------------------------------------------------------

class TestAssignDriver:
    async def test_assign_driver_to_pending_delivery(self, client, db_session, admin_user, driver_user, vehicle, pending_delivery, active_tenant, admin_token):
        await db_session.commit()
        response = await client.post(
            f"/api/v1/deliveries/{pending_delivery.id}/assign",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"driver_id": str(driver_user.id), "vehicle_id": str(vehicle.id)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "in_transit"
        assert data["driver_id"] == str(driver_user.id)

    async def test_cannot_assign_to_delivered_delivery(self, client, db_session, admin_user, driver_user, vehicle, active_tenant, admin_token):
        await db_session.commit()
        # Cria entrega já entregue
        from app.services.otp_service import OTPService
        import json
        tracking = f"TL-DONE-{uuid4().hex[:6].upper()}"
        d = Delivery(
            tenant_id=active_tenant.id,
            tracking_code=tracking,
            otp_secret=OTPService().generate_secret(),
            qr_code_data=json.dumps({"tracking_code": tracking}),
            status=DeliveryStatus.DELIVERED,
            origin_address="A", destination_address="B",
            recipient_name="X", recipient_email="x@x.com",
        )
        db_session.add(d)
        await db_session.commit()

        response = await client.post(
            f"/api/v1/deliveries/{d.id}/assign",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"driver_id": str(driver_user.id), "vehicle_id": str(vehicle.id)},
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# POST /deliveries/{id}/cancel
# ---------------------------------------------------------------------------

class TestCancelDelivery:
    async def test_cancel_pending_delivery(self, client, db_session, admin_user, pending_delivery, active_tenant, admin_token):
        await db_session.commit()
        response = await client.post(
            f"/api/v1/deliveries/{pending_delivery.id}/cancel",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"reason": "Cancelamento a pedido do cliente"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"

    async def test_cannot_cancel_delivered_delivery(self, client, db_session, admin_user, active_tenant, admin_token):
        await db_session.commit()
        from app.services.otp_service import OTPService
        import json
        tracking = f"TL-DONE2-{uuid4().hex[:6].upper()}"
        d = Delivery(
            tenant_id=active_tenant.id,
            tracking_code=tracking,
            otp_secret=OTPService().generate_secret(),
            qr_code_data=json.dumps({"tracking_code": tracking}),
            status=DeliveryStatus.DELIVERED,
            origin_address="A", destination_address="B",
            recipient_name="X", recipient_email="x@x.com",
        )
        db_session.add(d)
        await db_session.commit()

        response = await client.post(
            f"/api/v1/deliveries/{d.id}/cancel",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"reason": "Tentativa inválida"},
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /deliveries/{id}/qrcode
# ---------------------------------------------------------------------------

class TestDeliveryQRCode:
    async def test_get_qrcode_returns_base64(self, client, db_session, admin_user, pending_delivery, active_tenant, admin_token):
        await db_session.commit()
        response = await client.get(
            f"/api/v1/deliveries/{pending_delivery.id}/qrcode",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "qr_code_image" in data
        assert len(data["qr_code_image"]) > 100  # base64 válido


# ---------------------------------------------------------------------------
# Fluxo de conclusão: initiate → confirm
# ---------------------------------------------------------------------------

class TestDeliveryCompletion:
    async def test_initiate_completion_sends_otp(self, client, db_session, driver_user, in_transit_delivery, active_tenant, driver_token):
        await db_session.commit()
        response = await client.post(
            f"/api/v1/deliveries/{in_transit_delivery.id}/initiate-completion",
            headers={"Authorization": f"Bearer {driver_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "OTP" in data["message"] or "enviado" in data["message"].lower()
        assert data["expires_in"] == 600

    async def test_confirm_with_invalid_otp_returns_401(self, client, db_session, driver_user, in_transit_delivery, active_tenant, driver_token, fake_redis):
        await db_session.commit()
        # Popula Redis com OTP
        fake_redis._store[f"otp:delivery:{in_transit_delivery.id}"] = "123456"

        response = await client.post(
            f"/api/v1/deliveries/{in_transit_delivery.id}/confirm",
            headers={"Authorization": f"Bearer {driver_token}"},
            json={"otp": "999999", "gps_lat": -23.5505, "gps_lng": -46.6333},
        )
        assert response.status_code == 401

    async def test_confirm_with_valid_otp_and_gps(self, client, db_session, driver_user, in_transit_delivery, active_tenant, driver_token, fake_redis):
        await db_session.commit()
        fake_redis._store[f"otp:delivery:{in_transit_delivery.id}"] = "654321"

        response = await client.post(
            f"/api/v1/deliveries/{in_transit_delivery.id}/confirm",
            headers={"Authorization": f"Bearer {driver_token}"},
            json={
                "otp": "654321",
                "gps_lat": -23.5505,  # mesmo ponto do destino — distância 0
                "gps_lng": -46.6333,
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "delivered"

    async def test_confirm_gps_too_far_returns_422(self, client, db_session, driver_user, in_transit_delivery, active_tenant, driver_token, fake_redis):
        await db_session.commit()
        fake_redis._store[f"otp:delivery:{in_transit_delivery.id}"] = "777777"

        response = await client.post(
            f"/api/v1/deliveries/{in_transit_delivery.id}/confirm",
            headers={"Authorization": f"Bearer {driver_token}"},
            json={
                "otp": "777777",
                "gps_lat": -22.9068,   # Rio de Janeiro — muito longe de SP
                "gps_lng": -43.1729,
            },
        )
        assert response.status_code == 422
        assert "GPS_TOO_FAR" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Autorização manual — admin
# ---------------------------------------------------------------------------

class TestAdminAuthorization:
    async def test_admin_authorizes_delivery_with_own_password(self, client, db_session, admin_user, in_transit_delivery, active_tenant, admin_token, fake_redis):
        await db_session.commit()
        response = await client.post(
            f"/api/v1/deliveries/{in_transit_delivery.id}/authorize-admin",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"password": "Admin@1234", "reason": "GPS indisponível"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "delivered"
        assert data["manually_authorized"] is True

    async def test_admin_auth_wrong_password_returns_401(self, client, db_session, admin_user, in_transit_delivery, active_tenant, admin_token):
        await db_session.commit()
        response = await client.post(
            f"/api/v1/deliveries/{in_transit_delivery.id}/authorize-admin",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"password": "SenhaErrada@1", "reason": "Teste"},
        )
        assert response.status_code == 401

    async def test_driver_cannot_use_admin_authorization(self, client, db_session, driver_user, in_transit_delivery, active_tenant, driver_token):
        await db_session.commit()
        response = await client.post(
            f"/api/v1/deliveries/{in_transit_delivery.id}/authorize-admin",
            headers={"Authorization": f"Bearer {driver_token}"},
            json={"password": "Admin@1234", "reason": "Teste"},
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Autorização manual — operador
# ---------------------------------------------------------------------------

class TestOperatorAuthorization:
    async def test_operator_authorizes_with_client_otp(self, client, db_session, driver_user, in_transit_delivery, active_tenant, driver_token, fake_redis):
        await db_session.commit()
        fake_redis._store[f"otp:delivery:{in_transit_delivery.id}"] = "112233"

        response = await client.post(
            f"/api/v1/deliveries/{in_transit_delivery.id}/authorize-operator",
            headers={"Authorization": f"Bearer {driver_token}"},
            json={"client_otp": "112233", "reason": "GPS falhou"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "delivered"
        assert data["manually_authorized"] is True

    async def test_operator_wrong_otp_returns_401(self, client, db_session, driver_user, in_transit_delivery, active_tenant, driver_token, fake_redis):
        await db_session.commit()
        fake_redis._store[f"otp:delivery:{in_transit_delivery.id}"] = "112233"

        response = await client.post(
            f"/api/v1/deliveries/{in_transit_delivery.id}/authorize-operator",
            headers={"Authorization": f"Bearer {driver_token}"},
            json={"client_otp": "000000", "reason": "GPS falhou"},
        )
        assert response.status_code == 401
