# CrashGuard Security + Detection Integration Repair

Scope: current working tree following `system-audit-2026-09-26.md`. Findings were checked against the current implementation. No physical camera was contacted for validation, and no training was run.

## 1. Authentication Bypass

Verified: **YES**

Root cause: camera list, camera access, camera stream, camera status, and connection-test handlers converted missing/failed authentication into access. Default camera status/test-detection endpoints lacked authentication. The compatibility verifier also accepted unsigned identity payloads when Firebase verification was not configured.

Fixed: **YES**

- Compatibility routes now use the existing PostgreSQL cookie/bearer session verifier, including the first-password-change gate.
- No synthetic dispatcher/admin principal remains. Failed authentication stays 401; unavailable authentication storage does not create access.
- Camera list/detail require `cameras.view`; streaming/monitoring require both view and monitor permissions. Create/update/disable use the existing explicit permission checks.
- Connection testing requires camera create/update permission and no longer creates a camera or starts a monitor.
- Camera stream tickets are tied to an active PostgreSQL session and current permissions; logout revokes their usefulness. The default signing secret is random per process rather than a source-code constant.
- Removed automatic legacy bootstrap-account seeding from server import. No existing account was modified.

Regression tests: unauthenticated list, detail, status, preview GET/HEAD, latest frame, events, monitor start/stop, stream token, detection controls, add/delete/enable/disable, connection test, and stream ingestion reject requests. Responder denial, dispatcher/admin access, unsigned bearer rejection, password-change gate, and stream-ticket logout revocation are covered.

## 2. Camera Credential Exposure

Verified: **YES**

Fixed: **YES**

Credentials returned by API: **NO** in the tested response paths.

Legacy camera list/detail/create/update/enable/disable use the public serializer. PostgreSQL camera list/update and audit data omit connection secrets. Validation errors no longer echo submitted input. Application log/error text redacts URL user-info. Camera settings omit the stored username/password and expose configuration flags. Public edit responses do not contain credentials, so omitted connection settings now preserve the stored URL.

Tests cover secret-bearing URLs in legacy camera responses, PostgreSQL list/mutation/audit responses, validation failures, and preservation of stored credentials. Native decoder behavior with a real RTSP camera was not exercised.

## 3. Detection Persistence

Detection authoritative store: **PostgreSQL for accepted confirmed-crash and aftermath-review operational events.**

Dispatcher authoritative store: **PostgreSQL.**

Runtime bridge before: **NO**

Runtime bridge after: **YES**

Current path:

1. CCTV frame inference, existing candidate/confirmation decisions, and the three-observation behavior remain in the active detector.
2. Accepted operational decisions enter `persist_operational_detection` through the compatibility persistence adapter.
3. `phase3.service.create_ai_incident` commits the incident, pending review, alert, dispatcher notifications, timeline, and audit in one PostgreSQL transaction.
4. Dispatcher `/api/v3/incidents` and notifications read those same committed records.
5. Existing review/assignment services update PostgreSQL; responder APIs enforce assignment scope.

Confirmed operational events are not independently inserted into SQLite. SQLite remains for existing camera compatibility metadata, historical cases, isolated legacy tests, and one-shot static-image review, which has no operational dispatch creation contract. There is no silent SQLite fallback on an operational save failure.

The historical function name `persist_sqlite_crash_case` remains for compatibility, but its confirmed/aftermath branches return through the PostgreSQL adapter before any SQLite case write.

Database safety:

- Configured operational target: `127.0.0.1:5433/crashguard`, user `crashguard`; password not printed.
- That target timed out during the read-only connection check; its current migration state could not be verified.
- The separately configured test target was not overwritten or reused.
- A fresh temporary PostgreSQL 16 cluster bound to `127.0.0.1:55433` hosted `crashguard_test` for validation and was stopped after testing.
- Existing migrations were applied only to that fresh test database; head is `0003_camera_permissions`. No new migration was required.
- Operational users, passwords, incidents, cases, and assignments were not deleted, reseeded, or reset.

## 4. Detection → Dispatcher

Validation label: **CONTROLLED_INTEGRATION_TEST**

Controlled confirmed crash:

- Persisted: **YES**
- Visible through dispatcher API: **YES**
- Duplicate prevented: **YES**
- Candidate created incident: **NO**

The test invokes the real persistence adapter with a simulated confirmed detector decision and uses real PostgreSQL. It verifies one incident, one alert/audit creation, dispatcher notification delivery, queue retrieval, repeated and concurrent same-event submissions, review, assignment, responder visibility, and unauthenticated rejection. No parallel SQLite operational case is created.

Stable detector event IDs survive retry. The database unique event key and transaction-level serialization prevent concurrent duplicates. Pending review lookup uses the operational store. Failed saves do not start a successful-save cooldown.

The existing aftermath path creates `aftermath_review` with `AWAITING_REVIEW`; it does not auto-confirm the incident. Candidate, ignored, and unverified decisions do not create operational incidents. Human confirmation remains required before dispatch.

This is not live-camera E2E validation, a fresh model-accuracy evaluation, or browser playback validation.

## 5. Notification Contract

False `failed_missing_notification` reproduced: **YES**, verified from the repository return contract and handler branches.

Fixed: **YES**

Successful persistence is a committed operational incident, not the presence of a single notification ID. Dispatcher notifications execute transactionally; the adapter returns their count. No fake notification ID is created. API save status remains `created` when an optional notification ID is absent, while actual save failure remains `failed`/`backend_save_failed`. Duplicate processing reports an existing incident and sends no duplicate notification.

