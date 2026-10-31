# CCD collision diagnostic report

Date: 2026-10-20, Asia/Manila  
Repository: `C:\Users\Lenovo\Desktop\MyCrushguard`  
Branch: `work/track-identity-stabilization-2026-10-12`  
HEAD: `ebc93333`  
Scope: diagnosis only; current working-tree production source was inspected, including pre-existing uncommitted work.

## Result and evidence boundary

**The requested CCD replay could not be performed: no local CCD clip collection paired with verified crash-frame annotations and its split reservations was located in the inspected paths.** A dataset-location question was sent during discovery; no CCD path was supplied before this report was prepared.

This is an availability and production-gate audit, not a completed empirical CCD collision study. It does not establish which production subsystem causes real CCD collisions to fail. None of the detector, tracking, collision, or sampling failure verdicts can be supported without the requested clips and annotations.

No training, inference, threshold changes, production fixes, dataset reassignment, commits, or pushes were performed in this diagnosis. Existing modified production files from the preceding UI/evidence/alarm task were not reverted or changed by this diagnosis.

## Local dataset discovery

Searched the project and the user's Desktop, Downloads, Documents, OneDrive, and Videos locations. Dependency, build, interpreter, and Git directories were pruned. Additional checks covered the root entries of `C:\work`, `C:\opt`, the local Ultralytics checkout, and local cache directory names. This is a documented local search, not a claim that every possible location on the computer was inspected.

Machine-readable evidence is saved in [availability_audit.json](backend/validation/ccd_collision_diagnostic_20261020/availability_audit.json), including inspected archive contents, media parent directories, source/configuration fingerprints, reservation-manifest fingerprints, and any search errors. No credentials or general environment-file contents are included.

| Located material | Observed contents | Suitability for this CCD study |
|---|---|---|
| `dataset/confirmed_crash/` | Only `.gitkeep` | No crash clips available here |
| `Downloads/carcrash1cctv/` and `Downloads/archive (4).zip` | Train/validation/test still-image collection, including names such as `test10_33.jpg` | No verified source-FPS/positive-frame manifest located; category labels are insufficient to reconstruct a temporal clip |
| `Downloads/carcrash2cctv/` and `Downloads/archive (3).zip` | Accident/non-accident still images and severity-score material | No verified CCD source-clip timing or crash-participant annotations located |
| `backend/datasets/crash_classification/` | Existing classifier image splits | Training/validation/test reservations left untouched; not converted into artificial clips |
| `backend/validation/phase8b/incoming/cadp_pilot/` | CADP media | Not CCD; excluded |
| `backend/validation/phase8/incoming/nexar/` | Nexar positive/negative media | Not CCD; excluded |
| `backend/data/tapo_replay_pilot/` | Camera/replay studies and other source families | No verified CCD mapping located; excluded |
| Project uploads/outputs and Downloads videos | Individual uploads, generated media, and unrelated videos | No verified CCD clip/annotation/split mapping located; excluded |
| `Desktop/Sentinel/SENTINEL-AI/python/data/video_clips/` | UUID-named application clips | No verified CCD mapping located; excluded |

Existing historical reports/manifests were treated as discovery pointers, not as fresh CCD results. In particular, old replay scripts use different sampling or tracking paths; their reported outcomes cannot substitute for a run of the current `CollisionObservationSession` pipeline.

CCD was not mixed with AI City, VRU, CADP, Nexar, the classifier image collections, or camera demonstration material. No data was downloaded to replace the requested existing local collection.

## Requested subset and measured outcomes

| Quantity | Result |
|---|---|
| Verified CCD positive clips located | 0 in the inspected locations |
| Crash-positive clips selected/analyzed | **0**; requested 20–50 not achieved |
| CCD normal controls selected/analyzed | **0**; requested minimum 10 not achieved |
| Native/source-resolution positive replays | 0 |
| 2 FPS comparison replays | 0 |
| Correctly confirmable crash clips under current logic | **Not measured** |
| Rejected crash clips | **Not measured** |
| Rejection-reason counts | **Not measured** |
| Detector participant miss rate | **Not measured; denominator unavailable** |
| Tracking fragmentation rate | **Not measured; denominator unavailable** |
| Pair-continuity failures | **Not measured** |
| Temporal-sampling failures | **Not measured** |
| Normal-control false confirmations | **Not measured**, not zero |

