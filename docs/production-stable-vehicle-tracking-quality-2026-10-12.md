# Production vehicle tracking identity quality — 2026-10-12

Work branch: `work/track-identity-stabilization-2026-10-12`.

**Latest root-cause audit: TRACK_IDENTITY_READY_QUALITY_LIMITED.** Independent
packet counting and fresh telemetry rule out per-frame tracker recreation,
session drift and a continuation-counting defect. Slower analysis cadence and
conservative ownership gates explain the observed collapse, followed by age
expiry; the exact historical pipeline stall origin remains unproven. A fresh
30-second audit reached 2.30 FPS and 19 visually correct continuations without
changing production code. See **ZERO-CONTINUATION ROOT-CAUSE AUDIT** below.

**Latest extended-validation result: TRACK_IDENTITY_READY_QUALITY_LIMITED.**
The fresh 90.047-second Bago run contains 80 analyzed frames and 601 real DETECTED
observations, all with singleton IDs. Zero observed cross-vehicle transfers do
not establish stable ownership when there are no continuations. No fresh pair
reached two shared observations; at least 11 physical fragmentations were
visually verified. Historical pair 346/354 remains separate. Production behavior
is unchanged. See **EXTENDED PAIR-CONTINUITY VALIDATION** below.

**Tracking-continuity milestone: TRACK_IDENTITY_READY_QUALITY_LIMITED.** Its 20-second
Bago validation has zero observed cross-vehicle transfers and 15 verified
same-vehicle continued transitions across seven vehicles, including histories of
three, four, and five analyzed observations. At least 25 fragmentations remain;
the severe fragmentation and display-replay scene limit readiness. Tracking-only
changes and 305 passing tests preserve the existing pair-safety expected failure.

**Initial identity-only pass: TRACK_IDENTITY_READY_QUALITY_LIMITED.** The reproduced identity transfer
is rejected and deterministic ownership tests pass. The bounded Bago run had zero
observed transfers, but also zero ID continuations: every accepted detection started
a new identity. This is a severe quality limitation, not evidence of stable live
continuity or readiness for physical pair ownership. No pair-safe integration was
performed. The native road scene and FOBOS remain unvalidated. The subsequent
continuity improvement is described below; these initial measurements are retained
as the before result.

## Reproduced failure and measured cause

Before editing the tracker, the committed implementation was replayed against
rounded boxes from the preceding normal-traffic physical review. This reproduced
one silver-to-black vehicle handoff; it was a diagnostic replay, not a fresh camera
validation. Evidence is local in
`backend/validation/production_tracking_quality_20261012/reproduced-transfer.json`.

Camera/session: `Bago` / `normal-review`; old ID: 1; sequences: 130 to 138;
elapsed/track age: 0.55 s; misses: 0; class: car; one prior track, two detections.
The previous silver box was `[734, 239, 991, 428]`; its predicted center was
`[862.5, 333.5]` because it had only one real observation.

| Candidate | Box | Actual center | IoU | Center distance | Old cost/result |
| --- | --- | --- | --- | --- | --- |
| Same silver car | `[505,171,745,327]` | `[625,249]` | 0.01138 | 252.08 px | 1,000,000; rejected |
| Different black car | `[776,274,1060,469]` | `[918,371.5]` | 0.46737 | 67.26 px | 0.45134; inherited ID 1 |

The supported cause is a permissive geometric continuation after a frame gap:
the different vehicle occupied the previous region, while the real vehicle moved
outside the gate. Class compatibility and geometry could not distinguish them;
there was no appearance check or short bootstrap deadline. This was **not** a
greedy matcher: Hungarian assignment was already present. Crossing, overtaking,
occlusion, and detection ordering are not established causes of this particular
replay. The previous physical review also supplied bus/van and large-to-small
handoff cases retained as deterministic tests.

After the fix, both replay candidates receive new IDs (2 and 3); black does not
inherit ID 1. Its bootstrap-gap and motion gates reject the edge. This replay
contains no source pixels, so it demonstrates geometric rejection rather than
appearance validation. Separate pixel-backed replacement tests exercise appearance
rejection at short intervals. See local `repaired-transfer.json`.

## Association audit and implementation

Previously: vectorized geometry, Hungarian rectangular minimum-cost assignment,
then ambiguity rejection. Cost was `0.65*(1-IoU) + 0.35*normalized_distance/0.65`.
Center distance used the larger box diagonal, size ratios could reach 1.8, and
ordinary consecutive matches had no positive minimum IoU. Miss recovery required
old-box IoU 0.25 and predicted IoU 0.10. Velocity came from the last two real
centers; extrapolation duration was capped but displacement was not. State survived
1.5 s or four misses. Birth IDs followed detection order. Assignment was one-to-one,
but rejecting ambiguous edges after assignment could consume useful alternatives.

Now, hard gates and unresolved ownership are applied **before** global assignment.
Tracks are sorted by ID; detection columns and birth allocation are ordered by
class and box coordinates. The original detector array order remains unchanged in
the response. Hungarian assignment includes one unmatched dummy column per track
at cost 0.95; invalid edges cost 1,000,000. A detection or track can participate in
at most one accepted match. Exact duplicate observations remain distinct detector
records with distinct IDs; their physical ownership is deliberately unresolved.

| Gate | Current bound |
| --- | --- |
| Class | Exact normalized label compatibility |
| Elapsed since last real detection | At most 0.65 s |
| Bootstrap (fewer than two real observations) | At most 0.40 s |
| Recovery after misses | At most 0.60 s |
| Predicted-box overlap | IoU at least 0.25 |
| Width/height change | Each reciprocal ratio at most 1.35 |
| Aspect change | Reciprocal aspect ratio at most 1.25 |
| Center residual / smaller box diagonal | At most 0.30; bootstrap 0.20 |
| Miss uncertainty | Center limit divided by `1 + 0.5*misses` |
| Miss recovery support | Last real box IoU at least 0.25 |
| Current appearance distance | At most 0.08 |
| Appearance distance from birth anchor | At most 0.10 |
| Duplicate overlap | IoU at least 0.75 blocks continued ownership |
| Ambiguity | Competing feasible costs within 0.10 block ownership |

Appearance is nine normalized Lab quartile statistics from a central crop of the
exact analyzed source frame. Crops are reduced to 12×12, then color conversion and
quantiles are batched. Distance takes the greater of mean channel-statistic change
and maximum median-channel change. An immutable birth signature bounds gradual
drift. No model, extra inference, retained crop, or image export is added to the
tracker. Invalid, tiny, or border-truncated crops cannot authorize a pixel-backed
continuation. Production supplies the exact uint8 BGR source frame. Geometry-only
mode remains available for existing unit callers; it does not establish pixel
identity and is not the live production call mode.

The cost is `0.55*(1-IoU) + 0.30*residual/0.30 + 0.15*appearance_distance/0.08`.
The bounds are conservative rejection choices tested against reproduced and
synthetic cases, not physically calibrated universal vehicle-motion limits.
They were not relaxed after the slow live run.

## Prediction, ambiguity, and lifecycle

Velocity is the component-wise median of up to three real-observation differences
from the latest four real observations. Prediction duration remains at most 0.75 s;
displacement is additionally capped at half the last real box diagonal. Both
histories remain bounded at 16 points, and prediction never feeds velocity.

Near-tied feasible alternatives on either assignment side reject ownership. The
affected old identities retire so later observations cannot resurrect them. Highly
overlapping duplicate detections cannot inherit IDs or seed continued ownership;
their newly allocated identities retire on the next observation.

Identity scope remains `(camera_id, session_id, track_id)`. There are at most 256
tracks. Retirement occurs after 1.5 s since a real observation, four missed analyzed
frames, resolution changes, ambiguous ownership, or unresolved duplicate origins.
At capacity, missed tracks are evicted by last-real time and ID. IDs increment and
are never recycled within a session. Session reset clears histories and permits
numeric reuse only in the new session. Duplicate/late sequences and retired sessions
are rejected before mutation. Predictions have `detected=false`,
`collisionObservation=false`, and their last real detection sequence. Their
confidence is retained from the last real observation, not newly manufactured
detector confidence. They never enter collision counts, geometry, hits, or evidence.

## Production call sites and preserved scope

`backend/main.py` owns one tracker per live worker (construction near line 2300).
Stop, capture connection/release, and explicit post-disconnect seed reset state.
The sole production update is guarded by the worker lock and captured session near
line 3016. Its only integration change is `source_frame=frame`. Tracking metadata
is published with the exact analyzed frame and returned separately as predictions.
Shared TypeScript types describe IDs/predictions; no UI or collision consumer was
changed. Repository search found no other production session-tracker update.

The accepted detector boxes, labels, confidence, counts, and sequence/frame
provenance remain intact. Collision code continues consuming real `response_boxes`
and the existing scene-level hit window. No pair ledger, crash threshold, alarm,
incident, model, detector threshold, inference scheduler, or frontend change was
made. The reserved collision recording was never opened.

## Deterministic and regression verification

