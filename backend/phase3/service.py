from __future__ import annotations

import json
import os
import uuid
from datetime import timedelta
from typing import Any

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from backend.camera_privacy import public_camera_data
from backend.phase3.database import connection
from backend.phase3.security import (
    generate_session_token,
    generate_temporary_password,
    hash_password,
    hash_session_token,
    session_expiry,
    utcnow,
    validate_password,
    verify_password,
)


ACTIVE_ASSIGNMENT_STATES = {"ASSIGNED", "ACCEPTED", "EN_ROUTE", "ARRIVED", "RESPONDING"}
RESPONDER_ONLINE_TIMEOUT_SECONDS = max(
    30, int(os.getenv("CRASHGUARD_RESPONDER_ONLINE_TIMEOUT_SECONDS", "60"))
)
ASSIGNMENT_TRANSITIONS = {
    "ASSIGNED": {"ACCEPTED", "DECLINED"},
    "ACCEPTED": {"EN_ROUTE"},
    "EN_ROUTE": {"ARRIVED"},
    "ARRIVED": {"RESPONDING"},
    "RESPONDING": {"RESOLVED"},
}
TRANSITION_PERMISSION = {
    "ACCEPTED": "assignments.accept",
    "DECLINED": "assignments.decline",
    "EN_ROUTE": "response.en_route",
    "ARRIVED": "response.arrive",
    "RESPONDING": "response.start",
    "RESOLVED": "response.resolve",
}
TRANSITION_TIMESTAMP = {
    "ACCEPTED": "accepted_at",
    "DECLINED": "declined_at",
    "EN_ROUTE": "en_route_at",
    "ARRIVED": "arrived_at",
    "RESPONDING": "responding_at",
    "RESOLVED": "resolved_at",
}


class DomainError(RuntimeError):
    status_code = 400


class NotFound(DomainError):
    status_code = 404


class Conflict(DomainError):
    status_code = 409


class Forbidden(DomainError):
    status_code = 403


def _json(value: Any) -> Jsonb:
    return Jsonb(_serialize(value if value is not None else {}))


def _serialize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, (uuid.UUID,)):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


USER_PRINCIPAL_SQL = """
SELECT u.id, u.email, u.full_name, u.status, u.must_change_password, u.area_id,
       u.availability_status, u.last_login_at, u.created_at, u.updated_at,
       COALESCE(array_agg(DISTINCT r.name) FILTER (WHERE r.name IS NOT NULL), '{}') AS roles,
       COALESCE(array_agg(DISTINCT p.code) FILTER (WHERE p.code IS NOT NULL), '{}') AS permissions
FROM users u
LEFT JOIN user_roles ur ON ur.user_id=u.id
LEFT JOIN roles r ON r.id=ur.role_id
LEFT JOIN role_permissions rp ON rp.role_id=r.id
LEFT JOIN permissions p ON p.id=rp.permission_id
WHERE u.id=%s
GROUP BY u.id
"""


def _principal_row(conn, user_id: str) -> dict | None:
    return conn.execute(USER_PRINCIPAL_SQL, (user_id,)).fetchone()


def safe_user(row: dict) -> dict:
    roles = list(row.get("roles") or [])
    role = roles[0] if roles else None
    return _serialize(
        {
            "uid": row["id"],
            "id": row["id"],
            "email": row["email"],
            "displayName": row["full_name"],
            "fullName": row["full_name"],
            "role": role.lower() if role else None,
            "roles": roles,
            "permissions": list(row.get("permissions") or []),
            "areaId": row.get("area_id"),
            "active": row["status"] == "ACTIVE",
            "status": row["status"],
            "mustChangePassword": row["must_change_password"],
            "availabilityStatus": row.get("availability_status"),
            "lastLoginAt": row.get("last_login_at"),
            "createdAt": row.get("created_at"),
            "updatedAt": row.get("updated_at"),
        }
    )


def get_principal_by_id(user_id: str) -> dict | None:
    with connection() as conn:
        row = _principal_row(conn, user_id)
    return safe_user(row) if row else None


def authenticate_session(token: str) -> dict | None:
    token_hash = hash_session_token(token)
    now = utcnow()
    with connection() as conn, conn.transaction():
        session = conn.execute(
            """SELECT id, user_id FROM sessions
               WHERE token_hash=%s AND revoked_at IS NULL AND expires_at>%s
               FOR UPDATE""",
            (token_hash, now),
        ).fetchone()
        if not session:
            return None
        row = _principal_row(conn, str(session["user_id"]))
        if not row or row["status"] != "ACTIVE":
            conn.execute(
                "UPDATE sessions SET revoked_at=%s WHERE id=%s AND revoked_at IS NULL",
                (now, session["id"]),
            )
            return None
        conn.execute("UPDATE sessions SET last_used_at=%s WHERE id=%s", (now, session["id"]))
    principal = safe_user(row)
    principal["sessionId"] = str(session["id"])
    return principal


def authenticate_stream_session(session_id: str, user_id: str) -> dict | None:
    try:
        uuid.UUID(session_id)
        uuid.UUID(user_id)
    except (ValueError, TypeError):
        return None
    with connection() as conn:
        session = conn.execute(
            "SELECT id FROM sessions WHERE id=%s AND user_id=%s AND revoked_at IS NULL AND expires_at>now()",
            (session_id, user_id),
        ).fetchone()
        row = _principal_row(conn, user_id) if session else None
    if not row or row["status"] != "ACTIVE" or row["must_change_password"]:
        return None
    return safe_user(row)


def login(email: str, password: str, *, user_agent: str | None, ip_address: str | None) -> dict:
    normalized = (email or "").strip().lower()
    with connection() as conn, conn.transaction():
        account = conn.execute(
            "SELECT id, password_hash, status FROM users WHERE email=%s FOR UPDATE",
            (normalized,),
        ).fetchone()
        if not account or not verify_password(password, account["password_hash"]):
            raise Forbidden("Invalid email or password.")
        if account["status"] != "ACTIVE":
            raise Forbidden("This account is not active.")
        token = generate_session_token()
        now = utcnow()
        session = conn.execute(
            """INSERT INTO sessions
               (user_id, token_hash, expires_at, user_agent, ip_address)
               VALUES (%s,%s,%s,%s,%s) RETURNING id""",
            (account["id"], hash_session_token(token), session_expiry(), user_agent, ip_address),
        ).fetchone()
        conn.execute("UPDATE users SET last_login_at=%s, updated_at=%s WHERE id=%s", (now, now, account["id"]))
        conn.execute(
            """INSERT INTO audit_logs(actor_user_id,action,entity_type,entity_id,metadata)
               VALUES (%s,'auth.login','session',%s,%s)""",
            (account["id"], str(session["id"]), _json({"ip": ip_address})),
        )
        principal = safe_user(_principal_row(conn, str(account["id"])))
    return {"token": token, "user": principal}


