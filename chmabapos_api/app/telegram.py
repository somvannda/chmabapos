"""Best-effort Telegram notifications for the internal operations group.

Sending is intentionally fire-and-forget: an unreachable Telegram API must never
break a signup, login, sale or payment. When the bot token or chat id is unset
the whole module is a no-op, and outside a production deployment every send is a
no-op too: a local ``.env`` often carries the real bot credentials while
producing throwaway signups, test sales and probes of localhost services, and
none of that belongs in the operations group. Every message that does go out
ends with a ``Source: <public origin> (<environment>)`` line, so a reader can
tell which deployment sent it.
"""
from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"
MESSAGE_LIMIT = 4096


def source_label() -> str:
    """The deployment a message came from, e.g. ``https://chmaba.com (production)``.

    Appended to every message so a reader never has to guess whether a report
    came from the live platform or from someone's laptop. ``API_PUBLIC_URL`` is
    the public origin of this deployment; a local instance that was somehow
    allowed to page would show ``127.0.0.1`` or ``localhost`` here.
    """
    origin = (settings.api_public_url or settings.frontend_url or "").strip().rstrip("/")
    return f"{origin or 'unknown origin'} ({settings.environment})"


def alerts_enabled() -> bool:
    """Whether this process may post to the internal operations chat at all.

    A development or test instance often inherits the real
    ``TELEGRAM_BOT_TOKEN`` / ``TELEGRAM_CHAT_ID`` while producing throwaway
    signups, test sales and probes of localhost services. Posting those reports
    an outage or an event that exists only on that machine: the 12 Nov 2026
    "SMTP relay down" page was a laptop's switched-off MailHog.

    The rule is deliberately centralized here so every sender - activity
    forwarding, platform health alerts, the daily digest and the billing-worker
    alert - obeys it without each call site having to remember. Production is
    ``ENVIRONMENT=production``, which ``deploy/docker-compose.prod.yml`` pins.
    """
    return settings.environment == "production"


def with_source(text: str) -> str:
    """Append the deployment signature, staying inside Telegram's size limit."""
    suffix = f"\n\nSource: {source_label()}"
    body = text.rstrip()[: max(0, MESSAGE_LIMIT - len(suffix))].rstrip()
    return body + suffix


async def send_telegram_message(text: str, *, chat_id: str | None = None) -> bool:
    """Send ``text`` to the configured chat. Returns True only on success."""
    if not alerts_enabled():
        return False
    token = (settings.telegram_bot_token or "").strip()
    target = (chat_id or settings.telegram_chat_id or "").strip()
    if not token or not target or not text.strip():
        return False
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.post(
                f"{TELEGRAM_API_BASE}/bot{token}/sendMessage",
                json={
                    "chat_id": target,
                    "text": with_source(text),
                    "disable_web_page_preview": True,
                },
            )
            response.raise_for_status()
        return True
    except (httpx.HTTPError, OSError):
        logger.warning("Telegram notification failed", exc_info=True)
        return False