Production tracking: **42 tests pass**, including crossing, close following,
overtaking, reversed detection order, canonical birth IDs, one/two-frame miss
recovery, replacement near a missed track, replacement without an empty frame,
gradual/abrupt scale and aspect changes, class mismatch, overlapping duplicates,
six simultaneous vehicles, ambiguity retirement, retirement/non-reuse, camera
isolation, actual reconnect/reset, bounded histories/capacity, stale gaps,
appearance drift, invalid pixels, safe bounded diagnostics, and prediction exclusion
from crash hits. Pixel-backed following and simultaneous-vehicle tests require
continuity as well as correct ownership; tests do not merely accept all-new IDs.

The repaired physical identity assertion is now a regular passing test. The
separate known scene-level pair-safety expected failure remains unchanged:
`test_distinct_physical_pairs_must_not_share_three_hit_confirmation` in
`backend/tests/test_live_collision_diagnostics.py`.

Relevant isolated regression run: **292 total, 291 passed, 0 failures, 0 errors,
1 expected failure**, 45.118 s. It covered production/legacy/logical tracking,
temporal verification, pair classifier/ledger, crash decisions/state/aftermath,
vehicle tiers, live diagnostics, webcam sources/pipeline, scheduler, monitor
restoration, preprocessing, camera health/performance, and Phase 2 decision
contracts. Tests used temporary SQLite through the isolated runner; the operational
database was not initialized or seeded. An initial invocation named a nonexistent
test module; the corrected complete run has the results above. Local logs and
`regression-results.json` retain the evidence.

## Bounded Bago camera validation

The capture-only probe was visually checked before inference. Bago was physically
available and aimed at a display showing ordinary multi-vehicle highway traffic.
This is a live **camera-domain screen-replay proxy**, not direct road CCTV validation.
No reserved collision media or uploaded recording was used. After six seconds of
warmup, the production latest-frame worker ran for a 20-second measurement window.
Every completed analyzed observation was recorded (21, below the 64-frame bound).
All 21 source images and their bounded diagnostics were reviewed. Local evidence is
under `backend/validation/production_tracking_quality_20261012/` and contains media
that must remain outside checkpoint staging.

| Metric | Observed result |
| --- | --- |
| Cross-vehicle ID transfers | **0** within the recorded window |
| Continued detected identities | **0** |
| Physical fragmentations | **At least 32** visually verified transitions; exact count unresolved |
| Accepted detector observations | 117 |
| New tracks | 117; 5.85/s; one new ID per accepted observation |
| Retirements during window | 110 |
| Predicted missed-track packets | 146 |
| Analyzed frames / FPS | 21 / 1.05 FPS |
| Analyzed source timestamp gaps | 0.500–2.329 s |
| Tracking time with diagnostics | Mean 10.26 ms; p50 8.37; p95 18.51; max 20.60 |

Every `(session, ID)` occurred in exactly one detected observation during the
window, so none could transfer between observed vehicles. This zero-transfer result
is consequently weak evidence for association quality: **no physical continuation
was exercised**. All frame gaps exceeded the 0.40 s bootstrap gate. New tracks never
accumulated enough real observations to establish motion. The validated safety
choice is fragmentation under this cadence; useful live continuity is not proven.

The fragmentation lower bound counts 32 manually confirmed same-vehicle/new-ID
transitions between adjacent recorded frames. Occluded or uncertain participants
were omitted. A van with duplicate detections contributes only one physical edge
for its reviewed transition. This is not an exact physical-vehicle census; neither
117 new IDs nor 146 predictions should be mislabeled as a fragmentation count.
`physical-review.json` records frame numbers and old/new IDs for each counted edge.
Raw `live-results.json` retains null physical counts pending review; the separate
review artifact supplies the final zero-transfer result and lower bound.

Validation-owned startup database writes, crash persistence, and evidence writes
were blocked; 16 persistence attempts were rejected. The unchanged scene detector
reported possible-crash status even on this normal scene. No incident was stored
and no frontend alarm was invoked. These scene-level outputs were not changed to
make the identity run pass. The primary detector result was reused by the worker;
the harness added no second inference for tracking. Review JPEGs were written only
after the measured window.

## Performance and limitations

Synthetic baseline/current measurements used the committed previous tracker and
the new tracker with exact source pixels, five warmup frames and 30 measured frames
per count. They measure tracker cost, not detector speed; appearance adds work.

| Simultaneous vehicles | Previous p50/p95 ms | Current p50/p95 ms |
| --- | --- | --- |
| 1 | 0.81 / 1.47 | 2.30 / 2.69 |
| 8 | 1.28 / 1.77 | 3.78 / 4.15 |
| 32 | 2.88 / 3.60 | 8.51 / 13.77 |
| 64 | 5.33 / 5.96 | 14.91 / 16.95 |
| 256 | 34.71 / 39.98 | 130.83 / 161.00 |

Batching reduced the initial per-crop implementation's p50 from 7.16 to 3.78 ms at
eight vehicles and 228.36 to 130.83 ms at 256. This is an implementation optimization,
not an improvement over the old geometry-only tracker. At the extreme bound,
maximum measured cost was 182.24 ms and should not be described as negligible.
All synthetic identities/history counts remained bounded (256 tracks, 4,096 real
points and 4,096 display-history points at maximum). Normal-count overhead and
the live 8.37 ms median are small relative to the observed roughly one-second live
analysis cycle. Detector-only latency and CPU utilization were not isolated here;
the comparison does not attribute the full cycle to YOLO or prove scalable FPS.

The current cadence cannot bootstrap stable identities under these bounds.
Similar-looking vehicles, occlusion, exposure changes, duplicate boxes, and
perspective can remain unresolved; color statistics are rejection evidence, not a
proof of unique physical identity. Synthetic tests and a zero-continuation live
window cannot establish a general zero-transfer guarantee. Native road footage,
useful live continuity, and same-pair collision integration remain future work.

FOBOS was unavailable to the validation-owned capture process (connection-lost / no
usable frame). No cause beyond failed availability was established and no USB
tracking results were invented.

FOBOS_PHYSICAL_VALIDATION_PENDING

## Continuity improvement — subsequent pass

### Diagnosis from reviewed physical observations

The 32 manually verified same-vehicle fragmentation edges from the first run were
measured again using their exact accepted boxes, timestamps, and classes. Old
bootstrap velocity was zero, so center displacement was also predicted-center
error. These edges had zero preceding misses and the existing ambiguity margin of
0.10. Per-edge measurements, original available rejection reasons, competing boxes,
and JPEG-derived appearance measurements are in the local
`production_tracking_continuity_20261012/same-vehicle-measurements.json` artifact.
JPEG appearance replay is approximate; original in-memory diagnostic values remain
in the preceding run's observations.

| Measurement / old rejection | Reviewed same-vehicle edges |
| --- | --- |
| Elapsed time | 0.500–1.359 s; median 0.766 s |
| Bootstrap deadline exceeded | 32 / 32 |
| 0.65 s association deadline exceeded | 22 / 32 |
| 0.20-diagonal bootstrap residual exceeded | 32 / 32 |
| IoU below 0.25 | 31 / 32 |
| Width/height ratio above 1.35 | 17 / 32 |
| Aspect ratio above 1.25 | 8 / 32 |
| Detector class changed | 5 / 32 |
| JPEG-derived appearance change above 0.08 | 20 / 32 |

Normalized center displacement was 0.38–2.41 smaller-box diagonals; apparent speed
was 0.51–2.08 diagonals/s. Every bootstrap was rejected before it could establish
velocity. Raising only the deadline would therefore be insufficient and unsafe.

An initial appearance-only longer-gap candidate restored five IDs in the saved
normal-scene replay, but manual review found three cross-vehicle continuations: a
truck-to-car replacement, one white SUV receiving another SUV's identity, and a
white SUV-to-van replacement. It was rejected **before live validation**. The local
`rejected-appearance-only-replay.json` preserves those findings. This demonstrated
why appearance statistics plus narrow candidate uniqueness cannot prove identity.

### Separate path for stronger evidence at lower cadence

The earlier short-gap bounds remain. A separate pixel-backed
path handles gaps up to 1.25 s, including significant pixel-backed bootstrap
movement below 0.40 s. It preserves class, width/height
1.35, aspect 1.25, birth-anchor 0.10, duplicate rejection, and global one-to-one
ownership. Its current appearance limit is **stricter**, 0.05, and both assignment
sides need a 0.025 appearance separation from plausible rivals in addition to the
existing 0.10 assignment-cost ambiguity rule.

Observed displacement must be within `min(2.5, 0.10 + 1.25*elapsed)` smaller-box
diagonals. This is an explicit elapsed-time bound, not a fixed pixel radius.
For established histories, center prediction uses actual elapsed time and the
median recent real velocity; residual must be within
`min(0.35, 0.15 + 0.15*elapsed)/(1 + 0.5*misses)` diagonals. Old-box IoU is not
required in this stronger path, so supported nonoverlapping movement can continue.
The earlier display prediction remains capped and separate from detected evidence.

A bootstrap additionally requires independently checked sparse pixel motion from
the previous **analyzed** frame. Candidate boxes seed feature hypotheses, not
ownership. Forward/backward Lucas–Kanade flow must retain at least three corners
and 60% of the selected corners, with at most 1.5 pixels of round-trip error on the
reduced image, photometric error at most 14 in both directions, and median vector
spread at most 0.10 of a source box diagonal. Candidate center residual from that
feature motion must be at most 0.20 diagonals. A measured true black-car edge had
six of eight qualifying corners at error 14, versus four at error 12; all three
rejected false replay edges had **zero** qualifying corners at either threshold.
The resulting choice is evidence-based but not a universal physical calibration.

