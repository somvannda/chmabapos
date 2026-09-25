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
    # ChmabaPay (https://pay.chmaba.com). "mock" is a local fake (no sandbox
    # exists); "live" calls the real API.
    chamabapay_mode: Literal["mock", "live"] = "mock"
    chamabapay_api_url: str = "https://pay.chmaba.com"
    chamabapay_api_key: str | None = None
    chamabapay_webhook_secret: str | None = None
    # Chmaba's own internal ChmabaPay store, used to collect plan fees.
    chamabapay_platform_store_id: str | None = None
    # Paid plans stay fully usable for this many hours past ``ends_at`` before
    # the Free fallback runs, so a missed renewal does not instantly pause a
    # merchant's stores. A payment inside the window reactivates with no gap.
    billing_grace_hours: int = 48

    model_config = SettingsConfigDict(env_file="chmabapos_api/.env", env_file_encoding="utf-8", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
