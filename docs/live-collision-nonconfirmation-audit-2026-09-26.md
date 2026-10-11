# Live Collision Non-Confirmation Audit

Date: 2026-09-26. Scope: current working-tree RTSP Live Monitor collision path. Diagnosis only.

Analyzing banner reached: **YES — user-reported.**

Confirmed crash reached: **NO — user-reported; exact-event backend outcome independently UNKNOWN.**

**Finding:** In the inspected production worker, `candidate` means at least one qualifying observation exists but the required consecutive-observation count has not been reached. Defaults require three qualifying observations within five seconds. Confirmation additionally requires two accepted vehicle boxes to overlap or be sufficiently close in the current observation. This worker does not run the separate tracking, logical-continuity, pair-classification, or temporal-verifier services. There is no attributable, persistent collision pair in this path.

**Limit:** No screenshot, event timestamp, camera identifier, or matching per-observation event trace was supplied. Therefore the exact reason the streak did not complete, and whether the actual motorcycle or other participant was detected, cannot be established. A production integration gap is code-verified; attributing this particular miss to that gap, the detector, or FPS would exceed the evidence.

## Evidence and scope

- **DIRECTLY OBSERVED:** current source text; installed local Ultralytics default prediction cutoff; contents of an existing saved observation trace. This label does not mean the reported collision was directly observed.
- **CODE-PATH VERIFIED:** function calls, gate order, default settings, output assignments, frontend condition.
- **REPRODUCED:** isolated execution of the current pure decision and geometry functions, extracted with Python AST, using synthetic inputs and explicitly supplied code defaults. No model inference or recorded-event replay was performed.
- **INFERRED:** what a current RTSP `candidate` result necessarily implies, conditional on the reported banner originating from this code version.
- **UNKNOWN:** exact event values, participant identities, deployed process revision/environment, and causes of subsequent failure.

The working tree already contains extensive changes. It is the source authority for this audit, not a clean historical commit. No production code, models, thresholds, camera settings, databases, training data, Source B artifacts, or Phase 8C artifacts were changed. No server was started, camera opened, detection endpoint invoked, or database queried. Only this report was added.

Allowed detection-setting keys were checked in the audit shell and existing `.env`, `.env.local`, and `backend/.env` files; none were present. This does **not** establish the running server's inherited environment. All numerical settings below are code defaults unless explicitly identified as historical observations.

## Meaning of "Analyzing"

