# Phase 2 — Participant Continuity and True-Pair Feasibility

**The current evidence cannot establish defensible Source B A/B tracks.** Accepted-only and accepted-plus-supported-raw experiments both recover zero A/B observations. A has one rejected proposal without an established track; B has no proposal. Conservative bookkeeping passes the offline controls, but real-participant interaction and production integration remain unvalidated.

All new code and artifacts are confined to [the Phase 2 offline directory](../backend/validation/source_b_continuity_phase2_20260930/). This report distinguishes tested bookkeeping properties, measured detector limitations, and unproven physical collision verification.

## Interrupted Run Recovery

The first execution was interrupted by the reported model usage limit after the final duplicate-identity and interaction-transition safety edits. Recovery continued the existing working tree; nothing was restarted from scratch or undone. Inspection established that the previously launched `run_study.py` and `validate.py` subprocesses had in fact completed with exit code 0, but `finalize.py` had not run and the draft report still described earlier counts. The interrupted work was final validation/report reconciliation, rather than a demonstrated killed test process.

All previous Phase 2 files and the draft report were preserved in `recovery_previous_run_20261001/`. A **subsequent clean invocation of both the complete test suite and saved-proposal replay** supplies the final results below. The final prototype was retained; two additional tests explicitly check the before-near transition and simultaneous multiple-pair isolation. [Recovery manifest](../backend/validation/source_b_continuity_phase2_20260930/recovery_manifest.json). The requested report filename is retained.

## Phase 1 Baseline

Simultaneous accepted A+B: **0**

Dense unrelated pairs: **155**

Pair ledger: **PASS**

Production pair safety: **FAIL**

The complete [Phase 1 report](source-b-physical-pair-baseline-2026-09-30.md), annotations, participant matching tables, configuration, detector/worker trace, pair attribution, tracking results and integrity manifests were read. Phase 1 protected hashes were checked before replay; unchanged source/model/code hashes allow reuse of its real model proposals. Phase 2 performs **new acceptance checks, association and pair experiments on those saved proposals**, not new YOLO inference or a new collision recording.

Scope: cycle 1, frames **0–87**, host **+0.000–7.687 s**; physical scoring uses frames **30–70**. Fresh tracker and pair state are created for each mode; no replay boundaries are crossed. The remaining six recorded segments retain the Phase 1 cycle inventory; their image-phase correspondence is not treated as additional physical ground truth. Source B remains evaluation-only.

**Annotation authority:** Phase 1 labels are assistant-reviewed diagnostic envelopes, not human-verified labels. Phase 2 preserves that status. There are no supplied human-verified A/B boxes to display. The overlays explicitly state this limitation rather than relabeling them as human annotations. Post-overlap null boxes remain unassessable, not missed detections.

## Participant A

Labeled observations: **41 rows; 9 assessable boxes, 32 unassessable**.

Raw detected: **1/9**.

Accepted: **0/9**.

Rejected: **1**, frame **41**, host **+4.078 s**: `below_vehicle_confidence`.

Missed: **8/9**, frames **37,38,39,40,42,43,44,45**.

The sole proposal is `car`, confidence **0.387290418**, bbox `[851.221,433.877,969.517,558.013]`, versus the diagnostic envelope `[840,429,973,563]`; IoU **0.823960**. Current acceptance requires **0.40**. Its classification is `PROPOSAL_EXISTS_BUT_BELOW_CURRENT_ACCEPTANCE`, not `NO_PROPOSAL`.

## Participant B

Labeled observations: **41 rows; 10 assessable boxes, 31 unassessable**.

Raw detected: **0/10**.

Accepted: **0/10**.

Rejected: **0**. There is no matching proposal to reject.

Missed: **10/10**, frames **36–45**, host **+3.562–4.390 s**: `NO_PROPOSAL`.

For both participants, proposal absence means absence from the current YOLO output at its existing 0.25 proposal confidence/NMS settings. It does not prove that the network produced no lower-scored pre-NMS activation. No confidence floor or NMS setting was changed to inspect that possibility.

