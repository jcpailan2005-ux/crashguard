-- SQLite operational schema. Legacy captures remain in crashguard.sqlite.




CREATE TABLE IF NOT EXISTS areas (
    id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TEXT NOT NULL DEFAULT (now()),
    updated_at TEXT NOT NULL DEFAULT (now())
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    email TEXT COLLATE NOCASE NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','DISABLED','LOCKED')),
    must_change_password INTEGER NOT NULL DEFAULT TRUE,
    area_id TEXT REFERENCES areas(id) ON DELETE SET NULL,
    availability_status TEXT NOT NULL DEFAULT 'OFFLINE'
      CHECK (availability_status IN ('AVAILABLE','ASSIGNED','EN_ROUTE','ARRIVED','RESPONDING','OFFLINE')),
    last_login_at TEXT,
    created_at TEXT NOT NULL DEFAULT (now()),
    updated_at TEXT NOT NULL DEFAULT (now()),
    disabled_at TEXT
);

CREATE TABLE IF NOT EXISTS roles (
    id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    name TEXT NOT NULL UNIQUE CHECK (name IN ('ADMIN','DISPATCHER','RESPONDER')),
    description TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS permissions (
    id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    code TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS user_roles (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id TEXT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);
CREATE TABLE IF NOT EXISTS role_permissions (
    role_id TEXT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id TEXT NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    created_at TEXT NOT NULL DEFAULT (now()),
    last_used_at TEXT NOT NULL DEFAULT (now()),
    user_agent TEXT,
    ip_address TEXT
);

CREATE TABLE IF NOT EXISTS cameras (
    id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    legacy_id TEXT UNIQUE,
    area_id TEXT REFERENCES areas(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    location TEXT,
    stream_reference TEXT,
    status TEXT NOT NULL DEFAULT 'OFFLINE' CHECK (status IN ('ONLINE','OFFLINE','DISABLED','ERROR')),
    detection_enabled INTEGER NOT NULL DEFAULT TRUE,
    latitude REAL,
    longitude REAL,
    last_heartbeat_at TEXT,
    fps REAL,
    ai_latency_ms REAL,
    created_at TEXT NOT NULL DEFAULT (now()),
    updated_at TEXT NOT NULL DEFAULT (now())
);

CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    legacy_case_id TEXT UNIQUE,
    detector_event_id TEXT NOT NULL UNIQUE,
    camera_id TEXT REFERENCES cameras(id) ON DELETE SET NULL,
    state TEXT NOT NULL DEFAULT 'AWAITING_REVIEW'
      CHECK (state IN ('AWAITING_REVIEW','CONFIRMED','FALSE_ALARM','ACTIVE_RESPONSE','RESOLVED','CANCELLED')),
    priority TEXT CHECK (priority IS NULL OR priority IN ('CRITICAL','HIGH','MEDIUM','LOW')),
    incident_type TEXT,
    detection_mode TEXT NOT NULL CHECK (detection_mode IN ('temporal_collision','aftermath_review')),
    ai_score REAL NOT NULL CHECK (ai_score >= 0 AND ai_score <= 1),
    evidence_summary TEXT NOT NULL DEFAULT '{}',
    media TEXT NOT NULL DEFAULT '{}',
    location TEXT,
    latitude REAL,
    longitude REAL,
    detected_at TEXT NOT NULL,
    confirmed_at TEXT,
    resolved_at TEXT,
    created_at TEXT NOT NULL DEFAULT (now()),
    updated_at TEXT NOT NULL DEFAULT (now())
);

CREATE TABLE IF NOT EXISTS review_cases (
    id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    incident_id TEXT NOT NULL UNIQUE REFERENCES incidents(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'PENDING_REVIEW'
      CHECK (status IN ('PENDING_REVIEW','UNDER_REVIEW','FALSE_ALARM','CONFIRMED')),
    reviewed_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    review_started_at TEXT,
    claim_expires_at TEXT,
    reviewed_at TEXT,
    false_alarm_reason TEXT,
    dispatcher_notes TEXT,
    created_at TEXT NOT NULL DEFAULT (now()),
    updated_at TEXT NOT NULL DEFAULT (now())
);

CREATE TABLE IF NOT EXISTS assignments (
    id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    responder_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    assigned_by TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    previous_assignment_id TEXT REFERENCES assignments(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'ASSIGNED'
      CHECK (status IN ('ASSIGNED','ACCEPTED','EN_ROUTE','ARRIVED','RESPONDING','RESOLVED','DECLINED','CANCELLED','REASSIGNED')),
    assigned_at TEXT NOT NULL DEFAULT (now()),
    accepted_at TEXT,
    en_route_at TEXT,
    arrived_at TEXT,
    responding_at TEXT,
    resolved_at TEXT,
    declined_at TEXT,
    cancelled_at TEXT,
    decline_reason TEXT,
    response_notes TEXT,
    outcome TEXT,
    updated_at TEXT NOT NULL DEFAULT (now())
);

CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'EMITTED' CHECK (state IN ('EMITTED','ACKNOWLEDGED','CLOSED')),
    emitted_at TEXT NOT NULL DEFAULT (now()),
    acknowledged_at TEXT,
    UNIQUE (incident_id, type)
);
CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    incident_id TEXT REFERENCES incidents(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    read_at TEXT,
    created_at TEXT NOT NULL DEFAULT (now())
);
CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    actor_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    before_data TEXT,
    after_data TEXT,
    metadata TEXT,
    created_at TEXT NOT NULL DEFAULT (now())
);
CREATE TABLE IF NOT EXISTS incident_timeline (
    id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    actor_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    details TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (now())
);
CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    updated_at TEXT NOT NULL DEFAULT (now())
);

CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);
CREATE INDEX IF NOT EXISTS idx_users_area ON users(area_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user_active ON sessions(user_id, expires_at) WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_cameras_area ON cameras(area_id);
CREATE INDEX IF NOT EXISTS idx_incidents_camera_detected ON incidents(camera_id, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_incidents_state ON incidents(state, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_review_cases_status_created ON review_cases(status, created_at);
CREATE INDEX IF NOT EXISTS idx_review_cases_reviewer_status ON review_cases(reviewed_by, status);
CREATE INDEX IF NOT EXISTS idx_assignments_responder_status ON assignments(responder_id, status);
CREATE INDEX IF NOT EXISTS idx_assignments_incident_status ON assignments(incident_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS uq_assignments_one_active_incident ON assignments(incident_id)
  WHERE status IN ('ASSIGNED','ACCEPTED','EN_ROUTE','ARRIVED','RESPONDING');
CREATE INDEX IF NOT EXISTS idx_notifications_user_read_created ON notifications(user_id, read_at, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_entity_created ON audit_logs(entity_type, entity_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_timeline_incident_created ON incident_timeline(incident_id, created_at);


CREATE TABLE IF NOT EXISTS user_preferences (
 user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 theme TEXT NOT NULL DEFAULT 'system' CHECK (theme IN ('light','dark','system')),
 notification_preferences TEXT NOT NULL DEFAULT '{}',
 updated_at TEXT NOT NULL DEFAULT (now())
);
CREATE TABLE IF NOT EXISTS live_camera_sessions (
 area_id TEXT PRIMARY KEY,
 responder_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 payload TEXT NOT NULL,
 updated_at TEXT NOT NULL DEFAULT (now())
);
