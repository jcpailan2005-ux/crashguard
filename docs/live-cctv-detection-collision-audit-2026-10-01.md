# Executive Summary

Audit date: 2026-10-01. Scope: current working-tree code, existing measurements and isolated decision tests; **planning only**. Existing uncommitted work was preserved. No camera session, model inference benchmark, training, operational incident, database write or implementation was performed.

**Multiple interacting blockers:** production lacks persistent participant identities and pair-owned confirmation; the generic detector supplies no accepted actual Source B participants; the frontend displays old detections over newer video. Smooth capture alone cannot fix these failures.

- **P0 safety failure remains:** three unrelated physical pairs can donate one hit each and produce `confirmed_crash`. Fresh direct execution of the existing assertion fails. Neither the test nor its expected-failure marker was changed.
- Capture already uses a native latest-frame slot, separate capture/analysis threads and one decoder thread. Do not repeat the earlier pipeline rewrite. Preview defaults to 10 FPS against a reported 15 FPS source; the historical revised-preview harness delivered 9.42 FPS, not close to source rate.
- Source B first interaction: raw participant recall A **1/9**, B **0/10**; accepted A **0/9**, B **0/10**. Offline tracking cannot restore missing observations. These are diagnostic envelopes, not independent human ground truth or general vehicle-recall estimates.
- Selected-camera boxes update through **2.5-second status polling**, with **4-second box holding**, independently of MJPEG. The exposed SSE endpoint is not the selected-camera consumer.
- Phase 4 progressed beyond its early source-availability failure: Round 3 cleared **10 originals / 4 source families / ~35:40.747** for replay capture. Physical replay capture, annotations and candidate training remain unstarted. Native roadside validation remains unestablished.

# Current Live Architecture

References below are relative to this report. Line references describe this working tree; function names remain the primary anchors. `M` = [backend/main.py](../backend/main.py).

| Stage | Exact implementation | Execution / input → output | Blocking, buffering and latency exposure |
|---|---|---|---|
| Source/start | M `resolve_saved_camera_stream` :4691; `api_start_camera_monitor` :4703; `start_live_camera_monitor` :3293 | Async start offloads initial grab; registry aliases reuse running source worker | Initial connection/decode can block off-thread. Saved record and default/global Tapo profile are different source-selection paths. |
| RTSP/decode | M `LiveCameraMonitor._capture_loop` :2320 | Dedicated daemon thread; TCP RTSP → native BGR frames | FFmpeg `nobuffer`, `max_delay=500000`, one decoder thread, 5 s open/read limits; failed open waits 2 s, reconnect loop waits 1 s. `BUFFERSIZE=1` requested, historically rejected. Upstream/decoder buffers remain opaque. |
| Publication | Same capture loop | Replace `latest_frame`; increment `frame_seq`; record host decode-completion time; signal event | One overwritten frame, no application capture FIFO. Short state lock; no JPEG work. Timestamp excludes sensor/network/decode backlog. |
| Preview encoding | M `latest_jpeg` :2421; `latest_preview_packet` :2450 | Request-driven native JPEG, quality 75 default; bytes plus frame-bound headers | One cached JPEG per source sequence; preview-only RLock covers encoding, not network send. Capture remains free. Encoded array → bytes copy; no frame copy in this encoder path. |
| Delivery/display | M `mjpeg_stream` :2465, preview route :4844; `components/live-camera.tsx` :1604 | Synchronous streaming iterator via response threadpool → browser `<img object-contain>` | Default sleep 100 ms **plus** encode/send/scheduling; no application JPEG queue, but TCP/server/browser buffers may exist. Slow clients resume at latest frame. Same JPEG can repeat if source stalls. |
| Status/boxes | M `snapshot` / status route :4770; `LiveCamera.pollCctvMonitor` :1245 | Status JSON/latest result → React boxes; interval ≥2500 ms | Status also queries pending incident. Snapshot fetch runs alongside MJPEG; requests lack source-generation/abort/order protection. Tiles poll every 4000 ms (`cctv-monitor-workspace.tsx`:677). SSE `detection_events` :2495 checks every 500 ms but is not used here. |
| Analysis scheduling | M `_detection_loop` :3222; `analyze_current_frame` :2683; `services/inference_execution.py::bounded_inference` | Dedicated thread + new-frame event; default artificial interval 0; latest-frame copy → analysis | Per-camera nonblocking lock and global nonblocking model RLock; busy calls rejected with 503, not queued. One full native copy under state lock. Global lock spans whole analysis, including persistence. No fairness guarantee between cameras/uploads. |
| Model calls | M `_analyze_current_frame` :2692; `detect_vehicle_boxes` :945; `classify_crash_frame` :1184 | Quality metrics; primary YOLO → scene classifier → separate vehicle YOLO; optional detector retry | Synchronous serial calls on analysis thread. Bad quality prevents decisions but does **not** short-circuit these model calls. Repeated primary/vehicle work is a consolidation candidate only after output-parity checks. |
| Acceptance / identity | M extractor :898, ROI filter :554, response scaling :991 | Post-NMS boxes → allowed class/confidence/geometry/ROI boxes | No live tracker, persistent IDs, association or track smoothing. Array indices are frame-local. |
| Pair / confirmation | M `crash_like_vehicle_interaction` :623; `_analyze_current_frame` :2774; decision helper :643 | Any close box pair → boolean; scene positives → hit deque → decision | Pair loop short-circuits first match; worst case O(n²). Scene deque bounded to max(10, hits×4), default 12; 3 consecutive positives in 5 s. No canonical participant pair owns history. |
| Incident | M `persist_sqlite_crash_case` :1779 → `services/operational_detection.py::persist_operational_detection` → `phase3/service.py::create_ai_incident` :550 | Confirmed/aftermath decision → PostgreSQL incident/review/notification | Despite bridge name, operational authority is PostgreSQL. Synchronous evidence JPEG/file and DB work delays result publication and releases model lock only afterward. Initial operational state is awaiting dispatcher review. |
| Dispatcher/alarm | `components/dispatcher-alarm-monitor.tsx` :30; `lib/dispatcher-alarm-delivery.ts`; `lib/incident-alarm-contract.ts` | 5 s polling plus visibility refresh → fresh unseen `temporal_collision` incident alarm | UI arming and browser audio remain prerequisites. Candidate/aftermath/duplicate do not earn fresh alarm. Downstream trusts upstream decision; it cannot repair false pair attribution. |

