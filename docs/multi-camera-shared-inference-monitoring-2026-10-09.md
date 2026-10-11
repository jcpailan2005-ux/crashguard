# Multi-Camera Shared Inference Monitoring

Date: 2026-10-09
Project: CrashGuard school demo
Mode: bounded implementation

## Cameras Tested

Bago CCTV:

- Saved ID: `CAM-30960048ED`
- Source: RTSP CCTV
- Physical result: LIVE at 1280x720
- Simultaneous result: PASS

FOBOS MODEL GW600:

- Saved ID: `CAM-A7F4F11CF9`
- Source: external USB webcam through the private `webcam://school-demo-webcam` alias
- Private Windows selection: device 0, MSMF, reported as `REDRAGON Live Camera`; this is the external USB camera, not the built-in laptop camera
- Physical result: LIVE at 640x480 and approximately 30 capture FPS
- Simultaneous result: PASS

Additional:

- A deterministic three-camera scheduler test passed.
- The bundled non-collision road image `public/samples/vehicle-02.jpg` produced six accepted car/truck boxes. Its rendered proof is `backend/validation/multi_camera_20261009/safe-vehicle-exact-box-proof.jpg`.

## Runtime Model

Model:

- Primary detector: `backend/best.pt`, loaded once at module scope by `YOLO`; SHA-256 `F59B3D833E2FF32E194B5BB8E08D211DC7C5BDF144B90D2C8412C47CCFC83B36`.
- Vehicle detector: `yolov8n.pt`, also loaded once at module scope; its current file hash is identical to `backend/best.pt`.
- Crash classifier: `backend/models/crash_classifier.pt`, loaded once at module scope; SHA-256 `26393B9D3E7B5E32766FB0A0F6DAB6040C87C2DDE39A8279AF2D8FE58EF97DA9`.
- Every `LiveCameraMonitor`, regardless of source type, calls the same module-global detector and classifier objects through `_analyze_current_frame()`.
- Primary detector `imgsz`: 640.
- Vehicle detector `imgsz`: Ultralytics production default 640 because no per-camera override is passed.
- Proposal confidence: the existing Ultralytics default 0.25; unchanged.
- Normal vehicle acceptance: 0.40; unchanged. The existing, source-independent crash-suspicion retry at 0.15 remains unchanged.
- Vehicle classes: car, motorcycle, bus, truck, bicycle, vehicle, van, SUV, automobile, and auto, with motorbike/moped normalized to motorcycle where applicable.

Shared across cameras: YES

Datasets loaded at runtime: NO

The runtime path opens only trained weight artifacts and camera frames. Training images, annotations, Source B, Phase 8C material, and dataset manifests are not imported by camera inference.

## Multi-Camera

Simultaneous sources: 2 physical sources (Bago RTSP and external USB) for 20 seconds, after a 12-second one-camera baseline.

Camera isolation: PASS

Capture isolation: PASS

Inference fairness: PASS

Scheduling policy:

- Each camera retains its own capture worker, session ID, sequence, timestamp, latest-frame slot, health, reconnect state, and result.
- One shared inference thread services an ordered latest-frame map.
- At most one pending callback is stored per camera. A newer frame replaces that camera's pending frame without changing its turn.
- The oldest waiting camera runs next. This prevents a high-FPS source from repeatedly moving ahead of a slower source.
- The queue bound is the number of cameras, not the number of captured frames.
- A reconnect retires the prior session. Pending work is cancelled, callbacks check the scheduled session, and in-flight inference checks the epoch again before publishing boxes or continuing toward persistence.
- Exceptions from one callback are caught by the scheduler so the next camera continues.

Observed maximum pending work was one for one camera and two for two cameras. Both physical feeds advanced analyzed sequences. There were zero camera-ID mismatches across 85 sampled exact packets in the final simultaneous run.

Physical failure isolation also passed: after stopping FOBOS, Bago advanced from capture sequence 700 to 754 during the next three seconds.

## Detection Visualization

Vehicle boxes: PASS

Class labels: PASS

Confidence: PASS

Exact frame synchronization: PASS

Each tile fetches one analyzed JPEG and its boxes in the same packet. The packet includes camera ID, session ID, sequence, capture timestamp, source dimensions, analysis timestamps, label, and confidence. The client rejects a wrong camera, retired session, duplicate/older sequence, invalid dimensions, invalid image payload, and packets outside the 500 ms transport freshness window. The exact image and its exact boxes may remain together for a five-second viewing window; they are never placed over a newer raw frame. A new zero-box packet replaces the older boxed packet.

The responsive SVG uses the packet's source dimensions and `preserveAspectRatio="xMidYMid meet"`. Box display waits until that specific image identity has loaded at the declared dimensions, preventing an old image-loaded state from exposing new boxes early.

Physical evidence:

- `bago-exact-analyzed-frame.jpg`: exact live Bago analyzed frame; current empty yard produced zero accepted vehicles.
- `fobos-exact-analyzed-frame.jpg`: exact live USB analyzed frame; the current dark view produced zero accepted vehicles.
- `safe-vehicle-exact-box-proof.jpg`: ordinary, non-collision road scene with six visibly aligned labels and boxes at unchanged production thresholds.
- `safe-box-proof.json`: dimensions, class labels, confidence, and coordinates for that proof.

