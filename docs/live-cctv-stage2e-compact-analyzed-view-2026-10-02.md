# Stage 2E — Compact Analyzed Frame Inspector

## Previous Layout

Large live views:
2

The monitor displayed two full-width, full-height panels:
1. RAW LIVE PREVIEW (smooth MJPEG video stream).
2. LATEST ANALYZED FRAME (second full-width view showing the analyzed camera frame and SVG overlays).
This created visual duplication and consumed excessive vertical screen area.

## New Layout

Large live views:
1

Analyzed inspector:
COMPACT

Expandable:
YES

The primary monitor view displays ONE large, smooth raw live CCTV preview. The duplicate full-size lower panel is replaced with a compact inspection panel:
- Default thumbnail width: ~280 px (within the recommended 220–320 px range).
- Exact bounding boxes with capitalized class and confidence percentages remain drawn directly on the thumbnail.
- Header displays FRESH / STALE badge, delivery age, vehicle summary (e.g., `Car 92% • Bus 87%`), frame sequence, and capture timestamp.
- Clickable thumbnail and toggle action ("Expand view" / "Collapse view") allow expanding to a larger inspection container when detailed investigation is needed.

## Frame Safety

Exact image/box pair:
PASS

Frame identity remains strictly atomic:
- Analyzed frame N image and detector boxes from frame N are joined in the immutable `LiveBoxPacket`.
- The SVG overlay uses native `viewBox={`0 0 ${width} ${height}`}` with `xMidYMid meet`, scaling synchronously with the thumbnail or expanded view.
- Historical boxes are never projected onto raw live preview video.

## Retention Audit

Configured visual retention:
5000 ms (`VISUAL_RETENTION_LIMIT_MS = 5000`)

Observed previous age:
5.8 s

Verified cause:
Three compounding factors caused the 5.8 s displayed age:
1. **Unbounded ticker in `AnalyzedFrame`**: The child component maintained a 100 ms interval (`setInterval`) that kept incrementing `currentAgeMs`. When `now >= retentionExpiresAt`, `isRetained` only conditioned the SVG `<svg>` element; the header text and the `<img>` element were not unmounted by `AnalyzedFrame`.
2. **Browser timer throttling / parent decoupling**: `SynchronizedAnalysisPreview` had no interval ticker and relied solely on macro-task `setTimeout` to call `setView(null)`. If the main thread or browser throttled the timer by several hundred milliseconds, the child's 100 ms ticker continued running and incrementing the displayed age.
3. **Delivery offset not deducted from retention window**: In `lib/api-client.ts`, `retentionExpiresAt` was initialized as `performance.now() + 5000` (5000 ms from client arrival) rather than subtracting `resultAgeMs` and `transportMs`. If a packet arrived with initial age ~800 ms, 5000 ms of client display caused the total age to reach 5.8 s before timer expiry.

Measured maximum after fix:
<= 5000 ms (bounded to `Math.max(100, 5000 - packet.resultAgeMs) - transportMs`). When `now >= retentionExpiresAt`, `AnalyzedFrame` immediately returns the waiting state and halts rendering.

## Manual Validation

Live preview:
PASS

Duplicate full-size view removed:
PASS

Analyzed thumbnail:
PASS

Boxes:
PASS

Class/confidence:
PASS

Fresh/stale:
PASS

Hard expiry:
PASS

## Tests

Frontend:
- `backend/validation/live_cctv_implementation_stage2e_20261002/stage2e.test.cjs`: 13/13 passed.
- `backend/validation/live_cctv_implementation_stage2d_20261002/stage2d.test.cjs`: 15/15 passed.
- `backend/validation/live_cctv_implementation_stage2_20261001/frontend.test.cjs`: 8/8 passed.
- `frontend-tests/*.test.ts`: 19/19 passed.

Backend:
- 48 focused tests passed (`test_stage1`, `test_stage2`, `test_live_collision_diagnostics`, `test_pair_hit_ledger`), 1 expected pair-safety failure.

TypeScript:
- `npx tsc --noEmit --incremental false`: PASS (0 errors).

## Collision Safety

Detection logic changed:
NO

Tracking changed:
NO

Pair logic changed:
NO

Collision logic changed:
NO

Alarm changed:
NO

## Stage 2E Verdict

STAGE2E_COMPACT_ANALYZED_VIEW_READY
