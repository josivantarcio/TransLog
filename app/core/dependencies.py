from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis

from app.core.redis import get_redis_client
from app.core.security import decode_token

bearer_scheme = HTTPBearer()


class CurrentUser:
    """Representa o usuário autenticado extraído do JWT (sem roundtrip ao banco)."""

    def __init__(self, user_id: UUID, tenant_id: UUID, role: str) -> None:
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.role = role


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> CurrentUser:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise credentials_exception
        user_id = UUID(payload["sub"])
        tenant_id = UUID(payload["tenant_id"])
        role: str = payload["role"]
    except (jwt.PyJWTError, KeyError, ValueError):
        raise credentials_exception

    return CurrentUser(user_id=user_id, tenant_id=tenant_id, role=role)


def require_role(*roles: str):
    """Factory que retorna um Depends verificando se o usuário tem o role necessário."""

    async def _check_role(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissão insuficiente",
            )
        return current_user

    return Depends(_check_role)


async def get_redis() -> Redis:
    return await get_redis_client()


# Tipos anotados para injeção limpa nos routers
CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
RedisDep = Annotated[Redis, Depends(get_redis)]
