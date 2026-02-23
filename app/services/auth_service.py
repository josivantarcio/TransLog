from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
)
from app.schemas.auth import LoginRequest, TokenResponse


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def login(self, payload: LoginRequest) -> TokenResponse:
        # TODO: buscar usuário por email+tenant, verificar senha, gerar tokens
        raise NotImplementedError

    async def refresh(self, refresh_token: str) -> TokenResponse:
        # TODO: validar refresh token, verificar blacklist no Redis, gerar novo access token
        raise NotImplementedError

    async def logout(self, user_id: str, refresh_token: str) -> None:
        # TODO: adicionar refresh token à blacklist no Redis
        raise NotImplementedError
