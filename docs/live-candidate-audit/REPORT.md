# Live Collision Candidate-to-Confirmation Audit

## Evidence boundary

This is a **partial event diagnosis**, not a recovered complete candidate-to-expiry trace.

1. A read-only observer recorded 114 distinct live inference results from **2026-09-16 00:50:28.637 to 00:51:58.449**, plus 345 timestamped preview snapshots. All results were `ignored / no_vehicle_detected`. The camera showed the desk/monitor rather than the collision replay. This is not a valid collision test, and its observations are not counted as impact observations.
2. Existing backend evidence from the earlier replay was found under `backend/outputs/`, approximately **00:42–00:46**. Thirteen saved, unannotated JPEG keyframes were inspected through an isolated model reproduction. These snapshots were saved selectively by the original backend; they omit candidate-only and rejected observations. They cannot supply the requested five seconds before and after a complete event.
3. Offline model outputs below are explicitly distinguished from original live outputs. JPEG compression and reproduction can change confidence slightly. The latest annotated original frame confirms that only three cars were accepted; the corresponding reproduction closely matches those car confidences.
4. The running process is PID **3556**, started **2026-09-15 23:46:13**, before the preceding restoration edits. It has not been restarted by this investigation. The older capture/inference implementation and the current working tree must not be conflated.

The original replay file or a fresh replay with the observer running is still required to establish the real counterpart, impact duration, exact state boundaries, and every live raw detection.

## 1. Candidate Trigger

Exact code path: `pre_temporal_positive` requires good frame quality, whole-frame Model 1 accident probability at or above the configured case threshold (default **0.90**), at least one accepted in-ROI vehicle, and a valid scene. These positives accumulate in a five-second window.

Before the default **three consecutive positives**, `evaluate_crash_case_decision(... temporal_verified=False, aftermath_candidate=False)` returns `candidate / temporal_not_verified` when the streak is nonzero. The frontend explicitly displays **“Analyzing potential collision...”** for `candidate` or `verifying`.

This candidate does **not** prove that the true participants were tracked, paired, or observed in motion. The live path's `motion_valid` variable is calculated from current box overlap/proximity, not measured vehicle motion. Whole-frame Model 1 can initiate the candidate while unrelated cars satisfy the vehicle-presence condition.

## 2. Actual Collision Participants

### P-A — visibly fallen motorcycle near the center

For the final inspected keyframe, `live_camera_keyframe_125a7162.jpg` (camera OSD **00:46:01**, saved **00:46:04.939**):

| Field | Finding |
|---|---|
| Class | Motorcycle |
| Raw detected | **YES in offline reproduction**; original raw live proposals were not retained |
| Raw confidence | **0.321782**, approximately **32.2%** |
| Raw box, native coordinates | Approximately `[563, 318, 822, 448]`, from the detector output; no box was injected |
| Accepted | **NO**; original annotation contains no accepted motorcycle box |
| Acceptance reason | Reproduction fails the unchanged **0.40** vehicle-confidence gate |
| Acceptance tier | **REJECTED** in the reproduction; the active live path has no implemented supported/trusted tier processing |
| Tracker ID / logical ID | **NOT AVAILABLE — those engines are not invoked by this live path** |
| Motion observed | **NOT ESTABLISHED**; this frame is aftermath, not an observed impact trajectory |

Manual correspondence across the sampled keyframes identifies the fallen motorcycle proposal in four of thirteen reproductions, at approximately **30.8%, 34.1%, 34.6%, and 32.2%**. All are below 40%. Other motorcycle proposals in those images refer to background traffic, not P-A. In the remaining sampled images no motorcycle proposal corresponding to the fallen bike was returned at the existing raw prediction settings. Some rider/person detections are present; they cannot substitute for a tracked motorcycle.

Thus the supported finding is **intermittently missed or rejected participant evidence**, not the blanket claim that Model 2 never detects motorcycles. Where the participant was not returned, `MODEL2_MISSED_PARTICIPANT` applies only to that offline sample, not to the unrecorded full live sequence.

### P-B — actual counterpart unresolved

The silver vehicle at the right is clearly detected, but the available aftermath frames do not establish that it was the collision counterpart. It must not be silently assigned as the true P-B.