| Phase | A: assessable / raw / accepted / rejected / missed | B: assessable / raw / accepted / rejected / missed |
|---|---|---|
| PRE_APPROACH, 30–35 | 0 / 0 / 0 / 0 / N/A | 0 / 0 / 0 / 0 / N/A |
| APPROACH, 36–44 | 8 / 1 / 0 / 1 / 7 | 9 / 0 / 0 / 0 / 9 |
| INTERACTION, 45–50 | 1 / 0 / 0 / 0 / 1 | 1 / 0 / 0 / 0 / 1 |
| IMMEDIATE_POST, 51–60 | 0 / 0 / 0 / 0 / N/A | 0 / 0 / 0 / 0 / N/A |
| AFTERMATH, 61–70 | 0 / 0 / 0 / 0 / N/A | 0 / 0 / 0 / 0 / N/A |

[Participant diagnosis](../backend/validation/source_b_continuity_phase2_20260930/participant_diagnosis.json) retains counts and phases. Unrelated labels remain U1, the left-turning white car, and U2–U5, upper queued vehicles; these are not substitutes for A/B.

## Why Simultaneous Accepted A+B = 0

| Joint classification | Count | Frames / host-time examples |
|---|---:|---|
| A_ACCEPTED_B_ACCEPTED | 0 | None |
| A_ACCEPTED_B_RAW_ONLY | 0 | None |
| A_RAW_ONLY_B_ACCEPTED | 0 | None |
| A_RAW_ONLY_B_RAW_ONLY | 0 | None |
| A_ACCEPTED_B_MISSED | 0 | None |
| A_MISSED_B_ACCEPTED | 0 | None |
| A_RAW_ONLY_B_MISSED | **1** | **41 / +4.078 s**; A below 0.40, B no proposal |
| A_MISSED_B_RAW_ONLY | 0 | None |
| A_MISSED_B_MISSED | **8** | 37/+3.656, 38/+3.734, 39/+3.843, 40/+3.968, 42/+4.156, 43/+4.250, 44/+4.328, 45/+4.390 |

The nine rows above exhaust **jointly assessable** frames. The other **32 frames** are explicitly marked with one or both participants `UNASSESSABLE`: 30–36 and 46–70. At frame 36 B is missed but A is unassessable; forcing it into “A_MISSED” would invent a recall denominator. [Frame-by-frame JSON](../backend/validation/source_b_continuity_phase2_20260930/frame_categories.json) and [CSV](../backend/validation/source_b_continuity_phase2_20260930/frame_categories.csv) include all 41 frames and individual failure classes.

This establishes two distinct failures: **18 absent proposals** over 19 assessable individual participant observations, plus **one real proposal rejected by confidence**. Merely accepting A's frame-41 proposal would still leave B absent and A without a measured history.

Diagnostic matching review: [contact sheet](../backend/validation/source_b_continuity_phase2_20260930/matching_contact_sheet.jpg), [frame 41 rejection](../backend/validation/source_b_continuity_phase2_20260930/overlay_0041.png), and [frame 69 unrelated queue](../backend/validation/source_b_continuity_phase2_20260930/overlay_0069.png). Six overlays show labeled envelopes, all recorded raw proposals, accepted/rejected status, proposal IDs, confidence, evaluated ownership and rejection reason. Original frame pixels are rehashed against the Source B sidecar before rendering. Full-resolution PNGs preserve review detail; raw proposals are never moved to fit labels.

## Acceptance Audit

The exact current pure extractor and ROI function were re-executed for **all 88 recorded observations** without importing the application. Rejection reasons and acceptance counts match Phase 1 throughout: [acceptance recheck](../backend/validation/source_b_continuity_phase2_20260930/current_acceptance_recheck.json). Production telemetry sanitizes non-vehicle class names as `other_class`; their precise non-vehicle subtype is unavailable, but the recorded class-rejection branch is reproducible.

