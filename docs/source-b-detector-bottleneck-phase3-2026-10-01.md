# Phase 3 — Detector and Acceptance Bottleneck

Offline diagnosis only, 2026-10-01. The assessable first Source B interaction supplies **no accepted observation of either physical participant** under the present detector path. Lower diagnostic confidence extraction reveals some B signal but does not produce a safe pair pipeline. Source B labels are assistant-reviewed diagnostic envelopes, **not independently human-verified ground truth**. The capture is a screen replay and a known, repeatedly studied stress case, not an untouched performance test.

Artifacts: [Phase 3 evidence](../backend/validation/source_b_detector_phase3_20261001/), [Phase 1 physical labels and worker trace](../backend/validation/source_b_physical_pair_baseline_20260930/), [Phase 2 conservative offline prototype](../backend/validation/source_b_continuity_phase2_20260930/).

## Phase 1/2 Baseline

- A accepted seed: **none**; one raw frame-41 box at 0.3872904 is below the 0.40 acceptance threshold.
- B proposal at production cutoff: **none**.
- Recovered A track: **NO**. Recovered B track: **NO**. True pair: **NO**.
- First-cycle assessable approach/overlap: A **9** frames (37–45), B **10** (36–45). Post-overlap individual boxes are unassessable, not misses.

## Production Detector Path

The live RTSP `LiveCameraMonitor._analyze_current_frame` copies the latest decoded **native BGR 1280×720** frame and passes it to the primary `backend/best.pt` YOLO at `imgsz=640` for general detections, then to the crash classifier at `imgsz=224`. Vehicle boxes come from the **separate** root `yolov8n.pt` model if loaded; otherwise the primary model results are the fallback. The default model path is set by `VEHICLE_MODEL_PATH`, and the Phase 1 run resolved it to the root file. The local weights are generic COCO YOLOv8n detection weights (80 classes, 3,157,200 parameters); `best.pt` and `yolov8n.pt` were reported SHA-identical in the earlier candidate study. No detector training is evident for this CCTV scene.

The separate call is `vehicle_model.predict(frame, verbose=False)` without an explicit `conf` or `imgsz`: the installed YOLO defaults observed in Phase 1 are **0.25 proposal confidence**, **640 input size**, class-aware NMS at **IoU 0.70**, `max_det=300`. These are returned post-NMS boxes, not all neural-network pre-NMS proposals. The production extractor normalizes labels and allows `car`, `motorcycle`, `bus`, `truck`, `bicycle`, `vehicle`, `van`, `suv`, `automobile` and `auto`. It rejects scores below **0.40**, clamps boxes to frame bounds and rejects nonpositive geometry. An empty `CRASH_ROI_NORMALIZED` accepts the full frame; a configured ROI would require the box center inside it. There is no participant-specific context-support rule in this live path. The one retry with extractor confidence **0.15** occurs only if no vehicle is accepted and the classifier suspects a crash; it does **not** lower YOLO's proposal cutoff and is not a reliable recovery path when unrelated vehicles are already accepted. Frame quality, classifier, proximity and temporal checks follow acceptance.

These are distinct settings: **model proposal cutoff 0.25** versus **production acceptance 0.40**. Neither was changed.

## Current Baseline

Phase 1 fresh inference and the Phase 2 exact extractor/ROI recheck reproduce A **1/9 raw, 0/9 accepted**, best 0.3872904 at frame 41, rejected `below_vehicle_confidence`. B is **0/10 raw, 0/10 accepted**; its best confidence at this proposal cutoff is N/A and no acceptance rejection can be attributed to a box that does not exist. Both true-participant boxes are absent in the same frame at the production cutoff. All **155 visited dense pair comparisons** in Phase 1 involve unrelated traffic. This confirms the Phase 2 baseline, with its scope limited to the first cycle.

## Diagnostic Proposal Sweep

