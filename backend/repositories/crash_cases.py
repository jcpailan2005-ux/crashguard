from datetime import datetime, timedelta
from pathlib import Path
import uuid

from backend.db import get_connection
from backend.media_store import copy_media_file, media_dir, relative_media_path


CASE_STATUSES = {
    "pending_review",
    "under_review",
    "confirmed_crash",
    "false_alarm",
    "dispatched",
    "resolved",
}

ACTION_NEXT_STATUS = {
    "review_alert": "under_review",
    "confirm_crash": "confirmed_crash",
    "mark_false_alarm": "false_alarm",
    "dispatch_help": "dispatched",
    "add_notes": None,
    "resolve_case": "resolved",
}

ALLOWED_ACTIONS = {
    "review_alert": {"pending_review"},
    "confirm_crash": {"under_review"},
    "mark_false_alarm": {"under_review"},
    "dispatch_help": {"confirmed_crash"},
    "add_notes": {"pending_review", "under_review", "confirmed_crash", "false_alarm", "dispatched"},
    "resolve_case": {"dispatched", "false_alarm"},
}


def now_iso() -> str:
    return datetime.now().isoformat()


def _row_to_case(row) -> dict:
    return {
        "caseId": row["caseId"],
        "status": row["status"],
        "confidence": row["confidence"],
        "createdAt": row["detectedAt"],
        "detectedAt": row["detectedAt"],
        "reviewedAt": row["reviewedAt"],
        "confirmedAt": row["confirmedAt"],
        "falseAlarmAt": row["falseAlarmAt"],
        "dispatchedAt": row["dispatchedAt"],
        "resolvedAt": row["resolvedAt"],
        "updatedAt": row["updatedAt"],
        "location": row["location"],
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "areaId": row["areaId"],
        "videoPath": row["videoPath"],
        "keyFramePath": row["keyFramePath"],
        "thumbnailPath": row["thumbnailPath"],
        "annotatedPath": row["annotatedPath"],
        "sourceCamera": row["sourceCamera"],
        "cameraId": row["cameraId"],
        "cameraName": row["cameraName"],
        "cameraIp": row["cameraIp"],
        "barangay": row["barangay"],
        "roadName": row["roadName"],
        "assignedResponderId": row["assignedResponderId"],
        "triggerStatus": row["triggerStatus"],
        "responderId": row["responderId"],
        "accidentDetected": bool(row["accidentDetected"]),
        "notes": row["notes"] or "",
    }


def _row_to_camera(row) -> dict:
    return {
        "cameraId": row["cameraId"],
        "label": row["label"],
        "name": row["label"],
        "cameraIp": row["cameraIp"],
        "areaId": row["areaId"],
        "barangay": row["barangay"] or row["areaId"],
        "roadName": row["roadName"],
        "locationDescription": row["locationDescription"],
        "location": row["location"],
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "streamUrl": row["streamUrl"],
        "cameraType": row["cameraType"],
        "status": row["status"] or "offline",
        "isActive": bool(row["isActive"]),
        "detectionEnabled": bool(row["detectionEnabled"]),
        "lastEventAt": row["lastEventAt"],
        "lastSeenAt": row["lastSeenAt"],
        "createdAt": row["createdAt"],
        "updatedAt": row["updatedAt"],
    }


def _row_to_action(row) -> dict:
    return {
        "actionId": row["actionId"],
        "caseId": row["caseId"],
        "action": row["action"],
        "actorId": row["actorId"],
        "timestamp": row["timestamp"],
        "notes": row["notes"] or "",
        "previousStatus": row["previousStatus"],
        "nextStatus": row["nextStatus"],
    }


def _row_to_box(row) -> dict:
    return {
        "boxId": row["boxId"],
        "caseId": row["caseId"],
        "label": row["label"],
        "confidence": row["confidence"],
        "x": row["x"],
        "y": row["y"],
        "width": row["width"],
        "height": row["height"],
        "framePath": row["framePath"],
        "detectedAt": row["detectedAt"],
    }


