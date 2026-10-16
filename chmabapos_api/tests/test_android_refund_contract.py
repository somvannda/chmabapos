"""The body the Android till sends to refund an order is one the API acts on.

`POST /orders/{id}/refund` matches each returned line to the order's line by
`(product_id, variant_id)` (v1.py:7113). A line that arrives without its variant matches nothing, so
it is refunded as *nothing* while the rest of the refund goes through - and the endpoint still
answers 201, so nothing anywhere says a line was missed. That is why this is pinned rather than
trusted.

The app's own Kotlin test (`RefundBodyContractTest`) pins the till's body to
`apps/android/app/src/test/resources/android-refund-body.json`; this posts that file here, filling in
only the ids and the variant.
"""
from __future__ import annotations

import json
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN = (
    REPO_ROOT
    / "apps"
    / "android"
    / "app"
    / "src"
    / "test"
    / "resources"
    / "android-refund-body.json"
)

PRICE = "4.50"


def the_tills_body() -> dict[str, Any]:
    """The app's own refund body, exactly as its Kotlin test pins it."""
    assert GOLDEN.exists(), f"the app's golden refund body is missing: {GOLDEN}"
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_the_androids_own_refund_body_refunds_every_line_it_names() -> None:
    body = the_tills_body()
    company_id = None
    email = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(
                client,
                "Android Refund Contract",
                "Main",
                plan="starter",
                email_prefix="android-refund",
            )
            email, company_id = ctx["email"], ctx["company_id"]
            store_headers = ctx["store_headers"]

            # One plain product and one sold in variants, because the second is the line the app used
            # to refund as nothing.
            plain = (
                await client.post(
                    "/api/v1/products",
                    headers=store_headers,
                    json={
                        "name": "Contract Plain",
                        "sku": f"ARC-{uuid.uuid4().hex[:8]}",
                        "price": PRICE,
                        "opening_stock": 5,
                    },
                )
            ).json()
            varied = (
                await client.post(
                    "/api/v1/products",
                    headers=store_headers,
                    json={
                        "name": "Contract Varied",
                        "sku": f"ARV-{uuid.uuid4().hex[:8]}",
                        "price": PRICE,
                        "opening_stock": 5,
                    },
                )
            ).json()
            set_variants = await client.put(
                f"/api/v1/products/{varied['id']}/variants",
                headers=store_headers,
                json={
                    "variants": [
                        {"sku": f"ARV-L-{uuid.uuid4().hex[:6]}", "name": "Large", "price": PRICE}
                    ]
                },
            )
            assert set_variants.status_code == 200, set_variants.text
            variant_id = set_variants.json()["variants"][0]["id"]
            # A variant created through the variants route has no stock of its own, so an order that
            # names it is refused before the refund is reached. PATCH /inventory/{id} takes the
            # *target* on-hand for a variant rather than a delta.
            stocked = await client.patch(
                f"/api/v1/inventory/{varied['id']}",
                headers=store_headers,
                json={"quantity": 5, "reason": "refund contract fixture", "variant_id": variant_id},
            )
            assert stocked.status_code == 200, stocked.text

            order = (
                await client.post(
                    "/api/v1/orders",
                    headers=store_headers,
                    json={
                        "items": [
                            {"product_id": plain["id"], "quantity": 2},
                            {"product_id": varied["id"], "variant_id": variant_id, "quantity": 1},
                        ],
                        "tenders": [
                            {"method": "cash", "currency_code": "USD", "amount": "50.00"}
                        ],
                    },
                )
            ).json()
            assert order["status"] == "paid", order

            # Only the ids are the fixture's. The quantities, the method and the shape are the till's.
            body["items"][0]["product_id"] = plain["id"]
            body["items"][1]["product_id"] = varied["id"]
            body["items"][1]["variant_id"] = variant_id

            response = await client.post(
                f"/api/v1/orders/{order['id']}/refund", headers=store_headers, json=body
            )
            assert response.status_code == 201, response.text

            refund = response.json()
            # Both lines were refunded, at the prices they were sold at: 2 x 4.50 plus 1 x 4.50. A
            # body that lost the variant would refund only the first line and answer 201 anyway.
            assert Decimal(refund["subtotal"]) == Decimal("13.50"), refund
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
