from __future__ import annotations

import pytest
from sqlalchemy.exc import OperationalError

from scripts.wait_for_db import wait_for_database


def _starting_up_error() -> OperationalError:
    """The error Postgres answers with while it is still in automatic recovery."""
    return OperationalError(
        "SELECT 1",
        {},
        Exception("connection failed: FATAL:  the database system is starting up"),
    )


def test_wait_for_database_returns_immediately_when_the_database_is_up() -> None:
    slept: list[float] = []

    def connect() -> None:
        return None

    assert wait_for_database(connect, sleep=slept.append) is True
    assert slept == []


def test_wait_for_database_retries_until_the_database_answers() -> None:
    attempts: list[int] = []

    def connect() -> None:
        attempts.append(len(attempts))
        if len(attempts) < 3:
            raise _starting_up_error()

    assert wait_for_database(connect, sleep=lambda _: None) is True
    assert len(attempts) == 3


def test_wait_for_database_gives_up_after_the_timeout() -> None:
    attempts: list[int] = []

    def connect() -> None:
        attempts.append(len(attempts))
        raise _starting_up_error()

    # timeout 0 makes the first failure final, so the test never sleeps.
    assert wait_for_database(connect, timeout_seconds=0, sleep=lambda _: None) is False
    assert len(attempts) == 1


def test_wait_for_database_does_not_retry_unexpected_errors() -> None:
    def connect() -> None:
        raise ValueError("a bug, not a cold database")

    with pytest.raises(ValueError):
        wait_for_database(connect, sleep=lambda _: None)
