import pyotp

from app.core.config import settings


class OTPService:
    def generate_secret(self) -> str:
        """Gera um secret TOTP aleatório."""
        return pyotp.random_base32()

    def generate_totp(self, secret: str) -> str:
        """Gera o OTP atual para um dado secret (válido por 30s)."""
        totp = pyotp.TOTP(secret, issuer=settings.OTP_ISSUER_NAME)
        return totp.now()

    def verify_totp(self, secret: str, otp_code: str, valid_window: int = 1) -> bool:
        """
        Verifica um OTP contra o secret.
        valid_window=1 permite 1 intervalo de 30s de tolerância.
        """
        totp = pyotp.TOTP(secret, issuer=settings.OTP_ISSUER_NAME)
        return totp.verify(otp_code, valid_window=valid_window)
