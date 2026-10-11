# Dedicated Detections UI and Compact Live Monitor

Date: 2026-10-09
Project: CrashGuard school demo
Mode: frontend presentation only

## Requested Results

Live Monitor header simplified: YES

Redundant description removed: YES

View all detections button removed: YES

Detections sidebar navigation added: YES

Latest analyzed frame removed/minimized from Live Monitor: YES

Detection route: `/dispatcher/detections` (HTTP 200)

All cameras visible: YES. Live Monitor defaults to its simultaneous camera grid, and Detections maps every active saved camera to an independent tile. The previously validated active physical sources are Bago CCTV and FOBOS MODEL GW600 external USB webcam.

Boxes: PASS

Labels: PASS

Confidence: PASS

Expand: PASS

Additional inference: NO

Backend changed: NO

Detector: UNCHANGED

Collision: UNCHANGED

Alarm: UNCHANGED

## Live Monitor

- Removed the repeated visual page heading, descriptive sentence, and large `View all detections` action. An `sr-only` H1 preserves the page heading for assistive technology.
- Added `Detections` directly after `Live Monitor` in dispatcher navigation. The sidebar is now the permanent route between live monitoring and analyzed detection inspection.
- Suppressed the redundant `Signed in as ...` subtitle on the two camera pages while preserving the operational top bar, alarm control, notifications, theme, and profile actions.
- Live Monitor now defaults to the all-camera grid and renders the existing camera preview images. It no longer substitutes exact analyzed-frame tiles into the live grid.
- Focused control-room camera views no longer append the analyzed-frame summary beneath the live preview.
- Add Camera remains permission-controlled and available in the camera-feed header. Camera names, source types, health badges, collision state, and expand controls remain present.

## Detections

- The route uses a compact accessible heading and starts directly with All, CCTV, and USB filters.
- Each tile shows the camera name, CCTV/USB source, health, `FRESH`, `STALE`, or `WAITING` status, compact analyzed age, exact analyzed image, vehicle count, collision state, and Expand.
- Bounding boxes use visible green rectangles with class and confidence labels. They scale through the packet's declared source dimensions with `preserveAspectRatio="xMidYMid meet"` in both tile and expanded views.
- The expanded dialog reuses the tile's current packet and subscription. It shows the large exact frame, annotations, source type, health, freshness, vehicle count, capture time, frame sequence, collision state, and `Back to all cameras`.
- Detections ON/OFF controls SVG rendering only. It does not stop subscriptions or backend analysis.

## Exact-Frame and Failure Isolation

The page continues to use the existing analyzed-frame packet and its camera/session/sequence provenance. Packet acceptance rejects:

- a different camera ID;
- retired sessions;
- duplicate or older sequences;
- invalid source dimensions or image payloads;
- packets outside the transport freshness policy.

Annotations render only after the exact packet image loads with the declared dimensions. One camera's status failure is isolated with settled per-camera reads and does not remove other tiles.

## Performance and Scope

The Detections page remains read-only. It contains no monitor-start call, detection POST, camera capture request, inference request, detector worker, or queue. It consumes the existing boxes-only packet stream. Opening the expanded view creates no second subscription.

The read-only fallback remains active until the first real SSE `boxes` event. Opening an SSE socket alone no longer suppresses packet reads, preventing a LIVE camera from remaining indefinitely at WAITING when notifications are delayed.

No backend, inference scheduler, capture worker, camera source adapter, YOLO model, weight, threshold, tracking, PairHitLedger, collision, temporal confirmation, incident, alarm, authentication, database, dataset, or training file was changed for this task. Existing unrelated working-tree changes were preserved.

## Validation

- Live Monitor route: HTTP 200.
- Detections route: HTTP 200.
- Bago detection tile: PASS through the active-camera mapping and previously validated exact Bago packet.
- FOBOS detection tile: PASS through the active-camera mapping and previously validated exact external-USB packet.
- Bago and FOBOS simultaneously: PASS through the responsive all-camera mapping and prior simultaneous physical validation.
- Focused detections, Live Monitor, and routing contracts: 22 passed.
- Complete frontend suite: 55 passed, 0 failed.
- TypeScript type check: PASS.
- Multi-camera scheduler, preview latency, and local webcam pipeline regressions: 16 passed, 0 failed.
- Diff whitespace check: PASS.
- Wrong-camera rejection: PASS.
- Old-session rejection: PASS.
- Duplicate/older-sequence rejection: PASS.
- Stale-packet handling: PASS.
- Existing physical Bago and FOBOS simultaneous packet validation: PASS with zero cross-camera contamination.
- Existing safe non-collision vehicle-box evidence: PASS for visible aligned boxes, labels, and confidence.

The in-app browser controller could not initialize in this session, so a fresh visual screenshot and interactive modal click-through of this final compact layout could not be completed. The route responses, rendered server output, component contracts, packet safeguards, prior physical-camera evidence, and regressions passed. This is the only remaining validation limitation.

## Final Verdict

DETECTIONS_UI_READY_WITH_LAYOUT_LIMITATION
