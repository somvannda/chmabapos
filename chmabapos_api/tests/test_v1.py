from __future__ import annotations

import uuid
import re
import json
import urllib.request

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app
from app.models import Company, Membership, User


@pytest.mark.asyncio
async def test_v1_workspace_catalog_cash_and_khqr_flow() -> None:
    email = f"api-test-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "API Test Owner", "password": "strong-password"})
            assert register.status_code == 201
            verification_token = register.json()["dev_verification_token"]
            assert verification_token

            verify = await client.post("/api/v1/auth/verify-email", json={"token": verification_token})
            assert verify.status_code == 200
            assert verify.json()["is_email_verified"] is True

            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
            assert login.status_code == 200
            token = login.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            setup = await client.post(
                "/api/v1/workspaces/setup",
                headers=headers,
                json={"company_name": "API Test Store", "store_name": "Main Counter", "country": "Cambodia", "currency_code": "USD", "plan_code": "starter"},
            )
            assert setup.status_code == 201
            workspace = setup.json()
            company_id = workspace["company"]["id"]
            store_id = workspace["store"]["id"]
            store_headers = {**headers, "X-Store-ID": store_id}

            # Paid plans start "pending" until payment completes. Simulate it in dev.
            billing_payment = workspace["billing_payment"]
            assert billing_payment is not None
            completed = await client.post(f"/api/v1/mock/cutluy/{billing_payment['external_id']}/complete", headers=headers)
            assert completed.status_code == 204

            categories = await client.get("/api/v1/categories", headers=headers)
            assert categories.status_code == 200
            category_id = categories.json()[0]["id"]

            currencies = await client.put("/api/v1/settings/currencies", headers=headers, json={"primary_code": "USD", "enabled_codes": ["USD", "KHR"]})
            assert currencies.status_code == 200
            rate = await client.post("/api/v1/exchange-rates", headers=headers, json={"base_currency_code": "USD", "quote_currency_code": "KHR", "rate": "4000"})
            assert rate.status_code == 201
            quote = await client.get("/api/v1/exchange-rates/quote?base_currency_code=USD&quote_currency_code=KHR&amount=2.50", headers=store_headers)
            assert quote.status_code == 200
            assert quote.json()["converted_amount"] == "10000"

            product = await client.post(
                "/api/v1/products",
                headers=store_headers,
                json={"name": "API Latte", "sku": f"API-{uuid.uuid4().hex[:8]}", "price": "4.50", "category_id": category_id, "opening_stock": 8, "reorder_point": 2},
            )
            assert product.status_code == 201
            product_id = product.json()["id"]
            assert product.json()["on_hand"] == 8

            edited = await client.patch("/api/v1/products/" + product_id, headers=store_headers, json={"name": "API Latte Updated", "price": "4.75"})
            assert edited.status_code == 200
            assert edited.json()["name"] == "API Latte Updated"

            company = await client.patch("/api/v1/company", headers=headers, json={"name": "API Test Store Updated"})
            assert company.status_code == 200
            assert company.json()["name"] == "API Test Store Updated"

            cash_order = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 2}], "payment_method": "cash"})
            assert cash_order.status_code == 201
            assert cash_order.json()["status"] == "paid"
            assert cash_order.json()["total"] == "10.45"

            inventory = await client.get("/api/v1/inventory", headers=store_headers)
            assert inventory.status_code == 200
            assert next(item for item in inventory.json() if item["product_id"] == product_id)["on_hand"] == 6

            mixed_order = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 1}], "tenders": [{"method": "cash", "currency_code": "USD", "amount": "10.00"}, {"method": "cash", "currency_code": "KHR", "amount": "10000"}], "change_currency_code": "KHR"})
            assert mixed_order.status_code == 201
            assert mixed_order.json()["status"] == "paid"
            assert mixed_order.json()["tendered_base_amount"] == "12.50"
            assert mixed_order.json()["change_amount"] == "29080"
            assert mixed_order.json()["change_currency_code"] == "KHR"

            khqr_order = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 1}], "payment_method": "khqr"})
            assert khqr_order.status_code == 201
            assert khqr_order.json()["status"] == "payment_pending"
            external_id = khqr_order.json()["payments"][0]["external_id"]
            complete = await client.post(f"/api/v1/mock/cutluy/{external_id}/complete")
            assert complete.status_code == 204

            after_khqr = await client.get(f"/api/v1/orders/{khqr_order.json()['id']}", headers=store_headers)
            assert after_khqr.status_code == 200
            assert after_khqr.json()["status"] == "paid"

            orders = await client.get("/api/v1/orders", headers=store_headers)
            assert orders.status_code == 200
            assert len(orders.json()) >= 3

            billing = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": "pro"})
            assert billing.status_code == 201
            assert billing.json()["payment"]["amount"] == "4.99"
    finally:
        async with SessionLocal() as db:
            if company_id:
                parameters = {"company_id": company_id}
                statements = [
                    "DELETE FROM billing_payments USING subscriptions WHERE billing_payments.subscription_id = subscriptions.id AND subscriptions.company_id = :company_id",
                    "DELETE FROM subscriptions WHERE company_id = :company_id",
                    "DELETE FROM membership_stores USING memberships WHERE membership_stores.membership_id = memberships.id AND memberships.company_id = :company_id",
                    "DELETE FROM memberships WHERE company_id = :company_id",
                    "DELETE FROM invitations WHERE company_id = :company_id",
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


@pytest.mark.asyncio
async def test_paid_setup_and_invitation_acceptance() -> None:
    owner_email = f"paid-owner-{uuid.uuid4().hex[:10]}@example.com"
    teammate_email = f"teammate-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            register = await client.post("/api/v1/auth/register", json={"email": owner_email, "full_name": "Paid Owner", "password": "strong-password"})
            assert register.status_code == 201
            await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
            login = await client.post("/api/v1/auth/login", json={"email": owner_email, "password": "strong-password"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            setup = await client.post("/api/v1/workspaces/setup", headers=headers, json={"company_name": "Paid API Store", "store_name": "Paid Counter", "currency_code": "USD", "plan_code": "starter"})
            assert setup.status_code == 201
            workspace = setup.json()
            company_id = workspace["company"]["id"]
            assert workspace["subscription"]["status"] == "pending"
            billing_payment_id = workspace["billing_payment"]["external_id"]
            assert billing_payment_id

            blocked_sale = await client.post("/api/v1/orders", headers={**headers, "X-Store-ID": workspace["store"]["id"]}, json={"items": []})
            assert blocked_sale.status_code == 422

            plan_paid = await client.post(f"/api/v1/mock/cutluy/{billing_payment_id}/complete")
            assert plan_paid.status_code == 204
            current_plan = await client.get("/api/v1/billing/subscription", headers=headers)
            assert current_plan.status_code == 200
            assert current_plan.json()["status"] == "active"

            invitation = await client.post("/api/v1/team/invitations", headers=headers, json={"email": teammate_email, "role": "cashier", "store_ids": [workspace["store"]["id"]]})
            assert invitation.status_code == 201
            invitation_token = invitation.json()["dev_invitation_token"]
            accepted = await client.post("/api/v1/team/invitations/accept", json={"token": invitation_token, "full_name": "Store Teammate", "password": "strong-password"})
            assert accepted.status_code == 200
            team = await client.get("/api/v1/team", headers=headers)
            assert team.status_code == 200
            teammate = next(member for member in team.json() if member["user"]["email"] == teammate_email)
            assert teammate["role"] == "cashier"
    finally:
        async with SessionLocal() as db:
            if company_id:
                parameters = {"company_id": company_id}
                statements = [
                    "DELETE FROM billing_payments USING subscriptions WHERE billing_payments.subscription_id = subscriptions.id AND subscriptions.company_id = :company_id",
                    "DELETE FROM subscriptions WHERE company_id = :company_id",
                    "DELETE FROM membership_stores USING memberships WHERE membership_stores.membership_id = memberships.id AND memberships.company_id = :company_id",
                    "DELETE FROM memberships WHERE company_id = :company_id",
                    "DELETE FROM invitations WHERE company_id = :company_id",
                    "DELETE FROM company_currencies WHERE company_id = :company_id",
                    "DELETE FROM stores WHERE company_id = :company_id",
                    "DELETE FROM categories WHERE company_id = :company_id",
                    "DELETE FROM companies WHERE id = :company_id",
                ]
                for statement in statements:
                    await db.execute(text(statement), parameters)
            await db.execute(text("DELETE FROM users WHERE email IN (:owner_email, :teammate_email)"), {"owner_email": owner_email, "teammate_email": teammate_email})
            await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id NOT IN (SELECT id FROM users)"))
            await db.commit()


@pytest.mark.asyncio
async def test_tenant_owner_cannot_access_platform_admin() -> None:
    email = f"tenant-guard-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Tenant Guard", "password": "strong-password"})
            await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            setup = await client.post("/api/v1/workspaces/setup", headers=headers, json={"company_name": "Guard Store", "store_name": "Main Counter", "currency_code": "USD", "plan_code": "free"})
            company_id = setup.json()["company"]["id"]
            denied = await client.get("/api/v1/admin/overview", headers=headers)
            assert denied.status_code == 403
    finally:
        async with SessionLocal() as db:
            if company_id:
                parameters = {"company_id": company_id}
                statements = [
                    "DELETE FROM membership_stores USING memberships WHERE membership_stores.membership_id=memberships.id AND memberships.company_id=:company_id",
                    "DELETE FROM memberships WHERE company_id=:company_id",
                    "DELETE FROM company_currencies WHERE company_id=:company_id",
                    "DELETE FROM categories WHERE company_id=:company_id",
                    "DELETE FROM stores WHERE company_id=:company_id",
                    "DELETE FROM subscriptions WHERE company_id=:company_id",
                    "DELETE FROM companies WHERE id=:company_id",
                ]
                for statement in statements:
                    await db.execute(text(statement), parameters)
            await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email=:email)"), {"email": email})
            await db.execute(text("DELETE FROM users WHERE email=:email"), {"email": email})
            await db.commit()


