from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.delivery import DeliveryStatus


class DeliveryBase(BaseModel):
    origin_address: str
    origin_lat: float | None = None
    origin_lng: float | None = None
    destination_address: str
    destination_lat: float | None = None
    destination_lng: float | None = None
    description: str | None = None
    weight_kg: float | None = None
    value: float | None = None
    estimated_delivery_at: datetime | None = None
    delivery_notes: str | None = None


class DeliveryCreate(DeliveryBase):
    recipient_name: str = Field(..., min_length=2, max_length=255)
    recipient_email: EmailStr
    recipient_phone: str | None = None
    client_id: UUID | None = None


class DeliveryUpdate(BaseModel):
    delivery_notes: str | None = None
    estimated_delivery_at: datetime | None = None


class AssignDriverRequest(BaseModel):
    driver_id: UUID
    vehicle_id: UUID


class CancelRequest(BaseModel):
    reason: str = Field(..., min_length=3)


class DeliveryConfirm(BaseModel):
    otp: str = Field(..., min_length=6, max_length=6)
    gps_lat: float
    gps_lng: float


class OperatorAuthRequest(BaseModel):
    client_otp: str = Field(..., min_length=6, max_length=6)
    reason: str = Field(..., min_length=3)


class AdminAuthRequest(BaseModel):
    password: str
    reason: str = Field(..., min_length=3)


class DeliveryResponse(DeliveryBase):
    model_config = {"from_attributes": True}

    id: UUID
    tenant_id: UUID
    tracking_code: str
    status: DeliveryStatus
    driver_id: UUID | None = None
    client_id: UUID | None = None
    recipient_name: str | None = None
    recipient_email: str | None = None
    recipient_phone: str | None = None
    accepted_at: datetime | None = None
    picked_up_at: datetime | None = None
    delivered_at: datetime | None = None
    manually_authorized: bool = False
    failure_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class PaginatedDeliveries(BaseModel):
    items: list[DeliveryResponse]
    total: int
    page: int
    page_size: int


class DeliveryQRCodeResponse(BaseModel):
    delivery_id: UUID
    qr_code_image: str  # base64
    qr_code_data: str   # payload do QR


class CompletionInitiateResponse(BaseModel):
    message: str
    expires_in: int


# Mantido para compatibilidade retroativa com testes existentes
class DeliveryOTPRequest(BaseModel):
    delivery_id: UUID


class DeliveryOTPVerify(BaseModel):
    delivery_id: UUID
    otp_code: str = Field(..., min_length=6, max_length=6)
