"""Serviço de gestão de Entregas.

Fluxo de conclusão de entrega:
  1. create() — gera tracking_code, otp_secret, QR Code, envia email ao destinatário
  2. assign_driver() — PENDING → IN_TRANSIT (simplificado)
  3. initiate_completion() — DRIVER escaneia QR, gera OTP TOTP, envia email ao cliente
  4. confirm_delivery() — valida OTP + GPS → DELIVERED
  5. authorize_operator() / authorize_admin() — fallback manual com auditoria
"""

import json
import math
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.models.delivery import Delivery, DeliveryStatus
from app.models.delivery_authorization_log import AuthorizationMethod, DeliveryAuthorizationLog
from app.models.user import User, UserRole
from app.models.vehicle import Vehicle
from app.schemas.delivery import DeliveryCreate, DeliveryUpdate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_tracking_code() -> str:
    """Gera código de rastreamento: TL-YYYYMMDD-XXXXXX."""
    import random
    import string
    today = datetime.now(UTC).strftime("%Y%m%d")
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"TL-{today}-{suffix}"


def _haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distância em metros entre dois pontos GPS (fórmula de Haversine)."""
    R = 6_371_000  # raio da Terra em metros
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class DeliveryService:
    OTP_TTL_SECONDS = 600          # 10 minutos
    MAX_GPS_RADIUS_METERS = 200.0  # distância máxima aceita do destino

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, tenant_id: UUID, payload: DeliveryCreate) -> Delivery:
        """Cria entrega com tracking_code único e otp_secret TOTP."""
        from app.services.otp_service import OTPService

        # Garante tracking_code único
        for _ in range(5):
            code = _generate_tracking_code()
            existing = await self.db.execute(
                select(Delivery).where(Delivery.tracking_code == code)
            )
            if not existing.scalar_one_or_none():
                break

        otp_svc = OTPService()
        otp_secret = otp_svc.generate_secret()
        qr_payload = json.dumps({"tracking_code": code, "tenant_id": str(tenant_id)})
        # QR Code image é gerada sob demanda no endpoint /qrcode (não armazenada no DB)

        delivery = Delivery(
            tenant_id=tenant_id,
            tracking_code=code,
            otp_secret=otp_secret,
            qr_code_data=qr_payload,
            status=DeliveryStatus.PENDING,
            origin_address=payload.origin_address,
            origin_lat=payload.origin_lat,
            origin_lng=payload.origin_lng,
            destination_address=payload.destination_address,
            destination_lat=payload.destination_lat,
            destination_lng=payload.destination_lng,
            description=payload.description,
            weight_kg=payload.weight_kg,
            value=payload.value,
            estimated_delivery_at=payload.estimated_delivery_at,
            delivery_notes=payload.delivery_notes,
            client_id=payload.client_id,
            recipient_name=payload.recipient_name,
            recipient_email=payload.recipient_email,
            recipient_phone=payload.recipient_phone,
        )
        self.db.add(delivery)
        await self.db.flush()
        return delivery

    async def get_by_id(self, tenant_id: UUID, delivery_id: UUID) -> Delivery:
        result = await self.db.execute(
            select(Delivery).where(Delivery.id == delivery_id, Delivery.tenant_id == tenant_id)
        )
        delivery = result.scalar_one_or_none()
        if not delivery:
            raise ValueError("Entrega não encontrada.")
        return delivery

    async def get_by_tracking_code(self, tenant_id: UUID, tracking_code: str) -> Delivery:
        result = await self.db.execute(
            select(Delivery).where(
                Delivery.tracking_code == tracking_code,
                Delivery.tenant_id == tenant_id,
            )
        )
        delivery = result.scalar_one_or_none()
        if not delivery:
            raise ValueError("Entrega não encontrada.")
        return delivery

    async def list(
        self,
        tenant_id: UUID,
        status_filter: DeliveryStatus | None = None,
        driver_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Delivery], int]:
        query = select(Delivery).where(Delivery.tenant_id == tenant_id)
        if status_filter:
            query = query.where(Delivery.status == status_filter)
        if driver_id:
            query = query.where(Delivery.driver_id == driver_id)

        count_q = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_q)).scalar_one()

        offset = (page - 1) * page_size
        result = await self.db.execute(
            query.order_by(Delivery.created_at.desc()).offset(offset).limit(page_size)
        )
        return list(result.scalars().all()), total

    async def assign_driver(
        self, tenant_id: UUID, delivery_id: UUID, driver_id: UUID, vehicle_id: UUID
    ) -> Delivery:
        """Atribui motorista e veículo. PENDING → IN_TRANSIT."""
        delivery = await self.get_by_id(tenant_id, delivery_id)
        if delivery.status not in (DeliveryStatus.PENDING, DeliveryStatus.ACCEPTED):
            raise ValueError("Entrega não pode ser atribuída neste status.")

        # Valida driver e vehicle pertencem ao tenant
        driver = await self.db.execute(
            select(User).where(
                User.id == driver_id,
                User.tenant_id == tenant_id,
                User.role == UserRole.DRIVER,
                User.is_active.is_(True),
            )
        )
        if not driver.scalar_one_or_none():
            raise ValueError("Motorista não encontrado ou inativo.")

        vehicle = await self.db.execute(
            select(Vehicle).where(
                Vehicle.id == vehicle_id,
                Vehicle.tenant_id == tenant_id,
                Vehicle.is_active.is_(True),
            )
        )
        if not vehicle.scalar_one_or_none():
            raise ValueError("Veículo não encontrado ou inativo.")

        delivery.driver_id = driver_id
        delivery.status = DeliveryStatus.IN_TRANSIT
        delivery.accepted_at = datetime.now(UTC)
        delivery.picked_up_at = datetime.now(UTC)
        await self.db.flush()
        return delivery

    async def cancel(self, tenant_id: UUID, delivery_id: UUID, reason: str) -> Delivery:
        delivery = await self.get_by_id(tenant_id, delivery_id)
        if delivery.status == DeliveryStatus.DELIVERED:
            raise ValueError("Entrega já concluída não pode ser cancelada.")
        delivery.status = DeliveryStatus.CANCELLED
        delivery.failure_reason = reason
        await self.db.flush()
        return delivery

    # ---------------------------------------------------------------------------
    # Fluxo de conclusão de entrega
    # ---------------------------------------------------------------------------

    async def initiate_completion(
        self, tenant_id: UUID, delivery_id: UUID, driver_id: UUID
    ) -> dict:
        """DRIVER escaneia QR — gera OTP TOTP e envia ao destinatário por email."""
        from app.services.otp_service import OTPService
        from app.services.email_service import EmailService

        delivery = await self.get_by_id(tenant_id, delivery_id)
        if delivery.status != DeliveryStatus.IN_TRANSIT:
            raise ValueError("Entrega não está em trânsito.")
        if str(delivery.driver_id) != str(driver_id):
            raise ValueError("Motorista não autorizado para esta entrega.")
        if not delivery.recipient_email:
            raise ValueError("Destinatário sem email cadastrado.")

        otp_svc = OTPService()
        otp_code = otp_svc.generate_totp(delivery.otp_secret)

        # Armazena OTP no Redis com TTL
        redis = await get_redis_client()
        redis_key = f"otp:delivery:{delivery_id}"
        await redis.setex(redis_key, self.OTP_TTL_SECONDS, otp_code)

        # Envia email ao destinatário
        email_svc = EmailService()
        email_svc.send_otp_email(
            to_email=delivery.recipient_email,
            full_name=delivery.recipient_name or "Cliente",
            otp_code=otp_code,
            delivery_code=delivery.tracking_code,
        )

        return {"message": "OTP enviado ao destinatário.", "expires_in": self.OTP_TTL_SECONDS}

    async def confirm_delivery(
        self,
        tenant_id: UUID,
        delivery_id: UUID,
        otp: str,
        gps_lat: float,
        gps_lng: float,
    ) -> Delivery:
        """Valida OTP + GPS e marca entrega como DELIVERED."""
        delivery = await self.get_by_id(tenant_id, delivery_id)
        if delivery.status != DeliveryStatus.IN_TRANSIT:
            raise ValueError("Entrega não está em trânsito.")

        # Valida OTP no Redis
        redis = await get_redis_client()
        redis_key = f"otp:delivery:{delivery_id}"
        stored_otp = await redis.get(redis_key)
        if not stored_otp or stored_otp != otp:
            raise ValueError("OTP inválido ou expirado.")

        # Valida GPS se coordenadas de destino disponíveis
        if delivery.destination_lat and delivery.destination_lng:
            dist = _haversine_meters(
                float(delivery.destination_lat),
                float(delivery.destination_lng),
                gps_lat,
                gps_lng,
            )
            if dist > self.MAX_GPS_RADIUS_METERS:
                raise ValueError(
                    f"GPS_TOO_FAR: motorista está a {dist:.0f}m do destino "
                    f"(máximo permitido: {self.MAX_GPS_RADIUS_METERS:.0f}m)."
                )

        await redis.delete(redis_key)
        delivery.status = DeliveryStatus.DELIVERED
        delivery.delivered_at = datetime.now(UTC)
        await self.db.flush()
        return delivery

    async def authorize_operator(
        self,
        tenant_id: UUID,
        delivery_id: UUID,
        operator_id: UUID,
        client_otp: str,
        reason: str,
        request_ip: str | None = None,
    ) -> Delivery:
        """Operador autoriza entrega usando o OTP que o cliente apresentou."""
        delivery = await self.get_by_id(tenant_id, delivery_id)
        if delivery.status != DeliveryStatus.IN_TRANSIT:
            raise ValueError("Entrega não está em trânsito.")

        redis = await get_redis_client()
        redis_key = f"otp:delivery:{delivery_id}"
        stored_otp = await redis.get(redis_key)
        if not stored_otp or stored_otp != client_otp:
            raise ValueError("OTP do cliente inválido ou expirado.")

        await redis.delete(redis_key)
        delivery.status = DeliveryStatus.DELIVERED
        delivery.delivered_at = datetime.now(UTC)
        delivery.manually_authorized = True
        delivery.manually_authorized_by = operator_id

        log = DeliveryAuthorizationLog(
            delivery_id=delivery.id,
            authorized_by_user_id=operator_id,
            method=AuthorizationMethod.OPERATOR_OTP,
            reason=reason,
            request_ip=request_ip,
        )
        self.db.add(log)
        await self.db.flush()
        return delivery

    async def authorize_admin(
        self,
        tenant_id: UUID,
        delivery_id: UUID,
        admin_id: UUID,
        admin_password: str,
        reason: str,
        request_ip: str | None = None,
    ) -> Delivery:
        """Admin autoriza entrega usando a própria senha do sistema."""
        from app.core.security import verify_password

        delivery = await self.get_by_id(tenant_id, delivery_id)
        if delivery.status != DeliveryStatus.IN_TRANSIT:
            raise ValueError("Entrega não está em trânsito.")

        admin = await self.db.execute(
            select(User).where(
                User.id == admin_id,
                User.tenant_id == tenant_id,
                User.role == UserRole.ADMIN,
                User.is_active.is_(True),
            )
        )
        admin_user = admin.scalar_one_or_none()
        if not admin_user:
            raise ValueError("Administrador não encontrado.")
        if not verify_password(admin_password, admin_user.hashed_password):
            raise ValueError("Senha de administrador incorreta.")

        delivery.status = DeliveryStatus.DELIVERED
        delivery.delivered_at = datetime.now(UTC)
        delivery.manually_authorized = True
        delivery.manually_authorized_by = admin_id

        log = DeliveryAuthorizationLog(
            delivery_id=delivery.id,
            authorized_by_user_id=admin_id,
            method=AuthorizationMethod.ADMIN_PASSWORD,
            reason=reason,
            request_ip=request_ip,
        )
        self.db.add(log)
        await self.db.flush()
        return delivery
