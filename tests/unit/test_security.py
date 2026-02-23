"""Testes unitários para app/core/security.py

Equivalente ao JUnit + Mockito para o módulo de segurança.
Sem acesso a banco — testes puramente unitários.
"""

import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_returns_string(self):
        hashed = hash_password("senha123")
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_hash_is_not_plain_text(self):
        plain = "minha_senha_secreta"
        assert hash_password(plain) != plain

    def test_two_hashes_of_same_password_differ(self):
        # bcrypt usa salt aleatório
        h1 = hash_password("abc123")
        h2 = hash_password("abc123")
        assert h1 != h2

    def test_verify_correct_password(self):
        plain = "senha_correta"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("senha_certa")
        assert verify_password("senha_errada", hashed) is False

    def test_verify_empty_password_fails(self):
        hashed = hash_password("alguma_senha")
        assert verify_password("", hashed) is False


class TestAccessToken:
    def test_create_access_token_returns_string(self):
        token = create_access_token(
            user_id=uuid4(), tenant_id=uuid4(), role="admin"
        )
        assert isinstance(token, str)
        assert len(token) > 0

    def test_access_token_payload_contains_required_claims(self):
        user_id = uuid4()
        tenant_id = uuid4()
        token = create_access_token(user_id=user_id, tenant_id=tenant_id, role="driver")

        payload = decode_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["tenant_id"] == str(tenant_id)
        assert payload["role"] == "driver"
        assert payload["type"] == "access"

    def test_access_token_has_expiration(self):
        token = create_access_token(user_id=uuid4(), tenant_id=uuid4(), role="client")
        payload = decode_token(token)
        assert "exp" in payload
        assert "iat" in payload

    def test_access_token_exp_is_in_future(self):
        token = create_access_token(user_id=uuid4(), tenant_id=uuid4(), role="admin")
        payload = decode_token(token)
        now = datetime.now(UTC).timestamp()
        assert payload["exp"] > now

    @pytest.mark.parametrize("role", ["admin", "driver", "client"])
    def test_access_token_all_roles(self, role: str):
        token = create_access_token(user_id=uuid4(), tenant_id=uuid4(), role=role)
        payload = decode_token(token)
        assert payload["role"] == role


class TestRefreshToken:
    def test_create_refresh_token_returns_string(self):
        token = create_refresh_token(user_id=uuid4())
        assert isinstance(token, str)

    def test_refresh_token_type_claim(self):
        token = create_refresh_token(user_id=uuid4())
        payload = decode_token(token)
        assert payload["type"] == "refresh"

    def test_refresh_token_has_no_tenant_or_role(self):
        token = create_refresh_token(user_id=uuid4())
        payload = decode_token(token)
        assert "tenant_id" not in payload
        assert "role" not in payload

    def test_refresh_token_longer_expiry_than_access(self):
        user_id = uuid4()
        access = decode_token(create_access_token(user_id, uuid4(), "admin"))
        refresh = decode_token(create_refresh_token(user_id))
        assert refresh["exp"] > access["exp"]


class TestDecodeToken:
    def test_decode_valid_token(self):
        token = create_access_token(uuid4(), uuid4(), "admin")
        payload = decode_token(token)
        assert isinstance(payload, dict)

    def test_decode_invalid_token_raises(self):
        with pytest.raises(jwt.PyJWTError):
            decode_token("token.invalido.aqui")

    def test_decode_tampered_token_raises(self):
        token = create_access_token(uuid4(), uuid4(), "admin")
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(jwt.PyJWTError):
            decode_token(tampered)

    def test_decode_expired_token_raises(self):
        from app.core.config import settings

        expired_payload = {
            "sub": str(uuid4()),
            "type": "access",
            "tenant_id": str(uuid4()),
            "role": "admin",
            "iat": datetime.now(UTC) - timedelta(hours=2),
            "exp": datetime.now(UTC) - timedelta(hours=1),
        }
        expired_token = jwt.encode(
            expired_payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM
        )
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_token(expired_token)
