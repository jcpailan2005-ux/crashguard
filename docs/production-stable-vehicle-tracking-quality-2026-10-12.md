# Production vehicle tracking identity quality — 2026-10-12

Work branch: `work/track-identity-stabilization-2026-10-12`.

**Latest result: TRACK_IDENTITY_READY_QUALITY_LIMITED.** The final fresh 20-second
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

## Git and final disposition

Changes are limited to the session tracker, its existing production frame argument,
tracking tests, this report, and local bounded validation artifacts. Pre-existing
`next-env.d.ts` and unrelated untracked material were left untouched. The known
pair-safety expected failure and protected inference/collision modules were checked
against HEAD. Nothing was staged, committed, or pushed; the index remains empty.

TRACK_IDENTITY_READY_QUALITY_LIMITED
