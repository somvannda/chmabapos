from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import httpx

from app.config import settings


class CutLuyError(RuntimeError):
    """Provider request failed or provider configuration is incomplete."""


class CutLuyClient:
    def __init__(self, *, mode: str | None = None, api_url: str | None = None, api_key: str | None = None) -> None:
        self.mode = mode or settings.cutluy_mode
        self.api_url = (api_url or settings.cutluy_api_url).rstrip("/")
        self.api_key = settings.cutluy_api_key if api_key is None else api_key

    async def create_payment(self, amount: Decimal, reference_id: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.mode == "mock":
            payment_id = f"mock_{uuid.uuid4().hex}"
            return {
                "id": payment_id,
                "status": "pending",
                "amount": f"{amount:.2f}",
                "currency": "USD",
                "reference_id": reference_id,
                "qr_string": f"chmaba-mock-khqr-{payment_id}",
                "checkout_url": f"http://localhost:8000/api/v1/mock/cutluy/{payment_id}",
                "metadata": metadata,
            }
        if not self.api_key:
            raise CutLuyError("CutLuy API key is required when CutLuy mode is live")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": reference_id,
        }
        payload = {"amount": float(amount), "reference_id": reference_id}
        if metadata:
            payload["metadata"] = metadata
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(f"{self.api_url}/payments", headers=headers, json=payload)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise CutLuyError("CutLuy payment request failed") from exc
