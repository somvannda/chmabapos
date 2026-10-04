"""Server-side sign-in sessions and rotating refresh tokens.

The access token is short-lived and only references a session by id; the
long-lived credential is an opaque refresh token held in an httpOnly cookie and
stored here as a hash. Rotating the token on every refresh means a leaked token
is only usable once, and replaying an already-rotated token revokes the session.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthSession, User
from app.security import hash_opaque_token
from app.services.session_policy import resolve_session_ttl_minutes


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def _user_agent(request: Request | None) -> str | None:
    if request is None:
        return None
    value = (request.headers.get("user-agent") or "").strip()
    return value[:255] or None


def _ip(request: Request | None) -> str | None:
    if request is None or request.client is None:
        return None
    return request.client.host


def _expiry(ttl_minutes: int) -> datetime:
    return _now() + timedelta(minutes=ttl_minutes)


async def create_session(
    db: AsyncSession, user: User, *, remember: bool, request: Request | None
) -> tuple[AuthSession, str]:
    """Start a session for ``user`` and return ``(session, refresh_token)``.

    The caller commits. The session lifetime is resolved from the company
    override (or the platform default), capped by the platform maximum;
    ``remember`` opts into the longer remembered lifetime, still capped the
    same way. ``remember`` also affects cookie persistence, set by the API
    layer.
    """
    # A brand-new user (e.g. first Google sign-in) has no id until it is flushed.
    await db.flush()
    token = _new_refresh_token()
    ttl_minutes = await resolve_session_ttl_minutes(db, user, remember=remember)
    session = AuthSession(
        user_id=user.id,
        refresh_token_hash=hash_opaque_token(token),
        remember=remember,
        user_agent=_user_agent(request),
        ip_address=_ip(request),
        last_used_at=_now(),
        expires_at=_expiry(ttl_minutes),
    )
    db.add(session)
    await db.flush()
    return session, token


async def is_new_device(db: AsyncSession, user_id: UUID, *, user_agent: str | None) -> bool:
    """True when this user-agent has not signed in on a live session before.

    Returns False for a brand-new account's first session (no prior sessions)
    and when the same user-agent was already seen, so the alert only fires for a
    genuinely different device. Call before :func:`create_session`, otherwise the
    session being started would suppress its own alert.
    """
    cleaned = (user_agent or "").strip()[:255] or None
    if cleaned is None:
        return False
    now = _now()
    agents = (
        await db.execute(
            select(AuthSession.user_agent).where(
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
            )
        )
    ).scalars().all()
    seen = {agent for agent in agents if agent}
    if not seen:
        return False
    return cleaned not in seen


async def rotate_session(
    db: AsyncSession, refresh_token: str, *, request: Request | None
) -> tuple[AuthSession | None, str | None]:
    """Exchange a refresh token for a rotated one.

    Returns ``(session, new_refresh_token)`` on success, or ``(None, None)`` when
    the token is unknown, expired or revoked. If the token matches a session's
    *previous* (already-rotated) token, the whole session is revoked: that only
    happens when a token is replayed after it was already used.
    """
    digest = hash_opaque_token(refresh_token)
    session = (
        await db.execute(select(AuthSession).where(AuthSession.refresh_token_hash == digest))
    ).scalar_one_or_none()
    if session is not None:
        if session.revoked_at is not None or session.expires_at <= _now():
            return None, None
        new_token = _new_refresh_token()
        session.previous_token_hash = session.refresh_token_hash
        session.refresh_token_hash = hash_opaque_token(new_token)
        session.last_used_at = _now()
        agent = _user_agent(request)
        if agent:
            session.user_agent = agent
        await db.flush()
        return session, new_token

    # Not the current token. If it is a recently rotated one, treat it as theft
    # and revoke the session it belongs to.
    replayed = (
        await db.execute(select(AuthSession).where(AuthSession.previous_token_hash == digest))
    ).scalar_one_or_none()
    if replayed is not None and replayed.revoked_at is None:
        replayed.revoked_at = _now()
        await db.flush()
    return None, None


async def revoke_session_by_token(db: AsyncSession, refresh_token: str) -> None:
    """Revoke the session that owns ``refresh_token`` (current or previous).

    Used by logout, which must work even after the access token has expired.
    """
    digest = hash_opaque_token(refresh_token)
    session = (
        await db.execute(
            select(AuthSession).where(
                (AuthSession.refresh_token_hash == digest)
                | (AuthSession.previous_token_hash == digest)
            )
        )
    ).scalar_one_or_none()
    if session is not None and session.revoked_at is None:
        session.revoked_at = _now()
        await db.flush()


async def get_active_session(db: AsyncSession, session_id: UUID) -> AuthSession | None:
    """Return the session if it exists, is unrevoked and unexpired."""
    session = await db.get(AuthSession, session_id)
    if session is None or session.revoked_at is not None or session.expires_at <= _now():
        return None
    return session


async def revoke_user_sessions(db: AsyncSession, user_id: UUID, *, keep_session_id: UUID | None = None) -> int:
    """Revoke every active session for a user, optionally sparing one.

    Used on a password change so a lost or forgotten device cannot keep using
    the account with the refresh token it already holds. Returns how many
    sessions were revoked. The caller commits.
    """
    query = select(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
    if keep_session_id is not None:
        query = query.where(AuthSession.id != keep_session_id)
    sessions = (await db.execute(query)).scalars().all()
    now = _now()
    for session in sessions:
        session.revoked_at = now
    await db.flush()
    return len(sessions)
