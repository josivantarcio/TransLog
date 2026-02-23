"""Testes unitários para QRCodeService."""

import base64
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.services.qrcode_service import QRCodeService
from app.services.otp_service import OTPService


@pytest.fixture
def qr_service() -> QRCodeService:
    return QRCodeService()


@pytest.fixture
def otp_secret() -> str:
    return OTPService().generate_secret()


class TestQRCodeService:
    def test_generate_returns_tuple(self, qr_service: QRCodeService, otp_secret: str):
        result = qr_service.generate_delivery_qr(
            delivery_id=uuid4(),
            tenant_id=uuid4(),
            otp_secret=otp_secret,
        )
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_generate_image_is_valid_base64(self, qr_service: QRCodeService, otp_secret: str):
        img_b64, _ = qr_service.generate_delivery_qr(
            delivery_id=uuid4(),
            tenant_id=uuid4(),
            otp_secret=otp_secret,
        )
        # Não deve lançar exceção ao decodificar
        decoded = base64.b64decode(img_b64)
        # PNG começa com a assinatura \x89PNG
        assert decoded[:4] == b"\x89PNG"

    def test_generate_expires_at_is_in_future(self, qr_service: QRCodeService, otp_secret: str):
        _, expires_at = qr_service.generate_delivery_qr(
            delivery_id=uuid4(),
            tenant_id=uuid4(),
            otp_secret=otp_secret,
        )
        assert expires_at > datetime.now(UTC)

    def test_generate_different_deliveries_different_images(
        self, qr_service: QRCodeService, otp_secret: str
    ):
        img1, _ = qr_service.generate_delivery_qr(uuid4(), uuid4(), otp_secret)
        img2, _ = qr_service.generate_delivery_qr(uuid4(), uuid4(), otp_secret)
        assert img1 != img2

    def test_qr_payload_contains_delivery_id(
        self, qr_service: QRCodeService, otp_secret: str, mocker
    ):
        """Verifica que o payload do QR contém o delivery_id."""
        import qrcode as qrcode_lib

        captured_data = []
        original_add_data = qrcode_lib.QRCode.add_data

        def mock_add_data(self, data):
            captured_data.append(data)
            return original_add_data(self, data)

        mocker.patch.object(qrcode_lib.QRCode, "add_data", mock_add_data)

        delivery_id = uuid4()
        qr_service.generate_delivery_qr(delivery_id, uuid4(), otp_secret)

        assert len(captured_data) == 1
        payload = json.loads(captured_data[0])
        assert payload["delivery_id"] == str(delivery_id)
        assert "expires_at" in payload
        assert "secret" in payload