Frontend condition: `latestResult && ['candidate', 'verifying'].includes(latestResult.finalDecision ?? '')`, at [components/live-camera.tsx:1691](../components/live-camera.tsx#L1691). `applyDetectionResult` accepts candidate/verifying updates into display state at line 835. The literal banner does not inspect a pair score or a crash label.

Delivery: `pollCctvMonitor` → `getCameraMonitoringStatus` → `GET /api/cameras/{camera_identifier}/status` → `api_live_camera_status` → `LiveCameraMonitor.snapshot_status().latestResult`. Sources: [components/live-camera.tsx:1238](../components/live-camera.tsx#L1238), [lib/api-client.ts:670](../lib/api-client.ts#L670), [backend/main.py:4752](../backend/main.py#L4752). The workspace also polls this status endpoint. `GET /api/cameras/{camera_identifier}/events` exposes the same worker result through SSE; it is not a different collision engine.

Producer: `LiveCameraMonitor._analyze_current_frame` calls `evaluate_crash_case_decision` with an explicit boolean `temporal_verified`. Its false branch returns `candidate` when the consecutive-hit count is positive, otherwise `ignored` (main.py:674–681). The worker also sets the status message to the banner text for candidate/verifying at main.py:3146.

For this exact RTSP call path, `candidate` implies:

1. Current frame quality status is `good`.
2. At least one accepted vehicle remains in the ROI and `sceneValid` is true.
3. Current whole-frame accident probability meets the **case** threshold, default **0.90**.
4. There is at least one consecutive positive observation, but fewer than the configured required count, default **3**.

Why item 4 follows: once `temporal_ready` becomes true, the worker supplies either `temporal_verified=true` (interaction present) or `aftermath_candidate=true` (interaction absent). Neither yields `candidate`. The `verifying` branch exists in the general helper's `temporal_verified=None` mode, but the inspected RTSP caller always passes a boolean, so it cannot emit `verifying` through that branch.

The separate **0.80** UI threshold sets `crashSuspected`/`thresholdHit` and permits the empty-vehicle retry. Crossing 0.80 alone does not produce this RTSP banner. The banner proves neither the identities of the road users nor collision contact, trajectories, or final confirmation. The displayed preview may be newer than the result; display retention is also possible, so the banner is not necessarily a measurement of the pixels currently visible.

## Current Production Pipeline

```text
RTSP → OpenCV FFmpeg read() → newest native BGR frame + sequence/timestamp
  → frame-available event → _detection_loop
  → analyze_current_frame (per-camera lock)
  → _analyze_current_frame (shared nonblocking inference lock)
  → reject repeated sequence / stale frame
  → analyze_frame_quality(native frame)
  → best.pt.predict(native frame, imgsz=640)
  → extract_detections (display detections; returned accident flag ignored here)
  → crash_classifier.pt.predict(native frame, imgsz=224 by default)
  → whole-frame accidentProbability
  → detect_vehicle_boxes (separate detector if loaded; else best.pt results)
  → class/confidence/valid-box filtering; conditional empty-result retry
  → ROI-center filtering → accepted vehicle count
  → crash_like_vehicle_interaction(all accepted ROI boxes)
  → time-bounded consecutive qualifying-hit deque
  → temporal_verified / aftermath_candidate
  → evaluate_crash_case_decision → finalDecision
  → eligible case persistence; observation accident boolean assigned separately
  → latest_result → status polling → frontend banner/confirmation predicate
```

Sources: main.py `_capture_loop` (2312), `_detection_loop` (3204), `analyze_current_frame` (2673), `_analyze_current_frame` (2682), and [inference_execution.py](../backend/services/inference_execution.py).

Vehicle source matters: `vehicle_model` loads `VEHICLE_MODEL_PATH`, default `yolov8n.pt` (main.py:443). `detect_vehicle_boxes` uses it whenever loading succeeded; only an unavailable separate model causes fallback to `best.pt` outputs. The declared `LIVE_CAMERA_USE_SEPARATE_VEHICLE_MODEL` flag is not consulted by this helper or this live call. Actual loaded detector/model hashes for the running event are UNKNOWN.

| Service or mechanism | Called by current RTSP worker? | Evidence |
|---|---|---|
| Whole-frame binary crash classifier | YES | `classify_crash_frame`, main.py:2714; accident-class probability at 1224 |
| Vehicle detector and simple filtering | YES | `detect_vehicle_boxes`, 939; caller 2728 |
| ByteTrack / `vehicle_tracking.py` | NO | No import/call in worker or its detection helpers; `.predict`, not `.track` |
| `vehicle_detection_tiers.py` | NO | Worker accepts ordinary box lists, not tier results |
| `logical_vehicle_continuity.py` | NO | No identities or continuity update in worker |
| `classify_collision_pair_regions` / pair classifier | NO | Helper defined at 711 but no invocation in main.py |
| `temporal_crash_verifier.py` | NO | Local deque and boolean calculation at 2775–2789, 2912 |
| `crash_aftermath_detector.py`, evidence resolver, event-state service | NO | Worker derives aftermath directly as `temporal_ready and not motion_valid` |
| Stateless `CameraDecisionTracker` | NO for this worker | Separate camera-image request mechanism; RTSP uses `self.hit_window` |

## Gate Trace

The table distinguishes a candidate-producing observation from the entire reported incident. Source references below are in backend/main.py unless otherwise stated.

| GATE | OBSERVED/CURRENT STATE | REQUIRED STATE | PASS / FAIL / UNKNOWN | FAILURE REASON | SOURCE FILE + FUNCTION |
|---|---|---|---|---|---|
| New usable frame / inference access | Banner requires a previously completed analysis; exact age unknown | New sequence; frame present; age ≤ freeze timeout (default 10 s); locks available | PASS for originating result, INFERRED | Later duplicate/stale frames or busy inference can prevent observations; not proven here | `analyze_current_frame`, `_analyze_current_frame`:2673–2700 |
| Frame quality | Good at candidate observation, by branch logic | `frameQualityStatus == good` | PASS at candidate, INFERRED; later UNKNOWN | Bad quality breaks qualifying streak | `_analyze_current_frame`:2705,2768; `frame_quality.py:analyze_frame_quality` |
| Candidate / case probability | Meets configured case threshold at candidate | Accident probability ≥ default 0.90 | PASS, INFERRED | Subsequent lower probability resets streak; event scores unavailable | `_analyze_current_frame`:2720,2760–2773 |
| Participant A detected | Actual motorcycle has no linked raw record | Actual participant returned by detector | UNKNOWN | No exact-event raw detections | `detect_vehicle_boxes`:939 |
| Participant A accepted | No attributed box | Allowed class, confidence, nonzero box, ROI center | UNKNOWN | No raw-to-accepted mapping | `extract_vehicle_boxes_from_results`:896; `filter_boxes_in_roi`:553 |
| Participant B detected | Other actual road user's class/identity unknown | Actual participant returned by detector | UNKNOWN | No exact-event raw detections | `detect_vehicle_boxes`:939 |
| Participant B accepted | No attributed box | Same acceptance conditions; person is not an accepted vehicle | UNKNOWN | No raw-to-accepted mapping | Same filtering functions |
| Any accepted vehicle / ROI | At least one accepted vehicle, not necessarily A/B | Count > 0; scene valid | PASS at candidate, INFERRED | Does not prove two actual participants | `_analyze_current_frame`:2762–2773 |
| True pair generated | No identified pair object exists in this path | For attributable detection: actual A and B jointly evaluated | UNKNOWN for actual A/B geometry; persistent pair mechanism absent | Any eligible pair can satisfy the boolean; no attribution output | `crash_like_vehicle_interaction`:622 |
| Pair continuity | Not represented or required | No production pair-continuity requirement | UNKNOWN for real pair; N/A as implemented gate | No IDs, pair memory, or measured trajectories | `_analyze_current_frame`:2761–2789 |
| Temporal confirmation / hit count | Positive count below requirement at candidate | ≥ required consecutive positives, default 3 within 5 s | FAIL at candidate, INFERRED; later UNKNOWN | Streak incomplete; cause of continued noncompletion unknown | `_analyze_current_frame`:2775–2789 |
| Current interaction | Unknown at candidate; may already pass | At least two accepted boxes; any pair IoU ≥ 0.08 OR edge gap / max box dimension ≤ 0.05 | UNKNOWN | Not measured motion; no actual pair trace | `crash_like_vehicle_interaction`:622–638 |
| Dynamic evidence conjunction | False at candidate | Temporal-ready AND current interaction | FAIL at candidate, INFERRED | Incomplete streak is sufficient to fail regardless of interaction | `_analyze_current_frame`:2912 |
| Active-case suppression | Cannot block a candidate in helper ordering | No existing blocking case | UNKNOWN for later eligible observations | Evaluated for final decision only after evidence succeeds | `evaluate_crash_case_decision`:704 |
| Cooldown | No exact-event value | `cooldown_ready`, default 60 s since last created alert | UNKNOWN for later eligible observations | Cannot explain current candidate branch | `_analyze_current_frame`:2893; decision helper:706 |
| Final confirmation | Not confirmed in candidate result; user reports no transition | Evidence conjunction plus no duplicate/cooldown block for `finalDecision=confirmed_crash` | FAIL at candidate; later backend UNKNOWN | Do not infer final event failure from absent telemetry | Decision helper:675–708; payload:2931–2937,3144 |

Default quality checks: Laplacian variance ≥80, grayscale mean between 35 and 220 inclusive, standard deviation ≥20. `ENABLE_FRAME_QUALITY_GATE=false` overrides quality status to good while still computing scores. These are frame-level checks, not motorcycle-specific visibility checks.

## Earliest Failed Stage

**At the candidate-producing observation: the required consecutive-positive count has not yet been reached.** This follows from the current caller/helper combination, not an observed hit value. With defaults the count must be 1 or 2. An effective requirement of 1 would make this RTSP candidate branch unreachable for a qualifying frame.

**Across the complete incident: UNKNOWN.** We cannot identify which prerequisite first fails on the following observation: probability, frame quality, vehicle/ROI evidence, available observations/window expiry, or something else. Nor can we establish whether a completed streak later took the aftermath or duplicate branch. Do not blame pair continuity or the standalone temporal verifier: neither runs here. Do not claim the actual participants passed because nearby cars were boxed.

## Motorcycle

Participant A is the user-described apparent motorcycle; its actual model class is not known. Participant B is the other involved road user; its type is also unverified.

| Field | Participant A | Participant B |
|---|---|---|
| Raw detection | UNKNOWN | UNKNOWN |
| Model class | UNKNOWN | UNKNOWN |
| Confidence | UNKNOWN | UNKNOWN |
| Accepted by CrashGuard | UNKNOWN | UNKNOWN |
| Rejection reason | UNKNOWN | UNKNOWN |
| Accepted/consecutive observations | UNKNOWN | UNKNOWN |
| Identity continuity | UNKNOWN; not tracked by worker | UNKNOWN; not tracked by worker |

Detection: correct classification, low confidence, misclassification, small/distant scale, occlusion, and loss between frames are all **UNKNOWN** for the event. No screenshot or synchronized participant-labeled frames support any of those diagnoses.

Acceptance: motorcycle is allowed. `motorbike` and `moped` normalize to `motorcycle`. Accepted classes also include car, bus, truck, bicycle, vehicle, van, suv, automobile, and auto (main.py:518–528). Person is counted separately and cannot supply the second vehicle for the geometry rule. There is no minimum pixel-area/aspect-ratio gate here beyond positive clamped width/height. Class/confidence and ROI can still remove a motorcycle.

Normal acceptance cutoff is **0.40**. If the entire pre-ROI accepted vehicle list is empty and accident probability ≥0.80, the worker repeats vehicle detection with extraction cutoff **0.15**. This does not pass `conf=0.15` to YOLO. The installed predictor defaults to **0.25** when unspecified (`backend/.venv/Lib/site-packages/ultralytics/engine/predictor.py:127`), so the retry does not ordinarily recover proposals already suppressed below 0.25. A nearby car accepted at 0.40 prevents this retry even if the actual motorcycle is weaker. This is a **code-verified potential acceptance failure**, not a demonstrated cause of this incident. The retry also occurs before ROI filtering, so out-of-ROI accepted cars can prevent it.

Continuity: the boxes contain label, confidence, and geometry only. No track ID, velocity, acceleration, or actual participant identity is produced. The absence of usable identity/motion information is **CODE-PATH VERIFIED** for all participants; actual physical instability or observation loss remains UNKNOWN.

## True Pair

Generated: **UNKNOWN** whether actual A↔B was ever jointly present and geometrically evaluated. **NO** identity-bearing true-pair object is generated by this worker.

Persisted: **NO** persistent pair identity/state in the collision logic. Saved evidence boxes do not constitute pair continuity.

Score: **N/A** — the active interaction helper returns a boolean, not a scored/ranked pair. Actual A↔B IoU and normalized gap are UNKNOWN.

Pair passed confirmation: **UNKNOWN** for the actual participants; authoritative attribution is not represented.

Unrelated pair selected: **UNKNOWN** for this event. The helper iterates box-list combinations and returns immediately for the first qualifying pair. It neither ranks them nor records the selected identities. Earlier unrelated boxes can satisfy the boolean before the true pair is evaluated. A whole-scene high classifier score can therefore be combined with unrelated nearby traffic. An isolated geometry reproduction showed two stationary adjacent boxes can return true; that demonstrates the limitation, not an event false positive.

If no true pair existed, its earliest cause cannot be identified without raw and accepted participant evidence. The absence of a pair object must not be confused with proof that both participants were missed.

## Candidate Trigger

Score: **UNKNOWN** exact event value; logically ≥ effective case threshold for this RTSP candidate.

Threshold: default **0.90** for the qualifying observation; separate suspicion threshold **0.80**. Runtime overrides unverified.

Peak score: **UNKNOWN**. Frame/time: **UNKNOWN**.

Reason analyzing activated: an explicit `candidate` backend decision after at least one good, in-ROI, vehicle-bearing, case-threshold observation but before the required streak completed. `classify_crash_frame` uses the probability of class `accident`, not merely top-class confidence. The primary detector's extracted accident flag is intentionally assigned to an unused local in the live worker (main.py:2713).

The classifier alone cannot authoritatively confirm a crash. Unlike the historical offline temporal composition, its score is a mandatory streak gate in this production worker. The dormant pair-region classifier neither starts nor confirms this live candidate.

## Final Confirmation Requirement

In plain language: obtain enough **consecutive analyzed observations** with good frame quality, whole-frame accident probability at least the case threshold, and at least one accepted in-ROI vehicle, all inside the temporal window. On the current observation, at least two accepted vehicle boxes must overlap by IoU ≥0.08 or have normalized edge separation ≤0.05. The same vehicles need not appear in earlier observations, and no measured movement is required. These are the implemented rules, not proof of a physical collision.

Then `evaluate_crash_case_decision` returns `confirmed_crash` only if there is no active-case or cooldown block. A completed streak without the current box interaction is instead eligible for `possible_crash_aftermath`, not `confirmed_crash`.

The outputs are distinct:

- `temporalCrashVerified` = streak complete AND current box interaction AND good quality AND valid scene AND vehicle count >0.
- `accident_detected` and `accidentDetected` are overwritten from that evidence boolean at main.py:3144, even if duplicate/cooldown suppression changed the final decision. Temporary true values in persistence branches are not the final assignment.
- `finalDecision=confirmed_crash` additionally requires passing suppression. Persistence failure can prevent a saved case/alarm without undoing a successful evidence decision. A persisted aftermath review does not set the final accident boolean true in this path.
- Frontend confirmation uses both `accident_detected===true` and `finalDecision==='confirmed_crash'` ([lib/incident-alarm-contract.ts:17](../lib/incident-alarm-contract.ts#L17)). Audible alarm additionally needs a fresh newly created unseen case/incident. There is no additional frontend three-hit confirmation rule. These downstream conditions cannot explain why a backend result is still `candidate`.

Failed requirement: **incomplete consecutive-positive count at the originating candidate observation, conditionally established from code. The exact requirement preventing eventual confirmation remains UNKNOWN.**

### Isolated reproductions of current functions

Current pure functions were AST-extracted rather than importing backend.main, avoiding its model/database startup side effects. Default 0.90 threshold, three hits, five-second window; good quality, valid scene, no duplicate/cooldown unless stated. Hit-window inputs were synthetic, not event footage.

| Synthetic inputs | Result |
|---|---|
| One 0.95 observation, two boxes, interaction true | `candidate`, `temporal_not_verified` |
| 0.95 → 0.89 → 0.95, one second apart | `candidate → ignored → candidate`; score drop resets streak |
| Three 0.95 observations at 0/1/2 s, interaction true | `candidate → candidate → confirmed_crash` |
| Three 0.95 observations at 0/1/2 s, one vehicle/no interaction | `candidate → candidate → possible_crash_aftermath` |
| Three positives at 0/3/6 s | Remains candidate; earliest hit expires from five-second window |
| Qualifying confirmed evidence with active case | `duplicate_active_case` |
| Qualifying confirmed evidence with cooldown not ready | `duplicate_cooldown` |
| Two static 100×100 boxes separated by one pixel | Interaction boolean true |

## Cadence

Decoded FPS: **UNKNOWN for event**.

Inference cycles/sec: **UNKNOWN for event**.

Observations during collision / frame age / inference gaps: **UNKNOWN**.

Classification: **UNKNOWN**.

Capture continuously overwrites the latest native frame; inference consumes a new sequence rather than every decoded frame. The default added detection wait is zero. Shared nonblocking model access can reject concurrent work; the loop logs/retries, and no qualifying hit is appended for an analysis that never runs. Same-frame reanalysis and stale frames are rejected. The worker's five-second window is based on host time near completion of the inference steps, not source video time. Failures to acquire observations can allow evidence to age out; completed negative observations reset the consecutive suffix. Neither is shown for this event.

`snapshot_status` already exposes `captureFps`, `aiFps`, `inferenceMs`, `inferenceFrameAgeMs`, sequences and dropped-frame count (main.py:2594 onward). `captureFps`/`aiFps` are recent five-second rate estimates; frame age begins at host decode completion and does not measure sensor/network delay. Status/SSE cadence is not inference cadence. There is no evidence permitting a PRIMARY_CAUSE or CONTRIBUTING_FACTOR label here.

## Existing Evidence and Historical Findings

| Artifact | Finding | Applicability |
|---|---|---|
| `docs/live-candidate-audit/observation-1/observations.jsonl` and `summary.json` | 90-second saved session, 2026-09-16; 114 distinct result timestamps, all `ignored` / `no_vehicle_detected`; peak confidence 0.15525615215301514; no candidate/confirmation | DIRECTLY OBSERVED file contents. Does not capture the reported candidate episode; its values are not assigned to this event |
| `docs/live-monitor-restoration/REPORT.md` | September 15–16 inspection described the hit-window worker and absent newer service orchestration | HISTORICAL FINDING independently rechecked against current source |
| `backend/validation/live_cctv_audit/source_b_audit_report.md` | Explicitly offline service composition; sparse true-participant support and unrelated-pair behavior | HISTORICAL FINDING, not this production worker/event |
| `backend/validation/live_cctv_architecture_study/architecture_study_report.md` | Explicitly not an exact worker trace; primary-cycle participants accepted on different frames, no usable true-pair trajectory; unrelated queue pair confirmed in replay | HISTORICAL FINDING; safety evidence against blanket threshold lowering or blindly connecting those services |
| `backend/validation/cctv_detector_readiness/cctv_detector_readiness_report.md` | Participant-specific detection/readiness and wrong-pair regression requirements; proposed targets | HISTORICAL planning evidence, not measurements of this incident |
| `backend/validation/cctv_detector_trajectory_pilot/pilot_readiness_report.md`, `tapo_domain_pilot_report.md` | No completed participant-labeled calibration set demonstrating this event's recovery | HISTORICAL readiness limitations, not deployed detector proof |

The Source B audit identifies a dark participant whose subtype is uncertain and a light car. It must not be relabeled as the user's motorcycle incident. Its 0.862/0.863 unrelated temporal scores, later classifier peaks, and cadence conclusions cannot be imported into this event or into the current worker's boolean geometry rule. Existing top-level runtime log files are dated July 7–8, not a matched September 26 event record.

## Root-Cause Matrix

Classifications below concern the reported event, not general architecture risk.

| Component | Classification | Evidence / limit |
|---|---|---|
| Candidate classifier | UNKNOWN | Threshold crossed at candidate by inference; sustained scores absent. Its gate activation worked, but later score drops are unmeasured |
| Participant detection | UNKNOWN | No raw records matched to actual A/B |
| Vehicle acceptance | UNKNOWN | 0.40 cutoff and conditional retry verified; actual rejected participants unknown |
| Tracking/continuity | UNKNOWN | No participant tracker active; causal effect on this event unproved |
| True-pair generation | UNKNOWN | No persistent true-pair representation; actual joint boxes unknown |
| Pair attribution | UNKNOWN | Any-pair boolean permits distractor evidence; no event-selected pair record |
| Temporal confirmation | UNKNOWN for eventual miss | FAIL at candidate by code inference; unfinished streak is normal at that moment, not proof of a faulty temporal setting |
| Inference cadence | UNKNOWN | No synchronized collision observation counts/timing |
| Duplicate/aftermath | UNKNOWN for later outcome | NOT_CAUSAL for the originating candidate branch: suppression is downstream; completed no-interaction streak takes aftermath instead |
| Frontend | UNKNOWN for event-wide delivery | CODE-PATH VERIFIED that it displays backend candidate and requires backend confirmation; no proof it lost a confirmed result |

No component is labeled PRIMARY or CONTRIBUTING without event evidence.

## Root Cause

**Precisely established:** the current production algorithm is a whole-frame classifier streak plus an instantaneous any-vehicle-pair proximity boolean. The observed banner, if emitted by this code, represents an incomplete streak, not a tracked collision awaiting the separate temporal verifier. The production path has no way to demonstrate that the two actual participants supplied the evidence.

**Not established:** why the particular visible incident never produced a qualifying final observation. The source admits several distinct explanations that produce the same banner and later nonconfirmation. No matching event trace distinguishes them. Naming low motorcycle confidence, poor identity continuity, insufficient FPS, duplicate suppression, or classifier weakness as the exact root cause would be speculative.

## Minimum Telemetry Needed on the Next Occurrence

Design only; no instrumentation implemented.

1. Camera ID, event interval and effective runtime configuration/code/model hashes. Preserve native analyzed frames for a short pre-contact/contact/post-contact window, indexed by capture sequence; mark actual A/B independently of detector boxes. Preview screenshots alone are insufficient.
2. Per analyzed sequence: decode-completion timestamp, inference start/end, age at inference, gap/skipped/busy reason, raw post-NMS outputs from the detector actually used, model name/hash, and accepted/rejected boxes with confidence/class/invalid-box/ROI reasons. Record whether the empty-result retry ran. Distinguish primary display detections from separate vehicle-detector proposals.
3. Quality scores/status, whole-frame accident probability, effective thresholds, `pre_temporal_positive`, current ordered hit-window timestamps/booleans, consecutive count and `temporal_ready`.
4. Enumerated current box combinations with IoU/normalized gap and the first pair satisfying interaction; stable per-frame box indices are sufficient to audit this existing rule. Link A/B through human-reviewed frame annotations; do not invent track IDs where the worker has none.
5. `motionValid`, `temporalCrashVerified`, aftermath boolean, final/rejection decision, active-case/cooldown flags, accident boolean, and persistence outcome. Record exactly the result delivered/rendered with its result timestamp and displayed preview sequence.

Save every completed analysis around the event, not just periodic samples of `latestResult`; polling can miss an intermediate reset or confirmation. This is the minimum evidence needed to separate recognition failure, acceptance failure, missing observations, scene-score resets, wrong-pair attribution, and downstream suppression.

## Recommended Next Fix

Classification: **LIVE_PIPELINE_INTEGRATION_FIX — provisional diagnostic integration design, not a proven collision-recall fix.**

Component: the existing `LiveCameraMonitor._analyze_current_frame` decision boundary.

Reason: the immediate, justified next change is a bounded opt-in event trace attached to the **actual worker**, carrying the existing inputs, acceptance decisions, geometry attribution and streak transitions above. This closes the demonstrated observability gap before changing any detection component. It should not call an offline substitute, connect unvalidated temporal services, or alter the decision thresholds. No inference-changing fix can yet be justified for this specific incident.

Expected effect: make the next failure attributable to its earliest unmet requirement and to the actual road users, while preserving existing detection behavior. It does **not** promise improved crash recall. Once a trace proves the first failing gate, select one narrowly scoped behavior change and validate both actual-pair recovery and unrelated-traffic false confirmation. Historical wrong-pair cases must remain regression checks. Broadly lowering confidence or continuity thresholds is not recommended.

## Source Fingerprints

SHA-256 of audited files, so later edits are distinguishable from this report:

```text
backend/main.py
37647d93c499f89869af05aa2c71b73d2b2f703781b20e387b62bcc765435c36
components/live-camera.tsx
d4a6ccdce38735a5938591d4982b61205711362e750556b285e89bf008fe23ad
lib/api-client.ts
9dd542985dff39959b09cf0b5c363ffceb28fd733fe6e2badaa1830017764761
backend/services/frame_quality.py
ce19d7cbc0f2107afaa1d0d291a3a28a57acdcabd5a3b615fecc4c39ba45a9d2
```
