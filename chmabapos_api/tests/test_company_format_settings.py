from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_company_date_and_time_format_round_trip() -> None:
    """The merchant's date/time choice persists, is shared via the workspace
    read, and clearing it falls back to the device default."""
    email = f"format-test-{uuid.uuid4().hex[:10]}@example.com"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Format Owner", "password": "strong-password"})
        assert register.status_code == 201
        verify = await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
        assert verify.status_code == 200

        login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        setup = await client.post(
            "/api/v1/workspaces/setup",
            headers=headers,
            json={"company_name": "Format Co", "store_name": "Main", "country": "Cambodia", "currency_code": "USD", "plan_code": "free"},
        )
        assert setup.status_code == 201
        workspace = setup.json()
        store_headers = {**headers, "X-Store-ID": workspace["store"]["id"]}

        # Untouched workspace keeps the device default.
        assert workspace["company"]["date_format"] == ""
        assert workspace["company"]["time_format"] == ""

        # Choosing a format also updates the free country field.
        updated = await client.patch(
            "/api/v1/company",
            headers=headers,
            json={"date_format": "DD/MM/YYYY", "time_format": "24h", "country": "Thailand"},
        )
        assert updated.status_code == 200, updated.text
        body = updated.json()
        assert body["date_format"] == "DD/MM/YYYY"
        assert body["time_format"] == "24h"
        assert body["country"] == "Thailand"

        # Persisted and visible through the workspace read used by the app.
        current = await client.get("/api/v1/workspaces/current", headers=store_headers)
        assert current.status_code == 200
        assert current.json()["company"]["date_format"] == "DD/MM/YYYY"
        assert current.json()["company"]["time_format"] == "24h"

        # Empty clears the override back to the device default.
        cleared = await client.patch("/api/v1/company", headers=headers, json={"date_format": "", "time_format": ""})
        assert cleared.status_code == 200
        assert cleared.json()["date_format"] == ""
        assert cleared.json()["time_format"] == ""

        # Unknown formats are rejected rather than swallowed.
        bad = await client.patch("/api/v1/company", headers=headers, json={"date_format": "YYYY/MM/DD"})
        assert bad.status_code == 422
