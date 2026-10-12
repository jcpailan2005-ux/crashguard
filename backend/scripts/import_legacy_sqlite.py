from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from backend.phase3.service import _json as Jsonb

from backend.phase3.database import connection


ROOT = Path(__file__).resolve().parents[2]
LEGACY_PATH = ROOT / "data" / "crashguard.sqlite"


def rows(conn: sqlite3.Connection, table: str) -> list[dict]:
    try:
        return [dict(row) for row in conn.execute(f"SELECT * FROM {table}").fetchall()]
    except sqlite3.OperationalError:
        return []


def value(row: dict, *names, default=None):
    for name in names:
        if row.get(name) not in (None, ""):
            return row[name]
    return default


def main() -> None:
    if not LEGACY_PATH.exists():
        raise SystemExit(f"Legacy database not found: {LEGACY_PATH}")
    legacy = sqlite3.connect(LEGACY_PATH)
    legacy.row_factory = sqlite3.Row
    camera_rows = rows(legacy, "cameras")
    case_rows = rows(legacy, "crash_cases")
    imported_cameras = 0
    imported_incidents = 0

    with connection() as pg, pg.transaction():
        area_names = {
            str(value(row, "areaId", "barangay")).strip()
            for row in camera_rows + case_rows
            if value(row, "areaId", "barangay")
        }
        for name in area_names:
            pg.execute("INSERT INTO areas(name) VALUES (%s) ON CONFLICT(name) DO NOTHING", (name,))

        for camera in camera_rows:
            legacy_id = str(value(camera, "cameraId", "id", default="")).strip()
            if not legacy_id:
                continue
            result = pg.execute(
                """INSERT INTO cameras(legacy_id,area_id,name,location,status,detection_enabled,latitude,longitude)
                   VALUES (%s,(SELECT id FROM areas WHERE name=%s),%s,%s,%s,%s,%s,%s)
                   ON CONFLICT(legacy_id) DO NOTHING RETURNING id""",
                (legacy_id, value(camera, "areaId", "barangay"), value(camera, "label", "name", default=legacy_id),
                 value(camera, "location", "locationDescription"),
                 "ONLINE" if str(value(camera, "status", default="")).lower() == "online" else "OFFLINE",
                 bool(value(camera, "detectionEnabled", default=1)), camera.get("latitude"), camera.get("longitude")),
            ).fetchone()
            imported_cameras += int(result is not None)

        for case in case_rows:
            legacy_case_id = str(value(case, "caseId", "id", default="")).strip()
            if not legacy_case_id:
                continue
            detector_event_id = str(value(case, "detectorEventId", default=f"legacy:{legacy_case_id}"))
            raw_mode = str(value(case, "detectionMode", default="temporal_collision"))
            mode = raw_mode if raw_mode in {"temporal_collision", "aftermath_review"} else "temporal_collision"
            legacy_status = str(value(case, "status", default="pending_review")).lower()
            review_status = {
                "under_review": "UNDER_REVIEW", "false_alarm": "FALSE_ALARM",
                "confirmed": "CONFIRMED", "dispatching": "CONFIRMED", "resolved": "CONFIRMED",
            }.get(legacy_status, "PENDING_REVIEW")
            incident_state = {
                "false_alarm": "FALSE_ALARM", "confirmed": "CONFIRMED",
                "dispatching": "ACTIVE_RESPONSE", "resolved": "RESOLVED",
            }.get(legacy_status, "AWAITING_REVIEW")
            incident = pg.execute(
                """INSERT INTO incidents
                   (legacy_case_id,detector_event_id,camera_id,state,detection_mode,ai_score,evidence_summary,
                    media,location,latitude,longitude,detected_at,resolved_at)
                   VALUES (%s,%s,(SELECT id FROM cameras WHERE legacy_id=%s),%s,%s,%s,%s,%s,%s,%s,%s,%s,
                           CASE WHEN %s='RESOLVED' THEN COALESCE(%s,now()) ELSE NULL END)
                   ON CONFLICT(detector_event_id) DO NOTHING RETURNING id""",
                (legacy_case_id, detector_event_id, value(case, "cameraId"), incident_state, mode,
                 max(0.0, min(1.0, float(value(case, "confidence", "crashScore", default=0) or 0))),
                 Jsonb({"legacyImported": True}),
                 Jsonb({key: case.get(key) for key in ("originalPath", "keyFramePath", "thumbnailPath", "annotatedPath") if case.get(key)}),
                 value(case, "location"), case.get("latitude"), case.get("longitude"),
                 value(case, "detectedAt", "createdAt"), incident_state, value(case, "updatedAt", "detectedAt", "createdAt")),
            ).fetchone()
            if not incident:
                continue
            imported_incidents += 1
            pg.execute(
                """INSERT INTO review_cases(incident_id,status,false_alarm_reason,dispatcher_notes,reviewed_at)
                   VALUES (%s,%s,%s,%s,CASE WHEN %s IN ('CONFIRMED','FALSE_ALARM') THEN now() END)""",
                (incident["id"], review_status, case.get("falseAlarmReason"), case.get("notes"), review_status),
            )
            pg.execute(
                "INSERT INTO incident_timeline(incident_id,event_type,details) VALUES (%s,'LEGACY_IMPORTED',%s)",
                (incident["id"], Jsonb({"legacyCaseId": legacy_case_id})),
            )
    legacy.close()
    print(json.dumps({"camerasImported": imported_cameras, "incidentsImported": imported_incidents}))


if __name__ == "__main__":
    main()