No heavy RTSP inference runs directly on the asyncio event loop in this path. Stream-frame requests use `asyncio.to_thread`; synchronous endpoints/stream generators still consume threadpool capacity. Threadpool/network contention is a scaling risk, not a measured current bottleneck.

# Video Smoothness Findings

| Quantity | Evidence / meaning |
|---|---|
| Camera-reported FPS | **15.0**, Stage B successful saved-record probe; five immediate reads are not a sustained FPS measurement. |
| Historical host capture | **14.85 FPS**, 300 s revised-preview-only harness; earlier ~30 s native+AI component benchmark **13.87 FPS**. Different runs/workloads. |
| Historical preview delivery | **9.42 FPS** MJPEG HTTP receipt in the 300 s harness. Browser painted FPS **unknown**. Default 10 FPS cap alone prevents ≥90% of a 15 FPS source. |
| Decode → HTTP receipt age | Harness sampled mean **45.53 ms**, maximum **107.78 ms**; median/p95 not established by the report. Not physical end-to-end latency. |
| Encoding / read cost | Same harness sampled JPEG mean/max **4.67/7.38 ms**; capture read **57.86/132.04 ms**; publication **0.32/1.03 ms**. |
| Upstream delay evidence | Earlier default 12-thread decoder was one OSD second behind a one-thread decoder in **34/34 paired samples**. Current source already uses one thread. Buffer-size request returned false. |
| Absolute display delay | Unmeasured. Host-minus-camera-OSD includes clock offset and one-second quantization; historical browser validation was blocked. No new live measurement here. |
| Stale-frame handling | Analysis refuses repeated sequence and frames older than default 10 s; preview can continue returning cached stale image. A decode-recent image can still be old upstream. |

Architecture is **latest-frame processing**, not an unbounded old-frame work queue. Latency can remain before decode, during serial inference, during status polling, in held overlays, in fallback snapshots and in transport/display buffers. Internal queue depth, current lock-wait distributions, current browser age, reconnect freshness and current runtime overrides are unmeasured. Existing counters measure capture/encode/analysis rates; `previewFps` is not proof of browser paints.

# Vehicle Detection Findings

