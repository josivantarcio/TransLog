"""Testes de integração — endpoint de health."""

import pytest


@pytest.mark.asyncio
async def test_health_returns_ok(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "transLog"


@pytest.mark.asyncio
async def test_health_returns_env(client):
    response = await client.get("/health")
    assert "env" in response.json()
