# System audit — 26 September 2026

## Scope and verdict

Reviewed the current working tree, including uncommitted work: active FastAPI entrypoint, detection persistence, camera authentication, operational APIs, frontend API/authentication contracts, and automated tests. Application code was not changed.

The system has substantial implementation and test coverage, but detection-to-dispatch integration and camera access control have blocking defects. Passing component tests do not establish that a real detected collision reaches the operational dispatcher queue.

## Fresh verification

- `npm run typecheck`: passed.
- `node --experimental-strip-types --test frontend-tests/*.test.ts`: 35 passed.
- Backend unittest modules, excluding `test_phase3_postgres`: 223 run, 222 passed, one error. SQLite was redirected to a temporary database before importing the app; DATABASE_URL was removed from that test process to avoid operational PostgreSQL writes.
- The error is `test_live_vehicle_detector_forwards_configured_imgsz`, at `backend/tests/test_detector_preprocessing.py:77`: `backend.main.COLLISION_RAW_VEHICLE_CONFIDENCE_FLOOR` does not exist. The implementation also no longer forwards the expected `conf` argument to the vehicle model.
- Isolated execution of the actual camera guard/list function bodies, with authentication forced to return HTTP 401, returned a dispatcher principal for camera and stream access and returned raw `streamUrl` from the camera list. No real camera was started, stopped, or queried by these checks.
- Isolated host validation accepted `unapproved.example`.
- AST inspection found zero `await` expressions in the async video upload handler.

PostgreSQL integration tests were not run: their setup truncates tables and requires a verified isolated `crashguard_test` database. Production build, browser media playback, physical camera behavior, and fresh event-level model accuracy were not validated in this audit. Existing model evaluation documents are historical evidence, not fresh measurements.

## Findings, in priority order

### 1. Critical: authentication failure grants camera access

Locations: `backend/main.py:487`, `:4160`, `:4713`, `:4767`, `:4824`.

`require_camera_access` and `require_camera_stream_access` catch authentication exceptions and substitute `local_dispatcher` with wildcard permissions. `/api/cameras` similarly converts a 401 into a dispatcher identity. An unauthenticated caller can enumerate cameras and reach camera monitor control and preview paths. Database/authentication outages can also trigger the fallback.

Fix: propagate authentication errors, require the operational camera permission, and remove fallback principals from network-accessible handlers. Add negative endpoint tests for missing, expired, and invalid sessions, including preview and monitor start/stop.

### 2. High: detector persistence is disconnected from the operational dispatcher database

Locations: `backend/main.py:1833`, `:3016`, `:3641`, `:5409`; `backend/repositories/crash_cases.py:392`; `backend/phase3/service.py:538`, `:604`; `components/dispatcher-alerts-view.tsx:116`.

Live, image, and video detections call `persist_sqlite_crash_case`, which writes SQLite cases. Dispatcher alerts and incidents use `/api/v3` and read PostgreSQL. The PostgreSQL `create_ai_incident` function has no runtime caller in the reviewed application; its caller in the integration tests constructs incidents directly. A legacy import script is not continuous ingestion.

Consequence: a successfully detected and saved case can remain absent from dispatcher review, notifications, and assignment workflows.

Fix: connect accepted detector events to PostgreSQL ingestion with stable event identifiers and idempotent retries. Validate one actual detection through review, assignment, and responder visibility; do not seed the incident directly in that test.

### 3. High: a successful case save is classified as a notification failure

Locations: `backend/repositories/crash_cases.py:480`, `:499`; `backend/main.py:3050`, image/video persistence handling.

The repository intentionally creates no responder notification at detection time and returns `createdNotificationId = None`. Detection handlers nevertheless require that ID and convert a created case into `failed_missing_notification`. The live handler exposes `backend_save_failed` even after a successful case write; the video response's case-created condition is also affected.

Fix: distinguish case persistence from notification policy. Generate the intended dispatcher notification through operational ingestion and preserve the rule that responders are notified after dispatch. Test the real repository result rather than mocking a notification ID that it never returns.

### 4. High: camera list exposes stream credentials

Locations: `backend/main.py:4160`; `backend/repositories/crash_cases.py:316`, `:1126`; redaction helper at `backend/main.py:2148`.

The list endpoint returns repository camera objects directly, including `streamUrl`; PostgreSQL reconciliation can populate that URL too. If the URL contains camera credentials, they are returned to the caller. The existing `camera_client_payload` redaction helper is not applied here. Combined with finding 1, the list can expose these values without login.

Fix: serialize all public camera responses through a safe allowlist and test endpoint responses, including URLs with user-info credentials.

### 5. High: legacy token fallback accepts an unverified identity

Location: `backend/main.py:338`, especially `:393` onward.

