# Stage 2 — Fast Frame-Synchronized Bounding Boxes

## Scope

Stage 2 only, under implementation-plan A1/A5/A6/A9. Work began October 1 and validation continued October 2, 2026.

Allowlisted files: `backend/main.py`, `lib/types.ts`, `lib/api-client.ts`, `components/live-camera.tsx`, `components/cctv-video-overlay.tsx`, `components/cctv-monitor-workspace.tsx`, focused tests and new stage artifacts.

Modified existing files: the first five only. Workspace component needed no change. Added this requested report and [Stage 2 evidence](../backend/validation/live_cctv_implementation_stage2_20261001/). Existing unrelated edits were preserved. No commit/push; Stage 3 not started.

## Before Behavior

Native detector boxes passed through `response_boxes` → completed `latest_result` → status normalization → `pollCctvMonitor` → `applyDetectionResult` → `CctvVideoOverlay`. Stage 1 preserved `sourceFrame`, but rendering did not join it to pixels. Status polling at least every 2.5 seconds and a four-second hold reused boxes over independently advancing MJPEG. The normal dimension-based contain/cover transform did not solve that temporal mismatch.

## Implemented Box Pipeline

`LiveCameraMonitor._analyze_current_frame` publishes one latest analyzed-frame reference, copied native boxes, camera/session/sequence, host capture time, dimensions and inference timestamps immediately after existing model calls and ROI/scaling, before collision decisions/persistence. Classifier order is retained: publishing before it would change the detector execution path. No additional model calls or per-frame disk writes.

`latest_box_packet` lazily encodes that exact image outside capture/model locks. A separate visual encoder lock and one cached packet bound work. Current analyzed frame plus an older cached/in-flight reference can coexist; no archive/FIFO grows. A replacement or reconnect during encoding discards the packet.

Existing `/events?boxes_only=true` coalesces sequence notifications with a 100 ms wait. Existing default events/status behavior is retained. New read-only `/analysis-packet` returns image and boxes atomically, with `no-store`, using the same camera resolution/access guard. No new authentication scheme.

`subscribeCameraBoxes` uses existing cookie credentials and stream-event URL, one request in flight, one coalesced pending refresh, a two-second request timeout, and 250 ms fallback polling while SSE is unavailable. Cleanup aborts requests and rejects late responses. Duplicate/older sequence, retired epoch and changed camera identity cannot refresh a view. Retired-epoch memory is bounded to eight entries; transport is single-flight.

The CCTV analyzed preview replaces the old annotated thumbnail with a labeled exact-frame area below smooth video. Raw MJPEG receives no historical boxes. Device/upload display and incident/alarm consumers retain their existing paths. Visual packets contain no incident/confirmation fields.

## Frame Synchronization Rule

Render only the image and boxes contained in the same atomic `(cameraId, sessionId, sequence)` packet. Require finite positive native dimensions. A keyed image must finish decoding at those dimensions before its SVG boxes appear. Frame N boxes are never attached to raw preview N+K. New packets replace the whole analyzed view, including empty detections; old image-load callbacks cannot activate a new keyed frame.

Capture time means host decode/receipt time, not sensor exposure. The label shows sequence, capture time and estimated source age at delivery; it does not label the analyzed still as live video. Source age uses backend monotonic elapsed time plus conservative client request duration.

## Stale Box Policy

Server packets expire **500 ms after visual publication**, measured by `perf_counter`. Client deadline is `performance.now() + min(500, validForMs, 500-resultAgeMs) - requestDuration`. This is stricter than the plan's 500 ms post-receipt target and does not require synchronized wall clocks. A timer removes the entire analyzed view; decode and render also check the deadline. Duplicate fetches never extend it. Missing packets clear the view. At slow inference cadence, the panel can alternate between a frame and its waiting message; no motion prediction or long cosmetic hold is added. Browser suspension can delay timer execution; a rendered update always checks the deadline.

## Coordinate Mapping

Source resolution: actual packet dimensions, including tested **1280×720**; never inferred from box extents.

Display handling: the analyzed container preserves native aspect ratio; image and SVG share its full extent and `viewBox="0 0 width height"`, with centered `meet`. Native x/y/width/height remain native; resizing scales both together. Boxes are clipped to `[0,width] × [0,height]`; invalid/exterior boxes disappear. The existing contain/cover transform was extracted into a tested helper without changing its finite-dimension geometry. Tests cover native, 640×360, 320×180, 640×480 letterboxing and cover cropping. Browser pixels have not been visually inspected.

## Box Latency

Final [benchmark.json](../backend/validation/live_cctv_implementation_stage2_20261001/benchmark.json): serial 12-second before/after runs, 1280×720 synthetic black frames at 15 Hz, 250 ms fake inference, actual worker/preview/event generators and packet JPEG encoding. Empty detections, no YOLO, HTTP, RTSP, persistence or browser. CPU 100% means one core.

