"""Cloudflare Turnstile verification for the public auth endpoints.

Turnstile runs in the browser (see the site key exposed to the SPA) and hands the
login/sign-up form a short-lived token. The server checks that token against
Cloudflare's ``siteverify`` API before creating an account or a session.

When ``turnstile_secret_key`` is unset the whole check is a no-op: local
development, the test suite, and deployments that have not configured keys keep
working without a widget. A *configured* deployment fails closed — a missing or
invalid token is rejected.
"""
from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def verify_turnstile(token: str | None, *, remote_ip: str | None = None) -> bool:
    """Return True when the request passes Turnstile (or the check is disabled).

    ``token`` is the widget token from the request body; ``remote_ip`` is
    forwarded to Cloudflare as ``remoteip`` for extra signal when available.
    """
    secret = (settings.turnstile_secret_key or "").strip()
    if not secret:
        return True
    if not token:
        return False
    payload: dict[str, str] = {"secret": secret, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(settings.turnstile_verify_url, data=payload)
            response.raise_for_status()
            data = response.json()
    except Exception:
        # Never block a real user because Cloudflare is unreachable; treat an
        # unverifiable request as failed (fail closed) and log for the operator.
        logger.warning("Turnstile verification request failed", exc_info=True)
        return False
    return bool(data.get("success"))
