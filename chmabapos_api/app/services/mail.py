"""Outbound mail transport: SMTP relay or Resend, chosen from the admin panel.

The provider and its credentials live in ``platform_settings`` (DB overrides
env), so an operator can switch to Resend and paste an API key without touching
``.env`` or restarting. SMTP remains the default, so existing deployments keep
working unchanged.

Both transports raise on failure; ``deliver_message`` is the swallowing wrapper
used by ``app.email``, and ``send_with_settings`` is the raising one used by the
admin "send test" action so the real error can be shown.
"""
from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage
from email.policy import SMTP

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import SessionLocal
from app.models import PlatformSetting

MAIL_SETTING_KEYS: tuple[str, ...] = (
    "mail_provider",
    "resend_api_key",
    "resend_webhook_secret",
    "mail_from",
    "mail_from_name",
    "mail_reply_to",
    "mail_support_inbox",
)

MAIL_PROVIDERS: tuple[dict[str, str], ...] = (
    {"code": "smtp", "label": "SMTP relay"},
    {"code": "resend", "label": "Resend"},
)

RESEND_ENDPOINT = "https://api.resend.com/emails"

_ENV_MAIL_DEFAULTS: dict[str, str | None] = {
    "mail_provider": "smtp",
    "resend_api_key": settings.resend_api_key,
    "resend_webhook_secret": settings.resend_webhook_secret,
    "mail_from": settings.smtp_from,
    "mail_from_name": settings.mail_from_name,
    "mail_reply_to": settings.mail_reply_to,
    "mail_support_inbox": settings.support_inbox,
}


def mail_provider_catalog() -> list[dict[str, str]]:
    return [dict(provider) for provider in MAIL_PROVIDERS]


async def load_mail_settings(db: AsyncSession) -> dict[str, str | None]:
    """Return effective mail settings (DB overrides, else env defaults)."""
    result = await db.execute(select(PlatformSetting).where(PlatformSetting.key.in_(MAIL_SETTING_KEYS)))
    overrides = {row.key: row.value for row in result.scalars().all() if row.value not in (None, "")}
    effective = dict(_ENV_MAIL_DEFAULTS)
    effective.update(overrides)
    return effective


async def save_mail_settings(db: AsyncSession, updates: dict[str, str | None]) -> None:
    """Persist mail settings. An empty value removes the DB override."""
    for key, value in updates.items():
        if key not in MAIL_SETTING_KEYS:
            continue
        cleaned = (value or "").strip() if isinstance(value, str) else (value or "")
        row = await db.get(PlatformSetting, key)
        if not cleaned:
            if row is not None:
                await db.delete(row)
            continue
        if row is None:
            db.add(PlatformSetting(key=key, value=cleaned))
        elif row.value != cleaned:
            row.value = cleaned
    await db.commit()


async def effective_mail_settings() -> dict[str, str | None]:
    """Load settings on their own session, for callers without a db handle."""
    async with SessionLocal() as db:
        return await load_mail_settings(db)


def resolve_provider(cfg: dict[str, str | None]) -> str:
    provider = (cfg.get("mail_provider") or "smtp").strip().lower()
    return provider if provider in {item["code"] for item in MAIL_PROVIDERS} else "smtp"


def format_from(cfg: dict[str, str | None]) -> str:
    address = (cfg.get("mail_from") or settings.smtp_from or "").strip()
    name = (cfg.get("mail_from_name") or settings.mail_from_name or "").strip()
    return f"{name} <{address}>" if name else address


def _send_smtp(cfg, recipient, subject, text, html, headers, reply_to) -> None:
    message = EmailMessage(policy=SMTP.clone(max_line_length=998))
    message["From"] = format_from(cfg)
    message["To"] = recipient
    message["Subject"] = subject
    resolved_reply_to = reply_to or (cfg.get("mail_reply_to") or "").strip()
    if resolved_reply_to:
        message["Reply-To"] = resolved_reply_to
    for key, value in (headers or {}).items():
        message[key] = value
    message.set_content(text)
    if html:
        message.add_alternative(html, subtype="html")
    if settings.smtp_use_ssl:
        connection = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10)
    else:
        connection = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
    with connection as smtp:
        if settings.smtp_use_tls and not settings.smtp_use_ssl:
            smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


def _send_resend(cfg, recipient, subject, text, html, headers, reply_to) -> str | None:
    api_key = (cfg.get("resend_api_key") or "").strip()
    if not api_key:
        raise RuntimeError("Resend is selected but no API key is configured")
    payload: dict = {"from": format_from(cfg), "to": [recipient], "subject": subject, "text": text}
    if html:
        payload["html"] = html
    resolved_reply_to = reply_to or (cfg.get("mail_reply_to") or "").strip()
    if resolved_reply_to:
        payload["reply_to"] = resolved_reply_to
    if headers:
        payload["headers"] = dict(headers)
    with httpx.Client(timeout=15.0) as client:
        response = client.post(RESEND_ENDPOINT, json=payload, headers={"Authorization": f"Bearer {api_key}"})
    if response.status_code >= 400:
        raise RuntimeError(f"Resend rejected the message ({response.status_code}): {response.text[:300]}")
    # Resend returns ``{"id": "..."}``; keep it so webhook events can be matched
    # back to this message. A missing body is not fatal, just untrackable.
    try:
        return str(response.json().get("id") or "").strip() or None
    except ValueError:
        return None


async def send_with_settings(
    cfg: dict[str, str | None],
    *,
    recipient: str,
    subject: str,
    text: str,
    html: str | None = None,
    headers: dict[str, str] | None = None,
    reply_to: str | None = None,
) -> str | None:
    """Deliver one message with the given settings, raising on failure.

    Returns the provider's message id when it exposes one (Resend), else ``None``
    (SMTP has no equivalent).
    """
    provider = resolve_provider(cfg)
    sender = _send_resend if provider == "resend" else _send_smtp
    return await asyncio.to_thread(sender, cfg, recipient, subject, text, html, headers, reply_to)


async def deliver_message_with_id(
    *,
    recipient: str,
    subject: str,
    text: str,
    html: str | None = None,
    headers: dict[str, str] | None = None,
    reply_to: str | None = None,
) -> tuple[bool, str | None]:
    """Load the configured provider and deliver, returning ``(ok, message_id)``."""
    try:
        cfg = await effective_mail_settings()
        message_id = await send_with_settings(cfg, recipient=recipient, subject=subject, text=text, html=html, headers=headers, reply_to=reply_to)
        return True, message_id
    except (OSError, smtplib.SMTPException, RuntimeError, httpx.HTTPError):
        return False, None


async def deliver_message(
    *,
    recipient: str,
    subject: str,
    text: str,
    html: str | None = None,
    headers: dict[str, str] | None = None,
    reply_to: str | None = None,
) -> bool:
    """Load the configured provider and deliver, returning success as a bool."""
    ok, _ = await deliver_message_with_id(recipient=recipient, subject=subject, text=text, html=html, headers=headers, reply_to=reply_to)
    return ok
