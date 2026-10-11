# Safe Same-Pair Collision Fix

## Original Defect

`backend/main.py:LiveCameraMonitor._analyze_current_frame` stores `(timestamp, pre_temporal_positive)` in `self.hit_window`. The Boolean is a **scene-level** predicate: good quality, classifier accident score above the existing case threshold, at least one accepted in-ROI vehicle, valid scene. It contains no track or pair key. The worker counts consecutive true values inside five seconds, then evaluates proximity among **only the current frame's** accepted vehicles. Three positives plus any current proximal pair can reach `confirmed_crash`. Different vehicles in each observation can therefore inherit one streak. A new deterministic `@expectedFailure` safety regression invokes the real worker with three disjoint vehicle pairs and reproduces `streak_after=1,2,3` followed by `confirmed_crash`. The expected failure is intentional and means the production gate **fails**; it is not counted as pair safety passing.

## Production Architecture Before

RTSP `_capture_loop` → `_detection_loop` → `analyze_current_frame` → full-frame YOLO and crash classifier → `detect_vehicle_boxes` → ROI acceptance → `crash_like_vehicle_interaction` current-frame proximity → scene-level hit window → `evaluate_crash_case_decision` → `persist_sqlite_crash_case` → operational PostgreSQL incident/notifications → dispatcher alarm. The live worker calls none of `VehicleTrackingService`, `LogicalVehicleContinuityService`, or `TemporalCrashVerifier`. The classifier is full-frame, not attributable to a physical pair. Candidate/verifying displays “Analyzing potential collision...” and is not confirmation.

The existing service audit is:

| Component | Reusable elements | Production classification for this integration |
|---|---|---|
| `vehicle_tracking.py` | Actual detector observations, per-camera ByteTrack IDs, bbox/class/confidence history, 3-second stale expiry, six-second gap reset | **REQUIRES_BOUNDED_FIX**: IDs alone do not prove stable physical identity under a close pass/occlusion; Source B has too few true-participant proposals to create both useful histories. |
| `logical_vehicle_continuity.py` | Bounded one-second handoff, ambiguity scoring, max 64 identities, no motion fabricated on carried frames | **UNSAFE_FOR_PRODUCTION as a blind RTSP drop-in**: direct raw-ID reuse applies an observation without a fresh spatial handoff check; collision-region provisional association can attach to the wrong pair. Protected replay has no primary true-pair recovery. |
| `temporal_crash_verifier.py` | Canonical sorted pair key, isolated per-pair interaction state, approach/contact-proxy/post state, four-second pair expiry, `expire_track_ids` | **REQUIRES_BOUNDED_FIX and independent validation**: its offline composition selected and falsely confirmed an unrelated queued pair; a score/contact proxy is not proof of the actual pair. |
| `pair_hit_ledger.py` (new, isolated) | Canonical unordered pair ID, independent three-hit/five-second state, duplicate rejection, bounded pair count, explicit track expiry | **SAFE_TO_REUSE as bookkeeping only** after a separately verified identity and interaction source exists. It does not track boxes or authorize confirmation. |

## Tracking Design

No new production track association was installed. The current detector input is inadequate for a defensible production identity handoff: protected Source B primary approach found P-A accepted 1/19 and P-B 1/22, on different observations, with no simultaneously usable true-participant identities. A tracker cannot invent the missing participant. The existing raw tracker retains real bbox/class/confidence histories but does not establish identity-swap resistance for the filmed CCTV case. The logical service's raw-ID fast path needs a spatial/trajectory continuity guard before production use. Its ambiguity rejection, supported-miss limits, and expiry are useful parts, but the protected study's failure prevents treating the composition as ready.

## Pair Identity

`PairHitLedger` keys a supplied pair by sorted distinct integer track IDs: `(12,27)==(27,12)` and `(12,27)!=(12,35)`. It does not create identities or pairs from missing detections. State includes first/last observation and time, supporting/qualifying sequences, classifier/geometry/interaction metadata, streak, window start, expiry, and a reserved confirmation flag. At most 64 pair states and 16 entries per history are retained. A caller must explicitly expire a compromised track ID; the ledger cannot discover an identity swap by itself. This is an **isolated candidate component**, not called by the live worker.

## Pair-Specific Temporal State