Bootstrap ownership also uses a wider rejection-only neighborhood (up to 2.1
diagonals/s, size 1.8, aspect 1.5, appearance 0.25). This prevents tight acceptance
limits from hiding a nearby alternative. These larger limits **only reject
continuation**; they never authorize one. Ambiguous ownership retires the affected
old identities. Weak/textureless motion, duplicate boxes, unsupported scale/class
changes, and unresolved neighbors still fragment. The subsequent first fresh run
exposed one transfer inside the original 0.40-second bootstrap window, so that
short-gap path was additionally tightened: pixel-backed bootstrap movement above
0.10 diagonals now also needs verified feature motion and wider ownership
uniqueness. Small stable changes and existing geometry-only unit callers retain
their earlier behavior. The tighter bootstrap safety check remains mandatory.

A second bounded run after that tightening produced 52 frames / 387 observations
at 2.6 FPS with **zero continuations**. It is preserved separately in `final-run`
and does not satisfy the continuity requirement. Diagnostics supplied 32 verified
pixel-motion edges. One actual same-car edge at 0.188 s had displacement 0.272
diagonals, flow residual 0.056, appearance 0.041, size ratio 1.167, and aspect ratio
1.158; all strong-path gates passed except its lower cadence cutoff. A strong
verified motion must not become unusable solely because it arrives just below
0.40 s. The stronger path now accepts significant moving bootstraps at that cadence
as well, retaining every other time, motion, appearance, and ownership bound.
The broad rejection neighborhood was not narrowed.

One missed observation may recover at up to 2.25 s only after at least two real
pixel-backed observations establish motion. Its stricter residual and ownership
gates remain mandatory. Such tracks alone receive a matching age allowance; old
bootstrap tracks and tracks with two missed observations do not. Predicted packets
never become detector observations or collision hits.

### Verification and measured before/after replay

All 42 preceding production tracking tests remain. Fourteen new deterministic tests
require continuation across 0.8, 1.0, and 1.2 s gaps, perspective changes, one missed
1 FPS observation, learned fast movement with zero real-box overlap, reversed
ordering, and same-appearance neighbors with distinguishable motion. They also
require fragmentation for converging trajectories, unresolved bootstrap owners,
near-threshold rivals, velocity contradictions, different appearances, two misses,
long absence, textureless bootstrap images, and similar-color short-gap replacements.
A cadence-boundary regression requires actual textured same-vehicle motion at
0.20, 0.40, and 0.41 s to continue under the same strong ownership gates.
The moving-image fixtures contain
deterministic visible texture; hidden participant labels never enter the tracker.

Final relevant regression: **306 total, 305 passed,
0 failures, 0 errors, one preserved scene-level pair-safety expected failure**.
The run completed in 53.923 s. The operational
database was excluded using the same isolated runner. No collision/XFAIL assertion
was weakened.

The final tracker replayed all 117 accepted observations from the previous 21 source
frames, with no new inference. Before: 117 new IDs, zero continuations. After: 116
new IDs, **one visually verified same-black-car continuation**, zero transfers in
the replay. All other observations fragmented. This is useful diagnostic evidence,
but **saved-frame replay does not replace fresh physical validation**. Re-encoded
JPEG pixels and a different runtime also prevent treating replay timings as live
performance. Final `replay-results.json` retains every association for review.

The 52-frame second live run was also replayed without inference after fixing the
cadence boundary. All six continued transitions were visually reviewed and matched
the same physical vehicles, with zero transfers. One black car retained replay ID
35 across frames 5–9 (five observations); a white car retained ID 39 across frames
6–8 (three observations). Before the boundary fix this recorded run had zero
continuations. Evidence is in `replay-final`, separate from the live capture and
the original one-FPS replay. The exact recorded silver-to-silver failure still
receives a new ID after the boundary fix.

### Fresh physical validation and performance

The refreshed Bago probe initially showed the room. Inference was withheld until
the operator restored normal traffic and a fresh probe was visually checked.
The first new 20-second run analyzed 56 frames / 402 observations at 2.8 FPS. It
had 13 continued-ID transitions; review verified 12 and found **one transfer**
between different silver vehicles (frames 22→23, sequences 194→200, ID 249).
The failed run is preserved in the continuity directory, with source frames and
diagnostics; it is not a passing validation.

The original short-gap bootstrap accepted that candidate at 0.390 s, IoU 0.619,
35.74 px center distance / 0.186 diagonals, scale ratio 1.059, aspect ratio 1.018,
same class, no preceding misses, and approximate JPEG appearance distance 0.071.
The different vehicle entered the previous region while the original silver
vehicle moved forward. This exposed the same geometry/appearance weakness even
within the previously conservative bootstrap deadline. After tightening that
path, replay rejects the exact wrong continuation through
`bootstrap_pixel_motion`. See `reproduced-short-transfer.json`. The following
final live run is separate from the failed run.

After the cadence-boundary fix and passing regressions, another fresh normal-scene
probe was visually checked and a third bounded run was captured in `boundary-run`.
All 49 analyzed source frames and all 15 continued-ID transitions were visually
reviewed. **Zero cross-vehicle transfers were observed; all 15 continuations
matched the same vehicles.** Seven vehicles continued. ID 146 held across frames
8–10 (three observations, 0.797 s); the distinctive purple truck, ID 218, across
19–22 (four observations, 0.828 s); red car ID 346 across 40–44 (five observations,
1.156 s); white SUV ID 354 across 41–44 (four observations, 0.953 s). The other
three identities each continued across two observations. These were separate
captured/analyzed frames, not synthetic predictions or repeated packets. Gaps in
the verified fresh continuations ranged from 0.203 to 0.484 s. Longer 0.8–1.2 s
continuations are covered by deterministic tests; the prior one-FPS saved replay
demonstrates one real same-car edge, not sustained native-road one-FPS tracking.

| Bounded physical measurement | Initial conservative pass | Latest continuity run |
| --- | --- | --- |
| Validation duration | 20 s | 20 s |
| Analyzed frames / accepted observations | 21 / 117 | 49 / 337 |
| Cross-vehicle ID transfers | 0 | 0 |
| Verified same-vehicle continued transitions | 0 | 15 across 7 vehicles |
| Visually verified fragmentation lower bound | >=32 | >=25 |
| New IDs first observed in the window | 117 | 322 |
| New IDs / second | 5.85 | 16.10 |
| Predicted missed-track packets | 146 | 861 |
| Retirement events | 110 | 328 |
| Measured analysis rate | 1.05 FPS | 2.45 FPS |

Fragmentation is a **nonexhaustive lower bound**, supported by 25 explicit reviewed
same-vehicle / different-ID edges in `boundary-run/physical-review.json`; an exact
exhaustive physical-identity count is unavailable. New IDs counted here are IDs
first appearing within the review window; some can originate during warmup.
Retirements may include warmup identities. Predicted missed packets count each
temporarily missed track on each observation, not distinct missed physical
vehicles. Different traffic density and live cadence make these independent
windows unsuitable for attributing FPS or total-ID-rate changes to the tracker.
No detector-FPS improvement is claimed.

Latest measured live tracking overhead, with diagnostics enabled, was mean 34.845
ms, p50 33.841 ms, p95 53.955 ms, maximum 96.616 ms per analyzed frame. There were
49 captured records, below the 128-record validation bound; none were truncated.
Operational persistence was blocked in the validation-owned workers (32 attempts),
worker-generated image writes were blocked during inference, and source images
were saved only after the bounded window. The validation used the existing primary
model result, did not open the reserved collision recording, and stopped its
workers afterward. Existing scene-level possible-crash classifications were not
changed by this tracking task; this is not a collision false-positive validation.

Tracking uses no additional detector/model inference. It retains one grayscale
analyzed frame per session with its longest side at most 640 pixels, at most eight
corners per candidate hypothesis and 512 feature points per flow pass. State, pair
matrices, histories, diagnostics, and assignment remain bounded by the original
256-track and 16-point limits. The grayscale frame is cleared on session reset and
stop. No optical-flow output changes boxes, counts, detector confidence, collision
evidence, or the existing shared latest-frame inference architecture.

An isolated, no-inference before/after benchmark used identical synthetic pixels
and accepted boxes, five warmup updates and 20 timed updates per scenario. Before
means the immediately preceding conservative tracker snapshot, not the unsafe
original committed implementation. Measurements in milliseconds:

| Scenario | Before p50 / p95 | After p50 / p95 | After maximum |
| --- | --- | --- | --- |
| 8 vehicles, 0.2 s gap | 2.774 / 3.738 | 6.821 / 7.475 | 7.747 |
| 8 vehicles, 1.0 s gap | 3.561 / 4.351 | 19.813 / 25.444 | 26.602 |
| 64 vehicles, 0.2 s gap | 13.714 / 15.353 | 15.191 / 18.962 | 19.532 |
| 256 vehicles, 0.2 s gap | 111.325 / 138.310 | 104.930 / 157.103 | 188.117 |

