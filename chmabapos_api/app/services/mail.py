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
import json
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
    # JSON list of extra identities the composer may choose as From. The
    # default identity above is always available and need not be repeated.
    "mail_senders",
    # Per-purpose From overrides for automated mail. Unset purposes derive
    # their address from the configured default domain (see PURPOSES below).
    "mail_from_billing",
    "mail_from_support",
    "mail_from_security",
    "mail_from_onboarding",
    "mail_from_receipts",
    "mail_from_notifications",
    "mail_from_marketing",
    "mail_from_ops",
)

# A sender list is UI convenience, not a mailing list; cap it so a malformed
# setting cannot make the composer unusable.
MAX_SENDER_IDENTITIES = 10

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
    "mail_senders": None,
    "mail_from_billing": settings.mail_from_billing,
    "mail_from_support": settings.mail_from_support,
    "mail_from_security": settings.mail_from_security,
    "mail_from_onboarding": settings.mail_from_onboarding,
    "mail_from_receipts": settings.mail_from_receipts,
    "mail_from_notifications": settings.mail_from_notifications,
    "mail_from_marketing": settings.mail_from_marketing,
    "mail_from_ops": settings.mail_from_ops,
}

# Purpose -> local part used when no explicit ``mail_from_<purpose>`` is set.
# The domain comes from the configured default sender, so a deploy only needs
# SMTP_FROM (no-reply@chmaba.com) and gets billing@chmaba.com, support@... etc.
PURPOSE_LOCAL_PARTS: dict[str, str] = {
    "billing": "billing",
    "support": "support",
    "security": "security",
    "onboarding": "hello",
    "receipts": "receipts",
    "notifications": "notifications",
    "marketing": "hello",
    "ops": "ops",
}

# Queued mail carries its purpose through ``EmailSend.source``. A source that
# is not listed here keeps the platform default sender.
SOURCE_PURPOSES: dict[str, str] = {
    "billing_receipt": "billing",
    "billing_failure": "billing",
    "billing_reminder": "billing",
    "billing_expiry": "billing",
    "billing_price_change": "billing",
    "quota_warning": "billing",
    "sale_alert": "notifications",
    "store_note": "notifications",
    "store_chat_alert": "notifications",
    "store_chat_reply": "notifications",
    "receipt": "receipts",
    "refund_confirmation": "receipts",
    "online_order_ack": "receipts",
    "online_order_expired": "receipts",
    "service_ticket": "receipts",
    "support_chat_reply": "support",
    "shopper_signin": "security",
    "manual": "marketing",
    "drip": "onboarding",
}


def mail_provider_catalog() -> list[dict[str, str]]:
    return [dict(provider) for provider in MAIL_PROVIDERS]


async def load_mail_settings(db: AsyncSession) -> dict[str, str | None]:
    """Return effective mail settings (DB overrides, else env defaults)."""
    result = await db.execute(select(PlatformSetting).where(PlatformSetting.key.in_(MAIL_SETTING_KEYS)))
    overrides = {row.key: row.value for row in result.scalars().all() if row.value not in (None, "")}
    effective = dict(_ENV_MAIL_DEFAULTS)
    effective.update(overrides)
    if not effective.get("mail_reply_to"):
        effective["mail_reply_to"] = default_purpose_address(effective, "support")
    return effective


def _mail_domain(cfg: dict[str, str | None]) -> str | None:
    """Domain of the configured default sender, or ``None`` when unusable."""
    address = (cfg.get("mail_from") or settings.smtp_from or "").strip()
    if "@" not in address:
        return None
    domain = address.rsplit("@", 1)[1].strip().lower()
    return domain or None


def default_purpose_address(cfg: dict[str, str | None], purpose: str) -> str | None:
    """Derive the branded address for a purpose from the default sender domain."""
    local_part = PURPOSE_LOCAL_PARTS.get(purpose)
    domain = _mail_domain(cfg)
    if not local_part or not domain:
        return None
    return f"{local_part}@{domain}"


def purpose_from_source(source: str | None) -> str | None:
    """Purpose for a queued message, inferred from its outbox ``source``."""
    return SOURCE_PURPOSES.get((source or "").strip().lower())


def resolve_purpose_sender(cfg: dict[str, str | None], purpose: str) -> dict[str, str | None]:
    """From identity for automated mail: explicit override, derived, then default."""
    address = (cfg.get(f"mail_from_{purpose}") or "").strip()
    if not address:
        address = default_purpose_address(cfg, purpose) or ""
    if not address:
        address = (cfg.get("mail_from") or settings.smtp_from or "").strip()
    name = (cfg.get("mail_from_name") or settings.mail_from_name or "").strip() or None
    return {"address": address, "name": name}


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


def parse_sender_identities(raw: str | None) -> list[dict[str, str | None]]:
    """Read the extra identities stored in ``mail_senders``.

    Malformed entries are ignored rather than failing every mail request: the
    default identity still works, and the Settings page can show what is stored.
    """
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    output: list[dict[str, str | None]] = []
    seen: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        address = str(item.get("address") or "").strip()
        if "@" not in address:
            continue
        key = address.lower()
        if key in seen:
            continue
        seen.add(key)
        name = str(item.get("name") or "").strip()[:120] or None
        reply_to = str(item.get("reply_to") or "").strip() or None
        output.append({"name": name, "address": address, "reply_to": reply_to})
    return output[:MAX_SENDER_IDENTITIES]


