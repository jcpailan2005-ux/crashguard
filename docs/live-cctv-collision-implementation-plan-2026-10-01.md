# Executive Decision

Planning only, 2026-10-01. Based on the complete [live CCTV audit](live-cctv-detection-collision-audit-2026-10-01.md), with narrow source checks of live frame/result publication, UI polling, inference locking, tracker interfaces and `PairHitLedger`. No code, models, thresholds, evidence or operational data changed; no experiments or tests rerun.

Proceed through eight bounded stages. Preserve existing latest-frame capture and independent preview. Build frame provenance first; develop detector and conservative tracking offline before connecting same-pair interaction decisions. **Stages 1–6 do not make production collision confirmation safe.** The known production pair-safety regression remains FAIL; audit results were 26 passes plus one expected failure, with that assertion failing when called directly.

Use the requested priority taxonomy: P0 correctness, P1 detector/identity, P2 latency/synchronization, P3 optimization. This relabels the audit's P1 overlay/compute findings as P2 without lowering their release importance. Priority and implementation dependency order differ.

# Verified Blockers

`M` = `backend/main.py`; `S/` = `backend/services/`; `C/` = `components/`. Exact functions are more durable than line numbers.

| Priority / problem | Audit evidence / current behavior | Required behavior | File/function | Dependency | Safety / performance risk |
|---|---|---|---|---|---|
| P0 scene-owned hits | Existing distinct-pair assertion fails: A↔B, C↔D, E↔F yield 1,2,3 and confirmation | Each canonical observed pair owns independent history | M `LiveCameraMonitor._analyze_current_frame`, `evaluate_crash_case_decision`; `S/pair_hit_ledger.py::observe` | Valid identities and interaction qualification | False incident/alarm / bounded state required |
| P0 proximity treated as motion | `crash_like_vehicle_interaction` tests only overlap/distance; offline ownership-only queue pair qualifies at frames 69–71 | Measured same-pair interaction episode, including post evidence | M pair predicate; `S/temporal_crash_verifier.py::analyze`, `collision_features.py` | Observed trajectories | Stationary traffic falsely confirmed / bound pair work |
| P1 participant supply | Source B A raw 1/9, accepted 0/9; B raw 0/10, accepted 0/10 | Adequate accepted participant observations with measured precision | M `detect_vehicle_boxes`, `extract_vehicle_boxes_from_results` | Cleared capture and human labels | Missing actual pair / tested larger inputs cost more without recovery |
| P1 identity absent | No live tracker; offline logical service retained ID after 500 px/0.1 s jump | Conservative association, ambiguity rejection, expiry | `S/vehicle_tracking.py::update`; `logical_vehicle_continuity.py::update` | Frame provenance and real detections | History inheritance / bounded association cost |
| P2 mismatched boxes | Status poll ≥2.5 s, four-second hold, independent MJPEG | Exact source-frame association; explicit expiry | `C/live-camera.tsx::pollCctvMonitor`, `applyDetectionResult`; `cctv-video-overlay.tsx` | Stage 1 envelope | Misleading participant display / extra requests |
| P2 preview/cadence | Default preview cap 10 FPS; historical capture 14.85 vs HTTP preview 9.42 FPS; separate analysis benchmark 0.98 cycles/s | Source-relative preview and fresh, adequately sampled analysis | M `mjpeg_stream`, `_detection_loop`; `S/inference_execution.py::bounded_inference` | Baseline at declared load | Short interactions undersampled / CPU and bandwidth limits |
| P2 delayed result publication | Serial model calls and persistence within global analysis lock; latest result published at end | Prompt detection publication; bounded fair scheduling | M `_analyze_current_frame`; inference execution | Immutable results, serialized event handling | Reordering if carelessly split / camera starvation risk |

Polling order/source-switch hazards are verified code risks, not measured incident counts. No new speculative cause is added.

# Target Live Architecture

