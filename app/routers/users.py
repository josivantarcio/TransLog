from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUserDep, require_role
from app.models.user import UserRole
from app.schemas.user import (
    EmailResendRequest,
    PaginatedUsers,
    UserCreate,
    UserPasswordUpdate,
    UserResetPassword,
    UserResponse,
    UserUpdate,
)
from app.services.email_service import EmailVerificationService
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_role("admin")],
    summary="Criar usuário no tenant (admin)",
)
async def create_user(
    payload: UserCreate,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    """Cria um novo usuário dentro do tenant do admin autenticado."""
    svc = UserService(db)
    try:
        user = await svc.create(current_user.tenant_id, payload)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return user


@router.get(
    "/",
    response_model=PaginatedUsers,
    dependencies=[require_role("admin")],
    summary="Listar usuários do tenant (admin)",
)
async def list_users(
    current_user: CurrentUserDep,
    role: UserRole | None = Query(None, description="Filtrar por role"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    svc = UserService(db)
    users, total = await svc.list(
        tenant_id=current_user.tenant_id,
        role=role,
        page=page,
        page_size=page_size,
    )
    return PaginatedUsers(items=users, total=total, page=page, page_size=page_size)


@router.get(
    "/verify-email",
    status_code=status.HTTP_200_OK,
    summary="Verificar email por token (público)",
)
async def verify_email(
    token: str = Query(..., description="Token de verificação recebido por email"),
    db: AsyncSession = Depends(get_db),
):
    """Confirma o email do cliente a partir do token enviado por email."""
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


@router.post(
    "/resend-verification",
    status_code=status.HTTP_200_OK,
    summary="Reenviar email de verificação (público)",
)
async def resend_verification_email(
    payload: EmailResendRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reenvia o email de verificação. Resposta genérica para não revelar cadastros."""
    from sqlalchemy import select
    from app.models.user import User

    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    _generic = {"message": "Se o email estiver cadastrado e não verificado, você receberá um novo link."}

    if not user or user.is_verified:
        return _generic

    svc = EmailVerificationService(db)
    try:
        await svc.resend(user.id)
        await db.commit()
    except ValueError:
        pass

    return _generic


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Dados do usuário autenticado",
)
async def get_me(
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    svc = UserService(db)
    try:
        return await svc.get_by_id(current_user.tenant_id, current_user.user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Detalhe de usuário (admin ou próprio usuário)",
)
async def get_user(
    user_id: UUID,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "admin" and current_user.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissão insuficiente.")

    svc = UserService(db)
    try:
        return await svc.get_by_id(current_user.tenant_id, user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Atualizar usuário (admin ou próprio usuário)",
)
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "admin" and current_user.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissão insuficiente.")

    svc = UserService(db)
    try:
        user = await svc.update(current_user.tenant_id, user_id, payload)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[require_role("admin")],
    summary="Desativar usuário (admin)",
)
async def deactivate_user(
    user_id: UUID,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    svc = UserService(db)
    try:
        await svc.deactivate(current_user.tenant_id, user_id, current_user.user_id)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{user_id}/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Trocar própria senha",
)
async def change_password(
    user_id: UUID,
    payload: UserPasswordUpdate,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    if current_user.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissão insuficiente.")

    svc = UserService(db)
    try:
        await svc.change_password(
            current_user.tenant_id, user_id, payload.current_password, payload.new_password
        )
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{user_id}/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[require_role("admin")],
    summary="Redefinir senha de usuário (admin)",
)
async def reset_password(
    user_id: UUID,
    payload: UserResetPassword,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    svc = UserService(db)
    try:
        await svc.reset_password(current_user.tenant_id, user_id, payload.new_password)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
