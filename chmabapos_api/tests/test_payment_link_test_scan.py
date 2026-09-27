"""A paid KHQR test scan auto-activates the merchant's ABA PayWay link.

Merchants prove a link works by sending a $0.10 test payment. Once it settles the
link no longer needs platform review, so the status poll promotes it to
``active`` (with a tenant audit entry) and POS checkout can start generating
KHQR into the merchant's ABA account.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text

from app.db import SessionLocal
from app.main import app
from app.models import Company, Store, TenantAuditLog
from app.services.payments.chamabapay import ChmabaPayClient

pytestmark = pytest.mark.asyncio

LINK = "https://link.payway.com.kh/ABAPAYpe518710Y"


async def _cleanup(email: str, company_id: str | None) -> None:
    async with SessionLocal() as db:
        if company_id:
            parameters = {"company_id": company_id}
            statements = [
                "DELETE FROM tenant_audit_logs WHERE company_id = :company_id",
                "DELETE FROM billing_payments USING subscriptions WHERE billing_payments.subscription_id = subscriptions.id AND subscriptions.company_id = :company_id",
                "DELETE FROM subscriptions WHERE company_id = :company_id",
                "DELETE FROM membership_stores USING memberships WHERE membership_stores.membership_id = memberships.id AND memberships.company_id = :company_id",
                "DELETE FROM memberships WHERE company_id = :company_id",
                "DELETE FROM company_currencies WHERE company_id = :company_id",
                "DELETE FROM stock_movements USING stores WHERE stock_movements.store_id = stores.id AND stores.company_id = :company_id",
                "DELETE FROM inventory_balances USING stores WHERE inventory_balances.store_id = stores.id AND stores.company_id = :company_id",
                "DELETE FROM payments USING orders, stores WHERE payments.order_id = orders.id AND orders.store_id = stores.id AND stores.company_id = :company_id",
                "DELETE FROM order_items USING orders, stores WHERE order_items.order_id = orders.id AND orders.store_id = stores.id AND stores.company_id = :company_id",
                "DELETE FROM orders USING stores WHERE orders.store_id = stores.id AND stores.company_id = :company_id",
                "DELETE FROM products WHERE company_id = :company_id",
                "DELETE FROM categories WHERE company_id = :company_id",
                "DELETE FROM stores WHERE company_id = :company_id",
                "DELETE FROM companies WHERE id = :company_id",
            ]
            for statement in statements:
                await db.execute(text(statement), parameters)
        await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": email})
        await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": email})
        await db.commit()


async def _setup_workspace(client: AsyncClient, label: str) -> tuple[str, str, str, dict]:
    email = f"{label}-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Link Owner", "password": "strong-password"})
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": f"{label} Co", "store_name": "Main Counter", "country": "Cambodia", "currency_code": "USD", "plan_code": "starter"},
    )
    assert setup.status_code == 201, setup.text
    workspace = setup.json()
    billing = workspace.get("billing_payment")
    if billing:
        completed = await client.post(f"/api/v1/mock/chamabapay/{billing['external_id']}/complete", headers=headers)
        assert completed.status_code == 204
    return email, workspace["company"]["id"], workspace["store"]["id"], headers


@pytest.fixture
def pending_provider(monkeypatch):
    """Simulate a ChmabaPay store the provider reports as still pending review."""

    async def fake_ensure_store(self, external_id, raw_link, *, merchant_account_id=None, merchant_name=None, store_id=None):
        return {"id": store_id or "st_test", "status": "pending", "external_id": external_id}

    monkeypatch.setattr(ChmabaPayClient, "ensure_store", fake_ensure_store)


@pytest.fixture
def paid_reconcile(monkeypatch):
    async def fake_reconcile(self, payment_public_id: str) -> dict:
        return {"status": "PAID", "source": None}

    monkeypatch.setattr(ChmabaPayClient, "reconcile", fake_reconcile)


async def test_paid_test_scan_activates_company_link(pending_provider, paid_reconcile) -> None:
    email = ""
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            email, company_id, _store_id, headers = await _setup_workspace(client, "company-activate")

            linked = await client.patch("/api/v1/company", headers=headers, json={"aba_payway_link": LINK})
            assert linked.status_code == 200, linked.text
            assert linked.json()["aba_payway_status"] == "pending"

            scan = await client.post("/api/v1/company/payment-link/test-scan", headers=headers)
            assert scan.status_code == 200, scan.text

            status = await client.post(
                "/api/v1/company/payment-link/test-scan/status",
                headers=headers,
                json={"payment_public_id": scan.json()["payment_public_id"]},
            )
            assert status.status_code == 200, status.text
            body = status.json()
            assert body["paid"] is True
            assert body["aba_payway_status"] == "active"

            async with SessionLocal() as db:
                company = await db.get(Company, uuid.UUID(company_id))
                assert company is not None and company.aba_payway_status == "active"
                audit_count = await db.scalar(
                    select(func.count())
                    .select_from(TenantAuditLog)
                    .where(TenantAuditLog.company_id == uuid.UUID(company_id), TenantAuditLog.action == "payment_link_activated")
                )
                assert audit_count == 1
    finally:
        await _cleanup(email, company_id)


async def test_paid_test_scan_activates_store_link_only(pending_provider, paid_reconcile) -> None:
    email = ""
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            email, company_id, store_id, headers = await _setup_workspace(client, "store-activate")

            linked = await client.patch(f"/api/v1/stores/{store_id}", headers=headers, json={"aba_payway_link": LINK})
            assert linked.status_code == 200, linked.text
            assert linked.json()["aba_payway_status"] == "pending"

            scan = await client.post(f"/api/v1/stores/{store_id}/payment-link/test-scan", headers=headers)
            assert scan.status_code == 200, scan.text

            status = await client.post(
                f"/api/v1/stores/{store_id}/payment-link/test-scan/status",
                headers=headers,
                json={"payment_public_id": scan.json()["payment_public_id"]},
            )
            assert status.status_code == 200, status.text
            body = status.json()
            assert body["paid"] is True
            assert body["aba_payway_status"] == "active"

            async with SessionLocal() as db:
                store = await db.get(Store, uuid.UUID(store_id))
                assert store is not None and store.aba_payway_status == "active"
                company = await db.get(Company, uuid.UUID(company_id))
                assert company is not None and company.aba_payway_status == "none"
    finally:
        await _cleanup(email, company_id)


async def test_unpaid_test_scan_leaves_link_pending(pending_provider) -> None:
    email = ""
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            email, company_id, _store_id, headers = await _setup_workspace(client, "company-unpaid")

            linked = await client.patch("/api/v1/company", headers=headers, json={"aba_payway_link": LINK})
            assert linked.status_code == 200, linked.text
            assert linked.json()["aba_payway_status"] == "pending"

            scan = await client.post("/api/v1/company/payment-link/test-scan", headers=headers)
            assert scan.status_code == 200, scan.text

            status = await client.post(
                "/api/v1/company/payment-link/test-scan/status",
                headers=headers,
                json={"payment_public_id": scan.json()["payment_public_id"]},
            )
            assert status.status_code == 200, status.text
            body = status.json()
            assert body["paid"] is False
            assert body["aba_payway_status"] == "pending"

            async with SessionLocal() as db:
                company = await db.get(Company, uuid.UUID(company_id))
                assert company is not None and company.aba_payway_status == "pending"
    finally:
        await _cleanup(email, company_id)
