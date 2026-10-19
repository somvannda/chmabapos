"""The currency a payment is minted in.

ChmabaPay settles one currency per ABA PayWay link, and the riel has no subunit:
a KHR amount is a whole number, and a fractional one is refused by the provider
(``khr_amount_must_be_whole``) rather than rounded for us. Two things therefore
have to be right on our side - the rounding, and the fact that the request
actually carries the currency. A provider call that dropped the field would look
like riel support while charging dollars.
"""
from decimal import Decimal

import pytest

from app.services.payments.chamabapay import ChmabaPayClient, payment_body, quantize_amount


def test_usd_keeps_two_decimals() -> None:
    assert str(quantize_amount(Decimal("1.5"), "USD")) == "1.50"
    assert str(quantize_amount(Decimal("1.005"), "USD")) == "1.01"
    assert str(quantize_amount(Decimal("3"), "USD")) == "3.00"


def test_khr_is_whole_riel() -> None:
    assert str(quantize_amount(Decimal("5000"), "KHR")) == "5000"
    # A fractional riel cannot be charged, so it rounds instead of failing at the edge.
    assert str(quantize_amount(Decimal("5000.50"), "KHR")) == "5001"
    assert str(quantize_amount(Decimal("5000.49"), "KHR")) == "5000"


def test_the_body_carries_the_currency() -> None:
    body = payment_body(amount_str="5001", reference_id="order-1", idempotency_key=None, store_ref="st_1", currency="khr")
    assert body["currency"] == "KHR", "the request must name the currency"
    assert body["amount"] == "5001"
    assert body["store"] == "st_1"
    # Falls back to the reference, which is what makes a retry idempotent.
    assert body["idempotency_key"] == "order-1"
    assert body["hosted_qr"] is True
    # Omitted entirely when there is none, rather than sent as a null.
    assert "metadata" not in body


def test_the_body_includes_metadata_and_respects_an_explicit_key() -> None:
    body = payment_body(amount_str="1.50", reference_id="r", idempotency_key="k", store_ref="st", currency="USD", metadata={"type": "order"})
    assert body["metadata"] == {"type": "order"}
    assert body["idempotency_key"] == "k"
    assert body["currency"] == "USD"


@pytest.mark.asyncio
async def test_mock_mode_mints_the_requested_currency() -> None:
    """Development and tests take the same currency path as live."""
    client = ChmabaPayClient(mode="mock")
    payment = await client.create_payment(Decimal("5000.5"), "order-2", store_ref="st_1", currency="KHR")
    assert payment.currency == "KHR"
    assert payment.amount == Decimal("5001")


@pytest.mark.asyncio
async def test_mock_mode_defaults_to_usd() -> None:
    client = ChmabaPayClient(mode="mock")
    payment = await client.create_payment(Decimal("1.5"), "order-3", store_ref="st_1")
    assert payment.currency == "USD"
    assert payment.amount == Decimal("1.50")
