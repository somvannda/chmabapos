"""The request the Android till builds for a purchase order is one the API accepts.

`POST /purchases` reads a plain dict and validates it by hand (v1.py:9235), so unlike the sale there
is no schema to drift against: a field the app renames or stops sending is a 404 or a 422 at the
server and nothing at all in the `android` job. This is the join between the two jobs, the same way
`test_android_sale_contract.py` joins the sale body - the app's Kotlin test pins its own purchase body
to `apps/android/app/src/test/resources/android-purchase-body.json`, and this posts that file here.
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
    REPO_ROOT
    / "apps"
    / "android"
    / "app"
    / "src"
    / "test"
    / "resources"
    / "android-purchase-body.json"
)

PRICE = "4.50"
SUPPLIER_NAME = "Contract Supplier"


def the_tills_body() -> dict[str, Any]:
    """The app's own purchase order body, exactly as its Kotlin test pins it."""
    assert GOLDEN.exists(), f"the app's golden purchase body is missing: {GOLDEN}"
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_the_androids_own_purchase_body_is_accepted() -> None:
    body = the_tills_body()
    company_id = None
    email = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(
                client,
                "Android Purchase Contract",
                "Main",
                plan="starter",
                email_prefix="android-po",
            )
            email, company_id = ctx["email"], ctx["company_id"]
            store_headers = ctx["store_headers"]

            # Only the ids are the fixture's. Every other key and value is the till's, untouched.
            product_ids: list[str] = []
            for index in range(len(body["items"])):
                product = (
                    await client.post(
                        "/api/v1/products",
                        headers=store_headers,
                        json={
                            "name": f"Contract Item {index + 1}",
                            "sku": f"APO-{index}-{uuid.uuid4().hex[:8]}",
                            "price": PRICE,
                            "opening_stock": 5,
                        },
                    )
                ).json()
                product_ids.append(product["id"])
            for item, product_id in zip(body["items"], product_ids):
                item["product_id"] = product_id

            supplier = (
                await client.post(
                    "/api/v1/suppliers",
                    headers=store_headers,
                    json={"name": SUPPLIER_NAME},
                )
            ).json()
            body["supplier_id"] = supplier["id"]

            response = await client.post("/api/v1/purchases", headers=store_headers, json=body)
            assert response.status_code == 201, response.text

            order = response.json()
            assert order["po_number"], order
            assert order["status"] == "ordered", order
            # Every line the till stated was understood, in the order it stated them.
            assert [item["product_id"] for item in order["items"]] == product_ids, order["items"]
            assert [item["quantity"] for item in order["items"]] == [
                item["quantity"] for item in body["items"]
            ], order["items"]
            # The cost the till sent on one line is the cost the order records, and the line that
            # sent none records none rather than a zero or the word "null".
            costs = [item.get("unit_cost") for item in order["items"]]
            assert costs[0] == "1.20", costs
            assert costs[1] in (None, ""), costs
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