```text
RTSP → existing capture thread → one latest native frame slot
                               ├→ cached JPEG/MJPEG → smooth preview
                               └→ bounded fresh-frame detector admission
                                  → immutable detections + analyzed-frame reference
                                     ├→ exact-frame analyzed view + boxes
                                     └→ conservative observed identities
                                        → canonical pair → interaction episode
                                        → pair-owned 3-hit / 5-second state
                                        → confirmed_crash
                                        → existing incident/dispatcher boundary
                                        → armed siren attempts playback once
```

One slot/reader per effective source already exists; retain it. Capture and preview never wait on detector, tracker, verifier or persistence. Pending inference is replaceable by the latest frame, never an accumulating frame FIFO.

Add a live-only envelope: `cameraId`, connection/session epoch, `frameSequence`, host decode-completion UTC and monotonic timestamp, optional source PTS, native width/height, inference start/completion timestamps, native-coordinate boxes and optional track ID/observation state. Host decode time must not be labeled sensor exposure time. A `(camera, epoch, sequence)` key binds pixels, detections and analysis; reconnect starts a new epoch and invalidates old identity/pair state. Use monotonic capture time for elapsed windows, UTC for reporting.

Publish visual detections separately from the completed collision/incident result. Early box publication cannot set confirmation or incident-created fields. Keep operational persistence contracts, dispatcher polling and armed one-shot alarm delivery unchanged. Browser autoplay success cannot be guaranteed; preserve the existing attempt/feedback behavior.

Stage tables use the allowlist IDs below. **All denylisted areas remain untouched in every stage**, in addition to the stage-specific exclusions.

# Stage 1 — Frame Freshness and Synchronization

Objective: extend proven capture machinery with immutable frame identity and measurable freshness. Prerequisite: record effective runtime settings/hardware and baseline without creating incidents. Files: A1/A2/A5 and frame tests A9. Untouched: detector selection/thresholds, tracking, collision decisions, alarms and persistence.

| Current function / planned modification | Benefit / measurement | Stop or rollback |
|---|---|---|
| M `_capture_loop`, `seed_first_frame`: epoch + monotonic/UTC frame metadata, atomically published with frame | Unambiguous reconnect/frame ownership; verify no duplicate reader, accurate frame ages | Mixed metadata/pixels, capture waiting for inference |
| M `latest_jpeg`, `latest_preview_packet`: retain one sequence-keyed JPEG and preview-only lock; expose source epoch | Keep encode outside capture lock; measure encode/copy/lock durations and duplicate encodes | Capture FPS/age regression or growing cache |
| M `mjpeg_stream`: source-rate-aware, monotonic deadline pacing; bounded configured ceiling instead of sleep-after-work limiting 15 FPS source to ~10 | ≥90% source delivery target, unique-frame/browser cadence, encode CPU/network cost | Freshness/load gate fails; revert pacing only |
| M `_analyze_current_frame`, snapshot/events: carry exact source metadata through result; separate start age and completion age | Detect stale result versus fresh input; count skipped/repeated sequences | Same-frame repeat counted as fresh evidence |
| `S/live_collision_diagnostics.py`: bounded stage timing and queue/copy counters | Median/p95 and bounded-memory proof | Telemetry blocks hot path or exposes credentials |

RTSP transport remains TCP, one decoder thread and existing timeout/options. Buffer-size rejection stays visible; do not claim it controls buffering. No codec, JPEG quality, resolution, FFmpeg option or transport change without new measured need. No new unbounded queue. Tests: latest-slot overwrite, slow reader/inference, preview active during inference, reconnect epoch, clock adjustment and stalled source. Pass: frame provenance tests plus capture/preview/age gates. Safety: decision outputs unchanged for identical inputs.

# Stage 2 — Fast Aligned Vehicle Boxes

Objective: remove temporal misrepresentation with the smallest display correction. Prerequisite: Stage 1 envelope. Files: A1/A5/A6/A9. Untouched: detector, tracker, collision/persistence and alarm semantics.

