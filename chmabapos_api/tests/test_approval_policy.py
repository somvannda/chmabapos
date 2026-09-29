from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


async def _owner(client: AsyncClient) -> dict[str, str]:
    email = f"approval-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Approval Owner", "password": "strong-password"})
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Approval Store", "store_name": "Main", "country": "Cambodia", "currency_code": "USD", "plan_code": "starter"},
    )
    assert setup.status_code == 201, setup.text
    await client.post(f"/api/v1/mock/chamabapay/{setup.json()['billing_payment']['external_id']}/complete", headers=headers)
    return headers


def _policy_body(**rules: dict) -> dict:
    return {
        "enabled": True,
        "maker_checker": True,
        "expiry_minutes": 30,
        "notify_in_app": True,
        "notify_telegram": True,
        "rules": rules,
    }


@pytest.mark.asyncio
async def test_default_policy_is_unavailable_for_a_solo_owner() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _owner(client)
        response = await client.get("/api/v1/approval-policy", headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["available"] is False
        assert body["team_size"] == 1
        assert body["policy"]["enabled"] is False
        assert Decimal(body["policy"]["rules"]["refund"]["threshold"]) == Decimal("50")
        assert body["policy"]["rules"]["discount"]["mode"] == "review"
        assert body["policy"]["rules"]["price_cost_edit"]["approvers"] == ["owner"]


@pytest.mark.asyncio
async def test_owner_can_update_the_policy_and_it_is_audited() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _owner(client)
        payload = _policy_body(
            refund={"mode": "approval", "threshold": "75", "approvers": ["owner", "manager"]},
            discount={"mode": "off", "threshold": None, "approvers": ["owner"]},
        )
        updated = await client.put("/api/v1/approval-policy", headers=headers, json=payload)
        assert updated.status_code == 200, updated.text
        assert updated.json()["policy"]["enabled"] is True
        assert Decimal(updated.json()["policy"]["rules"]["refund"]["threshold"]) == Decimal("75")

        reloaded = await client.get("/api/v1/approval-policy", headers=headers)
        assert reloaded.json()["policy"]["rules"]["refund"]["mode"] == "approval"
        assert reloaded.json()["policy"]["rules"]["discount"]["mode"] == "off"

        logs = await client.get("/api/v1/audit-logs", headers=headers)
        assert logs.status_code == 200, logs.text
        assert any(row["action"] == "approval_policy_updated" for row in logs.json())


@pytest.mark.asyncio
async def test_unknown_actions_are_rejected() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _owner(client)
        response = await client.put("/api/v1/approval-policy", headers=headers, json=_policy_body(nonsense={"mode": "review", "threshold": None, "approvers": ["owner"]}))
        assert response.status_code == 400, response.text


@pytest.mark.asyncio
async def test_a_live_mode_needs_an_approver() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _owner(client)
        response = await client.put("/api/v1/approval-policy", headers=headers, json=_policy_body(refund={"mode": "approval", "threshold": "50", "approvers": []}))
        assert response.status_code == 400, response.text
