# Pair-Safe Production Collision Integration

Date: 2026-10-09
Mode: correctness first, bounded implementation
Outcome: implementation stopped at the mandatory stable-identity gate.

This audit continued from the existing working tree. It did not revert the fast-collision performance optimization or any earlier work. No production collision, UI, alarm, authentication, role, database, model, or threshold code was changed in this stage.

## Previous Defect

The live worker can combine qualifying observations from different physical vehicle pairs into one three-hit scene streak. A sequence representing A-B, then C-D, then E-F can therefore reach `confirmed_crash` when the third frame has crash-like single-frame geometry.

The existing deterministic regression `test_distinct_physical_pairs_must_not_share_three_hit_confirmation` still demonstrates this defect and remains an expected failure. The test was not removed, weakened, skipped, or relabeled.

## Production Confirmation State Before

The authoritative live state is `LiveCameraMonitor.hit_window` in `backend/main.py`. It is a bounded deque stored on one camera worker. Each analyzed frame appends `(timestamp, pre_temporal_positive)`, where `pre_temporal_positive` depends on frame quality, classifier case threshold, at least one vehicle, and scene validity.

The worker counts consecutive `True` values from the end of this scene-level deque. At three hits inside `CRASH_TEMPORAL_WINDOW_SECONDS`, it sets `temporal_ready`. `confirmed_crash` becomes eligible when the current frame also satisfies `crash_like_vehicle_interaction()`.

Ownership before this audit:

- global: NO;
- per camera worker: YES;
- per connection session: NO;
- per physical pair: NO;
- trajectory verified: NO;
- detector event identity: per worker/scene, not per pair.

Reconnect assigns a new `frame_epoch`, which correctly protects frame provenance, but it does not clear `hit_window`. Old qualifying state can therefore survive into a replacement connection session on the same worker. Stop/recreation creates a new worker and deque, but in-worker reconnect does not provide session isolation.

The exact defect is that the deque records only a boolean. It retains no participant identity, pair key, interaction history, or observation provenance from which pair ownership could be recovered.

## Stable Vehicle Identity

Available:
NO

Identity source:
No stable vehicle identity is produced or consumed by the production `LiveCameraMonitor._analyze_current_frame()` path. Its boxes contain label, confidence, and coordinates only. Detection order and box position are not valid persistent identities.

The repository contains `VehicleTrackingService`, `LogicalVehicleContinuityService`, and `TemporalCrashVerifier`, but `backend/main.py` does not instantiate or call them in the live production path. Repository-wide reference search finds those services only in their modules, tests, and offline validation tools. Their passing unit tests do not make track IDs available to production confirmation.

The frame `sessionId` is stable and suitable as one component of a future key. The required vehicle track components are missing. Under the task's non-negotiable gate, using proposal indices, detection order, class IDs, or positions would fabricate persistent identity. Implementation therefore stopped here.

## Canonical Pair Ownership

Key:
Unavailable in production. The required future form is `(camera_id, session_id, min(logical_track_id_a, logical_track_id_b), max(logical_track_id_a, logical_track_id_b))` after production tracking and logical continuity are validated.

Camera isolated:
PASS for the existing scene-level deque because each camera worker owns its own `hit_window`. This does not constitute pair-ledger integration.

Session isolated:
FAIL. Reconnect changes the frame epoch without clearing the existing hit deque.

`PairHitLedger` correctly canonicalizes `(A, B)` and `(B, A)` in isolation, bounds the number of pairs, rejects duplicate/out-of-order observations, expires state, and can retire all pairs containing a track. It accepts only integer track identities and deliberately does not associate boxes or authorize incidents. Those required identities are absent from production.

## Pair Ledger Integration

No integration was performed. `PairHitLedger` remains an isolated, tested service and is not authoritative for live confirmation.

Integrating it before a production tracker would require an impermissible box-index or position-based key. It would also leave session resets, track retirement, logical handoff, and detector-observation ownership unresolved. A pair ledger keyed by unstable identities would hide the existing regression without establishing physical pair safety.

The required preceding stage is production integration of:

1. detector observations into a per-camera and per-session tracker;
2. validated logical identity continuity across accepted tracker handoffs;
3. reset on connection epoch changes, stop, and disconnect;
4. explicit track retirement callbacks;
5. a strict distinction between new detector observations and tracked-only/predicted state.

Only after those conditions pass may `PairHitLedger` own the three-hit/five-second state.

## Interaction Verification

The current production helper `crash_like_vehicle_interaction()` evaluates only current-frame box overlap and distance. It has no approach, convergence, contact transition, velocity disruption, heading change, or post-contact evidence. It is therefore geometry, not temporal interaction verification.