The one-FPS synthetic scenario retained eight identities after the change; the
preceding tracker kept fragmenting. At maximum synthetic occupancy, retained
history stayed within 4,096 points and the 1920×1080-source grayscale cache was
230,400 bytes. Feature count and finite state are bounded, but overhead increases
when feature work is required; these measurements are not a latency guarantee or
an exhaustive all-256-vehicles-moving optical-flow benchmark. High-cadence stable
observations avoid the extra continuity pair comparisons when they are unnecessary.

Remaining limitations: most accepted observations still start new IDs. Uncertain
neighbors, class flips, perspective changes outside the unchanged scale/aspect
bounds, weak texture, large displacement, and appearance changes deliberately
fragment. Pixel evidence and learned velocity cannot guarantee identity for all
lookalike vehicles or unseen crowded scenes. Bago was a physical Tapo feed of
ordinary traffic played on a display, not a calibrated native-road deployment.
The bounded success demonstrates some real continuity while retaining zero
observed transfers; it does not establish readiness for pair-hit-ledger integration
or sustained native-road collision verification. All failed intermediate runs are
retained, and their results are explicitly separated from the final tracker run.

FOBOS_PHYSICAL_VALIDATION_PENDING

## PAIR-CONTINUITY READINESS

This task starts from the committed/pushed tracking milestone `f754a4b5`. It does
not restart or undo that work. **No production tracker, detector, collision,
threshold, incident, alarm, UI, or scheduler behavior was changed.** Existing
evidence already demonstrated a qualifying pair, so no additional tracker changes
were justified under this task's conditional improvement rule. Work added twelve
pair-focused tests, offline measurements, and two isolated bounded live captures.
No production collision pair state or pair-hit-ledger integration was created.

The minimum identity foundation is observed in the committed milestone capture:
the red car (ID 346) and white SUV (ID 354) retain distinct correct IDs on four
shared analyzed observations. The fresh first window fragmented all observations;
the repeat window demonstrated a different pair on only two shared observations.
The three-observation target therefore **did not repeat in either fresh window**.
The earlier valid example remains evidence, but it is insufficient to declare
consistent present pair readiness. The verdict stays quality-limited.

### Counting and physical review

Only boxes with `detected=true` and `observationKind=DETECTED` count. Predictions
are inspected separately and never increase single-track or shared-pair depth.
Identity is `(camera_id, session_id, track_id)`. Canonical numeric pair ordering is
used solely in an offline report, with no collision evidence accumulation.
Consecutive means adjacent **analyzed observations**; the capture sequence numbers
can skip because the existing worker analyzes the latest frame. Elapsed durations
use source capture monotonic timestamps, measuring actual elapsed clock time rather
than presumed FPS. Duplicate analyzed packets are rejected by the offline analyzer.

All continued transitions in both the earlier and repeat captures were visually
checked against their exact saved source frames. All 36 first-fresh and 50 repeat
source frames were reviewed. The distributions below count detector-ID lifetimes,
not a claimed census of unique physical vehicles: singleton IDs can include
duplicate/false detections and have no independent identity continuity proof.
The physically verified continued subset is seven earlier IDs and five repeat IDs.

| Maximum consecutive real detections per ID | Earlier milestone | First fresh window | Repeat fresh window |
| --- | --- | --- | --- |
| 1 | 315 | 295 | 278 |
| 2 | 3 | 0 | 2 |
| 3 | 1 | 0 | 2 |
| 4 | 2 | 0 | 1 |
| 5+ | 1 | 0 | 0 |
| Total observed ID lifetimes | 322 | 295 | 283 |

For the visually verified continued subset, the earlier distribution is 0 / 3 / 1
/ 2 / 1 in those five bins; the repeat distribution is 0 / 2 / 2 / 1 / 0. No
predicted-only packet enters either distribution. Fragmentation counts are explicit
nonexhaustive physical-review lower bounds, rather than new-ID or prediction counts.

Manually reviewed fragmentation edges additionally identify 36 earlier, 12
first-fresh, and 15 repeat singleton ID histories. The full reviewed-ID distributions
are respectively **36 / 3 / 1 / 2 / 1**, **12 / 0 / 0 / 0 / 0**, and
**15 / 2 / 2 / 1 / 0**. Several singleton IDs belong to the same fragmented physical
vehicle, so these are reviewed ID histories, not unique-vehicle counts. Complete
per-ID camera/session, real depth, elapsed duration, intervening predictions,
physical correctness, and termination records are in
`backend/validation/production_pair_continuity_20261012/prior-verified-vehicles.json`,
`first-fresh-verified-vehicles.json`, and `repeat-fresh-verified-vehicles.json`.

### Per-vehicle verified continuity

All rows below use camera `CAM-30960048ED` (Bago). Earlier rows use session
`e4348a7bd4fc49289aefd2274255dba4`; repeat rows use session
`428cc8c28d244798babea00340979b93`. Every listed identity remained physically
correct throughout its detected history. There were **zero predicted/missed
packets between its detections**. Predictions after the final detected observation
are listed separately. Lifecycle retirement does not prove that a physical vehicle
left the image; it is the measured reason the old ID was retired.

| Capture / track ID | Consecutive real detections | Start–end sequence | Elapsed seconds | Predictions after final detection | Lifecycle termination |
| --- | --- | --- | --- | --- | --- |
| Earlier / 146 | 3 | 122–133 | 0.797 | 2 | Age expiry, sequence 161 |
| Earlier / 218 | 4 | 199–211 | 0.828 | 3 | Age expiry, sequence 238 |
| Earlier / 331 | 2 | 306–309 | 0.250 | 3 | Four-miss budget, sequence 327 |
| Earlier / 346 | 5 | 314–330 | 1.156 | 2 | Age expiry, sequence 354 |
| Earlier / 354 | 4 | 317–330 | 0.953 | 2 | Age expiry, sequence 354 |
| Earlier / 363 | 2 | 327–330 | 0.250 | 2 | Age expiry, sequence 354 |
| Earlier / 365 | 2 | 327–330 | 0.250 | 2 | Age expiry, sequence 354 |
| Repeat / 171 | 4 | 182–196 | 0.922 | 3 | Age expiry, sequence 219 |
| Repeat / 186 | 3 | 192–202 | 0.687 | 3 | Age expiry, sequence 225 |
| Repeat / 257 | 2 | 269–274 | 0.360 | 3 | Four-miss budget, sequence 292 |
| Repeat / 298 | 3 | 297–305 | 0.672 | 3 | Four-miss budget, sequence 325 |
| Repeat / 311 | 2 | 305–309 | 0.219 | 3 | Age expiry, sequence 332 |

Earlier termination reasons were reconstructed from recorded real observations,
prediction packets, retirement events, and the unchanged tracker gates. Repeat
reasons use a bounded pre-update lifecycle snapshot in the validation harness.
Unknown warmup causes remain unknown in the aggregate retirement breakdown.

### Every evaluated co-continuous pair

The following are all candidate pairs with at least two consecutive shared real
detections; all seven reported rows were visually verified. Every row has distinct
IDs, zero transfers, zero missed/predicted gaps, zero fragmentation **within its
listed span**, and zero recorded ambiguity events for those members within that
span. Fragmentation outside a successful span is counted separately. The six
earlier pairs are combinations of the same four simultaneously visible vehicles,
not six independent traffic trials. Source traffic can repeat on the display;
independent capture sessions do not establish independent native-road trials.

| Capture / ordered IDs A, B | Shared start–end sequence | Shared real detections | Elapsed seconds |
| --- | --- | --- | --- |
| Earlier / 346, 354 | 317–330 | **4** | **0.953** |
| Earlier / 346, 363 | 327–330 | 2 | 0.250 |
| Earlier / 346, 365 | 327–330 | 2 | 0.250 |
| Earlier / 354, 363 | 327–330 | 2 | 0.250 |
| Earlier / 354, 365 | 327–330 | 2 | 0.250 |
| Earlier / 363, 365 | 327–330 | 2 | 0.250 |
| Repeat / 171, 186 | 192–196 | 2 | 0.281 |

The qualifying earlier pair spans source sequences **317, 321, 327, 330** (analyzed
frames 41–44). Both boxes are actual detections in every frame: the red car follows
the white van while the white SUV occupies the neighboring lane. Both IDs cease
their real detections after frame 44; later predictions do not extend the successful
pair span. The repeat pair consists of the distinctive purple truck and an opposing
white van. The truck continues on four observations and the van on three, but their
overlap is only **two**. Adding either member's unshared observations would falsely
manufacture a three-observation pair and is explicitly excluded.

### Measured churn causes

The earlier 322-ID / 328-retirement / 861-prediction run contains 25 manually
verified fragmentation edges. Exact original in-memory diagnostics were available
for 24 edges; the remaining edge came from an unresolved duplicate origin. Their
actual elapsed gaps were 0.313–0.610 s, median 0.391 s. Rejection counts overlap
because a single edge can fail several gates:

| Measured limitation on the 24 exact reviewed edges | Edges |
| --- | --- |
| Original short-path motion gate | 22 |
| Original bootstrap deadline | 11 |
| Strong-path pixel motion not available | 21 |
| Strong-path bootstrap ownership ambiguity | 20 |
| Strong-path prediction residual | 19 |
| Strong-path appearance limit | 10 |
| Aspect ratio bound | 5 |
| Width/height scale bound | 4 |
| Birth-anchor appearance bound | 3 |
| Second-best appearance separation | 3 |
| Time-scaled displacement bound | 2 |
| Class changed on the physical vehicle | 1 |

