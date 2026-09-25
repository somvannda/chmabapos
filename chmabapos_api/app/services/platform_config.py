from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import PlatformSetting

PAYMENT_SETTING_KEYS: tuple[str, ...] = (
    "chamabapay_mode",
    "chamabapay_api_url",
    "chamabapay_api_key",
    "chamabapay_webhook_secret",
    "chamabapay_platform_store_id",
)

_ENV_PAYMENT_DEFAULTS: dict[str, str | None] = {
    "chamabapay_mode": settings.chamabapay_mode,
    "chamabapay_api_url": settings.chamabapay_api_url,
    "chamabapay_api_key": settings.chamabapay_api_key,
    "chamabapay_webhook_secret": settings.chamabapay_webhook_secret,
    "chamabapay_platform_store_id": settings.chamabapay_platform_store_id,
}


async def load_payment_settings(db: AsyncSession) -> dict[str, str | None]:
    """Return effective ChmabaPay settings (DB overrides, else env)."""
    result = await db.execute(select(PlatformSetting).where(PlatformSetting.key.in_(PAYMENT_SETTING_KEYS)))
    overrides = {row.key: row.value for row in result.scalars().all() if row.value not in (None, "")}
    effective = dict(_ENV_PAYMENT_DEFAULTS)
    effective.update(overrides)
    return effective


async def save_payment_settings(db: AsyncSession, updates: dict[str, str | None]) -> None:
    """Persist ChmabaPay settings (DB overrides of env defaults).

    An empty/None value removes the DB override so the row falls back to the
    environment default.
    """
    for key, value in updates.items():
        if key not in PAYMENT_SETTING_KEYS:
            continue
        cleaned = (value or "").strip() if isinstance(value, str) else (value or "")
        row = await db.get(PlatformSetting, key)
        if not cleaned:
            if row is not None:
                await db.delete(row)
            continue
        if row is None:
            db.add(PlatformSetting(key=key, value=cleaned))
        elif row.value != cleaned:
            row.value = cleaned
    await db.commit()