Current sequence: separate vehicle YOLO proposals → normalize class → allowed vehicle class → confidence ≥0.40 → clamp coordinates to frame → positive box dimensions → ROI center test. Primary `best.pt` is a fallback if the separate vehicle model is unavailable. The existing 0.15 acceptance retry requires **no accepted vehicle** and scene suspicion; unrelated accepted cars prevent that retry from being a participant-specific recovery route. It does not lower YOLO's 0.25 proposal floor. Scene quality/classifier/temporal gates occur later and must not be reported as proposal rejection rules.

Dense-window proposal accounting: **264** proposal rows = **1 A**, **0 B**, **234 unrelated-region/vehicle proposals**, **29 unresolved non-vehicle proposals**. “Unrelated” does not mean the vehicle detection itself is false; it means unrelated to physical A/B. Broad U envelopes support that separation, not precise unrelated-vehicle ground truth. [Per-proposal audit](../backend/validation/source_b_continuity_phase2_20260930/proposal_audit.json).

| Rule | Intended protection | A rejects | B rejects | Unrelated rejects | Other/unresolved rejects | Assessment |
|---|---|---:|---:|---:|---:|---|
| Allowed vehicle class | Prevent non-vehicles entering collision geometry | 0 | 0 | 15 | 29 | WORKING_AS_INTENDED; UNSAFE_TO_RELAX |
| Confidence ≥0.40 | Limit weak vehicle evidence | **1** | 0 | **81** | 0 | Mechanically WORKING_AS_INTENDED; OVERLY_RESTRICTIVE_FOR_LABELED_PARTICIPANT at A41 only; UNSAFE_TO_RELAX globally from this evidence |
| Clamp and reject degenerate box | Prevent invalid geometry | 0 | 0 | 0 | 0 | NOT_RELEVANT to observed A/B losses; retain guard |
| ROI | Exclude out-of-source-region detections | 0 | 0 | 0 | 0 | NOT_RELEVANT here: empty/full-frame ROI |
| Special retry | Recover vehicle evidence in an otherwise empty suspected scene | 0 | 0 | 0 | 0 | NOT_RELEVANT: does not supply B or an established A track |

**138 unrelated proposals are accepted.** For A/B there are zero context, class, geometry or other-rule rejections. Thus neither “YOLO failed on every observation” nor “acceptance alone blocks the pair” describes this evidence correctly. No rule was removed or relaxed.

## Offline Tracker

Design: new [offline-only prototype](../backend/validation/source_b_continuity_phase2_20260930/prototype.py), with [fixed configuration](../backend/validation/source_b_continuity_phase2_20260930/prototype_config.json), tested before the Source B replay. It consumes proposal ID, class, score, bbox and **existing acceptance result/reason**. Physical labels, participant identities, source-region coordinates, classifier score and collision outcome are not tracker inputs.

Ground truth used as tracker input: **NO**

Existing-code audit:

| Component | Measured association/support | Classification and limitation |
|---|---|---|
| `vehicle_tracking.py` / installed ByteTrack | Kalman prediction, IoU matching, confidence stages, bounded observation history and camera map | REQUIRES_BOUNDED_OFFLINE_FIX for this contract: no wrapper-level ambiguity/physical-identity guard; installed distance function uses IoU/confidence without class gating; no explicit per-camera active-track cap. Retention expiry is not proof that every underlying identity expires simultaneously. |
| `logical_vehicle_continuity.py` | Handoff overlap, displacement, size, class, elapsed time, prediction error and trajectory checks | UNSAFE_FOR_THIS_USE unchanged: existing raw-ID mapping bypasses those checks. Ambiguity can start a new logical identity; candidate support can derive from a scene/pair region rather than a verified physical history. |
| `vehicle_detection_tiers.py` | Weak-candidate persistence and scene/spatial context | REQUIRES_BOUNDED_OFFLINE_FIX as an identity source; nearby strong traffic and scene score do not establish same-vehicle continuity. It is not the current live acceptance path. |
| `live_cctv_architecture_study/run_study.py:Provisional` | Short raw-proposal histories, displacement/size/class/direction checks | UNSAFE_FOR_THIS_USE as a drop-in: permits weak seeds and carried usable presence; its study reports failure to recover the primary true pair. Its old `best.pt` cache is not substituted for this live-detector baseline. |
| `live_collision_diagnostics/offline_pair_study.py` | Unique same/reversed pair bijection from class/IoU/scale/displacement | SAFE_FOR_OFFLINE_PROTOTYPE as a limited diagnostic comparator; not a persistent participant tracker or collision verifier. |
| `temporal_crash_verifier.py` | Pair-owned approach/contact-proxy/post features | REQUIRES_BOUNDED_OFFLINE_FIX/validation with independently reliable identities; prior queue attribution failure prevents presuming it safe. |
| `CameraDecisionTracker` / live `hit_window` | Scene-level positive observations | UNSAFE_FOR_THIS_USE as physical tracking: no vehicle identity at all. |