def logout(session_id: str, actor_id: str) -> None:
    with connection() as conn, conn.transaction():
        conn.execute(
            "UPDATE sessions SET revoked_at=now() WHERE id=%s AND user_id=%s AND revoked_at IS NULL",
            (session_id, actor_id),
        )
        conn.execute(
            """UPDATE users u SET availability_status='OFFLINE',updated_at=now()
               WHERE u.id=%s
                 AND u.availability_status='AVAILABLE'
                 AND NOT EXISTS (
                   SELECT 1 FROM sessions s
                   WHERE s.user_id=u.id AND s.revoked_at IS NULL AND s.expires_at>now()
                 )""",
            (actor_id,),
        )
        _audit(conn, actor_id, "auth.logout", "session", session_id)


def change_password(actor: dict, current_password: str, new_password: str) -> dict:
    new_hash = hash_password(new_password)
    with connection() as conn, conn.transaction():
        row = conn.execute(
            "SELECT password_hash FROM users WHERE id=%s FOR UPDATE", (actor["id"],)
        ).fetchone()
        if not row or not verify_password(current_password, row["password_hash"]):
            raise Forbidden("Current password is incorrect.")
        conn.execute(
            """UPDATE users SET password_hash=%s, must_change_password=FALSE,
               updated_at=now() WHERE id=%s""",
            (new_hash, actor["id"]),
        )
        conn.execute(
            """INSERT INTO audit_logs(actor_user_id,action,entity_type,entity_id)
               VALUES (%s,'auth.password_changed','user',%s)""",
            (actor["id"], actor["id"]),
        )
        principal = safe_user(_principal_row(conn, actor["id"]))
    return principal


