# Phase 4 — Tapo Domain Vehicle Detector Pilot

**Stage A verdict: CAMERA_NOT_AVAILABLE.** The saved Tapo host accepts TCP connections on RTSP port 554, but neither the saved `stream1` nor the historically documented `stream2` path opens with the saved camera account. No frames decoded. The physical view, resolution and cadence therefore remain unverified. Capture, calibration, annotation, splitting, training and evaluation were stopped without substituting Source B or any screen replay. The failure does not establish whether the cause is credentials, camera RTSP settings, stream path or another decoder/transport issue.

This report follows the completed [Phase 1 baseline](source-b-physical-pair-baseline-2026-09-30.md), [Phase 2 continuity study](source-b-participant-continuity-phase2-2026-09-30.md), [Phase 3 detector study](source-b-detector-bottleneck-phase3-2026-10-01.md), existing [detector readiness study](../backend/validation/cctv_detector_readiness/cctv_detector_readiness_report.md), and [Tapo preparation](../backend/data/tapo_domain_pilot/metadata/capture_plan.md). No prior evidence was overwritten.

## Phase 3 Baseline

Verdict: **DOMAIN_ADAPTED_DETECTOR_REQUIRED**. Source B A accepted: **0/9**; B accepted: **0/10**. A track: **NO**. B track: **NO**. True pair: **NO**. At offline diagnostic proposal cutoff 0.05, B appears on 5/10 assessable frames, but neither participant is accepted or tracked. That cutoff is **not** a production candidate. Phase 3's 151 protected paths were unchanged and its production pair-safety regression failed. [Phase 3 measurements](../backend/validation/source_b_detector_phase3_20261001/results.json).

## Camera Preflight

Saved configuration source: `backend/local_camera_config.json`, read in memory without printing credentials. The saved Tapo host is `192.168.1.17`, port `554`, configured stream `stream1`; an earlier Tapo pilot referred to `stream2`. The new [preflight record](../backend/validation/tapo_detector_phase4_stage_a_20261001/preflight.json) contains **no username, password or credential-bearing URL**.

- Reachable at TCP level: **YES**, one successful bounded connection on 2026-10-01 local time.
- RTSP opens: **NO** for the saved `stream1`; **NO** for the documented `stream2`, using the saved account without bypassing authentication.
- Frames decode: **0**. Native dimensions: **not measured**. Reported FPS: **not measured**. Host receive cadence: **not measured**.
- Native real-road view: **NO verification possible**. No scene snapshot was obtained. The prior history of this Tapo camera filming a screen cannot establish its present view.

The earlier September 16 checks timed out at TCP. Current TCP reachability is a change in observed network behavior; it does not make the RTSP stream usable. No camera/database setting was changed.

## Fresh Capture

Sessions: **0**. Total duration: **0 seconds**. Frames: **0**. Day/night conditions: **unobserved**. Traffic density, vehicle classes and scene provenance: **unobserved**. No recording or metadata sidecar was created. The existing `raw/` and `calibration/` directories remain empty. The target remains at least four distinct real-traffic sessions of approximately 10–20 minutes, totaling roughly 45–60+ minutes when practical, with native frame quality and per-frame host timing; those are future targets, not achieved counts.

## Training Provenance

Native Tapo real traffic: **NOT VERIFIED / 0 eligible frames**. Screen replay included in Stage A training data: **NO**; there is no training data. Source B included: **NO**. Phase 8C included: **NO**. Existing regression footage included: **NO**. No fresh footage exists to run visual, exact-hash or perceptual duplicate checks. `DATA_LEAKAGE_CHECK = FAIL` as a training gate because no dataset/split exists to audit; this is **not** a detected cross-split duplicate.

The prior [Tapo pilot audit](../backend/validation/cctv_detector_trajectory_pilot/tapo_domain_pilot_report.md) also recorded zero sessions and zero calibration frames. Its training-use authorization field is pending. The current request authorizes this preflight and, if feasible, fresh capture; it does not itself supply human verification or resolve the earlier training-use provenance field. No training decision is needed while the camera stream is unavailable.

## Calibration Set

Frames: **0/20**. Status: **NOT STARTED — RTSP stream unavailable**. Exactly 20 real, diverse native Tapo frames must be selected from verified sessions before calibration annotation can begin. None was fabricated or taken from Source B/Phase 8C.

## Annotation Dataset

Human-verified frames: **0**. Vehicle boxes: **0**. Car: **0**. Motorcycle: **0**. Truck: **0**. Bus: **0**. Bicycle: **0**. These are dataset counts, not statements that the physical road lacks these classes. Existing Tapo annotation and capture manifests have headers only; no sampled frames or verification records were found. There are no model prelabels and no AI-generated labels presented as `HUMAN_VERIFIED`.

