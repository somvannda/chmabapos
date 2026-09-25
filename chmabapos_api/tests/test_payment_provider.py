from __future__ import annotations

from decimal import Decimal

import pytest

from app.config import settings
from app.services.cutluy import CutLuyError
from app.services.payments.base import PaymentProviderError, ProviderPayment
from app.services.payments.chamabapay import ChmabaPayClient
from app.services.payments.cutluy import CutLuyProvider
from app.services.payments.registry import payment_provider_for


class _FakeCutLuyClient:
    async def create_payment(self, amount, reference, metadata=None):
        return {
            "id": "cl_123",
            "status": "pending",
            "amount": f"{Decimal(amount):.2f}",
            "currency": "USD",
            "reference_id": reference,
            "qr_string": "cutluy-qr",
            "checkout_url": "https://cutluy.com/pay/cl_123",
            "metadata": metadata,
        }


class _FailingCutLuyClient:
    async def create_payment(self, amount, reference, metadata=None):
        raise CutLuyError("boom")


async def test_chamabapay_mock_create_payment_returns_normalized_qr() -> None:
    client = ChmabaPayClient(mode="mock")
    payment = await client.create_payment(Decimal("4.95"), "CHM-000001", metadata={"type": "pos_order"})
    assert isinstance(payment, ProviderPayment)
    assert payment.provider == "chamabapay"
    assert payment.status == "pending"
    assert payment.amount == Decimal("4.95")
    assert payment.reference_id == "CHM-000001"
    assert payment.qr_string and payment.checkout_url
    assert payment.metadata == {"type": "pos_order"}


async def test_chamabapay_mock_ensure_store_activates() -> None:
    client = ChmabaPayClient(mode="mock")
    store = await client.ensure_store("store-abc", "https://link.payway.com.kh/ABAPAYpe518710Y", merchant_name="Main")
    assert store["id"].startswith("st_")
    assert store["status"] == "active"


async def test_chamabapay_live_requires_api_key() -> None:
    client = ChmabaPayClient(mode="live", api_key=None)
    with pytest.raises(PaymentProviderError):
        await client.create_payment(Decimal("1.00"), "ref", store_ref="st_x")


async def test_chamabapay_live_requires_store_ref() -> None:
    client = ChmabaPayClient(mode="live", api_key="ck_live_test")
    with pytest.raises(PaymentProviderError):
        await client.create_payment(Decimal("1.00"), "ref")


async def test_cutluy_provider_normalizes_legacy_payload() -> None:
    provider = CutLuyProvider(_FakeCutLuyClient())
    payment = await provider.create_payment(Decimal("10.00"), "CHM-9")
    assert payment.provider == "cutluy"
    assert payment.id == "cl_123"
    assert payment.qr_string == "cutluy-qr"


async def test_cutluy_provider_wraps_errors() -> None:
    provider = CutLuyProvider(_FailingCutLuyClient())
    with pytest.raises(PaymentProviderError):
        await provider.create_payment(Decimal("10.00"), "CHM-9")


async def test_registry_defaults_to_cutluy(monkeypatch) -> None:
    async def fake_settings(_db):
        return {}

    monkeypatch.setattr("app.services.payments.registry.load_payment_settings", fake_settings)
    monkeypatch.setattr(settings, "payments_provider", "cutluy")
    provider = await payment_provider_for(db=None)  # type: ignore[arg-type]
    assert provider.name == "cutluy"


async def test_registry_selects_chamabapay(monkeypatch) -> None:
    async def fake_settings(_db):
        return {"payments_provider": "chamabapay", "chamabapay_mode": "mock"}

    monkeypatch.setattr("app.services.payments.registry.load_payment_settings", fake_settings)
    provider = await payment_provider_for(db=None)  # type: ignore[arg-type]
    assert provider.name == "chamabapay"