def _audit(conn, actor_id: str | None, action: str, entity_type: str, entity_id: str,
           *, before: Any = None, after: Any = None, metadata: Any = None) -> None:
    conn.execute(
        """INSERT INTO audit_logs
           (actor_user_id,action,entity_type,entity_id,before_data,after_data,metadata)
           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
        (actor_id, action, entity_type, entity_id,
         _json(public_camera_data(before)) if before is not None else None,
         _json(public_camera_data(after)) if after is not None else None,
         _json(metadata) if metadata is not None else None),
    )


def update_own_profile(actor: dict, *, full_name: str) -> dict:
    normalized_name = full_name.strip()
    if len(normalized_name) < 2 or len(normalized_name) > 160:
        raise DomainError("Full name must be between 2 and 160 characters.")
    with connection() as conn, conn.transaction():
        before = conn.execute(
            "SELECT full_name FROM users WHERE id=%s FOR UPDATE", (actor["id"],)
        ).fetchone()
        if not before:
            raise NotFound("User not found.")
        conn.execute(
            "UPDATE users SET full_name=%s,updated_at=now() WHERE id=%s",
            (normalized_name, actor["id"]),
        )
        _audit(
            conn,
            actor["id"],
            "profile.updated_own",
            "user",
            actor["id"],
            before={"fullName": before["full_name"]},
            after={"fullName": normalized_name},
        )
        updated = _principal_row(conn, actor["id"])
    return safe_user(updated)


def get_own_preferences(actor: dict) -> dict:
    with connection() as conn, conn.transaction():
        conn.execute(
            "INSERT INTO user_preferences(user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING",
            (actor["id"],),
        )
        row = conn.execute(
            "SELECT theme,notification_preferences,updated_at FROM user_preferences WHERE user_id=%s",
            (actor["id"],),
        ).fetchone()
    return _serialize(row)


def update_own_preferences(
    actor: dict,
    *,
    theme: str | None,
    notification_preferences: dict[str, Any] | None,
) -> dict:
    normalized_theme = theme.lower() if theme else None
    if normalized_theme is not None and normalized_theme not in {"light", "dark", "system"}:
        raise DomainError("Theme must be light, dark, or system.")
    if notification_preferences is not None and not isinstance(notification_preferences, dict):
        raise DomainError("Notification preferences must be an object.")
    with connection() as conn, conn.transaction():
        before = conn.execute(
            "SELECT theme,notification_preferences FROM user_preferences WHERE user_id=%s FOR UPDATE",
            (actor["id"],),
        ).fetchone()
        previous_theme = before["theme"] if before else "system"
        previous_notifications = before["notification_preferences"] if before else {}
        next_theme = normalized_theme or previous_theme
        next_notifications = {
            **previous_notifications,
            **(notification_preferences or {}),
        }
        row = conn.execute(
            """INSERT INTO user_preferences(user_id,theme,notification_preferences)
               VALUES (%s,%s,%s)
               ON CONFLICT(user_id) DO UPDATE SET
                 theme=excluded.theme,
                 notification_preferences=excluded.notification_preferences,
                 updated_at=now()
               RETURNING theme,notification_preferences,updated_at""",
            (actor["id"], next_theme, _json(next_notifications)),
        ).fetchone()
        _audit(
            conn,
            actor["id"],
            "preferences.updated_own",
            "user_preferences",
            actor["id"],
            before={"theme": previous_theme, "notificationPreferences": previous_notifications},
            after={"theme": next_theme, "notificationPreferences": next_notifications},
        )
    return _serialize(row)


def _timeline(conn, incident_id: str, event_type: str, actor_id: str | None, details: Any = None) -> None:
    conn.execute(
        "INSERT INTO incident_timeline(incident_id,actor_user_id,event_type,details) VALUES (%s,%s,%s,%s)",
        (incident_id, actor_id, event_type, _json(details)),
    )


def create_user(actor: dict | None, *, email: str, full_name: str, role: str,
                area_id: str | None = None, status: str = "ACTIVE") -> dict:
    role = role.upper()
    if role not in {"ADMIN", "DISPATCHER", "RESPONDER"}:
        raise DomainError("Unsupported role.")
    if status not in {"ACTIVE", "DISABLED", "LOCKED"}:
        raise DomainError("Unsupported account status.")
    temporary_password = generate_temporary_password()
    password_hash = hash_password(temporary_password)
    try:
        with connection() as conn, conn.transaction():
            user = conn.execute(
                """INSERT INTO users(email,full_name,password_hash,status,must_change_password,area_id)
                   VALUES (%s,%s,%s,%s,TRUE,%s) RETURNING id""",
                (email.strip().lower(), full_name.strip(), password_hash, status, area_id),
            ).fetchone()
            conn.execute(
                """INSERT INTO user_roles(user_id,role_id)
                   SELECT %s,id FROM roles WHERE name=%s""",
                (user["id"], role),
            )
            _audit(conn, actor.get("id") if actor else None, "user.created", "user", str(user["id"]),
                   after={"email": email.strip().lower(), "role": role, "status": status})
            result = safe_user(_principal_row(conn, str(user["id"])))
    except UniqueViolation as error:
        raise Conflict("An account with that email already exists.") from error
    result["temporaryPassword"] = temporary_password
    return result


def list_users(*, search: str | None = None, role: str | None = None,
               status: str | None = None) -> list[dict]:
    clauses = ["TRUE"]
    params: list[Any] = []
    if search:
        clauses.append("(u.email ILIKE %s OR u.full_name ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])
    if role:
        clauses.append("r.name=%s")
        params.append(role.upper())
    if status:
        clauses.append("u.status=%s")
        params.append(status.upper())
    sql = f"""SELECT u.id FROM users u
              LEFT JOIN user_roles ur ON ur.user_id=u.id
              LEFT JOIN roles r ON r.id=ur.role_id
              WHERE {' AND '.join(clauses)} ORDER BY u.created_at DESC"""
    with connection() as conn:
        ids = [str(row["id"]) for row in conn.execute(sql, params).fetchall()]
        return [safe_user(_principal_row(conn, user_id)) for user_id in ids]


def update_user_status(actor: dict, user_id: str, status: str) -> dict:
    status = status.upper()
    if status not in {"ACTIVE", "DISABLED", "LOCKED"}:
        raise DomainError("Unsupported account status.")
    with connection() as conn, conn.transaction():
        before = conn.execute("SELECT status FROM users WHERE id=%s FOR UPDATE", (user_id,)).fetchone()
        if not before:
            raise NotFound("User not found.")
        conn.execute(
            """UPDATE users SET status=%s, disabled_at=CASE WHEN %s='DISABLED' THEN now() ELSE NULL END,
               updated_at=now() WHERE id=%s""", (status, status, user_id)
        )
        if status != "ACTIVE":
            conn.execute("UPDATE sessions SET revoked_at=now() WHERE user_id=%s AND revoked_at IS NULL", (user_id,))
        _audit(conn, actor["id"], "user.status_changed", "user", user_id,
               before={"status": before["status"]}, after={"status": status})
        return safe_user(_principal_row(conn, user_id))


def update_user(actor: dict, user_id: str, *, email: str | None,
                full_name: str | None, area_id: str | None) -> dict:
    try:
        with connection() as conn, conn.transaction():
            before = _principal_row(conn, user_id)
            if not before:
                raise NotFound("User not found.")
            conn.execute(
                """UPDATE users SET email=COALESCE(%s,email),full_name=COALESCE(%s,full_name),
                   area_id=%s,updated_at=now() WHERE id=%s""",
                (email.strip().lower() if email else None,
                 full_name.strip() if full_name else None, area_id, user_id),
            )
            updated = _principal_row(conn, user_id)
            _audit(conn, actor["id"], "user.updated", "user", user_id,
                   before={"email": before["email"], "fullName": before["full_name"], "areaId": before["area_id"]},
                   after={"email": updated["email"], "fullName": updated["full_name"], "areaId": updated["area_id"]})
            return safe_user(updated)
    except UniqueViolation as error:
        raise Conflict("An account with that email already exists.") from error


def update_user_role(actor: dict, user_id: str, role: str) -> dict:
    role = role.upper()
    if role not in {"ADMIN", "DISPATCHER", "RESPONDER"}:
        raise DomainError("Unsupported role.")
    with connection() as conn, conn.transaction():
        before = _principal_row(conn, user_id)
        if not before:
            raise NotFound("User not found.")
        conn.execute("DELETE FROM user_roles WHERE user_id=%s", (user_id,))
        conn.execute("INSERT INTO user_roles(user_id,role_id) SELECT %s,id FROM roles WHERE name=%s", (user_id, role))
        conn.execute("UPDATE sessions SET revoked_at=now() WHERE user_id=%s AND revoked_at IS NULL", (user_id,))
        _audit(conn, actor["id"], "user.role_changed", "user", user_id,
               before={"roles": before["roles"]}, after={"role": role})
        return safe_user(_principal_row(conn, user_id))


def reset_user_password(actor: dict, user_id: str) -> dict:
    temporary = generate_temporary_password()
    with connection() as conn, conn.transaction():
        changed = conn.execute(
            """UPDATE users SET password_hash=%s,must_change_password=TRUE,updated_at=now()
               WHERE id=%s RETURNING id""", (hash_password(temporary), user_id)
        ).fetchone()
        if not changed:
            raise NotFound("User not found.")
        conn.execute("UPDATE sessions SET revoked_at=now() WHERE user_id=%s AND revoked_at IS NULL", (user_id,))
        _audit(conn, actor["id"], "user.password_reset", "user", user_id)
    return {"userId": user_id, "temporaryPassword": temporary, "mustChangePassword": True}


def list_roles() -> list[dict]:
    with connection() as conn:
        rows = conn.execute(
            """SELECT r.name,r.description,COALESCE(array_agg(p.code ORDER BY p.code)
               FILTER (WHERE p.code IS NOT NULL),'{}') permissions
               FROM roles r LEFT JOIN role_permissions rp ON rp.role_id=r.id
               LEFT JOIN permissions p ON p.id=rp.permission_id GROUP BY r.id ORDER BY r.name"""
        ).fetchall()
    return _serialize(rows)


def list_areas() -> list[dict]:
    with connection() as conn:
        return _serialize(conn.execute("SELECT * FROM areas ORDER BY name").fetchall())


def upsert_area(actor: dict, *, area_id: str | None, name: str, description: str | None) -> dict:
    with connection() as conn, conn.transaction():
        if area_id:
            row = conn.execute(
                "UPDATE areas SET name=%s,description=%s,updated_at=now() WHERE id=%s RETURNING *",
                (name.strip(), description, area_id),
            ).fetchone()
            action = "area.updated"
        else:
            row = conn.execute(
                "INSERT INTO areas(name,description) VALUES (%s,%s) RETURNING *",
                (name.strip(), description),
            ).fetchone()
            action = "area.created"
        if not row:
            raise NotFound("Area not found.")
        _audit(conn, actor["id"], action, "area", str(row["id"]), after=row)
    return _serialize(row)


def list_cameras() -> list[dict]:
    with connection() as conn:
        rows = conn.execute(
            """SELECT c.*,a.name area_name FROM cameras c LEFT JOIN areas a ON a.id=c.area_id
               ORDER BY c.created_at DESC"""
        ).fetchall()
    return public_camera_data(_serialize(rows))


def upsert_camera(actor: dict, data: dict, camera_id: str | None = None) -> dict:
    from backend.services.camera_sources import is_webcam_reference, resolve_source
    if is_webcam_reference(data.get("streamReference")):
        try:
            resolve_source(data["streamReference"])
        except ValueError as error:
            raise DomainError(str(error)) from error
    allowed_status = {"ONLINE", "OFFLINE", "DISABLED", "ERROR"}
    status = str(data.get("status") or "OFFLINE").upper()
    if status not in allowed_status:
        raise DomainError("Unsupported camera status.")
    with connection() as conn, conn.transaction():
        if camera_id:
            before = conn.execute("SELECT * FROM cameras WHERE id=%s FOR UPDATE", (camera_id,)).fetchone()
            if not before:
                raise NotFound("Camera not found.")
            row = conn.execute(
                """UPDATE cameras SET area_id=%s,name=%s,location=%s,stream_reference=%s,status=%s,
                   detection_enabled=%s,latitude=%s,longitude=%s,updated_at=now() WHERE id=%s RETURNING *""",
                (data.get("areaId"), data["name"], data.get("location"), data.get("streamReference", before["stream_reference"]),
                 status, bool(data.get("detectionEnabled", True)), data.get("latitude"),
                 data.get("longitude"), camera_id),
            ).fetchone()
            action = "camera.updated"
        else:
            before = None
            row = conn.execute(
                """INSERT INTO cameras(area_id,name,location,stream_reference,status,detection_enabled,latitude,longitude)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (data.get("areaId"), data["name"], data.get("location"), data.get("streamReference"),
                 status, bool(data.get("detectionEnabled", True)), data.get("latitude"), data.get("longitude")),
            ).fetchone()
            action = "camera.created"
        _audit(conn, actor["id"], action, "camera", str(row["id"]), before=before, after=row)
    clean = _serialize(row)
    clean.pop("stream_reference", None)
    clean["streamConfigured"] = bool(row.get("stream_reference"))
    return public_camera_data(clean)