def serialise_sender_identities(senders: list[dict[str, str | None]]) -> str:
    return json.dumps(parse_sender_identities(json.dumps(senders)), separators=(",", ":"), ensure_ascii=False)


def sender_identities(cfg: dict[str, str | None]) -> list[dict[str, str | None]]:
    """The default From identity followed by any configured extras."""
    default_address = (cfg.get("mail_from") or settings.smtp_from or "").strip()
    identities: list[dict[str, str | None]] = []
    if default_address:
        identities.append(
            {
                "name": (cfg.get("mail_from_name") or settings.mail_from_name or "").strip() or None,
                "address": default_address,
                "reply_to": (cfg.get("mail_reply_to") or "").strip() or None,
            }
        )
    for item in parse_sender_identities(cfg.get("mail_senders")):
        if item["address"] and item["address"].lower() == default_address.lower():
            continue
        identities.append(item)
    return identities


def resolve_sender(
    cfg: dict[str, str | None],
    address: str | None = None,
    reply_to: str | None = None,
) -> dict[str, str | None]:
    """Resolve a requested From/reply-to against the configured allow-list.

    Raises ``ValueError`` with an operator-facing message when the address is
    not configured. Replies fall back from an explicit override, to the chosen
    identity's own reply-to, to the platform default reply-to.
    """
    identities = sender_identities(cfg)
    chosen: dict[str, str | None] | None = None
    if address and address.strip():
        wanted = address.strip().lower()
        chosen = next((item for item in identities if (item["address"] or "").lower() == wanted), None)
        if chosen is None:
            raise ValueError("That sender address is not configured. Add it under Settings > Email sending.")
    elif identities:
        chosen = identities[0]
    if chosen is None:
        raise ValueError("No From address is configured for outbound mail.")
    resolved_reply = (
        (reply_to or "").strip()
        or (chosen.get("reply_to") or "").strip()
        or (cfg.get("mail_reply_to") or "").strip()
        or None
    )
    return {"address": chosen["address"], "name": chosen.get("name"), "reply_to": resolved_reply}


def format_from(cfg: dict[str, str | None], address: str | None = None, name: str | None = None) -> str:
    resolved_address = (address or cfg.get("mail_from") or settings.smtp_from or "").strip()
    resolved_name = (name if name is not None else (cfg.get("mail_from_name") or settings.mail_from_name or "")).strip()
    return f"{resolved_name} <{resolved_address}>" if resolved_name else resolved_address


def _send_smtp(cfg, recipient, subject, text, html, headers, reply_to, from_address=None, from_name=None) -> None:
    message = EmailMessage(policy=SMTP.clone(max_line_length=998))
    message["From"] = format_from(cfg, from_address, from_name)
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


def _send_resend(cfg, recipient, subject, text, html, headers, reply_to, from_address=None, from_name=None) -> str | None:
    api_key = (cfg.get("resend_api_key") or "").strip()
    if not api_key:
        raise RuntimeError("Resend is selected but no API key is configured")
    payload: dict = {"from": format_from(cfg, from_address, from_name), "to": [recipient], "subject": subject, "text": text}
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
    from_address: str | None = None,
    from_name: str | None = None,
) -> str | None:
    """Deliver one message with the given settings, raising on failure.

    Returns the provider's message id when it exposes one (Resend), else ``None``
    (SMTP has no equivalent).
    """
    provider = resolve_provider(cfg)
    sender = _send_resend if provider == "resend" else _send_smtp
    return await asyncio.to_thread(sender, cfg, recipient, subject, text, html, headers, reply_to, from_address, from_name)


async def deliver_message_with_id(
    *,
    recipient: str,
    subject: str,
    text: str,
    html: str | None = None,
    headers: dict[str, str] | None = None,
    reply_to: str | None = None,
    from_address: str | None = None,
    from_name: str | None = None,
    purpose: str | None = None,
) -> tuple[bool, str | None]:
    """Load the configured provider and deliver, returning ``(ok, message_id)``.

    ``purpose`` selects the branded From identity for automated mail (billing,
    support, receipts, ...). An explicit ``from_address`` always wins, which is
    how a composer-chosen campaign identity keeps working.
    """
    try:
        cfg = await effective_mail_settings()
        if from_address is None and purpose:
            sender = resolve_purpose_sender(cfg, purpose)
            from_address = sender["address"]
            from_name = from_name or sender["name"]
        message_id = await send_with_settings(
            cfg,
            recipient=recipient,
            subject=subject,
            text=text,
            html=html,
            headers=headers,
            reply_to=reply_to,
            from_address=from_address,
            from_name=from_name,
        )
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
    from_address: str | None = None,
    from_name: str | None = None,
    purpose: str | None = None,
) -> bool:
    """Load the configured provider and deliver, returning success as a bool."""
    ok, _ = await deliver_message_with_id(
        recipient=recipient,
        subject=subject,
        text=text,
        html=html,
        headers=headers,
        reply_to=reply_to,
        from_address=from_address,
        from_name=from_name,
        purpose=purpose,
    )
    return ok
