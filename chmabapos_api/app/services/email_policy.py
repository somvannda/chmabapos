"""Reject email domains that cannot belong to a real merchant.

Two classes are refused in production:

* reserved domains (``example.com``, ``localhost``, ``.test`` and friends),
  which exist only for documentation and tests; and
* well-known disposable inbox providers, where anyone can read the mailbox and
  a verification code proves nothing about a real person.

The check is deliberately production-only. The test suite and Playwright use
``@example.com`` addresses, and local development must keep working. A static
list is not a complete defence on its own: it is one layer beside Turnstile,
rate limits and email verification, and a maintained reputation service is the
next step if disposable signups continue.
"""

from __future__ import annotations

from app.config import settings

RESERVED_DOMAINS = frozenset(
    {
        "example.com",
        "example.net",
        "example.org",
        "example.edu",
        "localhost",
        "test",
        "invalid",
        "local",
    }
)

DISPOSABLE_DOMAINS = frozenset(
    {
        "10minutemail.com",
        "dispostable.com",
        "emailondeck.com",
        "euploading.com",
        "fakeinbox.com",
        "getnada.com",
        "guerrillamail.com",
        "maildrop.cc",
        "mailinator.com",
        "mailnesia.com",
        "mintemail.com",
        "moakt.com",
        "mytemp.email",
        "sharklasers.com",
        "spamgourmet.com",
        "temp-mail.org",
        "tempail.com",
        "tempmail.com",
        "throwawaymail.com",
        "trashmail.com",
        "yopmail.com",
    }
)


def _domain(email: str) -> str:
    local, _, domain = (email or "").strip().lower().rpartition("@")
    return domain if local and domain else ""


def _matches(domain: str, blocked: frozenset[str]) -> bool:
    return any(domain == item or domain.endswith(f".{item}") for item in blocked)


def blocked_reason(email: str) -> str | None:
    """Return a user-facing reason when ``email`` must not be registered.

    ``None`` means the address is allowed. The message deliberately does not
    name the matched list, so an attacker cannot use it to enumerate the rules.
    """
    if settings.environment != "production":
        return None
    domain = _domain(email)
    if not domain:
        return "Please enter a valid email address."
    if _matches(domain, RESERVED_DOMAINS):
        return "Please use a permanent email address, not a test or example domain."
    if _matches(domain, DISPOSABLE_DOMAINS):
        return "Please use a permanent email address, not a disposable inbox."
    return None
