# Fast Collision Temporal Detection Audit

Date: 2026-10-09
Scope: audit first, with one measured low-risk detector optimization
Production detector: `backend/best.pt`
Validation rule: operational incident persistence and evidence-image writes were blocked during physical benchmarking; collision footage was not intentionally tested.

## Root Cause of Unstable Detection View

The unstable box display was caused by low analysis cadence, not frontend polling. The camera workers already use a one-frame latest-slot, bounded fair scheduling, and an exact analyzed-frame packet. Before this audit, the shared inference path nevertheless ran the same YOLO detector twice on every analyzed frame:

1. the primary inference call produced the normal detections;
2. `detect_vehicle_boxes()` called the configured vehicle model again.

`backend/best.pt` and the configured `yolov8n.pt` are byte-identical. Both are 6,549,796 bytes and have SHA-256 `F59B3D833E2FF32E194B5BB8E08D211DC7C5BDF144B90D2C8412C47CCFC83B36`. The second call therefore spent CPU time recomputing the same result.

The bounded optimization compares the files at startup. If they are byte-identical, the vehicle detector shares the primary model object and extracts vehicle boxes from the primary result. A distinct configured model still follows the former separate-inference path. No model, threshold, ROI, classifier, collision rule, alarm rule, or incident rule changed.

## Current Analysis Cadence

The previous two-camera physical baseline was:

| Camera | Capture | Preview | Analysis |
|---|---:|---:|---:|
| Bago CCTV | 14.8 FPS | 3.8 FPS | 1.2 FPS |
| FOBOS MODEL GW600 | 30.2 FPS | 3.8 FPS | 1.0 FPS |

After removing the duplicate inference, the physical two-camera run measured:

| Camera | Capture FPS mean / p50 | Preview FPS mean / p50 | Analysis FPS mean / p50 |
|---|---:|---:|---:|
| Bago CCTV | 14.90 / 15.00 | 3.26 / 3.60 | 3.33 / 3.20 |
| FOBOS MODEL GW600 | 27.41 / 29.80 | 3.26 / 3.60 | 2.84 / 3.20 |

Bago by itself reached 10.01 FPS mean and 11.60 FPS p50 analysis. With both cameras active, CPU contention reduced each camera to about 3.2 analyzed observations per second. That is a substantial improvement over the baseline but remains below the desired sustained target of 5 per active camera.

The capture threads remained independent from slow inference. Latest native frames continued to replace older frames instead of accumulating a backlog.

## Pipeline Timing Breakdown

An isolated safe-scene profile measured eight-thread CPU execution after result reuse:

| Stage | p50 | p95 |
|---|---:|---:|
| Frame copy | 0.650 ms | 1.097 ms |
| Primary preprocess | 4.558 ms | 6.746 ms |
| Primary model inference | 118.281 ms | 127.760 ms |
| Primary postprocess | 1.658 ms | 2.318 ms |
| Primary predict wall time | 126.509 ms | 135.382 ms |
| Result extraction | 1.034 ms | 1.723 ms |
| Vehicle extraction from primary result | 0.652 ms | 1.390 ms |
| ROI/filter/scaling | 0.430 ms | 0.955 ms |
| Crash classifier | 23.417 ms | 28.535 ms |
| Frame quality gate | 12.456 ms | 17.986 ms |
| Collision diagnostic emit | 0.001 ms | 0.004 ms |
| Analysis-packet JPEG | 3.306 ms | 4.547 ms |
| Total profiled path | 169.817 ms | 185.642 ms |

The physical two-camera run measured the complete live worker path once per new analyzed sequence:

| Camera | Frame copy p50/p95 | Model processing p50/p95 | JPEG p50/p95 | Full analysis p50/p95 |
|---|---:|---:|---:|---:|
| Bago | 1.33 / 1.85 ms | 128.29 / 174.49 ms | 10.83 / 12.64 ms | 160.61 / 217.98 ms |
| FOBOS | 0.18 / 0.24 ms | 133.29 / 189.44 ms | 3.07 / 3.79 ms | 145.14 / 204.21 ms |

Freshness and scheduling observations were:

| Camera | Latest-frame age p50/p95 | Source age at analysis start p50/p95 | Completion age p50/p95 |
|---|---:|---:|---:|
| Bago | 31 / 91 ms | 31 / 79 ms | 188 / 281 ms |
| FOBOS | 23 / 53 ms | 31 / 47 ms | 172 / 234 ms |

The two-camera scheduler's maximum pending depth was two, one latest job per camera. It did not grow with incoming capture frames. The dominant remaining cost is model execution under simultaneous CPU load; frame copying, diagnostics, and JPEG encoding are secondary.

## Available Hardware Acceleration

