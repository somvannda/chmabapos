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

    async def ensure_store(self, external_id, raw_link, *, merchant_account_id=None, merchant_name=None, store_id=None):
        self.calls.append((external_id, raw_link, merchant_account_id, merchant_name, store_id))
        return {"id": store_id or "st_test", "status": "active", "external_id": external_id}


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
    assert merchant.chamabapay_store_id == "st_existing"


async def test_sync_aba_payway_link_force_reuses_existing_store_id(monkeypatch) -> None:
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
    assert fake.calls[-1][4] == "st_existing"
    assert merchant.chamabapay_store_id == "st_existing"


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


class _RecordingClient(ChmabaPayClient):
    def __init__(self, responses: list[dict]) -> None:
        super().__init__(mode="live", api_key="ck_live_test")
        self.requests: list[tuple[str, str, dict | None]] = []
        self._responses = responses

    async def _request(self, method, url, *, json=None):
        self.requests.append((method, url, json))
        return self._responses.pop(0)


async def test_ensure_store_updates_link_when_store_id_known() -> None:
    client = _RecordingClient([{"id": "st_existing", "status": "active", "external_id": "store:abc"}])
    result = await client.ensure_store(
        "store:abc",
        "https://link.payway.com.kh/ABAPAYpe518710Y",
        merchant_account_id="ABAPAYpe518710Y",
        merchant_name="Main",
        store_id="st_existing",
    )
    assert result["id"] == "st_existing"
    assert [method for method, _, _ in client.requests] == ["PUT"]
    assert client.requests[0][1].endswith("/v1/stores/st_existing/link")
    assert client.requests[0][2]["merchant_account_id"] == "ABAPAYpe518710Y"


async def test_ensure_store_updates_existing_external_id_instead_of_duplicating() -> None:
    client = _RecordingClient([
        {"data": [{"id": "st_found", "external_id": "store:abc", "status": "active"}]},
        {"id": "st_found", "status": "active", "external_id": "store:abc"},
    ])
    result = await client.ensure_store(
        "store:abc",
        "https://link.payway.com.kh/ABAPAYpe518710Y",
        merchant_account_id="ABAPAYpe518710Y",
    )
    assert result["id"] == "st_found"
    assert [method for method, _, _ in client.requests] == ["GET", "PUT"]
    assert client.requests[1][1].endswith("/v1/stores/st_found/link")
    assert not any(method == "POST" for method, _, _ in client.requests)


async def test_ensure_store_creates_when_external_id_absent() -> None:
    client = _RecordingClient([
        {"data": []},
        {"id": "st_new", "status": "active", "external_id": "store:new"},
    ])
    result = await client.ensure_store(
        "store:new",
        "https://link.payway.com.kh/ABAPAYpe518710Y",
        merchant_account_id="ABAPAYpe518710Y",
        merchant_name="New",
    )
    assert result["id"] == "st_new"
    assert [method for method, _, _ in client.requests] == ["GET", "POST"]
    assert client.requests[1][2]["external_id"] == "store:new"


async def test_chamabapay_mock_ensure_store_reuses_given_id() -> None:
    client = ChmabaPayClient(mode="mock")
    store = await client.ensure_store("store:abc", "https://link.payway.com.kh/ABAPAYpe518710Y", store_id="st_keep")
    assert store["id"] == "st_keep"


class _FakeHttpResponse:
    def __init__(self, payload, status_code: int = 400) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


async def test_error_message_surfaces_provider_detail() -> None:
    assert (
        ChmabaPayClient._error_message(_FakeHttpResponse({"detail": "payway_link_invalid"}))
        == "ChmabaPay rejected the request (payway_link_invalid)"
    )
    assert ChmabaPayClient._error_message(_FakeHttpResponse({"detail": [{"loc": ["body"]}]})) == "ChmabaPay request failed (400)"
    assert ChmabaPayClient._error_message(_FakeHttpResponse(ValueError("no json"))) == "ChmabaPay request failed (400)"


async def test_create_payment_requests_hosted_qr() -> None:
    client = _RecordingClient([{"id": "pay_1", "status": "pending", "amount": "0.01", "currency": "USD", "reference_id": "ref", "qr_string": "qr", "checkout_url": None}])
    payment = await client.create_payment(Decimal("0.01"), "ref", idempotency_key="ref", store_ref="st_x")
    assert payment.id == "pay_1"
    method, url, body = client.requests[0]
    assert method == "POST"
    assert url.endswith("/v1/payments")
    assert body["hosted_qr"] is True
    assert body["store"] == "st_x"