The in-app browser controller could not initialize because its Node sandbox metadata was unavailable, so a fresh browser screenshot of the React grid was not captured. Type checking, UI contracts, physical exact packets, and rendered box evidence all passed.

## Collision Visualization

Candidate status: PASS

Confirmed status: NOT_TESTED

Fake crash box introduced: NO

The UI maps existing result fields to `MONITORING`, `ANALYZING POTENTIAL COLLISION`, `CONFIRMED CRASH`, and `INCIDENT SENT`. No new collision class, collision box, detector decision, or alarm trigger was added. Candidate and analyzing states remain silent. Collision footage was not intentionally tested.

## UX

Camera grid: PASS

Show all: PASS

Expand: PASS

Add Camera: PASS

CCTV setup: PASS

USB setup: PASS

`Show all cameras` renders real saved cameras in a responsive one-column/two-column/three-column wrapping grid without placeholder feeds. Detection display defaults ON and can be toggled. Each tile shows the name, CCTV/USB type, health badges, exact analyzed view, vehicle count, analysis age, collision state, and an expand button. `Focused` returns to the larger existing monitor, whose exact analyzed-frame view can also expand. Entering grid mode starts every active, detection-enabled camera independently with `Promise.allSettled`, so one failed start does not discard successful starts.

The existing Add Camera dialog remains permission-controlled and supports both CCTV/network and safe named USB sources. Users do not enter a device index or OpenCV backend.

## Performance

Final benchmark conditions: production model pipeline, one shared inference worker, preview JPEG requested at approximately 4 Hz by the harness, operational persistence disabled, no intentional collision input. The backend service was also running during this conservative measurement. Process CPU can exceed 100% because `psutil` reports usage across logical cores.

### One camera: Bago

| Metric | Result |
|---|---:|
| Capture FPS | 15.2 |
| Preview FPS under 4 Hz consumer | 3.8 |
| Analysis FPS | 2.4 |
| Capture frame age p50 / p95 | 39 / 99 ms |
| Analysis source age p50 / p95 | 484 / 610 ms |
| Inference time p50 / p95 | 428.51 / 515.63 ms |
| System CPU p50 / p95 | 100 / 100% |
| Process CPU p50 / p95 | 464.1 / 533.2% |
| Process memory p50 / p95 | 441.25 / 447.46 MB |

### Two cameras simultaneously

| Metric | Bago RTSP | FOBOS USB |
|---|---:|---:|
| Capture FPS | 14.8 | 30.2 |
| Preview FPS under 4 Hz consumer | 3.8 | 3.8 |
| Analysis FPS | 1.2 | 1.0 |
| Capture frame age p50 / p95 | 34 / 93 ms | 19 / 47 ms |
| Analysis source age p50 / p95 | 453 / 578 ms | 453 / 516 ms |
| Inference time p50 / p95 | 430.76 / 480.75 ms | 438.68 / 483.33 ms |
| Distinct analyzed slots sampled | 24 | 23 |

Two-camera system CPU was 100% p50/p95. Process CPU was 454.0% p50 and 539.4% p95. Process memory was 483.48 MB p50 and 488.19 MB p95. Capture and the UI-facing latest slots remained fresh while analysis slowed fairly to about one frame per second per camera. The current hardware is therefore CPU-limited for inference, but it does not build a stale FIFO backlog.

Raw measurements are in `backend/validation/multi_camera_20261009/physical-benchmark.json`.

## Regressions

RTSP: PASS

USB: PASS

Stage 1: PASS

Stage 2: PASS

Pair-safety: EXPECTED FAIL/XFAIL

Validation summary:

- 55 camera health, performance, authorization, security, Stage 1/Stage 2, RTSP, USB, preview, and scheduler tests passed.
- 64 collision diagnostics, pair ledger, temporal verification, tracking, and continuity tests passed with exactly one expected failure.
- The preserved expected failure is `test_distinct_physical_pairs_must_not_share_three_hit_confirmation`.
- 46 frontend tests passed.
- Final focused scheduler/webcam run: 11 passed.
- TypeScript type check passed.
- Safe ordinary-object proof: six accepted boxes, visually inspected.
- Backend health after restart: PASS on `127.0.0.1:8010`.

## Unchanged Systems

Detector semantics: UNCHANGED

Collision semantics: UNCHANGED

Incident semantics: UNCHANGED

Alarm: UNCHANGED

Auth: UNCHANGED

Database schema: UNCHANGED

Datasets: UNCHANGED

No production changes were made to tracking, PairHitLedger, pair ownership, interaction verification, classifier thresholds, collision geometry, the three-hit rule, the five-second temporal rule, incident creation, alarm delivery, authentication, permissions, or database schema.

Production files changed for this implementation are limited to:

- `backend/main.py`
- `backend/services/inference_execution.py`
- `components/cctv-monitor-workspace.tsx`
- `components/cctv-video-overlay.tsx`
- `lib/api-client.ts`

Tests, validation scripts/artifacts, and this report are non-production files.

## Final Verdict

MULTI_CAMERA_READY_PERFORMANCE_LIMITED
