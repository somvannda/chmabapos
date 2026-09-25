"""Best-effort Telegram notifications for the internal operations group.

Sending is intentionally fire-and-forget: an unreachable Telegram API must never
break a signup, login, sale or payment. When the bot token or chat id is unset
the whole module is a no-op, so local development and tests incur no traffic.
"""
from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"
MESSAGE_LIMIT = 4096


async def send_telegram_message(text: str, *, chat_id: str | None = None) -> bool:
    """Send ``text`` to the configured chat. Returns True only on success."""
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
