
# Live Collision Diagnostic Telemetry

Instrumented production function: **`LiveCameraMonitor._analyze_current_frame`**, in [backend/main.py](../backend/main.py). The existing vehicle extractor and proximity loop emit observation-local details only while this worker's diagnostic context is active. Uploads, offline validation, tracking and pair-verification services are not instrumented.

Diagnostics location: **`backend/validation/live_collision_diagnostics/observations.jsonl`**, with `.1` and `.2` rotated backups. Generated files are Git-ignored. The writer uses an absolute project-relative path, independent of the launch directory. No live capture was enabled during this implementation.

## Enable command/config

Opt-in environment variable: **`LIVE_COLLISION_DIAGNOSTICS=1`**. In the PowerShell terminal used to launch the backend:

```powershell
cd C:\Users\Lenovo\Desktop\MyCrushguard
$env:LIVE_COLLISION_DIAGNOSTICS = '1'
.\backend\.venv\Scripts\uvicorn.exe backend.main:app --host 127.0.0.1 --port 8010
```

If the backend is already running, stop that process first and launch it with this environment. Changing another terminal's environment does not change the running process. Use the existing single backend worker; do not launch a second listener or add `--workers` for this diagnostic capture. The rotating file is shared by the cameras in that process and is not a multiprocess logging service.

Exercise the existing Live Monitor normally. After completed inference observations, inspect the trace in a separate terminal:

```powershell
Get-Content .\backend\validation\live_collision_diagnostics\observations.jsonl -Tail 1 |
    ConvertFrom-Json |
    Select-Object camera_id, observation_sequence, streak_before, observation_qualified,
        streak_after, streak_action, reset_reasons, final_decision, telemetry_complete
```

For event review, retain the current file and both available backups before continued capture overwrites the relevant window. Review in order `.2`, `.1`, then the current file, grouping by `run_id` and `camera_id`. No credentials, image files, or databases are needed to operate this trace.

## Disable command/config

Stop the diagnostic-enabled backend process. In its launch terminal:

```powershell
$env:LIVE_COLLISION_DIAGNOSTICS = '0'
.\backend\.venv\Scripts\uvicorn.exe backend.main:app --host 127.0.0.1 --port 8010
```

Alternatively remove the variable before launch:

```powershell
Remove-Item Env:LIVE_COLLISION_DIAGNOSTICS -ErrorAction SilentlyContinue
```

Only the exact value `1` enables capture. Default is OFF. No source edits, new API endpoint, authentication change, database setting, or camera setting is needed. Existing diagnostic files remain available after disabling; disabling does not delete them.

## Required consecutive observations

Current code default and deterministic test value: **3**, within **5 seconds**, with case probability threshold **0.90**. Existing environment overrides remain unchanged. Each record captures the effective `required_consecutive_hits`, `temporal_window_seconds`, `classifier_case_threshold`, and per-pass `acceptance_threshold`; a running server's overrides were not independently queried.

The authoritative qualifier remains:

```text
frameQualityStatus == good
AND accidentProbability >= case threshold
AND accepted in-ROI vehicle count > 0
AND sceneValid
```

Proximity is **not** a streak-qualification gate. It supplies the existing current-frame interaction boolean used alongside temporal readiness. A completed streak without that interaction continues to produce the existing aftermath decision. No `INSUFFICIENT_VEHICLES`, geometry, or proximity condition was added to the qualifier.

## Captured fields

One JSON object is submitted per completed live decision observation, including clean/ignored results. It is collected at the decision boundary before persistence and queued when the worker exits. The response itself is unchanged.