| Metric | Before | After | Evidence |
|---|---:|---:|---|
| Model-end → visual state available, median/p95 | 0.68 / 0.92 ms | 0.10 / 0.13 ms | 48 analyses each; no persistence delay in fixture |
| Model-end → consumer receipt, median/p95 | 203.45 / 230.34 ms | 48.89 / 103.23 ms | 4 status deliveries / 47 packet deliveries |
| Source age at consumer, median/p95 | 491.72 / 513.48 ms | 340.06 / 389.43 ms | Host receipt → in-process consumer |
| Consumer update rate | 0.33/s | 3.91/s | Not React render/paint rate |
| Capture FPS | 15.07 | 14.98 | Synthetic producer |
| Unique preview FPS | 14.90 | 14.40 | Actual MJPEG generator receipt |
| Preview age median/p95 | 69.32 / 77.35 ms | 71.02 / 76.98 ms | 180 preview deliveries each |
| Analysis cycles/s | 4.00 | 3.99 | Detector frequency unchanged |
| Process CPU | 7.02% | 7.54% | One-core convention |
| RSS start → end | 65.29 → 72.59 MiB | 69.32 → 79.98 MiB | Same process; not independent peaks |

Before polling sees only the newest result: its four samples omit most observations and must not be interpreted as a 230 ms guarantee for every result. Final preview rate remains above the synthetic 13.5 FPS target, with a 0.50 FPS decrease and small CPU/memory cost. Browser latency, render rate, moving-box IoU/jitter and multicamera/soak behavior are unmeasured.

An earlier run overlapped regression checks and measured after-preview 10.90 FPS; it is retained as `benchmark_concurrent_checks.json`, excluded from the isolated comparison because external load differed. This illustrates load sensitivity, not a demonstrated full-load guarantee.

## Visual Alignment

**NOT VERIFIED** visually. Deterministic synthetic packet/geometry/render-gate tests pass, but no moving-vehicle browser or physical camera check was completed. The browser skill's runtime initialization failed with `codex/sandbox-state-meta: missing field sandboxPolicy`, before navigation. No collision media or Source B replay was shown.

**LIVE_BOX_ALIGNMENT_NOT_PHYSICALLY_VALIDATED**.

## Tests

Reproducible commands and logs: `final_checks.py`, `checks.json` in the evidence directory.

Backend: **167 passed**, plus one existing expected failure: 48 focused tests comprise 47 passes/one expected failure; broader isolated regressions add 120 passes. Nine new Stage 2 tests cover packet pixels/provenance, source changes, expiry, replacement during encoding, early publication/empty results, notification isolation, preview independence and camera-access guard reuse. Models/persistence are mocked; broader tests use disposable SQLite, not operational PostgreSQL.

Frontend: **27 passed**: eight new executed TypeScript/TSX tests plus 19 existing live/incident/alarm/API-fetch tests. New tests exercise subscription ordering, bounded single-flight behavior, cleanup, expiry budget, reconnect, clipping, contain/cover geometry, native SVG mapping, image-load gating and timer removal through a deterministic hook harness. This harness is not a browser renderer.

TypeScript: **PASS**, `tsc --noEmit --incremental false`. Scoped `git diff --check`: PASS. Known direct pair-safety assertion exits 1 as expected.

## Stage 1 Regression

Frame freshness: **PASS**. Latest-frame behavior: **PASS**. All 12 Stage 1 tests pass, including slow inference/preview, duplicate admission, epochs, bounded cache and collision-output comparisons. Capture, preview, detection scheduling and analysis admission methods are unchanged by AST comparison.

## Collision Safety

Collision logic changed: **NO**. Pair ownership changed: **NO**. Known pair-safety regression: **FAIL**. Expected: **FAIL**. No safety assertion was weakened.

`semantic-protection.json` verifies that removing only the new visual publication/timestamp statements leaves the entire analysis AST identical to the pre-stage snapshot. The other 153 existing top-level definitions, excluding the scoped live class/events route, are unchanged. Visualization has no route back to hit history, model admission, incident creation or alarm delivery.

Protection audit: **15,527 pre-existing files checked; exactly five allowed files changed; zero missing or unexpected changes**. This includes existing model/evaluation/training evidence and Stage 1 artifacts. Operational database contents were not part of this file inventory; tests used isolated storage/mocked persistence. The requested report was added after inventory enumeration. Task-specific `stage2.patch` distinguishes these edits from the extensive pre-existing working-tree changes; full `git diff --stat` and `git diff` were saved and reviewed. Hash results are in `protection.json`.

## Detector

Model: **UNCHANGED**. Thresholds: **UNCHANGED**. Acceptance: **UNCHANGED**. No training, tracker, ID assignment, classifier/proximity/geometry or model-order changes.

## Alarm

**UNCHANGED**. Candidate/aftermath/duplicate silence and fresh-confirmed one-shot behavior pass existing compatibility tests. No audible browser test or operational incident was created.

## Remaining Limitations

Vehicle recall still unresolved; domain detector improvement still pending; persistent tracking not implemented; pair ownership not fixed; interaction verification not integrated; collision safety not yet resolved. Physical alignment and browser/HTTP latency remain unverified. Synthetic black-frame JPEG cost does not establish busy-traffic bandwidth or multicamera capacity. Low inference cadence causes deliberate expiry gaps. Existing status/incident polling remains separate and retains its prior behavior.

## Stage 2 Verdict

**STAGE2_ALIGNMENT_UNVERIFIED**

The implemented packet/expiry/coordinate pipeline and scoped deterministic regressions pass. Physical/browser alignment and end-to-end display latency remain unvalidated, so no complete visual readiness claim is made. Stop before Stage 3.

STAGE 2 IMPLEMENTATION COMPLETE — SEND RESULTS BEFORE STAGE 3
