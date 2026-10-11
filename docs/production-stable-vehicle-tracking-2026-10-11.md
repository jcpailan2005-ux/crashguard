# Production Stable Vehicle Tracking

Date: 2026-10-11 (Asia/Manila). Scope: bounded identity integration only.

## Implementation

The authoritative `LiveCameraMonitor` in `backend/main.py` now owns a
`SessionVehicleTracker`. Accepted, in-ROI, native-coordinate vehicle boxes enter
it once per analyzed source frame, after the existing detector/classifier calls.
The identity is **(cameraId, sessionId, trackId)**. Numeric IDs are local to a
session, start at 1, and are never globally shared or derived from detection order.

The production adapter reuses the existing tested coordinate parser, class-ID
parser and `TrackState` detected-observation histories. It deliberately does not
activate the old offline ByteTrack wrapper unchanged: that wrapper has no session
or sequence admission, can retain backend association state beyond application
retirement, relies on Ultralytics' process-wide ID counter, and does not emit an
identity for every newly accepted low-confidence observation. Its older tests
remain intact. No new dependency was installed; NumPy and SciPy are already pinned.

Association uses bounded motion prediction, box IoU, center displacement relative
to box diagonal, label compatibility and size compatibility. A global one-to-one
linear assignment prevents two accepted boxes from claiming one identity. A
near-tie on either side rejects the handoff and starts a new ID. An ambiguous
crossing is therefore allowed to fragment rather than assert unverified physical
continuity. Detection array positions only connect the assignment to the current
frame's output; they are never persistent keys. Classifier scores are not inputs.

The center gate is 0.65 vehicle-box diagonals and the per-axis size ratio is at
most 1.8. A missed-track recovery additionally requires IoU >= 0.25 against the
last actual detected box and IoU >= 0.10 against the motion prediction. These
conservative gates deliberately prefer fragmentation when continuity is uncertain.

Association costs and ambiguity checks are vectorized. There is no new inference,
per-track process, background tracking thread, display-frame propagation or queue.
The existing one-frame slots, per-worker analysis lock, shared fair scheduler and
byte-identical YOLO-result reuse remain in place.

## Ownership and lifecycle

Each worker owns one independent camera/session tracker. Creation, successful
capture connection and reconnection establish a clean session. Capture release,
disconnect and stop clear the tracker and disable observations until a fresh
connection. Explicit source seeding after disconnect establishes a new epoch.
Worker replacement receives a new UUID. Lifecycle operations execute under the
worker lock. An arriving old-session frame cannot reset the tracker to its old
session. Tracking and exact analyzed-pixel packet publication share one session
guard and lock transaction.

Tracks have `NEW`, `ACTIVE`, `TEMPORARILY_MISSED` and `RETIRED` states. A track is
retired before re-association after more than **1.5 seconds** without an accepted
observation, or on the **fourth analyzed detector miss**. These are tracking bounds,
not changes to collision detection thresholds. Returning after retirement receives
a new numeric ID within the same session. IDs may restart only when sessionId
changes. Resolution changes retire pixel-motion histories without recycling IDs.

State is bounded to **256 tracks per worker**, including missed tracks, and **16
trajectory points per track**. Missed tracks are evicted first when space is needed
for new detections. A frame with more than 256 accepted vehicles fails explicitly
before mutation rather than silently dropping vehicles or publishing fabricated
identities. There is no unlimited retired-track registry. Retirement IDs describe
only the current result; lifecycle resets clear the entire retired session.

Duplicate/decreasing sequences, decreasing timestamps, nonfinite timestamps and
retired sessions are rejected without tracker mutation. Windows can give distinct
frames equal monotonic timestamps: increasing sequences remain valid in that
case, and velocity estimation avoids dividing by zero. Capture sequence gaps do
not invent detector observations for frames the scheduler skipped.

## Detected observations and predictions

