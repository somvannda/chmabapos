from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from app.billing import recommend_plan
from app.features import derive_plan_marketing_features
from app.main import app


def _plan(code: str, price, stores: int, members: int) -> SimpleNamespace:
    return SimpleNamespace(code=code, monthly_price=price, max_stores=stores, max_members=members)


PLANS = [
    _plan("free", Decimal("0.00"), 1, 1),
    _plan("starter", Decimal("0.99"), 5, 10),
    _plan("pro", Decimal("4.99"), 50, 99),
]


def test_recommend_plan_by_bands() -> None:
    assert recommend_plan(PLANS, "1", "1").code == "free"
    assert recommend_plan(PLANS, "2-5", "2-10").code == "starter"
    assert recommend_plan(PLANS, "6-50", "11-99").code == "pro"
    # Unknown/missing bands fall back to the entry tier.
    assert recommend_plan(PLANS, None, None).code == "free"
    assert recommend_plan(PLANS, "bogus", "bogus").code == "free"
    # Nothing covers the answer -> the largest plan, not nothing.
    assert recommend_plan(PLANS, "50+", "100+").code == "pro"
    # No plans at all.
    assert recommend_plan([], "1", "1") is None


@pytest.mark.asyncio
async def test_recommended_plan_endpoint() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        entry = await client.get("/api/v1/plans/recommended")
        assert entry.status_code == 200
        assert entry.json()["code"] == "free"

        growing = await client.get("/api/v1/plans/recommended", params={"stores": "2-5", "team": "2-10"})
        assert growing.status_code == 200
        assert growing.json()["code"] == "starter"

        big = await client.get("/api/v1/plans/recommended", params={"stores": "6-50", "team": "100+"})
        assert big.status_code == 200
        assert big.json()["code"] == "pro"

def test_quota_bullet_matches_the_prepaid_period() -> None:
    paid = derive_plan_marketing_features(
        max_stores=5,
        max_members=10,
        transaction_limit=15000,
        capabilities={},
        monthly_price=Decimal("0.99"),
    )
    assert "15,000 transactions per billing period" in paid
    assert all("per month" not in bullet for bullet in paid)

    free = derive_plan_marketing_features(
        max_stores=1,
        max_members=1,
        transaction_limit=3000,
        capabilities={},
        monthly_price=Decimal("0.00"),
    )
    assert "3,000 transactions" in free
    assert all("per month" not in bullet for bullet in free)
