"""SQLite operational storage; no network database or Firebase fallback."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.phase3.permissions import ROLE_PERMISSIONS, PERMISSION_DESCRIPTIONS

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "crashguard-operations.sqlite"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")
_schema_lock = threading.Lock()
_initialized: set[Path] = set()
JSON_COLUMNS = {"evidence_summary", "media", "before_data", "after_data", "metadata",
                "details", "value", "notification_preferences"}


class DatabaseUnavailable(RuntimeError):
    pass


def database_path() -> Path:
    value = os.getenv("CRASHGUARD_SQLITE_PATH", "").strip()
    path = Path(value).expanduser() if value else DEFAULT_PATH
    if not path.is_absolute():
        path = DEFAULT_PATH.parent.parent / path
    return path.resolve()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row(cursor, values) -> dict:
    result = dict(zip((column[0] for column in cursor.description), values))
    for name, value in result.items():
        if value is None:
            continue
        if name in JSON_COLUMNS:
            result[name] = json.loads(value)
        elif name in {"roles", "permissions"}:
            result[name] = value.split(",") if value else []
        elif name in {"must_change_password", "detection_enabled"}:
            result[name] = bool(value)
        elif name.endswith("_at") or name in {"lastSeenAt", "lastLoginAt"}:
            result[name] = datetime.fromisoformat(value)
    return result


def _parameter(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def _open(path: Path):
    conn = sqlite3.connect(path, timeout=30, isolation_level=None)
    conn.row_factory = _row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.create_function("now", 0, _now)
    conn.create_function("gen_random_uuid", 0, lambda: str(uuid.uuid4()))
    conn.create_function("minutes_from_now", 1, lambda minutes:
                         (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat())
    conn.create_function("seconds_ago", 1, lambda seconds:
                         (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat())
    return conn


def init_db() -> None:
    path = database_path()
    with _schema_lock:
        if path in _initialized and path.exists():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = _open(path)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
            conn.execute("BEGIN IMMEDIATE")
            for role, permissions in ROLE_PERMISSIONS.items():
                conn.execute("INSERT OR IGNORE INTO roles(name,description) VALUES (?,?)",
                             (role, role.title()))
                for code in sorted(permissions):
                    conn.execute("INSERT OR IGNORE INTO permissions(code,description) VALUES (?,?)",
                                 (code, PERMISSION_DESCRIPTIONS[code]))
                    conn.execute("""INSERT OR IGNORE INTO role_permissions(role_id,permission_id)
                                    SELECT r.id,p.id FROM roles r CROSS JOIN permissions p
                                    WHERE r.name=? AND p.code=?""", (role, code))
            conn.commit()
            _initialized.add(path)
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()


class Connection:
    def __init__(self, conn):
        self.raw = conn

    def execute(self, sql, params=()):
        # SQL belongs to the service; API clients supply bound values only.
        return self.raw.execute(sql.replace("%s", "?"), tuple(_parameter(p) for p in params))

    @contextmanager
    def transaction(self):
        # Serialize competing review, assignment and detector decisions.
        nested = self.raw.in_transaction
        savepoint = "nested_" + uuid.uuid4().hex
        self.raw.execute(f"SAVEPOINT {savepoint}" if nested else "BEGIN IMMEDIATE")
        try:
            yield self
        except BaseException:
            if nested:
                self.raw.execute(f"ROLLBACK TO {savepoint}")
                self.raw.execute(f"RELEASE {savepoint}")
            else:
                self.raw.rollback()
            raise
        else:
            if nested:
                self.raw.execute(f"RELEASE {savepoint}")
            else:
                self.raw.commit()


@contextmanager
def connection(*, autocommit: bool = False):
    try:
        init_db()
        conn = _open(database_path())
    except (OSError, sqlite3.Error) as error:
        raise DatabaseUnavailable("SQLite operational storage is unavailable.") from error
    try:
        yield Connection(conn)
    finally:
        conn.close()


def check_database() -> dict:
    with connection() as conn:
        row = conn.execute("SELECT sqlite_version() AS version").fetchone()
    return {"status": "ok", "engine": "sqlite", "database": database_path().name,
            "version": row["version"]}