@pytest.mark.asyncio
async def test_password_reset_flow() -> None:
    email = f"reset-{uuid.uuid4().hex[:10]}@example.com"
    old_password = "old-password-123"
    new_password = "new-password-456"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Reset User", "password": old_password})
        assert register.status_code == 201
        await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
        reset_request = await client.post("/api/v1/auth/request-password-reset", json={"email": email})
        assert reset_request.status_code == 200

        messages = json.load(urllib.request.urlopen("http://127.0.0.1:8025/api/v2/messages"))
        message = next(item for item in messages["items"] if email in " ".join(item["Content"]["Headers"].get("To", [])) and "Reset your Chmaba password" in " ".join(item["Content"]["Headers"].get("Subject", [])))
        token = re.search(r"reset-password\?token=([^\s]+)", message["Content"]["Body"]).group(1)
        reset = await client.post("/api/v1/auth/reset-password", json={"token": token, "password": new_password})
        assert reset.status_code == 200
        old_login = await client.post("/api/v1/auth/login", json={"email": email, "password": old_password})
        assert old_login.status_code == 401
        new_login = await client.post("/api/v1/auth/login", json={"email": email, "password": new_password})
        assert new_login.status_code == 200
        reused = await client.post("/api/v1/auth/reset-password", json={"token": token, "password": old_password})
        assert reused.status_code == 400

    async with SessionLocal() as db:
        await db.execute(text("delete from email_verification_tokens where user_id in (select id from users where email=:email)"), {"email": email})
        await db.execute(text("delete from password_reset_tokens where user_id in (select id from users where email=:email)"), {"email": email})
        await db.execute(text("delete from users where email=:email"), {"email": email})
        await db.commit()


