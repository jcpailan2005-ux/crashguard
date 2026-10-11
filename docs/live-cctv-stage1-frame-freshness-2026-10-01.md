# Stage 1 — Frame Freshness and Synchronization

## Scope

Implemented infrastructure only under the [implementation plan](live-cctv-collision-implementation-plan-2026-10-01.md), Stage 1 / allowlist A1, A5 and A9. Existing successful work was retained during continuation; Stage 2 was not started.

Allowlisted files: `backend/main.py` live capture/preview/provenance functions; optional shared contracts in `lib/types.ts` and `lib/api-client.ts`; focused tests and new validation outputs. A2 execution/diagnostic services were permitted but needed no edits.

Modified existing files: **exactly those three production/shared files**. No frontend rendering changes. New validation/report files: this report and [Stage 1 artifacts](../backend/validation/live_cctv_implementation_stage1_20261001/): `test_stage1.py`, `benchmark.py`, `run_regressions.py`, `final_checks.py`, `verify_protection.py`, before-file snapshots, protection manifests, task-specific/full review patches, benchmark JSONs and test logs.

The repository already contained extensive unrelated edits. `git diff --stat` and `git diff` were reviewed; [stage1.patch](../backend/validation/live_cctv_implementation_stage1_20261001/stage1.patch) isolates this task against the pre-edit working tree, rather than attributing all changes since HEAD to Stage 1. No commit/push.

## Before Architecture

RTSP capture already overwrote one native frame slot. Separate capture/detection threads, a new-frame event, per-camera analysis lock and global nonblocking model lock already bounded work. JPEG encoding ran outside the capture lock. Inference copied pixels inside that lock; result JSON lacked explicit source identity. Preview used a default 10 FPS ceiling plus an after-work sleep.

## Implemented Architecture

Retained that architecture. Added frame/session provenance and timing; moved the inference copy outside the capture lock; preserved one sequence-keyed JPEG cache. Preview uses monotonic high-resolution deadlines, default ceiling **15 FPS**, capped by valid reported source FPS. Explicit configured ceilings remain honored. Quality, resolution, codecs and RTSP transport/options are unchanged.

## Frame Identity

- **camera_id:** `sourceFrame.cameraId` uses the saved safe camera ID; an unsaved/invalid-ID source gets an opaque `live-…` worker ID. Credentials and stream URLs are never identity fallbacks. Operational camera IDs are unchanged.
- **frame_sequence_id:** `sourceFrame.sequence` increases on each published frame, never resets within a worker, and is not derived from pixels.
- **capture_timestamp:** `capturedAt` is host frame-receipt/decode-completion time in UTC epoch seconds, captured before publication/copy—not inference completion or sensor exposure time. `capturedMonotonic` supports local age measurement.
- **session identity:** `sessionId` is an opaque epoch created at worker initialization and renewed on successful RTSP connection. Old pixels/results retain their old epoch during reconnection; sequence numbers continue increasing.

## Latest-Frame Behavior

Capture replaces the slot; inference pins the newest available array and its metadata after acquiring the existing model gate. Intermediate frames are intentionally skipped, counted by `framesSkippedBeforeInference`. Repeated analysis of the same sequence remains rejected. No frame FIFO, inference task backlog or new worker pool was introduced.

The deterministic blocked-inference test captures frame 1, publishes through frame 11, then verifies result 1 still identifies frame 1 and the next inference consumes frame 11, accounting for nine skipped intermediate frames.

## Capture Locking

The lock pins references/metadata only. The owned inference copy runs afterward, and its source reference is released after copying. Seed copies also occur before publication. Capture publishes owned arrays by replacement; consumers do not mutate the slot. JPEG encoding, model/classifier calls, serialization, network sends and evidence persistence remain outside the capture lock.

## Preview Independence

Preview consumes the native slot independently of inference. Cached JPEG bytes retain their sequence, camera/session and decode time in HTTP headers. Deadlines include encoding time; slow consumers resume from the latest slot without catch-up queues. Empty-frame retries wait; stop interrupts waiting. Repeated source frames retain the same identity, not a fabricated new observation.

