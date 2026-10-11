# Source B Physical Pair Baseline

Phase 1 only, 2026-09-30. **The current live-path detector does not supply both physical participants in the assessable first interaction.** There are zero simultaneous accepted A+B observations. The production different-pair safety regression still fails. No collision fix or alarm change was implemented.

Study artifacts: [diagnostic directory](../backend/validation/source_b_physical_pair_baseline_20260930/). Labels are assistant-reviewed diagnostic annotations, **not independently human-verified ground truth**. Physical approach identities are distinguishable; vehicle-specific post-overlap identities are not defensibly resolved from these pixels.

## Evidence Integrity

SOURCE_B_INTEGRITY: **PASS**

Protected source: `backend/validation/cctv_runtime_audit/capture_20260907T201319Z/`.

- `source_b.mkv`, `frame_times.jsonl`, `contact_sheet.jpg`, `window_0_11_1.jpg`, and `window_3.5_6.5_0.25.jpg` are present.
- Fresh sequential decode: **1,399 frames**, each **1280×720**; all **1,399 decoded BGR SHA-256 hashes match the sidecar**; zero adjacent pixel-identical frames. Sidecar indices are contiguous and host elapsed times strictly increase.
- First/last frame host times: **0.000 / 120.062 s**. Recorder completion elapsed time is **120.187 s**, a different endpoint. Recording metadata specifies lossless FFV1, nominal 15 FPS, and approximately 11.632 recorded frames/s.
- All indexing below uses sidecar host time. Container FPS, recorder throughput, and inference cadence are different quantities.
- [Integrity manifest](../backend/validation/source_b_physical_pair_baseline_20260930/integrity.json) records before hashes. [Protection audit](../backend/validation/source_b_physical_pair_baseline_20260930/protection_audit.json) rechecks 108 protected files: **zero changed**, including source assets, model files, production main/services, sampled alarm files and existing Phase 8C files included in the manifest.

## Replay Cycles

Frame indices are zero-based. All times are host elapsed seconds. Phase cells show **frames / host seconds**. Existing image-phase measurements were used to locate corresponding phases; saved reset images and freshly decoded representative approach/interaction/post images were visually reviewed. Phase boundaries are approximate scene-phase labels, not exact physical contact timestamps.

| Cycle | Segment frames | Segment host seconds | Approach | Interaction | Immediate post | Completeness |
|---|---|---|---|---|---|---|
| 1 | 0–87 | 0.000–7.687 | 36–44 / 3.562–4.328 | 45–50 / 4.390–4.750 | 51–60 / 4.828–5.515 | Capture starts mid-playback |
| 2 | 88–377 | 7.750–31.390 | 133–152 / 11.750–13.187 | 153–164 / 13.265–14.078 | 165–183 / 14.156–15.750 | Complete reset-to-reset |
| 3 | 378–545 | 31.484–44.421 | 493–502 / 40.359–41.140 | 503–508 / 41.218–41.609 | 509–518 / 41.687–42.281 | Complete reset-to-reset |
| 4 | 546–836 | 44.500–68.875 | 592–610 / 48.125–49.484 | 611–622 / 49.562–50.562 | 623–641 / 50.640–51.984 | Complete reset-to-reset |
| 5 | 837–1083 | 68.968–93.562 | 961–979 / 84.031–85.406 | 980–989 / 85.468–86.250 | Skipped by forward discontinuity | Discontinuous |
| 6 | 1084–1251 | 93.625–107.921 | 1200–1208 / 103.812–104.437 | 1209–1214 / 104.531–104.859 | 1215–1224 / 104.921–105.562 | Complete reset-to-reset |
| 7 | 1252–1398 | 108.015–120.062 | 1297–1316 / 111.703–113.390 | 1317–1328 / 113.500–114.328 | 1329–1347 / 114.406–116.031 | Capture ends before next reset |

There are **four complete, uninterrupted reset-to-reset segments: 2, 3, 4 and 6**. Segments 1 and 7 preserve the approach–interaction–immediate-post sequence despite truncated playback endpoints. Segment 5 jumps forward at frames **931 (+81.625 s)** and **990 (+86.312 s)**; do not bridge either jump. Frame 88 contains blended reset content.

