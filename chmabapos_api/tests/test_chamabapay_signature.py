import hashlib
import hmac
import time

from app.api import v1


def _signed(body: bytes, secret: str, timestamp: int | None = None) -> str:
    ts = str(timestamp if timestamp is not None else int(time.time()))
    digest = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"


def test_valid_signature_accepted() -> None:
    body = b'{"type":"payment.completed"}'
    assert v1.signature_is_valid(body, _signed(body, "whsec_test"), "whsec_test", "mock", "development") is True
    assert v1.signature_failure_reason(body, _signed(body, "whsec_test"), "whsec_test", "mock", "development") is None


def test_wrong_secret_rejected() -> None:
    body = b"{}"
    reason = v1.signature_failure_reason(body, _signed(body, "whsec_other"), "whsec_test", "mock", "development")
    assert reason == "the signature does not match the configured secret"


def test_stale_timestamp_rejected() -> None:
    body = b"{}"
    signature = _signed(body, "whsec_test", timestamp=int(time.time()) - 3600)
    assert v1.signature_failure_reason(body, signature, "whsec_test", "mock", "development") == "the signature timestamp is stale"


def test_malformed_header_rejected() -> None:
    assert v1.signature_failure_reason(b"{}", "not-a-signature", "whsec_test", "mock", "development") == "the signature header is malformed"


def test_missing_header_rejected_when_secret_set() -> None:
    assert v1.signature_failure_reason(b"{}", "", "whsec_test", "mock", "development") == "the signature header is missing"


def test_missing_secret_live_rejected() -> None:
    assert v1.signature_failure_reason(b"{}", "", None, "live", "development") == "the webhook secret is not configured"


def test_missing_secret_mock_development_accepted() -> None:
    assert v1.signature_failure_reason(b"{}", "", None, "mock", "development") is None
