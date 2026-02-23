from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Aplicação
    APP_NAME: str = "transLog"
    APP_ENV: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str

    # JWT
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Banco de Dados
    DATABASE_URL: str

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # CORS — recebe string JSON no .env, ex: '["http://localhost:3000"]'
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: str | list) -> list:
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v

    # Asaas
    ASAAS_API_KEY: str = ""
    ASAAS_API_URL: str = "https://sandbox.asaas.com/api/v3"
    ASAAS_WEBHOOK_SECRET: str = ""

    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM_EMAIL: str = "noreply@translog.com.br"
    EMAILS_FROM_NAME: str = "transLog"

    # QR Code / OTP
    OTP_ISSUER_NAME: str = "transLog"
    QR_CODE_TTL_SECONDS: int = 300

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60


settings = Settings()