Repository tracking/continuity implementations and their replay/test callers were searched and inspected; no experimental service was wired into production. A fresh [existing-service probe](../backend/validation/source_b_continuity_phase2_20260930/existing_continuity_probe.json) supplies raw ID 3 at x=40 then x=540 within **0.1 s**. The unchanged logical service preserves logical ID **1** after the **500-pixel jump**, with **zero handoff checks**. This is an offline safety defect demonstration, not a claim that Source B experienced that particular swap.

The new tracker is **SAFE_FOR_OFFLINE_PROTOTYPE within the tested contract**, with real-world identity safety still unvalidated:

- Accepted real proposals may seed tracks. Isolated weak proposals never seed supported identities.
- Every association must pass exact class compatibility, area similarity ≥0.50, displacement ≤`0.02 + 0.30 × elapsed_seconds` in normalized image coordinates, previous/predicted IoU ≥0.20, bounded prediction residual ≤0.025, and a direction-reversal guard where motion is measurable.
- Unique mutual association is required. Any ambiguous connected set of proposals/tracks is rejected and affected IDs revoked; their pair histories are removed. Proposal IDs/order are never treated as persistent identities.
- Proposals overlapping at IoU ≥0.50 are rejected as identity-ambiguous, including different-class duplicate boxes, rather than seeding two physical identities. This deliberately favors missing an uncertain identity over duplicate observed identities.
- Up to one second of dormancy requires at least two prior accepted observations. Dormant output is `PREDICTED_ONLY`, with **bbox=null** and a separately named last-observed box. A lone seed cannot support dormancy. Long misses expire identity; new entrants receive new IDs.
- Experimental `OBSERVED_RAW_SUPPORTED` requires a confidence-only rejection, unique geometric/temporal association, at least two prior accepted observations, last accepted observation within one second, and at most two consecutive weak supports. Other rejection reasons cannot be bypassed.
- Every output state is `OBSERVED_ACCEPTED`, `OBSERVED_RAW_SUPPORTED`, `PREDICTED_ONLY` or `EXPIRED`. Only accepted observations may qualify collision hits in this experiment. Raw-supported continuity does not change production acceptance.
- Limits: 64 proposals/observation, 64 retained tracks, 16 observations/track, 64 pair states, 16 entries/pair history. Overflow and duplicate/out-of-order observations fail closed. IDs are not recycled within an experiment.

These are generic research bounds, not calibrated camera parameters or a production recommendation. Same-looking vehicles that are observationally indistinguishable can defeat any bbox-only identity claim; passing the finite synthetic controls does not establish universal swap resistance.

## A Track

Recall: accepted-only **0/9**; accepted + supported raw **0/9**.

ID switches: **0 observed; rate N/A**, because no A track exists.

False associations: **0 observed for an established A track; safety rate N/A**, not a successful identity-recovery claim.

Longest supported span: **0 s**.

At frame 41 the raw-enabled tracker explicitly reports `weak_without_strong_prior_continuity`. The 0.3873 box is real, but there is no established A identity whose measured history can support it. Borrowing a queued vehicle's ID would violate the task.

## B Track

Recall: accepted-only **0/10**; accepted + supported raw **0/10**.

ID switches: **0 observed; rate N/A**, because no B track exists.

False associations: **0 observed for an established B track; safety rate N/A**.

