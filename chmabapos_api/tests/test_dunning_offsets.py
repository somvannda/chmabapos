"""The reminder cadence is configurable without changing the default."""
from app.config import settings
from app.services.reminders import DEFAULT_REMINDER_OFFSETS, reminder_offsets


def test_reminder_offsets_parse_and_drop_invalid_values(monkeypatch) -> None:
    monkeypatch.setattr(settings, "billing_reminder_offsets", " 14, 3,3, bad, 0, 400 ")
    assert reminder_offsets() == (14, 3)


def test_reminder_offsets_fall_back_to_the_historical_cadence(monkeypatch) -> None:
    monkeypatch.setattr(settings, "billing_reminder_offsets", "")
    assert reminder_offsets() == DEFAULT_REMINDER_OFFSETS
