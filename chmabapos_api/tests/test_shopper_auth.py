"""Shopper sign-in with an emailed code.

Covers the two things most likely to be got wrong: that the endpoints cannot be
used to discover who shops here, and that a shopper identity is genuinely separate
from a staff one.
"""
from __future__ import annotations

import re
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text

from app.db import SessionLocal
from app.main import app
from app.models import EmailSend, EmailSuppression, ShopperAccount, ShopperAddress
from app.security import decode_token


async def _latest_code(email: str) -> str | None:
    async with SessionLocal() as db:
        row = (
            await db.execute(
                select(EmailSend)
                .where(EmailSend.recipient_email == email, EmailSend.source == "shopper_signin")
                .order_by(EmailSend.created_at.desc())
            )
        ).scalars().first()
    if row is None:
        return None
    match = re.search(r"<strong>(\d{6})</strong>", row.body_html or "")
    return match.group(1) if match else None


async def _purge(email: str) -> None:
    async with SessionLocal() as db:
        await db.execute(text("DELETE FROM shopper_email_codes WHERE shopper_id IN (SELECT id FROM shopper_accounts WHERE email = :e)"), {"e": email})
        await db.execute(text("DELETE FROM shopper_addresses WHERE shopper_id IN (SELECT id FROM shopper_accounts WHERE email = :e)"), {"e": email})
        await db.execute(text("DELETE FROM shopper_accounts WHERE email = :e"), {"e": email})
        await db.execute(text("DELETE FROM email_suppressions WHERE lower(email) = lower(:e)"), {"e": email})
        await db.execute(text("DELETE FROM email_sends WHERE recipient_email = :e"), {"e": email})
        await db.commit()


async def _signin(client: AsyncClient, email: str) -> dict[str, str]:
    assert (await client.post("/api/v1/public/auth/email-code", json={"email": email})).status_code == 202
    code = await _latest_code(email)
    assert code
    verified = await client.post("/api/v1/public/auth/verify", json={"email": email, "code": code})
    assert verified.status_code == 200, verified.text
    return {"Authorization": f"Bearer {verified.json()['access_token']}"}


