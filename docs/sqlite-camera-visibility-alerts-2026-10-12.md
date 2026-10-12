# Camera boxes, collision notices, and SQLite storage

## Result

Detection boxes are always enabled in the camera monitor grid, selected camera
view, and dedicated detections grid. Network CCTV and USB cameras share the same
presentation. Each backend-camera surface uses the exact analyzed image paired
with its boxes, dimensions, camera, session and sequence. It retains the last
analyzed frame between updates and clearly marks it stale when appropriate;
retained boxes are never presented as positions in a newer raw video frame.
Normal object boxes are no longer suppressed by accident-only history filtering.
Non-project labels in returned detections are preserved for display.

The selected camera and background monitor tiles show **Collision Detected**
when the backend returns `confirmed_crash`. The selected-camera notice remains
until dismissed, including when incident persistence fails; the failure remains
visible. The dispatcher shell also shows a dismissible incident notice even if
the siren is unarmed. Candidate/verifying states say that no collision has been
confirmed yet. Confirmation criteria, tracker ownership, detector models,
thresholds and collision logic were not loosened. Audible alarms retain the
existing rules for newly persisted confirmed incidents and duplicate suppression.

## SQLite migration

Operational authentication, roles, sessions, cameras, incidents, review cases,
assignments, notifications, preferences and audits now use
`data/crashguard-operations.sqlite`. `CRASHGUARD_SQLITE_PATH` can override this
path. The existing `data/crashguard.sqlite` retains legacy camera/capture data.
Both stores are SQLite; the runtime ignores former network database URLs.

SQLite foreign keys, case-insensitive account-email uniqueness, partial unique
assignment indexes, WAL, a busy timeout and `BEGIN IMMEDIATE` transactions
preserve authorization and serialize competing claim/assignment/event writes.
JSON, booleans and UTC timestamps round-trip through the operational API.
Legacy sample camera status now uses authenticated, area-scoped SQLite endpoints.

Firebase client imports, configuration helpers, rules/configuration, runtime and
development package dependencies were removed. The npm lockfile was pruned by
dependency reachability without upgrading retained packages. The pnpm lockfile
already contained no Firebase entries. Local unused Firebase environment entries
were removed without displaying values. Database files and SQLite sidecars are
ignored; no secret values were added to source or examples.

The old backend was stopped before the final read-only PostgreSQL snapshot was
imported. The SQLite backend was restarted on `127.0.0.1:8010`. Imported counts:
5 areas, 3 users, 114 sessions, 8 cameras, 38 incidents/reviews, 20 assignments,
32 alerts, 64 notifications, 351 audits, 182 timeline entries and 3 preferences.
All imported table counts, account password hashes, session hashes and protected
camera references were checked against the source without printing their values.
The old PostgreSQL database was not modified or deleted. External Firebase data
was not accessed or deleted.

`backend/scripts/migrate_operations_to_sqlite.py` is an explicit one-time import
tool, not a runtime fallback. Its optional dependencies live in
`backend/requirements-migration.txt`; the running application does not import
psycopg. Historical PostgreSQL migration files are retained for the old schema.
Do not run them to initialize the new SQLite runtime. SQLite initializes its
schema and role/permission seeds automatically. The importer refuses populated
destinations and prints counts only. Existing accounts keep their credentials;
no account resets were performed.

## Validation

- Final isolated backend suite: **389 passed, 0 failed, 1 existing pair-safety
  XFAIL** (390 tests, 94.432 seconds). Tests use temporary SQLite files, including
  authentication, dispatch, concurrent claims/assignments, event deduplication,
  privacy, rollback, foreign keys and camera-status scope.
- Frontend: **57 passed, 0 failed**; TypeScript check passed.
- Restarted backend `/api/health`: HTTP 200; SQLite health reports engine
  `sqlite`, integrity `ok`, and no foreign-key violations.
- Login, dispatcher live monitor and detections routes compile and return HTTP
  200. The backend had no network database/Firebase connections at verification.
- Git whitespace check passed. Index empty; nothing staged, committed or pushed.

Windows Computer Use reported an unavailable native pipe, and browser inventory
was empty. Live visual placement and audible playback could not be inspected in
this session. No physical-camera inference or reserved collision recording was
used for these checks. Camera monitoring must be started again after the backend
restart; alarms must be armed through the normal browser control for playback.
Prior continuity limitations and the pair-safety XFAIL remain unresolved by this
UI/storage task; candidate footage is not automatically promoted to a collision.
