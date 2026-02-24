from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUserDep, RedisDep, require_role
from app.schemas.delivery_tracking import TrackingEventCreate, TrackingEventResponse
from app.services.tracking_service import TrackingService

router = APIRouter(prefix="/tracking", tags=["tracking"])


@router.post(
    "/",
    response_model=TrackingEventResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_role("driver")],
    summary="Registrar evento GPS (motorista)",
)
async def record_tracking_event(
    payload: TrackingEventCreate,
    current_user: CurrentUserDep,
    redis: RedisDep,
    db: AsyncSession = Depends(get_db),
):
    """Motorista envia posição GPS → salvo no Postgres + Redis + pub/sub."""
    svc = TrackingService(db=db, redis=redis)
    try:
        event = await svc.record_event(
            tenant_id=current_user.tenant_id,
            driver_id=current_user.user_id,
            payload=payload,
        )
        await db.commit()
        return event
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/{delivery_id}/live",
    dependencies=[require_role("admin", "driver")],
    summary="Posição ao vivo (Redis)",
)
async def get_live_tracking(
    delivery_id: UUID,
    current_user: CurrentUserDep,
    redis: RedisDep,
    db: AsyncSession = Depends(get_db),
):
    """Retorna a última posição conhecida do motorista via Redis."""
    svc = TrackingService(db=db, redis=redis)
    try:
        data = await svc.get_live_position(
            tenant_id=current_user.tenant_id,
            delivery_id=delivery_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    if data is None:
        return {"message": "Sem dados de rastreamento disponíveis."}
    return data


@router.get(
    "/{delivery_id}",
    response_model=list[TrackingEventResponse],
    dependencies=[require_role("admin", "driver")],
    summary="Histórico de rastreamento (Postgres)",
)
async def get_tracking_history(
    delivery_id: UUID,
    current_user: CurrentUserDep,
    redis: RedisDep,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(200, ge=1, le=500),
):
    """Retorna até `limit` eventos GPS históricos, mais recentes primeiro."""
    svc = TrackingService(db=db, redis=redis)
    try:
        events = await svc.get_history(
            tenant_id=current_user.tenant_id,
            delivery_id=delivery_id,
            limit=limit,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return events