Longest supported span: **0 s**.

B has no matching raw proposal on any assessable observation. No continuity rule can generate a B observation from that absence.

[Accepted-only scoring](../backend/validation/source_b_continuity_phase2_20260930/accepted_only_scoring.json) and [raw-supported scoring](../backend/validation/source_b_continuity_phase2_20260930/accepted_plus_supported_raw_scoring.json) retain frame/time/assessability/track IDs/states. Labels are applied only after tracker execution. Unassessable post-overlap frames do not increase or decrease recall.

## Simultaneous Supported Tracks

Count: **0** in both modes.

Frames/times: **[]**. No predicted box or unrelated vehicle counts as an A/B observation.

The raw-enabled mode supports **23 weak observations across the full 88-frame trace**, but none recovers assessable A/B. This is additional context-vehicle continuity, not participant recovery.

## True Pair

Created: **NO**

TRUE_PAIR_CREATED = **NO**

Pair identity: **None**. No canonical A/B pair is created from annotation names. First/last true-pair observation and inter-observation spacing are **N/A**.

## Pair-Owned Hits

Actual A/B qualifying observations: **0**.

`PairHitLedger` is used unchanged, with three hits/five seconds and sorted tracker-generated pair keys. The offline engine expires/revokes pair state with compromised track IDs, resets qualifying streaks when a participant is missing, and refuses duplicate observation contributions. Neither a dormant track nor raw-only support increments collision hits.

Two comparisons are retained:

1. **Ownership-only comparison:** accepted pair + scene classifier/quality/ROI + current proximity. This isolates pairs but still permits queue false eligibility.
2. **Conservative interaction experiment:** additionally requires measured recent closing from at least three accepted pair observations, a proximity transition, and at least two observed post-proxy low-speed observations following measured motion. Only then can three accepted pair-owned qualifying hits become *offline eligibility*.

The interaction experiment uses a 0.08 normalized-image net closing requirement, 0.002 closing-jitter tolerance, 0.04 normalized-image/s moving threshold, 0.018 stopped threshold, and a three-second interaction history/window. These generic research gates were fixed before replay and were not adjusted to make Source B pass. The classifier 0.90, production proximity predicate, three-hit requirement and five-second window remain unchanged. The experiment is narrower than all real collision types; it can reject valid events and does not prove contact.

## Existing 3-Hit / 5-Second Feasibility

**NO** for the actual Source B A/B pair.

Reason: zero simultaneous supported participant observations, zero tracker-created true pair and zero attributable qualifying hits. Accepting A's isolated weak proposal would not supply B, prior motion or post-interaction identity. Additional elapsed time or cross-cycle evidence cannot fix that deficit legitimately.

## 155 Unrelated Pairs

Result: unrelated traffic receives tracks and forms pairs, but conservative interaction eligibility remains **false**.

False confirmations: **0** in the conservative offline experiment; there is no production incident API in the prototype. The ownership-only comparison reaches **false collision eligibility** on an unrelated queue pair.

| Measurement | Accepted-only | Accepted + supported raw |
|---|---:|---:|
| Original 155 comparisons mapped to observed tracker pairs | 151 | 127 |
| Unrelated tracks with multiple labeled observations | 7 | 10 |
| Unique pair keys over all 88 frames | 40 | 52 |
| Maximum ownership-only hits within dense 30–70 window | 2 | 2 |
| Maximum conservative qualifying hits in those comparisons | 0 | 0 |
| Conservative eligibility observations over all 88 frames | 0 | 0 |
| Ownership-only false eligibility outside dense endpoint | Frame 71 | Frame 71 |

Four comparisons are conservatively unavailable in accepted-only mode, all at frame **39**. Raw-enabled mode rejects **28** comparisons: frames **35 (3), 36 (3), 37 (5), 38 (7), 39 (5), 40 (3), 54 (2)**. Additional weak/overlapping proposals make associations ambiguous, causing identity revocation rather than guessing. They are not silently counted as safe recovered pairs. The traces preserve exact proposal IDs and revocations. These final counts include the duplicate-overlap protection.

