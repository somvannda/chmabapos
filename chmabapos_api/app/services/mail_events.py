"""Resend (Svix) webhook verification and bounce/complaint handling.

A hard bounce or a spam complaint is the signal that genuinely damages a sending
domain's reputation, so both immediately suppress the address and flag the
delivery row. Other event types are acknowledged and ignored.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EmailSend, EmailSuppression

# Svix rejects stale deliveries; mirror that so a replayed payload cannot be used.
SIGNATURE_TOLERANCE_SECONDS = 300

BOUNCE_EVENTS = {"email.bounced"}
COMPLAINT_EVENTS = {"email.complained"}


def verify_svix_signature(
    *,
    secret: str,
    payload: bytes,
    svix_id: str | None,
    svix_timestamp: str | None,
    svix_signature: str | None,
) -> bool:
    """Validate a Svix-signed webhook (Resend uses Svix).

    Svix signs ``{id}.{timestamp}.{body}`` with the base64-decoded secret, and
    sends one or more base64 signatures space-separated as ``v1,<sig>``.
    """
    if not secret or not svix_id or not svix_timestamp or not svix_signature:
        return False
    try:
        timestamp = int(svix_timestamp)
    except (TypeError, ValueError):
        return False
    sent_at = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    if abs((datetime.now(timezone.utc) - sent_at).total_seconds()) > SIGNATURE_TOLERANCE_SECONDS:
        return False

    raw_secret = secret.strip()
    if raw_secret.startswith("whsec_"):
        raw_secret = raw_secret[len("whsec_") :]
    try:
        key = base64.b64decode(raw_secret)
    except (ValueError, TypeError):
        return False

    signed = f"{svix_id}.{svix_timestamp}.".encode() + payload
    expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
    for candidate in svix_signature.split():
        value = candidate.split(",", 1)[1] if "," in candidate else candidate
        if hmac.compare_digest(value, expected):
            return True
    return False


def _recipients(data: dict) -> list[str]:
    to = data.get("to")
    if isinstance(to, str):
        return [to]
    if isinstance(to, list):
        return [item for item in to if isinstance(item, str)]
    return []


async def _suppress(db: AsyncSession, email: str, reason: str) -> None:
    cleaned = email.strip().lower()
    if not cleaned:
        return
    existing = await db.scalar(select(EmailSuppression.id).where(func.lower(EmailSuppression.email) == cleaned))
    if existing is None:
        db.add(EmailSuppression(email=cleaned, reason=reason))


async def apply_resend_event(db: AsyncSession, event_type: str, data: dict) -> dict:
    """Suppress and flag the recipient for a bounce/complaint; ignore the rest."""
    summary = {"event": event_type, "suppressed": 0, "flagged": 0}
    if event_type not in BOUNCE_EVENTS | COMPLAINT_EVENTS:
        return summary

    complained = event_type in COMPLAINT_EVENTS
    reason = "complained" if complained else "bounced"
    bounce = data.get("bounce") if isinstance(data.get("bounce"), dict) else {}
    message = str(bounce.get("message") or bounce.get("type") or "").strip()

    for recipient in _recipients(data):
        await _suppress(db, recipient, reason)
        summary["suppressed"] += 1
        rows = (
            await db.execute(
                select(EmailSend)
                .where(
                    func.lower(EmailSend.recipient_email) == recipient.strip().lower(),
                    EmailSend.status.in_(("queued", "sent")),
                )
                .order_by(EmailSend.created_at.desc())
                .limit(1)
            )
        ).scalars().all()
        for row in rows:
            row.status = "complained" if complained else "bounced"
            # A bounced address must not be retried by the queue.
            row.next_attempt_at = None
            row.error = message or f"Recipient {reason}"
            summary["flagged"] += 1

    await db.commit()
    return summary