Unavailable pixel motion is a failed evidence prerequisite, not proof of poor
texture: size/class/appearance eligibility can prevent the flow check from running.
Likewise, a residual failure without verified bootstrap motion does not establish
that learned velocity was wrong. The diagnostics identify conservative gates and
ambiguity as substantial causes of fragmentation; their safeguards were retained.
One of the 25 reviewed edges had a duplicate origin, and one had an actual detector
class flip. The first fresh capture also provides a reviewed detector-intermittency
example: the grey SUV in the right lane, accepted as ID 38 in frame 0, is still
visible in frame 1 with no accepted box. There is no exhaustive intermittency count.

Earlier lifecycle reconstruction assigns 168 retirement events to age expiry, 99
to the four-miss budget, 16 to association ambiguity, and six to unresolved
duplicate origins. **39 causes remain unrecorded/uncertain at the warmup boundary**
(31 unseen warmup states and eight partially observed states). Known retirement
ages ranged from 0.203 to 2.031 s, median 1.578 s. Age allowance falls back to 1.5 s
after more than one missed observation, including established tracks; this explains
the later expiry of successful IDs. This is bounded lifetime behavior, not evidence
that each prediction packet represents a new missed physical vehicle.

Fresh snapshots provide a clearer retirement breakdown: the first window had 290
age expiries, five association ambiguity retirements, and two duplicate-origin
retirements, totaling 297. The repeat had 184 age expiries, 105 four-miss retirements,
19 association ambiguity retirements, and four duplicate-origin retirements,
totaling 312. At three preceding misses and a gap above 0.65 s, both association
paths are invalid, so the raw mixed budget/ambiguity event is classified as budget
expiry. No capacity or frame-dimension retirement was observed. Warmup identities
can retire inside the measured window, so retirements can exceed new IDs first
seen in that window.

The first fresh window had analyzed gaps 0.359–0.985 s, median 0.532 s; repeat gaps
were 0.219–0.890 s, median 0.390 s. Useful continuity varies with this measured
cadence and scene conditions. These independent windows do not isolate cadence as
the sole cause and do not establish an FPS improvement caused by tracking.

### Fresh physical Bago validation and performance

Each new capture used a fresh visually checked ordinary-traffic probe, six seconds
of uncounted warmup, and a bounded 20-second window. The first fresh capture is in
`backend/validation/production_pair_continuity_20261012/`; the repeat is in its
`repeat-run/` subdirectory. Existing milestone media was not overwritten. The
offline analyzer and physical-review records retain per-ID and per-pair details.

| Measurement | Earlier milestone | First fresh | Repeat fresh |
| --- | --- | --- | --- |
| Duration | 20 s | 20 s | 20 s |
| Analyzed frames / accepted observations | 49 / 337 | 36 / 295 | 50 / 292 |
| Actual analysis FPS | 2.45 | 1.80 | 2.50 |
| Observed ID transfers | 0 | 0 | 0 |
| Verified single-vehicle continued transitions | 15 | 0 | 9 |
| Maximum real detected continuity depth | 5 | 1 | 4 |
| Verified physical pairs with >=2 shared detections | 6 | 0 | 1 |
| Verified physical pairs with >=3 shared detections | 1 | 0 | 0 |
| Verified physical pairs with >=4 shared detections | 1 | 0 | 0 |
| Longest verified pair span | 0.953 s | None | 0.281 s |
| Reviewed fragmentation lower bound | >=25 | >=8 | >=10 |
| New IDs first seen in window | 322 | 295 | 283 |
| Retirement events | 328 | 297 | 312 |
| Missed-track prediction packets | 861 | 641 | 779 |
| Recorded ambiguity events | >=16 | 5 | 19 |
| Tracking mean / p95 / maximum | 34.845 / 53.955 / 96.616 ms | 40.379 / 66.026 / 95.528 ms | 31.051 / 55.363 / 68.185 ms |

Recorded ambiguity events count distinct camera/session/sequence/old-track events,
not failed candidate edges. Earlier diagnostics are capped at 64 edges per update;
the earlier ambiguity count is a lower bound. Fresh retirement snapshots confirm
the five and nineteen explicit association-ambiguity events. This does not quantify
every ambiguous physical ownership scenario rejected by an earlier gate.

Both fresh windows had zero observed transfers, but the first achieved that by
fragmenting every observation and therefore supplies no useful continuity proof.
The repeat's nine transitions all remain on the correct vehicles. The single fresh
pair falls short of three shared real observations. The earlier four-detection
pair is not substituted for a successful fresh repeat.

Tracking remains bounded by the existing 256-track, 16-history-point, 640-pixel
grayscale-frame, and 512-feature-point limits. Diagnostics are capped at 64 edges;
validation snapshots at 256 tracks and source capture at 128 records. Neither
capture was truncated. Per-frame tracker timings above exclude offline analysis
and source-image writes; validation instrumentation contributes some additional
worker overhead. No new production inference or duplicate detector call was
added. Shared latest-frame inference, model weights, and detector thresholds are
unchanged. Persistence was blocked in validation-owned workers (17 attempts in the
first window, 32 in the repeat); worker image writes were blocked during inference.
Source review images were written after each window. No reserved collision
recording was opened, no operational server restarted, and validation workers were
stopped after their bounded captures.

### Tests and remaining limitations

Twelve new deterministic production-tracker tests require two distinct IDs across
at least three low-cadence observations, ordering reversal, safe one-member miss
recovery, one-member fragmentation with the other continuing, ambiguous crossing
fragmentation, overtaking, close following, no physical ID swaps, rejection of a new
vehicle near a missed member, exclusion of predicted-only pair observations,
retired-ID non-reuse, camera isolation, and session reset. Hidden participant labels
are used only for assertions and never passed to the tracker. Existing unsafe
transfer regressions remain intact.

Relevant regression: **317 passed, zero failed, zero errors, one preserved
scene-level pair-safety expected failure**, 318 total in 56.659 s. Focused regression:
94 passed and the same expected failure, 95 total. The full regression covers
production/legacy/logical tracking, temporal verification, collision pair
classifier and ledger, live diagnostics, aftermath/state/decision contracts,
webcam pipelines, camera health/performance, restoration, preprocessing, and the
multi-camera scheduler. Operational database writes were excluded. The known
collision correctness expected failure remains visible and byte-unchanged; this
identity proof does not resolve it or authorize production pair-safe integration.

Bago remains a physical camera observing ordinary traffic played on a display.
This is **not native-road validation**. Most ID lifetimes contain one observation;
the three-shared-observation pair target was not reproduced in either fresh window.
Future pair-safe collision work requires more repeatable pair evidence and must
address the existing collision correctness failure separately. No tracker gates
were loosened to obtain a favorable pair count.

FOBOS_PHYSICAL_VALIDATION_PENDING

## EXTENDED PAIR-CONTINUITY VALIDATION

### Earlier blocked scene gate and incomplete attempt

The new task requests at least 60 seconds, preferably 90–120 seconds, with the
production tracker unchanged. A fresh Bago probe (CAM-30960048ED, camera overlay
2026-10-12 04:21:43 AM) shows two damaged vehicles in collision footage playing on
the display. This scene does not meet the ordinary multi-vehicle traffic gate.
The camera still observes a display; native-road validation is not established.
A second capture-only probe at camera overlay **04:25:18 AM** shows the same
collision scene. No inference validation was started after this recheck.

The validator was mistakenly launched before the probe image was visually
reviewed. Its Python processes were immediately terminated after that review.
There is no completed live-observations.json or live-results.json for this
attempt. Whether any warmup inference occurred before termination is unverified.
The attempt supplies no continuity evidence and is excluded from all success
metrics. A fresh ordinary-traffic probe must be reviewed before restarting.

For that aborted attempt, duration, analysis FPS, transfers, verified continuations,
maximum real observation depth, verified pair counts at 2/3/4 observations,
longest pair span, maximum shared count, fragmentations, new tracks, retirements,
predicted/missed packets, and ambiguity events are **not measured**. They must
not be reported as zero or copied from the prior short runs. No fresh qualifying
pair has been established by this attempt.

### Fresh resumed 90-second ordinary-traffic run

After the user restored ordinary traffic, a new capture-only probe at Bago camera
overlay **2026-10-12 04:30:37 AM** was visually reviewed before launching the full
validator. It shows multiple ordinary vehicles on the display. Every one of the
**80 analyzed source frames**, reviewed in 20 contact sheets, remains ordinary
traffic; no reserved collision scene is visible. The traffic clip visibly repeats,
so repeated appearances are not independent native-road trials. The prior blocked
attempt is excluded, and historical pair 346/354 is not pooled into this run.

Camera: `CAM-30960048ED`. Session: `81a7779056a34ef78fd742e2e765805c`.
Capture sequences: **81–1349**. Source camera overlay:
**04:31:45–04:33:13 AM**. Six seconds of warmup are excluded from the measured
window and physical review. The nominal 90-second recording window lasted
**90.047 seconds**; first-to-last retained capture timestamps span
**88.563 seconds**. These are different boundaries, not different runs.