The zero analyzed count describes missing eligible inputs. It is not evidence that the pipeline confirmed zero out of an evaluated CCD subset or rejected every collision.

Coverage of car–car, car–motorcycle, frontal/rear/side impacts, partial occlusion, small/distant participants, late impacts, and low-light/weather cases is **not assessable**. No representative failure examples or case IDs are invented.

## Per-clip records that remain unavailable

There are no eligible CCD per-clip records. Consequently, these requested fields remain unmeasured:

1. **Annotation:** authoritative clip ID, supplied complete positive-frame sequence, first/final positive frame, source FPS, decoded frame count, frame-index convention, and original train/validation/test reservation.
2. **Detections:** both involved participants' real detections, class, confidence, source-pixel bounding boxes, and participant-miss frame indices.
3. **Tracking:** physical-participant-to-track assignments before/contact/after impact, fragmentation, identity transfer, real observations, and predicted-only observations. Physical ID transfer cannot be inferred reliably from numeric track IDs alone without participant review/annotation.
4. **Pair evidence:** session-scoped canonical pair IDs, pixel center distances, production-normalized center/edge distances, IoU, timestamped relative velocity, convergence, opposing-motion diagnostics, approach trends, and contact/interaction histories.
5. **Decisions:** candidate creation, same-pair hit accumulation, before/contact/after evidence, confirmation progression, final `confirmed_crash` result, and the exact production gate and temporal-verifier rejection reasons.
6. **Sampling:** the corresponding native and 2 FPS records, retained/discarded source-frame indices, and evidence lost between sampling schedules.

Frame-level crash labels alone would not establish participant bounding-box recall or physical identity transfer. Where a supplied CCD manifest lacks participant boxes, a separately documented visual participant review is needed before reporting those rates.

## Current production path inspected

The active live path is implemented in `backend/main.py`, not `backend/carc.py`:

1. Take an owned copy of one decoded source frame and retain camera/session/sequence/timestamp/dimensions.
2. Compute frame quality, primary detections, crash-classifier probability, and vehicle detections on that frame.
3. Pass accepted vehicle observations and the exact source pixels through `SessionVehicleTracker`.
4. Filter collision-eligible detected observations and call `CollisionObservationSession.observe()` with the source timestamp and dimensions.
5. Accumulate pair-owned temporal evidence through `TemporalCrashVerifier` and `PairHitLedger`.
6. Pass the observed result to `evaluate_crash_case_decision()` with quality, vehicle/person, scene, temporal, duplicate-case, and cooldown inputs.

Relevant current source:

- [Live frame analysis and final decision](backend/main.py)
- [Session vehicle tracking](backend/services/session_vehicle_tracking.py)
- [Collision observation session](backend/services/collision_observation_session.py)
- [Temporal verifier](backend/services/temporal_crash_verifier.py)
- [Pair-owned hit ledger](backend/services/pair_hit_ledger.py)
- [Motion/distance features](backend/services/collision_features.py)
- [Latest-frame inference scheduler](backend/services/inference_execution.py)

No production module was imported for this availability audit, so application startup, camera workers, operational incident persistence, or model loading were not triggered by it. There was no production replay and no simulated confirmation substituted for one.

### Gates established by source inspection, not CCD measurements

- `CollisionObservationSession` accepts collision observations only when `detected` is true and `observationKind` is `DETECTED`. Predicted boxes do not supply collision motion evidence.
- Pair identity is derived from two distinct real track IDs; session state resets when session identity or image dimensions change.
- The default temporal verifier requires at least three observations per participant to establish approach history, then contact, at least two subsequent observations, post-contact motion disruption, and sufficient temporal score.
- The default post-contact observation window is 3 seconds. Track histories and pair histories are bounded; association ambiguity can create new identities rather than transfer an identity without evidence.
- The pair hit ledger requires three qualifying same-pair observations within the configured window by default. A classifier-positive streak across unrelated pairs does not supply that evidence.
- The final evaluator also enforces quality, vehicle/scene validity, and operational duplicate/cooldown gates. A visually positive frame or large classifier score is not sufficient by itself.

