from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUserDep, require_role
from app.schemas.vehicle import VehicleCreate, VehicleResponse, VehicleUpdate

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.post("/", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
async def create_vehicle(
    payload: VehicleCreate,
    _=require_role("admin"),
    db: AsyncSession = Depends(get_db),
):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.get("/", response_model=list[VehicleResponse])
async def list_vehicles(
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.get("/{vehicle_id}", response_model=VehicleResponse)
async def get_vehicle(
    vehicle_id: UUID,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.patch("/{vehicle_id}", response_model=VehicleResponse)
async def update_vehicle(
    vehicle_id: UUID,
    payload: VehicleUpdate,
    _=require_role("admin"),
    db: AsyncSession = Depends(get_db),
):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vehicle(
    vehicle_id: UUID,
    _=require_role("admin"),
    db: AsyncSession = Depends(get_db),
):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)