- Keep smooth MJPEG as the live view; **do not draw an old observed box over its newest frame**. Reuse the existing analyzed-preview area for the exact analyzed frame with native-coordinate boxes, capture time and age. This provides fast aligned observations at detector cadence, not source-rate observed boxes.
- Publish a bounded latest analyzed-frame packet before classifier/persistence completes. Reuse live read-only delivery/auth boundaries; bind image fetch to requested epoch/sequence. If replaced before fetch, discard/retry newest, never substitute newer pixels under older boxes. One current analyzed packet and bounded in-flight references suffice; no frame archive or disk write per detection.
- Use existing `detection_events` for new-sequence notification/metadata, with coalesced bounded delivery and measured ≤100 ms notification scheduling target. Preserve existing authentication/access checks; no new token or permission scheme. A single-flight fallback poll replaces the 2.5 s box-update dependency. Status/tile health polling remains separate.
- Update `applyDetectionResult` and `CctvVideoOverlay`: join packet/image before rendering; reject duplicate/out-of-order epochs; abort/discard late fetches; clear on camera switch or expiry. Stop refreshing a hold from duplicate results. Define a **500 ms post-result receipt display-expiry target** for the live analyzed indicator; older analyzed stills may remain only explicitly labeled stale, without implying current presence.
- Keep existing contain/cover/native scaling and clipping; require real source dimensions rather than inferring frame size from box extents. No interpolation, extrapolation or production smoothing is planned. Missing/ambiguous observations may disappear rather than be cosmetically fabricated.

Tests: frame N boxes never on frame M; source switch, missing/replaced packet, leaving vehicle, out-of-order HTTP, reconnect, aspect ratios and clipping. Measure detector-end→aligned display, displayed frame age, jitter/IoU separately and preview continuity. Pass: exact joins on every test, display latency gate, no retained-current stale boxes. Rollback: wrong frame/source, extra unbounded traffic, or preview regression; fall back to raw preview with explicitly unavailable analysis, never mismatched overlays.

# Stage 3 — Vehicle Detector Improvement

Objective: improve usable participant recall without threshold hacks. Files: A1/A3/A9; separate candidate/data artifacts A10 require their own authorized work package. Prerequisites: frozen cleared Phase 4 sources, permitted physical replay capture, human vehicle labels, source-family/session splits and leakage review. Untouched: existing weights, originals/manifests, thresholds, production associations and decisions.

Phase 4 Round 3 has 10 cleared originals/four families/~35:40.747; it has **not** delivered Tapo captures, annotations or a trained candidate. Continue that sequence, using new artifacts and respecting source conditions. Preserve Source B/Phase 8C as protected evaluation evidence; never select epochs/settings using them. Native CCTV needs separately verified direct-road capture and its own held-out evaluation.

Report four failure categories independently: **NO DETECTOR PROPOSAL**, **RAW PROPOSAL**, **ACCEPTANCE REJECTION** (class/confidence/geometry/ROI reason), **TRACK LOSS** after an actual accepted identity exists. Raw means post-NMS, not a tracked vehicle. Measure cars/motorcycles and small/distant/partially occluded strata; truck/bus/bicycle where samples support them. Replay degradation and native traffic remain distinct domains.

Evaluate a separately named candidate offline at unchanged acceptance and production proposal settings. No repeat of conclusive 640/768/960/1280/ROI/tiling sweeps; no global confidence lowering. Any future acceptance exception needs separate evidence/scope. Tests/measurements: held-out raw/accepted recall, precision, false proposals/frame and target-hardware latency; freeze candidate before protected stress tests. Pass: detector gates and sufficient jointly observed real participants. Stop: leakage, precision/negative regression or no useful recall gain within budget; retain incumbent weights without claiming readiness.

**Ordering:** detector collection/evaluation may proceed alongside Stage 4 synthetic/offline engineering once frame contracts exist. Successful detector support is required **before live tracking/confirmation integration**, not before writing isolated tracking tests. No extra agents or concurrent experiments are implied.

# Stage 4 — Conservative Vehicle Identity

Objective: measured persistent identity without history inheritance. Files: A4/A9. Prerequisites: Stage 1 observation contract; Stage 3 accepted trajectories for real validation. Untouched: protected offline prototype/artifacts, ledger integration, live decision path, thresholds.

