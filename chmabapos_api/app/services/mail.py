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
RESEND_DOMAINS_ENDPOINT = "https://api.resend.com/domains"
RESEND_WEBHOOKS_ENDPOINT = "https://api.resend.com/webhooks"

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


async def resend_tracking_state(api_key: str) -> dict:
    """Read Resend's live domain and webhook configuration.

    Open and click tracking is a per-domain switch inside Resend, not something
    Chmaba stores, so a delivery log with no reads can only be explained by
    looking there. Returns the two lists the admin diagnostic needs and raises
    ``RuntimeError`` with the provider's message on any non-2xx response.
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            domains_response, webhooks_response = await asyncio.gather(
                client.get(RESEND_DOMAINS_ENDPOINT, headers=headers),
                client.get(RESEND_WEBHOOKS_ENDPOINT, headers=headers),
            )
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Could not reach Resend to check tracking: {exc}") from exc

    for response, label in ((domains_response, "domains"), (webhooks_response, "webhooks")):
        if response.status_code >= 400:
            raise RuntimeError(f"Resend rejected the {label} request ({response.status_code}): {response.text[:200]}")

    def _list(response) -> list[dict]:
        try:
            body = response.json()
        except ValueError:
            return []
        data = body.get("data") if isinstance(body, dict) else None
        return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []

    domains = [
        {
            "name": str(row.get("name") or ""),
            "status": row.get("status"),
            "open_tracking": bool(row.get("open_tracking")),
            "click_tracking": bool(row.get("click_tracking")),
            "tracking_subdomain": str(row.get("tracking_subdomain") or "") or None,
        }
        for row in _list(domains_response)
    ]
    webhooks = [
        {
            "endpoint": str(row.get("endpoint") or ""),
            "status": row.get("status"),
            "events": [str(event) for event in row.get("events") or [] if isinstance(event, str)],
        }
        for row in _list(webhooks_response)
    ]
    return {"domains": domains, "webhooks": webhooks}


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
