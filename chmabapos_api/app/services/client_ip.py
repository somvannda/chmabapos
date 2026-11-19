"""Resolve the visitor's address behind nginx and Cloudflare.

The API only ever sees the nginx container, so ``request.client.host`` is a
Docker network address. nginx overwrites ``X-Real-IP``; in production
``deploy/nginx.conf`` fills it from Cloudflare's ``CF-Connecting-IP`` so the API
can rate-limit and report the real visitor rather than a Cloudflare edge node.

``X-Forwarded-For`` is the last resort, and the **right-most** entry is used:
nginx appends to whatever the client sent, so only the entry nginx itself added
is trustworthy. The left-most values are client-controlled.

The origin must stay reachable only through Cloudflare. If it is exposed
directly, a client can send any of these headers itself; keeping the origin
firewalled to Cloudflare's ranges is what makes them meaningful.
"""

from __future__ import annotations

from ipaddress import ip_address

from fastapi import Request


def _valid(value: str | None) -> str | None:
    candidate = (value or "").strip()
    if not candidate:
        return None
    try:
        ip_address(candidate)
    except ValueError:
        return None
    return candidate


def client_ip(request: Request) -> str:
    """Best available visitor address, never empty."""
    for header in ("x-real-ip", "cf-connecting-ip"):
        found = _valid(request.headers.get(header))
        if found:
            return found
    forwarded = (request.headers.get("x-forwarded-for") or "").strip()
    if forwarded:
        for part in reversed(forwarded.split(",")):
            found = _valid(part)
            if found:
                return found
    if request.client and request.client.host:
        return request.client.host
    return "unknown"