[Cycle manifest](../backend/validation/source_b_physical_pair_baseline_20260930/cycles.json) and `cycle_1_review.jpg` through `cycle_7_review.jpg` retain the evidence. This fresh detector baseline evaluates **only cycle 1**, with a new monitor and new tracker at frame 0, stopping at frame 87. No state crosses a replay boundary. Later-cycle phase mapping is not counted as new participant ground truth or detector recall.

## Physical Participant A

Class: **Vehicle; subtype unresolved visually.** Dark vehicle entering from the bottom and moving diagonally toward the upper right, with conspicuous red/white light streaks. A detector calling it a car does not settle its physical subtype.

Visibility: Distinct approximate visible envelopes at **frames 37–45 (+3.656–4.390 s)**. Entry is clipped at frame 37; motion blur is substantial. It is not individually localizable in the preceding reviewed frames. From frame 46 onward the overlap/glare does not support reliable separate A boxes through post-interaction and aftermath.

## Physical Participant B

Class: **Car, provisional visual class.** Light-colored vehicle entering from the right and moving left toward A. This is distinct from the bright white car turning on the left.

Visibility: Distinct approximate envelopes at **frames 36–45 (+3.562–4.390 s)**. Separate B identity is unresolved after overlap. No post-contact boxes were extrapolated from the approach.

[Annotations](../backend/validation/source_b_physical_pair_baseline_20260930/annotations.json) cover every frame **30–70**, including host time, phase, A/B bbox or explicit null, visibility/occlusion uncertainty and class. They reuse the previously recorded native-pixel envelopes after fresh visual review. Null observations are **unassessable**, not detector misses. Unrelated vehicles are labeled separately: U1 is the left-turning white car; U2–U5 are upper queued vehicles. Their broad envelopes distinguish unrelated traffic; U1 intermediate envelopes interpolate manually reviewed anchors and are not precision localization truth. Exclusion regions additionally support conservative unrelated-pair attribution.

Native-pixel diagnostic crops: [approach and overlap, frames 42–47](../backend/validation/source_b_physical_pair_baseline_20260930/dense_review_42.jpg). The seven `dense_review_*.jpg` sheets cover all 41 dense frames. Review includes the unchanged original full-frame dense images for context.

## Collision Interaction

Contact: **CONTACT_NOT_DIRECTLY_RESOLVABLE**

Interaction window: **frames 45–50, host +4.390–4.750 s**, provisional; closest convergence/overlap is around frames **45–48 (+4.390–4.593 s)**. The earlier +4.25 s/frame 43 estimate includes approach. No exact contact instant, surface intersection or individual post-impact trajectory is asserted. The apparent convergence and ensuing blended motion can be studied temporally without asserting visually proven physical contact.

Dense phase convention: PRE_APPROACH 30–35; APPROACH 36–44; INTERACTION 45–50; IMMEDIATE_POST 51–60; AFTERMATH 61–70. These are observation labels, not production decisions.

## Participant A Detector Recall

Raw: **1/9 (11.1%)** across assessable observations.

Accepted: **0/9 (0%)** across assessable observations.

| Phase | Assessable / reviewed | Raw recall | Accepted recall |
|---|---:|---:|---:|
| PRE_APPROACH | 0 / 6 | N/A | N/A |
| APPROACH | 8 / 9 | 1/8 (12.5%) | 0/8 (0%) |
| INTERACTION | 1 / 6 | 0/1 (0%) | 0/1 (0%) |
| IMMEDIATE_POST | 0 / 10 | N/A | N/A |
| AFTERMATH | 0 / 10 | N/A | N/A |

Only matching proposal: **frame 41, +4.078 s**, class `car`, confidence **0.3872904**, box `[851.221, 433.877, 969.517, 558.013]`; expected envelope `[840, 429, 973, 563]`; IoU **0.823960**. RAW_DETECTED=true, ACCEPTED=false, REJECTED=true, REJECTION_REASON=`below_vehicle_confidence` at the unchanged **0.40** acceptance threshold.

## Participant B Detector Recall

Raw: **0/10 (0%)** across assessable observations.

Accepted: **0/10 (0%)** across assessable observations.

| Phase | Assessable / reviewed | Raw recall | Accepted recall |
|---|---:|---:|---:|
| PRE_APPROACH | 0 / 6 | N/A | N/A |
| APPROACH | 9 / 9 | 0/9 (0%) | 0/9 (0%) |
| INTERACTION | 1 / 6 | 0/1 (0%) | 0/1 (0%) |
| IMMEDIATE_POST | 0 / 10 | N/A | N/A |
| AFTERMATH | 0 / 10 | N/A | N/A |

