from pathlib import Path
import sqlite3


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_PATH = DATA_DIR / "crashguard.sqlite"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        _ensure_columns(
            conn,
            "cameras",
            {
                "location": "TEXT",
                "cameraType": "TEXT",
                "cameraIp": "TEXT",
                "barangay": "TEXT",
                "roadName": "TEXT",
                "locationDescription": "TEXT",
                "isActive": "INTEGER NOT NULL DEFAULT 1",
                "detectionEnabled": "INTEGER NOT NULL DEFAULT 1",
                "lastEventAt": "TEXT",
            },
        )
        _ensure_columns(
            conn,
            "users",
            {
                "passwordHash": "TEXT",
                "passwordSalt": "TEXT",
                "isActive": "INTEGER NOT NULL DEFAULT 1",
                "lastLoginAt": "TEXT",
            },
        )
        _ensure_columns(
            conn,
            "crash_cases",
            {
                "cameraIp": "TEXT",
                "cameraId": "TEXT",
                "cameraName": "TEXT",
                "barangay": "TEXT",
                "roadName": "TEXT",
                "assignedResponderId": "TEXT",
            },
        )
        _ensure_indexes(conn)


def _ensure_columns(
    conn: sqlite3.Connection,
    table: str,
    columns: dict[str, str],
) -> None:
    existing = {
        row[1]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    for name, column_type in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {column_type}")


def _ensure_indexes(conn: sqlite3.Connection) -> None:
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_crash_cases_cameraId ON crash_cases(cameraId)",
        "CREATE INDEX IF NOT EXISTS idx_cameras_areaId ON cameras(areaId)",
        "CREATE INDEX IF NOT EXISTS idx_cameras_status ON cameras(status)",
        "CREATE INDEX IF NOT EXISTS idx_cameras_active ON cameras(isActive)",
        "CREATE INDEX IF NOT EXISTS idx_responder_assignments_responder ON responder_camera_assignments(responderId)",
        "CREATE INDEX IF NOT EXISTS idx_responder_assignments_camera ON responder_camera_assignments(cameraId)",
    ]
    for statement in indexes:
        conn.execute(statement)


def get_connection() -> sqlite3.Connection:
    init_db()
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
