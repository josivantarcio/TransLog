"""Configuração global dos testes.

Stack de testes (equivalências Java → Python):
- JUnit       → pytest
- Mockito     → pytest-mock (mocker fixture) + unittest.mock
- JaCoCo      → pytest-cov (--cov=app --cov-report=html)
- AssertJ     → asserções nativas do pytest

Banco: SQLite in-memory via aiosqlite.
Redis: FakeRedis in-memory (fakeredis[aioredis]).
Os tipos UUID do PostgreSQL são mapeados para String no SQLite via TypeDecorator.
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import String, TypeDecorator

import app.models  # noqa: F401 — garante que todos os modelos são importados
from app.core.database import get_db
from app.main import app
from app.models.base import Base

# ---------------------------------------------------------------------------
# Adaptador: mapeia UUID(as_uuid=True) do PostgreSQL → String(36) no SQLite
# ---------------------------------------------------------------------------

class UUIDStr(TypeDecorator):
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        return str(value) if value is not None else None

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        return value


def _patch_uuid_for_sqlite(target_metadata):
    for table in target_metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, PG_UUID):
                col.type = UUIDStr()


_patch_uuid_for_sqlite(Base.metadata)

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Mock Redis — substitui get_redis_client() nos testes
# Simula um dict em memória com suporte a setex/exists/get/set
# ---------------------------------------------------------------------------

class FakeRedis:
    """Redis fake simples para testes — evita dependência de servidor Redis."""

    def __init__(self):
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = value  # sem TTL real nos testes

    async def exists(self, key: str) -> int:
        return 1 if key in self._store else 0

    async def delete(self, *keys: str) -> int:
        count = 0
        for k in keys:
            if k in self._store:
                del self._store[k]
                count += 1
        return count

    async def publish(self, channel: str, message: str) -> None:
        pass  # pub/sub não testado aqui

    async def aclose(self) -> None:
        pass

    def clear(self):
        self._store.clear()


# ---------------------------------------------------------------------------
# Fixtures de sessão
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(eng.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield eng

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


# ---------------------------------------------------------------------------
# Fixtures de função (recriadas a cada teste)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    TestSession = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with TestSession() as session:
        yield session
        await session.rollback()


@pytest.fixture
def fake_redis() -> FakeRedis:
    r = FakeRedis()
    yield r
    r.clear()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, fake_redis: FakeRedis) -> AsyncGenerator[AsyncClient, None]:
    """Cliente HTTP com overrides de DB e Redis."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_get_redis() -> FakeRedis:
        return fake_redis

    # Patch get_redis_client usado diretamente pelos serviços
    import app.core.redis as redis_module
    import app.services.auth_service as auth_svc_module

    original_get_redis = redis_module.get_redis_client

    async def fake_get_redis_client():
        return fake_redis

    redis_module.get_redis_client = fake_get_redis_client
    auth_svc_module.get_redis_client = fake_get_redis_client

    app.dependency_overrides[get_db] = override_get_db

    from app.core.dependencies import get_redis
    app.dependency_overrides[get_redis] = override_get_redis

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
    redis_module.get_redis_client = original_get_redis
    auth_svc_module.get_redis_client = original_get_redis