The existing [five-class annotation specification](../backend/validation/cctv_detector_readiness/annotation_spec.md) and [Tapo capture plan](../backend/data/tapo_domain_pilot/metadata/capture_plan.md) remain the workflow references. Once a real scene and sessions are verified, frame selection must retain session/frame/time lineage, use tight visible-vehicle boxes, mark partial occlusion/truncation/blur and uncertain class explicitly, keep motorcycle body distinct from rider-only pixels, and annotate parked, small and overlapping vehicles where supportable. The model classes are car, motorcycle, truck, bus and bicycle; there is no accident/damage class. Every future prelabel begins `UNVERIFIED` and requires an identifiable human reviewer before training export. A new annotation workspace was **not** populated after the camera stop condition; there is no frame to launch for review.

## Split Integrity

Session/time-block split: **NOT RUN — 0 sessions**. Hash leakage across splits: **NOT RUN — 0 frames/splits**. Protected evidence leakage into assembled training data: **PASS in the limited sense that no data was assembled**; future intake still requires exact and near-duplicate checks against protected families. Training-gate leakage result: **FAIL / NOT ESTABLISHED**. When capture becomes possible, assign entire separate sessions or time blocks to train/validation/held-out test **before** sampling and keep the same vehicle episode and adjacent frames in one partition. One Tapo camera cannot establish independent-camera generalization.

## Training Gate

**FAIL.** Reasons: no open RTSP stream, no verified native road footage, no 20-frame calibration set, no human-verified annotations, no defensible 300–600-frame single-camera pilot dataset, no session split or leakage audit. Source B, Phase 8C and screen replays remain excluded. Training was not attempted.

## Candidate Training

**NOT RUN.** No base weights were loaded for training, no candidate weights were produced, and no production model was replaced.

## Held-Out Native Tapo Evaluation

**NOT RUN.** There is no held-out native Tapo session or trained candidate. Precision, recall, per-class performance, false proposals and CPU comparison are unavailable; no diagnostic 0.05 result was substituted.

## Protected Source B Stress Test

**NOT RUN in Stage A.** No candidate was selected or frozen. The Phase 3 generic-detector numbers remain the baseline, not a new candidate evaluation. Source B was not used for training, validation, early stopping, hyperparameter or threshold selection.

## Phase 2 Offline Replay

**NOT RUN in Stage A.** No candidate detections exist. A track, B track, true pair, pair hits, interaction and unrelated false confirmations for a new candidate are **N/A**; Phase 2's prior generic-detector replay remains unchanged.

## Performance

Camera TCP port: reachable. RTSP decode throughput, source FPS, frame dimensions, host receive cadence, detector inference time, CPU and memory comparison: **not measured** because the stream did not open and no candidate was trained. Container FPS, host capture FPS, detector FPS and production collision-cycle rate must be reported separately when footage and a model actually exist.

## Production Pair-Safety Regression

**FAIL**, as expected with production unchanged. The unchanged assertion, run directly with its expected-failure marker disabled **in memory only**, returned `confirmed_crash` after three different physical pairs each supplied one scene-level hit. One test ran, one failure. The test file was not edited.

## Production Changes

Collision worker: **UNCHANGED**. Production detector: **UNCHANGED**. Production thresholds: **UNCHANGED**. Pair engine: **NOT INTEGRATED**. Alarm: **UNCHANGED**. Incident pipeline: **UNCHANGED**. Camera settings/database records: **UNCHANGED**. No production incident or alarm was triggered.

## Protected Assets

Before preflight, [257 protected paths](../backend/validation/tapo_detector_phase4_stage_a_20261001/protected_before.json) were hashed, including Source B capture and evidence, all Phase 8C annotation-area files, Phase 1/2/3 artifacts, existing weights, production collision code and alarm assets. The [final rehash](../backend/validation/tapo_detector_phase4_stage_a_20261001/protection_audit.json) found **zero changed paths**. Source B: **UNCHANGED**. Phase 8C: **UNCHANGED**. Phase 1/2/3: **UNCHANGED**. Existing production models: **UNCHANGED**. Alarm: **UNCHANGED**. Training: **NONE**.

## Phase 4 Stage A Verdict

**CAMERA_NOT_AVAILABLE**

Stage A stops here. To resume fresh native collection, restore an authenticated RTSP stream from the saved Tapo camera, then inspect a newly decoded frame to verify it points at real road traffic rather than a screen. After that, the next gate is actual multi-session capture and human-verified five-class vehicle annotation. No protected footage should be substituted while the stream remains unavailable.
