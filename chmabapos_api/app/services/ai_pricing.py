"""Approximate USD prices per 1,000 tokens for the AI usage dashboard.

Used only for a rough cost estimate in the admin panel — this is not billing and
not authoritative. Prices change; update this table when a provider changes them.
A model is matched by the longest key that appears as a substring of its name, so
more specific names win.
"""
from __future__ import annotations

from typing import Final

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


def estimate_cost_usd(model: str | None, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimated USD cost for one call; 0.0 when the model has no known price."""
    name = (model or "").lower()
    for key in sorted(PRICES_PER_1K, key=len, reverse=True):
        if key in name:
            input_price, output_price = PRICES_PER_1K[key]
            return (prompt_tokens / 1000.0) * input_price + (completion_tokens / 1000.0) * output_price
    return 0.0