The initial revised pacing used a coarse local clock and missed the source-relative target. Local `get_clock_info` reported `GetTickCount64` resolution **15.625 ms**, versus `QueryPerformanceCounter` **0.0001 ms**. Final pacing uses the latter through `perf_counter`. The initial benchmark is retained separately.

## Inference Independence

Existing nonblocking analysis/model locks remain unchanged. Busy admission does not queue a stale frame or launch overlapping model calls. Capture and JPEG preview continue during blocked inference. Model calls, thresholds, decision order and persistence behavior are unchanged; this stage does not shorten the global lock around persistence or integrate fair scheduling.

## Synchronization Metadata

Optional result fields: `sourceFrame` (camera/session/sequence, capture clocks, native dimensions), `inferenceStartedAt`, `inferenceFinishedAt`, `modelProcessingMs`, `inferenceSourceAgeAtCompletionMs`. Start/finish fields bound the analysis invocation; `modelProcessingMs` measures the serial primary/classifier/vehicle stage separately from whole-analysis duration.

Status adds `latestFrameIdentity`, source-reported FPS, model/completion/copy timings and skipped count. Existing bounded FPS histories remain; preview FPS measures encoding, **not browser painting**. Preview and inference age diagnostics use monotonic elapsed time where available. Existing collision clocks/gates are untouched.

Shared TypeScript fields are optional; existing response normalizers preserve them through object spreads. A result from frame N never substitutes the current N+K identity. **Frontend box synchronization/rendering remains unchanged**: metadata enables Stage 2 but does not repair the current overlay mismatch.

## Performance

Synthetic worker benchmark: **YES**. Live RTSP benchmark: **NO**. Browser-display benchmark: **NO**.

Paired final [benchmark.json](../backend/validation/live_cctv_implementation_stage1_20261001/benchmark.json): serial 12-second runs, native 1280×720 synthetic producer at 15 Hz, actual worker/JPEG generator, fixed 250 ms fake inference. No camera, YOLO, browser, collision media or operational persistence. After-measurement sample counts: 180 preview deliveries and 48 analyses; before: 112 and 48. Subsequent metadata-ID hardening/reference release was covered by deterministic checks, not another performance run.

| Metric | Before | After | Evidence |
|---|---:|---:|---|
| Capture FPS | 15.07 | 14.99 | SYNTHETIC |
| Unique preview FPS | 9.33 | 14.99 | SYNTHETIC generator receipt |
| Analysis cycles/sec | 4.00 | 4.00 | SYNTHETIC |
| Preview age median / p95 | 39.08 / 69.81 ms | 72.09 / 74.38 ms | SYNTHETIC decode→generator receipt |
| Inference source age median / p95 | 31.68 / 57.23 ms | 31.00 / 63.00 ms | SYNTHETIC |
| Fake model latency median / p95 | 250.40 / 250.66 ms | 250.41 / 250.61 ms | SYNTHETIC sleep; **not YOLO latency** |
| Whole analysis median / p95 | 250.79 / 251.47 ms | 252.44 / 253.42 ms | SYNTHETIC |
| Process CPU, 100%=one core | 8.72% | 13.15% | SYNTHETIC process CPU time |
| RSS start→end | 66.41→72.78 MiB | 69.30→74.45 MiB | SYNTHETIC same process; not independent peaks |
| Intermediate frames skipped | 132 of 181 published | 131 of 180 published | SYNTHETIC; no frame queue |

The earlier 9.41 FPS baseline belongs to `benchmark_initial.json`; it is not mixed into this final paired comparison. Actual detector latency is unmeasured here.

**LIVE_RTSP_PERFORMANCE_NOT_VALIDATED_IN_STAGE1**. Camera availability was not probed. No browser-display performance claim is made.

## Performance Tradeoffs

Preview FPS improved **9.33→14.99**; capture/inference rates were effectively unchanged. Preview median age increased **39.08→72.09 ms**, p95 **69.81→74.38 ms**. CPU increased **8.72→13.15% of one core** as more JPEG frames were delivered; RSS endpoints also increased.

The plan's Performance Gates specify decode→paint median/p95 **≤100/200 ms** and ≥90% source preview rate. Synthetic receipt ages are below those numeric budgets and synthetic rate meets the source-relative target, but **receipt is not paint**: the end-to-end browser gates remain unvalidated. These short runs establish bounded observed behavior, not a multicamera/30-minute soak or live CPU/memory guarantee. No preview quality reduction or collision-correctness tradeoff was used.

