from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.services.cutluy import CutLuyClient, CutLuyError
from app.services.payments.base import PaymentProviderError, ProviderPayment


class CutLuyProvider:
    """Legacy adapter that normalizes ``CutLuyClient`` into the provider protocol.

    Kept until the final migration phase so call sites can move to
    ``payment_provider_for`` without a behaviour change.
    """

    name = "cutluy"

    def __init__(self, client: CutLuyClient) -> None:
        self._client = client

    async def create_payment(
        self,
        amount: Decimal,
        reference_id: str,
        *,
        idempotency_key: str | None = None,
        store_ref: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProviderPayment:
        try:
            data = await self._client.create_payment(amount, reference_id, metadata)
        except CutLuyError as exc:
            raise PaymentProviderError(str(exc)) from exc
        return ProviderPayment(
            provider=self.name,
            id=str(data.get("id", "")),
            status=data.get("status", "pending"),
            amount=Decimal(str(data.get("amount", amount))),
            currency=data.get("currency", "USD"),
            reference_id=data.get("reference_id", reference_id),
            qr_string=data.get("qr_string"),
            checkout_url=data.get("checkout_url"),
            metadata=data.get("metadata") or {},
        )