Implement the conservative contract within `vehicle_tracking.py`/`logical_vehicle_continuity.py`, using Phase 2 as a reference, not a production import. Recheck associations even when raw tracker IDs repeat; reject impossible displacement, inconsistent trajectory/size or ambiguous many-to-one/one-to-many assignments. Suppress duplicate seeds. IDs are never recycled within an epoch; expiry/reconnect revokes every dependent pair.

| Output state | Allowed meaning / collision use |
|---|---|
| `OBSERVED_ACCEPTED` | Current real proposal passes unchanged acceptance; eligible seed/measurement, not by itself a collision hit |
| `OBSERVED_SUPPORTED_RAW` | Current real weak proposal uniquely extends an established accepted identity within bounded history; no new seed and **no collision hit** |
| `PREDICTED_ONLY` | Brief dormant identity, no current observed bbox; no collision hit or observed display box |
| `EXPIRED` | Terminal identity; revoke pair/interaction history |

The prototype calls its weak state `OBSERVED_RAW_SUPPORTED`; map explicitly at the new interface, do not edit protected evidence. Start with accepted-only operation; leave weak extension disabled until its independent safety controls pass. Brief-miss bounds and association constants must be declared/frozen from existing research defaults before evaluation, not tuned to Source B. No new class-jitter tolerance initially: normalize established aliases; uncertain class changes abstain/revoke. Any broader tolerance needs separate evidence. Ground truth is scoring-only.

Tests: stable motion/jitter, brief/long misses, jump, reused ID, crossing, nearby vehicles, ambiguity, duplicate class boxes, new entrant and class change. Measure switches, wrong associations, fragmentation, retained state and association latency. Pass: zero inheritance/ambiguity guessing and identity gates on actual trajectories. Stop/rollback: any contaminated history; keep offline, do not integrate.

# Stage 5 — Pair-Owned Collision State

Objective: canonical pair histories independent of scene hits. Files: A7/A9, isolated adapter within A4 as needed; no production wiring yet. Prerequisite: Stage 4 valid identities. Untouched: live confirmation, operational boundary, interaction thresholds and protected prototype.

Own one `PairHitLedger` per camera/epoch, keyed by sorted persistent IDs. Keep **3 hits / 5 seconds**. Caller must reset on an analyzed negative/missing participant, expiry, ambiguity or reconnect; duplicate/out-of-order frame IDs add nothing. Use immutable monotonic source times and prune bounded history; never backfill hits from interpolated/missing frames. Skipped capture frames are not observations.

Ledger `geometry`/`interaction` fields are recorded metadata, not enforced gates. Only the Stage 6 verifier may supply `qualified=True`; ledger readiness cannot authorize incidents by itself. Expire absent pairs explicitly rather than silently retaining a streak. Use existing ledger bounds; log overflow/abstention.

Tests/measurements: A↔B history; AB/CD/EF each one hit; pair expiry, missing participant, no inherited history, camera/epoch isolation, capacity/ordering. Pass: zero cross-pair contributions and bounded memory/latency. Rollback: any mixed history. Current production regression remains FAIL until Stage 7 wires a fully verified path; offline ledger PASS is insufficient.

# Stage 6 — Interaction Verification

Objective: distinguish interacting participants from stable queue proximity. Files: A8/A9. Prerequisite: Stages 4–5. Untouched: scene/pair classifier weights, all existing classifier/proximity/geometry thresholds and live decision wiring.

Build a bounded episode through `TemporalCrashVerifier.analyze` and `collision_features.py`; validate against the Phase 2 conservative reference. Do not adopt the prior verifier or its score maxima without reproducing queue/distractor rejection.

| Signal | Future role |
|---|---|
| Both currently accepted identities; unique same-pair observations; good quality/ROI | **REQUIRED** eligibility |
| Measured pre-interaction approach/distance closure and transition into an interaction region | **REQUIRED** episode sequence; proximity alone cannot start qualifying hits |
| Immediate observed post-interaction relative-motion response consistent with that pair | **REQUIRED**; a validated velocity/trajectory change or abrupt stop relative to prior motion may support it; no need for every possible response |
| Scene classifier passing unchanged case threshold | **REQUIRED existing gate**, but supporting appearance evidence, **UNSAFE_ALONE** |
| Observable contact-region detail, pair appearance classifier, additional divergence/heading features | **SUPPORTING**; pair classifier remains disconnected initially to minimize scope/cost |
| Proximity, bbox overlap, damage, stopped vehicles, fallen motorcycle, high classifier score | **UNSAFE_ALONE** |

