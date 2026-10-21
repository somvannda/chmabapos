"""Terminal order-payment states must not regress after a sale is paid.

ChmabaPay can deliver events late or out of order. A paid sale must stay paid:
an ``expired``/``failed``/``superseded`` event that arrives afterwards must not
void the order, release its stock or overwrite the paid payment row.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


def event(payment_id: str, status: str, amount: str) -> dict:
    return {
        "id": f"evt_{uuid.uuid4().hex}",
        "type": "payment.test",
        "created": datetime.now(timezone.utc).isoformat(),
        "data": {
            "payment": {
                "id": payment_id,
                "status": status,
                "amount": amount,
                "currency": "USD",
                "reference_id": "terminal-guard",
                "approved_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    }


@pytest.mark.asyncio
async def test_late_regressive_event_does_not_void_a_paid_order(monkeypatch) -> None:
    monkeypatch.setattr("app.api.v1.signature_is_valid", lambda *args, **kwargs: True)
    email = None
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Terminal Guard Co", "Main", plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            linked = await client.patch(
                "/api/v1/company",
                headers=headers,
                json={"aba_payway_link": "https://link.payway.com.kh/ABAPAYpe518710Y"},
            )
            assert linked.status_code == 200, linked.text

            product = await client.post(
                "/api/v1/products",
                headers=store_headers,
                json={"name": "Guard Latte", "sku": f"TG-{uuid.uuid4().hex[:8]}", "price": "4.50", "opening_stock": 5},
            )
            assert product.status_code == 201, product.text
            product_id = product.json()["id"]
            order = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={"items": [{"product_id": product_id, "quantity": 1}], "payment_method": "khqr"},
            )
            assert order.status_code == 201, order.text
            assert order.json()["status"] == "payment_pending"
            external_id = order.json()["payments"][0]["external_id"]
            amount = order.json()["total"]
            order_id = order.json()["id"]

            paid = await client.post("/api/v1/webhooks/chamabapay", json=event(external_id, "paid", amount))
            assert paid.status_code == 200, paid.text
            after_paid = await client.get(f"/api/v1/orders/{order_id}", headers=store_headers)
            assert after_paid.status_code == 200
            assert after_paid.json()["status"] == "paid"

            for late_status in ("expired", "failed", "superseded"):
                response = await client.post(
                    "/api/v1/webhooks/chamabapay",
                    json=event(external_id, late_status, amount),
                )
                assert response.status_code == 200, response.text
                current = await client.get(f"/api/v1/orders/{order_id}", headers=store_headers)
                assert current.status_code == 200
                assert current.json()["status"] == "paid", late_status
                assert any(payment["status"] == "paid" for payment in current.json()["payments"]), late_status

            refunded = await client.post(
                f"/api/v1/orders/{order_id}/refund",
                headers=store_headers,
                json={"method": "cash", "items": [{"product_id": product_id, "quantity": 1}]},
            )
            assert refunded.status_code == 201, refunded.text
            assert (await client.get(f"/api/v1/orders/{order_id}", headers=store_headers)).json()["status"] == "refunded"

            # A duplicate "paid" must not revive a refunded sale.
            replay = await client.post("/api/v1/webhooks/chamabapay", json=event(external_id, "paid", amount))
            assert replay.status_code == 200, replay.text
            terminal = await client.get(f"/api/v1/orders/{order_id}", headers=store_headers)
            assert terminal.status_code == 200
            assert terminal.json()["status"] == "refunded"
    finally:
        await cleanup_company(company_id, [email] if email else [])