| Fresh extended-run metric | Result |
| --- | --- |
| Measured validation duration | 90.047 s (90 s requested) |
| Analyzed source frames | 80 |
| Analysis FPS | 0.888 (0.89 rounded) |
| Actual DETECTED observations | 601 |
| Observed cross-vehicle ID transfers | 0 within reviewed real observations |
| Verified same-vehicle continued transitions | 0 |
| Maximum single-track consecutive DETECTED depth | 1 |
| Physically verified pairs with >=2 shared real detections | 0 |
| Physically verified pairs with >=3 shared real detections | 0 |
| Physically verified pairs with >=4 shared real detections | 0 |
| Longest verified pair co-continuity | 0 s; no qualifying pair |
| Maximum verified shared DETECTED observation count | 0; no verified pair streak |
| Visually verified fragmentations | **>=11**, conservative lower bound |
| New / first-seen track IDs within the window | 601 |
| Retirements | 587 |
| Predicted/missed packets | 808, excluded from all real continuity counts |
| Recorded ambiguity events | 3 distinct session/sequence/track events; diagnostics lower bound |
| Recorded ambiguity retirements | 3 |
| Dropped analyzed frames | 0; complete evidence within the bounded recorder |

Every real detected ID appears exactly once in this recording window: the ID-depth
distribution is **601 / 0 / 0 / 0 / 0** for depths 1 / 2 / 3 / 4 / 5+. These are
detector ID lifetimes, not a census of 601 physical vehicles. Zero observed
transfers is a weak result here because there is no repeated real ID to establish
continued physical ownership. Unreviewed warmup history is outside that claim.
Simultaneous singleton boxes do not count as pair co-continuity.

There are **no candidate pair streaks at >=2 real observations**, including before
physical filtering. Therefore there is no >=3 pair to review or report with two
stable physical owners, sequences, elapsed duration, prediction gaps, or ambiguity
events. No pair was counted using prediction packets, ID labels alone, or historical
evidence. The required fresh >=3 physically verified pair gate is not met.

Manually reviewed fragmentation examples (frame indices are zero based):

| Physical vehicle | Reviewed frames | Fresh IDs | Fragmentation edges |
| --- | --- | --- | --- |
| White compact panel van, first appearance | 0, 1, 2 | 25 → 36 → 43 | 2 |
| Purple Zesty box truck, first segment | 4, 5 | 57 → 63 | 1 |
| Same purple box truck, later segment | 7, 8 | 71 → 74 | 1 |
| White panel van, later traffic group | 17, 18, 19 | 132 → 143 → 151 | 2 |
| White SUV behind that panel van | 17, 18, 19, 20 | 131 → 138 → 147 → 159 | 3 |
| Dark hatchback in the adjacent left lane | 17, 18, 19 | 128 → 135 → 144 | 2 |

The 11 edges are individually recorded with exact boxes and capture sequences in
`extended-resume-run/physical-review.json`. The two purple-truck segments describe
one physical vehicle, not independent trials. Further visible fragmentation was
not added to this conservative count.

Observed cadence is materially poorer than in the earlier short runs: adjacent
retained source timestamps have minimum / median / maximum gaps of
**0.391 / 0.687 / 16.625 seconds**.
**45 of 79** gaps exceed 0.65 s and **14 of 79** exceed 1.25 s. One 16.625-second
gap occurs between frames 23 and 24. These measured gaps limit associations under
the unchanged conservative tracker; this task does not establish their runtime
cause or attribute every fragmentation solely to cadence. Retirement details show
**574 real-observation age expirations, 10 duplicate-origin retirements, and
3 association-ambiguity retirements**, totaling 587. Tracking processing time has
mean / p50 / p95 / maximum **48.137 / 33.030 / 84.528 / 924.637 ms**.

The existing worker and primary YOLO result were reused. No detector thresholds,
models, tracker gates, inference architecture, collision state, ledger, incidents,
or alarms were changed. The isolated validation process blocked 29 case-persistence
attempts; its internal possible-crash status is not a crash correctness result or
a persisted incident. Captured evidence was written only after the measurement
window. No reserved recording was directly opened by the validator.

Local evidence is under
`backend/validation/production_pair_continuity_20261012/extended-resume-run/`:
`live-observations.json`, `live-results.json`, `physical-review.json`,
`pair-continuity.json`, `extended-summary.json`, and the 80 source frames / 20
review sheets. Generated media remains local and unstaged.

No production source, recorder, or counting-tool changes were required for the
resumed run, so the suite was not rerun. The preceding extended-tool preparation
checks remain **7 passed**;
focused tracking/live-diagnostics regression remains **94 passed, 0 failed,
1 preserved pair-safety XFAIL**. The test file containing that XFAIL is unchanged
from HEAD. The existing earlier full regression evidence remains separate.

Fresh extended-run verdict: **TRACK_IDENTITY_READY_QUALITY_LIMITED**. The scene
gate was satisfied and the window completed; the fresh continuity success gate
was not. Production tracking was not tuned to force a pair metric.

### Historical evidence retained separately

The previously verified pair **346/354** belongs to camera CAM-30960048ED,
session e4348a7bd4fc49289aefd2274255dba4. Its four shared real DETECTED
observations occur at sequences **317, 321, 327, 330**, spanning **0.953 seconds**.
The red car retained ID 346 and the white SUV retained the distinct ID 354, with
zero observed cross-vehicle transfers, no prediction gaps inside that shared
streak, and no recorded pair ambiguity. The detailed physical review remains
in PAIR-CONTINUITY READINESS. This historical pair is not part of a new extended
run and does not satisfy the fresh-run gate.

### Local tooling and checks

Only the local validation recorder was extended: the bounded duration accepts
1–120 seconds; the frame capacity increased from 128 to 512; the measured window
and any discarded analyzed frames are recorded explicitly. Capacity overflow
marks the evidence incomplete rather than silently reporting a truncated window.
Source frames are retained during the window and saved afterward. No second
YOLO pass, production association change, or collision integration was added.

Seven focused validation-tool checks pass: 300 shared real observations remain
intact; prediction-only packets split a real pair streak; unreviewed IDs cannot
certify physical ownership; duplicate packets are rejected; the simulated
90-second recorder retains its complete window; overflow invalidates evidence;
and out-of-bounds durations are rejected before camera access. Focused tracking
and live-diagnostics regression: **94 passed, 0 failed, 1 preserved pair-safety
XFAIL**, 95 total in **23.010 seconds**. Existing project tests were not changed
in this extended-validation task. The full suite was not rerun unnecessarily.

Production tracker, backend entrypoint, pair ledger, and the pair-safety XFAIL
remain equal to HEAD. No files were staged, committed, or pushed. Local probe,
attempt log, focused test results, and tool checks remain untracked validation
artifacts under `backend/validation/production_pair_continuity_20261012/`.

FOBOS_PHYSICAL_VALIDATION_PENDING

The earlier attempt was blocked by its scene. The resumed extended run completed
and remains **TRACK_IDENTITY_READY_QUALITY_LIMITED** because no fresh pair qualifies.

## ZERO-CONTINUATION ROOT-CAUSE AUDIT

### Finding and scope

**TRACKING_CONTINUITY_CADENCE_LIMITED**, coupled to conservative bootstrap
ownership requirements and changes in observed boxes/pixels. The 90-second
recording's zero continuations are present in the raw production DETECTED packets,
not introduced by finalization. A persistent tracker and stable session survived
the run. Slower analyzed-frame cadence made most fresh tracks ineligible for the
short association path; the stronger path rejected the reviewed true edges for
missing verified pixel motion, prediction residual, ownership ambiguity,
appearance, scale, aspect, or its own time limit. Those rejected singleton tracks
then predominantly expired by monotonic capture time.

No production tracker defect or counting defect was demonstrated. **No production
code was changed.** The audit does not prove that cadence alone explains every
fragmentation: fresh higher-cadence examples still correctly fragment when physical
ownership is ambiguous. The system-level cause of the historical latency outlier
is not fully recoverable because that run did not record model/CPU stage timings.

### Validator and persistent lifetime audit

`validate_live.py` creates one worker per approved camera, stores its bound tracker
update once, and records its returned packets. `backend/main.py` constructs the
tracker once in `LiveCameraMonitor.__init__` (line 2301); update is called on that
same field under the worker lock (line 3016). Resets occur on connection open,
disconnect, explicit seeding after stop, or stop, not each analyzed frame.
`SessionVehicleTracker.update` refuses late sessions/duplicate sequences and does
not reset itself. `analyze.py` groups by `(camera_id, session_id, track_id)` and
counts only `detected is True` plus `observationKind == DETECTED`.

The archived bad run has **one camera, one session, strictly increasing sequences
and timestamps, and zero provenance mismatches**. Its retirement snapshots carry
earlier state into 61 analyzed rows. Predicted packets retain their old IDs and
are explicitly non-DETECTED. Independently recounting the actual packets yields
**601 real observations / 601 distinct scoped IDs / 0 continuations / depth 1**.
The same independent counter correctly reports **15** continuations in the older
49-frame run, **9** in the prior repeat, and **19** in the new instrumented audit.