def _insert_detection_boxes(
    conn,
    case_id: str,
    boxes: list[dict],
    *,
    frame_path: str | None,
    detected_at: str,
) -> None:
    if not boxes:
        return
    conn.executemany(
        """
        INSERT INTO detection_boxes (
          boxId, caseId, label, confidence, x, y, width, height,
          framePath, detectedAt
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                f"BOX-{uuid.uuid4().hex}",
                case_id,
                box.get("label") or "unknown",
                float(box.get("confidence") or 0),
                float(box.get("x") or 0),
                float(box.get("y") or 0),
                float(box.get("width") or 0),
                float(box.get("height") or 0),
                frame_path,
                detected_at,
            )
            for box in boxes
        ],
    )


def create_crash_case(
    data: dict,
    *,
    boxes: list[dict] | None = None,
    frame_path: str | None = None,
) -> dict:
    case_id = data.get("caseId") or f"CASE-{uuid.uuid4().hex[:10].upper()}"
    detected_at = data.get("detectedAt") or now_iso()
    updated_at = data.get("updatedAt") or detected_at
    notification_id = f"NOT-{uuid.uuid4().hex}"
    area_id = data.get("areaId")
    if not area_id and data.get("triggerStatus") == "camera_detection":
        area_id = "demo"

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO crash_cases (
              caseId, status, confidence, detectedAt, updatedAt, location,
              latitude, longitude, areaId, videoPath, keyFramePath, thumbnailPath,
              annotatedPath, sourceCamera, cameraId, cameraName, cameraIp,
              barangay, roadName, assignedResponderId, triggerStatus, responderId,
              accidentDetected, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_id,
                data.get("status", "pending_review"),
                float(data.get("confidence") or 0),
                detected_at,
                updated_at,
                data.get("location"),
                data.get("latitude"),
                data.get("longitude"),
                area_id,
                data.get("videoPath"),
                data.get("keyFramePath"),
                data.get("thumbnailPath"),
                data.get("annotatedPath"),
                data.get("sourceCamera"),
                data.get("cameraId"),
                data.get("cameraName") or data.get("sourceCamera"),
                data.get("cameraIp"),
                data.get("barangay") or area_id,
                data.get("roadName"),
                data.get("assignedResponderId"),
                data.get("triggerStatus") or "unknown",
                data.get("responderId"),
                1 if data.get("accidentDetected") else 0,
                data.get("notes") or "",
            ),
        )
        conn.execute(
            """
            INSERT INTO crash_actions (
              actionId, caseId, action, actorId, timestamp, notes,
              previousStatus, nextStatus
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"ACT-{uuid.uuid4().hex}",
                case_id,
                "create_case",
                data.get("responderId") or "system",
                detected_at,
                "Possible crash detected. Awaiting responder review.",
                "pending_review",
                "pending_review",
            ),
        )
        if data.get("triggerStatus") == "camera_detection":
            camera_label = data.get("cameraName") or data.get("sourceCamera") or "Live Camera"
            area_label = area_id or data.get("barangay")
            area_suffix = f" in {area_label}" if area_label else ""
            camera_message = f"A pending review case was created from {camera_label}{area_suffix}."
        else:
            camera_message = "Crash alert needs responder review."
        conn.execute(
            """
            INSERT INTO notifications (
              notificationId, caseId, title, message, alertLevel, read,
              responderId, areaId, createdAt
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                notification_id,
                case_id,
                "Possible Crash Detected",
                camera_message,
                "review",
                0,
                data.get("responderId"),
                area_id,
                detected_at,
            ),
        )
        if data.get("cameraId"):
            conn.execute(
                "UPDATE cameras SET lastEventAt = ?, updatedAt = ? WHERE cameraId = ?",
                (detected_at, updated_at, data.get("cameraId")),
            )
        _insert_detection_boxes(
            conn,
            case_id,
            boxes or [],
            frame_path=frame_path,
            detected_at=detected_at,
        )
    case_item = get_crash_case(case_id)
    if case_item is not None:
        case_item["createdNotificationId"] = notification_id
    return case_item


def find_unresolved_camera_case(
    camera_ip: str | None = None,
    camera_id: str | None = None,
    source_camera: str | None = None,
    *,
    area_id: str | None = None,
    location: str | None = None,
    block_minutes: int | None = None,
    block_seconds: int | None = None,
) -> dict | None:
    camera_ip = (camera_ip or "").strip() or None
    camera_id = (camera_id or "").strip() or None
    source_camera = (source_camera or "").strip() or None
    area_id = (area_id or "").strip() or None
    location = (location or "").strip() or None
    if not camera_ip and not camera_id and not source_camera:
        return None
    if camera_id:
        camera_clause = "cameraId = ? AND cameraId IS NOT NULL AND cameraId != ''"
        camera_value = camera_id
    elif camera_ip:
        camera_clause = "cameraIp = ? AND cameraIp IS NOT NULL AND cameraIp != ''"
        camera_value = camera_ip
    else:
        camera_clause = "sourceCamera = ? AND sourceCamera IS NOT NULL AND sourceCamera != ''"
        camera_value = source_camera
    with get_connection() as conn:
        params: list[object] = [camera_value]
        area_clause = ""
        if area_id:
            area_clause = "AND areaId = ?"
            params.append(area_id)
        location_clause = ""
        if location:
            location_clause = "AND location = ?"
            params.append(location)
        age_clause = ""
        if block_seconds is not None and block_seconds > 0:
            cutoff = datetime.now() - timedelta(seconds=block_seconds)
            age_clause = "AND datetime(detectedAt) >= datetime(?)"
            params.append(cutoff.isoformat())
        elif block_minutes is not None and block_minutes > 0:
            cutoff = datetime.now() - timedelta(minutes=block_minutes)
            age_clause = "AND datetime(detectedAt) >= datetime(?)"
            params.append(cutoff.isoformat())
        row = conn.execute(
            f"""
            SELECT * FROM crash_cases
            WHERE {camera_clause}
              {area_clause}
              {location_clause}
              AND triggerStatus = 'camera_detection'
              AND status IN ('pending_review', 'under_review')
              {age_clause}
            ORDER BY detectedAt DESC
            LIMIT 1
            """,
            params,
        ).fetchone()
        if row is None:
            return None
    return get_crash_case(row["caseId"])


def list_crash_cases(
    *,
    status: str | None = None,
    area_id: str | None = None,
    search: str | None = None,
    date: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    sort: str = "newest",
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    clauses = []
    params: list[object] = []
    if status and status != "all":
        clauses.append("status = ?")
        params.append(status)
    if area_id and area_id != "all":
        clauses.append("areaId = ?")
        params.append(area_id)
    if search:
        clauses.append("(caseId LIKE ? OR location LIKE ? OR sourceCamera LIKE ?)")
        term = f"%{search}%"
        params.extend([term, term, term])
    if date:
        clauses.append("substr(detectedAt, 1, 10) = ?")
        params.append(date)
    else:
        if from_date:
            clauses.append("substr(detectedAt, 1, 10) >= ?")
            params.append(from_date)
        if to_date:
            clauses.append("substr(detectedAt, 1, 10) <= ?")
            params.append(to_date)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    order = "ASC" if sort == "oldest" else "DESC"
    params.extend([limit, offset])
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM crash_cases
            {where}
            ORDER BY detectedAt {order}
            LIMIT ? OFFSET ?
            """,
            params,
        ).fetchall()
    return [_row_to_case(row) for row in rows]