| Component | Finding |
|---|---|
| CPU | 12th Gen Intel Core i5-12450H, 8 physical / 12 logical cores |
| RAM | 8,267,882,496 bytes, about 7.70 GiB |
| GPU | Intel UHD Graphics, driver 32.0.101.7076 |
| NVIDIA/CUDA | No NVIDIA device; PyTorch CUDA unavailable; zero CUDA devices |
| PyTorch | 2.11.0+cpu, 8 compute threads and 8 interop threads |
| Ultralytics | 8.4.38 |
| OpenCV | 4.13.0; OpenCL available/enabled, FFmpeg and Intel IPP available, no OpenCV CUDA device |
| ONNX Runtime | Not installed |
| OpenVINO | Not installed |
| ONNX exporter package | Not installed |
| DirectML / `torch_directml` | Not installed |

The current approved detector therefore has only the PyTorch CPU execution path available. OpenCV OpenCL does not accelerate the PyTorch YOLO call. The Intel GPU may offer a future OpenVINO path, but that path is not installed, exported, benchmarked, or semantically validated in this environment. No large runtime dependency was installed during this audit.

## Runtime Benchmarks

Only the installed PyTorch CPU runtime could be benchmarked. CUDA, ONNX Runtime, OpenVINO, and DirectML results are intentionally absent because those execution providers are unavailable.

The isolated profile used three safe inputs: a vehicle sample and the previously captured exact analyzed frames from Bago and FOBOS. It did not persist incidents or test collision footage.

| Input | Previous duplicate path p50/p95 | Reused-result path p50/p95 | Removed second YOLO mean |
|---|---:|---:|---:|
| Safe vehicle scene | 407.818 / 515.409 ms | 271.791 / 392.118 ms | 189.529 ms |
| Bago analyzed frame | 286.705 / 359.606 ms | 188.569 / 262.982 ms | 106.090 ms |
| FOBOS analyzed frame | 246.467 / 335.976 ms | 136.761 / 139.678 ms | 101.697 ms |

For all three inputs, vehicle boxes were exactly equal and classifier outputs were equal. On the safe vehicle scene, all six accepted vehicle boxes retained the same labels, confidences, and coordinates. This is expected because the two weight files are byte-identical and the reused object is the same already-approved model result.

Thread counts of 2, 4, 6, 8, and 12 were compared. Eight threads, the current configuration, had the best mean total time at 168.935 ms. Raising the count to 12 degraded mean total time to 216.805 ms. The audit therefore retained the existing thread configuration.

Raw results:

- `backend/validation/fast_collision_20261009/detector-profile.json`
- `backend/validation/fast_collision_20261009/post-optimization-physical-benchmark.json`

## Multi-Camera Throughput

The one-camera Bago run sustained 10.01 FPS mean analysis with 15.00 FPS p50 capture. The two-camera run sustained 3.33 FPS mean for Bago and 2.84 FPS mean for FOBOS, with a 3.20 FPS median for both.

During the two-camera run:

- both cameras remained `LIVE`;
- Bago remained at 1280x720 and FOBOS at 640x480;
- the scheduler pending depth never exceeded two;
- analyzed packet camera mismatches were zero;
- stopping the USB worker did not stall Bago: its capture sequence advanced from 771 to 823 during the following three seconds;
- system CPU was 25.3% p50 and 69.8% p95 across all logical processors;
- the Python process used 233.5% p50 and 376.8% p95 CPU in psutil's multi-core process scale;
- process memory was 456.41 MiB p50 and 462.84 MiB p95.

The synthetic three-camera scheduler regression passed. It confirms round-robin order, latest-frame replacement, per-camera/session cancellation, and a queue bounded to one pending job per camera. This is scheduler correctness evidence, not a claim that this machine can run three physical cameras at 5 analysis FPS each.

## Tracking / Visual Continuity Design

The repository contains a bounded per-camera `VehicleTrackingService` and a logical continuity service. Tests confirm stable IDs, bounded history, camera isolation, gap reset, stale expiry, ambiguity rejection, and bounded camera/identity registries.

They are not currently integrated into the exact analyzed-frame production packet. The current tracker retains internal state across a short missed observation but returns no active visualization box for that miss. Wiring it into the UI now would therefore fail the stated requirement that a short detector miss keep a valid box visible, or would require inventing a prediction policy that has not been validated.

The smallest safe follow-up is a separate visualization stage:

1. key the tracker by `camera_id + session_id`;
2. update it only from real detector observations;
3. emit detected boxes and short-lived predicted boxes as separate internal states;
4. clear all state on a new session, stop, or disconnect;
5. cap prediction by elapsed time and missed-observation count;
6. keep predicted boxes out of the detector-evidence packet and collision hit ledger.

No frontend or tracking integration was made in this audit.

## Detector Evidence vs Tracked State

The existing exact analyzed-frame packet remains detector evidence: its image, boxes, source camera, session, frame sequence, and capture time refer to the same analyzed frame. The physical benchmark observed zero camera-identity mismatches.