## Tests

Final commands and statuses are reproducible through `final_checks.py`; [checks.json](../backend/validation/live_cctv_implementation_stage1_20261001/checks.json) records process exits.

- **Stage 1:** 12 deterministic tests passed, including exact provenance, overwrite/skips, capture/preview under slow inference, copy outside lock, cache pinning, reconnect, clock jump, credential exclusion, bounded model admission, deadline pacing and five before/after collision-output scenarios.
- **Backend focused combined:** 39 run = **38 passed + 1 existing expected pair-safety failure** (includes the 12 Stage 1 tests, diagnostics and ledger suites).
- **Backend broader:** **120 passed**, covering preview, restoration, camera performance/health/security/permissions, API contracts, crash decisions and aftermath behavior. Disposable SQLite; operational PostgreSQL not used.
- **Frontend:** **19 passed**, existing API-fetch and incident/dispatcher/alarm/restoration contracts.
- **TypeScript:** **PASS**, `node node_modules/typescript/bin/tsc --noEmit --incremental false`.
- **Direct pair-safety assertion:** exit **1**, expected assertion failure; the test was neither edited nor hidden. `git diff --check` passed for changed existing files.

Early new-harness failures were missing fixture constants, corrected in the isolated harness. No remaining unexpected test failure is claimed as a pass. No expensive ML studies were rerun.

## Collision Regression

Collision semantics changed: **NO**. 3-hit rule: **UNCHANGED**. 5-second window: **UNCHANGED**. Pair behavior: **UNCHANGED**.

Known production pair-safety regression: **FAIL**. Expected: **FAIL**. The direct unchanged assertion still reports `AssertionError: 'confirmed_crash' == 'confirmed_crash'`. Scene-level ownership remains unsafe. Candidate, positive, reset/window-expiry and single-vehicle aftermath outputs match the saved pre-edit worker in deterministic comparisons.

## Detector

Model: **UNCHANGED**. Proposal threshold: **UNCHANGED**. Acceptance: **UNCHANGED**. Training: **NONE**. Classifier/proximity/geometry settings and incident creation semantics: **UNCHANGED**.

## Alarm

**UNCHANGED**. No alarm implementation/audio/arming changes or operational incident creation. Existing tests verify fresh-confirmed one-shot attempts and candidate/aftermath/duplicate silence; this is not an audible-browser validation.

## Protected Areas

[Protection audit](../backend/validation/live_cctv_implementation_stage1_20261001/protection_audit.json): **15,511 pre-existing paths checked; exactly 3 changed, 0 missing, 0 unexpected changes**. Changed paths are the three allowlisted files above. The only changed top-level Python function/class definition is `LiveCameraMonitor`; the separate preview-FPS default change is scoped infrastructure.

The inventory includes model weights, Source B, Phase 8C, prior reports/artifacts, training originals/manifests/provenance and protected application modules. No hash changes outside the allowlist. Operational database contents were not part of this file inventory; test isolation and mocked persistence prevented operational writes. Existing unrelated user edits were preserved, not reverted. Stage 2 rendering/tracking/pair/verifier modules were not changed.

## Remaining Limitations

Frontend box synchronization not implemented yet; vehicle recall and domain detector improvement unresolved; persistent production tracking, pair ownership, interaction verification and collision safety unresolved. Live RTSP/browser performance remains unverified. Stalled preview can retain its last image with its original provenance; this stage does not implement UI stale-box expiry. CPU fairness and long-duration/multicamera capacity are not established.

## Stage 1 Verdict

**STAGE1_FRAME_PIPELINE_READY**

Latest-frame/bounded-work behavior, independent capture/preview, exact result provenance and API compatibility pass the scoped deterministic gates. Collision/alarm semantics and protected areas remain unchanged; the known pair-safety failure remains explicit. Performance is a bounded synthetic improvement with disclosed age/CPU costs, not production collision readiness. Stop before Stage 2.

STAGE 1 IMPLEMENTATION COMPLETE — SEND RESULTS BEFORE STAGE 2
