from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUserDep, RedisDep
from app.schemas.auth import LoginRequest, MeResponse, RefreshRequest, TokenResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Autentica o usuário e retorna access + refresh tokens.

    O campo `tenant_slug` identifica a empresa no sistema multi-tenant.
    """
    svc = AuthService(db)
    try:
        return await svc.login(payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """Renova o access token usando o refresh token.

    O refresh token continua válido até expirar ou até um logout explícito.
    """
    svc = AuthService(db)
    try:
        return await svc.refresh(payload.refresh_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: RefreshRequest,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    """Invalida o refresh token (blacklist no Redis).

    Requer o access token no header Authorization e o refresh_token no body.
    """
    svc = AuthService(db)
    await svc.logout(payload.refresh_token)


@router.get("/me", response_model=MeResponse)
async def me(
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    """Retorna dados completos do usuário autenticado (lê do banco para dados frescos)."""
    svc = AuthService(db)
    try:
        return await svc.get_me(
            user_id=str(current_user.user_id),
            tenant_id=str(current_user.tenant_id),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
