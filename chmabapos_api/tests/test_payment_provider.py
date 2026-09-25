from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.payments.base import PaymentProviderError, ProviderPayment
from app.services.payments.chamabapay import ChmabaPayClient
from app.services.payments.registry import payment_provider_for

pytestmark = pytest.mark.asyncio


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


async def test_chamabapay_mock_list_stores_has_internal() -> None:
    client = ChmabaPayClient(mode="mock")
    stores = await client.list_stores()
    assert any(store.get("is_internal") for store in stores)


async def test_mask_secret() -> None:
    from app.api.admin import _mask_secret

    assert _mask_secret(None) is None
    assert _mask_secret("short") == "*****"
    assert _mask_secret("ck_live_1234567890abcdef") == "ck_live_...cdef"
    assert _mask_secret("whsec_abcdefghijklmnop") == "whsec_...mnop"
    assert _mask_secret("abcdefghijklmnop") == "abcdef...mnop"


async def test_chamabapay_live_requires_api_key() -> None:
    client = ChmabaPayClient(mode="live", api_key=None)
    with pytest.raises(PaymentProviderError):
        await client.create_payment(Decimal("1.00"), "ref", store_ref="st_x")


async def test_chamabapay_live_requires_store_ref() -> None:
    client = ChmabaPayClient(mode="live", api_key="ck_live_test")
    with pytest.raises(PaymentProviderError):
        await client.create_payment(Decimal("1.00"), "ref")


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


async def test_sync_aba_payway_link_unchanged_skips_provider(monkeypatch) -> None:
    from app.api import v1

    fake = _EnsureStoreProvider()

    async def fake_provider(_db):
        return fake

    monkeypatch.setattr(v1, "payment_provider_for", fake_provider)
    merchant = _SimpleMerchant()
    merchant.aba_payway_link = "https://link.payway.com.kh/ABAPAYpe518710Y"
    merchant.aba_payway_status = "active"
    merchant.chamabapay_store_id = "st_existing"
    status = await v1.sync_aba_payway_link(
        None,  # type: ignore[arg-type]
        merchant,
        merchant.aba_payway_link,
        external_id="store:abc",
        merchant_name="Main",
    )
    assert status == "active"
    assert fake.calls == []


async def test_sync_aba_payway_link_force_revalidates_unchanged(monkeypatch) -> None:
    from app.api import v1

    fake = _EnsureStoreProvider()

    async def fake_provider(_db):
        return fake

    monkeypatch.setattr(v1, "payment_provider_for", fake_provider)
    merchant = _SimpleMerchant()
    merchant.aba_payway_link = "https://link.payway.com.kh/ABAPAYpe518710Y"
    merchant.aba_payway_status = "active"
    merchant.chamabapay_store_id = "st_existing"
    status = await v1.sync_aba_payway_link(
        None,  # type: ignore[arg-type]
        merchant,
        merchant.aba_payway_link,
        external_id="store:abc",
        merchant_name="Main",
        force=True,
    )
    assert status == "active"
    assert len(fake.calls) == 1
    assert merchant.chamabapay_store_id == "st_test"


async def test_aba_payway_status_message() -> None:
    from app.api import v1

    assert v1.aba_payway_status_message("active") == (True, "Connection verified. KHQR checkout is live.")
    assert v1.aba_payway_status_message("pending")[0] is True
    assert v1.aba_payway_status_message("error")[0] is False
    assert v1.aba_payway_status_message("none")[0] is False


class _FakePayment:
    def __init__(self) -> None:
        self.status = "pending"
        self.external_id = "pay_1"


class _FakeOrder:
    def __init__(self) -> None:
        self.id = "o1"
        self.status = "payment_pending"
        self.payments = [_FakePayment()]


class _FakeDb:
    def __init__(self) -> None:
        self.committed = False

    async def commit(self) -> None:
        self.committed = True


class _ReconcileProvider:
    name = "chamabapay"

    def __init__(self, status: str) -> None:
        self._status = status

    async def reconcile(self, payment_id: str):
        return {"status": self._status}


async def test_reconcile_completes_order_when_paid(monkeypatch) -> None:
    from app.api import v1

    async def fake_provider(_db):
        return _ReconcileProvider("PAID")

    calls = {"complete": 0}

    async def fake_complete(_db, order_id):
        calls["complete"] += 1

    monkeypatch.setattr(v1, "active_payment_provider", fake_provider)
    monkeypatch.setattr(v1, "complete_order", fake_complete)
    db = _FakeDb()
    order = _FakeOrder()
    paid = await v1.reconcile_pending_order_payment(db, order)  # type: ignore[arg-type]
    assert paid is True
    assert order.payments[0].status == "paid"
    assert calls["complete"] == 1
    assert db.committed is True


async def test_reconcile_marks_failed(monkeypatch) -> None:
    from app.api import v1

    async def fake_provider(_db):
        return _ReconcileProvider("FAILED")

    monkeypatch.setattr(v1, "active_payment_provider", fake_provider)
    db = _FakeDb()
    order = _FakeOrder()
    paid = await v1.reconcile_pending_order_payment(db, order)  # type: ignore[arg-type]
    assert paid is False
    assert order.payments[0].status == "failed"
    assert db.committed is True


async def test_reconcile_noop_when_provider_lacks_reconcile(monkeypatch) -> None:
    from app.api import v1

    class _Legacy:
        name = "cutluy"

    async def fake_provider(_db):
        return _Legacy()

    monkeypatch.setattr(v1, "active_payment_provider", fake_provider)
    db = _FakeDb()
    order = _FakeOrder()
    paid = await v1.reconcile_pending_order_payment(db, order)  # type: ignore[arg-type]
    assert paid is False
    assert order.payments[0].status == "pending"
    assert db.committed is False


async def test_reconcile_noop_when_already_paid(monkeypatch) -> None:
    from app.api import v1

    db = _FakeDb()
    order = _FakeOrder()
    order.status = "paid"
    paid = await v1.reconcile_pending_order_payment(db, order)  # type: ignore[arg-type]
    assert paid is False
    assert db.committed is False


async def test_chamabapay_webhook_event_tolerates_extra_fields() -> None:
    from app.schemas import ChmabaPayWebhookEvent

    event = ChmabaPayWebhookEvent.model_validate(
        {
            "id": "evt_1",
            "type": "payment.completed",
            "created": "2026-09-25T00:00:00Z",
            "data": {
                "payment": {
                    "id": "pay_1",
                    "status": "paid",
                    "amount": "4.95",
                    "currency": "USD",
                    "reference_id": "CHM-1",
                    "approved_at": None,
                    "unknown_payment_field": 1,
                },
                "store": {"id": "st_1"},
                "merchant": {"external_id": "store:abc"},
                "financial": {"fee_cents": 0},
            },
            "unknown_event_field": "ignored",
        }
    )
    assert event.data.payment.id == "pay_1"
    assert event.data.payment.status == "paid"
    assert event.data.payment.amount == Decimal("4.95")
