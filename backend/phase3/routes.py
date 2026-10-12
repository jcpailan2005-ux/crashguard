from __future__ import annotations

import os
import ipaddress
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from backend.phase3.database import DatabaseUnavailable, check_database
from backend.phase3 import service
from backend.phase3.database import connection
import json


router = APIRouter(prefix="/api/v3", tags=["Phase 3 Operations"])
SESSION_COOKIE = "crashguard_session"


class LiveCameraSessionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    active: bool | None = None
    latestDetection: dict[str, Any] | None = None
    livePreviewDataUrl: str | None = Field(default=None, max_length=400000)


class LoginIn(BaseModel):
    email: str
    password: str


class ChangePasswordIn(BaseModel):
    currentPassword: str
    newPassword: str


class OwnProfileUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fullName: str = Field(min_length=2, max_length=160)


class NotificationPreferencesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    alertNotifications: bool | None = None
    browserNotifications: bool | None = None
    emailNotifications: bool | None = None
    alarmAudio: bool | None = None


class OwnPreferencesUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    theme: str | None = None
    notificationPreferences: NotificationPreferencesIn | None = None


class UserCreateIn(BaseModel):
    email: str
    fullName: str = Field(min_length=2, max_length=160)
    role: str
    areaId: str | None = None
    status: str = "ACTIVE"


class UserStatusIn(BaseModel):
    status: str


class UserUpdateIn(BaseModel):
    email: str | None = None
    fullName: str | None = Field(default=None, min_length=2, max_length=160)
    areaId: str | None = None


class UserRoleIn(BaseModel):
    role: str


class AreaIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = None


class CameraIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    areaId: str | None = None
    location: str | None = None
    streamReference: str | None = None
    status: str = "OFFLINE"
    detectionEnabled: bool = True
    latitude: float | None = None
    longitude: float | None = None


class ReviewDecisionIn(BaseModel):
    decision: str
    priority: str | None = None
    incidentType: str | None = None
    notes: str | None = None
    falseAlarmReason: str | None = None
    actorId: str | None = None
    role: str | None = None


class AssignmentIn(BaseModel):
    responderId: str
    actorId: str | None = None
    role: str | None = None


class AssignmentTransitionIn(BaseModel):
    status: str
    notes: str | None = None
    outcome: str | None = None
    declineReason: str | None = None
    actorId: str | None = None
    role: str | None = None


class AvailabilityIn(BaseModel):
    status: str


class SettingIn(BaseModel):
    value: Any


