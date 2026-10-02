"""Approximate USD prices per 1,000 tokens for the AI usage dashboard.

Used only for a rough cost estimate in the admin panel — this is not billing and
not authoritative. A model is matched by the longest key that appears as a
substring of its name, so more specific names win.

``PRICES_PER_1K`` are the defaults; a platform admin can override them (stored as
JSON in ``platform_settings`` under ``ai_prices``) so the estimate can track
provider price changes without a code change.
"""
from __future__ import annotations

import json
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PlatformSetting

# model-name substring -> (input USD per 1k tokens, output USD per 1k tokens)
PRICES_PER_1K: Final[dict[str, tuple[float, float]]] = {
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4o": (0.0025, 0.01),
    "deepseek-chat": (0.00027, 0.0011),
    "deepseek-reasoner": (0.00055, 0.00219),
    "claude-3-5-sonnet": (0.003, 0.015),
    "claude-3-5-haiku": (0.0008, 0.004),
    "claude-3-opus": (0.015, 0.075),
}

PRICES_KEY: Final[str] = "ai_prices"


def estimate_cost_usd(
    model: str | None,
    prompt_tokens: int,
    completion_tokens: int,
    prices: dict[str, tuple[float, float]] | None = None,
) -> float:
    """Estimated USD cost for one call; 0.0 when the model has no known price.

    ``prices`` overrides the built-in defaults (they are merged, so a partial map
    only changes the models it lists).
    """
    table = {**PRICES_PER_1K, **(prices or {})}
    name = (model or "").lower()
    for key in sorted(table, key=len, reverse=True):
        if key in name:
            input_price, output_price = table[key]
            return (prompt_tokens / 1000.0) * input_price + (completion_tokens / 1000.0) * output_price
    return 0.0


async def load_prices(db: AsyncSession) -> dict[str, tuple[float, float]]:
    """Defaults merged with the admin's stored overrides (``ai_prices``)."""
    prices = dict(PRICES_PER_1K)
    row = await db.get(PlatformSetting, PRICES_KEY)
    if row is not None and row.value:
        try:
            override = json.loads(row.value)
        except ValueError:
            override = None
        if isinstance(override, dict):
            for key, value in override.items():
                if isinstance(value, (list, tuple)) and len(value) == 2:
                    try:
                        prices[str(key)] = (float(value[0]), float(value[1]))
                    except (TypeError, ValueError):
                        continue
    return prices


async def save_prices(db: AsyncSession, prices: dict | None) -> None:
    """Persist the override map; an empty value removes the override."""
    value = json.dumps(prices) if prices else None
    row = await db.get(PlatformSetting, PRICES_KEY)
    if not value:
        if row is not None:
            await db.delete(row)
        return
    if row is None:
        db.add(PlatformSetting(key=PRICES_KEY, value=value))
    elif row.value != value:
        row.value = value