Each supplied pair has its own three-hit/five-second count. Duplicated or out-of-order observation sequences do not increment it; an explicitly nonqualifying observation resets only that pair; entries older than five seconds and pair states not seen for five seconds expire. A different pair cannot donate hits. The pure ledger is deliberately insufficient for `confirmed_crash`: it has no authority to assert that an identity is physical or that interaction occurred. Production still uses `self.hit_window`, so this correct ownership is **not yet integrated**.

## Interaction Verification

Existing `TemporalCrashVerifier` models approach, a geometric contact proxy, and short post-contact motion change/stopping. That is the right temporal shape, but protected Source B offline composition assigned a high score (about 0.863) and false confirmation to unrelated upper-left queued vehicles. The later C3 closure experiment suppressed that specific false episode but recovered **zero** correct selected true pairs, including an independent human-verified positive check. No existing service configuration has passed both positive and wrong-pair gates. Stable pair identity, proximity, or a high classifier score cannot independently confirm.

## After-Collision Verification

The desired approach → interaction → immediate post-interaction → verification sequence is not safely deployed. Existing production `possible_crash_aftermath` remains a review outcome, not a proven collision. The isolated ledger records interaction metadata only; it never treats a damaged/stopped vehicle or lone fallen motorcycle as collision proof. No post-collision confirmation rule was added without trustworthy A/B histories and held-out negative validation.

## Detector Dependency

Protected Source B: P-A raw/accepted **1/19**, P-B raw **2/22** and accepted **1/22** in the primary assessable approach; no simultaneous usable true-pair identities. This is a detector proposal/acceptance input shortage before safe tracking and pair verification. The latest synchronized Bago capture cannot label A/B or prove contact from its seven saved roadway frames and therefore cannot update those participant-specific rates. Distinguish `DETECTOR_PROPOSAL_FAILURE` and `DETECTION_ACCEPTANCE_FAILURE` on protected Source B from `TRACK_CONTINUITY_FAILURE`, `PAIR_ATTRIBUTION_FAILURE`, `INTERACTION_VERIFICATION_FAILURE`, and `TEMPORAL_FAILURE` on the latest unlabeled capture: only the scene-level streak reset at observation 5095 is observed there, not an earliest true-pair cause. No threshold was lowered or model trained.

## Changes Implemented

- `backend/tests/test_live_collision_diagnostics.py`: one deterministic expected-failure regression for the unsafe current RTSP decision path. Three different disjoint pairs yield 1/2/3 scene hits and `confirmed_crash`; the expected failure remains a release gate.
- `backend/services/pair_hit_ledger.py`: isolated, bounded canonical pair-hit bookkeeping with fixed three-hit/five-second defaults; **not imported by `backend/main.py`**.
- `backend/tests/test_pair_hit_ledger.py`: six deterministic ownership, duplicate, expiry, invalid pair, bound, and explicit track-revocation checks.
- This report. Alarm UI, production collision decisions, camera runtime, operational database, model weights, and protected evidence were not changed.

## Positive Collision Test

Isolated pair-hit support: **PASS** for three supported same-key observations, including reverse key order, within five seconds. Full A+B approach → interaction → post-collision → `confirmed_crash` exactly once: **NOT ESTABLISHED**. The ledger has no tracker or verifier authority, and the protected architecture study recovered zero correct selected true pairs. A fabricated synthetic detector/pair/interaction success would not validate the live physical case. No fake production incident was created. Thus the required positive production integration gate **FAILS**.

## Pair-Safety Regression

| Case | Isolated ledger | Production gate |
|---|---|---|
| Different pairs A/B, C/D, E/F | **PASS**: no pair has 3/3 | **FAIL**: real worker confirms in expected-failure regression |
| A/B, A/C, A/B | **PASS**: A/B has 2 | **FAIL / unvalidated** in live worker (no pair identity) |
| Identity swap | **PASS only with explicit revoked track ID** | **FAIL / unvalidated**: raw-ID fast path can inherit without independent spatial recheck |
| Queued traffic | No interaction decision in ledger | **FAIL** in protected offline service composition: unrelated queue confirmation |
| Parked vehicles | No interaction decision in ledger | **NOT VALIDATED** for production |
| High-score unrelated pair | Score alone cannot make ledger authorize confirmation | **FAIL** as a production safety claim; current full-frame classifier and proximity lack pair attribution |
| Aftermath only / damaged vehicles | No ledger confirmation authority | **NOT VALIDATED** for production; review semantics retained |
| Fallen motorcycle beside car | No ledger confirmation authority | **NOT VALIDATED** for production |
| Missing participant | **PASS**: invalid/same-ID pair rejected, no pair synthesized | **NOT VALIDATED** for actual A/B input |
| Duplicate observation | **PASS**: sequence cannot add a hit | Current RTSP worker uses each analyzed observation; duplicate physical frames are not tracked by pair |
| Pair expiry/new vehicles | **PASS** with five-second or explicit track expiry | Live path has no pair state |
| Multiple simultaneous pairs | **PASS** for isolated independent state | Live path remains scene-wide |
| Repeated post-confirmation incident | Ledger never creates incidents | PostgreSQL dedup exists; full true-pair end-to-end test not run |

