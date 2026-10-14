"""Storefront branding rules.

A merchant picks an *accent preset* rather than an arbitrary colour. The preset
is a vetted pair — a colour dark enough to carry white text, and a matching soft
tint — so a store page can never be published with unreadable contrast. This is
the WCAG requirement in ``docs/marketplace-storefront-plan.md`` §6.3 turned into
data instead of a review step.

Values are space-separated RGB channels so the storefront can hand them straight
to the ``packages/ui`` design tokens as CSS custom properties:

    --color-brand: 105 87 245;
    --color-brand-soft: 240 239 255;

That is the whole theming mechanism: the POS keeps the Chmaba palette because it
never receives these overrides, and a merchant's colours cannot leak into the
cashier UI.
"""

from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

DEFAULT_ACCENT = "violet"

# Monday-first, matching ``datetime.weekday()``.
DAY_ORDER = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

# Every ``brand`` clears 4.5:1 against white text, so a preset cannot produce an
# unreadable button. ``soft`` is the matching light tint for badges and panels.
ACCENT_PRESETS: dict[str, dict[str, str]] = {
    "violet": {"label": "Violet", "brand": "105 87 245", "brand_soft": "240 239 255"},
    "emerald": {"label": "Emerald", "brand": "4 120 87", "brand_soft": "236 253 245"},
    "teal": {"label": "Teal", "brand": "15 118 110", "brand_soft": "240 253 250"},
    "crimson": {"label": "Crimson", "brand": "185 28 28", "brand_soft": "254 242 242"},
    "amber": {"label": "Amber", "brand": "180 83 9", "brand_soft": "255 251 235"},
    "slate": {"label": "Slate", "brand": "51 65 85", "brand_soft": "241 245 249"},
}

ACCENT_KEYS: tuple[str, ...] = tuple(ACCENT_PRESETS)


def resolve_accent(key: str | None) -> tuple[str, dict[str, str]]:
    """The preset key and values for ``key``, falling back to the default.

    Falling back rather than raising keeps an old or hand-edited row renderable:
    a store page must never fail because somebody stored a preset we removed.
    """
    resolved = (key or "").strip().lower()
    if resolved not in ACCENT_PRESETS:
        resolved = DEFAULT_ACCENT
    return resolved, ACCENT_PRESETS[resolved]


def accent_choices() -> list[dict[str, str]]:
    """Presets for the merchant editor, so the UI cannot offer an invalid one."""
    return [{"key": key, **preset} for key, preset in ACCENT_PRESETS.items()]


def store_open_state(
    storefront: dict | None,
    timezone_name: str | None,
    now: datetime | None = None,
) -> bool | None:
    """Whether the store is open right now, or ``None`` when that is unknowable.

    Computed on the server so every visitor sees the same answer regardless of
    their own clock or timezone. ``None`` means "no hours published" or an
    unusable timezone, and the page then omits the status rather than guessing.
    """
    hours = (storefront or {}).get("hours") or []
    if not hours:
        return None
    try:
        zone = ZoneInfo(timezone_name or "UTC")
    except Exception:
        # Missing tzdata in the image, or a bad name: degrade to "unknown".
        return None

    local = (now or datetime.now(timezone.utc)).astimezone(zone)
    entry = next((row for row in hours if row.get("day") == DAY_ORDER[local.weekday()]), None)
    if not entry or entry.get("closed"):
        return False
    try:
        opens = time.fromisoformat(str(entry["open"]))
        closes = time.fromisoformat(str(entry["close"]))
    except Exception:
        return None

    current = local.time()
    if closes <= opens:
        # Window that runs past midnight, e.g. 18:00 -> 02:00.
        return current >= opens or current < closes
    return opens <= current < closes