def create_ai_incident(data: dict) -> dict:
    detector_event_id = str(data.get("detectorEventId") or "").strip()
    if not detector_event_id:
        raise DomainError("detectorEventId is required for PostgreSQL incident identity.")
    detection_mode = data.get("detectionMode") or "temporal_collision"
    if detection_mode not in {"temporal_collision", "aftermath_review"}:
        raise DomainError("Unsupported detection mode.")
    with connection() as conn, conn.transaction():
        camera_key = str(data.get("cameraKey") or "")
        # Serialize competing observations of one camera; the unique event key
        # also protects replay and concurrent processing across workers.
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (camera_key or detector_event_id,))
        existing = conn.execute(
            "SELECT id FROM incidents WHERE detector_event_id=%s", (detector_event_id,)
        ).fetchone()
        if existing:
            return {"incidentId": str(existing["id"]), "incidentCreated": False, "duplicateEvent": True}
        if camera_key:
            pending = conn.execute(
                """SELECT i.id FROM incidents i JOIN review_cases rc ON rc.incident_id=i.id
                   WHERE i.evidence_summary->>'cameraKey'=%s
                     AND rc.status IN ('PENDING_REVIEW','UNDER_REVIEW') LIMIT 1""", (camera_key,),
            ).fetchone()
            if pending:
                return {"incidentId": str(pending["id"]), "incidentCreated": False, "duplicateEvent": True}
        camera_id = data.get("postgresCameraId")
        if not camera_id and data.get("cameraId"):
            camera = conn.execute("SELECT id FROM cameras WHERE legacy_id=%s OR id::text=%s",
                                  (data["cameraId"], data["cameraId"])).fetchone()
            camera_id = camera["id"] if camera else None
        evidence = {**(data.get("evidenceSummary") or {}), "cameraKey": camera_key}
        incident = conn.execute(
            """INSERT INTO incidents
               (legacy_case_id,detector_event_id,camera_id,detection_mode,ai_score,evidence_summary,
                media,location,latitude,longitude,detected_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (detector_event_id) DO NOTHING RETURNING id,created_at""",
            (data.get("caseId"), detector_event_id, camera_id, detection_mode,
             float(data.get("crashScore") or data.get("confidence") or 0),
             _json(evidence), _json(data.get("media") or {}),
             data.get("location"), data.get("latitude"), data.get("longitude"), data["detectedAt"]),
        ).fetchone()
        if not incident:
            existing = conn.execute("SELECT id FROM incidents WHERE detector_event_id=%s", (detector_event_id,)).fetchone()
            return {"incidentId": str(existing["id"]), "incidentCreated": False, "duplicateEvent": True}
        incident_id = str(incident["id"])
        review = conn.execute(
            "INSERT INTO review_cases(incident_id) VALUES (%s) RETURNING id", (incident_id,)
        ).fetchone()
        alert = conn.execute(
            "INSERT INTO alerts(incident_id,type) VALUES (%s,'NEW_CRASH_REVIEW') RETURNING id", (incident_id,)
        ).fetchone()
        notification_rows = conn.execute(
            """INSERT INTO notifications(user_id,incident_id,type,title,message)
               SELECT ur.user_id,%s,'NEW_CRASH_REVIEW','New crash review',%s
               FROM user_roles ur JOIN roles r ON r.id=ur.role_id
               JOIN users u ON u.id=ur.user_id
               WHERE r.name='DISPATCHER' AND u.status='ACTIVE' RETURNING id""",
            (incident_id, f"Incident {incident_id} requires dispatcher review."),
        ).fetchall()
        _timeline(conn, incident_id, "AI_INCIDENT_CREATED", None,
                  {"detectionMode": detection_mode, "score": data.get("crashScore")})
        _timeline(conn, incident_id, "REVIEW_CASE_CREATED", None, {"reviewCaseId": str(review["id"])})
        _audit(conn, None, "incident.ai_created", "incident", incident_id,
               after={"detectorEventId": detector_event_id, "detectionMode": detection_mode})
    return {
        "incidentId": incident_id,
        "reviewCaseId": str(review["id"]),
        "alertId": str(alert["id"]),
        "incidentCreated": True,
        "duplicateEvent": False,
        "createdAt": incident["created_at"].isoformat(),
        "notificationCount": len(notification_rows),
    }


