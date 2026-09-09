from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import PlatformSetting

CUTLUY_SETTING_KEYS: tuple[str, ...] = (
    "cutluy_mode",
    "cutluy_api_url",
    "cutluy_api_key",
    "cutluy_webhook_secret",
    "cutluy_store_link",
    "cutluy_callback_url",
    "cutluy_checkout_success_url",
    "cutluy_checkout_failure_url",
)

PADDLE_SETTING_KEYS: tuple[str, ...] = (
    "paddle_mode",
    "paddle_api_url",
    "paddle_api_key",
    "paddle_client_token",
    "paddle_webhook_secret",
    "paddle_price_ids",
    "paddle_checkout_success_url",
    "paddle_checkout_failure_url",
)

_ENV_DEFAULTS: dict[str, str | None] = {
    "cutluy_mode": settings.cutluy_mode,
    "cutluy_api_url": settings.cutluy_api_url,
    "cutluy_api_key": settings.cutluy_api_key,
    "cutluy_webhook_secret": settings.cutluy_webhook_secret,
    "cutluy_store_link": None,
    "cutluy_callback_url": None,
    "cutluy_checkout_success_url": None,
    "cutluy_checkout_failure_url": None,
}

_PADDLE_ENV_DEFAULTS: dict[str, str | None] = {
    "paddle_mode": settings.paddle_mode,
    "paddle_api_url": settings.paddle_api_url,
    "paddle_api_key": settings.paddle_api_key,
    "paddle_client_token": settings.paddle_client_token,
    "paddle_webhook_secret": settings.paddle_webhook_secret,
    "paddle_price_ids": settings.paddle_price_ids,
    "paddle_checkout_success_url": settings.paddle_checkout_success_url,
    "paddle_checkout_failure_url": settings.paddle_checkout_failure_url,
}


async def load_cutluy_settings(db: AsyncSession) -> dict[str, str | None]:
    """Return effective CutLuy platform settings (DB overrides, else env)."""
    result = await db.execute(select(PlatformSetting).where(PlatformSetting.key.in_(CUTLUY_SETTING_KEYS)))
    overrides = {row.key: row.value for row in result.scalars().all() if row.value not in (None, "")}
    effective = dict(_ENV_DEFAULTS)
    effective.update(overrides)
    return effective


async def save_cutluy_settings(db: AsyncSession, updates: dict[str, str | None]) -> None:
    """Persist CutLuy platform settings. An empty/None value removes the DB
    override so the row falls back to the environment default."""
    for key, value in updates.items():
        if key not in CUTLUY_SETTING_KEYS:
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


def _parse_price_ids(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key): str(value) for key, value in parsed.items() if value}


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return json.dumps(value, separators=(",", ":"))
    return str(value).strip()


async def load_paddle_settings(db: AsyncSession) -> dict[str, Any]:
    """Return effective Paddle platform settings (DB overrides, else env).

    ``price_ids`` is returned as a parsed ``{plan_code:billing_cycle: price_id}``
    mapping keyed by ``"<plan_code>:<billing_cycle>"`` (e.g. ``pro:annual``).
    """
    result = await db.execute(select(PlatformSetting).where(PlatformSetting.key.in_(PADDLE_SETTING_KEYS)))
    overrides = {row.key: row.value for row in result.scalars().all() if row.value not in (None, "")}
    effective = dict(_PADDLE_ENV_DEFAULTS)
    effective.update(overrides)
    price_ids = _parse_price_ids(effective.get("paddle_price_ids"))
    return {
        "paddle_mode": effective.get("paddle_mode") or "mock",
        "paddle_api_url": effective.get("paddle_api_url"),
        "paddle_api_key": effective.get("paddle_api_key"),
        "paddle_client_token": effective.get("paddle_client_token"),
        "paddle_webhook_secret": effective.get("paddle_webhook_secret"),
        "paddle_checkout_success_url": effective.get("paddle_checkout_success_url"),
        "paddle_checkout_failure_url": effective.get("paddle_checkout_failure_url"),
        "paddle_price_ids": price_ids,
    }


async def save_paddle_settings(db: AsyncSession, updates: dict[str, str | None]) -> None:
    """Persist Paddle platform settings. Empty/None values remove the DB override."""
    for key, value in updates.items():
        if key not in PADDLE_SETTING_KEYS:
            continue
        cleaned = _stringify(value)
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
