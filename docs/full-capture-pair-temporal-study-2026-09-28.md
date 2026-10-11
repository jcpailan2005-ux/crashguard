# Full-Capture Pair + Temporal Study

The complete capture does not support a pair-specific three-hit confirmation at 5.0, 6.5, or 7.0 seconds. Only two of 591 post-baseline decisions contain an evaluated pair, and neither has pair evidence in the adjacent supporting decisions. A longer window would make a **scene-level** third hit possible at OBS 4022; it would not establish that one pair supplied all three hits. Pair continuity by itself also cannot prove collision: a stable unrelated queue pair can pass the same geometric checks.

## Evidence

Authoritative input: [full preserved JSONL](../backend/validation/live_collision_diagnostics/preserved-full-20260928-postcapture/observations.jsonl), SHA-256 `940aa0ab5f5d3e293e99b1e50db901fe1c5b8b2f93bf41ad9f810a0cafb5f390`. It was read without modification. The [capture report](two-vehicle-live-collision-diagnostic-2026-09-28.md) and [temporal audit](live-collision-temporal-feasibility-audit-2026-09-28.md) provide context; the JSONL prevails where an earlier partial report stops at OBS 5810.

| Measure | Complete capture |
|---|---:|
| Total JSONL records | 863 |
| Post-baseline decisions | 591 |
| Baseline | OBS 3547 |
| Final observation | OBS 9949 |
| Confirmed crashes | 0 |
| Candidate decisions / qualified observations | 7 / 7 |
| Evaluated pairs | 2 (OBS 3839, 4022) |
| Decisions with 0 / 1 / at least 2 accepted vehicles | 583 / 6 / 2 |
| Required hits / maximum observed streak | 3 / 2 |
| Streak resets | 6: four expiry, one classifier, one no vehicle |
| Dropped records / write errors at final observation | 16 / 0 |

The 520 additional decisions from OBS 5833–9949 are all unqualified `ignored` decisions with no accepted vehicles, no evaluated pairs, and a zero streak. They add no candidate or pair sequence. All 591 records are complete and belong to the same run and camera. The 16 dropped records predate the post-baseline window according to the cumulative counters, but missing decisions anywhere cannot be reconstructed. The JSONL contains no images, direct contact labels, or persistent physical vehicle IDs.

## Current Semantics

