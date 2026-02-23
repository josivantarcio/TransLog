from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUserDep
from app.schemas.delivery import (
    DeliveryCreate,
    DeliveryOTPVerify,
    DeliveryQRCodeResponse,
    DeliveryResponse,
    DeliveryUpdate,
)

router = APIRouter(prefix="/deliveries", tags=["deliveries"])


@router.post("/", response_model=DeliveryResponse, status_code=status.HTTP_201_CREATED)
async def create_delivery(
    payload: DeliveryCreate,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.get("/", response_model=list[DeliveryResponse])
async def list_deliveries(
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.get("/{delivery_id}", response_model=DeliveryResponse)
async def get_delivery(
    delivery_id: UUID,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.patch("/{delivery_id}", response_model=DeliveryResponse)
async def update_delivery(
    delivery_id: UUID,
    payload: DeliveryUpdate,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.get("/{delivery_id}/qrcode", response_model=DeliveryQRCodeResponse)
async def get_delivery_qrcode(
    delivery_id: UUID,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    """Gera QR Code para confirmação da entrega."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.post("/{delivery_id}/verify-otp", status_code=status.HTTP_200_OK)
async def verify_delivery_otp(
    delivery_id: UUID,
    payload: DeliveryOTPVerify,
    db: AsyncSession = Depends(get_db),
):
    """Verifica OTP para confirmar entrega (sem autenticação — link público)."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)
