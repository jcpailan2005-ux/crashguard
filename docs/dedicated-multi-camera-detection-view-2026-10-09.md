# Dedicated Multi-Camera Detection View

Date: 2026-10-09
Project: CrashGuard school demo
Mode: frontend presentation only

## Result

Detection View route: `/dispatcher/detections` (HTTP 200 from the running Next.js development server)

Live Monitor link: PASS

Bottom analyzed inspector: MINIMIZED

Simultaneous camera tiles: Dynamic responsive grid for every active saved camera; each camera owns an independent existing packet subscription, and one failed status request does not remove other tiles. The previously validated active sources are Bago CCTV and FOBOS MODEL GW600 (external USB webcam).

Vehicle boxes: PASS by component and coordinate tests; prior safe non-collision exact-frame evidence remains in `backend/validation/multi_camera_20261009/safe-vehicle-exact-box-proof.jpg`.

Labels: PASS by component tests and prior safe rendered evidence.

Confidence: PASS by component tests and prior safe rendered evidence.

Expand: PASS by implementation and component-contract tests. Fresh interactive visual validation was unavailable because the in-app browser controller could not initialize in this session.

Responsive layout: PASS by deterministic one-, two-, four-, and five-camera layout tests. Fresh browser visual inspection was unavailable for the reason above.

Exact frame synchronization: PASS

Additional inference introduced: NO

Backend changed: NO

CPU/inference behavior: UNCHANGED

Collision semantics: UNCHANGED

Alarm: UNCHANGED

## Implementation

- Added a dedicated `Camera Detection View` route with All Cameras, CCTV, and USB Webcam filters.
- Added a responsive camera grid with camera name, source type, health, freshness, analyzed-frame age, vehicle count, collision state, and an Expand action.
- Reused the existing boxes-only SSE/analyzed-frame packet path. The page does not start monitors, open cameras, submit detection requests, or create an inference loop.
- Kept each image and its annotations tied to the same `camera_id`, `session_id`, and `sequence`. The shared acceptance helper rejects the wrong camera, retired sessions, duplicate or older sequences, invalid dimensions, invalid image data, and packets outside the freshness policy.
- The SVG overlay uses the packet dimensions and `preserveAspectRatio="xMidYMid meet"`. Annotation rendering waits for the exact packet image to load at its declared dimensions.
- The Detections ON/OFF control changes SVG rendering only. Packet subscriptions and backend inference continue unchanged.
- The expanded dialog reuses the tile's existing in-memory packet and subscription. It does not create a second subscriber or open another browser tab.
- Replaced the large Live Monitor analyzed-frame inspector with a compact freshness, vehicle-count, and age summary plus the `View all detections` link.

## Failure Isolation and Performance

Status refresh uses independent settled results, and packet subscriptions remain scoped by camera ID. An unavailable or reconnecting camera remains represented without blocking other camera tiles.

The page performs one existing boxes-only packet subscription per displayed camera and reads status every four seconds. It adds no camera capture worker, detector worker, model invocation, analysis cadence change, or unbounded queue. Navigating from Live Monitor unmounts that view before mounting the dedicated page, and opening the modal reuses its tile's packet state.

## Validation

- Dedicated Detection View focused tests: 8 passed.
- Focused Detection View plus Live Monitor tests: 17 passed.
- Complete frontend suite: 54 passed, 0 failed.
- TypeScript type check: PASS.
- Multi-camera scheduler, preview latency, and local webcam pipeline regressions: 16 passed, 0 failed.
- Route request: `GET http://127.0.0.1:3000/dispatcher/detections` returned HTTP 200.
- Scoped diff whitespace check: PASS.
- Read-only source audit: PASS; the new page contains no monitor-start, capture, detection POST, or inference call.
- Existing physical evidence: Bago RTSP and FOBOS external USB packets advanced simultaneously with zero cross-camera contamination in the preceding validated run.
- Safe box evidence: six ordinary vehicle boxes were previously rendered with aligned labels and confidence at unchanged production thresholds.

The in-app browser controller could not connect because required browser sandbox metadata was unavailable. Therefore a fresh screenshot and interactive click-through of the new grid and modal could not be completed. This limits the verdict to layout-limited even though the route, types, component behavior, synchronization guards, and regressions pass.

## Scope Review

Production files changed for this frontend-only task:

- `app/dispatcher/detections/page.tsx`
- `app/dispatcher/live/page.tsx`
- `components/camera-detection-grid.tsx`
- `components/cctv-video-overlay.tsx`
- `lib/camera-analysis-view.ts`
- `lib/api-client.ts`

Test and documentation files changed for this task:

- `frontend-tests/dedicated-detection-view.test.ts`
- `frontend-tests/live-monitor-restoration.test.ts`
- `docs/dedicated-multi-camera-detection-view-2026-10-09.md`

No backend, detector, scheduler, model, threshold, camera source, tracking, PairHitLedger, collision, incident, alarm, authentication, permission, database, training, or dataset file was changed for this task. The working tree contains earlier changes outside this task; they were preserved.

## Final Verdict

DETECTION_VIEW_READY_LAYOUT_LIMITED