| Setting | Current live implementation / evidence |
|---|---|
| Primary detector | `backend/best.pt`, explicit `imgsz=640`; earlier inventory identified generic COCO YOLOv8n, 80 classes, 3,157,200 parameters, SHA-identical to root `yolov8n.pt` at that inventory. No new weight hash/architecture load here. |
| Vehicle box source | `VEHICLE_MODEL_PATH`, default root `yolov8n.pt`; primary results only if separate load unavailable. `LIVE_CAMERA_USE_SEPARATE_VEHICLE_MODEL` is declared but does not gate this function's call. |
| Vehicle inference | Native BGR input; no explicit `imgsz`, `conf`, device or NMS overrides in live call. Installed defaults: 640, predict confidence 0.25, class-aware NMS IoU 0.70, max_det 300. Device auto-selected; prior measurements used CPU, active process device not inspected. |
| Accepted classes | Normalized `car`, `motorcycle`, `bus`, `truck`, `bicycle`, `vehicle`, `van`, `suv`, `automobile`, `auto`. Generic COCO supports the first five vehicle categories; aliases do not add learned classes. |
| Acceptance | Default ≥0.40, clamp xyxy to native bounds, reject nonpositive width/height; optional normalized ROI tests box center. Empty ROI means full frame. No temporal/context-supported admission in this path. |
| Retry | Only when no vehicles accepted AND scene score ≥0.80: rerun vehicle model, extractor minimum 0.15. Proposal cutoff remains 0.25; unrelated accepted traffic prevents retry. |
| Scene classifier | `backend/models/crash_classifier.pt`, 224 default; full-scene accident probability. UI threshold 0.80, case threshold 0.90. No pair classifier called by RTSP worker. |

**Raw proposal ≠ accepted vehicle ≠ tracked vehicle.** Raw here means returned **post-NMS** model box, not pre-NMS network output. Accepted boxes pass production extraction/ROI. RTSP has no tracked-vehicle output.

Source B first-cycle audit: A exists in 9 assessable frames, raw in 1 (0.3872904), accepted in 0; B exists in 10, raw in 0 at 0.25, accepted in 0. Eight A misses and ten B misses are proposal failures; A frame 41 is an additional acceptance failure. No matched-participant class/ROI/degenerate-box rejection explains this result. All **155 visited dense pair comparisons** concern unrelated vehicles. Post-overlap individual identity is unassessable, not scored as a miss.

At diagnostic cutoff 0.05, A raw **2/9**, B raw **5/10**, only **one simultaneous raw** frame; all rejected by unchanged acceptance. B best score **0.1637074**. Dense returned vehicle proposals grow **220→699** over 41 frames; unmatched proposals are not verified false objects. No safe threshold candidate emerged.

Observed conditions include night glare, blur, overlap and perspective-compressed screen recapture. Native envelope sizes roughly A 100–191×99–183 px, B 90–132×72–81 px shrink about twofold at 640-width model content. Small-object detail, occlusion and domain mismatch are plausible contributors, not separately isolated causal measurements. Class-specific general car/motorcycle/truck/bus/bicycle recall, distance curves and real-road recall remain unknown. Faster cadence cannot recover a participant absent even in dense offline processing.

**Domain separation:** pipeline timing/identity defects apply structurally to both `TAPO_SCREEN_REPLAY_DOMAIN` and `NATIVE_REAL_CCTV`; measured Source B recall applies only to the former. Display resampling, moiré, glare, refresh/exposure interaction, recapture compression and perspective are additional replay risks; no individual-effect ablation exists. Stage B2 fresh frames still contained a historical traffic-video timestamp. A working Tapo RTSP connection is not native-road validation. Round 3 source clearance authorizes no inference about a trained model: capture/labels/training are still absent.

# Bounding Box Speed / Quality

| Dimension | Finding |
|---|---|
| Detection speed | Whole serial analysis must finish before `latest_result` publishes; then selected UI waits up to the next ≥2.5 s poll, plus HTTP/render time. No measured detection-to-paint percentile. |
| Position quality | Detector coordinates are already mapped to input-native xyxy; production clips them and uses scale 1 for native input. Overlay uses actual source size and centered contain/cover scaling. No verified letterbox conversion bug in this path. Missing-size fallback infers extent from boxes and can mis-scale; actual status dimensions/natural image dimensions normally avoid it. |
| Stability | No tracker smoothing/interpolation. `BOX_HOLD_MS=4000` holds missing detections until a later result permits clearing, not an independent expiry timer. Re-polling unchanged nonempty results can refresh holding. Crash display can select a prior saved sample. These can preserve stale boxes; they do not establish identity. |
| Display latency / synchronization | Detection snapshots frame N, MJPEG displays newer frame M. Internal `frame_seq` and MJPEG part headers exist, but the result/React overlay has no matching frame contract and ordinary `<img>` does not expose per-part IDs. Boxes are **not temporally synchronized**. Native dimensions fix spatial scale, not temporal displacement. |

Status/snapshot polls have no in-flight/generation ordering guard here, so late responses can overwrite newer/source-changed display state. This is a code-demonstrated risk; occurrence/frequency was not measured. Boxes are also hidden until a fallback/annotated frame surface exists even when MJPEG is present. Visual persistence must remain separate from collision evidence and fresh-incident alarm semantics.

# Tracking / Identity Findings