Use existing research feature constants unchanged for initial offline comparison. If they cannot support safe episodes, stop for a separately evidenced design revision; do not tune thresholds to force Source B. Qualifying hits must occur on distinct real observations after the required episode evidence exists—no retroactive synthetic hits. If contact/identity is unresolvable, abstain/review; 2D evidence does not prove physical contact universally.

Tests: attributed synthetic positive; queue, near-miss, parked, classifier-only, proximity-only, fallen aftermath, distractor, missing/predicted participant and changing pair negatives. Measure false eligibility, correctly attributed event recall, latency and per-pair cost. Pass: zero negative qualifications and positive control succeeds without fabricated participants. Rollback: pair persistence/appearance alone qualifies or correct positive requires weakened controls.

# Stage 7 — Bounded Production Integration

Objective: connect only the jointly validated detector→identity→interaction→ledger path. Files: A1/A2/A4/A7/A8/A9. Prerequisites: Stages 1–6 gates; candidate frozen; rollback package prepared. Untouched: PostgreSQL/operational service, incident contracts, roles, camera CRUD, dispatcher/responder and alarm implementation.

First run shadow decisions with persistence mocked/disabled at the harness boundary. Replace scene ownership for **RTSP confirmed-crash qualification** only after parity/safety validation; retain silent candidate/aftermath and duplicate semantics. Share no state with upload/device-camera decision paths; do not claim those separately scoped paths repaired.

Scope global model locking to model use, keeping per-camera analysis/decision ordering. Admit at most one latest pending frame per camera with fair bounded scheduling across cameras/uploads; reject/drop superseded work visibly. Reuse detector outputs only when effective weights, preprocessing, inference options and outputs are proved equivalent. No speculative model consolidation. Publish boxes early; preserve serialized event/incident creation and synchronous downstream contract after decision. Reset identity and interaction on source/session discontinuity.

Tests: real worker with mocked inference/persistence, concurrency/starvation, timeout/reconnect, duplicate input/event, exception recovery, retained incident/alarm regressions. Measures: frame/analysis rates, latency percentiles, lock time, CPU/RSS, false confirmations and incident/alarm counts. Pass: existing distinct-pair assertion genuinely passes, positive confirmation still reaches unchanged incident boundary once, all safety/resource gates hold. Remove its expected-failure marker only when actual fix passes the unchanged substantive assertion; do not fake a green suite by disabling all positives.

Rollback: any P0 or ordering/side-effect regression stops new confirmation integration; retain safe preview/analysis-only validation. Do not present the older known-unsafe confirmer as a safe operational fallback.

# Stage 8 — Controlled Validation

Objective: demonstrate the frozen pipeline on physical replay, then separately native CCTV. Files: new A9 validation outputs only. Prerequisites: Stage 7 isolated integration gates, source permissions, human participant truth, source-family holdout and explicit capture authorization. All production code, weights, thresholds, prior reports/assets/manifests remain untouched during evaluation.

Run controlled Tapo replay through the real display→camera→RTSP chain; compare observed participants/tracks/pairs against human scoring after inference. Include normal traffic, negative interactions and genuine collision clips. Use protected Source B/Phase 8C read-only as known regressions, never as untouched holdout or tuning material. Preserve uncertain/occluded truth as unassessable. Test initial connection, stalled source, slow viewer and maximum declared load.

Score frame/box performance, per-class recall, identity, pair attribution, false confirmations and event latency under the populations below. Validate dispatcher/armed-siren one-shot attempts in a disposable isolated environment with synthetic test records only under that future stage's authorization; no production incidents for testing. Actual replay positives require no staged physical crash.

