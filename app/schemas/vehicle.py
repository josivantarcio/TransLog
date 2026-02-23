from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.vehicle import VehicleType


class VehicleBase(BaseModel):
    plate: str = Field(..., min_length=4, max_length=20)
    model: str = Field(..., min_length=1, max_length=100)
    brand: str = Field(..., min_length=1, max_length=100)
    year: int | None = Field(None, ge=1990, le=2100)
    color: str | None = Field(None, max_length=50)
    vehicle_type: VehicleType = VehicleType.MOTORCYCLE


class VehicleCreate(VehicleBase):
    driver_id: UUID | None = None


class VehicleUpdate(BaseModel):
    model: str | None = Field(None, min_length=1, max_length=100)
    brand: str | None = Field(None, min_length=1, max_length=100)
    year: int | None = Field(None, ge=1990, le=2100)
    color: str | None = Field(None, max_length=50)
    vehicle_type: VehicleType | None = None
    driver_id: UUID | None = None
    is_active: bool | None = None


class VehicleResponse(VehicleBase):
    model_config = {"from_attributes": True}

    id: UUID
    tenant_id: UUID
    driver_id: UUID | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