Production RTSP assigns **no persistent vehicle IDs**, cannot preserve identity through a miss, and cannot enforce safe weak-box track extension. There is no production track-swap rate to score. Instead, new vehicles inherit **scene hit history** without any identity association at all. Predicted-only boxes are not currently generated in RTSP; future predicted/dormant/display-only observations must never count toward collision hits.

Offline `VehicleTrackingService.update` (`services/vehicle_tracking.py`:250) wraps ByteTrack; `LogicalVehicleContinuityService` attempts handoffs. Phase 2 demonstrated a reused raw ID retaining logical ID 1 after a **500 px jump in 0.1 s**, without handoff checks. Do not integrate those services merely because their names imply continuity.

Phase 2 `ConservativeTracker.update` (`validation/source_b_continuity_phase2_20260930/prototype.py`) rechecks bounded class/geometry/motion association, revokes ambiguous crossings/duplicate proposals, expires IDs and associated pair history. Two prior accepted observations are needed before bounded dormancy or weak support; predicted-only has no current bbox. Weak support extends identity only and cannot qualify collision. Synthetic controls pass, but actual A/B tracks remain absent; zero observed A/B ID switches with no recovered tracks is **not successful tracking**.

# Collision Logic Findings

Actual live rule: good frame + scene classifier ≥0.90 + ≥1 accepted in-ROI vehicle adds a **scene** positive. Three consecutive positives within 5 s establish `temporal_ready`. Current-frame `motion_valid` is only **IoU ≥0.08 OR normalized edge distance ≤0.05 for any pair**. It measures neither motion nor physical contact. `temporal_verified = temporal_ready and motion_valid` selects `confirmed_crash`; no current proximity selects aftermath review instead.

Thus earlier hits need not involve two vehicles, much less the final pair. Pair indices change per frame; the worker does not prove approach, contact, immediate post-impact evidence or same-pair continuity. Time uses wall-clock decision-time samples rather than immutable per-pair capture timestamps. The required 3 hits and 5 s are retained in this plan, but their ownership and evidence must change in a future task.

| Signal | Current authority and safety interpretation |
|---|---|
| Accepted vehicles, quality, ROI | Authoritative live eligibility gates; necessary observations, unsafe alone. Quality measures reliability, not collision. |
| Persistent identity / canonical pair | **Unused in production**; required future ownership authority. |
| Distance / overlap | Authoritative final boolean gate today; supporting interaction candidate only, **unsafe alone** for queued/occluded/nearby vehicles. |
| Relative motion / approach / contact / post-impact stopping or divergence | **Not measured by live decision**. Offline proxies require identity, episode and attribution validation; 2D overlap is not proven physical contact. |
| Full-scene classifier | Authoritative threshold today; supporting appearance evidence only. Cannot identify participants or prove contact. |
| Pair classifier | `classify_collision_pair_regions` helper and service exist; **not called by live RTSP worker**. Even pair appearance score is supporting, not physical proof. |
| Temporal hits / 5 s | Authoritative live confirmation; **unsafe scene ownership**. Pair ledger alone is also insufficient without interaction. |
| Stopped/damaged/fallen vehicle | No dedicated measured live collision proof. One vehicle alone cannot pass pair predicate, but nearby stationary vehicles can. Aftermath must stay review-only/silent. |
| Duplicate / cooldown / event ID | Persistence suppression, not participant identity or collision evidence. Keep independent. |

Fresh regression: `test_live_collision_diagnostics.py::LiveDiagnosticsTests.test_distinct_physical_pairs_must_not_share_three_hit_confirmation` :177 supplies A↔B, C↔D, E↔F at successive observations; live streak becomes 1,2,3 and returns `confirmed_crash`. Direct assertion **FAIL**. Preserve visibility until an explicitly authorized repair passes it.

Phase 2 ownership-only comparator also gives the **same unrelated queue pair** three hits at frames 69–71. Conservative approach/contact-proxy/post checks reject it with zero interaction hits. Pair bookkeeping alone does not solve false confirmation.

# Live vs Offline Differences

| Concern | Current RTSP | Offline/validation |
|---|---|---|
| Observations | Latest available frame, load-limited | Saved dense frames/host timestamps or explicit sampled cadence; not real-time throughput |
| Detector/admission | Default 0.25 proposals / 0.40 acceptance; special empty-result retry | Diagnostic low floors, resolutions/ROI/tiling; acceptance kept distinct; older tier experiments vary |
| Identity | None | ByteTrack/logical service variants; separate Phase 2 conservative prototype |
| Pair ownership | One scene deque | `PairHitLedger.observe/expire_track` sorted pair keys, unique sequence, bounded states; caller supplies real IDs and qualification |
| Interaction | Current-frame proximity boolean | `TemporalCrashVerifier`, collision features and Phase 2 `PairExperiment` approach/contact-proxy/post sequences; prior attribution defects remain relevant |
| Classifier | Full scene | Some studies add pair crops; Phase 2/3 replay saved scene scores; no universal single offline configuration |
| Side effects | Evidence files, incidents, notifications | Isolated traces/eligibility, mocked persistence |

