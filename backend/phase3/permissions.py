ADMIN_PERMISSIONS = {
    "users.view", "users.create", "users.update", "users.disable", "users.assign_role",
    "roles.view", "roles.manage", "cameras.view", "cameras.monitor", "cameras.create", "cameras.update",
    "cameras.disable", "cameras.manage_credentials", "areas.view", "areas.manage", "incidents.view_all",
    "analytics.view", "ai_settings.view", "ai_settings.manage", "audit_logs.view",
    "system_settings.view", "system_settings.manage", "notifications.view_own",
    "profile.view_own", "profile.update_own", "preferences.view_own",
    "preferences.update_own", "password.change_own", "notifications.preferences_own",
}

DISPATCHER_PERMISSIONS = {
    "cameras.view", "cameras.monitor", "cameras.create", "incidents.view", "incidents.review", "incidents.confirm",
    "incidents.false_alarm", "incidents.prioritize", "incidents.add_note",
    "responders.view", "dispatch.assign", "dispatch.reassign", "dispatch.cancel",
    "map.view", "history.view", "notifications.view_own", "profile.view_own",
    "profile.update_own", "preferences.view_own", "preferences.update_own",
    "password.change_own", "notifications.preferences_own",
}

RESPONDER_PERMISSIONS = {
    "assignments.view_own", "assignments.accept", "assignments.decline",
    "response.en_route", "response.arrive", "response.start", "response.resolve",
    "incidents.view_assigned", "response_notes.create", "notifications.view_own",
    "profile.view_own", "profile.update_own", "preferences.view_own",
    "preferences.update_own", "password.change_own", "notifications.preferences_own",
}

ROLE_PERMISSIONS = {
    "ADMIN": ADMIN_PERMISSIONS,
    "DISPATCHER": DISPATCHER_PERMISSIONS,
    "RESPONDER": RESPONDER_PERMISSIONS,
}


def principal_has_permission(principal: dict, code: str) -> bool:
    return code in set(principal.get("permissions") or [])

PERMISSION_DESCRIPTIONS = {
    code: code.replace("_", " ").replace(".", ": ").title()
    for values in ROLE_PERMISSIONS.values()
    for code in values
}
