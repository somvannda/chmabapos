from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1 import _local_day, _report_window


def test_report_window_is_the_local_calendar_day_in_the_store_timezone() -> None:
    # Default Cambodia store is UTC+7; a local day must be the local calendar day,
    # not the UTC day (which would shift the first/last hours into the wrong bucket).
    store = SimpleNamespace(timezone="Asia/Phnom_Penh")
    start_date, end_date, start_at, end_at = _report_window(store, date(2026, 10, 5), date(2026, 10, 5))

    assert (start_date, end_date) == (date(2026, 10, 5), date(2026, 10, 5))
    # 2026-10-05 00:00 +07:00 == 2026-10-04 17:00 UTC
    assert start_at.astimezone(timezone.utc) == datetime(2026, 10, 4, 17, 0, tzinfo=timezone.utc)
    assert end_at - start_at == timedelta(days=1)


def test_report_window_defaults_to_month_start_and_rejects_inverted_ranges() -> None:
    store = SimpleNamespace(timezone="UTC")
    start_date, end_date, start_at, end_at = _report_window(store, None, date(2026, 10, 5))
    assert (start_date, end_date) == (date(2026, 10, 1), date(2026, 10, 5))
    assert start_at == datetime(2026, 10, 1, tzinfo=timezone.utc)
    assert end_at == datetime(2026, 10, 6, tzinfo=timezone.utc)

    with pytest.raises(HTTPException):
        _report_window(store, date(2026, 10, 5), date(2026, 10, 1))


def test_local_day_buckets_a_utc_timestamp_into_the_store_local_day() -> None:
    # 2026-10-04 17:30 UTC is 2026-10-05 00:30 in Phnom Penh (UTC+7); the order
    # must be attributed to the 5th, matching the _report_window they fall in.
    store = SimpleNamespace(timezone="Asia/Phnom_Penh")
    assert _local_day(store, datetime(2026, 10, 4, 17, 30, tzinfo=timezone.utc)) == "2026-10-05"
    assert _local_day(store, datetime(2026, 10, 4, 16, 30, tzinfo=timezone.utc)) == "2026-10-04"


def test_local_day_falls_back_to_utc_for_utc_and_unknown_timezones() -> None:
    when = datetime(2026, 10, 5, 3, 0, tzinfo=timezone.utc)
    assert _local_day(SimpleNamespace(timezone="UTC"), when) == "2026-10-05"
    assert _local_day(SimpleNamespace(timezone="Not/AZone"), when) == "2026-10-05"