There are **different live and experimental architectures**, not one already-integrated safe collision engine. `PairHitLedger` documents itself as bookkeeping, not a verifier; it trusts caller `qualified` and does not enforce its recorded geometry/interaction flags. No live import/call connects the tracker, ledger or temporal verifier.

# Performance Findings

Prior scale sweep (48-frame serial timing subset after warm-up, two PyTorch CPU threads/one OpenCV thread; first-cycle recall from the existing full sweep at research floor 0.10):

| Mode | A raw /9 | B raw /10 | Accepted A/B | Detector mean ms |
|---|---:|---:|---|---:|
| 640 | 2 | 3 | 0/0 | 107.7 |
| 768 | 0 | 1 | 0/0 | 124.7 |
| 960 | 0 | 1 | 0/0 | 170.3 |
| 1280 | 0 | 2 | 0/0 | 293.1 |
| Two 640 tiles | 0 | 0 | 0/0 | 254.2 |
| Broad road ROI /640 | 0 | 1 | 0/0 | 64.3 |

None yields accepted true participants or safe confirmation. Earlier raw-history admission introduced a near-miss false confirmation in the 20-negative-group study; ROI attributed a verified positive to a foreground distractor. Do not rerun these sweeps or recommend global confidence reduction.

Different workload evidence must remain separate: Phase 3 ten-frame CPU paired sample at 0.25 averaged **433.5 ms** detector-only; first-cycle worker replay median **2.846 s/frame** excluded initial warm-up and included diagnostics. Earlier native live component benchmark achieved **0.98 analysis cycles/s**, whole-cycle mean **914.24 ms**, mean inference-input age **37.60 ms**, process CPU **172.77%** (100%=one core). These are not current browser/live measurements. Source B recorded **11.632 frames/s**, nominal 15; that is not inference FPS.

The <1 s assessable participant interval and ~1 Hz historical analysis present an additional cadence risk; no original-live observation mapping proves which frames were skipped. Model/domain capability, acceptance, serial CPU work, UI cadence and unsafe collision architecture interact. Capture freshness is partly repaired already. Fair global scheduling, frame-copy/lock time, current RSS, per-stage inference cost and multiple-camera load require measurement; no current memory/CPU saturation claim is justified.

# Root Cause Priorities

| Priority / subsystem | Verified problem / evidence | User-visible effect | Safety effect | Performance effect | Likely modules / future fix | Risk |
|---|---|---|---|---|---|---|
| P0 collision ownership | Direct distinct-pair regression fails | Wrong crash incident/alarm possible | Unrelated participants combine hits | Minimal ledger cost; identity cost unmeasured | M decision seam + conservative tracking + pair ledger | High: no blind offline integration |
| P0 evidence | Proximity called motion; no approach/post sequence; queue comparator false eligibility | Stopped/nearby traffic can appear confirmed | Pair ownership alone inadequate | Bound candidate pairs and history | Temporal verifier/collision features; attributed interaction gate | High: 2D ambiguity |
| P1 detector | Source B A/B accepted 0/9, 0/10 | Actual vehicles/crash participants missed | True pair unavailable | Higher tested resolution costs more without recovery | Detector execution/preprocessing; separately evaluated domain candidate | High: data leakage/precision tradeoff |
| P1 overlay | 2.5 s polling, 4 s hold, no frame join | Late, drifting or lingering boxes | Display may misrepresent analyzed vehicle | Extra snapshots/status traffic | Live camera, overlay, metadata; frame-bound observed boxes | Medium |
| P1 compute | Serial models + persistence under global lock; historical ~1 Hz | Sparse boxes/analysis | Short interaction undersampled | Camera fairness and CPU contention | M analysis + inference execution; bounded fair scheduling | Medium/high |
| P2 preview | 10 FPS default; historical HTTP 9.42 vs capture 14.85 | Choppiness despite fresh capture | No proof lost solely due preview cap | JPEG/network budget rises with FPS | Existing preview path; cadence/instrumentation tuning | Medium |
| P2 fallback | Unordered polls; old JPEG retained during stall | Old/source-mismatched surface possible | Stale display, not extra backend hits | Redundant work | UI request lifecycle and explicit freshness | Low/medium |
| P3 telemetry | No browser paint/frame join or current full-load percentiles | Delay source hard to diagnose | Release evidence incomplete | Bounded sampling overhead | Existing diagnostics and frame metadata | Low |