def find_pending_detection(camera_key: str) -> dict | None:
    with connection() as conn:
        return conn.execute(
            """SELECT i.*,rc.status review_status FROM incidents i
               JOIN review_cases rc ON rc.incident_id=i.id
               WHERE i.evidence_summary->>'cameraKey'=%s
                 AND rc.status IN ('PENDING_REVIEW','UNDER_REVIEW')
               ORDER BY i.detected_at DESC LIMIT 1""", (camera_key,),
        ).fetchone()


INCIDENT_SELECT = """
SELECT i.*,rc.id review_case_id,rc.status review_status,rc.reviewed_by,
       rc.review_started_at,rc.reviewed_at,rc.false_alarm_reason,rc.dispatcher_notes,
       a.id assignment_id,a.responder_id,a.status assignment_status,a.assigned_at,
       a.accepted_at,a.en_route_at,a.arrived_at,a.responding_at,a.resolved_at,
       u.full_name responder_name
FROM incidents i JOIN review_cases rc ON rc.incident_id=i.id
LEFT JOIN assignments a ON a.incident_id=i.id AND a.status IN ('ASSIGNED','ACCEPTED','EN_ROUTE','ARRIVED','RESPONDING','RESOLVED')
LEFT JOIN users u ON u.id=a.responder_id
"""


def list_incidents(actor: dict, *, review_status: str | None = None) -> list[dict]:
    params: list[Any] = []
    where = ["TRUE"]
    if review_status:
        where.append("rc.status=%s")
        params.append(review_status.upper())
    if "RESPONDER" in actor["roles"]:
        where.append("a.responder_id=%s")
        params.append(actor["id"])
    sql = INCIDENT_SELECT + " WHERE " + " AND ".join(where) + " ORDER BY i.detected_at DESC"
    with connection() as conn:
        return _serialize(conn.execute(sql, params).fetchall())


def get_incident(actor: dict, incident_id: str) -> dict:
    where = "i.id=%s"
    params: list[Any] = [incident_id]
    if "RESPONDER" in actor["roles"]:
        where += " AND a.responder_id=%s"
        params.append(actor["id"])
    with connection() as conn:
        row = conn.execute(INCIDENT_SELECT + " WHERE " + where, params).fetchone()
        if not row:
            raise NotFound("Incident not found or outside your assignment scope.")
        timeline = conn.execute(
            """SELECT t.*,u.full_name actor_name FROM incident_timeline t
               LEFT JOIN users u ON u.id=t.actor_user_id WHERE incident_id=%s ORDER BY created_at""",
            (incident_id,),
        ).fetchall()
    result = _serialize(row)
    result["timeline"] = _serialize(timeline)
    return result


def claim_review(actor: dict, incident_id: str, *, minutes: int = 15) -> dict:
    with connection() as conn, conn.transaction():
        row = conn.execute(
            """UPDATE review_cases SET status='UNDER_REVIEW',reviewed_by=%s,review_started_at=now(),
               claim_expires_at=now()+(%s || ' minutes')::interval,updated_at=now()
               WHERE incident_id=%s AND (
                 status='PENDING_REVIEW' OR
                 (status='UNDER_REVIEW' AND (reviewed_by=%s OR claim_expires_at<now()))
               ) RETURNING *""",
            (actor["id"], minutes, incident_id, actor["id"]),
        ).fetchone()
        if not row:
            current = conn.execute("SELECT status,reviewed_by FROM review_cases WHERE incident_id=%s", (incident_id,)).fetchone()
            if not current:
                raise NotFound("Review case not found.")
            raise Conflict("Review case is already claimed or completed.")
        _timeline(conn, incident_id, "REVIEW_STARTED", actor["id"])
        _audit(conn, actor["id"], "incident.review_claimed", "incident", incident_id)
    return _serialize(row)


