import base64
import io
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

import qrcode
from qrcode.image.pil import PilImage

from app.core.config import settings


class QRCodeService:
    def generate_delivery_qr(
        self,
        delivery_id: UUID,
        tenant_id: UUID,
        otp_secret: str,
    ) -> tuple[str, datetime]:
        """
        Gera QR Code para confirmação de entrega.
        Retorna (imagem_base64, expires_at).
        """
        expires_at = datetime.now(UTC) + timedelta(seconds=settings.QR_CODE_TTL_SECONDS)
        payload = {
            "delivery_id": str(delivery_id),
            "tenant_id": str(tenant_id),
            "expires_at": expires_at.isoformat(),
            "secret": otp_secret,
        }
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(json.dumps(payload))
        qr.make(fit=True)

        img: PilImage = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        img_b64 = base64.b64encode(buffer.getvalue()).decode()

        return img_b64, expires_at