For that **provisional counterpart only** in the final reproduction:

- Class: `car`; raw detected: **YES**; confidence: **0.930584**, approximately **93.1%**.
- Accepted: **YES** by class/confidence; the original annotated image shows approximately 93%.
- Tracker ID and logical ID: **NOT AVAILABLE**, because no tracking/continuity engine runs here.
- Motion observed: **NOT ESTABLISHED** as collision motion.

**P-A_USABLE_TRACK: NO. P-B_USABLE_TRACK: NO.** This describes the inspected runtime's lack of usable identity traces, not a measured tracker-association failure.

## 3. True Collision Pair

**P-A ↔ P-B generated: NO recorded true temporal pair.** The actual P-B remains unresolved, and the active live path never invokes the temporal pair-generation engine.

The implementation loops over accepted boxes for an anonymous overlap/proximity boolean. It does not emit logical IDs, relative velocity, closure evidence, pair histories, or pair temporal scores. In the final reproduced frame P-A is rejected before even that geometry check.

## 4. Selected Pair

**Selected temporal pair: NOT AVAILABLE.** There is no ranked temporal-pair selection in the active live method. The boolean geometry helper returns on the first qualifying pair; it does not return an identity or score.

All three accepted car pairs in the final reproduced frame fail that helper:

| Car confidence pair | IoU | Normalized edge gap | Qualifies |
|---|---:|---:|---|
| 93.1%, 75.2% | 0 | 2.041 | NO |
| 93.1%, 72.3% | 0 | 2.390 | NO |
| 75.2%, 72.3% | 0 | 0.201 | NO |

The unchanged helper requires IoU ≥ **0.08** or normalized gap ≤ **0.05**. Therefore `motion_valid` would be false for these accepted boxes. This is a geometry reproduction, not an invented selected-pair trace.

Whether an unrelated pair outranked the true pair during the original impact is **UNVERIFIABLE**. The previous night-scene Source-B audit concerns a different replay and was not substituted for this event.

## 5. Temporal Evidence

- True-pair maximum: **TEMPORAL_SCORE_NOT_AVAILABLE**.
- Pair confirmation threshold in this live path: **NOT APPLICABLE**; the newer temporal scorer is not called.
- Active live gate: **three consecutive qualifying observations** plus the geometry condition above, followed by cooldown/deduplication checks.
- Valid true-pair temporal observations: **NOT RECORDED / NOT COMPUTED**, not a measured score of zero.
- Highest unrelated-pair temporal score: **TEMPORAL_SCORE_NOT_AVAILABLE**.

The working tree defines `classify_collision_pair_regions`, but its only occurrence is the definition; the live method does not call it. The newer tracker/continuity/temporal modules exist elsewhere, but no live call to `analyze_vehicle_tracks` exists in the inspected backend.

## 6. Model 1

- Original candidate-window peak: **NOT RECORDED**.
- Thirteen saved-frame reproductions: accident probability **0.903806–0.997980** (peak approximately **99.8%**).
- Responsible for candidate eligibility: **YES in the inspected code path**. A high whole-frame score plus accepted vehicles starts the streak; neither condition identifies the actual collision pair.

The reproduction is biased toward backend-saved positive frames and must not be used to infer an uninterrupted high-confidence streak over omitted frames.

## 7. Pair Classifier

- True-pair diagnostic peak: **NOT AVAILABLE / NOT INVOKED**.
- Unrelated-pair diagnostic peak: **NOT AVAILABLE / NOT INVOKED**.
- No pair-region classification was made authoritative, and no such score was synthesized for this report.

## 8. Impact Sampling

- Impact/contact duration: **UNVERIFIED**.
- Capture frames during actual impact: **UNVERIFIED**.
- AI observations during actual impact: **UNVERIFIED**.

The 114 observed live results came from a non-collision recording window. The saved earlier keyframes predominantly show aftermath and omit the complete approach/contact interval. Neither count can honestly be presented as impact sampling.

## 9. Final Decision

Exact final decision of a complete candidate event: **UNVERIFIED — no complete live trace was captured**.

Two independently supported explanations apply to the available evidence:

