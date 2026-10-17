"""The body the Android Inventory screen sends to receive stock is one the API acts on.

`POST /inventory/{product_id}/restock` takes a positive delta plus parts that each change what the
receipt *means*: `variant_id` decides whose balance moves, `supplier` becomes the movement's own
wording, and `serial_numbers` is what a serial-tracked product cannot be received without at all.
None of that is type-checked across the two jobs. A renamed key is a 400 at runtime ("Provide one
serial per unit received") or stock on a balance no sale draws on, and the `android` job would still
be green - the same shape of failure that hid a short refund until it was pinned.

The app's own Kotlin test (`RestockBodyContractTest`) pins the screen's body to
`apps/android/app/src/test/resources/android-restock-body.json`; this posts that file here, filling in
only the product, the variant and the serial numbers the fixture's store has to supply.
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
    / "android-restock-body.json"
)

PRICE = "9.99"


def the_screens_body() -> dict[str, Any]:
    """The app's own receive body, exactly as its Kotlin test pins it."""
    assert GOLDEN.exists(), f"the app's golden restock body is missing: {GOLDEN}"
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_the_androids_own_receive_body_receives_into_the_variant_with_its_serials() -> None:
    body = the_screens_body()
    company_id = None
    email = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(
                client,
                "Android Restock Contract",
                "Main",
                plan="starter",
                email_prefix="android-restock",
            )
            email, company_id = ctx["email"], ctx["company_id"]
            store_headers = ctx["store_headers"]

            # A product that tracks serials *and* is sold in variants, because the body names both and
            # testing either alone would leave the interesting half of it unexercised.
            product = (
                await client.post(
                    "/api/v1/products",
                    headers=store_headers,
                    json={
                        "name": "Contract Serialised",
                        "sku": f"ARS-{uuid.uuid4().hex[:8]}",
                        "price": PRICE,
                        "track_serials": True,
                        "reorder_point": 0,
                    },
                )
            ).json()
            set_variants = await client.put(
                f"/api/v1/products/{product['id']}/variants",
                headers=store_headers,
                json={
                    "variants": [
                        {"sku": f"ARS-L-{uuid.uuid4().hex[:6]}", "name": "Large", "price": PRICE}
                    ]
                },
            )
            assert set_variants.status_code == 200, set_variants.text
            variant_id = set_variants.json()["variants"][0]["id"]

            # Only the ids and the serial *values* are the fixture's. The key is the app's decision,
            # so it is asserted rather than written: supplying it here would hand the API the name
            # the app had just lost, and this test would stay green while receipts failed.
            assert "serial_numbers" in body, "the golden no longer names serial_numbers"
            serials = [
                f"SN-{uuid.uuid4().hex[:8].upper()}" for _ in range(int(body["quantity"]))
            ]
            body["variant_id"] = variant_id
            body["serial_numbers"] = serials

            response = await client.post(
                f"/api/v1/inventory/{product['id']}/restock",
                headers=store_headers,
                json=body,
            )
            assert response.status_code == 200, response.text

            # The units went where the body said: onto the variant, not the product's own balance.
            inventory = (await client.get("/api/v1/inventory", headers=store_headers)).json()
            row = next(item for item in inventory if item["product_id"] == product["id"])
            assert Decimal(str(row["on_hand"])) == Decimal("0"), row
            variant = next(item for item in row["variants"] if item["variant_id"] == variant_id)
            assert Decimal(str(variant["on_hand"])) == Decimal(body["quantity"]), row

            # The API named the movement from the supplier, because the body carried no `reason`.
            movements = (
                await client.get(
                    "/api/v1/inventory/movements",
                    headers=store_headers,
                    params={"product_id": product["id"]},
                )
            ).json()
            assert movements, "the receipt left no stock movement"
            latest = movements[0]
            assert latest["movement_type"] == "restock", latest
            assert Decimal(str(latest["quantity"])) == Decimal(body["quantity"]), latest
            assert latest["reason"] == f"Received from {body['supplier']}", latest
            assert latest["variant_id"] == variant_id, latest
            # The cost the screen typed is the cost the movement records. If the key were renamed the
            # API would ignore it and this receipt would silently lose what it cost.
            assert Decimal(str(latest["unit_cost"])) == Decimal(body["unit_cost"]), latest

            # Every unit arrived with its own number, which is the whole point of a serial-tracked
            # receipt and the reason the API refuses one without them.
            listed = (
                await client.get(f"/api/v1/products/{product['id']}/serials", headers=store_headers)
            ).json()
            assert sorted(item["serial_number"] for item in listed) == sorted(serials), listed
            assert all(item["variant_id"] == variant_id for item in listed), listed
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
