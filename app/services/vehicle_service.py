"""Serviço de gestão de Veículos dentro de um Tenant."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vehicle import Vehicle
from app.schemas.vehicle import VehicleCreate, VehicleUpdate


class VehicleService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, tenant_id: UUID, payload: VehicleCreate) -> Vehicle:
        """Cria veículo. Placa deve ser única no tenant.

        Raises:
            ValueError: placa já cadastrada neste tenant.
        """
        existing = await self.db.execute(
            select(Vehicle).where(
                Vehicle.plate == payload.plate.upper(),
                Vehicle.tenant_id == tenant_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Placa '{payload.plate}' já cadastrada neste tenant.")

        vehicle = Vehicle(
            tenant_id=tenant_id,
            plate=payload.plate.upper(),
            model=payload.model,
            brand=payload.brand,
            year=payload.year,
            color=payload.color,
            vehicle_type=payload.vehicle_type,
            driver_id=payload.driver_id,
            is_active=True,
        )
        self.db.add(vehicle)
        await self.db.flush()
        return vehicle

    async def get_by_id(self, tenant_id: UUID, vehicle_id: UUID) -> Vehicle:
        result = await self.db.execute(
            select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.tenant_id == tenant_id)
        )
        vehicle = result.scalar_one_or_none()
        if not vehicle:
            raise ValueError("Veículo não encontrado.")
        return vehicle

    async def list(
        self,
        tenant_id: UUID,
        only_active: bool = True,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Vehicle], int]:
        query = select(Vehicle).where(Vehicle.tenant_id == tenant_id)
        if only_active:
            query = query.where(Vehicle.is_active.is_(True))

        count_q = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_q)
        total = count_result.scalar_one()

        offset = (page - 1) * page_size
        result = await self.db.execute(
            query.order_by(Vehicle.created_at.desc()).offset(offset).limit(page_size)
        )
        return list(result.scalars().all()), total

    async def update(self, tenant_id: UUID, vehicle_id: UUID, payload: VehicleUpdate) -> Vehicle:
        vehicle = await self.get_by_id(tenant_id, vehicle_id)
        data = payload.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(vehicle, field, value)
        await self.db.flush()
        return vehicle

    async def deactivate(self, tenant_id: UUID, vehicle_id: UUID) -> Vehicle:
        vehicle = await self.get_by_id(tenant_id, vehicle_id)
        vehicle.is_active = False
        await self.db.flush()
        return vehicle