@pytest.mark.asyncio
async def test_google_signin_creates_and_links_merchants_only(monkeypatch) -> None:
    google_email = f"google-new-{uuid.uuid4().hex[:10]}@gmail.com"
    linked_email = f"google-link-{uuid.uuid4().hex[:10]}@gmail.com"
    admin_email = f"google-admin-{uuid.uuid4().hex[:10]}@gmail.com"

    import app.api.v1 as v1_module

    def fake_verify(id_token: str, client_id: str) -> dict:
        if id_token == "token-for-admin":
            return {"sub": "google-admin-sub-1", "email": admin_email, "email_verified": True, "name": "Google Admin"}
        if id_token == "token-for-linked":
            return {"sub": "google-linked-sub-1", "email": linked_email, "email_verified": True, "name": "Linked Owner"}
        return {"sub": "google-new-sub-1", "email": google_email, "email_verified": True, "name": "New Merchant"}

    monkeypatch.setattr(v1_module.settings, "google_client_id", "test-client-id")
    monkeypatch.setattr(v1_module, "verify_google_id_token", fake_verify)

    admin_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Unconfigured server -> 503.
            monkeypatch.setattr(v1_module.settings, "google_client_id", None)
            unconfigured = await client.post("/api/v1/auth/google", json={"id_token": "anything"})
            assert unconfigured.status_code == 503
            monkeypatch.setattr(v1_module.settings, "google_client_id", "test-client-id")

            # Brand-new merchant -> account created, verified, is_new_user=True.
            created = await client.post("/api/v1/auth/google", json={"id_token": "token-for-new"})
            assert created.status_code == 200
            created_body = created.json()
            assert created_body["is_new_user"] is True
            assert created_body["user"]["email"] == google_email
            assert created_body["user"]["is_email_verified"] is True
            assert created_body["user"]["platform_role"] is None
            assert created_body["access_token"]

            # Repeated sign-in is not a "new user".
            again = await client.post("/api/v1/auth/google", json={"id_token": "token-for-new"})
            assert again.status_code == 200
            assert again.json()["is_new_user"] is False

            # Existing email/password merchant gets linked to Google.
            register = await client.post("/api/v1/auth/register", json={"email": linked_email, "full_name": "Linked Owner", "password": "strong-password"})
            assert register.status_code == 201
            linked = await client.post("/api/v1/auth/google", json={"id_token": "token-for-linked"})
            assert linked.status_code == 200
            assert linked.json()["is_new_user"] is False
            assert linked.json()["user"]["email"] == linked_email

            # Platform admins are never allowed through Google.
            register_admin = await client.post("/api/v1/auth/register", json={"email": admin_email, "full_name": "Admin Person", "password": "strong-password"})
            assert register_admin.status_code == 201
            admin_user = register_admin.json()["user"]
            admin_id = admin_user["id"]
            async with SessionLocal() as db:
                await db.execute(text("UPDATE users SET platform_role = 'admin' WHERE id = :uid"), {"uid": admin_id})
                await db.commit()
            denied = await client.post("/api/v1/auth/google", json={"id_token": "token-for-admin"})
            assert denied.status_code == 403

            # Same Google account can log in even if it changed its email address.
            relog = await client.post("/api/v1/auth/google", json={"id_token": "token-for-linked"})
            assert relog.status_code == 200
            async with SessionLocal() as db:
                row = await db.execute(text("SELECT google_sub FROM users WHERE email = :email"), {"email": linked_email})
                assert row.scalar() == "google-linked-sub-1"
    finally:
        async with SessionLocal() as db:
            if admin_id:
                await db.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": admin_id})
            await db.execute(text("DELETE FROM users WHERE email IN (:a, :b, :c)"), {"a": google_email, "b": linked_email, "c": admin_email})
            await db.commit()


