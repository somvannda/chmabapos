from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Chmaba API"
    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/chmaba_v1"
    sync_database_url: str = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/chmaba_v1"
    jwt_secret: str = "chmaba-local-development-secret-change-me"
    jwt_access_ttl_minutes: int = 60
    jwt_remember_ttl_minutes: int = 60 * 24 * 30
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://127.0.0.1:8000/api/v1/auth/google/callback"
    frontend_url: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173"
    smtp_host: str = "127.0.0.1"
    smtp_port: int = 1025
    smtp_from: str = "no-reply@chmaba.local"
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = False
    mailhog_ui_url: str = "http://localhost:8025"
    cutluy_mode: Literal["mock", "live"] = "mock"
    cutluy_api_url: str = "https://cutluy.com/v1"
    cutluy_api_key: str | None = None
    cutluy_webhook_secret: str | None = None
    paddle_mode: Literal["mock", "sandbox", "live"] = "mock"
    paddle_api_url: str | None = None
    paddle_api_key: str | None = None
    paddle_client_token: str | None = None
    paddle_webhook_secret: str | None = None
    paddle_price_ids: str = "{}"
    paddle_checkout_success_url: str | None = None
    paddle_checkout_failure_url: str | None = None

    model_config = SettingsConfigDict(env_file="chmabapos_api/.env", env_file_encoding="utf-8", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
