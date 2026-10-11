# Phase 4 — Tapo Replay-Domain Vehicle Detector Pilot

**Verdict: INDEPENDENT_REPLAY_TRAINING_SOURCES_REQUIRED.** The accessible experimental chain is **traffic video → display → physical Tapo camera → authenticated Bago RTSP → CrashGuard**. This phase can investigate `TAPO_SCREEN_REPLAY_DOMAIN`; it cannot establish native roadside CCTV accuracy. The [read-only source audit](../backend/validation/tapo_replay_detector_phase4/source_audit.json) found **zero training-eligible source videos** in the existing 145-video provenance inventory. The training-source gate therefore stopped the work before replay capture, frame extraction, annotation, model training, or protected Source B evaluation.

The revised user scope intentionally permits this replay-capture domain. It supersedes Stage B2's native-road eligibility requirement **for this experimental phase only**. Stage B2's observation that the current view is a screen replay remains true; its physical-road prerequisite is no longer the question here. No replay was started or changed during this audit.

## Environment Constraint

Native real-road access: **NO**, per the user's stated constraint. Accessible domain: **TAPO_SCREEN_REPLAY_DOMAIN**. The authorized active Bago camera record previously authenticated and decoded 1280×720 `/stream2` frames; its global Tapo profile is separate and has a credential mismatch. No camera connection or new capture was needed after the source gate failed. The [Stage B](tapo-rtsp-recovery-phase4-stage-b-2026-10-01.md) and [Stage B2](tapo-native-road-gate-phase4-stage-b2-2026-10-01.md) diagnostic frames are **not** independent training videos; their displayed source is not cleared, and they are quarantined diagnostic evidence.

## Phase 3 Baseline

Verdict: **DOMAIN_ADAPTED_DETECTOR_REQUIRED** for the studied Source B first interaction. Physical A accepted: **0/9 assessable frames**. Physical B accepted: **0/10**. A track: **NO**. B track: **NO**. True A↔B pair: **NO**. At a diagnostic 0.05 proposal cutoff, B appeared in 5/10 frames, but this did not pass current acceptance or establish a safe production threshold. See the [Phase 3 report](source-b-detector-bottleneck-phase3-2026-10-01.md); its physical envelopes are assistant-reviewed diagnostics, not independent human ground truth.

## Training Source Audit

The existing [source manifest](../backend/validation/cctv_detector_trajectory_pilot/source_manifest.csv) lists **145 present video files**: 62 project uploads/outputs/recordings, 46 CADP, and 37 Nexar. It marks all 145 `eligible_for_training=False` and `permission_status=UNRESOLVED`; 120 have evaluation overlap, 24 unresolved clearance, and one known training-seen relationship. These are file counts, not independent traffic-source counts. The older [readiness inventory](../backend/validation/cctv_detector_readiness/cctv_detector_readiness_report.md) also recorded zero approved detector-training sources. The new audit preserves each of the 25 unreserved CADP IDs and its existing clearance status; it does not promote them.

