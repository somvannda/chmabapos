import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from app.api.v1 import expire_unpaid_online_orders, reconcile_open_held_order_payments, reconcile_open_order_payments, reconcile_pending_billing_payments, release_stale_reservations, router as v1_router
from app.api.admin import router as admin_router
from app.api.printing import router as printing_router
from app.config import settings
from app.db import SessionLocal, engine
from app.services.billing_lifecycle import BILLING_JOB_LOCK_KEY, reconcile_effective_capacity, run_expiry_job
from app.services import health as health_service
from app.services.mailing import release_scheduled_campaigns, run_mailing_drip, send_pending_emails
from app.services.public_limits import client_key
from app.services.reminders import run_reminder_job
from app.services.support import check_rate_limit
from app.services.quota_warnings import run_quota_warnings
from app.services.store_chat import run_unanswered_alerts
from app.services.store_notifications import run_store_notifications
from app.telegram import send_telegram_message

logger = logging.getLogger("chmaba.mailing")


async def _drain_mailing_queue() -> None:
    """Deliver queued mailing sends on a loop.

    Runs in-process so mailing does not depend on an external scheduler. A
    Postgres advisory lock in ``send_pending_emails`` means this cannot double
    up with a cron job or another worker.
    """
    while True:
        try:
            async with SessionLocal() as db:
                released = await release_scheduled_campaigns(db)
                stats = await send_pending_emails(db)
            if released["released"]:
                logger.info("scheduled campaigns released: %s", released)
            if stats["processed"]:
                logger.info("mailing queue drained: %s", stats)
        except asyncio.CancelledError:
            raise
        except Exception:  # a bad batch must never kill the worker
            logger.exception("mailing queue drain failed")
        await asyncio.sleep(max(5, settings.mailing_queue_interval_seconds))


async def _generate_mailing_drip() -> None:
    """Enqueue the onboarding drip for newly stalled signups on a loop.

    Without this, automatic onboarding email never fires: the queue worker only
    *drains* what has already been queued, and nothing else calls
    ``run_mailing_drip``. Generation is idempotent (one delivery per user per
    step via the ``mailing_drip_deliveries`` ledger) and respects the configured
    local send window, so it is safe to run on a timer.
    """
    while True:
        try:
            async with SessionLocal() as db:
                stats = await run_mailing_drip(db)
            if stats["queued"]:
                logger.info("mailing drip queued: %s", stats)
        except asyncio.CancelledError:
            raise
        except Exception:  # a bad batch must never kill the worker
            logger.exception("mailing drip generation failed")
        await asyncio.sleep(max(60, settings.mailing_drip_interval_seconds))


async def _queue_store_notifications() -> None:
    """Queue the store notification emails that are due on a loop.

    Idempotent per local day / open shift, so a short interval only enqueues
    what is actually due; the mailing queue worker delivers it.
    """
    while True:
        try:
            async with SessionLocal() as db:
                stats = await run_store_notifications(db)
                quota = await run_quota_warnings(db)
            if any(stats.get(key) for key in ("summaries", "low_stock", "shift_reminders", "sale_digests", "warranty_expiries")):
                logger.info("store notifications queued: %s", stats)
            if quota.get("warned"):
                logger.info("quota warnings queued: %s", quota)
        except asyncio.CancelledError:
            raise
        except Exception:  # a bad batch must never kill the worker
            logger.exception("store notification generation failed")
        await asyncio.sleep(max(60, settings.store_notification_interval_seconds))


async def _expire_reservations() -> None:
    """Release stock held by lapsed deposit reservations on a loop.

    Idempotent: a released order no longer matches the ``pending_pickup``
    filter, so a short interval only ever acts on what is actually due.
    """
    while True:
        try:
            async with SessionLocal() as db:
                released = await release_stale_reservations(db)
                if released:
                    await db.commit()
                    logger.info("reservation expiry sweep released %s order(s)", released)
        except asyncio.CancelledError:
            raise
        except Exception:  # a bad batch must never kill the worker
            logger.exception("reservation expiry sweep failed")
        await asyncio.sleep(max(60, settings.reservation_expiry_interval_seconds))


