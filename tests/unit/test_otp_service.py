"""Testes unitários para OTPService (pyotp/TOTP).

Sem banco, sem I/O — puramente unitários.
"""

import pytest

from app.services.otp_service import OTPService


@pytest.fixture
def otp_service() -> OTPService:
    return OTPService()


class TestOTPService:
    def test_generate_secret_returns_base32_string(self, otp_service: OTPService):
        secret = otp_service.generate_secret()
        assert isinstance(secret, str)
        assert len(secret) >= 16

    def test_generate_two_secrets_are_different(self, otp_service: OTPService):
        s1 = otp_service.generate_secret()
        s2 = otp_service.generate_secret()
        assert s1 != s2

    def test_generate_totp_returns_6_digit_string(self, otp_service: OTPService):
        secret = otp_service.generate_secret()
        otp = otp_service.generate_totp(secret)
        assert isinstance(otp, str)
        assert len(otp) == 6
        assert otp.isdigit()

    def test_verify_correct_otp_returns_true(self, otp_service: OTPService):
        secret = otp_service.generate_secret()
        otp = otp_service.generate_totp(secret)
        assert otp_service.verify_totp(secret, otp) is True

    def test_verify_wrong_otp_returns_false(self, otp_service: OTPService):
        secret = otp_service.generate_secret()
        assert otp_service.verify_totp(secret, "000000") is False

    def test_verify_otp_wrong_secret_returns_false(self, otp_service: OTPService):
        secret1 = otp_service.generate_secret()
        secret2 = otp_service.generate_secret()
        otp = otp_service.generate_totp(secret1)
        assert otp_service.verify_totp(secret2, otp) is False

    def test_verify_otp_invalid_format_returns_false(self, otp_service: OTPService):
        secret = otp_service.generate_secret()
        assert otp_service.verify_totp(secret, "abc123") is False
        assert otp_service.verify_totp(secret, "") is False

    def test_same_secret_same_window_same_otp(self, otp_service: OTPService):
        secret = otp_service.generate_secret()
        otp1 = otp_service.generate_totp(secret)
        otp2 = otp_service.generate_totp(secret)
        # Dentro da mesma janela de 30s devem ser iguais
        assert otp1 == otp2
