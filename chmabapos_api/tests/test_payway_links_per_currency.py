"""A merchant can hold an ABA PayWay link per currency.

ABA PayWay settles one currency per link, so a merchant who prices in riel needs a
KHR link beside the USD one. This covers the storage map, saving both in one call,
removing one without touching the other, and the legacy USD columns staying in step
while the rest of the app migrates to the map.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup

USD_LINK = "https://link.payway.com.kh/ABAPAYusd001"
KHR_LINK = "https://link.payway.com.kh/ABAPAYkhr001"


@pytest.mark.asyncio
async def test_a_store_holds_a_link_per_currency() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Payway Store", "Main", plan="free", email_prefix="payway")
            email, company_id = ctx["email"], ctx["company_id"]
            store_id = ctx["store_id"]
            headers = ctx["headers"]

            # Both currencies saved in one call.
            saved = await client.patch(
                f"/api/v1/stores/{store_id}", headers=headers, json={"aba_payway_links": {"USD": USD_LINK, "KHR": KHR_LINK}}
            )
            assert saved.status_code == 200, saved.text
            body = saved.json()
            assert set(body["aba_payway_links"]) == {"USD", "KHR"}
            assert body["aba_payway_links"]["KHR"]["link"] == KHR_LINK
            assert body["aba_payway_links"]["KHR"]["status"] in {"active", "pending"}
            assert body["aba_payway_links"]["USD"]["link"] == USD_LINK
            # The legacy USD view stays in step, so current readers keep working.
            assert body["aba_payway_link"] == USD_LINK

            # Removing one currency leaves the other alone.
            removed = await client.patch(
                f"/api/v1/stores/{store_id}", headers=headers, json={"aba_payway_links": {"KHR": None}}
            )
            assert removed.status_code == 200, removed.text
            after = removed.json()
            assert "KHR" not in after["aba_payway_links"], after["aba_payway_links"]
            assert after["aba_payway_links"]["USD"]["link"] == USD_LINK
            assert after["aba_payway_link"] == USD_LINK, "clearing KHR must not clear USD"

            # The old single-link field still works, and lands in the map's USD entry.
            legacy = await client.patch(
                f"/api/v1/stores/{store_id}", headers=headers, json={"aba_payway_link": "https://link.payway.com.kh/ABAPAYlegacy"}
            )
            assert legacy.status_code == 200, legacy.text
            assert legacy.json()["aba_payway_links"]["USD"]["link"] == "https://link.payway.com.kh/ABAPAYlegacy"
    finally:
        await cleanup_company(company_id, [email] if email else [])