| Area | Fields and meaning |
|---|---|
| Identity | `schema_version`, process `run_id`, sanitized `camera_id`, `observation_sequence` using the worker's actual captured-frame sequence. Sequence gaps are expected because the worker consumes the latest frame. No persistent vehicle identities are created |
| Candidate/result | `candidate_analyzing`, `final_decision`, `rejection_reason`, `accident_detected`, `temporal_verified`, `motion_valid`, `scene_valid`, `vehicle_count`. Accident boolean is the existing final observation-evidence boolean, not case persistence |
| Streak | `streak_before`, `observation_qualified`, `qualification_failures`, `streak_after`, `required_consecutive_hits`, `streak_action`, `reset_reasons` |
| Window | Exact copies of `window_before` and `window_after`, `window_evaluated_at`, `temporal_window_seconds`, `expired_observations`. Copying never mutates the deque |
| Classifier | Actual whole-frame `classifier_score`, `classifier_case_threshold`, `classifier_passed`, and `classifier_ui_threshold`. No pair-classifier or temporal-service score is invented |
| Quality | `frame_quality_status`, `quality_rejection_reason`, `blur_score`, `brightness_score`, `contrast_score` |
| Detector passes | `detector_passes` identifies `separate_vehicle_model` or `primary_model_fallback`; a real empty-result retry has a separate pass index. No model path or URL is serialized |
| Vehicles | `vehicles`: proposal ID, pass, class, confidence, original `raw_bbox_xyxy`, extraction threshold, accepted/rejected flag and exact branch reason. Accepted extraction boxes additionally include clamped `bbox_xywh`. ROI rejection updates acceptance to false |
| Final vehicle list | `accepted_vehicles`: index in the exact ROI-filtered list, source proposal ID, class, confidence, bbox. All IDs are observation-local and explicitly labeled as such |
| Evaluated pairs | `evaluated_pairs`: actual index pair, classes, boxes, IoU, edge distance, scale, normalized edge distance, required IoU 0.08, maximum normalized distance 0.05, qualifies boolean. The production short-circuit is preserved: pairs after the first qualifying pair are not evaluated or logged |
| Timing | Existing result `timestamp`; Unix-second `frame_receive_time`, `inference_start`, `inference_end`, `decision_time`; monotonic `inference_duration_ms`; `seconds_since_previous_analyzed_observation` (start-to-start, null on first captured analysis) |
| Integrity | `telemetry_complete`, process-cumulative `diagnostic_records_dropped`, `diagnostic_write_errors` |

The inference interval begins after the existing new-frame/staleness checks and ends after the final vehicle-detector pass. It includes quality/model work and diagnostic collection, but excludes later persistence. `decision_time` is sampled just after the existing decision evaluation; `window_evaluated_at` is the exact existing time used by the production temporal window. Frame receive time is host decode-completion time, not camera sensor time.

Raw proposals mean post-NMS outputs actually returned by the detector. The trace cannot reveal proposals already suppressed inside YOLO, and does not rerun inference to recover them. Unsupported labels are serialized as `other_class`; accepted vehicle labels and `person` retain their names. No pixels, frame arrays, RTSP URLs, labels/locations containing arbitrary text, credentials, session tokens, or exception messages are serialized.

## Reset reasons supported

Qualification failures follow the existing predicates, in order:

- `low_quality_blurry_frame`, `low_quality_dark_frame`, `low_quality_overexposed_frame`, `low_quality_low_contrast_frame`, or the existing `low_quality_frame` fallback.
- `below_case_threshold`.
- `no_vehicle_detected`.
- `vehicle_outside_roi`.

Multiple failed predicates are preserved. The existing single `rejection_reason` is also recorded separately; it may be more general, such as `temporal_not_verified`. A failed observation with an existing positive streak is `RESET`; one with a zero streak is `UNCHANGED`, with its qualification failures still present.

Vehicle-level rejection reasons are `class_not_vehicle`, `below_vehicle_confidence`, `invalid_bbox`, and `vehicle_outside_roi`. These report the actual extraction/ROI branch; they are distinct from the observation's qualification failures.

`temporal_window_expired` describes removal by the existing five-second pruning loop. A qualified observation can therefore log `RESET` with a nonzero `streak_after`: for example two old positives expire and the new positive leaves a count of one. This diagnostic action does not execute a reset itself. `window_before`, `window_after`, and the counts are authoritative when expiry and a new hit coincide.

Action precedence: `CONFIRM` when the actual final decision is `confirmed_crash`; otherwise `RESET` when an existing streak is broken or window expiry prevents the expected increment; otherwise `START` / `INCREMENT` when the count grows; otherwise `UNCHANGED`. Duplicate/cooldown and aftermath decisions retain their real final decision and are never relabeled as confirmed.

