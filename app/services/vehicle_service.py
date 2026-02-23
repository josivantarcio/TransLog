from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vehicle import Vehicle
from app.schemas.vehicle import VehicleCreate, VehicleUpdate


class VehicleService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, tenant_id: UUID, payload: VehicleCreate) -> Vehicle:
        # TODO: verificar placa única globalmente, salvar veículo
        raise NotImplementedError

    async def get_by_id(self, vehicle_id: UUID, tenant_id: UUID) -> Vehicle:
        raise NotImplementedError

    async def list(self, tenant_id: UUID) -> list[Vehicle]:
        raise NotImplementedError

    async def update(self, vehicle_id: UUID, tenant_id: UUID, payload: VehicleUpdate) -> Vehicle:
        raise NotImplementedError

    async def delete(self, vehicle_id: UUID, tenant_id: UUID) -> None:
        raise NotImplementedError