The 0.25 row uses the Phase 1 exact worker trace. Rows 0.20, 0.15 and 0.10 threshold the earlier **actual 0.10 YOLO run** on the same protected native frames, model and `imgsz=640`; the 0.25 returned vehicle boxes were checked against the older run on selected frames to within 1e-5 score and >0.99 box IoU. Filtering an already-NMSed 0.10 result is a **diagnostic extraction**, not proof that independent YOLO calls at each cutoff would have identical NMS outputs. The 0.05 row is a **fresh YOLO call on all first-cycle frames 0–87**, `conf=0.05, imgsz=640, iou=0.70`, with [complete returned boxes](../backend/validation/source_b_detector_phase3_20261001/fresh_005.jsonl). The current production acceptance rule is then applied without alteration. Matching uses frame-level IoU ≥0.30 against Phase 1 A/B envelopes; duplicate boxes on one frame count as only one recalled frame. Observations after frame 45 are not assigned to A/B.

“Unrelated” below is a proposal matched to a labeled U vehicle at IoU ≥0.20. “Region possible” falls within broad unrelated-traffic regions and is **not verified as a real or false vehicle**. “Unmatched” is unclassified, **not an established false-positive count**. These categories count vehicle-class returned proposals in frames 30–70 only; nonvehicle class proposals were excluded from the diagnostic tracker. The Phase 1/2 raw telemetry counted nonvehicle proposals too, so its 264 dense raw rows are not directly comparable with this table's 220 vehicle proposals at 0.25.

| Configuration | Proposal cutoff | Input size / mode | A raw recall | B raw recall | Simultaneous A+B raw | A track | B track | True pair | Unrelated / region possible / unmatched (dense) | False confirmations | CPU inference time | Production candidate |
|---|---:|---|---:|---:|---:|---|---|---|---:|---:|---|---|
| Current | 0.25 | native/640 | 1/9 | 0/10 | 0 | NO | NO | NO | 181 / 38 / 0 | 0 | 433.5 ms mean paired sample* | **NO** |
| Cached extraction | 0.20 | native/640 | 1/9 | 0/10 | 0 | NO | NO | NO | 194 / 54 / 5 | 0 | No independent call* | **NO** |
| Cached extraction | 0.15 | native/640 | 1/9 | 1/10 | 1 | NO | NO | NO | 207 / 82 / 13 | 0 | No independent call* | **NO** |
| Cached extraction | 0.10 | native/640 | 2/9 | 3/10 | 1 | NO | NO | NO | 228 / 146 / 26 | 0 | 51.6 ms old contended cache mean* | **NO** |
| Fresh extraction | 0.05 | native/640 | 2/9 | 5/10 | 1 | NO | NO | NO | 278 / 335 / 76 | 0 | 282.1 ms mean paired sample* | **NO** |

The dense vehicle proposal count grows **220 → 254 → 304 → 405 → 699**, or **5.37 → 6.20 → 7.41 → 9.88 → 17.05 proposals/frame** across the 41 annotated frames. Best A score remains **0.3872904**. Best B score is **0.1637074** at cutoffs ≤0.15. Phase 3 [results JSON](../backend/validation/source_b_detector_phase3_20261001/results.json), [CSV](../backend/validation/source_b_detector_phase3_20261001/evidence_table.csv) and per-configuration proposal audits retain all frames, boxes, scores, assignments and rejection reasons.

## Detector vs Acceptance Failure

**A:** At 0.25, eight of nine assessable frames have no matching proposal: detector proposal failure. Its only matching box exists but is rejected by the **0.40 vehicle-confidence rule**: acceptance failure at frame 41. At 0.10/0.05 there is one additional A frame (42, score 0.1142973), also rejected. The extra 0.05 A box at frame 41 is a duplicate observation, not a new recalled frame.