# Recommended Architecture

Keep one native latest-frame slot and one capture reader per effective source. Attach immutable camera/session epoch, sequence, decode time and source PTS when available. Preview and inference consume independently; measure sensor/OSD latency separately from post-decode age. Keep queues bounded and replace pending inference with the newest frame, with fair per-camera admission. Measure before changing JPEG transport; WebRTC is not required by current evidence.

Run one validated vehicle inference result per analyzed frame where output parity permits reuse; bound scene/pair classifier work. Publish detections promptly, without holding the model lock through filesystem/DB work, while preserving serialized decision/event ordering. Add frame-bound metadata to the live detection contract only; preserve incident contracts.

For **observed boxes**, display the exact analyzed frame with its boxes (e.g. an analyzed-frame panel), or use a bounded frame-aware renderer with a measured latency budget. The smooth live surface may use separately marked, short-lived display predictions only after validation; those are not observed detections and must never feed collision logic. Hiding expired boxes is safer than implying alignment. No renderer can make old measurements current without prediction or delaying video.

Require accepted participant seeds, revalidated persistent identities, canonical same-pair history, measured approach → interaction evidence → immediate post evidence, unique capture observations and explicit ambiguity/expiry resets before confirmation. Keep 3 hits/5 s; insufficient evidence remains candidate/review. No predicted-only participant, borrowed queue history or classifier-only confirmation. Unresolvable occlusion/contact cannot justify saying “actual A and B collided.” Preserve incident creation, dispatcher review and fresh one-shot alarm boundaries.

# Staged Change Plan

All stages are future candidates, not implementation authorization. P0 safety gates block release throughout; the order below is an engineering dependency order, not permission to release stages 1–4 independently as safe collision detection.

| Stage | Objective / likely modules | Dependencies | Tests and success gate | Rollback/stop condition |
|---|---|---|---|---|
| 1 Smooth/fresh video | M capture/JPEG/stream/snapshot; existing diagnostic telemetry | Establish active runtime settings and full-load baseline | One reader; slow consumer/reconnect/stall tests; preview/freshness gates below | Age/backlog growth, duplicate readers, higher load without delivery gain |
| 2 Fast synchronized boxes | M result metadata; `lib/types.ts`, `lib/api-client.ts`; live-camera/overlay/workspace | Stage 1 frame epoch/sequence | Exact frame join, aspect ratios, resize, source switch, late response, missing-result expiry; no stale observed overlay | Wrong frame/source or misleading prediction; preview budget exceeded |
| 3 Detector/domain improvement | M model seam; detector preprocessing/acceptance; separate future candidate assets | Cleared independent sources, capture, human labels, source-family splits | Per-class/raw/accepted recall and precision; freeze candidate before protected stress evaluation | No participant gain, negative regression, leakage or CPU budget failure |
| 4 Conservative identity | Vehicle tracking/logical continuity interfaces; new bounded production adapter only after explicit review | Stages 2–3 real accepted observations | Miss/crossing/jump/reused-ID/duplicate/weak-support tests; annotated trajectory gates | History inheritance, fabricated seeds or ambiguous reassignment |
| 5 Same-pair verification | Pair ledger, temporal verifier, collision features; M decision seam | Stage 4 identity validity | Distinct-pair test genuinely passes; queue/near-miss/stopped/fallen/occlusion controls; true participant positives | Any unrelated-pair hit, predicted hit or false confirmation |
| 6 Bounded integration | Inference execution and narrowly scoped M orchestration | Stages 1–5; preserve operational boundary | Concurrent cameras/uploads, fairness, reconnect reset, 30-min soak; unchanged incident/alarm regression suites | Starvation, unbounded work, duplicate/fresh-alarm regression; disable new decision path for release |
| 7 Physical validation | New isolated validation output; existing evidence read-only | Frozen implementation/model; stage gates | Separate replay/native campaigns, human participant truth, independent holdout; all metrics below | Any P0 failure or inadequate sample/provenance: no release claim |

# Measurable Success Gates

**Proposed engineering targets, not achieved results or guarantees.** Report sample counts, exclusions, median/p95, source/hardware/settings and confidence intervals. Treat correlated frames as trajectories/sessions when estimating uncertainty.