When no Firebase verifier/emulator is configured, authentication decodes a JWT payload without verifying its signature. For an unknown UID, it can create a local profile using the payload's `admin` role. Legacy routes guarded only by `require_admin` or dashboard role checks can consequently trust caller-controlled identities. This finding is conditional on that configuration; the camera fallback in finding 1 is independent of it.

Fix: use the PostgreSQL session verifier consistently and fail closed when verification is unavailable. Remove the unsigned-token fallback.

### 6. High: unauthenticated stream ingestion bypasses camera onboarding controls

Locations: `backend/main.py:2037`, `:4545`, `:5026`.

`/api/detect/stream-frame` requires no authenticated user. Its helper opens the supplied source and then upserts a camera using caller-supplied metadata. `is_authorized_camera_host` returns true for every nonempty host, despite the validation message describing an allowlist.

Consequence: a caller can trigger backend connections to arbitrary accepted HTTP/RTSP hosts and, for a readable stream, create or overwrite camera records without camera management permission.

Fix: require an authorized saved camera ID; apply camera management permissions to mutations and implement the intended destination policy, including resolution/redirect handling where applicable.

### 7. High: uploaded media processing blocks the API event loop

Locations: `backend/main.py:4452`, `:5045`, `:5140`.

Both upload routes are async functions but directly perform synchronous file operations, OpenCV work, and model inference. The video handler processes the complete video without yielding. With the documented single-worker launch, an upload can prevent other requests from being serviced until processing completes, affecting authentication and live monitoring requests.

Fix: move processing to a bounded worker/thread or job queue, with explicit concurrency and model-access controls. Verify concurrent health/status requests during a representative video upload.

### 8. High: legacy case actions lack per-case authorization and trust actor IDs

Locations: `backend/main.py:4067`, `:4076`; `backend/repositories/crash_cases.py:761`.

Case detail and action routes only require a dashboard role. Actions accept `body.actorId` and pass it into mutation/audit records. There is no check that the responder owns the requested case or that the authenticated user has dispatcher review permission. Repository transition checks validate status, not authorization.

Fix: remove these routes or enforce operational permissions and case ownership. Derive actor identity exclusively from the authenticated session.

### 9. Medium: cookie authentication is ignored during upload attribution

Locations: `backend/main.py:458`, `:4501`; `lib/api-client.ts:266`; `backend/phase3/routes.py` login cookie.

The frontend authenticates using an HttpOnly session cookie, but `optional_request_user` returns None unless an Authorization bearer header exists. Thus ordinary cookie-authenticated camera image requests lose user attribution and the user's default area; absent an explicit area, camera uploads fall back to `demo`.

Fix: recognize the same cookie/session mechanism used elsewhere and reject invalid supplied sessions rather than silently treating them as anonymous.

### 10. Medium: independent repository evidence checks receive fabricated measurements

Location: `backend/main.py:1954`.

Before persistence, the helper sets `temporalVerified=True` for a confirmed decision and substitutes minimum temporal scores. For aftermath decisions it hardcodes abnormality to 0.90 and raises observation count/persistence duration to gate minimums. Those values are not the original verifier measurements. This weakens the repository's stated independent safety check and makes persisted evidence misleading.

Fix: pass measured verifier evidence through unchanged and let the repository reject insufficient evidence. Add tests where a positive decision label is accompanied by insufficient observations or persistence duration.

### 11. Medium: upload resource limits and retention are missing

Locations: `backend/main.py:1134`, `:4452`, `:5045`.

Uploads are copied without application-level size limits; video work has no duration/frame budget, and raw uploaded files are retained even on many failure paths. These endpoints also lack mandatory authentication. Repeated large or invalid media can exhaust storage or processing capacity.

Fix: set upload and decoded-media limits, bound concurrent work, and define cleanup/retention rules while preserving evidence linked to cases.

## Additional verification gaps

- Repair the failing detector confidence-contract test by deciding the intended inference threshold; do not simply delete the assertion.
- Existing camera security tests cover the redaction helper, while the actual list endpoint bypasses it. An existing missing-session test exercises the editor guard, not the failing monitor/stream guards.
- `/outputs` and `/uploads/crash-media` are mounted as unauthenticated static files. Anyone holding a media URL can fetch it; operational role restrictions do not protect these files.
- `next.config.mjs` allows builds despite TypeScript errors. This audit's explicit typecheck passed, but a build alone is not a type-safety check.
- Project notes contain stale and conflicting status claims, including test counts and the alert-audio task. Update documentation after behavior is fixed and validated.

## Suggested repair sequence

1. Close authentication fallbacks, redact camera responses, and protect stream ingestion and case actions.
2. Connect detector events to PostgreSQL and reconcile persistence/notification semantics.
3. Preserve measured detection evidence and restore the detector test contract.
4. Move inference off the event loop and bound upload resources.
5. Run an isolated end-to-end test from media detection through dispatcher review and responder assignment, followed by browser playback and physical-camera validation.
