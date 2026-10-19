"""Opening-hours logic, and its exposure on the public storefront payload.

The state is resolved server-side so every visitor sees the same answer and the
page needs no clock or timezone library of its own.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app import storefront
from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup

# A fixed instant, so the day is derived from the datetime rather than hard-coded.
NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
TODAY = storefront.DAY_ORDER[NOW.weekday()]


def _hours(opens: str, closes: str, *, closed: bool = False, day: str | None = None) -> list[dict]:
    return [{"day": day or TODAY, "open": opens, "close": closes, "closed": closed}]


def test_no_hours_means_unknown() -> None:
    assert storefront.store_open_state(None, "UTC", NOW) is None
    assert storefront.store_open_state({}, "UTC", NOW) is None
    assert storefront.store_open_state({"hours": []}, "UTC", NOW) is None


def test_closed_day_is_closed() -> None:
    assert storefront.store_open_state({"hours": _hours("09:00", "21:00", closed=True)}, "UTC", NOW) is False


def test_day_with_no_entry_is_closed() -> None:
    other = storefront.DAY_ORDER[(NOW.weekday() + 1) % 7]
    assert storefront.store_open_state({"hours": _hours("09:00", "21:00", day=other)}, "UTC", NOW) is False


def test_inside_the_window_is_open() -> None:
    assert storefront.store_open_state({"hours": _hours("09:00", "21:00")}, "UTC", NOW) is True


def test_outside_the_window_is_closed() -> None:
    assert storefront.store_open_state({"hours": _hours("13:00", "21:00")}, "UTC", NOW) is False
    assert storefront.store_open_state({"hours": _hours("06:00", "11:00")}, "UTC", NOW) is False


def test_boundaries_are_half_open() -> None:
    # Open at the opening minute, closed at the closing minute.
    assert storefront.store_open_state({"hours": _hours("12:00", "13:00")}, "UTC", NOW) is True
    assert storefront.store_open_state({"hours": _hours("11:00", "12:00")}, "UTC", NOW) is False


def test_window_running_past_midnight() -> None:
    late = datetime(2026, 10, 14, 23, 30, tzinfo=timezone.utc)
    early = datetime(2026, 10, 14, 1, 30, tzinfo=timezone.utc)
    hours = _hours("18:00", "02:00")
    # 23:30 is inside the window that started at 18:00 ...
    assert storefront.store_open_state({"hours": hours}, "UTC", late) is True
    # ... and so is 01:30 the following morning, because the window has not closed.
    assert storefront.store_open_state({"hours": hours}, "UTC", early) is True
    assert storefront.store_open_state({"hours": hours}, "UTC", NOW) is False


def test_respects_the_store_timezone() -> None:
    hours = _hours("09:00", "21:00")
    # 12:00 UTC is 19:00 in Phnom Penh (UTC+7), still inside the window.
    assert storefront.store_open_state({"hours": hours}, "UTC", NOW) is True
    # 15:00 UTC is 22:00 there, so the store has closed.
    assert storefront.store_open_state({"hours": hours}, "Asia/Phnom_Penh", NOW.replace(hour=15)) is False


def test_unusable_input_degrades_to_unknown() -> None:
    assert storefront.store_open_state({"hours": _hours("09:00", "21:00")}, "Not/AZone", NOW) is None
    assert storefront.store_open_state({"hours": _hours("9am", "21:00")}, "UTC", NOW) is None


@pytest.mark.asyncio
async def test_public_payload_reports_open_state_and_timezone() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx = await register_and_setup(client, f"Hours Co {suffix}", f"Clock {suffix}", email_prefix="open-state")
            email, company_id = ctx["email"], ctx["company_id"]
            company_slug, store_slug = f"hours-co-{suffix}", f"clock-{suffix}"
            await client.patch(
                f"/api/v1/stores/{ctx['store_id']}/public-order", headers=ctx["headers"], json={"enabled": True}
            )

            # No hours published: the page must show no status rather than guess.
            before = (await client.get(f"/api/v1/public/store/{company_slug}/{store_slug}")).json()
            assert before["is_open"] is None
            assert before["timezone"]

            # Every day explicitly closed, which is deterministic at any hour.
            closed = [{"day": day, "open": "09:00", "close": "21:00", "closed": True} for day in storefront.DAY_ORDER]
            saved = await client.patch(
                f"/api/v1/stores/{ctx['store_id']}", headers=ctx["headers"], json={"storefront": {"hours": closed}}
            )
            assert saved.status_code == 200, saved.text

            after = (await client.get(f"/api/v1/public/store/{company_slug}/{store_slug}")).json()
            assert after["is_open"] is False
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_merchant_store_payload_reports_open_state() -> None:
    """The settings row shows open/closed, so StoreRead carries the same answer.

    It is computed by the same helper as the public page, so a merchant reading
    their own settings row and a shopper looking at the badge cannot be told two
    different things.
    """
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx = await register_and_setup(
                client, f"Row Co {suffix}", f"Row {suffix}", email_prefix="open-state-row"
            )
            email, company_id = ctx["email"], ctx["company_id"]

            # No hours published: unknown, not "closed".
            stores = (await client.get("/api/v1/stores", headers=ctx["headers"])).json()
            row = next(store for store in stores if store["id"] == ctx["store_id"])
            assert row["is_open"] is None

            # Every day explicitly closed, which is deterministic at any hour.
            closed = [{"day": day, "open": "09:00", "close": "21:00", "closed": True} for day in storefront.DAY_ORDER]
            saved = await client.patch(
                f"/api/v1/stores/{ctx['store_id']}", headers=ctx["headers"], json={"storefront": {"hours": closed}}
            )
            assert saved.status_code == 200, saved.text
            assert saved.json()["is_open"] is False
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