@pytest.mark.asyncio
async def test_shopper_signs_in_with_an_emailed_code() -> None:
    email = f"shopper-{uuid.uuid4().hex[:10]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            requested = await client.post("/api/v1/public/auth/email-code", json={"email": email})
            assert requested.status_code == 202, requested.text
            assert requested.json() == {"status": "code_sent"}

            code = await _latest_code(email)
            assert code, "a sign-in code should have been queued"

            verified = await client.post("/api/v1/public/auth/verify", json={"email": email, "code": code})
            assert verified.status_code == 200, verified.text
            body = verified.json()
            assert body["shopper"]["email"] == email
            assert body["shopper"]["is_email_verified"] is True

            # The token is a shopper token, not a staff access token. This is what
            # keeps the two identity systems from being interchangeable.
            payload = decode_token(body["access_token"])
            assert payload["type"] == "shopper"

            # ... and a staff endpoint must refuse it. The reverse (a staff token
            # on a shopper endpoint) is enforced by the same type check.
            staff = await client.get(
                "/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
            )
            assert staff.status_code == 401, f"a shopper token must not authenticate staff: {staff.text}"

            # Codes are single use.
            reused = await client.post("/api/v1/public/auth/verify", json={"email": email, "code": code})
            assert reused.status_code == 400, reused.text

            # The token identifies the shopper, but only to shopper endpoints.
            me = await client.get("/api/v1/public/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
            assert me.status_code == 200, me.text
            assert me.json()["email"] == email
            assert me.json()["id"] == body["shopper"]["id"]
            # ... and says nothing beyond what the shopper may see about themselves.
            assert "google_sub" not in me.json() and "telegram_id" not in me.json()
    finally:
        await _purge(email)


@pytest.mark.asyncio
async def test_code_request_does_not_reveal_whether_an_account_exists() -> None:
    known = f"shopper-known-{uuid.uuid4().hex[:10]}@example.com"
    unknown = f"shopper-unknown-{uuid.uuid4().hex[:10]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            first = await client.post("/api/v1/public/auth/email-code", json={"email": known})
            assert first.status_code == 202

            # The same call for an address nobody has used must look identical.
            second = await client.post("/api/v1/public/auth/email-code", json={"email": unknown})
            assert second.status_code == first.status_code
            assert second.json() == first.json()

            # A wrong code is refused, and says the same thing an unknown account
            # would: one message for every failure, so it cannot be used to probe.
            wrong = await client.post("/api/v1/public/auth/verify", json={"email": known, "code": "000000"})
            assert wrong.status_code == 400
            missing = await client.post("/api/v1/public/auth/verify", json={"email": unknown, "code": "000000"})
            assert missing.status_code == 400
            assert missing.json()["detail"] == wrong.json()["detail"]
    finally:
        await _purge(known)
        await _purge(unknown)


@pytest.mark.asyncio
async def test_shopper_signup_stores_name_and_phone_without_overwriting_on_signin() -> None:
    email = f"shopper-signup-{uuid.uuid4().hex[:10]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.post("/api/v1/public/auth/email-code", json={"email": email})).status_code == 202
            code = await _latest_code(email)
            assert code
            created = await client.post(
                "/api/v1/public/auth/verify",
                json={"email": email, "code": code, "full_name": "Sokha Dara", "phone": "+855 12 345 678"},
            )
            assert created.status_code == 200, created.text
            assert created.json()["shopper"]["full_name"] == "Sokha Dara"
            assert created.json()["shopper"]["phone"] == "+855 12 345 678"

            # A later sign-in with different details is a sign-in, not a rename.
            assert (await client.post("/api/v1/public/auth/email-code", json={"email": email})).status_code == 202
            code = await _latest_code(email)
            signed_in = await client.post(
                "/api/v1/public/auth/verify",
                json={"email": email, "code": code, "full_name": "Someone Else", "phone": "+855 99 999 999"},
            )
            assert signed_in.status_code == 200, signed_in.text
            assert signed_in.json()["shopper"]["full_name"] == "Sokha Dara"
            assert signed_in.json()["shopper"]["phone"] == "+855 12 345 678"
    finally:
        await _purge(email)


@pytest.mark.asyncio
async def test_shopper_can_update_their_name_and_phone() -> None:
    email = f"shopper-profile-{uuid.uuid4().hex[:10]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.post("/api/v1/public/auth/email-code", json={"email": email})).status_code == 202
            verified = await client.post("/api/v1/public/auth/verify", json={"email": email, "code": await _latest_code(email)})
            assert verified.status_code == 200, verified.text
            headers = {"Authorization": f"Bearer {verified.json()['access_token']}"}

            patched = await client.patch(
                "/api/v1/public/auth/me",
                headers=headers,
                json={"full_name": "Dara Sok", "phone": "+855 92 111 222"},
            )
            assert patched.status_code == 200, patched.text
            assert patched.json()["full_name"] == "Dara Sok"
            assert patched.json()["phone"] == "+855 92 111 222"

            me = await client.get("/api/v1/public/auth/me", headers=headers)
            assert me.json()["full_name"] == "Dara Sok"
            assert me.json()["phone"] == "+855 92 111 222"
    finally:
        await _purge(email)


@pytest.mark.asyncio
async def test_public_config_returns_only_browser_safe_values() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/public/config")
        assert response.status_code == 200
        assert set(response.json()) == {"google_client_id"}


@pytest.mark.asyncio
async def test_shopper_addresses_crud_and_default() -> None:
    email = f"shopper-address-{uuid.uuid4().hex[:10]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await _signin(client, email)

            first = await client.post(
                "/api/v1/public/auth/addresses",
                headers=headers,
                json={"recipient_name": "Dara", "line1": "12 Street 1", "city": "Phnom Penh"},
            )
            assert first.status_code == 201, first.text
            assert first.json()["is_default"] is True

            second = await client.post(
                "/api/v1/public/auth/addresses",
                headers=headers,
                json={"label": "Office", "recipient_name": "Dara", "line1": "88 Street 2", "is_default": True},
            )
            assert second.status_code == 201, second.text
            listed = await client.get("/api/v1/public/auth/addresses", headers=headers)
            assert [row["is_default"] for row in listed.json()] == [True, False]
            assert listed.json()[0]["id"] == second.json()["id"]

            patched = await client.patch(
                f"/api/v1/public/auth/addresses/{second.json()['id']}",
                headers=headers,
                json={"label": "Warehouse"},
            )
            assert patched.status_code == 200, patched.text
            assert patched.json()["label"] == "Warehouse"

            assert (await client.delete(f"/api/v1/public/auth/addresses/{second.json()['id']}", headers=headers)).status_code == 204
            remaining = (await client.get("/api/v1/public/auth/addresses", headers=headers)).json()
            assert len(remaining) == 1
            assert remaining[0]["is_default"] is True
    finally:
        await _purge(email)


@pytest.mark.asyncio
async def test_shopper_marketing_consent_uses_suppression_list() -> None:
    email = f"shopper-consent-{uuid.uuid4().hex[:10]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await _signin(client, email)
            opted_in = await client.patch("/api/v1/public/auth/me", headers=headers, json={"marketing_opt_in": True})
            assert opted_in.status_code == 200
            assert opted_in.json()["marketing_opt_in"] is True
            opted_out = await client.patch("/api/v1/public/auth/me", headers=headers, json={"marketing_opt_in": False})
            assert opted_out.status_code == 200
            assert opted_out.json()["marketing_opt_in"] is False

        async with SessionLocal() as db:
            suppressed = (await db.execute(select(EmailSuppression).where(func.lower(EmailSuppression.email) == email))).scalar_one_or_none()
            assert suppressed is not None
            assert suppressed.reason == "unsubscribed"
    finally:
        await _purge(email)


@pytest.mark.asyncio
async def test_shopper_export_includes_profile_and_addresses() -> None:
    email = f"shopper-export-{uuid.uuid4().hex[:10]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await _signin(client, email)
            await client.post(
                "/api/v1/public/auth/addresses",
                headers=headers,
                json={"recipient_name": "Dara", "line1": "12 Street 1"},
            )
            exported = await client.get("/api/v1/public/auth/export", headers=headers)
            assert exported.status_code == 200
            assert "attachment" in exported.headers["content-disposition"]
            body = exported.json()
            assert body["profile"]["email"] == email
            assert len(body["addresses"]) == 1
            assert "orders" in body and "conversations" in body
    finally:
        await _purge(email)


@pytest.mark.asyncio
async def test_shopper_can_delete_account_and_is_anonymised() -> None:
    email = f"shopper-delete-{uuid.uuid4().hex[:10]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await _signin(client, email)
            me = await client.get("/api/v1/public/auth/me", headers=headers)
            shopper_id = me.json()["id"]
            await client.post(
                "/api/v1/public/auth/addresses",
                headers=headers,
                json={"recipient_name": "Dara", "line1": "12 Street 1"},
            )

            refused = await client.post("/api/v1/public/auth/delete-account", headers=headers, json={"confirm_email": "wrong@example.com"})
            assert refused.status_code == 400

            deleted = await client.post("/api/v1/public/auth/delete-account", headers=headers, json={"confirm_email": email})
            assert deleted.status_code == 204, deleted.text

            # The session died with the account.
            assert (await client.get("/api/v1/public/auth/me", headers=headers)).status_code == 401

        async with SessionLocal() as db:
            assert (await db.execute(select(ShopperAccount).where(ShopperAccount.email == email))).scalar_one_or_none() is None
            from uuid import UUID as _UUID
            assert (await db.execute(select(ShopperAddress).where(ShopperAddress.shopper_id == _UUID(shopper_id)))).scalars().all() == []
    finally:
        await _purge(email)