**B:** At 0.25/0.20, no matching proposal exists: detector proposal failure. At 0.15 one B frame appears; at 0.10 three; at 0.05 five (37, 39, 40, 41, 43), best score 0.1637074. **Every returned B match** is rejected by the unchanged 0.40 confidence rule. Thus B is not completely invisible to the model, but its weak, incomplete output fails both proposal supply at production cutoff and acceptance. No class, degenerate-geometry or ROI rejection explains a matched A/B box. Class/geometry/ROI guards should remain.

## Previous Resolution / ROI / Tiling Evidence

The completed [Safe Fix Candidate Study](../backend/validation/live_cctv_audit/fix_candidate_report.md) already ran all 1,399 Source B frames at a 0.10 research floor with the same native arrays, generic YOLO, physical first-cycle labels, current 0.40 acceptance, and 20 negative groups. It compared `imgsz` **640, 768, 960, 1280**, two overlapping full-height **640 tiles**, and a broad **road ROI [0,0.25,1,1]**. This is sufficient to avoid duplicating its expensive scale/region sweep.

| Prior mode | First-cycle A raw/9 | First-cycle B raw/10 | First-cycle accepted A/B | Earlier serial detector mean |
|---|---:|---:|---:|---:|
| native640 | 2 | 3 | 0 / 0 | 107.7 ms |
| native768 | 0 | 1 | 0 / 0 | 124.7 ms |
| native960 | 0 | 1 | 0 / 0 | 170.3 ms |
| native1280 | 0 | 2 | 0 / 0 | 293.1 ms |
| tiles2_640 | 0 | 0 | 0 / 0 | 254.2 ms |
| roadroi640 | 0 | 1 | 0 / 0 | 64.3 ms |

No mode supplied accepted A+B, a recovered true pair, or a correct Source B confirmation. The same study found a **new false confirmation** on a near-miss when experimental raw-history admission was used; its ROI option wrongly attributed a human-verified Phase 8C positive to a foreground distractor. Faster sampling increases opportunities but cannot turn missing boxes into observations. The [architecture study](../backend/validation/live_cctv_architecture_study/architecture_study_report.md) found some cycle-4 experimental true-pair hypotheses but never selected the real pair and did not establish a safe fix. These earlier studies use different prototype logic; they are supporting prior evidence, not substitutes for this Phase 3 Phase-2-prototype replay.

## New Bounded Experiments

The only new detector run is the **0.05 native/640 first-cycle pass**. It detects B on 5/10 assessable frames, but never above 0.164 and never accepted. It adds no new A recall relative to the older 0.10 cache. There is still only **one simultaneous raw A+B frame (41)**, no simultaneous accepted frame, and no usable post-overlap identities. Neither repeated B-only weak boxes nor a single jointly weak frame is a safe production threshold candidate. `TRACKING_CANNOT_RECOVER_AN_UNOBSERVED_PARTICIPANT` applies at the production 0.25 setting; at lower cutoffs B has weak observations, but tracking still cannot fabricate accepted seeds or missing A/B frames.

## Participant Recovery

For **every tested configuration**, A track: **NO**; B track: **NO**; true Pair(A,B): **NO**. At 0.05 B's frames 39–41 provide a short, partly consecutive weak sequence, but there are **zero prior accepted B observations**. A has only two recalled frames and no accepted observation. The Phase 2 prototype requires at least two accepted observations before weak raw support can extend an identity, unique bounded class/geometry/motion association, and no ambiguous duplicate. It never admits isolated weak boxes as participant seeds. Thus the extra weak B output is diagnostic partial signal, not `TEMPORALLY_SUPPORTED_WEAK_PROPOSAL` in the Phase 2 contract.

## Phase 2 Replay

All five vehicle-proposal streams were fed in timestamp order through the **unchanged Phase 2 `ConservativeTracker` and `PairExperiment`** with the saved real first-cycle classifier, frame-quality and scene-validity values. Physical labels were applied only after tracker/pair output. Pair-owned qualifying A+B hits: **0** each; three hits/five seconds feasible: **NO**; interaction evidence: **INSUFFICIENT**; conservative false confirmations: **0** on this 88-frame replay. The `PairHitLedger`, production 0.90 case classifier threshold, proximity predicate and Phase 2 interaction constants were not modified. Phase 1/2's separate ownership-only comparison still reaches false eligibility on unrelated queue traffic; a zero here is limited to this conservative offline prototype, **not proof of production safety**.