| Metric | Proposed gate / measurement population |
|---|---|
| Preview rate | ≥90% of independently measured source rate (≥13.5 FPS for sustained 15 FPS), unique browser-presented frames; three ≥10 min sessions plus a 30 min full-load soak, one and intended maximum cameras. |
| Preview frame age | Decode→browser median ≤100 ms, p95 ≤200 ms; separately instrument source→browser target median ≤300 ms/p95 ≤500 ms with synchronized clock/visible time source. Report startup/reconnect separately; unknown clocks cannot pass absolute-age gate. |
| Inference input age | Decode→model-start median ≤75 ms, p95 ≤150 ms across ≥1,000 analyses per load configuration; queue depth ≤1 pending latest frame/camera, no age growth. |
| Detector latency/cadence | Provisional median ≤120 ms/p95 ≤200 ms at validated resolution; aim ≥5 unique analysis observations/s/camera and ≤250 ms p95 observation gap in eligible interaction intervals. Validate feasibility before promising short-event coverage; if CPU cannot meet it, bound supported cameras/hardware rather than weaken evidence. |
| Proposal/accepted recall | Predeclare IoU≥0.50 matching for new human-labeled data; proposal ≥95%, accepted ≥90% on assessable vehicle instances. Report both, precision ≥95%, false proposals/frame and small/occluded strata. Source B diagnostic IoU≥0.30 scores stay separately labeled. |
| Car/motorcycle recall | Each accepted ≥90% and proposal ≥95%; ≥100 independent trajectories and ≥500 assessable instances **per class per domain** across ≥3 sessions. Report 95% intervals, do not pool classes/domains to hide misses. Truck/bus/bicycle same provisional targets only where sample gate met; otherwise insufficient evidence. |
| Identity/pair accuracy | Zero history inheritance and false pair associations in all safety controls; ≤1 ID switch/100 evaluated trajectories as preliminary tracking target. Any switch contaminating collision state fails release. ≥200 labeled trajectories including ≥50 crossings/occlusions; report fragmentation and unknown identity, not only switch count. |
| False confirmations | Zero on protected controls and ≥200 independent held-out negative events plus ≥20 camera-hours normal traffic **per tested domain**. Zero/200 still has roughly 1.5% one-sided 95% event-rate upper bound; zero/20 h roughly 0.15/h under Poisson assumptions. Expand samples for stronger claims. |
| Confirmation latency/recall | From first qualifying same-pair interaction evidence: median ≤1 s, p95 ≤2 s **only with required real observations available**; ≥30 independent human-verified assessable positives initially, ≥90% correctly attributed confirmations as provisional target. Report missed/unconfirmed events and physical-impact→confirmation separately; do not hide failures in latency denominator. |
| Box accuracy/stability | Exact sequence match for all observed overlays; measure IoU and normalized center error against the displayed frame, stationary-track jitter and moving lag separately on ≥500 labeled observations/100 tracks. Target median IoU≥0.70 and p95 center error ≤10% box diagonal on assessable boxes; bound prediction age and report prediction results separately. |
| CPU/memory | Whole-host sustained CPU ≤70%, one-second p95 ≤85% at declared camera count, leaving decode/UI headroom; backend RSS provisional ceiling 2 GiB and ≤5% growth after warm-up over 30 min, no growing queues. Recalibrate hardware feasibility explicitly; historical CPU percentages were per core. |

# Future Change Candidates

Only these bounded modules/seams are candidates; listing a file does not authorize rewriting unrelated contents.

1. `backend/main.py`: `LiveCameraMonitor` capture/preview/scheduling/result metadata; model invocation, extractor/ROI and pair-decision seams. Keep existing thresholds until separately validated; preserve persistence/API behavior.
2. `backend/services/inference_execution.py`, `live_collision_diagnostics.py`, `detector_preprocessing.py`: fair bounded execution, stage timing and frame provenance. Extend telemetry without exposing camera credentials.
3. `backend/services/vehicle_tracking.py`, `logical_vehicle_continuity.py`, `vehicle_detection_tiers.py`: conservative identity/weak-support contracts only after offline validation. No automatic promotion of weak or predicted evidence.
4. `backend/services/pair_hit_ledger.py`, `temporal_crash_verifier.py`, `collision_features.py`, `collision_pair_classifier.py`: same-pair ownership and attributable interaction; ledger may need only integration, not algorithm changes. Pair classifier remains supporting and budgeted.
5. `components/live-camera.tsx`, `cctv-video-overlay.tsx`, `cctv-monitor-workspace.tsx`: synchronized display, age expiry, bounded/ordered polling and preview handling only. `lib/types.ts`, `lib/api-client.ts`: additive live frame/result metadata and consumer transport only.
6. Focused corresponding backend/frontend tests and **new isolated validation artifacts**. The distinct-pair safety assertion must remain substantive. Future separately named detector candidate/configuration/data work requires its own authorized stage; existing model files and source assets are not replacement targets in this audit.

