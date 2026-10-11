# Local Webcam Camera Source Audit

Date: 2026-10-08. Audit only; current working tree is authoritative.

## Executive Summary

The smallest safe extension is a typed backend source adapter, with a webcam alias stored in existing camera source-reference fields and resolved through private, explicit local-device configuration. Existing RTSP records keep their current behavior. Camera API validation must accept configured aliases in saved-camera contexts; no database migration or Live Monitor change is required for this approach.

The installed backend venv reports OpenCV **4.13.0**, with **DSHOW and MSMF available**. This establishes software support, not successful physical-device capture. No webcam/network camera was opened, frames persisted, models run, records changed, incidents created, or tests rerun. Only this report was added; existing uncommitted work was preserved.

Reviewed the requested October 1 audit/implementation plan and Stage 1, 2, 2C, 2D and 2E reports. Preserve their completed freshness, exact-frame packet, retention and compact-inspector work. Historical validation results are not fresh results from this audit.

## Current RTSP Camera Architecture

References are relative to this report; function names are the primary anchors.

| Step | Exact code | Current contract / constraint |
|---|---|---|
| Saved record | [repositories/crash_cases.py](../backend/repositories/crash_cases.py): `upsert_camera`, `get_camera`, `list_cameras`, `_sync_camera_to_postgres` | Operational reads use SQLite camelCase records; source is `cameraIp` or `streamUrl`. Sync writes PostgreSQL `stream_reference` under `legacy_id`; missing URLs can be reconciled from PostgreSQL. This is more specific than the older in-memory summary. |
| Storage | [schema.sql](../backend/schema.sql): `cameras`; [0001 migration](../backend/migrations/versions/0001_phase3_operational_schema.py): `cameras` | SQLite has nullable TEXT `streamUrl`, `cameraIp`, `cameraType`; PostgreSQL has TEXT `stream_reference`. No structured webcam fields exist. |
| CRUD | [main.py](../backend/main.py): `CameraRecordIn`, `validate_camera_record_payload`, `camera_record_payload`, `api_create_camera`, `api_update_camera` | Requires IP or URL. IP must be IPv4; URL uses network/demo validation. `cameraType` is descriptive, not a capture discriminator. |
| Resolution | `main.py`: `resolve_saved_camera_stream`, `build_tapo_rtsp_url` | IP takes precedence and uses configured Tapo credentials, port and stream path. Otherwise validates stored URL. Returns `(str, optional IP)`. |
| Initial frame | `main.py`: `api_start_camera_monitor`, `grab_frame_from_stream_url` | Authorization and active/detection gates precede resolution. Initial grab runs off-thread; failure is swallowed and worker still starts. Network reachability check precedes FFmpeg open. |
| Worker selection | `main.py`: `live_camera_worker_keys`, `live_camera_primary_key`, `start_live_camera_monitor`, `monitor_for_camera` | Process-local aliases: camera ID, IP, URL hash and label. Existing running matching URL is reused. Source string is assumed throughout. |
| Continuous capture | `main.py`: `LiveCameraMonitor._capture_loop` | `demo://` is synthetic. Other sources use `cap.open(str, CAP_FFMPEG, open/read timeouts, one decoder thread)` and RTSP options. Repeated `read()` replaces one native frame slot. |
| Preview | `main.py`: `latest_jpeg`, `latest_preview_packet`, `mjpeg_stream` | Sequence-keyed JPEG cache and independent preview pacing; `/latest-frame.jpg` and `/preview.mjpeg` consume it. |
| Analysis | `main.py`: `_detection_loop`, `analyze_current_frame`, `_analyze_current_frame` | Separate thread, new-frame event, nonblocking analysis/model admission; pins metadata and copies the newest BGR frame outside capture lock. |
| Packet | `main.py`: `_analyze_current_frame`, `latest_box_packet`, `detection_events`, `api_live_camera_analysis_packet` | One exact analyzed frame, boxes and provenance; JPEG encoded outside capture/model locks. Packet expires 500 ms after publication and rejects retired sessions. |