def get_crash_case(case_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM crash_cases WHERE caseId = ?",
            (case_id,),
        ).fetchone()
        if row is None:
            return None
        actions = conn.execute(
            "SELECT * FROM crash_actions WHERE caseId = ? ORDER BY timestamp ASC",
            (case_id,),
        ).fetchall()
        notification = conn.execute(
            """
            SELECT notificationId
            FROM notifications
            WHERE caseId = ?
            ORDER BY createdAt DESC
            LIMIT 1
            """,
            (case_id,),
        ).fetchone()
    case_item = _row_to_case(row)
    case_item["notificationId"] = notification["notificationId"] if notification else None
    case_item["actions"] = [_row_to_action(action) for action in actions]
    case_item["boxes"] = list_detection_boxes(case_id)
    case_item["detections"] = [
        {
            "label": box["label"],
            "score": box["confidence"],
            "box": [
                box["x"],
                box["y"],
                box["x"] + box["width"],
                box["y"] + box["height"],
            ],
        }
        for box in case_item["boxes"]
    ]
    return case_item


def list_detection_boxes(case_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM detection_boxes WHERE caseId = ? ORDER BY confidence DESC",
            (case_id,),
        ).fetchall()
    return [_row_to_box(row) for row in rows]


def save_detection_boxes(
    case_id: str,
    boxes: list[dict],
    *,
    frame_path: str | None,
    detected_at: str,
) -> None:
    if not boxes:
        return
    with get_connection() as conn:
        _insert_detection_boxes(
            conn,
            case_id,
            boxes,
            frame_path=frame_path,
            detected_at=detected_at,
        )