def complete_review(actor: dict, incident_id: str, *, decision: str, priority: str | None,
                    incident_type: str | None, notes: str | None,
                    false_alarm_reason: str | None) -> dict:
    decision = decision.upper()
    if decision not in {"CONFIRMED", "FALSE_ALARM"}:
        raise DomainError("Decision must be CONFIRMED or FALSE_ALARM.")
    if decision == "FALSE_ALARM" and not (false_alarm_reason or "").strip():
        raise DomainError("False alarm reason is required.")
    if decision == "CONFIRMED":
        if priority not in {"CRITICAL", "HIGH", "MEDIUM", "LOW"} or not incident_type:
            raise DomainError("Priority and incident type are required to confirm a crash.")
    with connection() as conn, conn.transaction():
        review = conn.execute(
            "SELECT * FROM review_cases WHERE incident_id=%s FOR UPDATE", (incident_id,)
        ).fetchone()
        if not review:
            raise NotFound("Review case not found.")
        if review["status"] != "UNDER_REVIEW" or str(review["reviewed_by"]) != actor["id"]:
            raise Conflict("You must hold the active review claim to complete this review.")
        conn.execute(
            """UPDATE review_cases SET status=%s,reviewed_at=now(),false_alarm_reason=%s,
               dispatcher_notes=%s,claim_expires_at=NULL,updated_at=now() WHERE incident_id=%s""",
            (decision, false_alarm_reason, notes, incident_id),
        )
        state = "CONFIRMED" if decision == "CONFIRMED" else "FALSE_ALARM"
        conn.execute(
            """UPDATE incidents SET state=%s,priority=%s,incident_type=%s,
               confirmed_at=CASE WHEN %s='CONFIRMED' THEN now() ELSE confirmed_at END,
               updated_at=now() WHERE id=%s""",
            (state, priority, incident_type, decision, incident_id),
        )
        event = "CRASH_CONFIRMED" if decision == "CONFIRMED" else "FALSE_ALARM"
        _timeline(conn, incident_id, event, actor["id"],
                  {"priority": priority, "incidentType": incident_type, "reason": false_alarm_reason, "notes": notes})
        _audit(conn, actor["id"], f"incident.{decision.lower()}", "incident", incident_id,
               after={"priority": priority, "incidentType": incident_type, "reason": false_alarm_reason})
    return get_incident(actor, incident_id)


def responder_heartbeat(actor: dict) -> dict:
    if "RESPONDER" not in set(actor.get("roles") or []):
        raise Forbidden("Responder presence is available only to responder accounts.")
    with connection() as conn, conn.transaction():
        row = conn.execute(
            """UPDATE users u
               SET availability_status=CASE
                     WHEN u.availability_status='OFFLINE' AND NOT EXISTS (
                       SELECT 1 FROM assignments a
                       WHERE a.responder_id=u.id
                         AND a.status IN ('ASSIGNED','ACCEPTED','EN_ROUTE','ARRIVED','RESPONDING')
                     ) THEN 'AVAILABLE'
                     ELSE u.availability_status
                   END,
                   updated_at=now()
               WHERE u.id=%s
               RETURNING availability_status""",
            (actor["id"],),
        ).fetchone()
    return {
        "presenceStatus": "ONLINE",
        "lastSeenAt": utcnow().isoformat(),
        "availabilityStatus": row["availability_status"],
        "onlineTimeoutSeconds": RESPONDER_ONLINE_TIMEOUT_SECONDS,
    }


def list_responders() -> list[dict]:
    with connection() as conn:
        rows = conn.execute(
            """SELECT u.id AS uid,u.id,u.email,u.full_name AS "displayName",
                      u.availability_status AS "availabilityStatus",u.area_id AS "areaId",
                      u.last_login_at AS "lastLoginAt",activity.last_seen_at AS "lastSeenAt",
                      CASE
                        WHEN activity.active_last_seen_at >= now() - make_interval(secs => %s)
                          THEN 'ONLINE'
                        ELSE 'OFFLINE'
                      END AS "presenceStatus",
                      active_assignment.id AS "activeAssignmentId",
                      active_assignment.status AS "activeAssignmentStatus",
                      active_assignment.incident_id AS "activeIncidentId"
               FROM users u JOIN user_roles ur ON ur.user_id=u.id JOIN roles r ON r.id=ur.role_id
               LEFT JOIN LATERAL (
                 SELECT max(s.last_used_at) AS last_seen_at,
                        max(s.last_used_at) FILTER (
                          WHERE s.revoked_at IS NULL AND s.expires_at>now()
                        ) AS active_last_seen_at
                 FROM sessions s WHERE s.user_id=u.id
               ) activity ON TRUE
               LEFT JOIN LATERAL (
                 SELECT a.id,a.status,a.incident_id
                 FROM assignments a
                 WHERE a.responder_id=u.id
                   AND a.status IN ('ASSIGNED','ACCEPTED','EN_ROUTE','ARRIVED','RESPONDING')
                 ORDER BY a.assigned_at DESC LIMIT 1
               ) active_assignment ON TRUE
               WHERE r.name='RESPONDER' AND u.status='ACTIVE'
               ORDER BY
                 CASE
                   WHEN activity.active_last_seen_at >= now() - make_interval(secs => %s)
                        AND active_assignment.id IS NULL AND u.availability_status='AVAILABLE' THEN 1
                   WHEN activity.active_last_seen_at >= now() - make_interval(secs => %s) THEN 2
                   ELSE 4
                 END,
                 u.full_name""",
            (
                RESPONDER_ONLINE_TIMEOUT_SECONDS,
                RESPONDER_ONLINE_TIMEOUT_SECONDS,
                RESPONDER_ONLINE_TIMEOUT_SECONDS,
            ),
        ).fetchall()
    return _serialize(rows)


def assign_responder(actor: dict, incident_id: str, responder_id: str, *, reassign: bool = False) -> dict:
    with connection() as conn, conn.transaction():
        incident = conn.execute("SELECT state FROM incidents WHERE id=%s FOR UPDATE", (incident_id,)).fetchone()
        if not incident:
            raise NotFound("Incident not found.")
        if incident["state"] not in {"CONFIRMED", "ACTIVE_RESPONSE"}:
            raise Conflict("Only a confirmed unresolved incident can be assigned.")
        responder = conn.execute(
            """SELECT u.id FROM users u JOIN user_roles ur ON ur.user_id=u.id JOIN roles r ON r.id=ur.role_id
               WHERE u.id=%s AND u.status='ACTIVE' AND r.name='RESPONDER' FOR UPDATE""",
            (responder_id,),
        ).fetchone()
        if not responder:
            raise NotFound("Active responder not found.")
        active = conn.execute(
            """SELECT * FROM assignments WHERE incident_id=%s
               AND status IN ('ASSIGNED','ACCEPTED','EN_ROUTE','ARRIVED','RESPONDING') FOR UPDATE""",
            (incident_id,),
        ).fetchone()
        previous_id = None
        if active:
            if not reassign:
                raise Conflict("Incident already has an active assignment.")
            previous_id = active["id"]
            conn.execute("UPDATE assignments SET status='REASSIGNED',cancelled_at=now(),updated_at=now() WHERE id=%s", (previous_id,))
        assignment = conn.execute(
            """INSERT INTO assignments(incident_id,responder_id,assigned_by,previous_assignment_id)
               VALUES (%s,%s,%s,%s) RETURNING *""",
            (incident_id, responder_id, actor["id"], previous_id),
        ).fetchone()
        conn.execute("UPDATE users SET availability_status='ASSIGNED',updated_at=now() WHERE id=%s", (responder_id,))
        conn.execute("UPDATE incidents SET state='ACTIVE_RESPONSE',updated_at=now() WHERE id=%s", (incident_id,))
        conn.execute(
            """INSERT INTO notifications(user_id,incident_id,type,title,message)
               VALUES (%s,%s,'NEW_ASSIGNMENT','New incident assignment',%s)""",
            (responder_id, incident_id, f"Incident {incident_id} was assigned to you."),
        )
        _timeline(conn, incident_id, "RESPONDER_ASSIGNED", actor["id"],
                  {"assignmentId": str(assignment["id"]), "responderId": responder_id, "reassigned": reassign})
        _audit(conn, actor["id"], "assignment.reassigned" if reassign else "assignment.created",
               "assignment", str(assignment["id"]), after={"incidentId": incident_id, "responderId": responder_id})
    return _serialize(assignment)


