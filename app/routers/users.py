from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUserDep, require_role
from app.schemas.user import (
    EmailResendRequest,
    UserCreate,
    UserPasswordUpdate,
    UserResponse,
    UserUpdate,
)
from app.services.email_service import EmailVerificationService

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    _=require_role("admin"),
    db: AsyncSession = Depends(get_db),
):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.get("/", response_model=list[UserResponse])
async def list_users(
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.get("/verify-email", status_code=status.HTTP_200_OK)
async def verify_email(
    token: str = Query(..., description="Token de verificação recebido por email"),
    db: AsyncSession = Depends(get_db),
):
    """Confirma o email do cliente (recebedor) a partir do token enviado por email.

    Após confirmação, o cliente está habilitado a receber a senha OTP de desbloqueio
    das entregas diretamente no seu email.
    """
    svc = EmailVerificationService(db)
    try:
        user = await svc.verify_token(token)
        await db.commit()
        return {
            "message": "Email confirmado com sucesso!",
            "user_id": str(user.id),
            "email": user.email,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/resend-verification", status_code=status.HTTP_200_OK)
async def resend_verification_email(
    payload: EmailResendRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reenvia o email de verificação para o endereço informado."""
    from sqlalchemy import select
    from app.models.user import User

    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    # Resposta genérica para não revelar se o email existe
    if not user or user.is_verified:
        return {"message": "Se o email estiver cadastrado e não verificado, você receberá um novo link."}

    svc = EmailVerificationService(db)
    try:
        await svc.resend(user.id)
        await db.commit()
    except ValueError:
        pass

    return {"message": "Se o email estiver cadastrado e não verificado, você receberá um novo link."}


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.post("/{user_id}/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    user_id: UUID,
    payload: UserPasswordUpdate,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)