@pytest.mark.asyncio
async def test_google_authorize_and_callback_flow(monkeypatch) -> None:
    email = f"google-cb-{uuid.uuid4().hex[:10]}@gmail.com"

    import app.api.v1 as v1_module

    async def fake_exchange(code: str, client_id: str, client_secret: str, redirect_uri: str) -> dict:
        assert code == "auth-code-1"
        assert client_id == "cb-client-id"
        return {"id_token": "cb-id-token"}

    def fake_verify(token: str, client_id: str) -> dict:
        assert token == "cb-id-token"
        assert client_id == "cb-client-id"
        return {"sub": "google-cb-sub-1", "email": email, "email_verified": True, "name": "Callback Merchant"}

    monkeypatch.setattr(v1_module.settings, "google_client_id", "cb-client-id")
    monkeypatch.setattr(v1_module.settings, "google_client_secret", "cb-secret")
    monkeypatch.setattr(v1_module.settings, "google_redirect_uri", "http://127.0.0.1:8000/api/v1/auth/google/callback")
    monkeypatch.setattr(v1_module, "exchange_authorization_code", fake_exchange)
    monkeypatch.setattr(v1_module, "verify_google_id_token", fake_verify)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False) as client:
            start = await client.get("/api/v1/auth/google/authorize")
            assert start.status_code == 302
            assert start.headers["location"].startswith("https://accounts.google.com/o/oauth2/v2/auth")
            set_cookie = start.headers.get("set-cookie") or ""
            state = set_cookie.split("chmaba_oauth_state=", 1)[1].split(";", 1)[0]
            assert state
            cookie_header = {"cookie": f"chmaba_oauth_state={state}"}

            done = await client.get("/api/v1/auth/google/callback", headers=cookie_header, params={"code": "auth-code-1", "state": state})
            assert done.status_code == 302
            location = done.headers["location"]
            assert "access_token=" in location
            assert "is_new_user=1" in location

            bad_state = await client.get("/api/v1/auth/google/callback", params={"code": "auth-code-1", "state": "wrong"})
            assert bad_state.status_code == 302
            assert "google_error=" in bad_state.headers["location"]
    finally:
        async with SessionLocal() as db:
            await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": email})
            await db.commit()