Authoritative implementation: [`LiveCameraMonitor._analyze_current_frame`](../backend/main.py#L2691), its camera-owned `hit_window` initialized at [line 2286](../backend/main.py#L2286), the pair geometry helper at [line 622](../backend/main.py#L622), and the final decision function at [line 643](../backend/main.py#L643). The live worker owns a deque of `(window_evaluated_at, boolean scene qualification)`; it does not store a pair ID in that deque.

Streak scope: **CAMERA / SCENE**. Cross-pair accumulation possible: **YES**, conditional on each frame passing the scene qualifier and the hit timestamps surviving the window. Different physical vehicles can supply successive positive booleans because the qualifier requires only good quality, accident probability at least the effective **0.90**, at least **one** accepted in-ROI vehicle, and a valid scene. It does **not** require two accepted vehicles, a passing pair, or the same pair. A different pair could inherit earlier scene hits. A no-pair frame with one accepted vehicle and a passing classifier **does not clear** support; OBS 3917 and 3997 demonstrate that. A failed classifier or zero accepted vehicles appends false and makes the trailing streak zero (OBS 3778 and 4420). The current qualified hit is appended first; individual old entries are then removed when their age is **strictly greater than 5.0 seconds**. Remaining positives survive. OBS 4022 shows a diagnostic `RESET` from 2 to 2, meaning an older hit was pruned while the current hit stayed; it is not an additional clearing operation.

The current `motion_valid` name denotes a **current-frame spatial** test: two accepted boxes pass if IoU ≥ 0.08 **or** normalized edge distance ≤ 0.05. It is evaluated on current boxes and short-circuits at the first passing pair. It cannot establish approach or impact. Temporal readiness and current geometry are combined for `confirmed_crash`; duplicate/cooldown checks remain downstream. There is no production pair-specific streak.

## Full-capture reconstruction

| OBS | Qualified | Scene streak | Production reason | Accepted vehicles | Evaluated pair |
|---:|---|---|---|---|---|
| 3547, baseline | YES | 1 → 2 | none | motorcycle | none |
| 3620 | YES | 2 → 1 | `temporal_window_expired`; car proposal rejected at 0.3373 below 0.40 | motorcycle | none |
| 3778 | NO | 1 → 0 | `below_case_threshold`, score 0.6837 < 0.90 | motorcycle | none |
| 3839 | YES | 0 → 1 | none | motorcycle, motorcycle | motorcycle/motorcycle, passed |
| 3917 | YES | 1 → 1 | `temporal_window_expired` | motorcycle | none |
| 3997 | YES | 1 → 2 | none | motorcycle | none |
| 4022 | YES | 2 → 2 | `temporal_window_expired` | motorcycle, car | motorcycle/car, passed |
| 4093 | YES | 2 → 1 | `temporal_window_expired` | motorcycle | none |
| 4348 | YES | 1 → 2 | none | motorcycle | none |
| 4420 | NO | 2 → 0 | `no_vehicle_detected` | none | none |
| 4451–9949 | NO | 0 → 0 | ignored; individual reasons vary | none | none |

The last row contains **582 individual decisions**; the complete JSONL retains each row and its reason. The first 62 are also expanded in the [earlier detailed appendix](two-vehicle-live-collision-evidence-2026-09-28.md). No `confirmed_crash` occurs. This reconstruction distinguishes the known two evaluated pairs from physical collision participants, whose identities remain undetermined.

## OBS 4022 support and attribution

The incoming scene streak is 2. With only this observation's time expiry ignored, the third scene hit would be OBS **3917 → 3997 → 4022**, spanning **6.423197746 seconds** by production window timestamps. These are the exact two supporting hits and current hit for the local counterfactual. The car/motorcycle pair at 4022 is current-frame geometry only.

| Hit | Local timestamp | Qualified evidence | Accepted boxes `[x,y,w,h]`; confidence | Pair |
|---|---|---|---|---|
| 3917 | 2026-09-28 23:20:24.957596 | good quality, score **0.999039948 ≥ 0.90**, one vehicle, scene valid | motorcycle **0.368556082**, `[739.650024,558.095947,178.330444,160.010010]` (accepted on existing 0.15 retry after 0.40 rejection) | **none** |
| 3997 | 2026-09-28 23:20:26.706501 | good quality, score **0.957409978 ≥ 0.90**, one vehicle, scene valid | motorcycle **0.402154833**, `[708.036011,519.080078,269.885010,199.380859]` | **none**; a second motorcycle proposal 0.354769 is rejected below 0.40 |
| 4022 | 2026-09-28 23:20:31.380793 | good quality, score **0.987033725 ≥ 0.90**, two vehicles, scene valid | motorcycle **0.359269977**, `[691.040161,508.097290,267.417236,208.014404]`; car **0.271768719**, `[596.582520,487.568237,357.465942,162.932861]` (both accepted on existing 0.15 retry) | motorcycle/car, IoU **0.490123595 ≥ 0.08**, normalized edge distance **0 ≤ 0.05**; passes |

The two earlier hits contain **no pair**. Similar motorcycle boxes cannot supply an unobserved car or prove persistent motorcycle identity. Same pair across all three hits: **PAIR_NOT_PRESENT_FOR_ALL_HITS**. Physical participant identity at 4022 remains **PAIR_IDENTITY_AMBIGUOUS**. This is not a true-pair confirmation. A cumulative replay without any expiry carries an additional earlier hit and reaches four scene hits at 4022; it still lacks pair evidence on the earlier decisions.

## TEMPORAL_PAIR_HYPOTHESIS design

This is a proposed **offline state contract**, not production tracking. Each hypothesis has: two observation-local member signatures `(class, accepted bbox, confidence)`, `first_seen`, `last_seen`, qualifying-hit timestamps, per-transition association evidence, ambiguity state, and expiry state. A hypothesis becomes eligible for a three-hit temporal condition only when **the same unambiguous pair** is observed and qualifies on three consecutive analyzed decisions within the window. Eligibility is not collision verification; physical interaction evidence and downstream duplicate/cooldown rules remain separate. With no direct contact evidence in this capture, no pair can be called the proven colliding pair.

Association at the next analyzed decision considers both A→A/B→B and the reversed ordering A→B/B→A. A proposal must retain its class, pass conservative bbox overlap, normalized center displacement, and scale-ratio checks. For two same-class members, or multiple cars, association is accepted only if **exactly one full bijection** satisfies all checks and no competing pair can claim the same members. Equal or close competing assignments are ambiguous and abstain; a car/car crossing cannot inherit identity from index order. A car/motorcycle pair can use class to restrict matching, but class alone does not prove physical identity. Each decision and its actual timestamp are used; no velocity is fabricated between gaps. These association gates need calibration against labeled positive and unrelated-traffic examples before implementation. The exploratory thresholds in the offline runner (IoU ≥ 0.5, normalized center displacement ≤ 0.35, scale ratio 0.5–2.0) are **not proposed production settings**; none affects this capture's result because no adjacent analyzed decisions both have a pair.

State transitions:

| New observation | Hypothesis action |
|---|---|
| Same pair, uniquely associated, frame qualified | append current timestamp; individually expire hits older than window; eligibility at three retained hits |
| Same pair present but frame/classifier/quality fails | close the qualifying streak; retain observation only as nonqualifying context if useful |
| One or both members missing, including a temporary miss | close the streak; do not mint a hit or let a later vehicle inherit support |
| Multiple possible associations or crossing ambiguity | abstain and close the streak; no silent handoff |
| Different or newly entering pair qualifies | create a new hypothesis with its own first hit; never borrow the previous pair's hits |
| Existing pair expires | remove its old hits individually; current qualified pair can start a new streak |

This strict rule favors safety over recall. A missed detection loses continuity; any future grace/occlusion policy would require separately demonstrated identity evidence and safety tests. It is not assumed in this study. Spatial closeness to a queued vehicle is not an identity proof, and an aftermath score is not contact evidence.

## Offline replay

Reproducible read-only runner: [offline_pair_study.py](../backend/validation/live_collision_diagnostics/offline_pair_study.py). It checks the full JSONL hash, executes the production camera-level append/prune/trailing-count semantics against all 591 post-baseline decisions, and checks every resulting streak and retained window against telemetry. It then applies the strict pair-hypothesis policy above using only production-evaluated pairs. Detector outputs, classifier scores, acceptance and pair geometry remain recorded values. The 5.0, 6.5, and 7.0-second comparisons change only the offline pair hypothesis's retention span. No model is rerun and no service is contacted.

| Replay | Pair-specific eligibility/confirmations | Unattributed live confirmations | Ambiguous live sequences | Wrong-pair live sequences | Expiry removals | Missing-pair resets |
|---|---:|---:|---:|---:|---:|---:|
| CURRENT, exact scene semantics | 0 `confirmed_crash`; **591/591** streak/window states match | 0 | physical pair attribution unknown | unknown | 4 diagnostic expiry resets | not pair-scoped |
| PAIR_AWARE_5S | 0 | 0 | 0 matched transitions; physical identity of both isolated pairs unresolved | 0 proven; cannot classify actual identities | 0 | 2 |
| PAIR_AWARE_6_5S | 0 | 0 | same | same | 0 | 2 |
| PAIR_AWARE_7S | 0 | 0 | same | same | 0 | 2 |

`missing-pair resets = 2` means the hypothesis created at each isolated pair observation is closed by the next qualified observation without a pair. No pair survived long enough to reach an expiry check in this conservative replay; zero expiry removals **does not** mean timing ceased to matter for production. There are no hypothetical live confirmations to label LIKELY_SAME_PAIR, LIKELY_UNRELATED_PAIR, or PAIR_IDENTITY_AMBIGUOUS. The two isolated pairs themselves remain physically **PAIR_IDENTITY_AMBIGUOUS**. The output count `unattributed confirmations = 0` follows the replay's refusal to confirm unresolved pair streaks; it is not evidence that those pairs were related to the crash.

Generic scene timing at 4022 differs: 6.5 or 7.0 seconds would retain OBS 3917,3997,4022 and permit a scene-level third hit (6.423198 seconds). The pair-aware replay still has **zero** because the first two hits have no evaluated pair. This comparison demonstrates why window extension alone answers the wrong question. Additional scene-level candidates at other times are not classified as collision confirmations because the pair and downstream case state are unknown.

## Detection continuity and false-pair safety

Classification: **DETECTION_CONTINUITY_INSUFFICIENT** for a three-hit pair hypothesis on this capture. Only **2/591 = 0.3384%** of post-baseline decisions have an evaluated pair. Among the **7 qualified** decisions, only 2 have a pair; 5 have one accepted vehicle. Across the full window, **583** decisions have zero accepted vehicles, 6 have one, and only 2 have at least two. There is no pair-bearing run of length two, let alone three. The 520 decisions beyond the earlier snapshot add no pair. A pair-aware temporal rule cannot produce a valid three-hit chain from these recorded detections at any of the tested windows. The capture does not show whether a missing physical participant was below model proposal threshold, rejected by extraction, outside ROI, occluded, or absent from the image in each case; use recorded proposal reasons only for specific observations.

The offline runner includes small **synthetic policy fixtures**, separate from real capture evidence:

- Different pairs A/B → C/D → E/F: **0** pair-specific confirmations.
- Substitution A/B → A/C → A/D: **0**.
- Missing pair member between hits: **0**.
- A/B ordering reversed while members remain uniquely distinguishable: **1 pair-specific temporal eligibility**. This checks order invariance, not physical crash detection.
- Indistinguishable car/car members: **0**, ambiguity abstains.
- Stable unrelated queued pair shown three times: **1 temporal eligibility**. This is a deliberate counterexample: pair continuity plus recorded-style proximity **does not prove impact**. The fixture is labeled unrelated by construction; it is not a claim about the live pair at OBS 3839 or 4022.

Previously preserved [CCTV architecture study](../backend/validation/live_cctv_architecture_study/architecture_study_report.md) records an unrelated queued pair LV-0002/LV-0010 with offline false confirmations on Source B frames 1235–1240. That study's isolated composition differs from the live worker and cannot label this capture's pairs, but it establishes a concrete wrong-pair regression risk. No Source B data was changed or reused as a training target. A pair-specific streak prevents *switching* among unrelated pairs; it does **not** prevent one stable unrelated pair from producing false evidence. An independent interaction criterion and labeled regression checks are necessary before production use.

## 6.5 Second Safety

- **TEMPORALLY_SUFFICIENT: YES**, narrowly for the generic scene hit span 3917→3997→4022 (6.423198 s ≤ 6.5 s). It is **not sufficient** for a pair-specific three-hit sequence on this capture.
- **PAIR_ATTRIBUTION_SUFFICIENT: NO**. The two earlier supporting hits at 4022 have no evaluated pair, and the actual physical pair cannot be identified.
- **DETECTION_CONTINUITY_SUFFICIENT: NO**. There is no adjacent pair-bearing decision run.
- **FALSE_PAIR_SAFETY_SUFFICIENT: NO**. A stable unrelated pair passes the synthetic temporal policy, consistent with the independent wrong-pair risk in preserved regression evidence.

Do not recommend or deploy 6.5 seconds from these results.

## Primary Bottleneck

**JOINT_DETECTION_PAIR_TEMPORAL**. The immediate measured blocker for pair-specific confirmation is sparse simultaneous accepted vehicle evidence. Scene-level window expiry is real (especially OBS 4022), but widening it cannot create missing pair observations or establish physical attribution. Pair association alone cannot recover a member that was not accepted. The safe design needs detector/acceptance continuity evidence, unique pair attribution, and cadence-aware temporal rules assessed together. This classification does not claim that a production detector threshold should be lowered.

## Safe Design Invariants

1. Different pair hypotheses cannot share qualifying hits.
2. A replacement vehicle cannot inherit another member's pair history.
3. Ordering reversal is allowed only with a unique two-member association; same-class crossings and competing cars cause abstention.
4. Window extension cannot turn an unresolved pair into confirmation.
5. A missing member creates no hit; a temporary miss is not filled with fabricated geometry or velocity.
6. Aftermath appearance and whole-frame score do not substitute for observed interaction.
7. Proximity and stable pair identity alone do not prove impact; a verified interaction criterion is required before automatic confirmed-crash eligibility.
8. Current scene qualification and pair interaction must be attributed to the **same observation and pair hypothesis**; no cross-pair borrowing of a whole-frame score as pair-specific proof.
9. Operational deduplication and cooldown remain downstream of collision verification, and cannot repair false physical attribution.
10. A decision gap or evidence discontinuity closes unsupported support; the test must not bridge it solely by increasing the window.

## Recommended Next Step

**JOINT_DETECTOR_AND_PAIR_PROTOTYPE_REQUIRED**. Build an isolated, labeled offline study of simultaneous participant recall, unique association, and interaction evidence with measured decision timestamps. Replay this complete capture and known unrelated traffic as separate scenarios; count correct physical pair coverage and false confirmations before any code or setting proposal. This is a prototype design recommendation, **not deployment approval**. Existing JSONL cannot establish the actual physical pair or contact phase, so it cannot validate true-positive recovery by itself.

## Safety

Production code changed: **NO**. Production window changed: **NO**. Production streak changed: **NO**. Production thresholds changed: **NO**. Models/weights changed: **NO**. Production tracking added: **NO**. Production pair verification added: **NO**. RTSP/FPS/camera settings changed: **NO**. Alarm changed: **NO**. Database/authentication/dispatcher/responder changed: **NO**. Source B changed: **NO**. Phase 8C changed: **NO**. Training performed: **NO**. Diagnostics: **OFF**, verified from the running port-8010 backend environment. The only files added are this report and the isolated offline replay script under `backend/validation/`.

## Verdict

**DETECTION_CONTINUITY_BLOCKS_PAIR_DESIGN**
