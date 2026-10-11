# Camera Source Selection and Preview Recovery

Date: 2026-10-09 (Asia/Manila). This report covers the current working tree. Earlier uncommitted work was preserved.

## Existing CCTV Failure

Root cause: The browser page retained a monitor session across a backend restart. The restarted backend had no Bago worker; the page kept polling status (HTTP 200 with `disconnected`) and the analysis packet (HTTP 404), but did not send a new monitor-start request. Its prior signed MJPEG/SSE access token was invalid after the backend process changed. The Bago camera and saved RTSP URL were healthy.

Fix: `components/live-camera.tsx` now handles a saved camera's `disconnected` status by starting that monitor again and obtaining fresh stream access. It limits recovery attempts to one in flight and at least five seconds apart. Existing media layout and detector behavior are unchanged. The backend was restarted to load the new source-list endpoint, and the open page subsequently sent one successful Bago monitor-start request.

Bago RTSP: **PASS**. Saved `CAM-30960048ED` still points to RTSP at `192.168.1.17:554/stream2` with credentials present; their values were not printed. Port 554 accepted TCP. OpenCV/FFmpeg opened the saved stream.

Bago frame decode: **PASS**. Direct decode and the existing `LiveCameraMonitor` capture loop produced 1280×720 BGR frames. The isolated loop published 20 frames with advancing sequence and capture timestamps.

Bago preview: **PASS at the backend and browser request level**. The same isolated worker produced a JPEG preview and analyzed-frame packet. The authenticated live page then made 179 successful latest-frame requests, 178 successful analysis-packet requests, and an MJPEG request. These are browser-origin requests; visual painting could not be independently inspected because the browser control tool failed to connect. The live service also served dispatcher incident requests successfully.

RTSP source selection: **PASS**. A Bago RTSP reference resolves as a network source; the worker still opens it with FFmpeg. The webcam opener is used only for configured `webcam://` aliases. No Bago record or RTSP credentials were changed.

## Add Camera

Implemented: **YES**. The existing Camera feeds `Add Camera` dialog now begins with `Camera type`. The CCTV / Network Camera option preserves its existing RTSP fields, test button, save API, and validation. The USB Webcam option shows only a camera name and a select of server-configured aliases. Saving uses the existing authorized camera CRUD fields and puts the record in the existing camera list. No schema or alternate monitor was added.

Dispatcher visibility correction (2026-10-09): The dialog existed, but the Dispatcher Live Monitor hid its `Add Camera` button because the PostgreSQL `DISPATCHER` role lacked `cameras.create`. The operator authorized Dispatcher camera creation. Migration `0004_dispatcher_camera_creation` was applied to the operational database and grants that permission. A page reload refreshes the account profile and reveals the existing button in the Camera feeds header. Dispatchers can create cameras and list configured USB aliases; update, disable, and credential management remain Admin-only. This was checked against the live role grants and permission tests; a browser click-through on the operator's session was not available.

Available types:

- CCTV / Network Camera: **YES**
- USB Webcam: **YES**

The new `GET /api/cameras/local-webcam-sources` route requires the existing `cameras.create` editor permission. It returns only alias references and friendly names, never device indices, backend names, device paths, network URLs, or credentials. It lists configured devices; it does not claim a device is physically available until capture succeeds.

## FOBOS MODEL GW600

USB device correction (2026-10-09): The operator clarified that the source must be the external USB camera, not the laptop's built-in camera. Windows lists `REDRAGON Live Camera` as the external device and `Integrated Camera` as the laptop device. DirectShow enumerated REDRAGON at index 0; a bounded index-0 MSMF capture showed the same scene as the DirectShow capture. The private `webcam://school-demo-webcam` alias now uses index 0 with MSMF and displays `USB Webcam (REDRAGON Live Camera)`. The existing saved operational camera record uses this alias, so its stored `FOBOS MODEL GW600` name was left intact. MSMF with configured 640×480/30 preferences opened and decoded at index 0 with a capture timestamp; the startup deadline was raised to 15 seconds because this USB device took 7.9–9.5 seconds to open with those preferences. Each diagnostic capture released its child and device handle. Reconfirm the index after unplugging or reordering devices.

Detected: Windows enumerates `REDRAGON Live Camera` and `Integrated Camera`. The physical model name `FOBOS MODEL GW600` was supplied by the operator, but Windows does not expose that exact friendly name. The active alias now points to the external USB device at index 0.

Configured: **YES in private source registry** as `webcam://school-demo-webcam`. An operational camera record named `FOBOS MODEL GW600` now exists and uses this alias. Existing Bago and other records remain untouched.

Friendly source name: `USB Webcam (REDRAGON Live Camera)`. The saved camera record retains the operator label `FOBOS MODEL GW600`.