The queued pair at **69/+6.171, 70/+6.265, 71/+6.359 s** receives ownership-only hits **1,2,3**. Accepted-only key is **(4,14)**; raw-enabled key **(11,21)**. Phase 1 labels identify the queue at 69–70; frame 71 is a one-observation extension of those measured tracks beyond the dense-label endpoint, not a newly labeled A/B positive. In both modes measured closing is false and conservative interaction hits remain **0**. Thus **pair isolation alone does not solve false collision qualification**.

[Accepted-only comparison of all 155 pairs](../backend/validation/source_b_continuity_phase2_20260930/accepted_only_155_pairs.json), [raw-enabled comparison](../backend/validation/source_b_continuity_phase2_20260930/accepted_plus_supported_raw_155_pairs.json), and the corresponding full `*_trace.json` files preserve classifier/proximity exposure, track keys, observed states, hits and eligibility. The prototype examines all supported pair combinations, while the production trace contains only comparisons visited before its proximity short-circuit; totals are not conflated.

## Different-Pair Regression

Offline corrected architecture: **PASS** for pair ownership.

Current production: **FAIL**, unchanged.

CURRENT_PRODUCTION_PAIR_SAFETY = **FAIL**

Explicit qualifying A↔B, C↔D, E↔F inputs yield **1,1,1**, no pair reaches three, and confirmation eligibility is false. The existing failing production test remains unchanged and was also invoked directly; it still raises `AssertionError: 'confirmed_crash' == 'confirmed_crash'`. [Failure log](../backend/validation/source_b_continuity_phase2_20260930/production_safety_failure.log).

## Positive Same-Pair Control

**PASS**

The direct canonical-key control yields three hits for `(1,2)`, `(2,1)`, `(1,2)` within five seconds. A separate end-to-end synthetic detector sequence supplies two independently tracked moving vehicles, measured closing, a close interaction proxy and subsequent stopping. It retains canonical pair **(1,2)**; the last three observations at **1.0, 1.1 and 1.2 s** produce **1,2,3 qualifying hits** and offline eligibility. Positive conditions come from synthetic detector observations, not Source B labels or a manually asserted interaction flag.

[Synthetic control traces](../backend/validation/source_b_continuity_phase2_20260930/synthetic_controls.json) retain detector boxes, tracker keys and interaction/ledger values. This validates the deterministic pipeline contract; it is not evidence that a real Source B collision was confirmed.

## Interaction Evidence

**INSUFFICIENT**

INTERACTION_EVIDENCE_INSUFFICIENT

The actual A/B pair has no detector-supported pair trajectory. Relative approach, separation change, velocity, geometry and immediate post-interaction signals therefore cannot be attributed through stable A/B tracks. Phase 1's visual convergence remains diagnostic context; its **CONTACT_NOT_DIRECTLY_RESOLVABLE** conclusion is unchanged. Full-scene classifier confidence and unrelated queue proximity cannot fill the missing physical evidence.

## Duplicate Identity Protection

**PASS in the offline deterministic controls.** Two heavily overlapping accepted proposals, even with different detector classes, produce no observed identities. Existing tracks connected to such ambiguity are revoked and their pair histories removed. Crossing/ambiguous candidates are rejected rather than reassigned. A dormant last-observed location has no current bbox and cannot become a second collision participant. These controls do not establish universal physical identity correctness in unobservable occlusions.

## Interaction Transition Requirement

**PASS in the offline deterministic controls.** A contact proxy now requires a current near observation **and an earlier not-near observation in the same measured pair history**, together with qualifying measured approach. A dedicated negative supplies vehicles that remain near while closing and stopping: measured closing occurs, but no contact proxy or eligibility is created because the transition never occurred. The positive approach→near→post control still yields three qualifying pair-owned hits. No threshold was adjusted against Source B.

## Pair Ownership Alone

Safe for collision verification: **NO**

Reason: isolating identity ownership prevents different pairs donating hits, but the **same unrelated queue pair** still reaches **3/3** from full-scene classifier and proximity evidence. Correct ownership is necessary bookkeeping, not sufficient collision evidence.

