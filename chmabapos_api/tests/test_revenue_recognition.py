"""Revenue is recognised on the day it was paid for, not the day it was written down.

A counter sale is both at once, so nothing changed for the till. An online pay-at-counter order
is not: it can be placed at lunchtime and collected the next morning, and counting it on the day
it was written down puts the takings on the day the shop heard about a sale rather than the day
it was paid for.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app

# The workspace these tests set up is in Cambodia, so its day boundary is +07.
LOCAL = timezone(timedelta(hours=7))


def _local_day(offset_days: int) -> str:
    return (datetime.now(timezone.utc).astimezone(LOCAL) + timedelta(days=offset_days)).date().isoformat()


async def _owner_workspace(client: AsyncClient) -> tuple[dict[str, str], str]:
    email = f"paid-at-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Paid At Owner", "password": "strong-password"})
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Paid At Co", "store_name": "Main", "country": "Cambodia", "currency_code": "USD", "plan_code": "starter"},
    )
    assert setup.status_code == 201, setup.text
    await client.post(f"/api/v1/mock/chamabapay/{setup.json()['billing_payment']['external_id']}/complete", headers=headers)
    workspace = setup.json()
    return {**headers, "X-Store-ID": workspace["store"]["id"]}, workspace["store"]["id"]


async def _paid_sale(client: AsyncClient, headers: dict[str, str]) -> str:
    product = await client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "Late Latte", "sku": f"LL-{uuid.uuid4().hex[:8]}", "price": "10.00", "opening_stock": 5},
    )
    assert product.status_code == 201, product.text
    sale = await client.post(
        "/api/v1/orders",
        headers=headers,
        json={"items": [{"product_id": product.json()["id"], "quantity": 1}], "payment_method": "cash"},
    )
    assert sale.status_code == 201, sale.text
    assert sale.json()["status"] == "paid"
    return sale.json()["id"]


async def _net_sales(client: AsyncClient, headers: dict[str, str], day: str) -> Decimal:
    response = await client.get(f"/api/v1/reports/summary?from_date={day}&to_date={day}", headers=headers)
    assert response.status_code == 200, response.text
    return Decimal(response.json()["net_sales"])


@pytest.mark.asyncio
async def test_a_sale_counts_on_the_day_it_was_paid() -> None:
    """Written down yesterday, paid today - what a collected pay-at-counter order looks like."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, _store_id = await _owner_workspace(client)
        order_id = await _paid_sale(client, headers)
        async with SessionLocal() as db:
            await db.execute(text("UPDATE orders SET created_at = paid_at - interval '1 day' WHERE id = :id"), {"id": uuid.UUID(order_id)})
            await db.commit()

        assert await _net_sales(client, headers, _local_day(0)) == Decimal("11.00"), "the money arrived today"
        assert await _net_sales(client, headers, _local_day(-1)) == Decimal("0.00"), "it was not paid for yesterday"


@pytest.mark.asyncio
async def test_an_order_with_no_paid_at_still_counts_on_the_day_it_was_written() -> None:
    """The fallback, and the reason it exists.

    Orders written before ``paid_at`` was always set have none. Treating an absent ``paid_at`` as
    "not paid" would drop that revenue out of every report, which is worse than counting it on
    the day it was written down.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, _store_id = await _owner_workspace(client)
        order_id = await _paid_sale(client, headers)
        async with SessionLocal() as db:
            await db.execute(text("UPDATE orders SET paid_at = NULL WHERE id = :id"), {"id": uuid.UUID(order_id)})
            await db.commit()

        assert await _net_sales(client, headers, _local_day(0)) == Decimal("11.00")
