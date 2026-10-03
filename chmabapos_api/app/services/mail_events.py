"""Resend (Svix) webhook verification and delivery-event handling.

A hard bounce or a spam complaint is the signal that genuinely damages a sending
domain's reputation, so both immediately suppress the address and flag the
delivery row. Resend's delivered/opened/clicked events advance the matching row
so the admin delivery log can show more than ``sent``.
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
DELIVERED_EVENTS = {"email.delivered"}
OPENED_EVENTS = {"email.opened"}
CLICKED_EVENTS = {"email.clicked"}
DELAYED_EVENTS = {"email.delivery_delayed"}
SENT_EVENTS = {"email.sent"}

TRACKED_EVENTS = (
    BOUNCE_EVENTS
    | COMPLAINT_EVENTS
    | DELIVERED_EVENTS
    | OPENED_EVENTS
    | CLICKED_EVENTS
    | DELAYED_EVENTS
    | SENT_EVENTS
)


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


async def _match_sends(db: AsyncSession, email_id: str, recipients: list[str]) -> list[EmailSend]:
    """Find the send rows a webhook event refers to.

    Prefer the provider message id, which is exact. Events for rows written
    before the id was stored fall back to the most recent send per recipient.
    """
    if email_id:
        rows = (
            await db.execute(select(EmailSend).where(EmailSend.provider_message_id == email_id))
        ).scalars().all()
        if rows:
            return list(rows)

    matched: list[EmailSend] = []
    seen: set[str] = set()
    for recipient in recipients:
        cleaned = recipient.strip().lower()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        row = await db.scalar(
            select(EmailSend)
            .where(func.lower(EmailSend.recipient_email) == cleaned)
            .order_by(EmailSend.created_at.desc())
            .limit(1)
        )
        if row is not None:
            matched.append(row)
    return matched


def _advance_status(row: EmailSend) -> None:
    """Move a row to the furthest confirmed stage, never downgrading it.

    Out-of-order webhooks are safe: the status is recomputed from every
    timestamp set so far rather than from the event currently being applied.
    """
    if row.status in ("bounced", "complained", "failed"):
        return
    if row.clicked_at is not None:
        row.status = "clicked"
    elif row.opened_at is not None:
        row.status = "opened"
    elif row.delivered_at is not None:
        row.status = "delivered"


async def apply_resend_event(db: AsyncSession, event_type: str, data: dict) -> dict:
    """Advance the matching delivery row(s); suppress on bounce/complaint."""
    summary = {"event": event_type, "suppressed": 0, "flagged": 0, "tracked": 0}
    if event_type not in TRACKED_EVENTS:
        return summary

    data = data if isinstance(data, dict) else {}
    email_id = str(data.get("email_id") or "").strip()
    recipients = _recipients(data)
    now = datetime.now(timezone.utc)

    complained = event_type in COMPLAINT_EVENTS
    bounced = event_type in BOUNCE_EVENTS
    reason = "complained" if complained else "bounced"
    bounce = data.get("bounce") if isinstance(data.get("bounce"), dict) else {}
    message = str(bounce.get("message") or bounce.get("type") or "").strip()

    if bounced or complained:
        for recipient in dict.fromkeys(item.strip().lower() for item in recipients if item.strip()):
            await _suppress(db, recipient, reason)
            summary["suppressed"] += 1

    for row in await _match_sends(db, email_id, recipients):
        if email_id and not row.provider_message_id:
            row.provider_message_id = email_id
        row.last_event_at = now

        if bounced or complained:
            row.status = reason
            # A bounced or complained address must not be retried by the queue.
            row.next_attempt_at = None
            row.error = message or f"Recipient {reason}"
            summary["flagged"] += 1
            continue

        if event_type in SENT_EVENTS:
            if row.status == "queued":
                row.status = "sent"
            continue

        if event_type in DELIVERED_EVENTS:
            row.delivered_at = row.delivered_at or now
        elif event_type in OPENED_EVENTS:
            row.opened_at = row.opened_at or now
        elif event_type in CLICKED_EVENTS:
            row.clicked_at = row.clicked_at or now
        elif event_type in DELAYED_EVENTS:
            row.error = message or "Delivery delayed"
            if row.status in ("queued", "sent"):
                row.status = "delayed"
        _advance_status(row)
        summary["tracked"] += 1

    await db.commit()
    return summary
