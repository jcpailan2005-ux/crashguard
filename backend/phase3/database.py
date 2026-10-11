from __future__ import annotations

import os
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row


class DatabaseUnavailable(RuntimeError):
    pass


def database_url() -> str:
    value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        raise DatabaseUnavailable(
            "DATABASE_URL is required for Phase 3 operational APIs."
        )
    return value


@contextmanager
def connection(*, autocommit: bool = False):
    try:
        conn = psycopg.connect(
            database_url(), row_factory=dict_row, autocommit=autocommit
        )
    except DatabaseUnavailable:
        raise
    except psycopg.Error as error:
        raise DatabaseUnavailable("PostgreSQL is unavailable.") from error
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def check_database() -> dict:
    with connection(autocommit=True) as conn:
        row = conn.execute(
            "SELECT current_database() AS name, current_setting('server_version') AS version"
        ).fetchone()
    return {"status": "ok", "database": row["name"], "version": row["version"]}