## Pair Ownership + Interaction Verification

Queue regression: **PASS**

Positive collision control: **PASS**, synthetic offline eligibility only.

Exact queue rejection at frames 69–71 in both modes: `measured_closing=false`, `approach=false`, `contact_proxy_at=null`, `post_observations=0`, `interaction=false`, `qualified=false`, **hits=0**. Although classifier/proximity supply ownership-only hits 1→2→3, no measured approach-triggered not-near→near contact proxy exists and therefore no post-proxy sequence can qualify. No real physical contact or Source B positive confirmation is claimed.

[Final queue comparison](../backend/validation/source_b_continuity_phase2_20260930/queue_comparison.json) validates the same key across all three observations in each mode and records the exact rejection conditions separately from ownership-only eligibility.

## Source B Detector Reality

Participant A accepted seed: **NO**

Participant A raw proposal: **One**, frame 41/+4.078 s, confidence **0.387290418**, rejected below **0.40**; no prior accepted A history.

Participant B proposal: **NO** in all ten assessable labeled observations.

A track recovered: **NO**

B track recovered: **NO**

True A↔B pair recovered: **NO**

**TRACKING_CANNOT_RECOVER_AN_UNOBSERVED_PARTICIPANT**

## Negative Controls

| Control | Result | What was checked |
|---|---|---|
| Queue | PASS | Stable close pair with high classifier cannot qualify from continuity alone; ownership-only comparator deliberately demonstrates false eligibility |
| Parked | PASS | No approach/contact/post sequence |
| High unrelated classifier | PASS | Score alone cannot qualify |
| Proximity only | PASS | Close boxes alone cannot qualify |
| Changing pair | PASS | A↔B, A↔C, A↔B preserves separate counts 2 and 1 |
| ID swap | PASS | Proposal-ID/order changes do not swap identities; ambiguous crossing revokes identities and pair history; impossible jump gets a new ID |
| Expired pair | PASS | Five-second expiry and revoked tracks prevent inherited hits |
| Duplicate observation | PASS | No new observation or artificial hit |
| Missing participant | PASS | No pair fabricated; predicted-only state contributes no hit |
| Aftermath only | PASS | Stationary close vehicles with high scene score cannot create a new collision sequence |

Additional controls pass for bbox jitter, supported brief miss, long miss, unsupported lone seed, class/scale mismatch, direction reversal, unrelated high-confidence intrusion, weak-history exhaustion, context-rejected raw proposals, raw support without collision hits, bounded capacity/overflow, and a close pass without post-interaction stopping. These are finite deterministic controls, not broad field validation.

## Detector Support Gate

**MULTIPLE_DETECTOR_AND_ACCEPTANCE_LIMITATIONS**

A loses eight assessable observations at proposal supply and one at acceptance; B loses ten at proposal supply. Conservative weak support cannot begin from the isolated A proposal. Detector proposals are the dominant practical blocker, with a separate observed acceptance loss. The evidence does not justify globally relaxing acceptance, changing models/thresholds, or claiming the current tracker can recover the actual pair.

## Performance

Measured over 88 cached observations per mode; no model inference is included.

| Metric | Accepted-only | Accepted + supported raw |
|---|---:|---:|
| Association median / maximum | 0.169 / 1.916 ms | 0.271 / 1.346 ms |
| Pair experiment median / maximum | 0.190 / 0.861 ms | 0.224 / 0.914 ms |
| Peak retained tracks | 6 | 6 |
| Peak retained pair states | 12 | 12 |
| Expired/revoked track IDs over replay | 15 | 23 |

Standalone unchanged ledger: **0.0041 ms median**, **0.964 ms maximum** across 10,000 updates. These are local measurements under shared-machine load, not production latency guarantees. Pair experiment cost includes interaction features and both comparison ledgers.