Tests cover successful saves without a notification ID, actual save failure/retry, duplicates, dispatcher notification creation, and absence of responder notifications before dispatch.

## 6. Legacy Authorization

Caller-controlled identity vulnerability: **YES**

Fixed: **YES**

Case actions now derive the actor from the authenticated principal and enforce the permission associated with the action. Responder detail/actions are restricted to their assigned case. Notification archiving checks responder ownership. Debug camera alert creation requires the administrative AI setting permission.

Stream ingestion requires an authorized saved camera ID, resolves the stored source, ignores a caller's replacement URL, and no longer upserts cameras. Proposed connection tests are read-only. Camera host validation now accepts local IPs/localhost or explicitly configured `AUTHORIZED_CAMERA_HOSTS` rather than every nonempty host.

## 7. Async Inference

Event-loop blocking verified: **YES** — async upload handlers previously performed synchronous inference/video loops without yielding.

Mitigation implemented: **YES**

Image/video upload handlers now execute as synchronous FastAPI worker-thread handlers. A shared nonblocking inference lock bounds model work across upload, stream-frame, and live-monitor paths to one job per process. Busy work receives a retryable 503 instead of creating an unbounded inference queue. The existing single-process launch is retained.

The concurrency regression holds a video request in controlled blocking work, verifies `/api/health` completes while it is still running, and verifies a second inference request receives 503.

Model behavior changed: **NO** — no weights, inference confidence arguments, detector thresholds, collision geometry, or confirmation rules were changed. Scheduling under concurrent load is intentionally bounded.

## 8. Tests

Final full regression run: **261 backend tests passed in 67.260 seconds; no failures, errors, or skipped tests.**

- TypeScript: **PASS** — `npm run typecheck`.
- Frontend: **PASS** — 35 tests.
- Backend: **PASS** — full suite, including isolated PostgreSQL tests; see final count below.
- Authentication: **PASS**.
- Permissions: **PASS**.
- Detection → dispatcher: **PASS**, `CONTROLLED_INTEGRATION_TEST`.

Commands:

```powershell
npm run typecheck
node --experimental-strip-types --test frontend-tests/*.test.ts
# DATABASE_URL must explicitly identify an isolated crashguard_test database.
.\backend\.venv\Scripts\python.exe backend/scripts/run_isolated_tests.py
```

The test runner redirects SQLite before importing the server and refuses an operational PostgreSQL database name. The existing PostgreSQL suite's destructive test setup ran only in the fresh disposable test cluster.

## 9. Existing Test Error

Missing detector constant root cause: the preprocessing test still expected the removed `COLLISION_RAW_VEHICLE_CONFIDENCE_FLOOR` and an explicit inference `conf` argument. The current runtime uses the loaded model's inference default and applies `min_confidence` during box extraction.

Pre-existing: **YES**

Resolved: **YES**, in the test contract, without changing production detector behavior. The original image-size forwarding test remains and still checks the complete prediction call. An additional test verifies that a box-filter confidence override reaches extraction without silently changing model inference confidence. No failing test was skipped or deleted.

## 10. Files Changed

Production:

- `backend/main.py` — fail-closed compatibility authentication, camera permissions/redaction, legacy authorization, operational persistence routing/metadata, stable event IDs, save-status correction, worker-thread upload handlers, bounded inference integration, and removal of automatic legacy account seeding.
- `backend/phase3/service.py` — transactional idempotent detector ingestion, pending operational lookup, camera linkage, notification counts, session-bound stream validation, and camera/audit serialization.
- `backend/phase3/routes.py` — preserve stored camera connection settings when an update omits them.
- `backend/camera_privacy.py` — shared public serialization and URL credential redaction.
- `backend/services/operational_detection.py` — typed detection-to-operational persistence boundary and pending-event compatibility mapping.
- `backend/services/inference_execution.py` — bounded shared inference execution.

Tests and test tooling:

- `backend/tests/test_repair_security.py` — camera endpoint/authentication, privacy, legacy identity, and stream ingestion regressions.
- `backend/tests/test_repair_integration.py` — controlled PostgreSQL detection/dispatch, deduplication, notification, credential, and stream-session tests.
- `backend/tests/test_repair_inference.py` — concurrent responsiveness and bounded model work.
- `backend/tests/test_live_monitor_restoration.py` — optional-notification and true-save-failure tests; use a permitted loopback address in the existing authorization fixture.
- `backend/tests/test_detector_preprocessing.py` — repair the stale expectation and protect unchanged detector confidence behavior.
- `backend/scripts/run_isolated_tests.py` — safe SQLite isolation and explicit test-database guard.

Documentation:

- `docs/security-integration-repair-2026-09-26.md` — this report.

Pre-existing unrelated working-tree changes were retained.

## 11. Safety

- Models changed: **NO**
- Detection thresholds changed: **NO**
- Phase 8C changed: **NO**
- Source B changed: **NO**
- Existing validation datasets changed: **NO**
- User passwords reset: **NO** — authentication tests use newly created isolated test accounts.
- Existing incidents deleted: **NO** — existing integration-test cleanup affected only disposable test data.
- Physical Tapo testing or training resumed: **NO**

## 12. Verdict

**SECURITY_AND_INTEGRATION_FIXED**

This verdict covers the repaired code and controlled integration checks. The configured operational PostgreSQL target was unavailable during this task; its availability/migration state and real-camera/browser operation remain unverified. No live-camera readiness or detector-accuracy claim is made.
