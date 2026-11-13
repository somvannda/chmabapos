"""Best-effort Telegram notifications for the internal operations group.

Sending is intentionally fire-and-forget: an unreachable Telegram API must never
break a signup, login, sale or payment. When the bot token or chat id is unset
the whole module is a no-op, and outside a production deployment every send is a
no-op too: a local ``.env`` often carries the real bot credentials while
producing throwaway signups, test sales and probes of localhost services, and
none of that belongs in the operations group.
"""
from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"
MESSAGE_LIMIT = 4096


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
                    "text": text[:MESSAGE_LIMIT],
                    "disable_web_page_preview": True,
                },
            )
            response.raise_for_status()
        return True
    except (httpx.HTTPError, OSError):
        logger.warning("Telegram notification failed", exc_info=True)
        return False
