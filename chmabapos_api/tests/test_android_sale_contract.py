"""The request the Android till builds is one the API actually accepts.

The `android` CI job runs that app's unit tests, and none of them touch the network; the `api` job
has the real endpoint. This is the join between the two:
`apps/android/.../SaleBodyContractTest` pins the app's own sale body to
`apps/android/app/src/test/resources/android-sale-body.json`, and this test posts that same file
here.

Without the pair, a body the till sends and the API refuses ships green. That is not hypothetical:
the till once sent `payment_method` and `tenders` together, `POST /orders` refuses a body carrying
both (v1.py:5604), and every sale failed from the app's first commit until it was caught by hand on
a device.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN = (
    REPO_ROOT / "apps" / "android" / "app" / "src" / "test" / "resources" / "android-sale-body.json"
)

PRICE = "4.50"
OPENING_STOCK = 10


def the_tills_body() -> dict[str, Any]:
    """The app's own sale body, exactly as its Kotlin test pins it."""
    assert GOLDEN.exists(), f"the app's golden sale body is missing: {GOLDEN}"
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_the_androids_own_sale_body_is_accepted() -> None:
    body = the_tills_body()
    company_id = None
    email = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(
                client, "Android Contract", "Main", plan="starter", email_prefix="android-contract"
            )
            email, company_id = ctx["email"], ctx["company_id"]
            store_headers = ctx["store_headers"]

            # Only the ids are the fixture's. Every other key and value is the till's, untouched -
            # this is the app's request, not a hand-written approximation of it.
            body["client_order_id"] = f"ac-{uuid.uuid4().hex}"
            product_ids: list[str] = []
            for index in range(len(body["items"])):
                product = (
                    await client.post(
                        "/api/v1/products",
                        headers=store_headers,
                        json={
                            "name": f"Contract Item {index + 1}",
                            "sku": f"AC-{index}-{uuid.uuid4().hex[:8]}",
                            "price": PRICE,
                            "opening_stock": OPENING_STOCK,
                        },
                    )
                ).json()
                product_ids.append(product["id"])
            for item, product_id in zip(body["items"], product_ids):
                item["product_id"] = product_id

            response = await client.post("/api/v1/orders", headers=store_headers, json=body)
            assert response.status_code == 201, response.text

            order = response.json()
            assert order["id"], order
            assert order["order_number"], order
            assert order["total"], order

            # The lines were understood rather than ignored: the shelf moved by exactly what the
            # body asked for, on every line, including the one carrying two modifiers.
            inventory = (await client.get("/api/v1/inventory", headers=store_headers)).json()
            for item, product_id in zip(body["items"], product_ids):
                row = next(entry for entry in inventory if entry["product_id"] == product_id)
                assert row["on_hand"] == OPENING_STOCK - int(item["quantity"])
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
