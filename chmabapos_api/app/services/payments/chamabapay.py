from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import httpx

from app.config import settings
from app.services.payments.base import PaymentProviderError, ProviderPayment

API_VERSION = "v1"


class ChmabaPayClient:
    """Adapter for the ChmabaPay payments API (https://pay.chmaba.com).

    ``mock`` mode is a local fake used by development and tests because
    ChmabaPay has no sandbox; only ``live`` calls the real API. One API key
    authenticates every store on the account. Merchant funds settle to each
    store's own ABA PayWay link; plan fees use the platform's internal store.
    """

    name = "chamabapay"

    def __init__(self, *, mode: str | None = None, api_url: str | None = None, api_key: str | None = None) -> None:
        self.mode = mode or settings.chamabapay_mode
        self.api_url = (api_url or settings.chamabapay_api_url).rstrip("/")
        self.api_key = settings.chamabapay_api_key if api_key is None else api_key

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise PaymentProviderError("ChmabaPay API key is required when ChmabaPay mode is live")
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def create_payment(
        self,
        amount: Decimal,
        reference_id: str,
        *,
        idempotency_key: str | None = None,
        store_ref: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProviderPayment:
        amount_str = str(Decimal(amount).quantize(Decimal("0.01")))
        if self.mode == "mock":
            payment_id = f"mock_{uuid.uuid4().hex}"
            return ProviderPayment(
                provider=self.name,
                id=payment_id,
                status="pending",
                amount=Decimal(amount_str),
                currency="USD",
                reference_id=reference_id,
                qr_string=f"chamaba-mock-khqr-{payment_id}",
                checkout_url=f"http://localhost:8000/api/v1/mock/chamabapay/{payment_id}",
                metadata=metadata or {},
            )
        if not store_ref:
            raise PaymentProviderError("ChmabaPay requires a store id (or merchant external id) to create a payment")
        body: dict[str, Any] = {
            "amount": amount_str,
            "reference_id": reference_id,
            "idempotency_key": idempotency_key or reference_id,
            "store": store_ref,
        }
        if metadata:
            body["metadata"] = metadata
        data = await self._request("POST", f"{self.api_url}/{API_VERSION}/payments", json=body)
        return self._to_payment(data, amount=Decimal(amount_str), reference_id=reference_id, metadata=metadata)

    async def ensure_store(
        self,
        external_id: str,
        raw_link: str,
        *,
        merchant_account_id: str | None = None,
        merchant_name: str | None = None,
    ) -> dict[str, Any]:
        """Register (or attach a link to) the ChmabaPay store for a merchant.

        Returns the store payload including its ``st_…`` id and ``status``.
        Re-saving the same link is idempotent on ChmabaPay's side.
        """
        if self.mode == "mock":
            return {"id": f"st_mock_{uuid.uuid4().hex[:12]}", "status": "active", "external_id": external_id}
        link: dict[str, Any] = {"raw_link": raw_link}
        if merchant_account_id:
            link["merchant_account_id"] = merchant_account_id
        if merchant_name:
            link["merchant_name"] = merchant_name
        return await self._request(
            "POST",
            f"{self.api_url}/{API_VERSION}/stores",
            json={"name": merchant_name or external_id, "external_id": external_id, "link": link},
        )

    async def reconcile(self, payment_public_id: str) -> dict[str, Any]:
        """Authoritative status for a payment (covers late/expired settlement)."""
        if self.mode == "mock":
            return {"status": "PENDING", "source": None}
        return await self._request("GET", f"{self.api_url}/{API_VERSION}/transactions/check-status/{payment_public_id}")

    async def list_stores(self) -> list[dict[str, Any]]:
        """List every store on the account (used to find the platform store)."""
        if self.mode == "mock":
            return [{"id": "st_mock_platform", "is_internal": True, "status": "active"}]
        data = await self._request("GET", f"{self.api_url}/{API_VERSION}/stores")
        if isinstance(data, dict):
            rows = data.get("data") or []
        else:
            rows = data if isinstance(data, list) else []
        return [row for row in rows if isinstance(row, dict)]

    async def _request(self, method: str, url: str, *, json: Any = None) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.request(method, url, headers=self._headers(), json=json)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise PaymentProviderError("ChmabaPay request failed") from exc

    def _to_payment(
        self,
        data: dict[str, Any],
        *,
        amount: Decimal,
        reference_id: str,
        metadata: dict[str, Any] | None,
    ) -> ProviderPayment:
        return ProviderPayment(
            provider=self.name,
            id=str(data.get("id", "")),
            status=data.get("status", "pending"),
            amount=Decimal(str(data.get("amount", amount))),
            currency=data.get("currency", "USD"),
            reference_id=data.get("reference_id", reference_id),
            qr_string=data.get("qr_string"),
            checkout_url=data.get("checkout_url"),
            expires_at=data.get("expires_at"),
            metadata=metadata or {},
        )