def cancel_assignment(actor: dict, assignment_id: str) -> dict:
    with connection() as conn, conn.transaction():
        row = conn.execute("SELECT * FROM assignments WHERE id=%s FOR UPDATE", (assignment_id,)).fetchone()
        if not row:
            raise NotFound("Assignment not found.")
        if row["status"] not in ACTIVE_ASSIGNMENT_STATES:
            raise Conflict("Assignment is not active.")
        updated = conn.execute(
            "UPDATE assignments SET status='CANCELLED',cancelled_at=now(),updated_at=now() WHERE id=%s RETURNING *",
            (assignment_id,),
        ).fetchone()
        conn.execute("UPDATE users SET availability_status='AVAILABLE',updated_at=now() WHERE id=%s", (row["responder_id"],))
        conn.execute("UPDATE incidents SET state='CONFIRMED',updated_at=now() WHERE id=%s", (row["incident_id"],))
        _timeline(conn, str(row["incident_id"]), "ASSIGNMENT_CANCELLED", actor["id"], {"assignmentId": assignment_id})
        _audit(conn, actor["id"], "assignment.cancelled", "assignment", assignment_id)
    return _serialize(updated)


def list_assignments(actor: dict, *, history: bool = False) -> list[dict]:
    where = ["a.responder_id=%s"]
    params: list[Any] = [actor["id"]]
    if not history:
        where.append("a.status IN ('ASSIGNED','ACCEPTED','EN_ROUTE','ARRIVED','RESPONDING')")
    with connection() as conn:
        rows = conn.execute(
            """SELECT a.*,i.priority,i.incident_type,i.location,i.latitude,i.longitude,i.detected_at,
                      d.full_name dispatcher_name
               FROM assignments a JOIN incidents i ON i.id=a.incident_id
               JOIN users d ON d.id=a.assigned_by WHERE """ + " AND ".join(where) +
            " ORDER BY a.assigned_at DESC", params,
        ).fetchall()
    return _serialize(rows)


def transition_assignment(actor: dict, assignment_id: str, target_status: str, *,
                          notes: str | None = None, outcome: str | None = None,
                          decline_reason: str | None = None) -> dict:
    target = target_status.upper()
    required_permission = TRANSITION_PERMISSION.get(target)
    if not required_permission or required_permission not in actor["permissions"]:
        raise Forbidden("You do not have permission for this response transition.")
    with connection() as conn, conn.transaction():
        current = conn.execute("SELECT * FROM assignments WHERE id=%s FOR UPDATE", (assignment_id,)).fetchone()
        if not current:
            raise NotFound("Assignment not found.")
        if str(current["responder_id"]) != actor["id"]:
            raise Forbidden("Responders may update only their own assignment.")
        if target not in ASSIGNMENT_TRANSITIONS.get(current["status"], set()):
            raise Conflict(f"Invalid assignment transition: {current['status']} -> {target}.")
        if target == "DECLINED" and not (decline_reason or "").strip():
            raise DomainError("Decline reason is required.")
        if target == "RESOLVED" and (not (notes or "").strip() or not (outcome or "").strip()):
            raise DomainError("Response notes and outcome are required to resolve an incident.")
        timestamp_column = TRANSITION_TIMESTAMP[target]
        updated = conn.execute(
            f"""UPDATE assignments SET status=%s,{timestamp_column}=now(),response_notes=COALESCE(%s,response_notes),
                outcome=COALESCE(%s,outcome),decline_reason=COALESCE(%s,decline_reason),updated_at=now()
                WHERE id=%s RETURNING *""",
            (target, notes, outcome, decline_reason, assignment_id),
        ).fetchone()
        availability = {
            "ACCEPTED": "ASSIGNED", "EN_ROUTE": "EN_ROUTE", "ARRIVED": "ARRIVED",
            "RESPONDING": "RESPONDING", "RESOLVED": "AVAILABLE", "DECLINED": "AVAILABLE",
        }[target]
        conn.execute("UPDATE users SET availability_status=%s,updated_at=now() WHERE id=%s", (availability, actor["id"]))
        if target == "RESOLVED":
            conn.execute("UPDATE incidents SET state='RESOLVED',resolved_at=now(),updated_at=now() WHERE id=%s", (current["incident_id"],))
        elif target == "DECLINED":
            conn.execute("UPDATE incidents SET state='CONFIRMED',updated_at=now() WHERE id=%s", (current["incident_id"],))
        _timeline(conn, str(current["incident_id"]), f"ASSIGNMENT_{target}", actor["id"],
                  {"assignmentId": assignment_id, "notes": notes, "outcome": outcome, "declineReason": decline_reason})
        _audit(conn, actor["id"], f"assignment.{target.lower()}", "assignment", assignment_id,
               before={"status": current["status"]}, after={"status": target})
        if target == "DECLINED":
            conn.execute(
                """INSERT INTO notifications(user_id,incident_id,type,title,message)
                   SELECT ur.user_id,%s,'ASSIGNMENT_DECLINED','Responder declined assignment',%s
                   FROM user_roles ur JOIN roles r ON r.id=ur.role_id JOIN users u ON u.id=ur.user_id
                   WHERE r.name='DISPATCHER' AND u.status='ACTIVE'""",
                (current["incident_id"], f"Assignment {assignment_id} was declined."),
            )
    return _serialize(updated)