def replace_case_evidence(
    case_id: str,
    *,
    key_frame_path: Path | None,
    thumbnail_path: Path | None = None,
    annotated_path: Path | None = None,
    boxes: list[dict] | None = None,
    detected_at: str | None = None,
) -> dict | None:
    timestamp = detected_at or now_iso()
    folder = media_dir(case_id)
    suffix = uuid.uuid4().hex[:8]
    key_frame = copy_media_file(key_frame_path, folder / f"keyframe_{suffix}.jpg")
    thumbnail = copy_media_file(
        thumbnail_path or key_frame_path,
        folder / f"thumbnail_{suffix}.jpg",
    )
    annotated_suffix = (annotated_path.suffix if annotated_path else ".jpg") or ".jpg"
    annotated = copy_media_file(
        annotated_path,
        folder / f"annotated_{suffix}{annotated_suffix}",
    )

    key_frame_relative = relative_media_path(key_frame)
    thumbnail_relative = relative_media_path(thumbnail)
    annotated_relative = relative_media_path(annotated)

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE crash_cases
            SET keyFramePath = COALESCE(?, keyFramePath),
                thumbnailPath = COALESCE(?, thumbnailPath),
                annotatedPath = COALESCE(?, annotatedPath),
                updatedAt = ?
            WHERE caseId = ?
            """,
            (
                key_frame_relative,
                thumbnail_relative,
                annotated_relative,
                timestamp,
                case_id,
            ),
        )
        if boxes is not None:
            conn.execute("DELETE FROM detection_boxes WHERE caseId = ?", (case_id,))
            _insert_detection_boxes(
                conn,
                case_id,
                boxes,
                frame_path=key_frame_relative or annotated_relative,
                detected_at=timestamp,
            )
    return get_crash_case(case_id)


def apply_action(case_id: str, action: str, actor_id: str | None, notes: str | None) -> dict:
    case_item = get_crash_case(case_id)
    if case_item is None:
        raise KeyError(case_id)
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"Unsupported action: {action}")
    previous_status = case_item["status"]
    if previous_status not in ALLOWED_ACTIONS[action]:
        raise ValueError(f"Cannot {action} while case is {previous_status}.")

    next_status = ACTION_NEXT_STATUS[action] or previous_status
    timestamp = now_iso()
    timestamp_updates = {
        "review_alert": ("reviewedAt", timestamp),
        "confirm_crash": ("confirmedAt", timestamp),
        "mark_false_alarm": ("falseAlarmAt", timestamp),
        "dispatch_help": ("dispatchedAt", timestamp),
        "resolve_case": ("resolvedAt", timestamp),
    }
    field_update_sql = ""
    field_update_params: tuple[str, ...] = ()
    if action in timestamp_updates:
        field_name, field_value = timestamp_updates[action]
        field_update_sql = f"{field_name} = ?,"
        field_update_params = (field_value,)

    with get_connection() as conn:
        conn.execute(
            f"""
            UPDATE crash_cases
            SET status = ?, responderId = ?, {field_update_sql} updatedAt = ?,
                notes = CASE WHEN ? != '' THEN trim(coalesce(notes, '') || char(10) || ?) ELSE notes END
            WHERE caseId = ?
            """,
            (
                next_status,
                actor_id,
                *field_update_params,
                timestamp,
                (notes or "").strip(),
                (notes or "").strip(),
                case_id,
            ),
        )
        conn.execute(
            """
            INSERT INTO crash_actions (
              actionId, caseId, action, actorId, timestamp, notes,
              previousStatus, nextStatus
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"ACT-{uuid.uuid4().hex}",
                case_id,
                action,
                actor_id or "unknown",
                timestamp,
                notes or "",
                previous_status,
                next_status,
            ),
        )
        conn.execute(
            "UPDATE notifications SET read = 1 WHERE caseId = ?",
            (case_id,),
        )
    return get_crash_case(case_id)


