from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUserDep, require_role
from app.models.delivery import DeliveryStatus
from app.schemas.delivery import (
    AdminAuthRequest,
    AssignDriverRequest,
    CancelRequest,
    CompletionInitiateResponse,
    DeliveryConfirm,
    DeliveryCreate,
    DeliveryQRCodeResponse,
    DeliveryResponse,
    DeliveryUpdate,
    OperatorAuthRequest,
    PaginatedDeliveries,
)
from app.services.delivery_service import DeliveryService
from app.services.qrcode_service import QRCodeService
from app.services.receipt_service import DeliveryReceiptService

router = APIRouter(prefix="/deliveries", tags=["deliveries"])


@router.post(
    "/",
    response_model=DeliveryResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_role("admin")],
    summary="Criar entrega (admin)",
)
async def create_delivery(
    payload: DeliveryCreate,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    svc = DeliveryService(db)
    delivery = await svc.create(current_user.tenant_id, payload)
    await db.commit()
    return delivery


@router.get(
    "/",
    response_model=PaginatedDeliveries,
    dependencies=[require_role("admin", "driver")],
    summary="Listar entregas",
)
async def list_deliveries(
    current_user: CurrentUserDep,
    delivery_status: DeliveryStatus | None = Query(None, alias="status"),
    driver_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    # DRIVER só vê as próprias entregas
    effective_driver_id = driver_id
    if current_user.role == "driver":
        effective_driver_id = current_user.user_id

    svc = DeliveryService(db)
    deliveries, total = await svc.list(
        tenant_id=current_user.tenant_id,
        status_filter=delivery_status,
        driver_id=effective_driver_id,
        page=page,
        page_size=page_size,
    )
    return PaginatedDeliveries(items=deliveries, total=total, page=page, page_size=page_size)


@router.get(
    "/{delivery_id}",
    response_model=DeliveryResponse,
    dependencies=[require_role("admin", "driver")],
    summary="Detalhe de entrega",
)
async def get_delivery(
    delivery_id: UUID,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    svc = DeliveryService(db)
    try:
        delivery = await svc.get_by_id(current_user.tenant_id, delivery_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    # DRIVER só acessa a própria entrega
    if current_user.role == "driver" and str(delivery.driver_id) != str(current_user.user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissão insuficiente.")

    return delivery


@router.patch(
    "/{delivery_id}",
    response_model=DeliveryResponse,
    dependencies=[require_role("admin")],
    summary="Atualizar notas/estimativa de entrega (admin)",
)
async def update_delivery(
    delivery_id: UUID,
    payload: DeliveryUpdate,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    svc = DeliveryService(db)
    try:
        delivery = await svc.get_by_id(current_user.tenant_id, delivery_id)
        data = payload.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(delivery, field, value)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return delivery


@router.post(
    "/{delivery_id}/assign",
    response_model=DeliveryResponse,
    dependencies=[require_role("admin")],
    summary="Atribuir motorista e veículo",
)
async def assign_driver(
    delivery_id: UUID,
    payload: AssignDriverRequest,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    svc = DeliveryService(db)
    try:
        delivery = await svc.assign_driver(
            current_user.tenant_id, delivery_id, payload.driver_id, payload.vehicle_id
        )
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return delivery


@router.post(
    "/{delivery_id}/cancel",
    response_model=DeliveryResponse,
    dependencies=[require_role("admin")],
    summary="Cancelar entrega (admin)",
)
async def cancel_delivery(
    delivery_id: UUID,
    payload: CancelRequest,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    svc = DeliveryService(db)
    try:
        delivery = await svc.cancel(current_user.tenant_id, delivery_id, payload.reason)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return delivery


@router.get(
    "/{delivery_id}/qrcode",
    response_model=DeliveryQRCodeResponse,
    dependencies=[require_role("admin", "driver")],
    summary="QR Code da entrega",
)
async def get_delivery_qrcode(
    delivery_id: UUID,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    svc = DeliveryService(db)
    try:
        delivery = await svc.get_by_id(current_user.tenant_id, delivery_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    qr_svc = QRCodeService()
    qr_image, _ = qr_svc.generate_delivery_qr(
        delivery_id=delivery.id,
        tenant_id=delivery.tenant_id,
        otp_secret=delivery.otp_secret or "",
    )
    return DeliveryQRCodeResponse(
        delivery_id=delivery.id,
        qr_code_image=qr_image,
        qr_code_data=delivery.qr_code_data or "",
    )


# ---------------------------------------------------------------------------
# Fluxo de conclusão de entrega
# ---------------------------------------------------------------------------

@router.post(
    "/{delivery_id}/initiate-completion",
    response_model=CompletionInitiateResponse,
    dependencies=[require_role("driver")],
    summary="Iniciar conclusão: DRIVER escaneia QR, OTP é enviado ao destinatário",
)
async def initiate_completion(
    delivery_id: UUID,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    svc = DeliveryService(db)
    try:
        result = await svc.initiate_completion(
            current_user.tenant_id, delivery_id, current_user.user_id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{delivery_id}/confirm",
    response_model=DeliveryResponse,
    dependencies=[require_role("driver")],
    summary="Confirmar entrega: DRIVER valida OTP + GPS",
)
async def confirm_delivery(
    delivery_id: UUID,
    payload: DeliveryConfirm,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    svc = DeliveryService(db)
    try:
        delivery = await svc.confirm_delivery(
            current_user.tenant_id,
            delivery_id,
            payload.otp,
            payload.gps_lat,
            payload.gps_lng,
        )
        await db.commit()
    except ValueError as e:
        detail = str(e)
        code = status.HTTP_400_BAD_REQUEST
        if "GPS_TOO_FAR" in detail:
            code = status.HTTP_422_UNPROCESSABLE_ENTITY
        elif "OTP" in detail.upper():
            code = status.HTTP_401_UNAUTHORIZED
        raise HTTPException(status_code=code, detail=detail)
    return delivery


@router.post(
    "/{delivery_id}/authorize-operator",
    response_model=DeliveryResponse,
    dependencies=[require_role("admin", "driver")],
    summary="Autorização manual — Operador usa OTP do cliente",
)
async def authorize_operator(
    delivery_id: UUID,
    payload: OperatorAuthRequest,
    current_user: CurrentUserDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    svc = DeliveryService(db)
    try:
        delivery = await svc.authorize_operator(
            current_user.tenant_id,
            delivery_id,
            current_user.user_id,
            payload.client_otp,
            payload.reason,
            request_ip=request.client.host if request.client else None,
        )
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return delivery


@router.post(
    "/{delivery_id}/authorize-admin",
    response_model=DeliveryResponse,
    dependencies=[require_role("admin")],
    summary="Autorização manual — Admin usa a própria senha",
)
async def authorize_admin(
    delivery_id: UUID,
    payload: AdminAuthRequest,
    current_user: CurrentUserDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    svc = DeliveryService(db)
    try:
        delivery = await svc.authorize_admin(
            current_user.tenant_id,
            delivery_id,
            current_user.user_id,
            payload.password,
            payload.reason,
            request_ip=request.client.host if request.client else None,
        )
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return delivery


# ---------------------------------------------------------------------------
# Comprovante de Entrega em PDF
# ---------------------------------------------------------------------------

@router.get(
    "/{delivery_id}/receipt",
    dependencies=[require_role("admin", "driver")],
    summary="Comprovante de entrega em PDF",
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "PDF do comprovante de entrega",
        }
    },
)
async def get_delivery_receipt(
    delivery_id: UUID,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    """Gera e retorna o comprovante de entrega em PDF. Disponível apenas após DELIVERED."""
    svc = DeliveryReceiptService(db)
    try:
        delivery = await svc.get_delivered_delivery(current_user.tenant_id, delivery_id)
        pdf_bytes = svc.generate_pdf(delivery)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    filename = f"comprovante-{delivery.tracking_code}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
