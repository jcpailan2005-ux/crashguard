# Live Collision Temporal Feasibility Audit

The five-second rule is feasible for much of the measured cadence, but **none of the four fully qualifying post-baseline triples fits it**. Timing instability demonstrably prevents a third hit at OBS 4022. Ignoring expiry also permits evidence from different or unidentified vehicles to accumulate; a resulting confirmation is not proof of the true collision.

Root cause: **MULTIPLE_INTERACTING_CAUSES**.

WINDOW_ONLY_FIX: **UNSAFE_WITHOUT_PAIR_ATTRIBUTION**.

Next step: **E. JOINT_TEMPORAL_AND_PAIR_DESIGN_NEXT**, design only.

## Evidence and scope

Read-only analysis of the [preserved JSONL](../backend/validation/live_collision_diagnostics/preserved-20260928-232231/observations.jsonl), [capture report](two-vehicle-live-collision-diagnostic-2026-09-28.md), [complete evidence appendix](two-vehicle-live-collision-evidence-2026-09-28.md), and [telemetry specification](live-collision-diagnostic-telemetry-2026-09-26.md). No new capture, inference, training, service restart, or production import was performed.

Run `e45af5de2f1a466db95088addfc45a8c`, Bago CCTV `CAM-30960048ED`. Baseline 3547; analyzed observations 3620?5810: 71 decisions. Preserved file: 343 records; SHA-256 `cee504b5395f232ce9fcee07f6be4fae4b569ba90445f58467eaebcf584ef475`. Dropped count stays 16 throughout this window; write errors 0. Every analyzed record is complete. Earlier 16 dropped records cannot be recovered. Pre-decision failures/busy calls are not records; feasibility is measured on completed decisions, not every attempted analysis or camera frame.

## Current Production Rules