async def _queue_chat_alerts() -> None:
    """Email the store when a chat message goes unanswered on a loop.

    The alert is recorded on the conversation, so a short interval only ever
    queues what is actually due; the mailing queue worker delivers it.
    """
    while True:
        try:
            async with SessionLocal() as db:
                stats = await run_unanswered_alerts(db)
                await db.commit()
            if stats["emails"]:
                logger.info("chat unanswered alerts queued: %s", stats)
        except asyncio.CancelledError:
            raise
        except Exception:  # a bad batch must never kill the worker
            logger.exception("chat alert scan failed")
        await asyncio.sleep(max(60, settings.chat_alert_interval_seconds))


async def _billing_cycle_once() -> dict | None:
    """Run one billing cycle, or return None if another worker owns it.

    The lock lives on a separate connection and is transaction-scoped, so it is
    released automatically when the cycle ends or the process dies. Jobs use
    their own session and are free to commit.
    """
    async with engine.connect() as lock_conn:
        acquired = await lock_conn.scalar(select(func.pg_try_advisory_xact_lock(BILLING_JOB_LOCK_KEY)))
        if not acquired:
            return None
        async with SessionLocal() as db:
            billing = await reconcile_pending_billing_payments(db)
            orders = await reconcile_open_order_payments(db)
            held = await reconcile_open_held_order_payments(db)
            expiry = await run_expiry_job(db)
            capacity = await reconcile_effective_capacity(db)
            reminders = await run_reminder_job(db)
            expired = await expire_unpaid_online_orders(db)
            await db.commit()
        return {
            "billing": billing,
            "orders": orders,
            "held": held,
            "expiry": expiry,
            "capacity": capacity,
            "reminders": reminders,
            "expired_orders": expired,
        }


async def _alert_billing_worker_failure(failures: int) -> None:
    """Page the internal ops chat after repeated failed cycles.

    Telegram is a safe no-op when unconfigured; never let an alert failure
    break the worker.
    """
    logger.critical("billing lifecycle failed %s consecutive cycles", failures)
    try:
        await send_telegram_message(
            f"Chmaba billing worker: {failures} consecutive failed cycles. "
            "Check the API logs (billing lifecycle worker failed)."
        )
    except Exception:
        logger.exception("could not send the billing worker failure alert")


async def _run_billing_lifecycle() -> None:
    """Reconcile payments, expire plans and send reminders on a loop.

    This is the in-process equivalent of ``scripts/run_billing_jobs.py``. Each
    step is idempotent (receipts/payments are row-locked, reminders are unique
    per subscription/bucket), so a restart or a missed cycle self-heals. A
    Postgres advisory lock means multiple API workers cannot run the same cycle
    at the same time.
    """
    failures = 0
    alerted = False
    threshold = max(1, settings.billing_job_alert_after_failures)
    while True:
        try:
            stats = await _billing_cycle_once()
            failures = 0
            alerted = False
            if stats is None:
                logger.debug("billing lifecycle skipped: another worker holds the lock")
            elif (
                stats["billing"].get("activated")
                or stats["billing"].get("closed")
                or stats["orders"].get("activated")
                or stats["held"].get("paid")
                or stats["expiry"].get("expired_subs")
                or stats["capacity"].get("companies")
                or stats["reminders"].get("reminders")
            ):
                logger.info(
                    "billing lifecycle: reconcile=%s orders=%s held=%s expiry=%s capacity=%s reminders=%s expired_orders=%s",
                    stats["billing"],
                    stats["orders"],
                    stats["held"],
                    stats["expiry"],
                    stats["capacity"],
                    stats["reminders"],
                    stats["expired_orders"],
                )
        except asyncio.CancelledError:
            raise
        except Exception:  # a bad cycle must never kill the worker
            failures += 1
            logger.exception("billing lifecycle worker failed (%s consecutive)", failures)
            if failures >= threshold and not alerted:
                alerted = True
                await _alert_billing_worker_failure(failures)
        await asyncio.sleep(max(300, settings.billing_job_interval_seconds))


