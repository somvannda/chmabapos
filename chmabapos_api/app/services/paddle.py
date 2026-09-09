"""Minimal Paddle Billing client for one-time prepaid plan checkouts.

Chmaba plans stay **prepaid periods**: a customer pays once for a fixed period
and there is no card on file and no auto-rebill. Paddle is used purely as a
card/alternative-payment checkout channel:

* the API creates a one-time *transaction* for an exact catalog price id;
* Paddle hosts the checkout (taxes, payment methods, receipt) as merchant of
  record;
* ``transaction.completed`` webhooks fulfil the existing prepaid subscription.

Only the server-side Transactions API is used; the client token / Paddle.js
overlay is intentionally avoided so the "pay exactly {amount}" guarantee stays
server-side.

Modes
-----
* ``mock``  — no network, returns a fake checkout URL (dev/tests, mirrors the
  CutLuy mock flow).
* ``sandbox`` / ``live`` — real Paddle Billing; ``sandbox`` hits
  ``sandbox-api.paddle.com``, ``live`` hits ``api.paddle.com``. A Paddle API
  key is required in both cases.
"""
from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal

import httpx

from app.config import settings

PaddleMode = Literal["mock", "sandbox", "live"]

_API_BASES = {
    "sandbox": "https://sandbox-api.paddle.com",
    "live": "https://api.paddle.com",
}


class PaddleError(RuntimeError):
    """Provider request failed or provider configuration is incomplete."""


def _api_base(mode: str, api_url: str | None) -> str:
    if api_url:
        return api_url.rstrip("/")
    return _API_BASES.get(mode, _API_BASES["sandbox"])


class PaddleClient:
    def __init__(
        self,
        *,
        mode: str | None = None,
        api_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.mode: str = mode or settings.paddle_mode
        self.api_url = _api_base(self.mode, api_url)
        self.api_key = settings.paddle_api_key if api_key is None else api_key

    async def create_transaction(
        self,
        *,
        price_id: str,
        reference_id: str,
        metadata: dict[str, Any] | None = None,
        currency_code: str = "USD",
    ) -> dict[str, Any]:
        """Create a one-time transaction and return its hosted checkout URL.

        The returned dict is normalised so callers treat mock and live the
        same: ``id``, ``status``, ``amount``, ``currency``, ``reference_id``,
        ``checkout_url``, ``metadata``.
        """
        if self.mode == "mock":
            payment_id = f"mock_paddle_{uuid.uuid4().hex}"
            return {
                "id": payment_id,
                "status": "pending",
                "amount": "0.00",
                "currency": currency_code,
                "reference_id": reference_id,
                "checkout_url": f"http://localhost:8000/api/v1/mock/paddle/{payment_id}/complete",
                "metadata": metadata,
            }
        if not self.api_key:
            raise PaddleError("Paddle API key is required when Paddle mode is not mock")
        payload: dict[str, Any] = {
            "items": [{"price_id": price_id, "quantity": 1}],
            "currency_code": currency_code,
        }
        if metadata:
            payload["custom_data"] = metadata
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": f"chmaba-{reference_id}",
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(f"{self.api_url}/transactions", headers=headers, json=payload)
                response.raise_for_status()
                data = response.json().get("data", {})
        except (httpx.HTTPError, ValueError) as exc:
            raise PaddleError("Paddle checkout request failed") from exc
        checkout = data.get("checkout") or {}
        return {
            "id": data.get("id") or f"paddle_{uuid.uuid4().hex}",
            "status": data.get("status") or "pending",
            "amount": "0.00",
            "currency": data.get("currency_code") or currency_code,
            "reference_id": reference_id,
            "checkout_url": checkout.get("url"),
            "metadata": metadata,
        }

    async def create_portal_session(self, *, customer_id: str, subscription_id: str) -> str | None:
        """Mint a Paddle customer portal session URL for self-service.

        Returns ``None`` in mock mode (no Paddle customer exists). The URL is
        one-time use and short-lived; callers must mint a fresh session per
        click and return only the overview URL.
        """
        if self.mode == "mock":
            return None
        if not self.api_key:
            raise PaddleError("Paddle API key is required when Paddle mode is not mock")
        payload = {"customer_id": customer_id, "subscription_ids": [subscription_id]}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(f"{self.api_url}/customer-portal-sessions", headers=headers, json=payload)
                response.raise_for_status()
                data = response.json().get("data", {})
        except (httpx.HTTPError, ValueError) as exc:
            raise PaddleError("Paddle customer portal request failed") from exc
        urls = data.get("urls") or {}
        general = urls.get("general") or {}
        return general.get("overview")

    async def get_customer(self, customer_id: str) -> dict[str, Any]:
        """Fetch a customer record (used to bridge an unknown webhook customer
        to a Chmaba workspace by email). Returns an empty dict when unknown."""
        if self.mode == "mock":
            return {}
        if not self.api_key:
            raise PaddleError("Paddle API key is required when Paddle mode is not mock")
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(f"{self.api_url}/customers/{customer_id}", headers=headers)
                response.raise_for_status()
                data = response.json().get("data", {})
        except (httpx.HTTPError, ValueError) as exc:
            raise PaddleError("Paddle customer lookup failed") from exc
        return data or {}


def paddle_signature_is_valid(raw_body: bytes, signature: str, secret: str | None, mode: str, environment: str) -> bool:
    """Verify a Paddle ``Paddle-Signature`` header (``ts=...;h1=...``).

    Signed payload is ``"{timestamp}:{raw_body}"`` HMAC-SHA256 with the
    notification destination secret. In mock mode with no secret configured the
    check is bypassed outside production (mirrors the CutLuy behaviour).
    """
    if not secret:
        return mode == "mock" and environment != "production"
    pieces = {part.split("=", 1)[0]: part.split("=", 1)[1] for part in signature.split(";") if "=" in part}
    timestamp = pieces.get("ts")
    received = pieces.get("h1")
    if not timestamp or not received:
        return False
    try:
        fresh = abs(datetime.now(timezone.utc).timestamp() - int(timestamp)) < 300
    except ValueError:
        return False
    payload = f"{timestamp}:".encode() + raw_body
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return fresh and hmac.compare_digest(expected, received)
