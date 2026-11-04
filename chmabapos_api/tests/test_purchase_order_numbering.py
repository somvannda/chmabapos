from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update

from app.db import SessionLocal
from app.main import app
from app.models import StoreSequence


async def _setup_store(client: AsyncClient) -> dict[str, str]:
    """Register an owner, verify, sign in and open a paid starter workspace."""
    email = f"po-number-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "PO Number Test", "password": "strong-password"})
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "PO Number Store", "store_name": "Main", "country": "Cambodia", "currency_code": "USD", "plan_code": "starter"},
    )
    assert setup.status_code == 201, setup.text
    await client.post(f"/api/v1/mock/chamabapay/{setup.json()['billing_payment']['external_id']}/complete", headers=headers)
    return {**headers, "X-Store-ID": setup.json()["store"]["id"]}


async def _create_order(client: AsyncClient, headers: dict[str, str], product_id: str):
    return await client.post(
        "/api/v1/purchases",
        headers=headers,
        json={"items": [{"product_id": product_id, "quantity": 1, "unit_cost": "12.00"}]},
    )


@pytest.mark.asyncio
async def test_a_stale_counter_skips_numbers_already_issued() -> None:
    """A counter behind the highest issued number must not fail the insert.

    ``store_sequences`` is seeded from a row *count*, so deleting a document (or
    restoring a backup) can leave it pointing at a number that already exists.
    The unique constraint on ``po_number`` then rejected the insert and the
    endpoint answered a bare 500 - permanently, because every retry allocated the
    same taken number.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        store_id = uuid.UUID(headers["X-Store-ID"])
        product = await client.post(
            "/api/v1/products",
            headers=headers,
            json={"name": "Numbered item", "sku": f"NUM-{uuid.uuid4().hex[:8]}", "price": "20.00"},
        )
        assert product.status_code == 201, product.text
        product_id = product.json()["id"]

        first = await _create_order(client, headers, product_id)
        assert first.status_code == 201, first.text
        assert first.json()["po_number"] == "PO-000001"

        # Point the counter back at the number already in use, the state a
        # count-seeded counter reaches once documents are deleted.
        async with SessionLocal() as db:
            await db.execute(
                update(StoreSequence)
                .where(StoreSequence.store_id == store_id, StoreSequence.scope == "purchase_order")
                .values(next_value=1)
            )
            await db.commit()

        second = await _create_order(client, headers, product_id)
        assert second.status_code == 201, second.text
        assert second.json()["po_number"] == "PO-000002"

        listed = (await client.get("/api/v1/purchases", headers=headers)).json()
        numbers = {row["po_number"] for row in listed}
        assert {"PO-000001", "PO-000002"} <= numbers
