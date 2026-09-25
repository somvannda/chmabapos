from __future__ import annotations

from decimal import Decimal

import pytest

from app.config import settings
from app.services.cutluy import CutLuyError
from app.services.payments.base import PaymentProviderError, ProviderPayment
from app.services.payments.chamabapay import ChmabaPayClient
from app.services.payments.cutluy import CutLuyProvider
from app.services.payments.registry import payment_provider_for

pytestmark = pytest.mark.asyncio


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


async def test_active_payment_provider_selects_chamabapay(monkeypatch) -> None:
    from app.api import v1

    async def fake_settings(_db):
        return {"payments_provider": "chamabapay", "chamabapay_mode": "mock"}

    monkeypatch.setattr(v1, "load_payment_settings", fake_settings)
    provider = await v1.active_payment_provider(db=None)  # type: ignore[arg-type]
    assert provider.name == "chamabapay"


async def test_active_payment_provider_defaults_to_cutluy(monkeypatch) -> None:
    from app.api import v1

    async def fake_settings(_db):
        return {}

    async def fake_cutluy_client(_db):
        return _FakeCutLuyClient()

    monkeypatch.setattr(v1, "load_payment_settings", fake_settings)
    monkeypatch.setattr(v1, "cutluy_client_for", fake_cutluy_client)
    monkeypatch.setattr(settings, "payments_provider", "cutluy")
    provider = await v1.active_payment_provider(db=None)  # type: ignore[arg-type]
    assert provider.name == "cutluy"


class _SimpleMerchant:
    def __init__(self) -> None:
        self.aba_payway_link: str | None = None
        self.aba_payway_status = "none"
        self.chamabapay_store_id: str | None = None


class _EnsureStoreProvider:
    name = "chamabapay"

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def ensure_store(self, external_id, raw_link, *, merchant_account_id=None, merchant_name=None):
        self.calls.append((external_id, raw_link, merchant_account_id, merchant_name))
        return {"id": "st_test", "status": "active", "external_id": external_id}


async def test_sync_aba_payway_link_activates_via_chamabapay(monkeypatch) -> None:
    from app.api import v1

    fake = _EnsureStoreProvider()

    async def fake_provider(_db):
        return fake

    monkeypatch.setattr(v1, "payment_provider_for", fake_provider)
    merchant = _SimpleMerchant()
    status = await v1.sync_aba_payway_link(
        None,  # type: ignore[arg-type]
        merchant,
        "https://link.payway.com.kh/ABAPAYpe518710Y",
        external_id="store:abc",
        merchant_name="Main",
    )
    assert status == "active"
    assert merchant.aba_payway_status == "active"
    assert merchant.chamabapay_store_id == "st_test"
    assert fake.calls[0][2] == "ABAPAYpe518710Y"


async def test_sync_aba_payway_link_legacy_provider_stays_pending(monkeypatch) -> None:
    from app.api import v1

    class _Legacy:
        name = "cutluy"

    async def fake_provider(_db):
        return _Legacy()

    monkeypatch.setattr(v1, "payment_provider_for", fake_provider)
    merchant = _SimpleMerchant()
    status = await v1.sync_aba_payway_link(
        None,  # type: ignore[arg-type]
        merchant,
        "https://link.payway.com.kh/ABC",
        external_id="store:abc",
        merchant_name="Main",
    )
    assert status == "pending"
    assert merchant.chamabapay_store_id is None


async def test_sync_aba_payway_link_error_on_provider_failure(monkeypatch) -> None:
    from app.api import v1

    class _Failing:
        name = "chamabapay"

        async def ensure_store(self, *args, **kwargs):
            raise PaymentProviderError("bad link")

    async def fake_provider(_db):
        return _Failing()

    monkeypatch.setattr(v1, "payment_provider_for", fake_provider)
    merchant = _SimpleMerchant()
    status = await v1.sync_aba_payway_link(
        None,  # type: ignore[arg-type]
        merchant,
        "https://link.payway.com.kh/BAD",
        external_id="store:abc",
        merchant_name="Main",
    )
    assert status == "error"
    assert merchant.chamabapay_store_id is None


async def test_sync_aba_payway_link_clears_on_empty(monkeypatch) -> None:
    from app.api import v1

    merchant = _SimpleMerchant()
    merchant.aba_payway_link = "https://link.payway.com.kh/OLD"
    merchant.aba_payway_status = "active"
    merchant.chamabapay_store_id = "st_old"
    status = await v1.sync_aba_payway_link(
        None,  # type: ignore[arg-type]
        merchant,
        "",
        external_id="store:abc",
        merchant_name="Main",
    )
    assert status == "none"
    assert merchant.aba_payway_link is None
    assert merchant.chamabapay_store_id is None