Future tracked output must be a different packet or explicitly typed collection. A detector observation may create or correct a track. Re-rendering that track on later capture frames must not create detector observations, extend the three-hit window, or increment pair evidence. One detector hit displayed ten times is still one detector hit.

The pair ledger and temporal verifier tests confirm that independent pairs and cameras remain isolated in their service implementations. The production integration gap described below remains visible as an expected failure.

## Fast Event Preservation

Removing duplicate YOLO execution raises the observation rate and reduces the interval in which a fast interaction can be missed. Under two-camera load, however, the measured median remains approximately 3.2 observations per second per camera, or about 312 ms between observations. That cadence does not meet the 5 FPS engineering target and cannot guarantee capture of short pre-impact motion.

A recent-frame buffer was considered but not added. Raw 1280x720 BGR frames consume about 2.64 MiB each; two seconds at 15 FPS would consume about 79 MiB per camera before object and queue overhead. A compressed buffer would use less memory but add encode cost and requires a separately validated trigger/replay design. It should be introduced only with the future pair-safe collision integration, with a fixed per-camera duration and byte cap, automatic overwrite, and no use as an unbounded recording system.

The recommended order is to benchmark an accelerated runtime, then add visualization-only tracking, then evaluate a bounded interaction-triggered replay path. Faster polling or duplicate inference in the Detections page would not solve the detector cadence.

## Static Crash Image Limitation

A static damaged-car image can test vehicle detection, classifier appearance response, box visibility, and the static aftermath review path. It cannot show pre-impact approach, impact timing, same-pair motion, collision occurrence, or temporal continuity. A high static-image score is therefore not collision-validation evidence and must not be reported as such.

## Collision Safety Constraints

This change does not modify the three-hit rule, five-second window, classifier threshold, collision geometry, `confirmed_crash` criteria, alarm behavior, incident creation, tracking, pair logic, or detector thresholds. The physical benchmark blocked persistence and evidence-image writes while allowing normal analysis decisions to execute. No persistence attempt occurred in the observed non-collision scenes.

Regression coverage confirms that one high frame cannot create an aftermath review candidate, tracked identities remain bounded and camera-isolated, high classifier confidence cannot bypass temporal verification, and normal motion/overlap negatives remain rejected.

## Pair-Safety Regression

`test_distinct_physical_pairs_must_not_share_three_hit_confirmation` remains an expected failure. The production live path still needs explicit ownership of the three required hits by the same physical A-to-B pair. The standalone pair ledger already has tests proving that three different pairs cannot share hits, but that ledger is not yet the authoritative production confirmation path.

The regression was not hidden or changed. The collision/tracking suite completed with 135 tests passing and exactly one expected failure.

## Recommended Architecture

Keep the byte-identical result reuse because it is output-equivalent and measurably faster. Preserve the current latest-frame scheduler and exact analyzed-frame packet.

The next performance stage should export the unchanged approved detector and benchmark OpenVINO on this Intel machine against PyTorch using the same corpus. Adoption requires matching accepted counts, labels, confidences within an explicit tolerance, and box coordinates within an explicit pixel/IoU tolerance. If acceleration cannot sustain at least 5 analyzed observations per second per active camera, hardware with a supported inference accelerator is required.

Tracking should follow as a visualization-only, per-camera/session layer with bounded prediction lifetime. Pair-safe collision integration must be a separate stage that makes detector observations authoritative, binds hits to the same logical A-to-B pair, and retains the current three-hit/five-second and alarm semantics.

## Measured Result

The audit retained one production optimization in `backend/main.py` and two focused regression tests in `backend/tests/test_camera_performance.py`. It also added reproducible profiling and physical benchmark artifacts under `backend/validation/fast_collision_20261009/`.

Validation completed:

- 58 camera health, performance, role, security, preview, scheduler, webcam, and live-monitor tests passed;
- 135 collision, aftermath, diagnostics, continuity, pair-ledger, temporal, vehicle-tier, and tracking tests passed with exactly one expected failure;
- Python compilation and scoped diff checks passed;
- one-camera and two-camera physical acquisition, analysis packets, fairness, freshness, resource use, and stop isolation were measured;
- no camera process or USB device handle remained after the benchmark.

No UI file, database schema, model weight, threshold, alarm behavior, or incident semantic was changed by this audit.

## Remaining Bottleneck

Simultaneous PyTorch CPU model processing remains the bottleneck. With two active cameras, model processing was about 128-133 ms p50 per camera, and complete analysis was about 145-161 ms p50. Shared CPU execution and the additional crash classifier reduce sustainable per-camera cadence to about 3.2 FPS.

The Intel GPU has no installed supported detector runtime in the current environment. Tracking can improve visual continuity but cannot create missing detector evidence or safely substitute for the required same-pair observations. Until acceleration and pair-safe integration are validated, fast collision observation remains performance limited.

## Final Verdict

HARDWARE_LIMITED