Existing `boxes` remain exclusively real accepted detector boxes with their exact
coordinates, labels, classes and confidences. Additive fields include `trackId`,
camera/session/sequence provenance, `capturedMonotonic`, `lastDetectedSequence`,
`observationKind`, `detected`, `collisionObservation` and `trackLifecycle`.

`predictedTracks` is a separate continuity-only list. Predictions have
`observationKind: PREDICTED`, `detected: false`, `collisionObservation: false`, and
retain the last actual detector sequence. Prediction stops after 0.75 seconds of
extrapolation and track retention is bounded by the miss/age limits. Predicted
coordinates are not substituted into an analyzed image's detected box list.

History records source timestamp, sequence, center, box, width/height,
detected/predicted flag and image-plane velocity. The reused `TrackState.history`
contains only real detector observations. The separate bounded trajectory history
also describes misses; future verification must keep that distinction.

`collisionObservation: true` identifies a new accepted detector observation; it
does **not** mean a qualifying collision hit. Qualification remains unchanged.
Geometry, counts, the scene hit window and incident/evidence code still receive
the original detector boxes, never predicted tracks. Five display or missed-frame
updates cannot multiply one real detection into new collision observations.

The frontend types accept the optional metadata. No UI component, alarm component
or database schema was changed.

## Deterministic validation

Final focused suite: **147 tests, 145 passes and two expected failures**.
The new production/session tracker suite has **25 passes and one expected failure**
for the physical handoff found during final review. The other expected failure is
the unchanged distinct-pair collision-safety regression. The expected-failure
markers make limitations reproducible; they do not constitute pass-gate success.
Stage 1 and Stage 2 tests
execute the actual worker body with inference/persistence isolated. Integration
tests use temporary SQLite and remove the operational PostgreSQL URL from the
test subprocess. No operational incident is created by these tests.

| Requested property | Evidence |
| --- | --- |
| Same vehicle persists; two vehicles get distinct IDs | New adjacent/two-vehicle tests |
| Detection order does not swap identities | Reversed-order test and alternating-order synthetic benchmark |
| Short miss recovery | Same ID with separately marked prediction |
| Long miss/absence retirement; return has new ID | Time expiry before association and fourth-miss retirement tests |
| Bago/FOBOS isolation, including same numeric ID | Two independent camera/session trackers |
| Reconnect reset and old-session exclusion | Actual capture-loop reconnect test, late-session rejection and reconnect during inference |
| Worker replacement, stop and explicit restart | Separate worker state, clearing on stop, fresh epoch on seeded restart |
| Duplicate and late frames | Service and worker admission tests; rejected calls leave history unchanged |
| Predicted-only state creates no collision evidence | Actual worker with high classifier score, no detector boxes: vehicleCount=0, motionValid=false, streak=0, no persistence |
| Bounded history/memory | 16-point history tests, 3-track churn test, explicit capacity test, 256-track benchmark |
| Fair multi-camera scheduling | Existing four scheduler regressions unchanged |
| USB stop preserves RTSP | Synthetic scheduler/worker test; physical result recorded below when available |
| Stage 2 frame/box synchronization | All nine original Stage 2 regressions and new identity/provenance test |
| Pair-safety failure remains visible | Original distinct-physical-pairs expected failure preserved |

Frontend incident/alarm/live-monitor contracts: **18 passes**. TypeScript:
`npx tsc --noEmit --incremental false` **PASS**. Scoped `git diff --check` **PASS**.
The old tracker, ledger, logical-continuity and trajectory-verifier services were
inspected; their collision authority is unchanged.

Reproduction: run `backend/scripts/run_isolated_tests.py` with the modules listed
in [tests.log](../backend/validation/production_tracking_20261011/tests.log), using
an empty `DATABASE_URL` in that subprocess. Run the frontend checks with
`node --experimental-strip-types --test` for the incident-alarm-contract,
dispatcher-alarm-delivery and live-monitor-restoration test files.

## Association overhead