`finalize_extended.py` is a run-specific evidence assembler: its assertions require
the already observed 80 frames and 601 singleton IDs. It would fail if those
packets contained repeated IDs; it does not rewrite production IDs or convert a
repeated identity into a first-seen identity. Its fixed summary numbers should
not be reused as a generic validator. The independent counter above avoids that
assumption and confirms the archived result directly.

A fresh capture-only Bago probe at camera overlay **04:41:52 AM** showed ordinary
traffic before inference authorization. The bounded profiling run analyzed
**69 frames in 30 seconds (2.30 FPS)** using **one tracker instance**, ID
`1383408814272`, and session `36d5892469314a7f9273a0564b8d34e5`. The one connection
reset occurred before the measured window; two cleanup resets occurred afterward.
There were **zero resets/recreations or session changes inside the measured
window**. Sequences and timestamps advanced strictly, with no provenance errors.
Each row records tracker identity, session, sequence, active-before/after state,
new/matched/missed/retired counts, and the old track ages/misses. Active tracks
ranged **0–44 before** and **4–44 after** update. Totals: **447 new tracks,
19 matches, 1,115 predicted/missed packets, 437 retirements**.

All 69 source frames and all 19 repeated-ID transitions were visually reviewed:
ordinary multi-vehicle traffic on the display, **0 observed cross-vehicle
transfers**, **19 physically correct continuations**, maximum real depth **4**,
and **>=7 verified fragmentations**. This is not native-road validation. The
traffic clip repeats and some consecutive views are nearly stationary; these
are not independent moving-road trials.

The new short audit includes physically correct pair **33/34**, three shared real
DETECTED observations at sequences **77, 82, 86**, spanning **0.625 s**, with two
distinct physical owners, no prediction gap and no recorded pair ambiguity.
This is separate from both historical pair **346/354** (four observations,
0.953 s, session `e4348a7bd4fc49289aefd2274255dba4`) and the bad 90-second run.
It does not retroactively satisfy that extended run's success gate or authorize
collision integration. The 30-second audit has 14 verified pairs at >=2, one at
>=3 and none at >=4; most two-observation pairs are combinations in one scene.

### Measured cadence and latency comparison

| Metric | Prior 49-frame run | Prior 50-frame repeat | Bad 80-frame extended run | Fresh 69-frame audit |
| --- | --- | --- | --- | --- |
| Window / FPS | 20 s / 2.45 | 20 s / 2.50 | 90.047 s / 0.89 | 30 s / 2.30 |
| Capture timestamp gap, median / mean | 0.406 / 0.409 s | 0.390 / 0.404 s | 0.687 / 1.121 s | 0.406 / 0.445 s |
| Capture timestamp gap, p95 / maximum | 0.660 / 0.938 s | 0.556 / 0.890 s | 2.503 / 16.625 s | 0.750 / 1.016 s |
| Capture-to-tracker completion, mean / p95 | 442.653 / 681.400 ms | 443.080 / 602.800 ms | 1169.212 / 2562.800 ms | 485.232 / 800.200 ms |
| Tracking, mean / p50 | 34.845 / 33.841 ms | 31.051 / 29.107 ms | 48.137 / 33.030 ms | 39.178 / 28.926 ms |
| Accepted detections per frame, mean / maximum | 6.878 / 13 | 5.840 / 11 | 7.513 / 13 | 6.754 / 13 |
| Raw real continued transitions | 15 | 9 | 0 | 19 |

In the bad run, **78/79** capture gaps exceed the 0.40-second bootstrap fast-path
limit, **45/79** exceed 0.65 seconds, **14/79** exceed 1.25 seconds, and **9/79**
exceed the 1.5-second singleton retirement limit. This is a much smaller opportunity
to establish motion history than in the earlier runs. All 601 IDs stayed at one
real observation; none established new trained-motion history within the window.

The largest historical stall is precisely localized: analyzed frame **23**,
sequence **489**, took **16.672 s** from capture timestamp to tracker completion,
but its production tracker update took only **12.535 ms**. Thus **16,659.465 ms**
elapsed outside that tracker core, before its result was recorded. The following
frame, sequence **729**, was captured 16.625 seconds later: capture advanced by
240 sequences during the stall, approximately **14.44 captured frames/s**. This
is not evidence of a capture stream frozen for 16 seconds. The next update retired
eight old tracks by age, all with **zero prior analyzed misses**. The recorder
saved JPGs/JSON only after the measured window, and that row's evidence copy comes
after the recorded completion timestamp, so those writes/copy do not explain the
preceding 16.672-second latency. The bad run skipped **1,189 captured sequences**
between its retained analyzed frames through the latest-frame architecture.

Fresh profiling times only the existing model calls, returning their exact
results; no extra model invocation is added. Mean / p95 / maximum detector latency:
**258.450 / 514.378 / 773.573 ms**. Classifier latency:
**79.240 / 125.197 / 175.957 ms**. Whole analysis-cycle latency:
**443.356 / 752.149 / 1444.204 ms**. Detector plus classifier average **337.690 ms**,
about **76.2%** of that mean cycle. Production frame-copy samples average
**2.374 ms**. Raw capture averages **14.454 FPS**; rolling analysis samples average
2.108 FPS, while the direct fixed-window count is 2.30 FPS. They use different
rolling-window boundaries. Preview FPS is **not measured as a browser metric**:
this isolated validator has no preview consumer, so its preview counter is zero.

The 30-second audit alternates **full / minimal / full**, ten seconds each, without
changing the worker or association rules. Full recorder: **46 frames / 20 s =
2.30 FPS**; minimal recorder: **23 frames / 10 s = 2.30 FPS**. Full recorder overhead
outside the tracker/added observer averages **2.636 ms**, p95 **3.919 ms**, maximum
**4.371 ms**. The minimal envelope averages **0.106 ms**. The added audit observer
averages **2.535 ms** in both modes, with one evidence-frame copy retained. Opt-in
association diagnostics are disabled in the minimal phase; that rendering cost is
included in production tracking time. The audit measures no large throughput
penalty from the recorder. These phases are not identical input replays and cannot
prove the absence of historical memory pressure or OS stalls.

The current host is highly loaded: sampled system CPU mean **99.444%**, median
100%. Validator process CPU mean **313.378%** in psutil's per-core units, about
**26.1% of 12 logical CPUs**. PyTorch uses eight threads and OpenCV one; neither
was changed. Working-set samples range **423.914–757.656 MB**. Resource contention
is consistent with variable inference latency, but historical CPU/process/memory
telemetry is absent, so a particular external process or exact historical stall
cause is **unproven**. No other application was stopped or reconfigured.

The existing scheduler keeps at most one pending latest-frame request for this
camera. Across startup/warmup and the measured session it received **476 submissions,
70 callbacks, and 405 pending replacements**; these are whole-session counts,
not 30-second-only rates. Sampled pending count never exceeds one, and skipped
source frames replace obsolete work rather than form an unbounded inference queue.
Queue-wait latency was inadvertently cleared by the newly added observer's cycle
initialization. That observer-only field was fixed and tested for future runs;
**no queue-wait latency is claimed for this saved run**, and the valid scheduler
counts above were unaffected. This small telemetry defect does not affect IDs or
the earlier zero-continuation result. No extra camera run was needed for that field.

The new profiler's full-mode-only subset initially retained image indices from
the partial recorder rather than the complete 69-frame stream. Its image paths
were reconciled by camera/session/sequence, and the subset is explicitly marked
incomplete because it omits the minimal phase. Focused tests require exact source
provenance and reject unknown packets. The complete observation stream and source
frames used for physical review were unaffected; this repair does not change the
historical extended run or its counts.

### Exact physical edges and association rejection counts

The historical successful run supplies accepted-edge controls from the exact
production diagnostics, rather than assuming every short gap succeeds:

| Prior accepted edge | dt / real track age | Observed displacement / diagonal | Prediction residual / diagonal | Predicted IoU | Scale / aspect | Accepted path |
| --- | --- | --- | --- | --- | --- | --- |
| Car 146, sequence 126 | 0.313 / 0.313 s | 0.372 | 0.007 | 0.814 | 1.126 / 1.033 | Verified pixel motion; bootstrap proof and ownership pass |
| Red car 346, sequence 317 | 0.203 / 0.203 s | 0.217 | 0.032 | 0.825 | 1.139 / 1.142 | Verified pixel motion establishes its second real observation |
| Same red car 346, sequence 327 | 0.391 / 0.906 s | 0.400 | 0.070 | 0.769 | 1.154 / 1.024 | Learned velocity supports the short-gap path |
| White SUV 354, sequence 327 | 0.391 / 0.703 s | 0.414 | 0.071 | 0.674 | 1.312 / 1.160 | Learned velocity supports the short-gap path |

All four accepted edges are class-consistent cars with zero prior misses, zero
ownership ambiguity and no rejected gates on the accepted path. Their learned
or pixel-backed prediction agrees with the actual next center. This differs from
the bad run's untrained singleton edges, where no motion history was established
and missing bootstrap pixel proof leaves a large zero-velocity prediction error.
Historical pair ownership remains scoped to its historical camera/session.

The following bad-run examples are visually verified same-vehicle observations,
with exact candidate boxes matched to recorded production diagnostic edges. All
have consistent vehicle class and **zero misses before the candidate**; none had
already been retired. Prediction-only packets are excluded.

