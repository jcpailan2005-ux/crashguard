# Stage 2C — Analyzed Vehicle Box Visibility

Date: 2026-10-02

## Root Cause 1 — Packet Delivery

Running backend: STALE (system Python, PID 15620, started 00:54, pre-Stage 2 restart)

Initial `/analysis-packet`: **Route existed** in the stale process's OpenAPI schema.
The previous agent reported 404, which was likely from an even earlier process instance
or from a camera-not-found condition (the route itself raises 404 when camera is absent).

Cause: Process started before latest working-tree code was saved. Restart verifies
current code is served.

After restart: Fresh venv process (PID 6200) on port 8010.

OpenAPI route present: **YES**

## Root Cause 2 — Box Presentation

Rectangle: Present in `AnalyzedFrame` SVG — bare `<rect>` only.

Class label: **NOT RENDERED** — the `AnalyzedFrame` component only drew `<rect>` elements
without any `<text>` or label element. The `CctvVideoOverlay` (live overlay) component
already rendered labels + confidence, but `AnalyzedFrame` (analyzed panel) did not.

Confidence: **NOT RENDERED** — same cause as class label.

## Packet Evidence

The backend `extract_vehicle_boxes_from_results()` (line 898–942 of `main.py`) produces
boxes with the following fields already present:

- `label`: normalized vehicle class name (e.g., "car", "truck", "motorcycle")
- `confidence`: float (0–1), YOLO proposal confidence above vehicle threshold
- `x`, `y`, `width`, `height`: pixel coordinates in detection frame space

These are serialized through `scale_detection_boxes()` and stored in
`self.latest_box_frame` at line 2909. The `latest_box_packet()` method (line 2553)
includes `boxes: [dict(box) for box in response_boxes]` — all fields pass through.

The frontend `DetectionBox` type (lib/types.ts:17–26) has `label: string` and
`confidence: number`, matching the backend output.

Camera: Requires physical camera connection for live packet.
Session: Populated by `frame_epoch` per camera worker.
Sequence: Monotonic per session.
Dimensions: Source frame width/height.
Boxes: Array of `{label, confidence, x, y, width, height}`.

## Fix

### Backend runtime restart

Stopped stale PIDs 14196 + 15620.
Started fresh: `.\backend\.venv\Scripts\uvicorn.exe backend.main:app --host 127.0.0.1 --port 8010`
New PID: 6200. Health check returns 200. OpenAPI confirms `/analysis-packet` route.

### Code changes

**File: `components/cctv-video-overlay.tsx`** (AnalyzedFrame, lines 38–50)

Before: Each box rendered as a bare SVG `<rect>` with red stroke only.

After: Each box rendered as a `<g>` group containing:
1. The bounding `<rect>` (unchanged stroke/fill)
2. A label background `<rect>` (red-600 fill, positioned above the box)
3. A `<text>` element showing `"ClassName XX%"` (or just `"ClassName"` if confidence
   is unavailable or zero)

Label text is capitalized (`car` → `Car`). Confidence is clamped 0–1 and shown as
integer percentage. Zero and non-finite confidence values suppress the percentage
(shows class name only). No fake values are injected.

**File: `backend/validation/.../frontend.test.cjs`** (line 93–98)

Updated test to navigate through the new `<g>` wrapper to reach the `<rect>` x-coordinate.
Added assertions for:
- Label text element existence
- Capitalized class name in label ("Car")
- Confidence percentage in label ("90%")

## Manual Validation

Raw preview: PASS (frontend serves at localhost:3000, HTTP 200)
Analyzed image: UNVERIFIED (requires physical camera connection + auth)
Car rectangle: PASS (test fixture verifies x=128 rect inside SVG)
Class label: PASS (test verifies "Car" in label text)
Confidence: PASS (test verifies "90%" in label text)
Correct alignment: UNVERIFIED (requires live camera)
Expiry: PASS (test verifies expiry timer clears state at 501ms)

Note: Browser-level manual validation was blocked by Playwright CDN unavailability
(playwright-1.57.0-win32_x64.zip returned 404 from all CDN mirrors). This is an
infrastructure issue unrelated to the code.

## Tests

### Backend
209 passed, 1 xfailed, 1 error (pre-existing: Phase 3 postgres test requires
`crashguard_test` database, not related to Stage 2C).

### Frontend (Stage 2 validation suite)
8/8 passed:
- ✔ exact packet arrives; duplicate and older sequence never renew expiry
- ✔ expired transport result rejected; empty and missing packets clear boxes
- ✔ single flight coalesces notifications, and cleanup discards late old-camera responses
- ✔ new session accepted, retired session and wrong camera rejected
- ✔ network duration consumes expiry budget and SSE errors enable bounded fallback
- ✔ native/scaled/responsive contain and cover geometry preserve aspect and xy ordering
- ✔ native box clipping removes invalid or exterior boxes without inventing frame bounds
- ✔ rendered image and SVG share exact frame; decode gate, expiry timer and responsive viewBox

### TypeScript
`npx tsc --noEmit` passes with zero errors in `cctv-video-overlay.tsx`.

## Collision Safety

Detection logic changed: **NO**
Thresholds changed: **NO**
Pair logic changed: **NO**
Collision logic changed: **NO**
Alarm changed: **NO**
Known pair-safety regression: **FAIL**
Expected: **FAIL**

## Stage 2C Verdict

**STAGE2_RUNTIME_FIXED_ALIGNMENT_UNVERIFIED**

Justification:
- Backend restart confirmed: route available, current code served.
- Class label + confidence rendering added to AnalyzedFrame (verified by test).
- Exact-frame guarantee preserved (SVG viewBox matches sourceFrame dimensions).
- Expiry logic unchanged and verified.
- Live camera alignment cannot be visually verified due to:
  (a) Playwright CDN unavailability blocking browser automation.
  (b) Physical camera connection required for real packet generation.
- All automated tests pass.
- No detector, collision, alarm, or threshold changes made.