def set_availability(actor: dict, status: str) -> dict:
    status = status.upper()
    if status not in {"AVAILABLE", "OFFLINE"}:
        raise DomainError("Availability may only be AVAILABLE or OFFLINE.")
    with connection() as conn, conn.transaction():
        active = conn.execute(
            "SELECT id FROM assignments WHERE responder_id=%s AND status IN ('ASSIGNED','ACCEPTED','EN_ROUTE','ARRIVED','RESPONDING')",
            (actor["id"],),
        ).fetchone()
        if active and status == "OFFLINE":
            raise Conflict("Cannot go offline while an assignment is active.")
        row = conn.execute(
            "UPDATE users SET availability_status=%s,updated_at=now() WHERE id=%s RETURNING availability_status",
            (status, actor["id"]),
        ).fetchone()
    return {"availabilityStatus": row["availability_status"]}


def list_notifications(actor: dict, *, unread_only: bool = False) -> list[dict]:
    where = "user_id=%s" + (" AND read_at IS NULL" if unread_only else "")
    with connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM notifications WHERE {where} ORDER BY created_at DESC LIMIT 200",
            (actor["id"],),
        ).fetchall()
    return _serialize(rows)


def mark_notification_read(actor: dict, notification_id: str) -> dict:
    with connection() as conn, conn.transaction():
        row = conn.execute(
            "UPDATE notifications SET read_at=COALESCE(read_at,now()) WHERE id=%s AND user_id=%s RETURNING *",
            (notification_id, actor["id"]),
        ).fetchone()
        if not row:
            raise NotFound("Notification not found.")
    return _serialize(row)


def list_audit_logs(limit: int = 200) -> list[dict]:
    with connection() as conn:
        rows = conn.execute(
            """SELECT a.*,u.full_name actor_name,u.email actor_email FROM audit_logs a
               LEFT JOIN users u ON u.id=a.actor_user_id ORDER BY a.created_at DESC LIMIT %s""",
            (max(1, min(limit, 500)),),
        ).fetchall()
    return public_camera_data(_serialize(rows))


def analytics_summary() -> dict:
    with connection() as conn:
        row = conn.execute(
            """SELECT
              (SELECT count(*) FROM cameras WHERE status='ONLINE') active_cameras,
              (SELECT count(*) FROM users WHERE status='ACTIVE') active_users,
              (SELECT count(*) FROM incidents WHERE detected_at::date=current_date) incidents_today,
              (SELECT count(*) FROM incidents WHERE detected_at>=date_trunc('week',now())) incidents_week,
              (SELECT count(*) FROM incidents WHERE detected_at>=date_trunc('month',now())) incidents_month,
              (SELECT count(*) FROM review_cases WHERE status='CONFIRMED') confirmed_incidents,
              (SELECT count(*) FROM review_cases WHERE status='FALSE_ALARM') false_alarms,
              (SELECT round(extract(epoch from avg(reviewed_at-review_started_at)))
                 FROM review_cases WHERE reviewed_at IS NOT NULL AND review_started_at IS NOT NULL) average_review_seconds,
              (SELECT round(extract(epoch from avg(accepted_at-assigned_at)))
                 FROM assignments WHERE accepted_at IS NOT NULL) average_acceptance_seconds,
              (SELECT round(extract(epoch from avg(resolved_at-assigned_at)))
                 FROM assignments WHERE resolved_at IS NOT NULL) average_response_seconds,
              (SELECT count(*) FROM assignments WHERE status IN ('ASSIGNED','ACCEPTED','EN_ROUTE','ARRIVED','RESPONDING')) active_responses,
              (SELECT count(*) FROM review_cases WHERE status='PENDING_REVIEW') pending_reviews,
              (SELECT count(*) FROM users u JOIN user_roles ur ON ur.user_id=u.id JOIN roles r ON r.id=ur.role_id
                 WHERE r.name='RESPONDER' AND u.availability_status='AVAILABLE' AND u.status='ACTIVE') available_responders"""
        ).fetchone()
        by_camera = conn.execute(
            """SELECT COALESCE(c.name,'Unknown camera') name,count(*) incidents,
                      count(*) FILTER (WHERE rc.status='FALSE_ALARM') false_alarms
               FROM incidents i LEFT JOIN cameras c ON c.id=i.camera_id
               JOIN review_cases rc ON rc.incident_id=i.id GROUP BY c.name ORDER BY incidents DESC"""
        ).fetchall()
        by_area = conn.execute(
            """SELECT COALESCE(a.name,'Unassigned') name,count(*) incidents
               FROM incidents i LEFT JOIN cameras c ON c.id=i.camera_id LEFT JOIN areas a ON a.id=c.area_id
               GROUP BY a.name ORDER BY incidents DESC"""
        ).fetchall()
    result = _serialize(row)
    result["by_camera"] = _serialize(by_camera)
    result["by_area"] = _serialize(by_area)
    return result


def get_settings() -> list[dict]:
    with connection() as conn:
        return _serialize(conn.execute("SELECT * FROM system_settings ORDER BY key").fetchall())


def set_setting(actor: dict, key: str, value: Any) -> dict:
    allowed = {"crash_detection_enabled", "temporal_threshold", "minimum_track_history", "post_contact_verification"}
    if key not in allowed:
        raise DomainError("Unsupported AI setting.")
    with connection() as conn, conn.transaction():
        before = conn.execute("SELECT value FROM system_settings WHERE key=%s", (key,)).fetchone()
        row = conn.execute(
            """INSERT INTO system_settings(key,value,updated_by) VALUES (%s,%s,%s)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_by=excluded.updated_by,updated_at=now()
               RETURNING *""", (key, _json(value), actor["id"])
        ).fetchone()
        _audit(conn, actor["id"], "ai_setting.changed", "system_setting", key,
               before=before["value"] if before else None, after=value)
    return _serialize(row)