## Unrelated-Traffic Cost

Lower extraction adds known-unrelated U matches (**181 → 278**) and many broad-region boxes (**38 → 335**) in the dense window; unmatched boxes rise **0 → 76**. The 0.05 result is **+479 vehicle proposals** over 41 dense frames versus current 0.25. Those counts are actual returned vehicle-class boxes, not verified false-object rates. Offline pair-frame observations change **282 → 161** across the 88-frame first cycle as more weak/overlapping candidates trigger conservative ambiguity and association rejection; the reduction is not a safety improvement or better A/B recovery. The prior 20-group negative study's raw-history admission failure makes globally lowering acceptance particularly unsafe. A broader fresh negative set and full-rate queue/congestion replay would be required for any future admission rule.

## Current Model Assessment

**MULTIPLE_DETECTOR_AND_ACCEPTANCE_BLOCKERS.** The generic model provides partial weak A/B signal, but misses most participant frames even at 0.05 and supplies only one simultaneous raw frame. Current 0.40 acceptance then rejects all matching boxes. The evidence does **not** show that acceptance alone is the primary blocker: admitting every weak box still cannot supply a conservative true pair or post-interaction observations.

The scene's measured native-frame envelopes are roughly A **100–191×99–183 px** and B **90–132×72–81 px**, about half that at 640-width letterbox content. It is a nighttime, perspective-compressed, motion-blurred, glare-affected **screen recapture** with overlapping participants; these are observed conditions, not independently proven individual causes of failure. The generic detector's reliable operating range on fresh native Tapo traffic has not yet been measured.

## Domain Adaptation Requirement

**REQUIRED for the next detector research phase.** None of the tested current-model cutoff, scale, tiling or broad ROI configurations establishes sufficient accepted A+B continuity. This is a scoped Source B conclusion, not a claim that every CCTV scene requires retraining. A separately named CCTV vehicle detector must be evaluated offline before any model-selection proposal, with ordinary-traffic vehicle boxes and distractors rather than “accident appearance” labels. No model was trained or downloaded in Phase 3.

## Acceptance Change Requirement

**INCONCLUSIVE for a future adapted detector.** The current 0.40 rule demonstrably rejects every *current-model* A/B proposal found here, but an improved detector may produce stronger boxes that pass it. There is **no safe acceptance-change candidate** from this sweep. If later still needed, scope a separate temporal evidence tier to an already-established, unambiguous accepted track; never allow an isolated weak box to seed/confirm. Quantify the true A/B observations regained, unrelated and unmatched admissions, identity swaps, queue/near-miss/foreground-distractor false confirmations, and CPU/multicamera cost on development and held-out negatives before proposing any production change. Keep class, geometry, ROI, pair and interaction guards.

## Proposed Next Step

**Phase 4 should be the Tapo detector-data/domain-adaptation phase, not production integration.** First verify fresh real-traffic provenance and training-use authorization, then collect and annotate a small pilot, validate its labels/leakage, and only afterward consider a separately authorized model training/evaluation experiment. Any future acceptance design and production pair-ownership repair remain separate safety gates. Production cannot be deployed while the scene-level streak defect persists. Stop after Phase 3.

## Tapo Data Requirement

[Existing pilot metadata](../backend/data/tapo_domain_pilot/metadata/) has a capture plan, prepared manifests and verification, but **zero recorded sessions, zero calibration frames, no completed vehicle annotations and no training**. The metadata marks training authorization pending. The camera did not need to be online and no network/camera capture was attempted here. The proposed pilot uses **one existing Tapo camera** for development footage; training footage does **not** add another operational CrashGuard camera.

