"""Revocable shopper sign-in sessions.

Shoppers had no server-side session: a bearer token stayed valid until it simply
expired, so signing out on a shared device changed nothing and a copied token
could not be killed. A session row gives logout something to revoke, and the
access token carries only its id.

This is the first half of the staff design: sessions that can be revoked. A
rotating refresh cookie is deliberately *not* here yet - sessions live as long as
``shopper_session_ttl_days``, and revoking one invalidates its token immediately.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import ShopperAccount, ShopperSession
from app.security import hash_opaque_token


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _user_agent(request: Request | None) -> str | None:
    if request is None:
        return None
    value = (request.headers.get("user-agent") or "").strip()
    return value[:255] or None


async def create_shopper_session(db: AsyncSession, shopper: ShopperAccount, *, request: Request | None = None) -> ShopperSession:
    """Start a session for ``shopper``. The caller commits.

    The refresh hash is minted now even though the rotating cookie that would use
    it is not wired yet: the column is unique and not-null, and issuing it here
    keeps the table ready for that change without a second migration.
    """
    await db.flush()
    session = ShopperSession(
        shopper_id=shopper.id,
        refresh_token_hash=hash_opaque_token(secrets.token_urlsafe(48)),
        user_agent=_user_agent(request),
        last_used_at=_now(),
        expires_at=_now() + timedelta(days=settings.shopper_session_ttl_days),
    )
    db.add(session)
    await db.flush()
    return session


async def get_active_shopper_session(db: AsyncSession, session_id: UUID) -> ShopperSession | None:
    """The session if it exists, is unrevoked and unexpired, else ``None``."""
    session = await db.get(ShopperSession, session_id)
    if session is None or session.revoked_at is not None or session.expires_at <= _now():
        return None
    return session


async def revoke_shopper_session(db: AsyncSession, session_id: UUID) -> bool:
    """Revoke one session. Returns whether it was still live. The caller commits."""
    session = await db.get(ShopperSession, session_id)
    if session is None or session.revoked_at is not None:
        return False
    session.revoked_at = _now()
    await db.flush()
    return True


async def revoke_shopper_sessions(db: AsyncSession, shopper_id: UUID, *, keep_session_id: UUID | None = None) -> int:
    """Revoke every live session for a shopper, optionally sparing one.

    For a future "sign out everywhere", and for the account-deletion path.
    """
    query = select(ShopperSession).where(ShopperSession.shopper_id == shopper_id, ShopperSession.revoked_at.is_(None))
    if keep_session_id is not None:
        query = query.where(ShopperSession.id != keep_session_id)
    sessions = (await db.execute(query)).scalars().all()
    now = _now()
    for session in sessions:
        session.revoked_at = now
    await db.flush()
    return len(sessions)