def list_notifications(
    *,
    role: str | None = None,
    responder_id: str | None = None,
    area_id: str | None = None,
) -> list[dict]:
    clauses = []
    params: list[object] = []
    if role == "responder":
        responder_clauses = ["n.responderId IS NULL"]
        if responder_id:
            responder_clauses.append("n.responderId = ?")
            params.append(responder_id)
        if area_id:
            responder_clauses.append("COALESCE(n.areaId, c.areaId) = ?")
            params.append(area_id)
        clauses.append(f"({' OR '.join(responder_clauses)})")

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                   n.notificationId,
                   n.caseId,
                   n.title,
                   n.message,
                   n.alertLevel,
                   n.read,
                   n.responderId,
                   COALESCE(n.areaId, c.areaId) AS areaId,
                   COALESCE(n.createdAt, c.detectedAt) AS createdAt,
                   c.sourceCamera,
                   c.cameraId,
                   c.cameraName,
                   c.cameraIp,
                   c.triggerStatus,
                   COALESCE(c.keyFramePath, c.thumbnailPath, c.annotatedPath) AS evidenceImageUrl,
                   c.annotatedPath AS annotatedImageUrl,
                   COALESCE(c.videoPath, c.keyFramePath, c.thumbnailPath, c.annotatedPath) AS mediaUrl,
                   c.thumbnailPath AS thumbnailUrl,
                   CASE
                     WHEN c.videoPath IS NOT NULL
                       OR c.keyFramePath IS NOT NULL
                       OR c.thumbnailPath IS NOT NULL
                       OR c.annotatedPath IS NOT NULL
                     THEN 1
                     ELSE 0
                   END AS hasEvidence
            FROM notifications n
            LEFT JOIN crash_cases c ON c.caseId = n.caseId
            {where_sql}
            ORDER BY COALESCE(n.createdAt, c.detectedAt) DESC
            LIMIT 100
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def archive_notification(notification_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE notifications SET read = 1 WHERE notificationId = ?",
            (notification_id,),
        )
    return cursor.rowcount > 0


def delete_notification(notification_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM notifications WHERE notificationId = ?",
            (notification_id,),
        )
    return cursor.rowcount > 0


def get_user_profile(uid: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE uid = ?",
            (uid,),
        ).fetchone()
    return dict(row) if row else None


def get_user_profile_by_email(email: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE lower(email) = lower(?)",
            (email,),
        ).fetchone()
    return dict(row) if row else None


def update_user_last_login(uid: str, timestamp: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET lastLoginAt = ?, updatedAt = ? WHERE uid = ?",
            (timestamp, timestamp, uid),
        )


