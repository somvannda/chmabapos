#!/usr/bin/env python3
"""Block until the database accepts connections, then exit 0.

The API container's command runs ``alembic upgrade head`` as its first step.
Compose only enforces ``depends_on: db: condition: service_healthy`` when it
*creates* containers - after a host reboot the ``restart: unless-stopped``
policy starts every container at once, so the API races Postgres. While
Postgres is still in automatic recovery it answers ``FATAL: the database system
is starting up``, alembic raises, and the ``&&`` chain exits. The API then
crash-loops, and because it is down every ``/api/*`` request is a 502, until
Postgres finally finishes starting.

Waiting here keeps the container alive so it serves the moment the database is
ready, which is what removes that 502 window.

Run it from the repository root:

    python chmabapos_api/scripts/wait_for_db.py
"""
from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings

# A loaded host with several Postgres instances recovering at once has taken
# over ten minutes to accept connections, so the default is generous: the
# container is not serving 502s by giving up early, it is only delaying its own
# startup. Override with DB_WAIT_TIMEOUT_SECONDS when a tighter bound is wanted.
DEFAULT_TIMEOUT_SECONDS = 900
RETRY_INTERVAL_SECONDS = 2
PROGRESS_EVERY_SECONDS = 15


def _first_line(error: BaseException) -> str:
    """The DBAPI error text can be multi-line; keep the log entry to one line."""
    text_repr = str(error).strip()
    return text_repr.splitlines()[0] if text_repr else type(error).__name__


def wait_for_database(
    connect: Callable[[], None],
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    retry_interval_seconds: float = RETRY_INTERVAL_SECONDS,
    progress_every_seconds: float = PROGRESS_EVERY_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    """Poll ``connect`` until it stops raising.

    Returns True as soon as a connection succeeds, or False once
    ``timeout_seconds`` have elapsed, so the caller can pick the exit code.
    Errors that are not SQLAlchemy errors are not a "database is not ready yet"
    signal, so they propagate instead of being retried.
    """
    started = time.monotonic()
    next_progress_at = 0.0

    while True:
        elapsed = time.monotonic() - started
        try:
            connect()
        except SQLAlchemyError as exc:
            if elapsed >= timeout_seconds:
                print(
                    f"Database still unreachable after {elapsed:.0f}s: {_first_line(exc)}",
                    file=sys.stderr,
                )
                return False
            if elapsed >= next_progress_at:
                next_progress_at = elapsed + progress_every_seconds
                print(f"Waiting for database ({elapsed:.0f}s): {_first_line(exc)}", flush=True)
            sleep(retry_interval_seconds)
        else:
            print(f"Database ready after {elapsed:.1f}s")
            return True


def main() -> int:
    timeout_seconds = float(os.getenv("DB_WAIT_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))
    engine = create_engine(settings.sync_database_url, pool_pre_ping=True)

    def connect() -> None:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    return 0 if wait_for_database(connect, timeout_seconds=timeout_seconds) else 1


if __name__ == "__main__":
    raise SystemExit(main())