async def _run_health_sweep() -> None:
    """Probe every platform dependency on a loop and page when one stays down.

    Self-healing on restart: the first sweep rewrites the current state, and
    alerting needs consecutive bad sweeps, so a redeploy does not page on a
    dependency that was already recorded down. The first sweep is a ``startup``
    one, which records the board without paging: a container that has just come up
    is still warming DNS and routes, and "Storefront down, Web POS down" two
    minutes after every deploy is noise that teaches people to ignore the channel.
    """
    first = True
    while True:
        try:
            async with SessionLocal() as db:
                state = await health_service.run_checks(db, trigger="startup" if first else "schedule")
            first = False
            if state["overall_status"] != health_service.STATUS_OK:
                unhealthy = [check for check in state["checks"] if check["status"] in health_service.UNHEALTHY_STATUSES]
                logger.warning(
                    "platform health is %s: %s",
                    state["overall_status"],
                    ", ".join(f"{check['name']}={check['status']}" for check in unhealthy) or "no detail",
                )
        except asyncio.CancelledError:
            raise
        except Exception:  # a failed sweep must never kill the worker
            logger.exception("platform health sweep failed")
        await asyncio.sleep(max(30, settings.health_check_interval_seconds))


async def _run_payment_smoke() -> None:
    """Mint a real test QR hourly and post the result to the operations chat.

    The sweep only proves ChmabaPay answers. This proves the mint path works with
    the live key, which is what a cashier actually depends on. ``payment_smoke_due``
    stops a redeploy from minting one on every restart; when it is not due yet the
    worker wakes every five minutes so a switch to live mode is picked up quickly.
    """
    while True:
        ran = False
        try:
            async with SessionLocal() as db:
                if await health_service.payment_smoke_due(db):
                    state = await health_service.run_payment_smoke(db)
                    ran = True
                    logger.info("hourly payment test: %s - %s", state["status"], state["summary"])
        except asyncio.CancelledError:
            raise
        except Exception:  # a failed test must never kill the worker
            logger.exception("hourly payment test failed to run")
        await asyncio.sleep(
            max(300, settings.health_check_payment_smoke_interval_seconds) if ran else 300
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    workers: list[asyncio.Task] = []
    if settings.environment != "test":
        if settings.billing_job_worker_enabled:
            workers.append(asyncio.create_task(_run_billing_lifecycle()))
        if settings.health_check_worker_enabled:
            workers.append(asyncio.create_task(_run_health_sweep()))
        if settings.health_check_payment_smoke_enabled:
            workers.append(asyncio.create_task(_run_payment_smoke()))
        if settings.mailing_queue_worker_enabled:
            workers.append(asyncio.create_task(_drain_mailing_queue()))
        if settings.mailing_drip_worker_enabled:
            workers.append(asyncio.create_task(_generate_mailing_drip()))
        if settings.store_notification_worker_enabled:
            workers.append(asyncio.create_task(_queue_store_notifications()))
        if settings.reservation_expiry_worker_enabled:
            workers.append(asyncio.create_task(_expire_reservations()))
        if settings.chat_alert_worker_enabled:
            workers.append(asyncio.create_task(_queue_chat_alerts()))
    yield
    for worker in workers:
        worker.cancel()
    for worker in workers:
        with suppress(asyncio.CancelledError):
            await worker
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="API-first backend for Chmaba cloud POS.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def limit_public_requests(request: Request, call_next):
    """Rate-limit the unauthenticated public surface.

    Done here rather than in each endpoint so a new public route cannot quietly
    ship without a limit - the failure mode of per-endpoint checks is that someone
    adds the next public endpoint and forgets. Writes are limited far more tightly
    than reads because order submission is the valuable thing to abuse.

    A limit of zero disables the check, which is how the test suite turns it off.
    """
    path = request.url.path
    if path.startswith("/api/v1/public/"):
        is_write = request.method not in ("GET", "HEAD", "OPTIONS")
        limit = (
            settings.public_order_rate_limit_per_minute
            if is_write
            else settings.public_read_rate_limit_per_minute
        )
        scope = "public-write" if is_write else "public-read"
        if not check_rate_limit(client_key(request, scope), limit=limit, window_seconds=60):
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please wait a moment and try again."},
            )
    return await call_next(request)

app.include_router(v1_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(printing_router, prefix="/api/v1")

_media_root = Path(settings.media_root)
_media_root.mkdir(parents=True, exist_ok=True)
app.mount(settings.media_url_prefix, StaticFiles(directory=str(_media_root)), name="media")


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {"service": settings.app_name, "version": "v1", "docs": "/docs"}
