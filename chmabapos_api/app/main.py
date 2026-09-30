import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1 import router as v1_router
from app.api.admin import router as admin_router
from app.config import settings
from app.db import SessionLocal, engine
from app.services.mailing import send_pending_emails

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


@asynccontextmanager
async def lifespan(_: FastAPI):
    worker = None
    if settings.mailing_queue_worker_enabled and settings.environment != "test":
        worker = asyncio.create_task(_drain_mailing_queue())
    yield
    if worker is not None:
        worker.cancel()
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

app.include_router(v1_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")

_media_root = Path(settings.media_root)
_media_root.mkdir(parents=True, exist_ok=True)
app.mount(settings.media_url_prefix, StaticFiles(directory=str(_media_root)), name="media")


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {"service": settings.app_name, "version": "v1", "docs": "/docs"}