## Bounds and failure handling

The opt-in writer uses a queue of at most **8 observations**, one daemon writer, **16 MiB rotation size**, and **2 backups** (approximately **48 MiB** total retained JSONL). Individual serialized records exceeding 16 MiB are dropped rather than expanding the files without bound. Existing inference/capture waits and RTSP settings are unchanged. Serialization, rotation and filesystem writes occur in the writer thread.

This is **best-effort telemetry**: queue overflow, oversized records or disk errors must not block or fail collision processing. Subsequent successfully written rows carry cumulative drop/error counts. An in-memory collector error sets `telemetry_complete=false`. Missing/partial rows must never be interpreted as a negative collision observation. Persistent disk failure produces no usable trace; verify that records are arriving before relying on capture. Abrupt process exit can lose queued rows. Rotated history is deliberately overwritten.

Busy, stale or repeated-frame calls that never reach a collision decision do not produce a decision row. Their effect may be visible through sequence/time gaps; this task does not add a separate inference-error trace. No live performance or physical collision recovery claim is made: collection adds some computation, although no deliberate cadence/scheduling changes or disk waits were added to inference. Deterministic equivalence establishes unchanged decisions for the same observations/timestamps, not zero wall-clock overhead on every machine.

## Behavioral equivalence and tests

Decision behavior with diagnostics OFF: original qualification, geometry, hit-window mutations and final confirmation remain active; no diagnostic sink is created.

Decision behavior with diagnostics ON: the same functions execute; telemetry reads existing inputs/outputs and adds no detection, model call, qualifying gate or decision input.

**DECISION_BEHAVIOR_IDENTICAL: YES**, for the deterministic observations/times tested.

The tests AST-load the actual production constructor, worker bodies, filtering/geometry helpers, thresholds and decision function without importing backend startup. Model predictions, media writes and persistence are stubbed. No operational database, camera or model file is opened. Comparisons cover diagnostics OFF, diagnostics ON, and a source-extracted worker with diagnostic calls/decorator removed. Candidate states, hit counts, confirmation booleans, rejection reasons, temporal candidate state, case-created flags and model-call counts are identical.

| Required sequence | States | Telemetry |
|---|---|---|
| 0.95 → 0.95 → 0.89; good quality, valid interacting vehicles | `candidate → candidate → ignored` | `0→1 START`, `1→2 INCREMENT`, `2→0 RESET`; reason `below_case_threshold` |
| 0.95 → 0.95 → 0.95; same conditions | `candidate → candidate → confirmed_crash` | `0→1 START`, `1→2 INCREMENT`, `2→3 CONFIRM` |

Tests: **16 passed** with:

```powershell
.\backend\.venv\Scripts\python.exe -m unittest backend.tests.test_live_collision_diagnostics -v
```

Additional coverage: quality/no-vehicle/ROI resets; qualifying observation after window expiry; one-vehicle aftermath without invented proximity qualification; every evaluated pair and first-success short-circuit; rejected confidence/class/invalid boxes; real empty-result retry and unchanged inference-call count; privacy; disabled sink creation; collector/sink failures; queue saturation; unwritable output; bounded rotation and valid JSONL.

Syntax parsing passed for all changed Python files. Removing only the added diagnostic hooks/import/decorator and reverting the pair-loop index enumeration reproduces the preceding audit's exact `backend/main.py` SHA-256: `37647d93c499f89869af05aa2c71b73d2b2f703781b20e387b62bcc765435c36`. The pair-loop enumeration preserves order and adds only the observation-local index. Pre-existing working-tree changes were preserved.

## Change boundaries

Production collision algorithm changed: **NO**

Models changed: **NO**

Thresholds changed: **NO**

Tracking added: **NO**

Pair verification added: **NO**

Database changed: **NO**

Authentication changed: **NO**

Dispatcher/responder changed: **NO**

Source B changed: **NO**

Phase 8C changed: **NO**

Verdict: **READY_FOR_LIVE_COLLISION_DIAGNOSTIC**