Authoritative path: [LiveCameraMonitor._analyze_current_frame](../backend/main.py#L2691), particularly the qualifier/window update at lines 2778?2802, then the call to [evaluate_crash_case_decision](../backend/main.py#L643). Proximity is [crash_like_vehicle_interaction](../backend/main.py#L622). The production source was read; no UI text is used to infer these rules.

Required hits: **3**. Temporal window: **5.0 s**. These are both code defaults and effective values in all captured observations. Configuration reads `CRASH_REQUIRED_CONSECUTIVE_FRAMES`, falling back to `LIVE_CAMERA_REQUIRED_HITS`, default 3, with minimum 1; the window reads `CRASH_TEMPORAL_WINDOW_SECONDS`, default 5.0. Effective recorded case threshold: **0.90**; UI threshold: **0.80**. Vehicle extraction uses **0.40**, with an existing **0.15** retry only if the initial extracted vehicle list is empty and the classifier reaches the UI threshold. Supported vehicle class, valid bbox and ROI filtering also apply.

The exact temporal operation is:

1. Compute current qualification: quality is `good`, accident probability ? 0.90, at least one accepted in-ROI vehicle, and scene valid.
2. Read `now_seconds = time.time()` after inference/ROI/geometry work.
3. Append `(now_seconds, qualification)` to the worker deque (maxlen 12 for N=3).
4. Remove oldest entries while `now_seconds - oldest_timestamp > 5.0`. Equality at 5.0 remains valid.
5. Count trailing true entries, stopping at the first false. Temporal readiness means count ? 3.

There is **no fixed timer started by the first candidate**. The window rolls backward from each current evaluation time. A streak's first retained positive is its effective oldest supporting hit. Window expiry is evaluated **after current qualification and append**, before the trailing count. Expiry does not explicitly clear the whole streak: remaining positives survive. The current qualified hit remains and can yield 1, 2, or more; a false current entry makes the trailing count zero. The diagnostic word `RESET` describes a loss relative to expected increment, including 1 ? 1 and 2 ? 2; it is not an extra production reset operation.

Proximity is **not part of the hit qualifier**. Confirmation requires current-frame `motion_valid` as well as temporal readiness. Despite its name, this current-path boolean is spatial: at least two accepted boxes, with **IoU ? 0.08 OR edge distance / scale ? 0.05**, where scale is max(1, both widths and heights). The loop stops at the first passing pair. It does not establish approach, contact, persistent identity, or that the same pair supported prior hits. One-vehicle observations can accumulate temporal hits; without current interaction a ready streak can enter the aftermath route instead. Final decision also checks quality/vehicles/scene and duplicate/cooldown gates. The JSONL does not expose all duplicate/cooldown inputs.

## Measured Live Cadence

Primary sample: **70 adjacent `decision_time` intervals within the 71 post-baseline observations**. The baseline-to-first interval is excluded from these distribution statistics and separately shown in reset 1. These are actual decision timestamps, not nominal FPS or start-to-start intervals. Percentiles use linear interpolation at sorted index `(n?1) ? p`.

| Measure | Median | P90 | P95 | Maximum |
|---|---:|---:|---:|---:|
| Decision-to-decision seconds (n=70) | 1.335180 | 3.192359 | 4.533659 | 19.482450 |
| Inference duration ms (n=71) | 1330.981 | 3366.877 | 4825.738 | 19357.720 |

`window_evaluated_at` is the **exact production pruning clock**; `decision_time` is emitted later, after decision evaluation and intervening work. They are not interchangeable at subsecond precision. Exact reset/triple calculations below use `window_evaluated_at`. The median window-evaluation interval is 1.335734 s. The largest corresponding gap, 4022 ? 4093, is 19.590821 s versus 19.482450 s in emitted decision timestamps. This explains why simple subtraction of displayed result timestamps and emitted decision times can differ.

## Reset Reconstruction

For each reset below the immediately preceding recorded decision is also the previous qualifying observation. Window-start and streak-start coincide for these six retained positive tails. All timestamps are UTC+08:00. Gap columns list **production window-clock gap / emitted decision gap**, both in seconds. The current observation timestamp is the window clock used by production, not the camera sensor time.

| Reset / OBS | Previous qualifying OBS | Current window timestamp | Gap since previous s | Oldest supporting hit timestamp / age s | Streak | Current qualified | Expired (count) | Other gate failure | Exact diagnostic reset reason |
|---|---|---|---|---|---|---|---|---|---|
| Reset 1: 3620 | 3547 | 2026-09-28T23:20:10.041568+08:00 | 10.623498 / 10.614586 | 2026-09-28T23:19:54.451253+08:00 / 15.590315 | 2 ? 1 | YES | YES (2) | none | temporal_window_expired |
| Reset 2: 3778 | 3620 | 2026-09-28T23:20:14.357950+08:00 | 4.316382 / 4.199480 | 2026-09-28T23:20:10.041568+08:00 / 4.316382 | 1 ? 0 | NO | NO (0) | below_case_threshold | below_case_threshold |
| Reset 3: 3917 | 3839 | 2026-09-28T23:20:24.957596+08:00 | 5.493244 / 5.502175 | 2026-09-28T23:20:19.464352+08:00 / 5.493244 | 1 ? 1 | YES | YES (1) | none | temporal_window_expired |
| Reset 4: 4022 | 3997 | 2026-09-28T23:20:31.380794+08:00 | 4.674292 / 4.807078 | 2026-09-28T23:20:24.957596+08:00 / 6.423198 | 2 ? 2 | YES | YES (1) | none | temporal_window_expired |
| Reset 5: 4093 | 4022 | 2026-09-28T23:20:50.971615+08:00 | 19.590821 / 19.482450 | 2026-09-28T23:20:26.706502+08:00 / 24.265113 | 2 ? 1 | YES | YES (2) | none | temporal_window_expired |
| Reset 6: 4420 | 4348 | 2026-09-28T23:20:55.755720+08:00 | 2.130012 / 2.023523 | 2026-09-28T23:20:50.971615+08:00 / 4.784105 | 2 ? 0 | NO | NO (0) | no_vehicle_detected | no_vehicle_detected |

- Reset 1 (3620): removes OBS 3437 and 3547; current qualified hit remains. **WINDOW_EXPIRY_WITH_CURRENT_OBSERVATION_QUALIFIED**.
- Reset 2 (3778): classifier 0.683715940 < 0.90; no expiry. Good quality and accepted motorcycle remain. **CURRENT_OBSERVATION_FAILED_WITHOUT_EXPIRY**.
- Reset 3 (3917): removes OBS 3839, now 5.493244 s old; current hit remains. **WINDOW_EXPIRY_WITH_CURRENT_OBSERVATION_QUALIFIED**.
- Reset 4 (4022): removes OBS 3917, retains 3997 and current 4022. **WINDOW_EXPIRY_WITH_CURRENT_OBSERVATION_QUALIFIED**.
- Reset 5 (4093): removes OBS 3997 and 4022; current hit remains. **WINDOW_EXPIRY_WITH_CURRENT_OBSERVATION_QUALIFIED**.
- Reset 6 (4420): no accepted vehicle in either existing detector pass; classifier 0.913120925 passes, quality and scene pass. No expiry. **CURRENT_OBSERVATION_FAILED_WITHOUT_EXPIRY**.

**WINDOW_EXPIRY_AND_CURRENT_OBSERVATION_FAILED: 0 of the six resets.** This must not be inferred from the frequency of reset labels. The final production `rejection_reason` can be the general `temporal_not_verified`; the diagnostic qualification/reset reasons give the precise observed cause.

## OBS 4022

Streak before: **2**, supporting OBS **3917 ? 3997**. Oldest timestamp: `2026-09-28T23:20:24.957596+08:00` (epoch 1790608824.957596). Current timestamp: `2026-09-28T23:20:31.380794+08:00` (epoch 1790608831.3807938). Elapsed: **6.423197746 s**. Limit: **5.0 s**.

The two intervals are **1.748905659 s** (3917 ? 3997) and **4.674292088 s** (3997 ? 4022). The second gap is less than five seconds, but their sum exceeds five; checking only the latest gap would miss the actual rule.

Observation qualified: **YES**. Good quality, valid scene, classifier **0.987033725 ? 0.90**, two ultimately accepted vehicles. Final actual state: `candidate`; `temporal_not_verified`; streak **2 ? 2**, not 3.

| Vehicle proposal | Confidence | Raw bbox xyxy | Initial pass | Retry pass |
|---|---:|---|---|---|
| motorcycle | 0.3592699766 | [691.0401611328125,508.0972900390625,958.4573974609375,716.1116943359375] | rejected below 0.40 | accepted ? 0.15 |
| car | 0.2717687190 | [596.58251953125,487.5682373046875,954.0484619140625,650.5010986328125] | rejected below 0.40 | accepted ? 0.15 |

The other three proposals per pass are persons, rejected as `class_not_vehicle`. The retry is existing production behavior. The exact full proposal list is in the capture appendix.

Evaluated pair: accepted indices [0,1], motorcycle/car. IoU **0.4901235947 ? 0.08**; edge distance **0**, scale **357.4659423828**, normalized distance **0 ? 0.05**. Proximity: **PASS** by both branches. Pair identity: **PAIR_IDENTITY_UNDETERMINED**.

Would OBS 4022 have completed the third required hit if this expiry had not occurred? **YES**, using its actual incoming two-hit state. This local counterfactual would yield 3. A cumulative replay ignoring every expiry from the baseline yields **4** at 4022, because the earlier 3839 hit also survives. Neither statement establishes the physical collision pair or a fresh incident.

## Timing Feasibility

For N hits, the latest N consecutive qualified decision-window timestamps must satisfy `t[N] ? t[1] ? W`, with no intervening false observation. For N=3 and W=5:

`?12 + ?23 ? 5 seconds`.

Neither gap has a separate 2.5-second limit: 1 s + 4 s fits. Each gap must be ?5 s and the sum must be ?5 s. With uniform cadence, the largest allowable interval is **2.5 s**, or at least **0.4 completed qualifying decisions per second** sustained across the triple. Equality is allowed by the strict `>` expiry comparison. A genuine interaction must also yield qualifying evidence on all three observations and an attributable passing pair at confirmation; timing alone supplies neither.

Use all **69 overlapping triples** wholly inside the 71-observation envelope; a triple is three consecutive completed decisions, not three arbitrarily selected positives. Rates are descriptive frequencies of this sample, not probabilities or independent trials.

- **TIMING_FEASIBLE_TRIPLE_RATE = 57 / 69 = 82.608696%** (qualifications ignored). Both exact window-clock and emitted decision timestamps produce the same count.
- **QUALIFYING_TRIPLE_RATE = 4 / 69 = 5.797101%** (all three frame qualifiers true, expiry ignored).
- **TIMING_AND_QUALIFYING_TRIPLE_RATE = 0 / 69 = 0%**. None of the four qualifying triples fits 5 s.

Selection matters: in the nine-observation candidate/reset span 3620?4420, only **1 / 7 triples = 14.285714%** fits five seconds, and that triple includes an unqualified observation. The later 62 ignored decisions have **55 / 60 timing-feasible triples = 91.666667%**, but no qualifying triple. Two triples cross that subdivision boundary; the subgroup denominators are not intended to sum to 69.

Thus the rule is not intrinsically impossible at the measured median cadence. Nor does the whole-envelope 82.6% rate demonstrate feasibility during the physical collision. Slower observations coincide with the qualifying run. Exact physical approach/contact duration is unavailable, so success probability for genuine collisions cannot be estimated from this capture.

## Counterfactual Without Window Expiry

**A. Current exact behavior:** AST-extracted the actual append/prune/trailing-count statements from `_analyze_current_frame` and executed them offline using recorded `window_evaluated_at` and qualification values. Seeded the deque from OBS 3620's `window_before`, retaining maxlen 12. **All 71 reconstructed streak counts and all 71 retained windows exactly matched telemetry.** No three-hit streak occurred after baseline; maximum 2.

**B. Ignore only temporal expiry:** executed the same extracted block with only the time-pruning `while` removed; same seed, maxlen, timestamps and qualification results. No detector, classifier, vehicle, proximity or quality value was recomputed or changed. No production module was imported. Failed observations still break the trailing streak.

| OBS | No-expiry hits | Recorded current pair passes? | Meaning |
|---|---:|---|---|
| 3620 | 3 | NO | Carries pre-baseline 3437,3547; temporal readiness only |
| 3997 | 3 | NO | First wholly post-baseline three-hit streak: 3839,3917,3997 |
| 4022 | 4 | YES | Temporal and current geometry prerequisites meet |
| 4093 | 5 | NO | Temporal readiness alone |
| 4348 | 6 | NO | Temporal readiness alone |

Streak resets to zero at 3778 and 4420 even without expiry. The six-hit qualifying run is 3839,3917,3997,4022,4093,4348.

3-hit sequence occurs: **YES**.

Classification at 4022: **COUNTERFACTUAL_UNATTRIBUTED_CONFIRMATION** ? specifically the temporal-and-current-geometry confirmation prerequisites. This is **not** an assertion that the full production function would persist a fresh incident: active-case/cooldown inputs are not captured, and hypothetical earlier aftermath decisions could alter that state. The replay holds recorded evidence fixed and does not simulate those feedback effects. It is not TRUE_COLLISION_CONFIRMATION.

## Minimum Window Analysis

For each overlapping triple of consecutive qualified observations, the exact minimum inclusive window is its last-minus-first `window_evaluated_at`. Values are float differences; rounded table values are not proposed configuration settings. Any window smaller than 5 s cannot improve any of these qualifying triples. No setting was changed or recommended.

| Triple | Minimum window s | Pair on third observation | Pair identity |
|---|---:|---|---|
| 3839,3917,3997 | 7.242149353 | none | PAIR_IDENTITY_UNDETERMINED |
| 3917,3997,4022 | **6.423197746** | motorcycle/car passes | PAIR_IDENTITY_UNDETERMINED |
| 3997,4022,4093 | 24.265113354 | none | PAIR_IDENTITY_UNDETERMINED |
| 4022,4093,4348 | 22.244915009 | none | PAIR_IDENTITY_UNDETERMINED |

Minimum observed window required among wholly post-baseline triples: **6.423197746 s**, triple **3917,3997,4022**. This gives mathematical feasibility for fixed recorded qualifiers, not safe physical-event verification. The boundary-crossing triple 3437,3547,3620 would need **15.590315104 s**; it is not included in post-baseline rates and is not claimed to belong to the reproduced event.

`NO_TEMPORAL_WINDOW_ALONE_CAN_FIX_CAPTURE` does **not** apply to the narrow mathematical streak question: qualifying triples do exist. It remains unproven that any window change can correctly identify the true collision.

## Pair-Safety Check

Every counterfactual three-hit sequence above, including the boundary-crossing sequence, is **PAIR_IDENTITY_UNDETERMINED**. None can be classified LIKELY_TRUE_PAIR or LIKELY_UNRELATED_PAIR using this JSONL alone.

The only post-baseline evaluated pairs are two motorcycles at 3839 and motorcycle/car at 4022. Intermediate hits 3917 and 3997 have only one accepted motorcycle. A passing pair at 4022 therefore receives accumulated frame-level evidence without proving the same pair existed or interacted throughout the triple. This is a safety limitation in the current evidence semantics, not proof that this particular pair was unrelated.

Reviewed prior [CCTV architecture study](../backend/validation/live_cctv_architecture_study/architecture_study_report.md), dated 2026-09-16. It reports an unrelated queued pair LV-0002/LV-0010 producing six offline confirmations on Source B frames 1235?1240, score 0.86300355, while the true pair was not recovered. The report explicitly identifies that experiment as isolated service composition, **not an exact production worker trace**. Its score, participants, cadence results, and thresholds must not be transferred to the September 28 event. It supports keeping wrong-pair regression evidence as a safety requirement, not declaring a wrong-pair incident in this capture. Source B and Phase 8C were not altered, rerun, or retrained.

## Root Cause

**MULTIPLE_INTERACTING_CAUSES**.

Timing is demonstrably causal for the recorded loss of temporal support: four resets preserve current qualification, all qualifying triples exceed five seconds, and no-expiry replay changes temporal eligibility. However, the median decision cadence is feasible and 82.6% of all timing triples fit, so an intrinsic global window-too-short diagnosis is too broad. Classifier failure at 3778 and no vehicles at 4420 still reset the counterfactual; timing is not the only unstable condition. Most qualifying observations lack a pair, and persistent participant identity is unavailable. These facts prevent both a single-cause diagnosis and a claim that a wider window recovers a genuine collision.

The largest gap is measured, but its cause (model compute, contention, scheduling, or other latency) is not isolated by this trace. No nominal FPS blame is assigned. The 3-hit rule is feasible in general at parts of this measured cadence, **not achieved in the captured qualifying run**, and unassessable as a reliable true-collision rule without phase/participant attribution.

## Window-Only Fix

WINDOW_ONLY_FIX: **UNSAFE_WITHOUT_PAIR_ATTRIBUTION**.

The minimum 6.423197746-second span can create temporal readiness at a passing current pair but does not connect that pair to the physical impact or to earlier supporting observations. Increasing retention could combine different vehicles or later appearance evidence. No claim of safety follows from producing more confirmations.

## Alarm

**ALARM_PATH_NOT_REACHED**. No further alarm inspection or changes were performed.

## Recommended Next Engineering Step

**E. JOINT_TEMPORAL_AND_PAIR_DESIGN_NEXT**.

The smallest safe next step is a design contract stating which observations may support the *same* collision hypothesis and how elapsed decision time expires that support under measured latency. Use this preserved trace plus existing wrong-pair negatives to specify acceptance/rejection cases before proposing settings or code. A temporal-only design ignores attribution; a pair-only design ignores the quantified inability of this qualifying run to reach three within five seconds. This is design work, not authorization to add tracking, widen windows, optimize FPS, or implement pair verification. No new live reproduction is needed for the timing arithmetic; physical collision identity remains an explicit evidence limitation.

## Safety

Production code changed: **NO**.

Temporal window changed: **NO**.

Required streak changed: **NO**.

Thresholds / vehicle acceptance / proximity / geometry changed: **NO**.

Models / weights changed: **NO**.

Tracking added: **NO**.

Pair verification added: **NO**.

Alarm changed or further investigated: **NO**.

Diagnostics enabled: **NO** ? current port-8010 process environment reports `LIVE_COLLISION_DIAGNOSTICS=0`; no restart performed.

RTSP / FPS / camera settings changed: **NO**.

Database / authentication / dispatcher / responder changed: **NO**.

Source B changed: **NO**.

Phase 8C changed: **NO**.

Training performed / training data changed: **NO**.

Only this audit document was created. Offline replay used the preserved evidence and source-extracted temporal statements; it wrote no production settings or data.

## Verdict

**TEMPORAL_AND_PAIR_SAFETY_PROBLEM**
