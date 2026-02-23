from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

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
    client_id: UUID | None = None


class DeliveryUpdate(BaseModel):
    status: DeliveryStatus | None = None
    driver_id: UUID | None = None
    delivery_notes: str | None = None
    failure_reason: str | None = None


class DeliveryResponse(DeliveryBase):
    model_config = {"from_attributes": True}

    id: UUID
    tenant_id: UUID
    tracking_code: str
    status: DeliveryStatus
    driver_id: UUID | None = None
    client_id: UUID | None = None
    accepted_at: datetime | None = None
    picked_up_at: datetime | None = None
    delivered_at: datetime | None = None
    failure_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class DeliveryQRCodeResponse(BaseModel):
    delivery_id: UUID
    qr_code_image: str  # base64
    expires_at: datetime


class DeliveryOTPRequest(BaseModel):
    delivery_id: UUID


class DeliveryOTPVerify(BaseModel):
    delivery_id: UUID
    otp_code: str = Field(..., min_length=6, max_length=6)