A 10,000-observation bounded-state exercise retains **4 tracks / 6 pairs**, with track histories capped at 16. Incremental Python allocation at 1,000/5,000/10,000 observations is **233,656 / 234,048 / 234,408 bytes**, with peak **278,496 bytes**; the small increase includes retained measurement records. After a >5-second empty gap, tracks, pair states and ledger pairs are all **0**. A one-second track expiry is exercised independently. Tracemalloc is not process RSS; emitted replay files grow with observations, while the prototype's retained state is bounded. [Performance artifact](../backend/validation/source_b_continuity_phase2_20260930/performance.json).

## Tests

| Group | Result |
|---|---|
| New conservative tracker/pair/negative/positive controls | **40 passed** |
| Existing PairHitLedger tests | **6 passed** |
| OFFLINE PAIR-SAFETY TESTS, combined | **46 passed, 0 failures** |
| Existing live diagnostic/current decision tests | **80 passed, 1 expected failure** |
| Existing ByteTrack/logical continuity/temporal verifier tests | **37 passed** |
| Total | **163 passed, 1 expected failure; 164 tests** |
| CURRENT PRODUCTION PAIR-SAFETY TEST, direct invocation | **FAIL**, real unresolved defect |

[Machine-readable results](../backend/validation/source_b_continuity_phase2_20260930/tests.json) and separate `offline_tests.log`, `production_collision_tests.log`, `existing_experimental_tests.log` preserve exact outcomes. Passing existing experimental tests does not negate the additional raw-ID jump probe. No existing test was edited, disabled or newly marked expected-failure.

Reproduction from the repository root, using `backend/.venv/Scripts/python.exe`: run the new directory's `run_study.py`, `render_review.py`, `validate.py`, then `finalize.py`. Inputs are Phase 1 artifacts; the study verifies its saved protection manifest before execution. The prototype has no app, detector, DB, RTSP, incident or alarm imports. Diagnostic scripts write only within their new directory. All evaluated modes use fresh state and host elapsed time.

## Changes

Production collision logic: **UNCHANGED**

Alarm: **UNCHANGED**

Incident pipeline: **UNCHANGED**

Production thresholds: **UNCHANGED**

3-hit requirement: **UNCHANGED**

5-second window: **UNCHANGED**

Production detector threshold: **UNCHANGED**

Classifier threshold: **UNCHANGED**

Models: **UNCHANGED**

Training: **NONE**

Source B: **UNCHANGED**

Phase 8C: **UNCHANGED**

Phase 1 annotations/artifacts: **UNCHANGED**

Only this report and the new Phase 2 offline directory were added. The existing workspace edits were preserved. Before/after protection manifests cover Phase 1 artifacts, protected Source B/model/production/service/Phase 8C files inherited from Phase 1, and its report. No physical reproduction or production incident/alarm action occurred.

Final [protection audit](../backend/validation/source_b_continuity_phase2_20260930/protection_audit.json): **145 files checked, zero changed**. [Artifact validation](../backend/validation/source_b_continuity_phase2_20260930/artifact_validation.json) checks both 88-observation replays, all 155 comparison records per mode, observed-state restrictions, bounds, protected hashes and report links. The recovered prototype's SHA-256 also matches its recovery-start snapshot.

A bounded **future design**, not integration authorization, is concrete: own a tracker and pair state per camera/session; consume each fresh detector observation once; preserve production acceptance; recheck every association; revoke pair history on identity ambiguity/expiry; admit only observed same-pair interaction evidence to the unchanged ledger; keep incident/alarm handling outside tracking. Before wiring it, actual-participant detector support, independent identity/interaction validation and negative-event coverage remain required. The prototype's research interaction gates are not ready-made production thresholds.

## Phase 2 Verdict

**MULTIPLE_PHASE2_LIMITATIONS**

The requested deterministic ownership, positive, negative, expiry and conservative-association controls pass. However, no actual Source B A/B pair was recovered, physical interaction remains unresolved, existing continuity has an independently reproduced unsafe shortcut, and pair ownership alone still permits unrelated queue eligibility. A bounded offline design exists, but these results do **not** establish safe real-participant production integration. Detector support is the next demonstrated evidence problem; Phase 3 was not started.
