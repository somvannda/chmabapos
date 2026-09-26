"""A paused store cannot sell, but stays readable in history/reports (item 7)."""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db import SessionLocal
from app.deps import get_store_context, get_store_context_read
from app.main import app
from app.models import Membership, User


async def create_free_workspace(client: AsyncClient, email: str) -> tuple[dict, dict]:
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Paused Owner", "password": "strong-password"})
    assert register.status_code == 201
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Paused Store", "store_name": "Main Counter", "country": "Cambodia", "currency_code": "USD", "plan_code": "free"},
    )
    assert setup.status_code == 201
    return setup.json(), headers


async def cleanup(email: str, company_id: str | None) -> None:
    async with SessionLocal() as db:
        if company_id:
            parameters = {"company_id": company_id}
            statements = [
                "DELETE FROM orders WHERE store_id IN (SELECT id FROM stores WHERE company_id = :company_id)",
                "DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE store_id IN (SELECT id FROM stores WHERE company_id = :company_id))",
                "DELETE FROM membership_stores USING memberships WHERE membership_stores.membership_id = memberships.id AND memberships.company_id = :company_id",
                "DELETE FROM memberships WHERE company_id = :company_id",
                "DELETE FROM company_currencies WHERE company_id = :company_id",
                "DELETE FROM stores WHERE company_id = :company_id",
                "DELETE FROM companies WHERE id = :company_id",
            ]
            for statement in statements:
                await db.execute(text(statement), parameters)
        await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": email})
        await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": email})
        await db.commit()


@pytest.mark.asyncio
async def test_paused_store_readable_but_not_sellable() -> None:
    email = f"paused-store-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            paused_id = workspace["store"]["id"]

        # Simulate a force-pause (expiry/downgrade).
        async with SessionLocal() as db:
            await db.execute(text("UPDATE stores SET is_active = FALSE WHERE id = :id"), {"id": paused_id})
            await db.commit()

        # Dependency level: writes refuse with a clear message; reads allow.
        async with SessionLocal() as db:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one()
            membership = (
                await db.execute(select(Membership).where(Membership.company_id == uuid.UUID(company_id), Membership.user_id == user.id))
            ).scalar_one()
            with pytest.raises(HTTPException) as blocked:
                await get_store_context(user=user, membership=membership, store_id=uuid.UUID(paused_id), db=db)
            assert blocked.value.status_code == 403
            assert "paused" in blocked.value.detail.lower()

            context = await get_store_context_read(user=user, membership=membership, store_id=uuid.UUID(paused_id), db=db)
            assert str(context.store.id) == paused_id
            assert context.store_paused is True

        # Over HTTP: report + order history resolve; a write is refused.
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            scoped = {**headers, "X-Store-ID": paused_id}
            report = await client.get("/api/v1/reports/summary", headers=scoped)
            assert report.status_code == 200
            orders = await client.get("/api/v1/orders", headers=scoped)
            assert orders.status_code == 200
            refused = await client.post(f"/api/v1/orders/{uuid.uuid4()}/cancel", headers=scoped)
            assert refused.status_code == 403
            assert "paused" in refused.json()["detail"].lower()
    finally:
        await cleanup(email, company_id)