**Fresh inference method for both tables:** current `LiveCameraMonitor` method and production acceptance/ROI/pair/decision functions execute through the existing AST test loader, without app startup. Actual local models run on native 1280×720 BGR: primary `backend/best.pt` at imgsz 640, separate vehicle detector **`yolov8n.pt`** at its unchanged default imgsz **640**, and the actual production classifier function using `backend/models/crash_classifier.pt` at **224**. Vehicle YOLO proposal confidence defaults to **0.25**; NMS IoU **0.7**; acceptance **0.40**; classifier UI/case thresholds **0.80/0.90**; ROI is empty/full frame. Configuration and hashes are saved. No threshold is overridden for this experiment.

The worker's existing 0.15 acceptance retry only occurs when no vehicle was accepted and the scene is suspected; unrelated accepted vehicles prevent using that retry to rescue a missing participant. YOLO's proposal threshold remains separate from that retry.

Primary geometric matching uses one-to-one IoU ≥0.30; diagnostic IoU ≥0.10 sensitivity gives **identical counts**. These are evaluation matching rules, not production threshold changes. This measures recall among returned model proposals, not pre-NMS network outputs. Exact participant class correctness is not claimed where the visual subtype is unresolved.

Every labeled participant/frame and match/no-match, expected box, proposal class/score/box, acceptance and rejection reason is in [JSON](../backend/validation/source_b_physical_pair_baseline_20260930/participant_observations.json) and [CSV](../backend/validation/source_b_physical_pair_baseline_20260930/participant_observations.csv). Production telemetry sanitizes unrelated non-vehicle classes as `other_class`; the sole matched participant proposal retains `car`.

This corrects a material comparison issue: older `best.pt`/experimental-tier participant recall is **not the current separate-vehicle-detector live baseline**. This run establishes current source-code behavior with the recorded configuration; it does not recover the original capture-day worker environment.

## Simultaneous A+B Support

Count: **0**

Frames: **[]**

Times: **[]**

Temporal spacing: **N/A**, no simultaneous observations. The result holds at both diagnostic matching IoUs. It concerns the assessable first-cycle physical labels; unresolved post-overlap observations cannot establish additional support.

## Current Production Identity

Persistent track IDs: **NO**

PRODUCTION_PERSISTENT_TRACK_ID = **NO**

The live RTSP path is capture → current-frame model calls → accepted boxes → ROI → current-frame pair proximity → scene hit window → decision. Production `backend/main.py` does not call `VehicleTrackingService`, `LogicalVehicleContinuityService`, `TemporalCrashVerifier` or `PairHitLedger`. Diagnostic proposal/pair indices are observation-local, not persistent identities.

The separate experimental ByteTrack service maintains per-camera histories, with 3-second stale expiry and a 6-second gap reset. A fresh offline run on the **actual accepted boxes** for frames 0–87 produces **zero matched A or B track observations** in the assessable labels. [Track output](../backend/validation/source_b_physical_pair_baseline_20260930/offline_tracking.json) and [participant matches](../backend/validation/source_b_physical_pair_baseline_20260930/track_participant_matches.json) retain the result. No interpolated/carried tracker state was counted as a new detector observation.

The logical continuity service can associate raw tracks and eligible proposals, but its raw-ID reuse path is not an independent physical identity check. The temporal verifier owns pair state but cannot supply missing participants. These services remain separate from production. Visual A/B approach association is possible for annotation; trustworthy **accepted-detection-based A/B histories are unavailable**. A/B identity-swap resistance through this overlap cannot be tested from zero accepted support.

## Current Pair Evaluation

True A↔B pair evaluated: **NO** in the annotated dense observations.

Wrong/unrelated pair evaluated: **YES**.

All **155 actually visited pair comparisons** in frames 30–70 are `UNRELATED_PAIR`; **0** are `LIKELY_TRUE_A_B_PAIR`, **0** are `AMBIGUOUS_PAIR` within that annotated scope. Comparisons outside the labeled window are retained as ambiguous/unlabeled, not assigned physical identity. [Pair attribution](../backend/validation/source_b_physical_pair_baseline_20260930/pair_attribution.json) includes each visited pair's boxes, physical labels, IoU, normalized edge distance and qualification. The actual production loop short-circuits on its first proximal pair; the trace does not invent comparisons after that return.

