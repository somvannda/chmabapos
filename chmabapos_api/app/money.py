"""Money rounding, in one place.

The riel has no subunit and most other currencies here use two decimals, so every
money value has to round with its own currency's quantum. A shared helper is what
stops a new call site hardcoding two decimals for KHR - which is how a total ends
up showing 4,000.00 riel, or a report drifts a riel per line.

`decimal_places` comes from `Currency.decimal_places` (0 for KHR, 2 for USD).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def quantum_for(decimal_places: int | None) -> Decimal:
    """The smallest representable unit: 1 for whole currencies, else 1/10^n."""
    places = int(decimal_places or 0)
    if places <= 0:
        return Decimal("1")
    return Decimal("1") / (Decimal("10") ** places)


def round_money(amount: Decimal, decimal_places: int | None) -> Decimal:
    """Round ``amount`` to the currency's own precision, half-up."""
    return Decimal(amount).quantize(quantum_for(decimal_places), rounding=ROUND_HALF_UP)