def _call(fn: Callable, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except service.DomainError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    except DatabaseUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


def _token_from_request(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header.split(" ", 1)[1].strip()
    return request.cookies.get(SESSION_COOKIE, "").strip()


def current_user(request: Request) -> dict:
    token = _token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        principal = service.authenticate_session(token)
    except DatabaseUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    if not principal:
        raise HTTPException(status_code=401, detail="Session is invalid, expired, or revoked.")
    return principal


def require_permission(code: str, *, allow_password_change_required: bool = False):
    def dependency(user: dict = Depends(current_user)) -> dict:
        if user.get("mustChangePassword") and not allow_password_change_required:
            raise HTTPException(status_code=403, detail="PASSWORD_CHANGE_REQUIRED")
        if code not in set(user.get("permissions") or []):
            raise HTTPException(status_code=403, detail=f"Permission required: {code}")
        return user
    return dependency


def require_any_permission(*codes: str):
    def dependency(user: dict = Depends(current_user)) -> dict:
        if user.get("mustChangePassword"):
            raise HTTPException(status_code=403, detail="PASSWORD_CHANGE_REQUIRED")
        permissions = set(user.get("permissions") or [])
        if not permissions.intersection(codes):
            raise HTTPException(status_code=403, detail="Permission denied.")
        return user
    return dependency


@router.post("/auth/login")
def login(body: LoginIn, request: Request, response: Response):
    remote_host = request.client.host if request.client else None
    try:
        ip_address = str(ipaddress.ip_address(remote_host)) if remote_host else None
    except ValueError:
        ip_address = None
    try:
        result = service.login(
            body.email,
            body.password,
            user_agent=request.headers.get("user-agent"),
            ip_address=ip_address,
        )
    except service.Forbidden as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    except DatabaseUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    session_token = result["token"]
    response.set_cookie(
        SESSION_COOKIE,
        session_token,
        httponly=True,
        secure=os.getenv("CRASHGUARD_SECURE_COOKIES", "false").lower() == "true",
        samesite="lax",
        max_age=int(os.getenv("CRASHGUARD_SESSION_TTL_SECONDS", str(7 * 24 * 60 * 60))),
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    # The browser authenticates with the HttpOnly cookie. Never expose the raw
    # session secret to frontend JavaScript or localStorage.
    return {"user": result["user"]}


@router.post("/auth/logout")
def logout(response: Response, user: dict = Depends(current_user)):
    _call(service.logout, user["sessionId"], user["id"])
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.headers["Cache-Control"] = "no-store"
    return {"success": True}


@router.get("/auth/me")
def me(response: Response, user: dict = Depends(current_user)):
    response.headers["Cache-Control"] = "no-store"
    return {"user": user}


@router.post("/auth/change-password")
def change_password(
    body: ChangePasswordIn,
    user: dict = Depends(
        require_permission("password.change_own", allow_password_change_required=True)
    ),
):
    return {"user": _call(service.change_password, user, body.currentPassword, body.newPassword)}


@router.get("/me/profile")
def own_profile(user: dict = Depends(require_permission("profile.view_own"))):
    return {"user": user}


@router.patch("/me/profile")
def update_own_profile(
    body: OwnProfileUpdateIn,
    user: dict = Depends(require_permission("profile.update_own")),
):
    return {"user": _call(service.update_own_profile, user, full_name=body.fullName)}


@router.get("/me/preferences")
def own_preferences(user: dict = Depends(require_permission("preferences.view_own"))):
    return {"preferences": _call(service.get_own_preferences, user)}


@router.patch("/me/preferences")
def update_own_preferences(
    body: OwnPreferencesUpdateIn,
    user: dict = Depends(require_permission("preferences.update_own")),
):
    if (
        body.notificationPreferences is not None
        and "notifications.preferences_own" not in set(user.get("permissions") or [])
    ):
        raise HTTPException(
            status_code=403,
            detail="Permission required: notifications.preferences_own",
        )
    return {
        "preferences": _call(
            service.update_own_preferences,
            user,
            theme=body.theme,
            notification_preferences=(
                body.notificationPreferences.model_dump(exclude_none=True)
                if body.notificationPreferences is not None
                else None
            ),
        )
    }


@router.get("/system/health")
def system_health(user: dict = Depends(require_permission("system_settings.view"))):
    database = _call(check_database)
    return {"backend": "ok", "database": database, "authenticatedAs": user["id"]}


@router.get("/roles")
def roles(user: dict = Depends(require_permission("roles.view"))):
    return {"roles": _call(service.list_roles)}


@router.get("/admin/users")
def users(search: str | None = None, role: str | None = None, status: str | None = None,
          user: dict = Depends(require_permission("users.view"))):
    return {"users": _call(service.list_users, search=search, role=role, status=status)}


@router.post("/admin/users")
def create_user(body: UserCreateIn, user: dict = Depends(require_permission("users.create"))):
    return {"user": _call(service.create_user, user, email=body.email, full_name=body.fullName,
                           role=body.role, area_id=body.areaId, status=body.status)}


@router.patch("/admin/users/{user_id}/status")
def user_status(user_id: str, body: UserStatusIn,
                user: dict = Depends(require_permission("users.disable"))):
    return {"user": _call(service.update_user_status, user, user_id, body.status)}


@router.patch("/admin/users/{user_id}")
def user_update(user_id: str, body: UserUpdateIn,
                user: dict = Depends(require_permission("users.update"))):
    return {"user": _call(service.update_user, user, user_id, email=body.email,
                           full_name=body.fullName, area_id=body.areaId)}


@router.patch("/admin/users/{user_id}/role")
def user_role(user_id: str, body: UserRoleIn,
              user: dict = Depends(require_permission("users.assign_role"))):
    return {"user": _call(service.update_user_role, user, user_id, body.role)}


@router.post("/admin/users/{user_id}/reset-password")
def reset_password(user_id: str, user: dict = Depends(require_permission("users.update"))):
    return _call(service.reset_user_password, user, user_id)


@router.get("/areas")
def areas(user: dict = Depends(require_any_permission("areas.view", "cameras.view"))):
    return {"areas": _call(service.list_areas)}


@router.post("/areas")
def create_area(body: AreaIn, user: dict = Depends(require_permission("areas.manage"))):
    return {"area": _call(service.upsert_area, user, area_id=None, name=body.name, description=body.description)}


@router.put("/areas/{area_id}")
def update_area(area_id: str, body: AreaIn, user: dict = Depends(require_permission("areas.manage"))):
    return {"area": _call(service.upsert_area, user, area_id=area_id, name=body.name, description=body.description)}


@router.get("/cameras")
def cameras(user: dict = Depends(require_permission("cameras.view"))):
    return {"cameras": _call(service.list_cameras)}


@router.post("/cameras")
def create_camera(body: CameraIn, user: dict = Depends(require_permission("cameras.create"))):
    return {"camera": _call(service.upsert_camera, user, body.model_dump(), None)}


@router.put("/cameras/{camera_id}")
def update_camera(camera_id: str, body: CameraIn,
                  user: dict = Depends(require_permission("cameras.update"))):
    data = body.model_dump()
    if "streamReference" not in body.model_fields_set:
        data.pop("streamReference", None)
    return {"camera": _call(service.upsert_camera, user, data, camera_id)}


@router.get("/incidents")
def incidents(reviewStatus: str | None = None,
              user: dict = Depends(require_any_permission("incidents.view_all", "incidents.view", "incidents.view_assigned"))):
    return {"incidents": _call(service.list_incidents, user, review_status=reviewStatus)}


@router.get("/incidents/{incident_id}")
def incident(incident_id: str,
             user: dict = Depends(require_any_permission("incidents.view_all", "incidents.view", "incidents.view_assigned"))):
    return {"incident": _call(service.get_incident, user, incident_id)}


@router.post("/dispatcher/incidents/{incident_id}/claim")
def claim(incident_id: str, user: dict = Depends(require_permission("incidents.review"))):
    return {"reviewCase": _call(service.claim_review, user, incident_id)}


@router.post("/dispatcher/incidents/{incident_id}/review")
def review(incident_id: str, body: ReviewDecisionIn,
           user: dict = Depends(require_any_permission("incidents.confirm", "incidents.false_alarm"))):
    required = "incidents.confirm" if body.decision.upper() == "CONFIRMED" else "incidents.false_alarm"
    if required not in user["permissions"]:
        raise HTTPException(status_code=403, detail=f"Permission required: {required}")
    return {"incident": _call(service.complete_review, user, incident_id, decision=body.decision,
                               priority=body.priority, incident_type=body.incidentType, notes=body.notes,
                               false_alarm_reason=body.falseAlarmReason)}


@router.get("/dispatcher/responders")
def responders(user: dict = Depends(require_permission("responders.view"))):
    return {"responders": _call(service.list_responders)}


@router.get("/responders/presence")
def responder_presence(user: dict = Depends(require_permission("responders.view"))):
    return {"responders": _call(service.list_responders)}


@router.post("/responder/presence/heartbeat")
def responder_presence_heartbeat(
    user: dict = Depends(require_permission("assignments.view_own")),
):
    return _call(service.responder_heartbeat, user)


@router.post("/dispatcher/incidents/{incident_id}/assign")
def assign(incident_id: str, body: AssignmentIn,
           user: dict = Depends(require_permission("dispatch.assign"))):
    return {"assignment": _call(service.assign_responder, user, incident_id, body.responderId, reassign=False)}


@router.post("/dispatcher/incidents/{incident_id}/reassign")
def reassign(incident_id: str, body: AssignmentIn,
             user: dict = Depends(require_permission("dispatch.reassign"))):
    return {"assignment": _call(service.assign_responder, user, incident_id, body.responderId, reassign=True)}


@router.post("/dispatcher/assignments/{assignment_id}/cancel")
def cancel(assignment_id: str, user: dict = Depends(require_permission("dispatch.cancel"))):
    return {"assignment": _call(service.cancel_assignment, user, assignment_id)}


@router.get("/responder/assignments")
def own_assignments(history: bool = False,
                    user: dict = Depends(require_permission("assignments.view_own"))):
    return {"assignments": _call(service.list_assignments, user, history=history)}


@router.post("/responder/assignments/{assignment_id}/transition")
def transition(assignment_id: str, body: AssignmentTransitionIn,
               user: dict = Depends(require_permission("assignments.view_own"))):
    return {"assignment": _call(service.transition_assignment, user, assignment_id, body.status,
                                  notes=body.notes, outcome=body.outcome,
                                  decline_reason=body.declineReason)}


@router.post("/responder/availability")
def availability(body: AvailabilityIn,
                 user: dict = Depends(require_permission("assignments.view_own"))):
    return _call(service.set_availability, user, body.status)


@router.get("/notifications")
def notifications(unreadOnly: bool = False,
                  user: dict = Depends(require_permission("notifications.view_own"))):
    return {"notifications": _call(service.list_notifications, user, unread_only=unreadOnly)}


@router.get("/live-camera-sessions/{area_id}")
def live_camera_session(area_id: str, user: dict = Depends(require_permission('profile.view_own'))):
    if user.get('role') not in {'admin', 'dispatcher'} and user.get('areaId') != area_id:
        raise HTTPException(status_code=403, detail='Outside your assigned area.')
    with connection() as conn:
        row = conn.execute('SELECT payload,updated_at FROM live_camera_sessions WHERE area_id=%s',
                           (area_id,)).fetchone()
    return {'session': {**json.loads(row['payload']), 'updatedAt': row['updated_at'].isoformat()}
            if row else None}


@router.put("/live-camera-sessions/{area_id}")
def update_live_camera_session(area_id: str, body: LiveCameraSessionIn,
                               user: dict = Depends(require_permission('assignments.view_own'))):
    if user.get('role') != 'responder' or user.get('areaId') != area_id:
        raise HTTPException(status_code=403, detail='Outside your assigned area.')
    payload = body.model_dump(exclude_unset=True)
    preview = payload.get('livePreviewDataUrl')
    if preview and not preview.startswith('data:image/jpeg;base64,'):
        raise HTTPException(status_code=422, detail='Preview must be a JPEG data URL.')
    if len(json.dumps(payload)) > 500000:
        raise HTTPException(status_code=422, detail='Live status exceeds the size limit.')
    with connection() as conn, conn.transaction():
        previous = conn.execute('SELECT payload FROM live_camera_sessions WHERE area_id=%s',
                                (area_id,)).fetchone()
        merged = {**(json.loads(previous['payload']) if previous else {}), **payload,
                  'areaId': area_id, 'responderUid': user['id']}
        conn.execute('''INSERT INTO live_camera_sessions(area_id,responder_id,payload)
                        VALUES (%s,%s,%s) ON CONFLICT(area_id) DO UPDATE SET
                        responder_id=excluded.responder_id,payload=excluded.payload,updated_at=now()''',
                     (area_id, user['id'], json.dumps(merged)))
    return {'success': True}


@router.post("/notifications/{notification_id}/read")
def notification_read(notification_id: str,
                      user: dict = Depends(require_permission("notifications.view_own"))):
    return {"notification": _call(service.mark_notification_read, user, notification_id)}


@router.get("/admin/audit-logs")
def audit_logs(limit: int = 200, user: dict = Depends(require_permission("audit_logs.view"))):
    return {"auditLogs": _call(service.list_audit_logs, limit)}


@router.get("/admin/analytics")
def analytics(user: dict = Depends(require_permission("analytics.view"))):
    return _call(service.analytics_summary)


@router.get("/admin/ai-settings")
def ai_settings(user: dict = Depends(require_permission("ai_settings.view"))):
    return {"settings": _call(service.get_settings)}


@router.put("/admin/ai-settings/{key}")
def ai_setting(key: str, body: SettingIn,
               user: dict = Depends(require_permission("ai_settings.manage"))):
    return {"setting": _call(service.set_setting, user, key, body.value)}
