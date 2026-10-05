"""Manager notifications are store-scoped; owners see the whole company.

A manager linked only to Store A must not be told about Store B events. Owners
remain company-wide. Also pins the ops-digest event set to the review kinds the
API actually emits.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.api.v1 import notify_company_managers
from app.db import SessionLocal
from app.main import app
from app.services.store_notifications import DIGEST_TYPES

CLEANUP = [
    "DELETE FROM notifications USING stores WHERE notifications.store_id = stores.id AND stores.company_id = :company_id",
    "DELETE FROM membership_stores USING memberships WHERE membership_stores.membership_id = memberships.id AND memberships.company_id = :company_id",
    "DELETE FROM memberships WHERE company_id = :company_id",
    "DELETE FROM invitations WHERE company_id = :company_id",
    "DELETE FROM company_currencies WHERE company_id = :company_id",
    "DELETE FROM stores WHERE company_id = :company_id",
    "DELETE FROM companies WHERE id = :company_id",
]


async def cleanup(company_id, emails) -> None:
    if not company_id:
        return
    async with SessionLocal() as db:
        for statement in CLEANUP:
            await db.execute(text(statement), {"company_id": company_id})
        await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = ANY(:emails))"), {"emails": emails})
        await db.execute(text("DELETE FROM users WHERE email = ANY(:emails)"), {"emails": emails})
        await db.commit()


def test_digest_covers_every_emitted_review_kind() -> None:
    for kind in ("approval_request", "discount_review", "refund_review", "stock_transfer", "price_cost_edit_review", "stock_write_off_review", "cancel_paid_order_review", "loyalty_adjust_review"):
        assert kind in DIGEST_TYPES, f"digest misses {kind}"


@pytest.mark.asyncio
async def test_manager_notifications_are_store_scoped() -> None:
    owner_email = f"notif-owner-{uuid.uuid4().hex[:10]}@example.com"
    manager_email = f"notif-manager-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            reg = await client.post("/api/v1/auth/register", json={"email": owner_email, "full_name": "Notif Owner", "password": "strong-password"})
            assert reg.status_code == 201, reg.text
            await client.post("/api/v1/auth/verify-email", json={"token": reg.json()["dev_verification_token"]})
            login = await client.post("/api/v1/auth/login", json={"email": owner_email, "password": "strong-password"})
            owner = {"Authorization": f"Bearer {login.json()['access_token']}"}

            setup = await client.post("/api/v1/workspaces/setup", headers=owner, json={"company_name": "Notif Co", "store_name": "Store A", "currency_code": "USD", "plan_code": "pro"})
            assert setup.status_code == 201, setup.text
            ws = setup.json()
            company_id = ws["company"]["id"]
            store_a = ws["store"]["id"]
            await client.post(f"/api/v1/mock/chamabapay/{ws['billing_payment']['external_id']}/complete")

            second = await client.post("/api/v1/stores", headers=owner, json={"name": "Store B", "currency_code": "USD", "timezone": "Asia/Phnom_Penh"})
            assert second.status_code == 201, second.text
            store_b = second.json()["id"]

            invite = await client.post("/api/v1/team/invitations", headers=owner, json={"email": manager_email, "role": "manager", "store_ids": [store_a]})
            assert invite.status_code == 201, invite.text
            accepted = await client.post("/api/v1/team/invitations/accept", json={"token": invite.json()["dev_invitation_token"], "full_name": "Notif Manager", "password": "strong-password"})
            assert accepted.status_code == 200, accepted.text

        async with SessionLocal() as db:
            owner_id = (await db.execute(text("SELECT id FROM users WHERE email = :email"), {"email": owner_email})).scalar_one()
            manager_id = (await db.execute(text("SELECT id FROM users WHERE email = :email"), {"email": manager_email})).scalar_one()

            async def count(user_id, store_id):
                return await db.scalar(text("SELECT count(*) FROM notifications WHERE user_id = :user_id AND store_id = :store_id AND type = 'stock_transfer'"), {"user_id": user_id, "store_id": store_id})

            # Event on Store B: the Store-A-only manager is not told, the owner is.
            await notify_company_managers(db, company_id, store_b, "stock_transfer", "Incoming stock", "one item")
            await db.commit()
            assert await count(manager_id, store_b) == 0
            assert await count(owner_id, store_b) >= 1

            # Event on the manager's own store reaches them.
            await notify_company_managers(db, company_id, store_a, "stock_transfer", "Incoming stock", "one item")
            await db.commit()
            assert await count(manager_id, store_a) >= 1
    finally:
        await cleanup(company_id, [owner_email, manager_email])
