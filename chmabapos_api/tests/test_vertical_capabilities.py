from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app
from app.verticals import CAPABILITY_LABELS, capabilities_for, default_capabilities


def test_capabilities_come_from_the_business_type() -> None:
    assert "serials" in capabilities_for("electronics")
    assert "modifiers" not in capabilities_for("electronics")
    assert {"unit_of_measure", "batches"} <= set(capabilities_for("mart"))
    assert {"modifiers", "tables"} <= set(capabilities_for("restaurant"))
    assert "tables" not in capabilities_for("coffee")
    assert "tables" not in capabilities_for("electronics")
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


def test_default_capabilities_are_independent_of_overrides() -> None:
    assert default_capabilities("coffee") == ("variants", "modifiers")
    assert default_capabilities("electronics") == ("barcode", "brand", "variants", "serials")
    assert default_capabilities("general") == ()
    assert default_capabilities(None) == ()
    assert default_capabilities("bogus") == ()


def test_store_preferences_delta_overrides() -> None:
    # Add a pack the vertical lacks.
    added = capabilities_for("coffee", {"capability_overrides": {"added": ["serials"]}})
    assert "serials" in added and "modifiers" in added
    # Remove a default pack.
    removed = capabilities_for("coffee", {"capability_overrides": {"removed": ["modifiers"]}})
    assert "modifiers" not in removed and "variants" in removed
    # Add and remove combine; unknown keys and junk never leak back.
    assert capabilities_for("general", {"capability_overrides": {"added": ["barcode", "nope", 42]}}) == ("barcode",)
    # Empty overrides fall back to the business type.
    assert capabilities_for("mart", {"capability_overrides": {}}) == capabilities_for("mart")
    # A delta takes precedence over a stale absolute list.
    mixed = capabilities_for("coffee", {"capabilities": ["serials"], "capability_overrides": {"added": ["barcode"]}})
    assert "barcode" in mixed and "serials" not in mixed and "variants" in mixed
    # Junk override shapes are ignored rather than crashing the read.
    assert capabilities_for("coffee", {"capability_overrides": "serials"}) == capabilities_for("coffee")
    # Order stays canonical.
    caps = capabilities_for("general", {"capability_overrides": {"added": ["serials", "barcode"]}})
    assert list(caps) == [key for key in CAPABILITY_LABELS if key in caps]


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
            assert "serials" in setup.json()["capability_defaults"]

            current = await client.get("/api/v1/workspaces/current", headers=headers)
            assert current.status_code == 200
            caps = current.json()["capabilities"]
            assert "serials" in caps
            assert "modifiers" not in caps
            assert "serials" in current.json()["capability_defaults"]
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
async def test_setup_seeds_capability_answers_and_profile() -> None:
    email = f"seed-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Seed Owner", "password": "strong-password"})
            assert register.status_code == 201
            await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            setup = await client.post(
                "/api/v1/workspaces/setup",
                headers=headers,
                json={
                    "company_name": "Seed General",
                    "store_name": "Main",
                    "currency_code": "USD",
                    "plan_code": "free",
                    "vertical": "general",
                    "store_count_band": "2-5",
                    "team_size_band": "11-99",
                    "capability_answers": ["barcode", "nope"],
                },
            )
            assert setup.status_code == 201
            company_id = setup.json()["company"]["id"]
            # "general" has no defaults, so the opted-in pack is seeded (junk dropped).
            assert setup.json()["capability_defaults"] == []
            assert setup.json()["capabilities"] == ["barcode"]

            current = await client.get("/api/v1/workspaces/current", headers=headers)
            assert current.status_code == 200
            profile = current.json()["store"]["preferences"]["onboarding_profile"]
            assert profile["store_count_band"] == "2-5"
            assert profile["team_size_band"] == "11-99"
            assert profile["capability_answers"] == ["barcode"]
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