Pass: every safety gate and sample-qualified performance gate; report acoustic playback separately from automatic attempt. Stop: insufficient labels/samples, contamination, any P0 failure or budget breach. Native-road claims wait for separately verified direct-road sessions and independent-camera evaluation; replay success cannot substitute.

# Test Plan

Write/extend tests before each stage's implementation; preserve existing assertions. Names below are suites to use/extend, not test execution claimed today.

| Area / likely suite | Required cases |
|---|---|
| Frames: `test_preview_latency.py`, `test_camera_performance.py`, `test_live_monitor_restoration.py` | Latest overwrite; bounded queue/cache; capture independent of inference; slow inference leaves preview active; decode/start/paint age definitions; repeat sequence; reconnect/clock/stall |
| UI: focused `frontend-tests/` additions | Exact frame/box join; contain/cover scaling; wrong source/epoch; old response; packet replacement; leaving vehicle clears current box; no duplicate-result hold extension |
| Identity: `test_vehicle_tracking.py`, `test_logical_vehicle_continuity.py` | Stable moving ID, jitter, brief miss, expiry, impossible jump, nearby/crossing ambiguity, duplicate seeds, class uncertainty, new entrant cannot inherit; raw/predicted state distinction |
| Pair: `test_pair_hit_ledger.py` | Same AB history; AB/CD/EF separation; expiry/reset; missing/negative/duplicate/out-of-order samples; epoch isolation; no history inheritance; finite capacity |
| Collision: `test_temporal_crash_verifier.py`, `test_live_collision_diagnostics.py` | Real observed same-pair synthetic positive; proximity/classifier-only negatives; parked/queue; fallen aftermath; changing pair; missing/predicted participant; wrong foreground participant; duplicate event |
| Integration: existing decision/restoration and frontend alarm suites, read-only contracts | Current production pair-safety regression; one new confirmed incident → one armed automatic playback attempt; duplicate/stale/candidate/aftermath silent; persistence errors do not invent incident success |

# Performance Gates

Baselines below are **historical audit evidence from different workloads**, not a current combined benchmark. Targets are provisional engineering acceptance goals. Log effective configuration/device, sample counts, exclusions and median/p95; do not convert a mean/max into a percentile.

| Metric | Audit baseline | Future gate |
|---|---|---|
| Capture FPS | 14.85 preview-only 300 s; 13.87 native+AI ~30 s | ≥95% sustained measured source FPS; ≥14.25 if source actually sustains 15 |
| Preview FPS | 9.42 HTTP receipt; browser unknown | ≥90% source unique presented frames; ≥13.5 at 15 FPS |
| Preview age median/p95 | Decode→HTTP mean 45.53 ms/max 107.78; paint unknown | Decode→paint ≤100/200 ms; separate synchronized source→paint ≤300/500 ms target |
| Inference input age median/p95 | Mean 37.60 ms in earlier component benchmark | ≤75/150 ms, latest pending depth ≤1/camera |
| Detector latency median/p95 | Controlled 640 detector mean 107.7 ms; different Phase 3 CPU sample mean 433.5 ms | ≤120/200 ms at validated model/resolution; hardware feasibility must be demonstrated |
| Analysis cycles/sec | 0.98; whole-cycle mean 914.24 ms, separate benchmark | ≥5 unique observations/s/camera target; p95 eligible observation gap ≤250 ms |
| Detector-end→aligned box display | Unknown; ≥2.5 s polling dependency and 4 s hold | Median ≤150 ms/p95 ≤300 ms; report source-frame age separately |
| Proposal / accepted recall | Source B diagnostic A 1/9→0/9; B 0/10→0/10 | ≥95% proposal / ≥90% accepted, precision ≥95%, predeclared IoU≥0.50 on new human labels |
| Car / motorcycle | General per-class recall unknown | Each separately meets recall/precision gate; small/distant/occluded strata disclosed |
| ID switches / wrong associations | No production IDs; rates undefined | ≤1 switch/100 trajectories preliminary target; zero wrong associations/history inheritance in safety controls and zero collision-state contamination |
| False pair / collision confirmations | Distinct-pair assertion FAIL; queue ownership-only false eligibility | Zero on all safety controls and held-out negatives; counts plus exposure/intervals, not “100% safe” |
| Collision confirmation latency | No defensible actual-pair baseline | First qualifying interaction evidence→confirm median ≤1 s/p95 ≤2 s when required observations exist; also report physical impact latency, abstentions and ≥90% correctly attributed event-recall target |
| CPU / memory | Earlier 172.77% process CPU, 100%=one core; RSS unknown | Whole-host mean ≤70%, one-second p95 ≤85%; backend RSS ≤2 GiB provisional and ≤5% post-warm-up growth over 30 min |