**Future implementation rule: CHANGE ONLY WHAT THE AUDIT EXPLICITLY LISTS AS A CHANGE CANDIDATE.** If a direct dependency outside this list emerges, explain it and obtain separate scope approval first.

# Protected / Do Not Change

- Authentication/session security, password handling, user accounts, role grants and Admin/Dispatcher/Responder permissions.
- PostgreSQL schema, existing database data, production incidents, camera CRUD semantics, camera credential privacy/redaction and saved credentials.
- Incident API contract, `operational_detection.py`/Phase 3 persistence workflow, dispatcher assignment, responder workflow, Response History. Inspected for dependency only; no change required by current evidence.
- Alarm arming UX/audio asset, fresh-incident one-shot semantics, candidate/aftermath silence and duplicate handling; alarm/dispatcher files are regression consumers, not redesign candidates.
- Existing Phase 8C and Source B evidence, all protected validation assets, licensing/provenance manifests, training-source originals and existing model weights. Read-only regression use does not authorize relabeling, tuning on or overwriting them.
- Unrelated frontend pages/backend APIs, `backend/carc.py`, and all other modules outside the explicit candidates. No threshold, geometry, 3-hit, 5-second, incident or alarm change in this task.

# Tests / Evidence Reviewed

| Evidence | Scope and result |
|---|---|
| Current code | M live class/helpers/model calls/status/stream/persistence; inference, diagnostics, tracker/continuity/tier/ledger/verifier interfaces; Phase 3 incident boundary; live overlay, polling, dispatcher and alarm contracts. No production app import/start required. |
| [Diagnostic telemetry report](live-collision-diagnostic-telemetry-2026-09-26.md) and current AST-isolated tests | Instrumentation separates proposals, acceptance, visited pairs, quality, streak and decision; telemetry does not provide participant identity. |
| [Source B Phase 1](source-b-physical-pair-baseline-2026-09-30.md), [Phase 2](source-b-participant-continuity-phase2-2026-09-30.md), [Phase 3](source-b-detector-bottleneck-phase3-2026-10-01.md) | Participant limits, unsafe scene streak, offline continuity defect, queue comparison, failed detector recovery. Reviewed Phase 2 prototype and Phase 3 `evidence_table.csv`/paired timing JSON under `backend/validation/`. |
| [Existing candidate sweep](../backend/validation/live_cctv_audit/fix_candidate_report.md) | Completed size/ROI/tiling/negative evidence reused, not rerun. |
| [Restoration report](live-monitor-restoration/REPORT.md), [preview latency report](preview-latency/REPORT.md) | Component/harness measurements, no-browser-validation limitations retained. Preview report's 23 assertions passed but runner had file-lock cleanup failure; restoration report retained one pre-existing integration error. Neither is represented as a clean current full-suite pass. |
| [Phase 4 Stage A](tapo-domain-detector-phase4-2026-10-01.md), [Stage B](tapo-rtsp-recovery-phase4-stage-b-2026-10-01.md), [B2](tapo-native-road-gate-phase4-stage-b2-2026-10-01.md), [replay pilot](tapo-replay-domain-detector-phase4-2026-10-01.md), [Round 3 acquisition](tapo-replay-source-acquisition-round3-phase4-2026-10-01.md) | Stage A failure superseded by saved-record RTSP success; native view still replay. Early empty-source gate superseded by cleared Round 3 sources, not by capture/training/evaluation. |
| **Fresh focused suite** | `backend/.venv/Scripts/python.exe -B -m unittest backend.tests.test_live_collision_diagnostics backend.tests.test_pair_hit_ledger -q`: **27 run, 26 passed, 1 expected failure**, exit 0. Inference/persistence/media I/O stubbed; current worker decision body executes. |
| **Fresh direct safety assertion** | Directly invoked existing test method without runner expected-failure handling: **exit 1**, `AssertionError: 'confirmed_crash' == 'confirmed_crash'`. No test edit, fake operational incident or hidden failure. |

No expensive conclusive experiment was repeated. Current-process settings, actual display FPS/latency, real-road recall, active device, full-load resource bounds and physical contact truth remain explicit evidence gaps. This task's only deliverable is this report; diagnostic commands were read-only or isolated tests with mocked operational side effects.

# Audit Verdict

**MULTIPLE_INTERACTING_BLOCKERS**

Safe participant attribution is blocked by missing accepted detections, absent live identity/pair ownership and insufficient interaction evidence. Display synchronization and bounded execution also require targeted work. Existing capture improvements should be retained; neither threshold reduction nor tracker/ledger integration alone is a defensible fix. No implementation was performed.

AUDIT COMPLETE — NO CHANGES MADE — SEND REPORT BEFORE IMPLEMENTATION
