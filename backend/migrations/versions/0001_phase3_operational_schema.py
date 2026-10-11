"""Phase 3 PostgreSQL operational schema and RBAC seeds."""

from alembic import op


revision = "0001_phase3"
down_revision = None
branch_labels = None
depends_on = None


SCHEMA_SQL = r"""
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

CREATE TABLE areas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email CITEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','DISABLED','LOCKED')),
    must_change_password BOOLEAN NOT NULL DEFAULT TRUE,
    area_id UUID REFERENCES areas(id) ON DELETE SET NULL,
    availability_status TEXT NOT NULL DEFAULT 'OFFLINE'
      CHECK (availability_status IN ('AVAILABLE','ASSIGNED','EN_ROUTE','ARRIVED','RESPONDING','OFFLINE')),
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    disabled_at TIMESTAMPTZ
);

CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE CHECK (name IN ('ADMIN','DISPATCHER','RESPONDER')),
    description TEXT NOT NULL
);
CREATE TABLE permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL
);
CREATE TABLE user_roles (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);
CREATE TABLE role_permissions (
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_agent TEXT,
    ip_address INET
);

CREATE TABLE cameras (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    legacy_id TEXT UNIQUE,
    area_id UUID REFERENCES areas(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    location TEXT,
    stream_reference TEXT,
    status TEXT NOT NULL DEFAULT 'OFFLINE' CHECK (status IN ('ONLINE','OFFLINE','DISABLED','ERROR')),
    detection_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    last_heartbeat_at TIMESTAMPTZ,
    fps DOUBLE PRECISION,
    ai_latency_ms DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    legacy_case_id TEXT UNIQUE,
    detector_event_id TEXT NOT NULL UNIQUE,
    camera_id UUID REFERENCES cameras(id) ON DELETE SET NULL,
    state TEXT NOT NULL DEFAULT 'AWAITING_REVIEW'
      CHECK (state IN ('AWAITING_REVIEW','CONFIRMED','FALSE_ALARM','ACTIVE_RESPONSE','RESOLVED','CANCELLED')),
    priority TEXT CHECK (priority IS NULL OR priority IN ('CRITICAL','HIGH','MEDIUM','LOW')),
    incident_type TEXT,
    detection_mode TEXT NOT NULL CHECK (detection_mode IN ('temporal_collision','aftermath_review')),
    ai_score DOUBLE PRECISION NOT NULL CHECK (ai_score >= 0 AND ai_score <= 1),
    evidence_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    media JSONB NOT NULL DEFAULT '{}'::jsonb,
    location TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    detected_at TIMESTAMPTZ NOT NULL,
    confirmed_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE review_cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL UNIQUE REFERENCES incidents(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'PENDING_REVIEW'
      CHECK (status IN ('PENDING_REVIEW','UNDER_REVIEW','FALSE_ALARM','CONFIRMED')),
    reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    review_started_at TIMESTAMPTZ,
    claim_expires_at TIMESTAMPTZ,
    reviewed_at TIMESTAMPTZ,
    false_alarm_reason TEXT,
    dispatcher_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    responder_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    assigned_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    previous_assignment_id UUID REFERENCES assignments(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'ASSIGNED'
      CHECK (status IN ('ASSIGNED','ACCEPTED','EN_ROUTE','ARRIVED','RESPONDING','RESOLVED','DECLINED','CANCELLED','REASSIGNED')),
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    accepted_at TIMESTAMPTZ,
    en_route_at TIMESTAMPTZ,
    arrived_at TIMESTAMPTZ,
    responding_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    declined_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    decline_reason TEXT,
    response_notes TEXT,
    outcome TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'EMITTED' CHECK (state IN ('EMITTED','ACKNOWLEDGED','CLOSED')),
    emitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    acknowledged_at TIMESTAMPTZ,
    UNIQUE (incident_id, type)
);
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    incident_id UUID REFERENCES incidents(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    before_data JSONB,
    after_data JSONB,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE incident_timeline (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE system_settings (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_by UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_users_area ON users(area_id);
CREATE INDEX idx_user_roles_user ON user_roles(user_id);
CREATE INDEX idx_sessions_user_active ON sessions(user_id, expires_at) WHERE revoked_at IS NULL;
CREATE INDEX idx_cameras_area ON cameras(area_id);
CREATE INDEX idx_incidents_camera_detected ON incidents(camera_id, detected_at DESC);
CREATE INDEX idx_incidents_state ON incidents(state, detected_at DESC);
CREATE INDEX idx_review_cases_status_created ON review_cases(status, created_at);
CREATE INDEX idx_review_cases_reviewer_status ON review_cases(reviewed_by, status);
CREATE INDEX idx_assignments_responder_status ON assignments(responder_id, status);
CREATE INDEX idx_assignments_incident_status ON assignments(incident_id, status);
CREATE UNIQUE INDEX uq_assignments_one_active_incident ON assignments(incident_id)
  WHERE status IN ('ASSIGNED','ACCEPTED','EN_ROUTE','ARRIVED','RESPONDING');
CREATE INDEX idx_notifications_user_read_created ON notifications(user_id, read_at, created_at DESC);
CREATE INDEX idx_audit_entity_created ON audit_logs(entity_type, entity_id, created_at DESC);
CREATE INDEX idx_timeline_incident_created ON incident_timeline(incident_id, created_at);

INSERT INTO roles (name, description) VALUES
 ('ADMIN','Manages accounts, configuration, cameras, analytics, and audit records'),
 ('DISPATCHER','Reviews AI incidents and manages operational dispatch'),
 ('RESPONDER','Handles assigned incidents in the field');

INSERT INTO permissions (code, description) VALUES
 ('users.view','View users'),('users.create','Create users'),('users.update','Update users'),
 ('users.disable','Disable or reactivate users'),('users.assign_role','Assign roles'),
 ('roles.view','View roles'),('roles.manage','Manage roles'),('cameras.view','View cameras'),
 ('cameras.create','Create cameras'),('cameras.update','Update cameras'),
 ('cameras.disable','Disable cameras'),('areas.view','View areas'),('areas.manage','Manage areas'),
 ('incidents.view_all','View all incidents'),('analytics.view','View analytics'),
 ('ai_settings.view','View AI settings'),('ai_settings.manage','Manage AI settings'),
 ('audit_logs.view','View audit logs'),('system_settings.view','View system settings'),
 ('system_settings.manage','Manage system settings'),('incidents.view','View operational incidents'),
 ('incidents.review','Claim reviews'),('incidents.confirm','Confirm incidents'),
 ('incidents.false_alarm','Mark false alarms'),('incidents.prioritize','Set incident priority'),
 ('incidents.add_note','Add dispatcher notes'),('responders.view','View responder availability'),
 ('dispatch.assign','Assign responders'),('dispatch.reassign','Reassign responders'),
 ('dispatch.cancel','Cancel assignments'),('map.view','View incident map'),
 ('history.view','View incident history'),('assignments.view_own','View own assignments'),
 ('assignments.accept','Accept own assignment'),('assignments.decline','Decline own assignment'),
 ('response.en_route','Mark en route'),('response.arrive','Mark arrived'),
 ('response.start','Start response'),('response.resolve','Resolve response'),
 ('incidents.view_assigned','View assigned incidents'),('response_notes.create','Create response notes'),
 ('notifications.view_own','View own notifications');

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
WHERE r.name='ADMIN' AND p.code IN (
 'users.view','users.create','users.update','users.disable','users.assign_role','roles.view','roles.manage',
 'cameras.view','cameras.create','cameras.update','cameras.disable','areas.view','areas.manage',
 'incidents.view_all','analytics.view','ai_settings.view','ai_settings.manage','audit_logs.view',
 'system_settings.view','system_settings.manage','notifications.view_own');
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
WHERE r.name='DISPATCHER' AND p.code IN (
 'cameras.view','incidents.view','incidents.review','incidents.confirm','incidents.false_alarm',
 'incidents.prioritize','incidents.add_note','responders.view','dispatch.assign','dispatch.reassign',
 'dispatch.cancel','map.view','history.view','notifications.view_own');
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
WHERE r.name='RESPONDER' AND p.code IN (
 'assignments.view_own','assignments.accept','assignments.decline','response.en_route',
 'response.arrive','response.start','response.resolve','incidents.view_assigned',
 'response_notes.create','notifications.view_own');
"""


def upgrade() -> None:
    op.execute(SCHEMA_SQL)


def downgrade() -> None:
    op.execute(
        "DROP TABLE IF EXISTS system_settings, incident_timeline, audit_logs, notifications, "
        "alerts, assignments, review_cases, incidents, cameras, sessions, role_permissions, "
        "user_roles, permissions, roles, users, areas CASCADE"
    )