Verifier reasons present in current source include `no_interaction_candidate`, `no_consistent_approach`, `no_contact_candidate`, `observing_post_contact`, `no_post_contact_motion_disruption`, and `temporal_score_below_threshold`. Final evaluator reasons include `temporal_not_verified` and additional quality, scene, duplicate, and cooldown reasons. **These are possible diagnostic labels, not observed CCD rejection counts.**

## Native 10 FPS versus 2 FPS

The requested comparison has not been run. Native 10 FPS cannot be assumed from filenames or from an unrelated dataset's documentation. The source files/manifest must first establish actual FPS and the supplied label indexing.

There is also a cadence distinction in current source: `get_video_frame_skip()` defaults to `VIDEO_ANALYSIS_FPS=3.0`; the live worker defaults to `LIVE_CAMERA_DETECTION_INTERVAL_MS=0` and uses a shared latest-frame scheduler. `.env.example` illustrates a 500 ms live interval, but an example file does not establish effective running configuration. Thus **2 FPS is a requested diagnostic comparison, not a verified universal production rate**. The real analyzed source timestamps, configured overrides, inference load, and dropped frames would need to establish the observed live cadence.

For a genuinely native 10 FPS clip, a deterministic 2 FPS schedule beginning at source frame 0 would retain indices `0, 5, 10, ...`; source time remains `frame_index / 10`. Different sampling phases can retain different contact frames and should be reported separately if evaluated.

| Potential sampling mechanism | Consequence inferred from code | CCD cases establishing it |
|---|---|---|
| A contact frame falls between retained frames | Observed overlap/contact opportunity may disappear | Not measured |
| Three observations require a longer real-time span | At 10 FPS, three consecutive samples span 0.2 s; at 2 FPS they span 1.0 s | Not measured |
| Impact occurs close to the real end of a clip | Two post-contact samples may be unavailable; no continuation is permitted | Not measured |
| Participant association is ambiguous across a 0.5 s gap | Identity fragmentation may reset same-pair evidence; low-cadence tracking support means failure is not automatic | Not measured |
| Sampling removes supporting same-pair observations | Pair qualification or valid confirmation-window evidence may be lost | Not measured |

These are testable mechanisms, **not findings that any particular CCD collision failed for these reasons**. No clips were padded, repeated, interpolated, concatenated, or retimed. No still-image categories were presented as native-time clips.

## Evidence needed to finish the requested diagnosis

The missing prerequisite is the local CCD root/archive plus the verified annotation file and existing split-reservation manifest, or a precise path mapping to those assets. The supplied positive-frame list and its index convention must be retained verbatim and checked against decoded frame count/FPS.

Once those inputs are locatable, the diagnostic subset can be selected and recorded without moving or reassigning any files. Each clip must first run at true source temporal resolution; the 2 FPS run must use only actual retained source frames and timestamps. Independent camera/session/tracker/pair state is required per clip. Raw model inference outputs can be cached at native cadence and sampled for comparison; tracker/verifier state must then be recomputed independently for each cadence. No annotation-positive score may be substituted for the model's real classifier output, and no synthetic tracker histories may replace actual detected observations.

Only paired empirical outcomes and visually grounded participant correspondences would justify assigning detector, tracking, collision-logic, or temporal-sampling failure counts. Operational persistence should remain isolated from evaluation; no diagnostic replay should create live dispatcher incidents.

## Preservation

The availability audit records SHA-256 fingerprints of current production services, active model files, configuration, and discovered split/reservation manifests. A post-report verification checks that those fingerprints and the pre-existing tracked-change inventory are unchanged. The diagnosis writes only this report and its availability-audit artifact.

## Final verdict

INSUFFICIENT_EVIDENCE