Population: three ≥10 min sessions plus 30 min soak at one/max declared cameras; ≥1,000 analyses per load configuration. Recall: ≥100 independent trajectories/500 assessable instances per class/domain over ≥3 sessions; correlate confidence intervals by trajectory/session. Truck/bus/bicycle below sample minimum: insufficient evidence, not pooled success. Boxes: ≥500 observations/100 tracks, median IoU≥0.70; measure jitter and moving lag separately.

Safety/event evaluation: ≥200 independent held-out negative events and ≥20 camera-hours normal traffic per domain; ≥30 independent human-verified assessable positives initially. Zero/200 negatives still implies roughly 1.5% one-sided 95% event-rate upper bound; zero/20 hours roughly 0.15/hour under a Poisson model. Increase samples for stronger claims. Never tune to these holdouts. If latency/cadence is infeasible, limit declared camera capacity or revisit hardware explicitly; do not lower correctness requirements.

# Safety Gates

1. Two real accepted participants, valid persistent identities, one canonical pair, measured interaction and immediate post evidence are required. Weak-support, dormant/predicted and ground-truth-derived identities contribute zero hits.
2. **3 hits, 5 seconds, classifier, proposal/acceptance, proximity and geometry thresholds are OUT OF SCOPE for changes.** Audit proves ownership/evidence defects, not a need to retune those constants. New interaction wiring must validate existing research constants before use; failure stops integration.
3. Distinct pairs cannot donate history; stable queue persistence cannot qualify; identity ambiguity/expiry resets all dependent state. Maintain a positive same-pair control so blanket nonconfirmation cannot pass as a repair.
4. Existing production regression remains visible until actual live repair; shadow/offline pass does not replace it. No unrestricted release while any P0 remains.
5. Candidate and aftermath stay silent; only a fresh persisted confirmed incident earns the existing one-shot armed siren attempt. Protected operational workflows remain compatible.

# Implementation Change Allowlist

`IMPLEMENTATION_CHANGE_ALLOWLIST` — file membership grants only the stated scope, not wholesale rewrites. All entries are future work; this task creates only this plan.

| ID / exact files or bounded artifact scope | Why / allowed change | Must remain compatible |
|---|---|---|
| A1 `backend/main.py` | Live capture/frame metadata, preview delivery, detector publication/scheduling and RTSP decision seam | Auth/CRUD/routes outside live delivery, uploads, incident bridge contract, thresholds, downstream alarm semantics |
| A2 `backend/services/inference_execution.py`, `live_collision_diagnostics.py` | Fair bounded model access; frame/stage timing | No unbounded jobs, secrets or telemetry-dependent decisions; existing busy behavior for unaffected callers |
| A3 `backend/services/detector_preprocessing.py` plus A1 detector helpers | Explicit frame transforms/model invocation and acceptance diagnostics; candidate evaluation seam | Native coordinate mapping, unchanged production acceptance/proposal settings, existing model files |
| A4 `backend/services/vehicle_tracking.py`, `logical_vehicle_continuity.py` | Conservative identity contract, reused-ID checks, expiry and pair adapter | Existing consumers until explicit migration; no ground-truth association or weak/predicted collision promotion |
| A5 `lib/types.ts`, `lib/api-client.ts` | Additive live envelope, sequence-bound media/metadata consumer and cancellation | Existing detection/incident response fields and auth/access mechanism |
| A6 `components/live-camera.tsx`, `cctv-video-overlay.tsx`, `cctv-monitor-workspace.tsx` | Exact analyzed-frame rendering, stale expiry, ordered fetch lifecycle, bounded preview demand | Device/upload flows, camera controls, permissions and alarm behavior |
| A7 `backend/services/pair_hit_ledger.py` | Integration contracts and bounded expiry/reset if tests prove necessary; reuse bookkeeping where sufficient | Three hits/five seconds, canonical isolation, no incident authority |
| A8 `backend/services/temporal_crash_verifier.py`, `collision_features.py` | Bounded measured episode and explicit qualification | Frozen constants, attribution, no appearance-only confirmation |
| A9 Focused tests named in Test Plan; new `backend/validation/live_cctv_implementation_*/` and `docs/live-cctv-implementation-*/` outputs | Verify changed seams and record new stage evidence only | Prior tests' substantive safety assertions and all existing evidence unchanged; no app-startup/DB side effects in unit fixtures |
| A10 Separately named detector candidate/configuration/capture/annotation artifacts | Domain improvement already identified by audit; **conditional separate authorized work package**, concrete new paths must be listed before execution | Existing weights, source manifests/licenses/originals and protected evaluation families remain immutable |