“Analyzing potential collision...” does **not** establish A↔B evaluation. In this replay, candidate observations are **57, 58, 69 and 70** inside the dense window, after A/B localization has become unresolved. At 69 and 70 the qualifying current pair is **U4↔U3 in the upper queue**, with normalized edge distances approximately **0.019 and 0.010**, below production's **0.05** limit. Neither vehicle is A or B.

Current available signals:

| Signal | Physical A/B evidence | Current production result |
|---|---|---|
| Detector confidence/acceptance | A has one 0.3873 proposal, rejected; B has none | No accepted A/B pair |
| Classifier | Full-frame, no physical-pair attribution | Approach probability range 0.02384–0.72534; interaction 0.00959–0.05776, all below 0.90 |
| Proximity/geometry | No accepted A/B boxes to evaluate | Only unrelated boxes evaluated; IoU ≥0.08 or edge-distance/scale ≤0.05 is a spatial proxy, not measured collision motion |
| Temporal qualification | Zero attributable same-A/B hit contributions | Scene positives at 57,58,59,69,70,71,74 across the full first cycle |
| Streak | No physical pair key | 57→58→59 yields 1→2→3 and `possible_crash_aftermath`; no proximal pair there |
| Later unrelated proximity | Not A/B evidence | 69→70→71 yields 1→2→3; at 71 temporal verification is true, final decision `duplicate_cooldown` after the isolated simulated aftermath creation |

The full [worker trace](../backend/validation/source_b_physical_pair_baseline_20260930/worker_trace.jsonl) records classifier, quality, accepted/rejected proposals, visited pairs, qualification failures, hit-window contents, reset reasons and decisions. All 41 dense frames pass the quality gate. Full-frame classifier evidence is never credited to A↔B merely because unrelated cars are accepted.

Persistence, snapshots and network side effects are stubbed in the harness. Display-only primary detection formatting is stubbed; actual primary inference still runs. Simulated timestamps use `1000 + host_elapsed` for both frame receipt and decision so every saved observation can be tested. Thus this is an **all-captured upper bound**, not real-time scheduling. No real incident, notification or siren action occurred.

## Pair Ledger

Bookkeeping safety: **PASS**

PAIR_LEDGER_BOOKKEEPING = **PASS**

Physical identity source: **INSUFFICIENT**

PHYSICAL_TRACK_IDENTITY_SUPPLY = **INSUFFICIENT**

The six existing ledger tests pass. Given trustworthy externally supplied distinct IDs, sorted pair keys isolate A↔B, C↔D and E↔F; those hits cannot become one three-hit streak. Tests also cover reversed key order, interleaving, duplicate observation rejection, negative resets, expiry, bounds and explicit track revocation. The ledger cannot detect an identity swap itself and cannot authorize physical collision confirmation. It was not integrated.

## Existing 3-Hit / 5-Second Feasibility

**Not supported for physical A↔B by these observations.** Zero simultaneous accepted samples cannot satisfy three same-pair hits in five seconds. Missing/ambiguous observations must not be fabricated or supplemented by a different replay cycle or unrelated queue.

The assessable approach-to-overlap support spans only approximately 0.83 s for B and 0.73 s for A. Three real inference observations would also require suitable sampling within that short interval. The measured offline worker median is **2.846 s/frame**, excluding the first warm-up observation, under the current machine workload. This includes the worker/model calls and diagnostic overhead; it is **not a historical production cadence measurement**. The saved recording contains no mapping to original production observations. No quantitative claim that original live inference definitely skipped particular A/B frames is justified. The all-captured result already fails even before dropping observations for real-time cadence.

## Earliest Verified Failure

**Detector proposal supply:** B is localizable at frame **36 (+3.562 s)** but has no matching proposal. A is localizable at frame **37 (+3.656 s)** but has no matching proposal. Seven of A's eight assessable approach frames lack a proposal; its sole proposal at frame 41 is rejected. This precedes any defensible same-pair tracking or temporal confirmation.

## Additional Failures

