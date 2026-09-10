"""Canonical plan pricing and prepaid period math.

Single source of truth for how a plan's monthly price becomes the amount
charged for a billing cycle, and how long that cycle lasts. Checkout, renewal
reminders, receipts and admin surfaces must all derive amounts from here so
pricing can never drift between them.

A plan stores exactly one canonical ``monthly_price``; cycle totals and
discounts are derived, never stored per cycle.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

# billing_cycle -> (months, discount, human label, fixed days)
CYCLE_META: dict[str, tuple[int, Decimal, str, int]] = {
    "monthly": (1, Decimal("0.00"), "monthly", 30),
    "semi_annual": (6, Decimal("0.15"), "semi-annually", 182),
    "annual": (12, Decimal("0.20"), "annually", 365),
}

DEFAULT_CYCLE = "monthly"


def _meta(billing_cycle: str) -> tuple[int, Decimal, str, int]:
    return CYCLE_META.get(billing_cycle, CYCLE_META[DEFAULT_CYCLE])


def cycle_days(billing_cycle: str) -> int:
    """Length of one prepaid period in days (fixed cycles for now)."""
    return _meta(billing_cycle)[3]


def period_label(billing_cycle: str) -> str:
    """Human label, e.g. ``monthly`` / ``semi-annually`` / ``annually``."""
    return _meta(billing_cycle)[2]


def period_total(monthly_price: Decimal, billing_cycle: str) -> Decimal:
    """Amount charged for one period, derived from the monthly price.

    ``semi_annual`` and ``annual`` apply their discount to the monthly price
    before multiplying, then round half-up to cents.
    """
    multiplier, discount, _label, _days = _meta(billing_cycle)
    total = monthly_price * (1 - discount) * multiplier
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def period_total_label(monthly_price: Decimal, billing_cycle: str) -> str:
    """Same as :func:`period_total` but formatted as a plain string."""
    return f"{period_total(monthly_price, billing_cycle):.2f}"