Existing RTSP is not the only supported source: HTTP(S) and demo sources also exist. Do not collapse these into an RTSP-only rewrite. No existing production opener accepts a numeric webcam through this saved-camera path: URL parsing/validation, socket probing, string assumptions and forced FFmpeg prevent it. The frame consumers already accept native NumPy BGR arrays regardless of origin.

## Webcam Feasibility

Backend-local USB/integrated capture is technically supported by the installed OpenCV build. The webcam must be attached to the **computer running FastAPI**, not a remote operator's browser. Browser `getUserMedia` in `components/live-camera.tsx` is a separate existing upload/detection path and is not the proposed CCTV source.

Hardware index, driver access, Windows camera privacy permission, service-session behavior, exclusive access, negotiated resolution/FPS and disconnect behavior remain unverified. Do not claim physical webcam readiness before Stage D.

## Recommended Source Abstraction

Add a narrow `CameraSourceSpec`/opener in future `backend/services/camera_sources.py`:

- Network source: existing validated URL and unchanged FFmpeg settings.
- Demo source: existing synthetic behavior.
- Webcam source: configured opaque alias, integer index, tested backend enum and optional preferred width/height/FPS.

Persist only a strict reference such as `webcam://desk-camera` in existing `streamUrl`/`stream_reference`. Resolve it to an operator-owned private configuration entry with `source_type=webcam`, `device_index`, friendly name, `backend` (`dshow`/`msmf`, selected after testing), and optional preferences. No credentials. Do not use `cameraIp`, fake RTSP credentials, numeric strings, or `cameraType` as the authoritative device selector.

The alias parser must require the exact grammar and membership in the configured allowlist. Reject userinfo, ports, paths, query/fragment, unknown aliases and all raw device/OpenCV strings. Pass **only the resolved integer** to the webcam opener; never pass the reference string to OpenCV. Keep `validate_stream_url` network/demo-only for arbitrary-input routes; introduce a saved-source validator rather than globally admitting webcams.

Structured API fields/DB columns are an optional larger alternative, not necessary for this bounded extension. Existing text references already carry source identity and round-trip through both stores. A private registry avoids overloading text references with hardware options.

## Windows/OpenCV Device Access

Read-only command used: backend venv Python imported `cv2`, queried `videoio_registry.getCameraBackends()/hasBackend`, and printed relevant `getBuildInformation()` lines. Results: DSHOW=700 available; MSMF=1400 available; FFmpeg available; DirectShow and Media Foundation build flags YES. No `VideoCapture` instance was created.