Device mapping: explicit local index 0. No arbitrary index, path, or backend is accepted from the public form.

Backend: MSMF. Resolution: 640×480. Reported FPS: 30; index-0 short probe observed about 33 FPS. Earlier index-1 FPS measurements applied to the wrong physical device.

Preview: **PASS in the earlier isolated pipeline**, but those seven frames came from index 1. Index 0 has now opened and decoded without inference or incident side effects. The USB-specific end-to-end monitor/analysis packet and visual Live Monitor switch still need validation.

## Shared Pipeline

RTSP: **PASS**. USB: **PASS in isolated physical validation**. Latest frame: **PASS for both**. Analyzed packet: **PASS for both**. A mocked detector received the real BGR frame at the camera's actual dimensions. This confirms input transport; it does not claim crash-detection accuracy.

## Security

Authorization: **PRESERVED**. The new source-list route returns 401 without a session and 403 to a viewer without the editor permission; its positive path returned only safe metadata in isolated tests. Saved camera creation, monitor start, status, JPEG, SSE, and packet retain their existing guards.

Credentials: **PRESERVED**. The Bago URL was checked without printing credentials. The temporary access log was sanitized of signed token query strings. The final backend runs with access logging disabled, preventing fresh token query strings in server logs.

Arbitrary source injection: **REJECTED** by the existing strict alias registry and saved-camera validation tests. The USB form only submits a server-provided configured alias.

## Unrelated Features

Operations Dashboard: **UNCHANGED**. Pending Review logic: **UNCHANGED**. Incidents: **UNCHANGED**. Detector: **UNCHANGED**. Tracking: **UNCHANGED**. Collision logic: **UNCHANGED**. Alarm: **UNCHANGED**. Database schema: **UNCHANGED**. No model, weight, threshold, pair, temporal, or incident decision code was edited in this task.

## Tests

- `npm run typecheck`: PASS.
- `node --test frontend-tests/live-monitor-restoration.test.ts frontend-tests/ui-contract.test.ts`: 11 passed.
- Isolated backend webcam, camera security/role, Live Monitor, Stage 1 and Stage 2 suite: 61 passed after making the Windows spawn test runner import-safe. One additional preview-endpoint test passed separately.
- Physical index 1 probe: DSHOW and MSMF decoded at 640×480; MSMF was faster. An initial bounded DSHOW probe returned unavailable under load; the probe tool now reports that result and continues to MSMF rather than aborting.
- USB correction: DirectShow listed `REDRAGON Live Camera` at index 0, and index-0 DSHOW/MSMF captures showed the same view. MSMF index 0 decoded at 640×480 with configured preferences and a capture timestamp. The current alias passed the isolated latest-frame, JPEG preview, detector-input, and analyzed-packet check with seven frames and incident persistence blocked. The previous index-1 validation must not be treated as external USB identity evidence.
- After the configuration change, the old webcam child was closed and the backend restarted; `/api/health` and the Live Monitor route both returned HTTP 200. The browser's authenticated USB preview after this restart was not independently observed.
- Isolated physical frame paths: Bago 20 frames at 1280×720; USB 7 frames at 640×480; both JPEG/packet paths passed. No operational incident was created by these checks.
- Live Bago path: one monitor-start HTTP 200, 179 latest-frame HTTP 200, 178 analyzed-packet HTTP 200, MJPEG HTTP 200, and dispatcher incidents HTTP 200 before access logging was disabled. See `backend/validation/connectivity_recovery_20261009/live-route-summary.json` and the sanitized validation logs.

## Diff Review

`git status`, `git diff --stat`, and `git diff` were run before and after. The original working tree contained 34 already-modified tracked files and many untracked earlier features. Those existing changes were preserved. Files edited for this task: `backend/main.py`, `backend/local_webcam_sources.json`, `backend/scripts/probe_local_webcams.py`, `backend/scripts/run_isolated_tests.py`, `backend/tests/test_local_webcam_pipeline.py`, `backend/validation/local_webcam_20261008/physical_pipeline.py`, `lib/api-client.ts`, `components/cctv-monitor-workspace.tsx`, and `components/live-camera.tsx`. This report and isolated validation logs were also added. No unrelated file was reverted or modified for this task. Full tracked-file status and diff are saved under `backend/validation/connectivity_recovery_20261009/`.

## Final Verdict

**CAMERA_SOURCE_SELECTION_READY_USB_VALIDATION_PENDING**

Bago preview delivery and the external USB frame path passed. The saved FOBOS camera now resolves to the `REDRAGON Live Camera` USB capture at MSMF index 0. The remaining validation is an authenticated user opening that saved camera in the operational Live Monitor and switching between Bago and USB after the backend restart. Reconfirm the device index after unplugging or reordering cameras.
