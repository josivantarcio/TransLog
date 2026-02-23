"""Configuração global dos testes.

Stack de testes (equivalências Java → Python):
- JUnit       → pytest
- Mockito     → pytest-mock (mocker fixture) + unittest.mock
- JaCoCo      → pytest-cov (--cov=app --cov-report=html)
- AssertJ     → asserções nativas do pytest

Banco: SQLite in-memory via aiosqlite.
Os tipos UUID do PostgreSQL são mapeados para String no SQLite via evento.
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import String, TypeDecorator

import app.models  # noqa: F401 — garante que todos os modelos são importados
from app.core.database import get_db
from app.main import app
from app.models.base import Base

# ---------------------------------------------------------------------------
# Adaptador: mapeia UUID(as_uuid=True) do PostgreSQL para String no SQLite
# ---------------------------------------------------------------------------

class UUIDStr(TypeDecorator):
    """Armazena UUID como string no SQLite."""
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        return str(value) if value is not None else None

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        return value


def _patch_uuid_for_sqlite(target_metadata):
    """Substitui UUID(as_uuid=True) por String(36) nas colunas para testes SQLite."""
    for table in target_metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, PG_UUID):
                col.type = UUIDStr()


_patch_uuid_for_sqlite(Base.metadata)

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Fixtures de sessão (criadas uma vez por test session)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop():
    """Loop de eventos compartilhado — necessário para fixtures session-scoped async."""
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

    # Habilita FK no SQLite
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
    """Sessão de banco isolada: rollback automático ao final de cada teste."""
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


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Cliente HTTP assíncrono com override da dependência de banco."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