`TemporalCrashVerifier` implements the needed trajectory logic and its deterministic tests reject close following, stopped overlap, ordinary motion, near misses, classifier-only positives, and overlap without approach. It also confirms synthetic rear-end and side-impact sequences. It is not connected to the live worker, so its decisions do not gate production `confirmed_crash`.

Pair ownership alone would remain insufficient. The future production hit must require a new detector observation for the same session-owned pair and an interaction decision from the trajectory verifier. Predicted or repeated display state must never add a ledger hit.

## Queue-Traffic Result

Confirmed:
YES in the unsafe current production architecture when a stable close pair repeatedly supplies high classifier/scene positives and current-frame geometry. The trajectory-verifier service rejects queue-like and close-following fixtures, but production does not use that result.

Expected:
NO

This gate fails for production. Passing offline/service tests cannot override the live path.

## Static Aftermath Result

Confirmed:
YES is possible in the unsafe current production architecture when repeated copies have high classifier confidence and box geometry makes `motion_valid` true. The scene deque cannot distinguish three copies of a static frame from three independent same-pair interaction observations.

Expected:
NO

The separate aftermath path correctly keeps review candidates distinct in its unit tests, and the isolated temporal verifier rejects overlap without approach. Neither protects the current live scene deque from treating repeated static geometry as temporal collision evidence.

## Three-Different-Pairs Regression

Before:
FAIL/XFAIL

After:
FAIL

The expected-failure marker remains because the required stable production identities do not exist. The implementation is explicitly incomplete, as required by the task when the regression cannot safely become a real pass.

## Same-Pair Positive Case

FAIL for production pair-safe integration because production emits no pair identity and has no pair-owned ledger.

The isolated `TemporalCrashVerifier` synthetic rear-end and side-impact positive cases pass. They show that a future integration has a viable interaction verifier, but they do not satisfy the production pass gate.

## Downstream Incident Regression

PASS

The unchanged event/incident tests confirm one confirmed event persists at most once, duplicates remain attached to the same event, persistence failure does not claim an incident, candidates do not persist, and a clear scene permits a later distinct event. The focused backend event/live-monitor run completed 23 tests successfully.

## Alarm Regression

PASS

Eighteen frontend alarm/live-monitor contract tests passed. Candidate, analyzing, aftermath, old, duplicate, unarmed, and declined cases remain silent. A fresh committed temporal-collision incident attempts the dispatcher alarm once, and a distinct fresh incident may attempt once. Alarm implementation was not changed.

## Performance Optimization

Preserved:
YES

The byte-identical primary-YOLO result reuse remains active. `backend/best.pt` and `yolov8n.pt` still have the same SHA-256 value: `F59B3D833E2FF32E194B5BB8E08D211DC7C5BDF144B90D2C8412C47CCFC83B36`.

The saved detector profile still reports exact equality for the complete output dictionaries on the safe vehicle, Bago, and FOBOS inputs, including accepted boxes, classes, confidences, and classifier results. Seven camera-performance tests and four scheduler tests passed. Redundant inference was not reintroduced.

## Tests

- Focused collision/tracking suite: 135 tests run; suite result `OK (expected failures=1)`.
- Remaining expected failure: `test_distinct_physical_pairs_must_not_share_three_hit_confirmation`.
- Camera performance and multi-camera scheduler: 11 passed.
- Backend event and live-monitor regression: 23 passed.
- Frontend incident/alarm/live-monitor contracts: 18 passed.
- Pair ledger unit coverage inside the collision suite: canonical order, independent pairs, distinct-pair isolation, expiry, track retirement, duplicate observation rejection, and bounded growth pass.
- Tracking and logical-continuity unit coverage inside the collision suite: camera isolation, bounded history/state, stale expiry, reset, ambiguity rejection, and handoff behavior pass in isolation.
- Production pair/session integration matrix: not run because the mandatory stable production identity prerequisite failed.

Expected pair-safety XFAIL remaining:
YES

Target:
NO

The target is intentionally not claimed. Converting the marker without stable production identity would produce a false pass.

## Unchanged Systems

Detector weights:
UNCHANGED

Thresholds:
UNCHANGED

3-hit rule:
UNCHANGED

5-second window:
UNCHANGED

UI:
UNCHANGED

Alarm semantics:
UNCHANGED

Auth:
UNCHANGED

Database schema:
UNCHANGED

No models were trained. Source B and Phase 8C were not used for training or threshold tuning. No Source B evaluation was required after the production identity gate failed.

## Final Verdict

STABLE_TRACK_IDENTITY_REQUIRED