`vehicle_detection_tiers.py` and `collision_pair_classifier.py` are audit candidates but **not needed in this minimum plan**: weak promotion and pair-classifier integration are deferred. They are not added “just in case.” Production must not import the protected Phase 2 prototype. Any new production module, data path outside the defined scope, or proven dependency outside this allowlist requires an explicit plan amendment before editing.

# Protected / Denylist

`IMPLEMENTATION_DENYLIST / PROTECTED AREAS`:

- Authentication/session security, passwords, accounts, PostgreSQL schema, role grants and Admin/Dispatcher/Responder permissions.
- Camera CRUD behavior, saved credentials, privacy/redaction and unrelated camera settings.
- Operational incident API contract; `backend/services/operational_detection.py`, `backend/phase3/`, persistence workflow, dispatcher assignment, responder workflow and Response History.
- Alarm audio asset, Arm Siren UX, fresh-confirmed-incident one-shot semantics, candidate/aftermath silence; existing alarm/dispatcher implementation is a regression consumer only.
- Source B, Phase 8C, Phase 1–4 reports/artifacts and protected regressions; existing audit; source manifests, licenses/provenance and downloaded training originals; existing model weights.
- Database contents, existing/production incidents, unrelated frontend routes/backend APIs, and pre-existing workspace edits.

Anything not explicitly allowlisted is **OUT OF SCOPE**. A future test proving a direct dependency is grounds to propose a narrow scope amendment, not automatic permission to modify protected areas.

# Rollback Strategy

Before each future stage, snapshot/hash only its scoped inputs and save a stage-specific diff against the user's working tree. Use isolated tests/shadow runs first; never reset the repository or overwrite unrelated work. Roll back only that stage's changes and new-runtime state; preserve evidence and explain the failing gate.

UI/performance rollback may restore prior preview pacing or raw preview. Detector rollback retains original weights. Tracking/verifier failure clears new per-camera state and stops its integration. **Do not restore known scene-owned confirmation as a claimed safe fallback.** Keep further validation isolated with operational side effects disabled until a safe decision path passes. No database rollback/migration or alarm redesign is required.

# Recommended First Implementation Stage

**Stage 1: frame identity, freshness instrumentation and bounded preview pacing.** Start with epoch/sequence/time metadata and tests, then measure pacing changes. It extends existing working capture without depending on detector training and enables trustworthy box/identity evidence downstream. It must not wire tracking, change thresholds, fix collision decisions or touch protected workflows.

Detector intake and offline identity tests can follow as independent work packages. Production collision release remains blocked by P0 until Stages 4–7 pass; faster video alone is not a release gate.

# Planning Verdict

**READY_FOR_STAGED_IMPLEMENTATION**

Ready to execute a separately authorized Stage 1, not ready for production collision release. Detector adaptation and physical evidence remain prerequisites for later integration; no model training, implementation or operational validation occurred in this planning task.

IMPLEMENTATION PLAN COMPLETE — NO CODE CHANGES MADE — SEND PLAN BEFORE STAGE 1