Synthetic results are in
[tracker-benchmark.json](../backend/validation/production_tracking_20261011/tracker-benchmark.json).
Each size uses 50 frames, excluding five warmup frames; order alternates every
frame. All sizes have zero synthetic ID switches. At capacity there are 256
retained tracks, 4,096 flagged trajectory points and 4,096 detected-history points.
These are association-only measurements under the machine's existing load, not
YOLO FPS, physical identity ground truth or an isolated CPU benchmark.

| Accepted vehicles | Tracking p50 | Tracking p95 |
| ---: | ---: | ---: |
| 1 | 0.57 ms | 0.67 ms |
| 8 | 1.11 ms | 1.40 ms |
| 32 | 2.45 ms | 3.13 ms |
| 64 | 4.63 ms | 6.36 ms |
| 256 | 33.36 ms | 36.51 ms |

The capacity limit is a memory bound, not a claim that a 256-vehicle dense scene
has negligible cost. Typical sparse scenes add roughly a millisecond; the highest
density requires separate throughput qualification.

## Physical validation

Physical measurements are recorded separately after inspecting the live sources.
The initial Bago probe showed collision content displayed on a screen; inference
was not started against it. The user subsequently switched to normal traffic,
which was verified in the next probe. Initial FOBOS showed a room without vehicles.
The system's USB monitor then prevented a separate capture process from acquiring
FOBOS. No credential was changed, password guessed, server killed or account
permission modified to bypass that ownership.

The validation script blocks incident persistence and evidence-output writes, and
suppresses application startup schema/seeding. It accepts only live RTSP/registered
webcam sources. It never opens `Recording 2026-10-11 230518.mp4` or any media file.
Probe screenshots inspect source pixels without running detection. Normal traffic
shown on another screen remains a camera-domain proxy rather than calibrated road
ground truth.

Normal-traffic review of the first working association exposed a real incorrect
handoff: track 14 followed a red bus at sequences 107/114, a different van at 132,
then a car mislabeled bus at 137/142. The earlier evidence is retained in
[prior-observations.json](../backend/validation/production_tracking_20261011/prior-observations.json)
and the `prior-review-*` images. Class compatibility alone was insufficient.
The final association adds stricter center/size gates and requires overlap with
both real and predicted boxes when recovering a missed track. Two deterministic
regressions reproduce and reject these handoffs. This correction changes tracking
association only; detector acceptance and collision decisions are unchanged.

The first measurement also exposed a missing `caseId` in the validation-only
persistence stub. It was corrected and measurement repeated before results were
used. Persistence remains blocked; the production persistence implementation was
not changed to accommodate the stub.

Final measurements are in
[physical-results.json](../backend/validation/production_tracking_20261011/physical-results.json)
and [observations.json](../backend/validation/production_tracking_20261011/observations.json).
The final 35-second run has no validation-stub detection exceptions.

| Metric | Bago | FOBOS |
| --- | ---: | ---: |
| Capture FPS mean / p50 | 14.20 / 14.20 | unavailable |
| Analysis FPS mean / p50 | 2.58 / 2.60 | unavailable |
| Analyzed packets sampled | 93 | 0 |
| Accepted vehicle observations | 441 | 0 |
| Numeric track IDs sampled | 193 | 0 |
| Detected observations per ID mean / max | 2.28 / 10 | unmeasured |
| Tracker-reported miss recoveries | 42 | unmeasured |
| Retirement events sampled | 189 | unmeasured |
| Tracking time p50 / p95 | 1.51 / 2.65 ms | unmeasured |
| Retained track count p50 / max | 12 / 21 | unmeasured |
| Camera/session/sequence provenance mismatches | 0 | unmeasured |

System CPU p50/p95 was **100%/100%**. Validation-process CPU p50/p95 was
**332.4%/545.6%**, where 100% represents one logical processor. Process RSS
p50/p95/max was **446.54/471.31/487.29 MiB**. Existing operational backend/capture
processes remained running; the host was saturated. This is not an isolated
comparison against the earlier 3.33/2.84 FPS two-camera baseline. Tracker overhead
is measured separately; the lower analysis cadence cannot be attributed solely
to tracking.