| Source | Provenance | Authorization | Existing-model relationship | Protected relationship | Eligibility |
|---|---|---|---|---|---|
| Source B and its crops, transcodes, Tapo recaptures or other derivatives | Known physical-pair screen replay and repeated stress case | Excluded by this task | Already repeatedly evaluated; model exposure is not a reason to train | **Protected evaluation only** | **PROTECTED_EVALUATION** |
| Phase 8C and derived imagery | Reserved positive/negative review and regression families | Excluded by this task | Prior experiments and labels overlap | **Protected evaluation only** | **PROTECTED_EVALUATION** |
| 62 project video files (`VIDEO-*`) | Uploads, annotated outputs, crash media and validation recordings; original source-family identity largely unresolved | Unresolved | Some derivative or previously evaluated relationships; no independent training clearance | Inventory reserves these for evaluation overlap | **PROTECTED_EVALUATION / TRAINING_INELIGIBLE** |
| 21 reserved CADP clips | CADP local short-clip collection | Local research/noncommercial terms require citation; specific training/derivative scope has not been cleared in project metadata | Cannot infer independence from existing models | Reserved evaluation overlap | **PROTECTED_EVALUATION** |
| 25 unreserved CADP clips | Same CADP collection; edited/montage/PTZ and cross-family lineage require individual review | **Unresolved** under the project's strict training-use gate | One clip family (`CADP-3VTdPoH5eGE`) is known to match classifier C1/C2 imagery; other upstream/model overlap is not proven absent | One is **TRAINING_SEEN**; 24 remain unresolved; none is cleared independent of all protected families | **24 AUTHORIZATION_UNRESOLVED; 1 TRAINING_SEEN_BY_EXISTING_MODEL** |
| 37 Nexar clips | Dashcam collection, not the fixed CCTV/replay chain; includes previously studied positive/negative intake | Local license restrictions need source-specific review | No local classifier training established for these clips; upstream generic-model overlap unknown | All 37 reserved for evaluation overlap in the manifest | **PROTECTED_EVALUATION** |
| Raw C1/C2 classifier frame archives and active crash-classification corpus | Upstream crash datasets; still images and event-derived frames, not independent replayable source videos | Rights and camera/event lineage unresolved | Current classifier-source exposure is established for its corpus | Train/test and regression overlap risk | **TRAINING_SEEN_BY_EXISTING_MODEL / TRAINING_INELIGIBLE** |
| Six `public/samples/` JPEGs | Frontend gallery/mock images, not source video sessions | Training rights and lineage not established | Model relationship unknown | Sample/demo/evaluation use | **TRAINING_INELIGIBLE** |
| Stage B/B2 Tapo diagnostic stills and four PNGs | Current physical camera viewing unidentified old displayed traffic footage | Underlying video authorization and independence unresolved | Underlying video relationship unknown | Diagnostic gate evidence; could be related to protected material | **AUTHORIZATION_UNRESOLVED; not dataset intake** |

The [CADP lineage review](../backend/validation/cctv_detector_pilot/cadp_provenance_lineage_report.md) found edited copies, montages and a classifier-training match, and explicitly did **not** certify independent source families or training permission. Its [local license assessment](../backend/validation/cctv_detector_pilot/cadp_license_evidence.md) describes research/noncommercial terms but leaves the project's model-training/derivative permission gate unresolved. A different filename, file hash, crop, encode, or Tapo screen recapture would not cure a source-family conflict. No web acquisition or new footage was substituted for missing cleared sources.

## Replay Dataset

Independent **training-eligible** source videos: **0**. Tapo training capture sessions: **0**. Human-verified replay frames: **0**. Vehicle boxes: **0**. The pilot `raw/` and `calibration/` directories remain empty. Four prior Stage B2 diagnostic frames exist only under `review/`; they are not training, validation, or test frames.

## Classes

Vehicle-detection target classes, with human-verified replay boxes currently available: car **0**, motorcycle **0**, truck **0**, bus **0**, bicycle **0**. No accident, collision, damage, or fallen-vehicle class was created. These zeros describe annotation availability, not what appears in any video.

## Leakage Audit

Source B absent from assembled training data: **PASS (empty dataset)**. Phase 8C absent: **PASS (empty dataset)**. Protected regressions absent: **PASS (empty dataset)**. Cross-split source leakage: **FAIL as an unestablished gate**—no source/session split or dataset exists to audit. Duplicate frame hashes and near-adjacent leakage: **NOT TESTABLE** without captured and selected frames. Training authorization: **FAIL**—no candidate is cleared. `REPLAY_DATA_LEAKAGE_CHECK = FAIL` as a **readiness gate**, not as a claim that actual cross-split duplication was found.

When cleared footage exists, assign original source-video families and Tapo capture sessions to train/validation/held-out test **before** sampling. Keep all replay passes, trims, crops and adjacent frames of one underlying video in the same split; record original-video ID and capture-session ID. Audit exact hashes plus perceptual/scene lineage against Source B, Phase 8C and protected regressions before any training export.

## Training Gate

