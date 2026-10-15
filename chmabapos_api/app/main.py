import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import release_stale_reservations, router as v1_router
from app.api.admin import router as admin_router
from app.api.printing import router as printing_router
from app.config import settings
from app.db import SessionLocal, engine
from app.services.mailing import run_mailing_drip, send_pending_emails
from app.services.public_limits import client_key
from app.services.support import check_rate_limit
from app.services.quota_warnings import run_quota_warnings
from app.services.store_notifications import run_store_notifications

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
                stats = await send_pending_emails(db)
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


@asynccontextmanager
async def lifespan(_: FastAPI):
    workers: list[asyncio.Task] = []
    if settings.environment != "test":
        if settings.mailing_queue_worker_enabled:
            workers.append(asyncio.create_task(_drain_mailing_queue()))
        if settings.mailing_drip_worker_enabled:
            workers.append(asyncio.create_task(_generate_mailing_drip()))
        if settings.store_notification_worker_enabled:
            workers.append(asyncio.create_task(_queue_store_notifications()))
        if settings.reservation_expiry_worker_enabled:
            workers.append(asyncio.create_task(_expire_reservations()))
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
