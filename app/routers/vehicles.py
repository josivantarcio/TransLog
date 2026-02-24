from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUserDep, require_role
from app.schemas.vehicle import PaginatedVehicles, VehicleCreate, VehicleResponse, VehicleUpdate
from app.services.vehicle_service import VehicleService

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.post(
    "/",
    response_model=VehicleResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_role("admin")],
    summary="Cadastrar veículo (admin)",
)
async def create_vehicle(
    payload: VehicleCreate,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    svc = VehicleService(db)
    try:
        vehicle = await svc.create(current_user.tenant_id, payload)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return vehicle


@router.get(
    "/",
    response_model=PaginatedVehicles,
    dependencies=[require_role("admin", "driver")],
    summary="Listar veículos do tenant",
)
async def list_vehicles(
    current_user: CurrentUserDep,
    only_active: bool = Query(True, description="Retornar apenas veículos ativos"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    svc = VehicleService(db)
    vehicles, total = await svc.list(
        tenant_id=current_user.tenant_id,
        only_active=only_active,
        page=page,
        page_size=page_size,
    )
    return PaginatedVehicles(items=vehicles, total=total, page=page, page_size=page_size)


@router.get(
    "/{vehicle_id}",
    response_model=VehicleResponse,
    dependencies=[require_role("admin", "driver")],
    summary="Detalhe de veículo",
)
async def get_vehicle(
    vehicle_id: UUID,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    svc = VehicleService(db)
    try:
        return await svc.get_by_id(current_user.tenant_id, vehicle_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch(
    "/{vehicle_id}",
    response_model=VehicleResponse,
    dependencies=[require_role("admin")],
    summary="Atualizar veículo (admin)",
)
async def update_vehicle(
    vehicle_id: UUID,
    payload: VehicleUpdate,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    svc = VehicleService(db)
    try:
        vehicle = await svc.update(current_user.tenant_id, vehicle_id, payload)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return vehicle


@router.delete(
    "/{vehicle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[require_role("admin")],
    summary="Desativar veículo (admin)",
)
async def deactivate_vehicle(
    vehicle_id: UUID,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    svc = VehicleService(db)
    try:
        await svc.deactivate(current_user.tenant_id, vehicle_id)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