1. For the final reproduced aftermath frame, the motorcycle is not accepted and all accepted car pairs fail the current interaction gate. Even a high Model 1 score is therefore insufficient for `confirmed_crash`. Once the streak matures without interaction, the code chooses aftermath review rather than dynamic collision confirmation.
2. A read-only database query found an already pending `aftermath_review` case, **CASE-DED5900C7A**, created **2026-09-10 03:49:42.234501** and last evidence-updated **2026-09-16 00:46:04.856644**, matching the final saved frame's time. An existing active case changes an otherwise eligible observation to `duplicate_active_case` and suppresses new case creation. That update is not proof of a fresh confirmed collision.

The historical case confidence (**0.951463**) was not used as this event's Model 1 score.

### Candidate state and expiry

- Original candidate start / last evidence / clear time: **NOT AVAILABLE**.
- Backend streak expiry: five-second window; a nonqualifying observation interrupts the consecutive run.
- UI: normally replaces the displayed result when new responses arrive. It has no independent candidate-freshness expiry, so a retained candidate can remain visible if updates stop. **Sticky state was not demonstrated for this event** because browser inspection was unavailable and the recorded window contained no candidate. No UI or alarm change was made in this task.

## 10. Failure Classification

**L — multiple evidence limitations/failures, provisionally A/C/F for the inspected aftermath samples.**

- **Primary observed failure:** P-A does not reach accepted vehicle evidence. Its raw proposal is intermittently absent (**A**) or below the current acceptance gate (**C**) in offline reproduction; the original annotation independently confirms no accepted P-A in the final frame.
- **Secondary structural failure:** no usable tracked/logical true pair or temporal-pair evaluation is produced by the active live path (**F**, pipeline integration gap). The final accepted boxes also lack qualifying geometry.
- Existing active-case deduplication is a further independent blocker to creating a fresh case.
- **Not proven:** wrong-pair ranking, impact cadence insufficiency, tracker association failure, Model 1 false-positive candidate, or a sticky UI for this exact event. These are not assigned as proven classifications.

This is not an assertion that the entire original event has been conclusively classified.

## 11. Is Camera Delay the Main Cause?

**NO — it is not supported as the primary explanation for the inspected aftermath frame.** Missing/rejected participant evidence and absent live temporal-pair processing are concrete blockers. Delay may affect impact sampling, but its contribution to this event remains unmeasured.

The separate preview audit demonstrated about one second of decoder delay from OpenCV's default 12 frame-decoding threads versus one thread. It did not demonstrate that this caused the candidate failure.

## 12. Required Next Fix

**OTHER — verify and restore the intended live pipeline integration before considering sensitivity changes.**

The requested trusted/supported tiers, tracking, logical continuity, and temporal-pair evidence are not produced by the inspected live implementation. Blindly lowering the flat 40% gate would neither establish the counterpart nor create valid temporal evidence. The next concrete step is to capture the original impact replay with complete raw/provenance instrumentation and verify the intended existing pipeline wiring. Only then can participant-detection or continuity improvements be chosen safely.

No detection-logic replacement was attempted here.

## 13. Safety

- Models changed: **NO**.
- Thresholds changed: **NO**.
- Production decision logic changed: **NO in this task**.
- Alarm behavior changed: **NO in this task**.
- PostgreSQL/database edited: **NO**; queries were read-only, and no login/session mutation was needed.
- Phase 8C changed: **NO**.
- Existing validation data changed: **NO**. New diagnostic artifacts are confined to `docs/live-candidate-audit/` and `docs/preview-latency/`.

The separate, previously requested preview fix changes only decoder open settings, preview timing diagnostics, and HTTP metadata. It does not change AI inputs or decisions and has not been activated by restarting the production process.

### Artifacts

- `observation-1/observations.jsonl`: 114 actual live result snapshots, with host receipt time and backend timestamps.
- `observation-1/preview-index.json`: HTTP preview receipt times; these JPEGs are **not claimed to be exact AI input frames**.
- `saved-frame-reproduction.json`: every returned COCO proposal for the thirteen saved-frame reproductions, scores, boxes, acceptance reason, and Model 1 probabilities.
- `last-frame-geometry.json`: all accepted car-pair geometry for the final reproduced frame.
- Original evidence remains untouched under `backend/outputs/`.
