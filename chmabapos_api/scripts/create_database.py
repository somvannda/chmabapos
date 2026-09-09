import asyncio
import os
import sys

import psycopg


TARGET_DATABASE = os.getenv("CHMABA_DATABASE", "chmaba_v1")
CONNECTION = os.getenv(
    "CHMABA_ADMIN_DATABASE_URL",
    "postgresql://postgres:postgres@127.0.0.1:5432/postgres",
)


async def main() -> None:
    try:
        await asyncio.to_thread(create_database)
    except Exception as exc:
        print(f"Could not create database: {exc}", file=sys.stderr)
        raise


def create_database() -> None:
    with psycopg.connect(CONNECTION, autocommit=True) as connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (TARGET_DATABASE,),
        ).fetchone()
        if exists:
            print(f"Database '{TARGET_DATABASE}' already exists")
            return
        connection.execute(f'CREATE DATABASE "{TARGET_DATABASE}"')
        print(f"Database '{TARGET_DATABASE}' created")


if __name__ == "__main__":
    asyncio.run(main())
