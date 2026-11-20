"""Public collector for first-party product telemetry.

The endpoint is unauthenticated on purpose: the most interesting part of the
journey happens before an account exists. Identity is resolved from an optional
bearer token, never trusted from the body, and everything is best-effort — a
telemetry failure must not surface in the app that is trying to sell.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics import (
    enabled,
    hash_ip,
    looks_like_bot,
    optional_user,
    record_batch,
    upsert_session,
)
from app.config import settings
from app.db import get_db
from app.deps import bearer
from app.schemas import TelemetryBatchIn, TelemetryBatchRead
from app.services.client_ip import client_ip
from app.services.public_limits import client_key
from app.services.support import check_rate_limit

logger = logging.getLogger("chmaba.analytics")

router = APIRouter(tags=["telemetry"])


@router.post("/telemetry/events", response_model=TelemetryBatchRead, status_code=202)
async def ingest_telemetry(
    payload: TelemetryBatchIn,
    request: Request,
    credentials=Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> TelemetryBatchRead | JSONResponse:
    """Accept a batch of client events.

    Returns 202 with how many events were stored and how many were dropped. A
    dropped event is almost always a client sending a name that is not in the
    registry, which the health page surfaces as registry drift.
    """
    if not enabled():
        return TelemetryBatchRead(accepted=0, dropped=0)

    try:
        declared = int(request.headers.get("content-length") or 0)
    except ValueError:
        declared = 0
    if declared > settings.analytics_max_request_bytes:
        return JSONResponse(status_code=413, content={"detail": "Telemetry batch is too large"})

    user_agent = request.headers.get("user-agent")
    if looks_like_bot(user_agent):
        return TelemetryBatchRead(accepted=0, dropped=0)

    user = await optional_user(db, credentials.credentials if credentials else None)

    # Two windows: one per session catches a runaway loop, one per address
    # catches a script cycling session ids. Both are generous enough never to
    # clip a real till.
    if not check_rate_limit(
        f"analytics-session:{payload.session.id}",
        limit=settings.analytics_rate_limit_per_session_per_minute,
        window_seconds=60,
    ):
        return TelemetryBatchRead(accepted=0, dropped=len(payload.events))
    if not check_rate_limit(
        client_key(request, "analytics-ip"),
        limit=settings.analytics_rate_limit_per_ip_per_minute,
        window_seconds=60,
    ):
        return TelemetryBatchRead(accepted=0, dropped=len(payload.events))

    events = [event.model_dump() for event in payload.events[: settings.analytics_max_batch_events]]
    overflow = max(len(payload.events) - len(events), 0)
    session = payload.session

    try:
        await upsert_session(
            db,
            session_id=session.id,
            anonymous_id=session.anonymous_id,
            source=payload.source,
            started_at=session.started_at,
            entry_route=session.entry_route,
            referrer_host=session.referrer_host,
            utm=session.utm.model_dump() if session.utm else None,
            app_version=payload.app_version,
            platform=session.platform,
            os_name=session.os,
            browser=session.browser,
            device_type=session.device_type,
            locale=session.locale,
            timezone_name=session.timezone,
            user=user,
            ip_hash=hash_ip(client_ip(request)),
            user_agent=user_agent,
        )
        accepted, dropped = await record_batch(
            db,
            source=payload.source,
            session_id=session.id,
            anonymous_id=session.anonymous_id,
            events=events,
            user=user,
            app_version=payload.app_version,
            platform=session.platform,
            os_name=session.os,
            browser=session.browser,
            device_type=session.device_type,
            locale=session.locale,
            timezone_name=session.timezone,
        )
        await db.commit()
    except Exception:
        # Best-effort by contract. Roll back so the session is not left in a
        # broken transaction, and report the events as dropped.
        await db.rollback()
        logger.exception("analytics: telemetry batch failed")
        return TelemetryBatchRead(accepted=0, dropped=len(events) + overflow)

    return TelemetryBatchRead(accepted=accepted, dropped=dropped + overflow)
