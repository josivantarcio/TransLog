"""Testes de integração para routers de autenticação.

Endpoints ainda são stubs (501), então testamos o comportamento esperado
dos contratos da API e o que já está implementado (/auth/me).
"""

import pytest


class TestAuthLogin:
    async def test_login_endpoint_exists(self, client):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@test.com", "password": "senha123"},
        )
        # Stub retorna 501 — endpoint existe mas não implementado
        assert response.status_code == 501

    async def test_login_requires_email_and_password(self, client):
        response = await client.post("/api/v1/auth/login", json={})
        assert response.status_code == 422  # Pydantic validation

    async def test_login_rejects_invalid_email(self, client):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "nao_e_email", "password": "senha"},
        )
        assert response.status_code == 422

    async def test_login_rejects_empty_password(self, client):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "user@test.com", "password": ""},
        )
        # Senha vazia é aceita no schema (sem min_length no login)
        # mas deve retornar 501 pois o stub não implementa
        assert response.status_code in (501, 422)


class TestAuthRefresh:
    async def test_refresh_endpoint_exists(self, client):
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "algum_token"},
        )
        assert response.status_code == 501

    async def test_refresh_requires_token(self, client):
        response = await client.post("/api/v1/auth/refresh", json={})
        assert response.status_code == 422


class TestAuthMe:
    async def test_me_requires_authentication(self, client):
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401  # HTTPBearer retorna 401 sem header

    async def test_me_with_invalid_token_returns_401(self, client):
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer token.invalido.aqui"},
        )
        assert response.status_code == 401

    async def test_me_with_valid_token_returns_user_info(self, client):
        from uuid import uuid4
        from app.core.security import create_access_token

        token = create_access_token(
            user_id=uuid4(), tenant_id=uuid4(), role="admin"
        )
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert "tenant_id" in data
        assert data["role"] == "admin"

    async def test_me_returns_correct_role(self, client):
        from uuid import uuid4
        from app.core.security import create_access_token

        for role in ["admin", "driver", "client"]:
            token = create_access_token(uuid4(), uuid4(), role)
            response = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.json()["role"] == role


class TestAuthLogout:
    async def test_logout_requires_authentication(self, client):
        response = await client.post("/api/v1/auth/logout")
        assert response.status_code == 401

    async def test_logout_with_valid_token(self, client):
        from uuid import uuid4
        from app.core.security import create_access_token

        token = create_access_token(uuid4(), uuid4(), "admin")
        response = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 501  # stub