| Requested blocker | Evidence classification |
|---|---|
| PARTICIPANT_A_NOT_DETECTED | Verified on 8/9 assessable observations overall |
| PARTICIPANT_B_NOT_DETECTED | Verified on 10/10 assessable observations |
| PARTICIPANT_A_REJECTED | Verified at frame 41, confidence 0.3873 <0.40 |
| PARTICIPANT_B_REJECTED | Not established; missing proposals cannot be called acceptance rejections |
| INSUFFICIENT_SIMULTANEOUS_PARTICIPANT_SUPPORT | Verified: zero |
| TRACK_IDENTITY_NOT_AVAILABLE | Verified in production; offline accepted-input experiment has no A/B track observations |
| TRACK_CONTINUITY_FAILURE | A/B continuity cannot be established; an independent tracker defect/identity swap is not demonstrated by missing inputs |
| TRUE_PAIR_NOT_EVALUATED | Verified in annotated dense window |
| WRONG_PAIR_EVALUATED | Verified: unrelated traffic, including proximal U4↔U3 |
| PAIR_STATE_NOT_PRODUCTION_INTEGRATED | Verified: production still owns scene-level hit history |
| CLASSIFIER_FAILURE | Observed threshold failure throughout labeled approach/interaction; scene classifier is not pair-specific |
| PROXIMITY_FAILURE | True-pair gate unavailable because accepted A/B boxes are missing; no independent physical-separation failure asserted |
| GEOMETRY_FAILURE | True-pair geometry unavailable; no separate production trajectory/contact verifier exists in this path |
| TEMPORAL_WINDOW_FAILURE | No attributable A/B hit sequence exists; no isolated five-second expiry failure proven |
| INFERENCE_CADENCE_LIMITATION | Offline timing indicates a further sampling limitation; capture-day production impact unmeasured |
| MULTIPLE_CAUSES | Verified detector misses, acceptance rejection, identity absence, unrelated-pair evaluation, scene-state ownership, and classifier threshold failures |

Additional evidence limitation: post-overlap participant-specific recall and identity cannot be scored honestly. Therefore this phase establishes a bounded diagnostic baseline, not complete physical collision ground truth through aftermath or a safe integration design.

## Production Pair-Safety Regression

**FAIL**

Fresh existing targeted suite: **87 tests, 86 passed, 1 expected failure**. Command:

```powershell
.\backend\.venv\Scripts\python.exe -m unittest backend.tests.test_pair_hit_ledger backend.tests.test_live_collision_diagnostics backend.tests.test_crash_decision -v
```

[Test log](../backend/validation/source_b_physical_pair_baseline_20260930/tests.log). The existing `test_distinct_physical_pairs_must_not_share_three_hit_confirmation` was also invoked directly without the test runner's expected-failure handling; it exits **1** with `AssertionError: 'confirmed_crash' == 'confirmed_crash'`. [Direct failure log](../backend/validation/source_b_physical_pair_baseline_20260930/production_safety_failure.log).

This is a **real unresolved safety failure**, not a passed production gate. No existing test was modified, weakened, or newly marked expected-failure.

## Changes

Production collision logic: **UNCHANGED**

Alarm: **UNCHANGED**

Thresholds: **UNCHANGED**

Models: **UNCHANGED**

Training: **NONE**

Source B: **UNCHANGED**

Phase 8C: **UNCHANGED**

Only this report and the new isolated `backend/validation/source_b_physical_pair_baseline_20260930/` artifacts/scripts were created. Existing workspace edits were preserved. The scripts verify evidence, replay cycle 1 through current code, render diagnostic annotations, and summarize traces; they do not wire production tracking or alter decisions. No new collision reproduction, RTSP capture, alarm action, model training or operational database write was performed.

To reproduce the diagnostic artifacts from the repository root, run the new directory's `verify.py`, `run_baseline.py`, `review_cycles.py`, then `finalize.py` using the backend virtualenv. Outputs belong only to that diagnostic directory. `verify.py` stops if frame/pixel/sidecar integrity fails; the original recording is never regenerated. The finalizer preserves explicit unknowns and checks protected hashes again.

## Phase 1 Verdict

**MULTIPLE_BASELINE_LIMITATIONS**

The approach participants can be distinguished, but current accepted detector input cannot support their pair, production has no persistent identities or pair-owned streak, the actual visited pairs are unrelated, and post-overlap physical identity/contact remain unresolved. Phase 2 was not started.
