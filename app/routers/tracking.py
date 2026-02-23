from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUserDep, RedisDep
from app.schemas.delivery_tracking import TrackingEventCreate, TrackingEventResponse

router = APIRouter(prefix="/tracking", tags=["tracking"])


@router.post("/", response_model=TrackingEventResponse, status_code=status.HTTP_201_CREATED)
async def record_tracking_event(
    payload: TrackingEventCreate,
    current_user: CurrentUserDep,
    redis: RedisDep,
    db: AsyncSession = Depends(get_db),
):
    """Registra evento de rastreamento (motorista envia GPS)."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.get("/{delivery_id}", response_model=list[TrackingEventResponse])
async def get_tracking_history(
    delivery_id: UUID,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    """Retorna histórico completo de rastreamento de uma entrega."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.get("/{delivery_id}/live")
async def get_live_tracking(
    delivery_id: UUID,
    redis: RedisDep,
):
    """Retorna posição ao vivo do motorista (via Redis)."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)
