from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app
from app.verticals import CAPABILITY_LABELS, capabilities_for


def test_capabilities_come_from_the_business_type() -> None:
    assert "serials" in capabilities_for("electronics")
    assert "modifiers" not in capabilities_for("electronics")
    assert {"unit_of_measure", "batches"} <= set(capabilities_for("mart"))
    assert "modifiers" in capabilities_for("restaurant")
    # A plain "general" store gets core only, and so does an unknown value.
    assert capabilities_for("general") == ()
    assert capabilities_for("bogus") == ()
    assert capabilities_for(None) == ()


def test_capabilities_are_returned_in_canonical_order() -> None:
    caps = capabilities_for("mart")
    assert list(caps) == [key for key in CAPABILITY_LABELS if key in caps]


def test_store_preferences_can_override_capabilities() -> None:
    # A mixed business can add a pack its vertical does not include.
    assert "serials" in capabilities_for("restaurant", {"capabilities": ["serials", "modifiers"]})
    # ...and can drop one it does.
    assert "modifiers" not in capabilities_for("coffee", {"capabilities": ["variants"]})
    # An explicit empty list means "no packs", not "fall back to defaults".
    assert capabilities_for("coffee", {"capabilities": []}) == ()
    # Unknown keys and junk values are ignored, never echoed back.
    assert capabilities_for("coffee", {"capabilities": ["nope", 42]}) == ()
    # A non-list override is ignored rather than crashing the read.
    assert capabilities_for("coffee", {"capabilities": "serials"}) == capabilities_for("coffee")


def test_every_vertical_maps_only_to_known_capabilities() -> None:
    from app.verticals import VERTICAL_CAPABILITIES

    for packs in VERTICAL_CAPABILITIES.values():
        assert set(packs) <= set(CAPABILITY_LABELS)


@pytest.mark.asyncio
async def test_workspace_exposes_capabilities_for_the_business_type() -> None:
    email = f"caps-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Caps Owner", "password": "strong-password"})
            assert register.status_code == 201
            await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            setup = await client.post(
                "/api/v1/workspaces/setup",
                headers=headers,
                json={"company_name": "Caps Electronics", "store_name": "Main", "currency_code": "USD", "plan_code": "free", "vertical": "electronics"},
            )
            assert setup.status_code == 201
            company_id = setup.json()["company"]["id"]
            assert "serials" in setup.json()["capabilities"]

            current = await client.get("/api/v1/workspaces/current", headers=headers)
            assert current.status_code == 200
            caps = current.json()["capabilities"]
            assert "serials" in caps
            assert "modifiers" not in caps
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
