from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TrackingEventCreate(BaseModel):
    delivery_id: UUID
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy: float | None = Field(None, ge=0)
    speed: float | None = Field(None, ge=0)
    heading: float | None = Field(None, ge=0, le=360)
    altitude: float | None = None
    event_description: str | None = None
    recorded_at: datetime | None = None


class TrackingEventResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    delivery_id: UUID
    driver_id: UUID | None = None
    latitude: float
    longitude: float
    accuracy: float | None = None
    speed: float | None = None
    heading: float | None = None
    altitude: float | None = None
    status_snapshot: str | None = None
    event_description: str | None = None
    recorded_at: datetime


class LiveTrackingData(BaseModel):
    """Dados ao vivo do Redis para o WebSocket."""

    delivery_id: str
    latitude: float
    longitude: float
    accuracy: float | None = None
    speed: float | None = None
    heading: float | None = None
    timestamp: datetime
    status: str
