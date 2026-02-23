from fastapi import APIRouter, HTTPException, Request, status

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/asaas", status_code=status.HTTP_200_OK)
async def asaas_webhook(request: Request):
    """Recebe webhooks do gateway Asaas (pagamentos)."""
    # TODO: validar assinatura HMAC do Asaas antes de processar
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)