The final pending scheduler depth was at most **one** because only Bago acquired
frames. Stopping the validation FOBOS worker cleared its tracker and Bago capture
advanced 606->651; analyzed sequence advanced 606->644 in three seconds. This
does **not** verify stopping an actively capturing USB camera, because FOBOS never
acquired the hardware in the validation process. The actual two-camera hardware,
fairness and contamination gates remain unverified. Their synthetic tests pass.
The user turned FOBOS off in the system, but an operational USB capture child
remained; the validator did not kill that worker, restart the server or alter the
camera lifecycle implementation. All validation-owned camera handles were released.

**Physical identity requirement: FAIL.** The final eight-frame visual review shows
some valid continuity (for example black minivan ID 27 at sequences 101/106/112/119
and white van ID 49 at 138/144/148). It also shows incorrect physical handoffs:
ID **47** follows a **silver hatchback at sequence 130**, a **different black car
at 138**, then a **blue hatchback at 144**. ID 41 also crosses vehicles. These are
within-camera physical contamination despite correct camera/session provenance.
The screenshots `review-CAM-30960048ED-{0..7}.jpg` retain the exact reviewed source
frames and visible IDs. `test_distinct_physical_vehicles_must_not_reuse_track_identity`
reproduces the silver-to-black handoff from the recorded boxes and remains an
explicit expected failure. Stricter gates fixed the earlier bus/van fixture but
did not solve the general vehicle-filling-a-former-box problem.

The high number of new IDs and short track segments is evidence of substantial
fragmentation/churn, not a verified physical-vehicle count. Forty-two reported
recoveries are bookkeeping events, not 42 proven same-vehicle recoveries. There
are at least two visually observed ID-47 switches in the limited reviewed burst.
Full-run ground-truth switch/fragmentation/false-persistence rates remain null
because no annotated full-run physical participant ledger exists. Claiming zero
physical switches or false persistence from provenance checks would be incorrect.

The validation pipeline blocked **63 persistence attempts** from the unchanged
scene-level collision logic on normal traffic. No validation incident, notification,
alarm or evidence output was committed. This reinforces the existing pair-safety
limitation; it is not a reason to change classifier thresholds in this stage.

## Preserved collision semantics

PairHitLedger: **not integrated**. Trajectory verifier: **not connected to live
confirmation**. The scene-owned three-hit/five-second window and its reconnect
ownership defect remain unchanged for the next pair-safe stage. The known
distinct-pair failure remains an expected failure, not a production safety pass.

No detector/classifier threshold, collision geometry, confirmed_crash rule,
incident rule, alarm rule, model weight, UI or database schema changed. No model
was trained. `backend/best.pt` and `yolov8n.pt` still have SHA-256
`F59B3D833E2FF32E194B5BB8E08D211DC7C5BDF144B90D2C8412C47CCFC83B36`.
The extensive pre-existing working tree was retained.

## Limitations and verdict

Geometry-based association cannot establish identity across indistinguishable
vehicles, complete occlusion, large jumps, camera scene cuts without a session
restart, or class-label changes. Ambiguity starts new IDs; this favors correct
ownership over optimistic continuity. Physical ID switches, fragmentation and
false persistence need annotated normal-traffic observations before broad quality
claims. A fresh production process must load this code; the running system server
was not restarted as part of implementation.

Final verdict: **TRACK_IDENTITY_UNSTABLE**.

Session/camera ownership, deterministic order independence, retirement, bounded
histories, prediction separation and scheduling are implemented. The adapter emits
identities for accepted detections, but real physical vehicle ownership remains
unsafe under the observed traffic/occlusion/cadence conditions. Numeric provenance
and passing synthetic fixtures cannot substitute for that requirement.

The stable-identity pass gate is **not met**. Do not use these IDs as authoritative
pair-ledger ownership. A subsequent tracking repair needs discriminating physical
association evidence and normal-traffic validation, including two-camera hardware
access, before pair-safe integration can begin. No PairHitLedger integration or
recorded-collision validation was performed.
