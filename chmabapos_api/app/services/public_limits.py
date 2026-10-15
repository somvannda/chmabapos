"""Rate limiting for the unauthenticated public surface.

The public endpoints are reachable by anyone: a store menu, the store directory,
and order submission. Without a limit they are a cheap target for scraping,
enumeration and order spam, and `docs/marketplace-storefront-plan.md` marks this
as required before the storefront goes public.

This reuses the process-local sliding window in ``app.services.support`` rather
than adding a second mechanism. **Its limitation is the same one**: the window
lives in memory, so with more than one API worker the effective limit is
per-worker. That is acceptable for the current single-process deployment and is
the first thing to replace with shared storage if the API scales out.
"""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.services.support import check_rate_limit


def client_key(request: Request, scope: str) -> str:
    """A per-client key for ``scope``.

    nginx sits in front of the API, so ``request.client.host`` is the proxy rather
    than the visitor - keying on it would put every visitor in one bucket and make
    the limit useless. Our nginx sets ``X-Real-IP`` to the true remote address and
    overwrites any client-supplied value, so that is the trustworthy source here.

    ``X-Forwarded-For`` is only a fallback, and the **right-most** entry is used
    because nginx appends to whatever the client sent: the left-most value is
    client-controlled and therefore spoofable.
    """
    ip = (request.headers.get("x-real-ip") or "").strip()
    if not ip:
        forwarded = (request.headers.get("x-forwarded-for") or "").strip()
        if forwarded:
            ip = forwarded.rsplit(",", 1)[-1].strip()
    if not ip and request.client:
        ip = request.client.host
    return f"{scope}:{ip or 'unknown'}"


def enforce(request: Request, scope: str, *, limit: int, window_seconds: int = 60) -> None:
    """Apply the limit for ``scope``, raising 429 when the caller is over it.

    A non-positive ``limit`` disables the check, which is how the test suite turns
    it off while exercising other behaviour.
    """
    if check_rate_limit(client_key(request, scope), limit=limit, window_seconds=window_seconds):
        return
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many requests. Please wait a moment and try again.",
    )
