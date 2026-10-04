from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


async def _owner_workspace(client: AsyncClient) -> tuple[dict[str, str], str]:
    email = f"reservations-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Res Owner", "password": "strong-password"})
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Res Co", "store_name": "Main", "country": "Cambodia", "currency_code": "USD", "plan_code": "starter"},
    )
    assert setup.status_code == 201, setup.text
    await client.post(f"/api/v1/mock/chamabapay/{setup.json()['billing_payment']['external_id']}/complete", headers=headers)
    workspace = setup.json()
    return {**headers, "X-Store-ID": workspace["store"]["id"]}, workspace["store"]["id"]


@pytest.mark.asyncio
async def test_reservation_and_waitlist_flow() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, _store = await _owner_workspace(client)
        table = await client.post("/api/v1/dining/tables", headers=headers, json={"name": "T1", "seats": 4})
        assert table.status_code == 201, table.text
        table_id = table.json()["id"]

        booking = await client.post(
            "/api/v1/dining/reservations",
            headers=headers,
            json={"kind": "reservation", "customer_name": "Dara", "party_size": 2, "reserved_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(), "table_id": table_id},
        )
        assert booking.status_code == 201, booking.text
        assert booking.json()["status"] == "booked"
        assert booking.json()["table_name"] == "T1"
        reservation_id = booking.json()["id"]

        waitlist = await client.post("/api/v1/dining/reservations", headers=headers, json={"kind": "waitlist", "customer_name": "Sok", "party_size": 3})
        assert waitlist.status_code == 201, waitlist.text
        assert waitlist.json()["status"] == "waiting"
        assert waitlist.json()["reserved_at"] is None

        rows = await client.get("/api/v1/dining/reservations", headers=headers)
        assert rows.status_code == 200, rows.text
        assert {row["customer_name"] for row in rows.json()} == {"Dara", "Sok"}

        seated = await client.patch(f"/api/v1/dining/reservations/{reservation_id}", headers=headers, json={"status": "seated"})
        assert seated.status_code == 200, seated.text
        tables = await client.get("/api/v1/dining/tables", headers=headers)
        assert next(t for t in tables.json() if t["id"] == table_id)["status"] == "occupied"

        cancelled = await client.patch(f"/api/v1/dining/reservations/{reservation_id}", headers=headers, json={"status": "cancelled"})
        assert cancelled.status_code == 200, cancelled.text
        tables = await client.get("/api/v1/dining/tables", headers=headers)
        assert next(t for t in tables.json() if t["id"] == table_id)["status"] == "available"

        deleted = await client.delete(f"/api/v1/dining/reservations/{reservation_id}", headers=headers)
        assert deleted.status_code == 200, deleted.text

        invalid = await client.post("/api/v1/dining/reservations", headers=headers, json={"customer_name": "X", "status": "nonsense"})
        assert invalid.status_code == 422, invalid.text