OpenCV supports an integer camera index with an explicit API preference; properties and backend support vary. Its open/read timeout properties are documented for FFmpeg/GStreamer, so current network timeouts must not be assumed to bound Windows webcam calls. See official [VideoCapture API](https://docs.opencv.org/4.13.0/d8/dfe/classcv_1_1VideoCapture.html) and [video I/O flags/properties](https://docs.opencv.org/4.13.0/d4/d15/group__videoio__flags__base.html).

Future diagnostic: operator supplies a small finite candidate-index list; probe each serially with DSHOW and MSMF, optionally CAP_ANY as a comparator. A bounded index probe is not reliable friendly-name/device enumeration; pair results with a local Windows device inventory when needed. No URL probing or automatic network discovery. Run each probe in a disposable child process with a hard deadline (e.g. 10 s); release on every path, terminate/join on timeout. Read only a bounded warm-up/sample window; report actual backend, dimensions, reported/measured FPS, first-frame delay, read failures and age. Discard frames; no display/save/model/DB work. Choose backend from these results, not convention. Device index 0 is not assumed; indices may change after reconnect/restart and are backend-specific.

## Frame Pipeline Compatibility

| Existing field/path | Webcam requirement |
|---|---|
| `latest_frame` | Publish owned, nonempty native BGR arrays by replacement under existing lock; no FIFO. |
| `sourceFrame.cameraId` | Same saved safe camera ID; no alias/index/path as fallback identity. |
| `sourceFrame.sessionId` | Renew opaque epoch on each successful connection; preserve epoch attached to old pixels. |
| `sourceFrame.sequence` | Increment for each successfully published frame, never reset within worker. Monotonic per session; may continue across reconnect as today. |
| `capturedAt`, `capturedMonotonic` | Host successful-read completion/receipt time, not sensor exposure, inference or browser time. |
| JPEG/preview | Reuse `latest_jpeg`, `latest_preview_packet`, `mjpeg_stream`, actual dimensions and existing ceiling. |
| Inference/packet | Reuse unchanged analysis admission, BGR detector input, exact-frame boxes and `latest_box_packet`. |

New worker after restart receives a new epoch; sequence restart is then valid. `latest_box_packet` already rejects old-session results. Reconnection creates presentation identity, not automatic reset of collision history: current `hit_window` is worker-owned and is not cleared on RTSP reconnect. Preserve and explicitly test that behavior; do not quietly change downstream semantics under this task.

## Camera Management Compatibility

Register through existing permission-protected legacy camera CRUD with `cameraIp=null`, `streamUrl=webcam://<configured-alias>`, ordinary camera ID/name/area/location and descriptive `cameraType=Local Webcam`. An administrator can use the API without new UI controls. Configure hardware options separately on the backend host; do not auto-register discovered devices. Retain normal active/detection gates and camera selection.

`camera_client_payload` needs a webcam-friendly label branch; keep `streamConfigured=true` and hide stored reference/device details. Existing public types already allow optional IP and URL plus source label, so no new frontend field is required. Existing management dialogs accept RTSP/IP only: UI webcam onboarding would be separately scoped, **FRONTEND_DEPENDENCY_REQUIRED** if later requested, not required for backend/API registration now.

PostgreSQL-only Phase 3 `routes.py::CameraIn` and `service.py::upsert_camera` already accept a text `streamReference` but do not create a legacy operational record. Do not claim PG-only creation automatically yields a Live Monitor camera. Use the existing legacy path and its sync; test unchanged alias persistence, reconciliation and update-with-omitted-source. If PG management accepts webcam references, validate them with the same registry, without changing its permissions.

## Live Monitor Impact

**NONE. LIVE_MONITOR_CHANGE_REQUIRED: NO.**

`components/cctv-monitor-workspace.tsx` computes auto-start eligibility from a saved `cameraId`; `components/live-camera.tsx::startIpCctvMonitor` uses `startCctvMonitoring(savedCameraId)` when present. `lib/api-client.ts::startCctvMonitoring`, `createCameraStreamAccess`, `subscribeCameraBoxes` address the saved ID and backend preview/events/packet URLs. `lib/types.ts::CctvCamera`, `LiveFrameIdentity`, `LiveBoxPacket` need no extension for rendering an API-registered webcam.

Keep raw preview, cards, navigation, compact analyzed inspector, native box mapping, 500 ms server packet freshness and up-to-5000 ms frontend inspection retention unchanged. No source controls, browser capture replacement or frontend implementation is planned. Zero-change feasibility is established by code inspection; physical browser behavior remains a Stage D check.

## Security / Privacy

Keep `require_camera_editor`, `require_camera_access`, `require_camera_stream_access`, camera-bound stream tokens, `can_access_camera`, and current saved-camera permissions unchanged. Current `can_access_camera` requires both view and monitor permissions; it does not enforce a separate per-record/area ACL. Do not claim stronger isolation or redesign RBAC here.

Only locally configured aliases may resolve; camera editors cannot select arbitrary indices/backends/paths through public payloads. No public device enumeration API. Require a saved authorized camera before local capture, including connection tests; never extend unsaved raw URL/IP endpoints into device access. Preserve network-host validation and RTSP credential redaction in `camera_privacy.py::public_camera_data/redact_camera_text`.

Public responses/errors contain camera ID, friendly name and bounded availability status; no device paths, registry contents or credentials. Source config stays operator-owned/server-side. Existing inference can save incident evidence when a real monitor runs; webcam-origin evidence follows existing rules. The feasibility diagnostic bypasses inference entirely and stores nothing.

## Device Reconnect Behavior

Current `_capture_loop` retries for the lifetime of `running` (2 s failed-open sleep; 1 s after read-loop exit). `stop()` sets events but does not join threads; `release()` happens in capture `finally`. `LIVE_CAMERA_WORKERS_LOCK` protects only a process-local map, not hardware across Uvicorn processes. Initial grabs/connection tests/one-shot detection can create additional independent captures. Repeated start also performs its preflight before checking worker reuse.

For webcam sources only: one owner per physical configured device, including aliases; reject a second camera registration/start for that device rather than returning another camera's worker. Keep ownership until capture is released and worker joined. Use a Windows named mutex or equivalent cross-process lease in the source adapter; a busy device returns a generic unavailable/busy status and no frames. Do not infer exclusive access from a successful open.

Skip webcam preflight opening on monitor start: the worker alone opens it. Saved connection tests use the active owner's latest frame or a serialized short lease when stopped. `detect_stream_frame`/`_detect_stream_frame_sync` also need a webcam acquisition branch, preserving their existing one-shot detector call and authorization rather than opening a second device. The normal Live Monitor continues using its worker pipeline.

Plan finite webcam retries, e.g. five failed attempts with stop-interruptible 1/2/4/8 s backoff, then release and expose existing `connection-lost`/OFFLINE status until explicit restart. Report success only after a valid read. Unplug/no frame triggers this same bounded cycle; successful reconnection renews epoch and increments reconnect metrics. Old preview pixels must remain accurately aged/stale, never relabeled as new frames. Preserve RTSP retry behavior.

A Python thread cannot guarantee interruption of a blocked native driver read. Stage D must establish a stop/release bound; if not met, stop release and scope a supervised capture child with one shared latest-frame slot (no queue), or reject that backend/device. A diagnostic child timeout alone does not prove production teardown. App restart releases OS resources and requires ordinary monitor start; no webcam auto-open at import/startup. Source ownership changes must not reset detector/collision state implicitly.

## Performance Considerations

Preserve Stage 1 independent capture/preview/inference, latest-slot overwrite, bounded caches and histories, no frame backlog, nonblocking model admission and existing YOLO cadence. Do not reuse FFmpeg-specific decoder-thread/timeout settings for webcam adapters or claim `CAP_PROP_BUFFERSIZE` guarantees low driver latency.

Future measurements at declared resolution/backend and one plus intended mixed-source load: receive FPS, unique JPEG/browser preview FPS, reported FPS, frame-age median/p95, inference input/completion age, analysis cadence, process/host CPU and RSS. Existing `capture_timestamps`, `preview_timestamps`, `ai_timestamps`, `inference_frame_age_ms` and snapshot metrics provide much of this. Preview counters measure encodes, not browser painting.

Proposed gates: receive >=95% of independently measured delivered device FPS; preview >=90% of min(measured receive FPS, unchanged configured preview ceiling); inference input-age median/p95 <=75/150 ms, subject to measured hardware feasibility; decode-to-browser age <=100/200 ms when instrumented. Compare matched RTSP baselines for regressions. A 30 FPS webcam need not produce 30 FPS preview when current ceiling is 15. Record CPU/RSS under a 30-minute soak and show no persistent growth; do not promise a numeric CPU budget without baseline. No cadence/model/threshold tuning to pass these gates.

## Downstream Detector Compatibility

`main.py::LiveCameraMonitor._analyze_current_frame` consumes copied native BGR arrays, runs quality analysis, `model.predict(..., imgsz=640)`, scene classification, `detect_vehicle_boxes`, ROI filtering and native box scaling. It does not require RTSP metadata. Webcam can enter unchanged. Color layout, nonempty dimensions and no implicit mirroring/cropping/resizing are adapter gates; preferences are negotiated and actual dimensions remain authoritative. Detection quality on a webcam view is unmeasured.

## Downstream Collision Compatibility

Current live analysis uses `crash_like_vehicle_interaction`, worker `hit_window`, existing consecutive-hit/window gates, `evaluate_crash_case_decision`, persistence and alert behavior independently of transport. Feed the same pixels/metadata through this path without changing it.

`services/vehicle_tracking.py::VehicleTrackingService`, `temporal_crash_verifier.py::TemporalCrashVerifier`, and `pair_hit_ledger.py::PairHitLedger` exist but are not wired into this current live worker. Adding webcam must not wire them in or claim safe same-pair confirmation. Reviewed reports identify the distinct-physical-pair safety regression; this audit did not rerun or fix it. Reuse means compatibility with existing behavior, not proof of collision accuracy. Protect 3 hits, 5-second window, pair ownership, classifier/thresholds, confirmed-crash/aftermath semantics and alarms.

## Required Schema/API Changes

| Required declaration | Verdict | Reason |
|---|---|---|
| SCHEMA_CHANGE_REQUIRED | **NO** | Existing TEXT references hold strict opaque aliases; hardware options live in private config. |
| CAMERA_API_CHANGE_REQUIRED | **YES** | Saved-camera source validation/resolution, public label, start/test acquisition and source-specific errors must recognize configured webcam aliases. Existing payload fields suffice. |
| LIVE_MONITOR_CHANGE_REQUIRED | **NO** | Saved ID, status, JPEG, events and analysis packet contracts remain compatible. |

No migration is authorized. Preserve current RTSP precedence/credentials and camera response shapes. Phase 3 validation is a direct source dependency only; SQL/RBAC are protected.

## Test Plan

Future tests use mocked capture and isolated storage; hardware tests never reuse operational camera records or create real incidents.

| Cases | Required assertions |
|---|---|
| A RTSP | Same URL/FFmpeg options, credentials, timeouts, one-thread decoder and open/read/release behavior. |
| B/C webcam / wrong index | Allowlisted alias resolves to exact configured integer/tested backend; wrong configured index fails within attempt/time budget. |
| D unavailable | No valid frame => offline/unavailable; no false connected result or busy retry storm. |
| E/F reconnect / sequences | New epoch on successful reconnect; sequence increases within worker/session; old pixels retain old epoch and old packet is rejected. |
| G/H latest slot / preview | Native frame reaches slot; overwrites during slow inference; JPEG and headers identify exact same captured frame; stop and cache bounds hold. |
| I/J detector / packet | Same BGR input reaches mocked detector; exact identity/image/box/dimension packet, empty detections and 500 ms expiry unchanged. |
| K authorization | Unauthorized CRUD/start/test/status/JPEG/MJPEG/events/packet denied before device open; wrong-camera/expired tokens denied. |
| L arbitrary sources | Reject numeric strings, negative/huge index payloads, paths, unknown aliases, decorated aliases and raw webcam URLs on unsaved routes. |
| M privacy | RTSP redaction unchanged; no registry/device paths or connection secrets in payloads/errors/logs. |
| N Live Monitor | API-registered source lists/selects/starts in unchanged UI; raw preview, exact boxes, fresh/stale/expiry and source switching work. |
| O collision/alarm | Identical controlled input sequences produce identical decisions/persistence/alarm eligibility; preserve known pair-safety assertion/expected failure. |
| Ownership/lifecycle | Repeat start/tests do not reopen active device; duplicate aliases/camera IDs, concurrent process lease, busy external app, unplug/replug, stop/restart and blocked read handled within declared bounds. |
| Storage compatibility | Legacy CRUD plus PG sync/reconcile retains alias; omitted-source update retains it; RTSP records unchanged; no schema changes. |

Reuse read-only Stage 1 `test_stage1.py`, Stage 2 `test_stage2.py`, camera security/health/role tests and frontend restoration/packet-retention/alarm suites. Do not edit protected Stage 1-4 evidence. Mock persistence in semantic tests; physical validation must disable/mock incident side effects. No new tests were written or run in this audit.

## Minimal Implementation Plan

| Stage | Files / exact purpose | Tests and success gate | Rollback condition |
|---|---|---|---|
| A Source adapter | New `backend/services/camera_sources.py`; narrow `main.py` resolver/worker-opening seams. Typed network/demo/webcam descriptor; isolate network-specific options. | Mock existing RTSP/demo source resolution/opening; unchanged frame consumers and network options. | Any RTSP behavior, detector, permission or response-contract drift. |
| B Webcam capture | Adapter and narrow `LiveCameraMonitor` capture/lifecycle seams; new private `backend/local_webcam_sources.json` when later configured. Integer opener, backend preferences, one-device ownership, finite retries and stop/release. | Fake-device publish/reconnect/busy/timeout tests; native latest slot and correct epoch; no second opener or queue. | Unbounded native call/retry, unreleased device, wrong provenance, capture blocked by inference. |
| C Registration compatibility | `main.py` saved-camera validator/payload/start/test/one-shot acquisition; `phase3/service.py` shared source validation only if webcam references accepted there. Existing fields/storage; friendly public label. | Isolated CRUD/store-sync round-trip, authorization/alias rejection/redaction; unchanged frontend consumes saved ID. | Schema migration needed, unsafe alias access, credential exposure or required Live Monitor edit. |
| D Tests + local validation | New focused tests, optional `backend/scripts/probe_local_webcams.py`, new validation docs/results. Diagnostic first, then isolated integration using actual selected device. | Bounded DSHOW/MSMF comparison, RTSP+webcam regression, A-O, browser validation and resource soak; record chosen backend/index/actual settings. | No backend meets read/stop bounds, physical/browser failure, RTSP/performance/semantic regression. Keep RTSP available and webcam unregistered/disabled. |

Implement only after a subsequent explicit implementation request. Stage A is a small prerequisite within the API extension, not a detector/collision architecture rewrite. Rollback removes webcam references/enablement and adapter branches while preserving existing RTSP records and all protected work.

## Future Webcam Change Allowlist

File membership permits only the stated scope:

- `backend/main.py`: camera-source models/validation/resolution, public source label, worker source-opening/ownership/lifecycle and saved acquisition branches. Analysis/detector/collision/alarm bodies protected.
- New `backend/services/camera_sources.py`: typed descriptors, strict alias registry, network/webcam openers, ownership and bounded source retries.
- New private `backend/local_webcam_sources.json`: explicit local source metadata only; no credentials/operational records.
- `backend/phase3/service.py`: shared validation of webcam source references only if exposed through that camera-management API; no SQL, permission or workflow changes.
- New `backend/scripts/probe_local_webcams.py`: bounded local-only, frame-discarding diagnostic.
- New `backend/tests/test_local_webcam_sources.py` and `backend/tests/test_local_webcam_pipeline.py`: focused source/security/lifecycle/storage regressions with isolated dependencies.
- New `docs/local-webcam-*.md` and a new webcam-only validation results directory: implementation/diagnostic evidence; never overwrite old evidence.

Repositories, schemas, migrations, privacy module, frontend/types/API client and existing evidence are read-only dependencies, not proposed edit targets. If an implementation later proves another dependency necessary, report it before expanding scope.

## Protected / Do Not Change

All Live Monitor pages/components/layout/cards/inspector/navigation/styling/boxes/alarm controls; Operations Dashboard; New Alerts; Pending Review; Active Incidents; Responders; Incident Map/History; Notifications; Settings/Profile/Response History UI; authentication, password handling and role permissions; PostgreSQL/SQLite schemas; incident API semantics; dispatcher/responder workflows; vehicle detector, weights, preprocessing/thresholds/cadence; tracking, PairHitLedger, pair ownership/interaction/collision/classifier rules; 3-hit and 5-second gates; confirmed-crash/aftermath behavior; alarm/Arm Siren/audio; Source B, Phase 8C, training data, Stage 1-4 validation evidence and source manifests/licenses.

Anything outside the future webcam allowlist is OUT OF SCOPE. Audit changed no production/frontend/config/schema/data files; the requested report is the sole authored artifact.

## Audit Verdict

**WEBCAM_SOURCE_REQUIRES_SMALL_CAMERA_API_CHANGE**

The recommended alias-backed source adapter can reuse existing storage, frame processing and Live Monitor contracts. Windows capture support is present; physical backend/device selection and lifecycle/performance gates remain for future validation. No implementation has been performed.