**FAIL.** No independent source is currently `TRAINING_ELIGIBLE`; no permitted Tapo replay session, 300–600-frame diverse pilot, human-verified five-class boxes, source-family split, or passing leakage audit exists. The 25 unreserved CADP files are candidates for further permission and lineage work, **not** a cleared substitute. Accordingly the source gate stopped the sequence before camera capture or an annotation package containing actual frames.

The needed intake is **several (at least three) independent, non-protected normal-traffic source videos**, with documented owner/provider, explicit academic model-training and derivative-use permission (or other clear applicable grant), stable original-video/source-family IDs, and evidence they are not Source B, Phase 8C, regression scenes, their derivatives, or an already training-seen family. Prefer different road layouts and lighting and usable cars, motorcycles, trucks, buses, bicycles, small/distant and occluded vehicles where genuinely present. Prove the source families are independent before replaying them through the same display and physical Tapo. This is an intake requirement, not a promise that three videos alone will yield a defensible 300–600-frame dataset or held-out test.

## Offline Candidate

**NOT RUN.** No YOLOv8n fine-tuning, model selection, weights, or threshold changes. `backend/best.pt` remains the production model.

## Held-Out Replay Evaluation

Current generic detector on a new held-out replay dataset: **NOT RUN; no eligible held-out replay set**. Frozen candidate: **NOT RUN; none trained or selected**. Precision, per-class recall, false proposals/frame, accepted recall, small-vehicle recall, and CPU latency are unavailable for this phase.

## Protected Source B Evaluation

**NOT RUN in this phase; no frozen candidate exists.** New A raw/accepted recall, B raw/accepted recall, best confidence, recovered tracks and simultaneous A+B observations are unavailable. The Phase 3 generic-detector baseline above is historical and is not a candidate result. Source B remains a known, repeatedly studied stress set, not an untouched final test; it cannot select epochs, hyperparameters, architecture, confidence cutoff, or weights.

## Phase 2 Offline Replay

**NOT RUN in this phase.** No candidate detections exist to pass through the conservative tracker, PairHitLedger or interaction verifier. A/B tracks, true pair, pair-owned hits, 3-hit/5-second feasibility, interaction support and new negative false confirmations are **not measured**. The [Phase 2 study](source-b-participant-continuity-phase2-2026-09-30.md) remains prior generic-detector evidence.

## Production Pair-Safety Regression

Expected: **FAIL**. Actual: **FAIL, one targeted assertion**. The existing expected-failure test was run with its marker disabled **in memory only**, without editing the file. Three distinct physical pairs still accumulate three scene-level hits and the production path returns `confirmed_crash`; the assertion rejecting that result failed. The known production defect remains unresolved, independently of this detector-data gate.

## Production Changes

Detector: **UNCHANGED**. Collision logic: **UNCHANGED**. Thresholds: **UNCHANGED**. Pair engine: **NOT INTEGRATED**. Alarm: **UNCHANGED**. Incident pipeline: **UNCHANGED**. No model, database camera record, global profile, source video, or protected annotation was modified. The [protection snapshot](../backend/validation/tapo_replay_detector_phase4/protected_before.json) covers **286** prior paths including Source B, Phase 8C, Phase 1–3, Stage A/B/B2 evidence, production model/logic and alarms; the [final rehash](../backend/validation/tapo_replay_detector_phase4/protection_audit.json) reports zero changed paths.

## Scope Limitation

Native roadside CCTV validation: **NOT ESTABLISHED**. Real-world deployment readiness: **NOT ESTABLISHED**. This phase evaluates only whether a **TAPO_SCREEN_REPLAY_DOMAIN** pilot can be assembled safely; it did **not** train or evaluate a detector. Even a later gain on Source B would support a controlled prototype/demo claim for the displayed-video chain, not general roadside accuracy, native CCTV validation, multi-camera generalization or production release.

## Phase 4 Verdict

**INDEPENDENT_REPLAY_TRAINING_SOURCES_REQUIRED**

Stop. Obtain and document training-eligible independent normal-traffic videos before Tapo replay capture. Keep Source B, Phase 8C and all derivatives reserved for evaluation; then resolve permission, source-family lineage, split integrity and human labels before any offline training.
