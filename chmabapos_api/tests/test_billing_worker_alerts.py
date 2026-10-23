"""The billing worker pages ops when it keeps failing."""
import pytest

import app.main as main_module


@pytest.mark.asyncio
async def test_billing_failure_alert_reaches_telegram(monkeypatch) -> None:
    sent: list[str] = []

    async def fake_send(text: str) -> bool:
        sent.append(text)
        return True

    monkeypatch.setattr(main_module, "send_telegram_message", fake_send)
    await main_module._alert_billing_worker_failure(3)
    assert len(sent) == 1
    assert "3 consecutive failed cycles" in sent[0]
    assert "billing lifecycle worker failed" in sent[0]
