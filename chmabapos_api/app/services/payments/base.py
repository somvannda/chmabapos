from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable


class PaymentProviderError(RuntimeError):
    """Provider request failed or provider configuration is incomplete."""


@dataclass
class ProviderPayment:
    """Normalized payment returned by any provider adapter.

    Call sites must depend on this shape, never on a provider's raw payload, so
    ingestion stays provider-agnostic (see docs/billing-improvement-plan.md
    §3.2.1).
    """

    provider: str
    id: str
    status: str
    amount: Decimal
    currency: str
    reference_id: str | None = None
    qr_string: str | None = None
    checkout_url: str | None = None
    expires_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class PaymentProvider(Protocol):
    name: str

    async def create_payment(
        self,
        amount: Decimal,
        reference_id: str,
        *,
        idempotency_key: str | None = None,
        store_ref: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProviderPayment: ...
