from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


async def _owner_workspace(client: AsyncClient) -> dict[str, str]:
    email = f"batch-expiry-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Batch Owner", "password": "strong-password"})
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Batch Expiry Co", "store_name": "Main", "country": "Cambodia", "currency_code": "USD", "plan_code": "starter"},
    )
    assert setup.status_code == 201, setup.text
    await client.post(f"/api/v1/mock/chamabapay/{setup.json()['billing_payment']['external_id']}/complete", headers=headers)
    workspace = setup.json()
    return {**headers, "X-Store-ID": workspace["store"]["id"]}


def _day(offset: int) -> str:
    return (date.today() + timedelta(days=offset)).isoformat()


@pytest.mark.asyncio
async def test_expiring_batches_returns_stocked_and_soon_ordered_by_expiry() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _owner_workspace(client)
        product = await client.post("/api/v1/products", headers=headers, json={"name": "Yoghurt", "sku": f"YOG-{uuid.uuid4().hex[:8]}", "price": "2.00", "opening_stock": 0})
        assert product.status_code == 201, product.text
        product_id = product.json()["id"]

        added = await client.post(
            f"/api/v1/products/{product_id}/batches",
            headers=headers,
            json={"batches": [
                {"batch_code": "EXPIRED", "expiry_date": _day(-1), "quantity_on_hand": "4"},
                {"batch_code": "SOON", "expiry_date": _day(5), "quantity_on_hand": "6"},
                {"batch_code": "FAR", "expiry_date": _day(100), "quantity_on_hand": "7"},
                {"batch_code": "EMPTY", "expiry_date": _day(-2), "quantity_on_hand": "0"},
            ]},
        )
        assert added.status_code == 201, added.text

        rows = await client.get("/api/v1/inventory/expiring-batches?days=30", headers=headers)
        assert rows.status_code == 200, rows.text
        codes = [row["batch_code"] for row in rows.json()]
        assert codes == ["EXPIRED", "SOON"]
        assert rows.json()[0]["days_until_expiry"] == -1
        assert rows.json()[1]["days_until_expiry"] == 5
        assert rows.json()[0]["product_name"] == "Yoghurt"

        just_expired = await client.get("/api/v1/inventory/expiring-batches?days=0", headers=headers)
        assert [row["batch_code"] for row in just_expired.json()] == ["EXPIRED"]
