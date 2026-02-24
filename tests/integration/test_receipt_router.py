"""Testes de integração para o comprovante de entrega em PDF."""

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.security import create_access_token, hash_password
from app.models.delivery import Delivery, DeliveryStatus
from app.models.tenant import Tenant, TenantPlan, TenantStatus
from app.models.user import User, UserRole


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def active_tenant(db_session):
    uid = uuid4().hex[:8]
    tenant = Tenant(
        name=f"Receipt SA {uid}",
        slug=f"receipt-{uid}",
        email=f"receipt-{uid}@sa.com",
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
        email=f"admin-rcpt-{uid}@receipt.com",
        hashed_password=hash_password("Admin@1234"),
        full_name="Admin Receipt",
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
        email=f"driver-rcpt-{uid}@receipt.com",
        hashed_password=hash_password("Driver@1234"),
        full_name="Motorista Receipt",
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
async def delivered_delivery(db_session, active_tenant, driver_user):
    from app.services.otp_service import OTPService
    otp_secret = OTPService().generate_secret()
    tracking = f"TL-RCPT-{uuid4().hex[:6].upper()}"
    d = Delivery(
        tenant_id=active_tenant.id,
        tracking_code=tracking,
        otp_secret=otp_secret,
        qr_code_data=json.dumps({"tracking_code": tracking}),
        status=DeliveryStatus.DELIVERED,
        origin_address="Rua Origem, 10",
        destination_address="Rua Destino, 20",
        recipient_name="João Silva",
        recipient_email="joao@cliente.com",
        recipient_phone="(11) 98765-4321",
        description="Caixa de eletrônicos",
        weight_kg=2.5,
        value=500.0,
        driver_id=driver_user.id,
        delivered_at=datetime.now(UTC),
        accepted_at=datetime.now(UTC),
        picked_up_at=datetime.now(UTC),
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
        recipient_name="Maria",
        recipient_email="maria@mail.com",
    )
    db_session.add(d)
    await db_session.flush()
    return d


# ---------------------------------------------------------------------------
# GET /deliveries/{id}/receipt
# ---------------------------------------------------------------------------

class TestDeliveryReceipt:
    async def test_admin_gets_pdf_for_delivered(
        self, client, db_session, admin_user, active_tenant, delivered_delivery, admin_token
    ):
        await db_session.commit()
        response = await client.get(
            f"/api/v1/deliveries/{delivered_delivery.id}/receipt",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        # PDF começa com %PDF
        assert response.content[:4] == b"%PDF"
        assert delivered_delivery.tracking_code in response.headers["content-disposition"]

    async def test_driver_gets_pdf_for_delivered(
        self, client, db_session, driver_user, active_tenant, delivered_delivery, driver_token
    ):
        await db_session.commit()
        response = await client.get(
            f"/api/v1/deliveries/{delivered_delivery.id}/receipt",
            headers={"Authorization": f"Bearer {driver_token}"},
        )
        assert response.status_code == 200
        assert response.content[:4] == b"%PDF"

    async def test_pending_delivery_returns_400(
        self, client, db_session, admin_user, active_tenant, pending_delivery, admin_token
    ):
        await db_session.commit()
        response = await client.get(
            f"/api/v1/deliveries/{pending_delivery.id}/receipt",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 400
        assert "DELIVERED" in response.json()["detail"]

    async def test_nonexistent_delivery_returns_400(
        self, client, db_session, admin_user, active_tenant, admin_token
    ):
        await db_session.commit()
        response = await client.get(
            f"/api/v1/deliveries/{uuid4()}/receipt",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 400

    async def test_unauthenticated_returns_401(
        self, client, db_session, delivered_delivery
    ):
        await db_session.commit()
        response = await client.get(
            f"/api/v1/deliveries/{delivered_delivery.id}/receipt",
        )
        assert response.status_code == 401

    async def test_pdf_filename_contains_tracking_code(
        self, client, db_session, admin_user, active_tenant, delivered_delivery, admin_token
    ):
        """Verifica que o filename do PDF contém o tracking code."""
        await db_session.commit()
        response = await client.get(
            f"/api/v1/deliveries/{delivered_delivery.id}/receipt",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        # O tracking code deve aparecer no nome do arquivo
        disposition = response.headers["content-disposition"]
        assert delivered_delivery.tracking_code in disposition
