PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  uid TEXT PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  displayName TEXT,
  role TEXT NOT NULL CHECK(role IN ('user', 'responder', 'admin')),
  areaId TEXT,
  passwordHash TEXT,
  passwordSalt TEXT,
  isActive INTEGER NOT NULL DEFAULT 1,
  lastLoginAt TEXT,
  createdAt TEXT NOT NULL,
  updatedAt TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS areas (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  city TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS crash_cases (
  caseId TEXT PRIMARY KEY,
  status TEXT NOT NULL CHECK(status IN ('pending_review', 'under_review', 'confirmed_crash', 'false_alarm', 'dispatched', 'responding', 'arrived', 'resolved')),
  confidence REAL NOT NULL DEFAULT 0,
  detectedAt TEXT NOT NULL,
  reviewedAt TEXT,
  confirmedAt TEXT,
  falseAlarmAt TEXT,
  dispatchedAt TEXT,
  resolvedAt TEXT,
  updatedAt TEXT NOT NULL,
  location TEXT,
  latitude REAL,
  longitude REAL,
  areaId TEXT,
  videoPath TEXT,
  keyFramePath TEXT,
  thumbnailPath TEXT,
  annotatedPath TEXT,
  sourceCamera TEXT,
  cameraId TEXT,
  cameraName TEXT,
  cameraIp TEXT,
  barangay TEXT,
  roadName TEXT,
  assignedResponderId TEXT,
  triggerStatus TEXT,
  responderId TEXT,
  accidentDetected INTEGER NOT NULL DEFAULT 0,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS crash_actions (
  actionId TEXT PRIMARY KEY,
  caseId TEXT NOT NULL,
  action TEXT NOT NULL,
  actorId TEXT,
  timestamp TEXT NOT NULL,
  notes TEXT,
  previousStatus TEXT,
  nextStatus TEXT,
  FOREIGN KEY(caseId) REFERENCES crash_cases(caseId) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS detection_boxes (
  boxId TEXT PRIMARY KEY,
  caseId TEXT NOT NULL,
  label TEXT NOT NULL,
  confidence REAL NOT NULL,
  x REAL NOT NULL,
  y REAL NOT NULL,
  width REAL NOT NULL,
  height REAL NOT NULL,
  framePath TEXT,
  detectedAt TEXT NOT NULL,
  FOREIGN KEY(caseId) REFERENCES crash_cases(caseId) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notifications (
  notificationId TEXT PRIMARY KEY,
  caseId TEXT,
  title TEXT NOT NULL,
  message TEXT NOT NULL,
  alertLevel TEXT NOT NULL DEFAULT 'review',
  read INTEGER NOT NULL DEFAULT 0,
  responderId TEXT,
  areaId TEXT,
  createdAt TEXT NOT NULL,
  FOREIGN KEY(caseId) REFERENCES crash_cases(caseId) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cameras (
  cameraId TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  cameraIp TEXT,
  areaId TEXT,
  barangay TEXT,
  roadName TEXT,
  locationDescription TEXT,
  location TEXT,
  latitude REAL,
  longitude REAL,
  streamUrl TEXT,
  cameraType TEXT,
  status TEXT,
  isActive INTEGER NOT NULL DEFAULT 1,
  detectionEnabled INTEGER NOT NULL DEFAULT 1,
  lastEventAt TEXT,
  lastSeenAt TEXT,
  createdAt TEXT NOT NULL,
  updatedAt TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS responder_camera_assignments (
  id TEXT PRIMARY KEY,
  responderId TEXT NOT NULL,
  areaId TEXT,
  cameraId TEXT,
  role TEXT NOT NULL DEFAULT 'viewer',
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(cameraId) REFERENCES cameras(cameraId) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS analytics_daily (
  day TEXT PRIMARY KEY,
  detections INTEGER NOT NULL DEFAULT 0,
  pendingReview INTEGER NOT NULL DEFAULT 0,
  confirmedCrashes INTEGER NOT NULL DEFAULT 0,
  falseAlarms INTEGER NOT NULL DEFAULT 0,
  dispatchedCases INTEGER NOT NULL DEFAULT 0,
  resolvedCases INTEGER NOT NULL DEFAULT 0,
  avgReviewTimeSeconds REAL,
  avgResolveTimeSeconds REAL
);

CREATE TABLE IF NOT EXISTS analytics_monthly (
  month TEXT PRIMARY KEY,
  detections INTEGER NOT NULL DEFAULT 0,
  confirmedCrashes INTEGER NOT NULL DEFAULT 0,
  falseAlarms INTEGER NOT NULL DEFAULT 0,
  avgReviewTimeSeconds REAL,
  avgResolveTimeSeconds REAL
);

CREATE INDEX IF NOT EXISTS idx_crash_cases_status ON crash_cases(status);
CREATE INDEX IF NOT EXISTS idx_crash_cases_detectedAt ON crash_cases(detectedAt);
CREATE INDEX IF NOT EXISTS idx_crash_cases_areaId ON crash_cases(areaId);
CREATE INDEX IF NOT EXISTS idx_crash_actions_caseId ON crash_actions(caseId);
CREATE INDEX IF NOT EXISTS idx_detection_boxes_caseId ON detection_boxes(caseId);
CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(read);
CREATE INDEX IF NOT EXISTS idx_notifications_caseId ON notifications(caseId);