| Bad-run vehicle / IDs / sequences | dt | Displacement (pixels / box diagonal) | IoU | Scale / aspect ratios | Actual rejection |
| --- | --- | --- | --- | --- | --- |
| White van 25 → 36, 81 → 93 | 0.844 s | 238.504 / 0.845 | 0.043 | 1.505 / 1.146 | Fast elapsed/bootstrap/motion/overlap/scale/appearance; strong appearance 0.116, scale, pixel proof, prediction and ownership fail |
| Same van 36 → 43, 93 → 100 | 0.578 s | 94.893 / 0.336 | 0.296 | 1.106 / 1.112 | Fast bootstrap/motion/pixel guard; strong appearance 0.078 >0.05, pixel proof, prediction and ownership fail |
| Purple truck 57 → 63, 126 → 133 | 0.485 s | 59.831 / 0.078 | 0.681 | 1.276 / 1.519 | Aspect 1.519 >1.25 and appearance 0.147 fail both paths, plus bootstrap gap/pixel proof/ownership |
| Same truck 71 → 74, 146 → 158 | 0.813 s | 181.320 / 0.303 | 0.330 | 1.286 / 1.037 | Appearance 0.045 passes strong path, but no verified pixel motion; residual 0.303 >0.20; fast elapsed/bootstrap/motion/pixel guard fail |
| White SUV 138 → 147, 374 → 381 | 0.562 s | 182.567 / 0.724 | 0.066 | 1.153 / 1.022 | Fast bootstrap/motion/overlap/pixel guard; strong appearance 0.059, pixel proof and prediction fail |
| Same SUV 147 → 159, 381 → 398 | 1.344 s | 11.173 / 0.046 | 0.827 | 1.062 / 1.032 | Even with good overlap/appearance, singleton dt >1.25 rejects strong cadence and >0.65 rejects fast elapsed; no trained history |

Eight of the 11 reviewed bad-run fragmentation edges have an exact diagnostic.
Three fall outside the nearest-two diagnostic selection and remain unclassified;
they are not assigned guessed rejection causes. For those eight edges, overlapping
fast failures are: bootstrap gap **8**, elapsed **4**, motion **6**, overlap **4**,
bootstrap pixel guard **6**, size **1**, aspect **1**, appearance **2**, anchor **2**.
Strong failures: pixel-motion proof **8**, prediction **6**, bootstrap ownership
**6**, appearance **4**, anchor **2**, cadence **1**, size **1**, aspect **1**.
Missing flow may result from failed eligibility prerequisites or feature
verification; this audit does not label every absence as a texture defect.

Fresh rejection breakdown below covers **1,583 sampled nearest candidate edges**
from the **46 full-mode frames**. Minimal-phase diagnostics are disabled. It
includes unrelated rivals; counts overlap and are not a census of true vehicles
or mutually exclusive causes. Lifecycle events are reported separately.
Fast counts use the recorded effective rejection list, which clears when a
fallback path succeeds; they are not independent counts of every raw fast-path
gate evaluation. Strong-path counts use its separately recorded gate failures.

| Requested reason | Fresh recorded count / scope |
| --- | --- |
| IoU failure | Fast predicted overlap 1,260; missed observed overlap 816 |
| Motion/displacement failure | Fast residual 1,497; strong observed displacement 603 |
| Prediction-error failure | Strong prediction residual 1,445 |
| Scale-change failure | 730, shared scale bound |
| Aspect-ratio failure | 481, shared aspect bound |
| Class mismatch | 188, shared class bound |
| Ambiguous ownership | 17 diagnostic track events (lower bound); 22 ambiguity retirements across all phases |
| Appearance uniqueness margin | 466 strong edge failures |
| Bootstrap ownership shadow | 1,433 strong edge failures |
| Stale/missed timing limits | Fast elapsed 1,040; bootstrap gap 1,209; missed gap 986; strong cadence 304 / miss budget 966 |
| Already retired before association | 342 age-expired and 6 duplicate-origin lifecycle retirements; excluded from candidate edges |
| Other evidence failures | Strong pixel motion 1,478; strong appearance 1,256 / anchor 871; fast appearance 1,018 / anchor 871 / bootstrap pixel guard 1,468 |

Fresh visually obvious same-vehicle examples show that safe fragmentation remains
necessary even at higher cadence. Dark van **118 → 125 → 132 → 139 → 147**, frames
15–19, has gaps **0.469, 0.390, 0.328, 0.360 s**: fast normalized residuals
**0.380, 0.339, 0.313, 0.273** exceed bootstrap 0.20, and all four strong edges
fail bootstrap ownership; the first three also lack pixel proof/prediction support.
Dark following car **127 → 134 → 142 → 150**, frames 16–19, has normalized residuals
**0.327, 0.276, 0.235** and IoUs **0.306, 0.362, 0.414**. The last two have otherwise
usable strong motion evidence but still fail bootstrap ownership, so ambiguity
retires their old IDs instead of forcing reassociation. All seven physical edges
have exact diagnostics and zero prior misses. The example sequences, boxes,
prediction centers/errors, scale/aspect, classes, ages and actual gate lists are
saved in `root-cause-run/fresh-audit.json`.

### Lifecycle timing and controlled low-cadence tests

Lifetime is bounded by **both elapsed monotonic capture time and analyzed miss
count**. Singleton tracks expire after 1.5 seconds; trained, pixel-backed tracks
with at most one miss can survive 2.25 seconds. Four unsuccessful analyzed updates
also retire a track. Skipped camera capture sequences do not increment misses.
Retirement happens before candidate association for expired/duplicate tracks;
ambiguous candidates may be retired during association. The short path allows
0.40-second singleton/bootstrap gaps, 0.65-second general association, and
0.60-second misses. Strong bootstrap requires verified pixel motion within
1.25 seconds; trained one-miss recovery allows 2.25 seconds with strict residual,
appearance and ownership checks. Prediction extrapolation is capped at 0.75 seconds
and half a box diagonal; predictions neither refresh real `last_seen_at` nor
establish real motion history or collision observations.

The bad run's retirement ledger is **574 age expirations, 10 duplicate-origin
retirements, 3 ambiguity retirements, 0 four-miss retirements**. Ages at expiration
range **1.531–16.625 s**, median **2.016 s**. Prior analyzed miss counts are
**0: 76, 1: 239, 2: 233, 3: 26**. Thus many tracks expire with fewer than four misses;
76 expire without even one analyzed miss. The fresh run instead has **342 age,
6 duplicate, 22 ambiguity and 67 four-miss retirements**. Rejecting association
first and then aging out is not a reset/recreation defect.

Deterministic visible-texture tests against the unchanged production tracker
pass at **0.4, 0.8 and 1.2-second cadence**, including two nearby differently
appearing moving vehicles and reversed detection order: both correct distinct
IDs persist with zero transfers. One missed observation recovers only with
established real motion; two slow-cadence misses safely fragment. An ambiguous
same-color bootstrap must fragment, a 1.6-second singleton gap expires before
association despite zero misses, and 1.2-second geometry without pixels cannot
authorize ownership. No gates were loosened to make these tests pass.

### Checks, limitations, and disposition

Focused validation/counting/timing/controlled-cadence checks: **23 passed,
0 failed, 0 XFAIL** (0.742 s). Focused production/legacy tracking and live collision
diagnostics regression: **94 passed, 0 failed, 1 preserved pair-safety XFAIL**,
95 total (24.452 s). Combined: **117 passed, 0 failed, 1 XFAIL**. The existing
pair-safety XFAIL remains unchanged; no project test assertions were weakened.
The small queue-wait observer field repair was verified by focused observer tests;
production tracking was not changed after its regression.

Local evidence/helpers are under
`backend/validation/production_pair_continuity_20261012/root-cause-run/`, including
`saved-run-audit.json`, `fresh-audit.json`, the 69-frame diagnostic observations,
tracker/lifecycle telemetry, CPU/capture samples, stage timings and physical review.
All new code is local audit tooling; production tracker, backend entrypoint,
detectors, thresholds, scheduler, collision/ledger, incidents and alarms are
unchanged. Validation persistence remained blocked and no reserved collision
recording was opened. Nothing was staged, committed or pushed; index empty.

The measured continuity collapse is explained by slower pipeline cadence combined
with the existing conservative ownership/shape/pixel gates, followed by time-based
retirement. The exact historical model/OS stall origin remains unresolved, as do
native-road behavior, repeatable extended moving-pair continuity and FOBOS physical
validation. The short audit's recovery is useful evidence, not a production
performance correction or grounds to pool historical pair 346/354 into the failed
extended window. Final disposition remains **TRACK_IDENTITY_READY_QUALITY_LIMITED**.

## Git and final disposition

The earlier production tracking changes and report are committed in `f754a4b5`.
The prior pair-readiness task changed tracking tests, this report, and local bounded
validation artifacts. The extended-validation task changes this report and local
validation tooling only; production files remain equal to that milestone. Pre-existing
`next-env.d.ts` and unrelated untracked material were left untouched. The known
pair-safety expected failure and protected inference/collision modules were checked
against HEAD. Nothing was staged, committed, or pushed; the index remains empty.

TRACK_IDENTITY_READY_QUALITY_LIMITED
