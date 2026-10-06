"""Loyalty points: redeem deducts atomically and refuses to overspend."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_redeem_points_deducts_and_rejects_overspend() -> None:
    company_id = None
    email = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Loyalty Store", "Main", plan="starter", email_prefix="loyalty")
            email, company_id = ctx["email"], ctx["company_id"]
            headers = ctx["headers"]
            customer = (await client.post("/api/v1/customers", headers=headers, json={"name": "Loyal Bo", "email": f"loyal-{uuid.uuid4().hex[:8]}@example.com"})).json()

            granted = await client.patch(f"/api/v1/customers/{customer['id']}/points", headers=headers, json={"delta": 100})
            assert granted.status_code == 200, granted.text
            assert granted.json()["points"] == 100

            redeem = await client.post(f"/api/v1/customers/{customer['id']}/redeem?points=40", headers=headers)
            assert redeem.status_code == 200, redeem.text
            assert redeem.json()["points_used"] == 40
            assert redeem.json()["points_left"] == 60

            over = await client.post(f"/api/v1/customers/{customer['id']}/redeem?points=1000", headers=headers)
            assert over.status_code == 409, over.text
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
