# Stage 2D — Analyzed Frame Human-Inspection Retention

## Previous Behavior

Freshness bound:
~500 ms after publication.

Visual retention:
~500 ms (coupled directly to the freshness safety bound).

User symptom:
The smooth Bago CCTV live stream played continuously in the upper preview panel, but the separate lower panel ("Latest analyzed frame") frequently flickered and showed:
`Waiting for a fresh analyzed frame. Live video continues above.`
Because the visual presentation was erased as soon as the ~500 ms freshness deadline expired, human operators could not reliably inspect the latest analyzed image, its bounding boxes, or vehicle classifications before it vanished.

## New Behavior

Freshness bound:
500 ms (`FRESHNESS_LIMIT_MS = 500`), preserving the strict temporal detection freshness bound.

Visual retention bound:
5000 ms (`VISUAL_RETENTION_LIMIT_MS = 5000`), allowing bounded 5-second human-inspection retention after publication.

Fresh state:
- Displayed when `now < view.expiresAt` (within the initial ~500 ms window).
- Prominently labeled with a green `FRESH` badge and elapsed delivery age (e.g., `FRESH • 243 ms old`).
- If no vehicle detections exist in the new frame: `FRESH — NO VEHICLES ACCEPTED • 243 ms old`.
- Exact analyzed JPEG frame and exact SVG vehicle boxes rendered atomically.

Stale state:
- Displayed when `now >= view.expiresAt` but `now < view.retentionExpiresAt` (between 500 ms and 5000 ms).
- Clearly labeled with an amber `STALE` badge and real-time updating age (e.g., `STALE • 1.4 s old`, `STALE • 3.8 s old`).
- If no vehicle detections existed in the frame: `STALE — NO VEHICLES ACCEPTED • 1.4 s old`.
- Retains the exact same analyzed image and exact same detector boxes without alteration or interpolation.
- At `now >= view.retentionExpiresAt` (5.0 s), the frame is removed and displays:
  `Waiting for a fresh analyzed frame. Live video continues above.`

## Safety Separation

Fresh detector evidence:
The 500 ms freshness limit (`expiresAt`) remains strictly enforced for all detector evidence, tracking, and backend decision logic.

Stale visualization:
Retained exclusively within frontend React UI state (`SynchronizedAnalysisPreview` and `AnalyzedFrame`). A stale displayed frame is never fed back into inference, never re-transmitted, and exists solely for human visual inspection.

Collision-state effect:
NONE. A stale displayed frame never counts as a new detection, never increments collision hit counters, never refreshes temporal collision states, never creates or extends tracks, never creates pair ownership, never evaluates the classifier, never creates confirmed crashes or incidents, and never triggers an audible or visual alarm.

## Frame Identity

Atomic packet preservation verified:
- Image frame N and bounding boxes from frame N are coupled in an immutable `LiveBoxPacket`.
- Coordinate clipping and scaling map natively to the source frame dimensions (`viewBox="0 0 width height"`).
- No boxes are projected onto raw live preview video.
- No box interpolation or predictive motion across frames.
- When packet N+1 arrives, packet N and its boxes are replaced atomically.

## Empty Detection Behavior

If a new valid analyzed frame arrives with zero accepted vehicle boxes (`boxes.length === 0`):
- The new empty frame immediately replaces any previous vehicle detection frame atomically.
- Old vehicle boxes (e.g., Car, Bus) are immediately discarded.
- UI displays `FRESH — NO VEHICLES ACCEPTED • <age>` while within the freshness bound.
- UI transitions to `STALE — NO VEHICLES ACCEPTED • <age>` after the freshness bound expires.
- The empty frame is removed after the 5000 ms retention period, returning to the waiting state.

## Camera / Session Reset

Visual retention is immediately cleared (`view` set to `null`) when:
- `cameraId` prop changes.
- `eventsUrl` prop changes.
- Stream disconnects, reconnects, or establishes a new session.
- Camera access returns 403 (unauthorized) or 404 (unavailable).
- Component unmounts.
An old analyzed frame from a previous camera or retired session is never shown on a new feed.

## Performance

Extra model calls:
NO

Frame archive:
NO

Unbounded queue:
NO

Extra RTSP load:
NO

Memory footprint is strictly O(1) containing only the single latest analyzed frame and its active bounding box list.

## Manual Validation

Raw preview:
PASS

Analyzed frame visible:
PASS

Boxes:
PASS

Class/confidence:
PASS

Fresh → stale transition:
PASS

Stale → removed transition:
PASS

New frame replacement:
PASS

## Tests

Frontend:
- `backend/validation/live_cctv_implementation_stage2d_20261002/stage2d.test.cjs`: 15/15 passed.
- `backend/validation/live_cctv_implementation_stage2_20261001/frontend.test.cjs`: 8/8 passed.
- `frontend-tests/*.test.ts`: 19/19 passed across incident-alarm, live-monitor, dispatcher-alarm, and backend-fetch.

Backend:
- 48 focused tests passed (`test_stage1`, `test_stage2`, `test_live_collision_diagnostics`, `test_pair_hit_ledger`), 1 expected failure.

TypeScript:
- `npx tsc --noEmit --incremental false`: PASS (0 errors).

## Collision Safety

Detector logic changed:
NO

Tracking changed:
NO

Pair logic changed:
NO

Collision logic changed:
NO

Alarm changed:
NO

Known pair-safety regression:
FAIL as already established (`AssertionError: 'confirmed_crash' == 'confirmed_crash'`).

## Stage 2D Verdict

STAGE2D_ANALYZED_VIEW_READY
