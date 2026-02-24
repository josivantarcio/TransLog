"""Serviço de autenticação — login, refresh, logout.

Estratégia multi-tenant:
- O login recebe email + password + tenant_slug
- Busca o tenant pelo slug, depois o user pelo email dentro do tenant
- O access token carrega tenant_id + role → sem DB roundtrip nas requests seguintes
- Refresh token blacklist: Redis com key "blacklist:refresh:{token_hash}"
"""

import hashlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import get_redis_client
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.models.tenant import Tenant, TenantStatus
from app.models.user import User
from app.schemas.auth import LoginRequest, MeResponse, TokenResponse

import jwt


def _token_hash(token: str) -> str:
    """Hash SHA-256 do token para usar como chave no Redis (não armazena o token raw)."""
    return hashlib.sha256(token.encode()).hexdigest()


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def login(self, payload: LoginRequest) -> TokenResponse:
        """Autentica o usuário e retorna access + refresh tokens.

        Raises:
            ValueError: credenciais inválidas, tenant suspenso, usuário inativo.
        """
        # 1. Busca o tenant pelo slug
        result = await self.db.execute(
            select(Tenant).where(Tenant.slug == payload.tenant_slug)
        )
        tenant = result.scalar_one_or_none()
        if not tenant or not tenant.is_active:
            raise ValueError("Tenant não encontrado ou inativo.")

        if tenant.status == TenantStatus.SUSPENDED:
            raise ValueError(
                "Conta suspensa. Entre em contato com o suporte transLog."
            )
        if tenant.status == TenantStatus.CANCELLED:
            raise ValueError("Conta cancelada.")

        # 2. Busca o usuário pelo email dentro do tenant
        result = await self.db.execute(
            select(User).where(
                User.email == payload.email,
                User.tenant_id == tenant.id,
            )
        )
        user = result.scalar_one_or_none()

        # Mensagem genérica — não revela se o email existe
        invalid_creds = ValueError("Email ou senha inválidos.")

        if not user:
            raise invalid_creds
        if not user.is_active:
            raise ValueError("Usuário desativado. Contate o administrador.")
        if not verify_password(payload.password, user.hashed_password):
            raise invalid_creds

        # 3. Gera tokens
        access_token = create_access_token(
            user_id=user.id,
            tenant_id=tenant.id,
            role=user.role.value,
        )
        refresh_token = create_refresh_token(user_id=user.id)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def refresh(self, refresh_token: str) -> TokenResponse:
        """Gera novo access token a partir de um refresh token válido.

        Raises:
            ValueError: token inválido, expirado ou na blacklist.
        """
        # 1. Valida o JWT
        try:
            payload = decode_token(refresh_token)
        except jwt.ExpiredSignatureError:
            raise ValueError("Refresh token expirado. Faça login novamente.")
        except jwt.PyJWTError:
            raise ValueError("Refresh token inválido.")

        if payload.get("type") != "refresh":
            raise ValueError("Token inválido.")

        # 2. Verifica blacklist no Redis
        redis = await get_redis_client()
        blacklist_key = f"blacklist:refresh:{_token_hash(refresh_token)}"
        if await redis.exists(blacklist_key):
            raise ValueError("Token já invalidado. Faça login novamente.")

        # 3. Busca o usuário para pegar tenant_id e role atualizados
        from uuid import UUID
        user_id = UUID(payload["sub"])

        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise ValueError("Usuário não encontrado ou desativado.")

        # 4. Emite novo access token
        access_token = create_access_token(
            user_id=user.id,
            tenant_id=user.tenant_id,
            role=user.role.value,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,  # reutiliza o mesmo refresh token
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def logout(self, refresh_token: str) -> None:
        """Invalida o refresh token adicionando-o à blacklist no Redis.

        O TTL da blacklist é calculado para coincidir com a expiração do token,
        evitando acúmulo infinito no Redis.
        """
        try:
            payload = decode_token(refresh_token)
        except jwt.PyJWTError:
            # Token inválido ou já expirado — nada a invalidar
            return

        exp = payload.get("exp", 0)
        now = datetime.now(UTC).timestamp()
        ttl = max(int(exp - now), 1)  # mínimo 1 segundo

        redis = await get_redis_client()
        blacklist_key = f"blacklist:refresh:{_token_hash(refresh_token)}"
        await redis.setex(blacklist_key, ttl, "1")

    async def get_me(self, user_id: str, tenant_id: str) -> MeResponse:
        """Retorna dados completos do usuário autenticado (com DB roundtrip para dados frescos)."""
        from uuid import UUID

        result = await self.db.execute(
            select(User).where(
                User.id == UUID(user_id),
                User.tenant_id == UUID(tenant_id),
            )
        )
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("Usuário não encontrado.")

        return MeResponse(
            user_id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            full_name=user.full_name,
            role=user.role.value,
            is_verified=user.is_verified,
        )
