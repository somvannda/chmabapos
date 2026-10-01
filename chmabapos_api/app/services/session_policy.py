"""Configurable lifetime of a sign-in session.

A normal (non "remember me") sign-in lasts ``session_default_ttl_minutes`` —
a platform setting, falling back to config — capped by
``session_max_ttl_minutes``. A company owner can override the duration for
their own team via ``Company.settings["session_ttl_minutes"]``, again bounded
by the platform maximum. "Remember me" keeps using the longer
``jwt_remember_ttl_minutes`` so an explicit opt-in still survives, but it is
capped by the same platform maximum.

The access token is unaffected: it stays short-lived and is refreshed from the
session cookie, so a long session never means a long-lived bearer token.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AuthSession, Company, Membership, PlatformSetting, User


DEFAULT_TTL_KEY = "session_default_ttl_minutes"
MAX_TTL_KEY = "session_max_ttl_minutes"

# Absolute ceiling no platform setting or company override may exceed (1 year).
# It exists so a typo can never mint an effectively permanent credential.
ABSOLUTE_MAX_TTL_MINUTES = 60 * 24 * 365


def _coerce_minutes(raw: object, fallback: int) -> int:
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return fallback


async def load_platform_session_policy(db: AsyncSession) -> tuple[int, int]:
    """Return ``(default_minutes, max_minutes)`` for normal sign-ins.

    Both are clamped to sane positive values, with the default never exceeding
    the maximum and the maximum never exceeding the absolute ceiling. A missing
    or malformed stored value falls back to the environment default.
    """
    rows = (
        await db.execute(select(PlatformSetting).where(PlatformSetting.key.in_([DEFAULT_TTL_KEY, MAX_TTL_KEY])))
    ).scalars()
    stored = {row.key: row.value for row in rows}

    maximum = _coerce_minutes(stored.get(MAX_TTL_KEY), settings.jwt_max_session_ttl_minutes)
    maximum = max(1, min(maximum, ABSOLUTE_MAX_TTL_MINUTES))

    default = _coerce_minutes(stored.get(DEFAULT_TTL_KEY), settings.jwt_session_ttl_minutes)
    default = max(1, min(default, maximum))
    return default, maximum


async def save_platform_session_policy(
    db: AsyncSession, *, default_minutes: int | None = None, max_minutes: int | None = None
) -> None:
    """Persist the platform default and/or maximum. The caller commits."""
    updates: dict[str, str] = {}
    if default_minutes is not None:
        updates[DEFAULT_TTL_KEY] = str(default_minutes)
    if max_minutes is not None:
        updates[MAX_TTL_KEY] = str(max_minutes)
    for key, value in updates.items():
        row = await db.get(PlatformSetting, key)
        if row is None:
            db.add(PlatformSetting(key=key, value=value))
        else:
            row.value = value
    await db.flush()


async def _company_override_minutes(db: AsyncSession, user: User) -> int | None:
    """The most generous session length across the user's active companies.

    A session belongs to a user, not a company, so when someone belongs to more
    than one company we honour the longest configured duration and let the
    platform maximum do the bounding.
    """
    rows = (
        await db.execute(
            select(Company.settings)
            .join(Membership, Membership.company_id == Company.id)
            .where(Membership.user_id == user.id, Membership.status == "active")
        )
    ).scalars()
    best: int | None = None
    for company_settings in rows:
        if not isinstance(company_settings, dict):
            continue
        value = _coerce_minutes(company_settings.get("session_ttl_minutes"), 0)
        if value > 0 and (best is None or value > best):
            best = value
    return best


async def resolve_session_ttl_minutes(db: AsyncSession, user: User, *, remember: bool) -> int:
    """Effective lifetime, in minutes, for a session created for ``user`` now."""
    default, maximum = await load_platform_session_policy(db)
    if remember:
        base = settings.jwt_remember_ttl_minutes
    else:
        base = await _company_override_minutes(db, user)
        if base is None:
            base = default
    return max(1, min(base, maximum))


def session_cookie_max_age(session: AuthSession) -> int:
    """Whole seconds the refresh cookie should live, from the session's own expiry."""
    remaining = session.expires_at - datetime.now(timezone.utc)
    return max(0, int(remaining.total_seconds()))
