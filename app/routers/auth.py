from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUserDep
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Autentica o usuário e retorna access + refresh tokens."""
    # TODO: implementar em auth_service
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(payload: RefreshRequest):
    """Renova o access token usando o refresh token."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(current_user: CurrentUserDep):
    """Invalida o refresh token (blacklist no Redis)."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.get("/me")
async def me(current_user: CurrentUserDep):
    """Retorna informações do usuário autenticado."""
    return {
        "user_id": str(current_user.user_id),
        "tenant_id": str(current_user.tenant_id),
        "role": current_user.role,
    }
