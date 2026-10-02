#!/usr/bin/env python3
"""Fail if the database is missing tables or columns the app expects.

Catches schema drift, such as a database whose recorded ``alembic_version`` is
ahead of its real schema (so startup ``alembic upgrade head`` is a no-op). Only
*missing* tables and columns are reported, so benign type, index or default
differences never trip it.

Run it from the repository root:

    python chmabapos_api/scripts/check_schema_drift.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect

from app.db import engine
from app.models import Base


async def main() -> int:
    async with engine.connect() as connection:
        def audit(sync_connection):
            inspector = inspect(sync_connection)
            existing_tables = set(inspector.get_table_names())
            missing_tables = sorted(name for name in Base.metadata.tables if name not in existing_tables)
            missing_columns: dict[str, list[str]] = {}
            for name, table in Base.metadata.tables.items():
                if name not in existing_tables:
                    continue
                present = {column["name"] for column in inspector.get_columns(name)}
                missing = sorted(column.name for column in table.columns if column.name not in present)
                if missing:
                    missing_columns[name] = missing
            return missing_tables, missing_columns

        missing_tables, missing_columns = await connection.run_sync(audit)

    if missing_tables or missing_columns:
        print("Schema drift detected:")
        for name in missing_tables:
            print(f"  missing table: {name}")
        for name, columns in missing_columns.items():
            print(f"  {name}: missing columns: {', '.join(columns)}")
        return 1

    print("Schema OK: every model table and column is present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