`PASS` in the ledger column means only pair-key bookkeeping was tested. It does **not** meet the five required production integration gates: different-pair worker behavior, real identity-swap resistance, queued-traffic safety, aftermath-only safety, and a positive verified same-pair collision.

## Operational Integration

`confirmed_crash`: **NO new safe production path integrated**. Fresh incident: **NOT APPLICABLE** to the isolated ledger. Dedup: existing PostgreSQL event/camera protections unchanged; no operational incident was inserted for this task. Alarm eligibility: the previously repaired frontend still requires a fresh `temporal_collision` incident and remains unchanged. The previous alarm regression suite passes; no candidate/analyzing/aftermath alarm branch was added.

## Alarm Regression

Existing frontend suite: **44/44 PASS**, including fresh confirmed incident → one attempted playback, duplicate/old → none, candidate/analyzing/aftermath → none. Arm Siren remains in the persistent dispatcher shell. Physical audible output remains unverified and is separate from pair safety.

## Performance

No new production inference/tracking/pair code runs, so production capture FPS, inference duration, frame age, tracking cost, association cost, and pair-verification cost are **unchanged by this task but not freshly measured**. Last preserved normal-feed diagnostic reference: median inference **789.074 ms** and observation interval **0.793 s** with capture diagnostics ON; this is historical, not an after-change benchmark. An isolated 10,000-update ledger microbenchmark had median update **0.0138 ms**, 159.09 ms total, and at most 64 active pair states; it excludes detection, tracking, interaction, Python import, and live scheduling. The protected C3 research replay reported +0.569 ms mean overlay against cached inputs, not a measured production full-pipeline cost. Existing tracker default expiry is 3 seconds, logical handoff 1 second, and temporal interaction retention 4 seconds. These are service settings, not validated live expiry behavior.

## Existing Tests

Backend targeted collision, diagnostics, vehicle tracking, logical continuity, temporal verifier, pair ledger, and camera security: **127 tests, OK with one expected failure**. The expected failure is the current production different-pair confirmation defect; it is a **failed safety gate**, not a passing safety test. Frontend: **44/44 PASS** from the existing alarm suite. TypeScript: **PASS** from the prior alarm work; no TypeScript files changed in this task. PostgreSQL integration tests were not run without an explicitly isolated test database. No protected evaluation asset was altered or trained on.

## Protected Assets

Models changed: **NO**. Thresholds changed: **NO**. Three-hit and five-second production rules changed: **NO**. Training: **NO**. Source B changed: **NO**. Phase 8C changed: **NO**. Protected annotations changed: **NO**. Authentication and schema changed: **NO**.

## Remaining Limitations

The isolated ledger cannot turn detector boxes into stable physical A/B identities, cannot tell a queued pair from a collision, and cannot prove post-impact behavior. The protected architecture study concluded `SAFE_ARCHITECTURE_NOT_FOUND`: C3 suppresses a known unrelated queue event but selects zero correct true pairs. Current detector input is too sparse in the protected approach for the existing tracker to recover both physical participants. The synchronized Bago run is not a labeled positive test. No safe production integration or physical CCTV validation is justified. Next work needs clean, separately authorized detector-domain data, explicit identity-swap and same-pair trajectory validation, plus held-out queue/parked/aftermath negatives before wiring a pair-specific gate into `backend/main.py`.

## Production Integration Decision

**MULTIPLE_COLLISION_LIMITATIONS_REMAIN**

The mandatory production gates fail for the current worker and are unestablished for any proposed full tracker/interaction composition. The isolated ledger is a bounded component, not a deployable same-pair collision pipeline. Do not run a live collision test until true-pair identity and interaction safety are demonstrated independently.