def upsert_user_profile(data: dict) -> dict:
    timestamp = data.get("updatedAt") or now_iso()
    uid = data.get("uid")
    if not uid:
        raise ValueError("uid is required")
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO users (
              uid, email, displayName, role, areaId, passwordHash, passwordSalt,
              isActive, lastLoginAt, createdAt, updatedAt
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(uid) DO UPDATE SET
              email = excluded.email,
              displayName = excluded.displayName,
              role = excluded.role,
              areaId = excluded.areaId,
              passwordHash = coalesce(excluded.passwordHash, users.passwordHash),
              passwordSalt = coalesce(excluded.passwordSalt, users.passwordSalt),
              isActive = excluded.isActive,
              lastLoginAt = coalesce(excluded.lastLoginAt, users.lastLoginAt),
              updatedAt = excluded.updatedAt
            """,
            (
                uid,
                data.get("email") or f"{uid}@local.test",
                data.get("displayName") or "",
                data.get("role") or "user",
                data.get("areaId"),
                data.get("passwordHash"),
                data.get("passwordSalt"),
                1 if data.get("isActive", data.get("active", True)) else 0,
                data.get("lastLoginAt"),
                data.get("createdAt") or timestamp,
                timestamp,
            ),
        )
        row = conn.execute("SELECT * FROM users WHERE uid = ?", (uid,)).fetchone()
    return dict(row)


def get_camera(camera_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM cameras WHERE cameraId = ?",
            (camera_id,),
        ).fetchone()
    return _row_to_camera(row) if row else None


def get_camera_by_ip(camera_ip: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM cameras WHERE cameraIp = ? ORDER BY updatedAt DESC LIMIT 1",
            (camera_ip,),
        ).fetchone()
    return _row_to_camera(row) if row else None


def list_cameras(
    *,
    role: str | None = None,
    user_id: str | None = None,
    area_id: str | None = None,
    include_inactive: bool = False,
) -> list[dict]:
    clauses = []
    params: list[object] = []
    if not include_inactive:
        clauses.append("c.isActive = 1")
    if role == "responder":
        clauses.append(
            """
            (
              c.areaId = ?
              OR EXISTS (
                SELECT 1 FROM responder_camera_assignments a
                WHERE a.cameraId = c.cameraId
                  AND a.responderId = ?
                  AND a.status = 'active'
              )
            )
            """
        )
        params.extend([area_id, user_id])
    elif area_id and area_id != "all":
        clauses.append("c.areaId = ?")
        params.append(area_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT c.* FROM cameras c {where} ORDER BY c.areaId ASC, c.roadName ASC, c.label ASC",
            params,
        ).fetchall()
    return [_row_to_camera(row) for row in rows]


def upsert_camera(data: dict) -> dict:
    camera_id = data.get("cameraId") or f"CAM-{uuid.uuid4().hex[:10].upper()}"
    timestamp = data.get("updatedAt") or now_iso()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO cameras (
              cameraId, label, cameraIp, areaId, barangay, roadName,
              locationDescription, location, latitude, longitude, streamUrl,
              cameraType, status, isActive, detectionEnabled, lastEventAt,
              lastSeenAt, createdAt, updatedAt
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cameraId) DO UPDATE SET
              label = excluded.label,
              cameraIp = excluded.cameraIp,
              areaId = excluded.areaId,
              barangay = excluded.barangay,
              roadName = excluded.roadName,
              locationDescription = excluded.locationDescription,
              location = excluded.location,
              latitude = excluded.latitude,
              longitude = excluded.longitude,
              streamUrl = excluded.streamUrl,
              cameraType = excluded.cameraType,
              status = excluded.status,
              isActive = excluded.isActive,
              detectionEnabled = excluded.detectionEnabled,
              lastEventAt = excluded.lastEventAt,
              lastSeenAt = excluded.lastSeenAt,
              updatedAt = excluded.updatedAt
            """,
            (
                camera_id,
                data.get("label") or "Authorized Camera",
                data.get("cameraIp"),
                data.get("areaId"),
                data.get("barangay") or data.get("areaId"),
                data.get("roadName"),
                data.get("locationDescription"),
                data.get("location"),
                data.get("latitude"),
                data.get("longitude"),
                data.get("streamUrl"),
                data.get("cameraType"),
                data.get("status") or "connected",
                1 if data.get("isActive", True) else 0,
                1 if data.get("detectionEnabled", True) else 0,
                data.get("lastEventAt"),
                timestamp,
                data.get("createdAt") or timestamp,
                timestamp,
            ),
        )
        row = conn.execute(
            "SELECT * FROM cameras WHERE cameraId = ?",
            (camera_id,),
        ).fetchone()
    return _row_to_camera(row)


def set_camera_active(camera_id: str, active: bool) -> dict | None:
    timestamp = now_iso()
    with get_connection() as conn:
        conn.execute(
            "UPDATE cameras SET isActive = ?, updatedAt = ? WHERE cameraId = ?",
            (1 if active else 0, timestamp, camera_id),
        )
    return get_camera(camera_id)


def delete_camera(camera_id: str) -> None:
    set_camera_active(camera_id, False)