Smallest defensible next intake: three naturally separated real-traffic sessions of about ten minutes each, subject to visibility, authorization and storage; preserve native frames plus per-frame host UTC/monotonic time, source PTS if available, session lineage and hashes. Review one fresh scene to exclude monitor replay. Allocate whole sessions or separated time blocks **before** sampling; keep related trajectories/near duplicates in one split. Begin with at most **20 diverse, fully reviewed calibration frames** to validate the five-class annotation rules, then expand only if actual footage covers ordinary moving/parked/congested cars, motorcycles, trucks/buses when present, small/distant and partially occluded vehicles, plus available day/night conditions. Annotate **all visible vehicles** and difficult/ignore states, not merely crash-like objects. Source B, its derivatives, Phase 8C, screen-replayed collisions and all prior regression families remain excluded from training and tuning. Source B is known stress evidence, not an untouched final test. One physical Tapo camera permits same-camera session validation only; independent-camera generalization and release claims require later new-camera evaluation. No capture, extraction, annotation or training occurred in this phase.

## Performance

The [paired CPU timing](../backend/validation/source_b_detector_phase3_20261001/paired_cpu_timing.json) uses ten fixed first-cycle frames, three warm-up calls per cutoff, two PyTorch threads, one OpenCV thread, serial detector calls, native input and YOLO 640: measured means **433.5 ms at 0.25** and **282.1 ms at 0.05** (medians 438.2 and 219.5 ms). The inverted ordering illustrates run-order/machine-load variability; it does **not** establish that 0.05 is faster. The fresh full 88-frame 0.05 run averaged **857.8 ms** including warm-up and current workload; the older 0.10 cache averaged **51.6 ms** under different load and is not comparable. The earlier controlled 48-frame serial study measured 107.7/124.7/170.3/293.1 ms for 640/768/960/1280 and 254.2/64.3 ms for tiling/ROI. Detector inference time is distinct from Source B's **11.632 recorded frames/s**, nominal 15 FPS, and actual production worker cycle rate (not measured in this phase). None of these timings authorizes a live cadence claim.

## Tests

- Phase 3 analysis (including re-execution of the current pure extractor on every matched diagnostic A/B box), Phase 2 offline, pair-ledger and relevant detector/preprocessing tests: **67 passed**.
- Existing collision, crash-decision, classifier, temporal verifier, vehicle tracking and logical continuity tests: **134 run, 133 passed, one expected failure** (the known production pair-safety test).
- Running that exact pair-safety test directly with the expected-failure marker disabled in memory (without editing the test) yields **1 failure**: `confirmed_crash` is returned after three different physical pairs contribute one scene hit each. This remains an unresolved production defect.
- Study integrity: **151 protected paths rehashed, zero changed**; see [protection audit](../backend/validation/source_b_detector_phase3_20261001/protection_audit.json).

## Production Pair-Safety Regression

**FAIL.** The production `hit_window` is still scene-level; the pair-specific safety assertion still fails when actually evaluated. Its `@unittest.expectedFailure` annotation is unchanged. The Phase 2 ledger's bookkeeping and Phase 3 offline zero false confirmations do not make production safe.

## Protected Assets

Source B: **UNCHANGED**. Phase 8C: **UNCHANGED**. Models: **UNCHANGED**. Training: **NONE**. Existing Phase 1/2 evidence and audited production files: **UNCHANGED**. The Phase 3 script wrote only under its new validation directory; this report is the sole new documentation file.

## Production Changes

Collision logic: **UNCHANGED**. Detector configuration: **UNCHANGED**. Thresholds: **UNCHANGED**. Alarm, fresh-incident path and database camera records: **UNCHANGED**. Phase 2 prototype integration: **NONE**.

## Phase 3 Verdict

**DOMAIN_ADAPTED_DETECTOR_REQUIRED**

Route Phase 4 to fresh real Tapo ordinary-traffic detector data and domain adaptation research. Preserve 0.25/0.40 production settings and the production pair-safety failure until separately validated work resolves them.