def assign_camera(data: dict) -> dict:
    assignment_id = data.get("id") or f"ASG-{uuid.uuid4().hex[:10].upper()}"
    timestamp = now_iso()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO responder_camera_assignments (
              id, responderId, areaId, cameraId, role, status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              responderId = excluded.responderId,
              areaId = excluded.areaId,
              cameraId = excluded.cameraId,
              role = excluded.role,
              status = excluded.status,
              updated_at = excluded.updated_at
            """,
            (
                assignment_id,
                data.get("responderId"),
                data.get("areaId"),
                data.get("cameraId"),
                data.get("role") or "viewer",
                data.get("status") or "active",
                data.get("created_at") or timestamp,
                timestamp,
            ),
        )
        row = conn.execute(
            "SELECT * FROM responder_camera_assignments WHERE id = ?",
            (assignment_id,),
        ).fetchone()
    return dict(row)


def seed_demo_camera_data() -> None:
    timestamp = now_iso()
    areas = [
        ("talomo", "Talomo", "Davao City"),
        ("matina", "Matina", "Davao City"),
        ("toril", "Toril", "Davao City"),
    ]
    cameras = [
        {
            "cameraId": "CAM-TALOMO-CROSSING",
            "label": "Talomo Crossing CCTV",
            "areaId": "talomo",
            "barangay": "Talomo",
            "roadName": "McArthur Highway",
            "locationDescription": "Talomo Crossing approach",
            "cameraIp": "demo-talomo-crossing",
            "streamUrl": "demo://talomo-crossing",
            "cameraType": "Demo",
            "status": "offline",
            "latitude": 7.0644,
            "longitude": 125.5889,
            "detectionEnabled": True,
        },
        {
            "cameraId": "CAM-TALOMO-HIGHWAY",
            "label": "Talomo Highway CCTV",
            "areaId": "talomo",
            "barangay": "Talomo",
            "roadName": "Talomo Highway",
            "locationDescription": "Highway traffic monitoring point",
            "cameraIp": "demo-talomo-highway",
            "streamUrl": "demo://talomo-highway",
            "cameraType": "Demo",
            "status": "offline",
            "latitude": 7.0618,
            "longitude": 125.5861,
            "detectionEnabled": True,
        },
        {
            "cameraId": "CAM-TALOMO-MARKET",
            "label": "Talomo Market CCTV",
            "areaId": "talomo",
            "barangay": "Talomo",
            "roadName": "Talomo Market Road",
            "locationDescription": "Market road junction",
            "cameraIp": "demo-talomo-market",
            "streamUrl": "demo://talomo-market",
            "cameraType": "Demo",
            "status": "offline",
            "latitude": 7.0671,
            "longitude": 125.5902,
            "detectionEnabled": False,
        },
        {
            "cameraId": "CAM-MATINA-CROSSING",
            "label": "Matina Crossing CCTV",
            "areaId": "matina",
            "barangay": "Matina",
            "roadName": "Matina Crossing",
            "locationDescription": "Matina crossing main road",
            "cameraIp": "demo-matina-crossing",
            "streamUrl": "demo://matina-crossing",
            "cameraType": "Demo",
            "status": "offline",
            "latitude": 7.0649,
            "longitude": 125.6003,
            "detectionEnabled": True,
        },
        {
            "cameraId": "CAM-TORIL-MAIN",
            "label": "Toril Main Road CCTV",
            "areaId": "toril",
            "barangay": "Toril",
            "roadName": "Toril Main Road",
            "locationDescription": "Toril main road monitoring point",
            "cameraIp": "demo-toril-main",
            "streamUrl": "demo://toril-main",
            "cameraType": "Demo",
            "status": "offline",
            "latitude": 7.0185,
            "longitude": 125.4971,
            "detectionEnabled": True,
        },
    ]
    with get_connection() as conn:
        for area_id, name, city in areas:
            conn.execute(
                """
                INSERT INTO areas (id, name, city, status, created_at, updated_at)
                VALUES (?, ?, ?, 'active', ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  name = excluded.name,
                  city = excluded.city,
                  updated_at = excluded.updated_at
                """,
                (area_id, name, city, timestamp, timestamp),
            )
    for camera in cameras:
        if get_camera(camera["cameraId"]) is None:
            upsert_camera(camera)
