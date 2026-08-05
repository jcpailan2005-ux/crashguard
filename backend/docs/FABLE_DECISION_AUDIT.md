# FABLE Decision Audit — MyCrushguard Crash Detection

This document records the strict crash-decision pipeline that gates every
crash case, notification, responder queue item, and map review item, the
false-alarm paths that were blocked, and the dataset/model work that remains.

## 1. Current strict decision pipeline

All persistence funnels through a single function,
`create_crash_case` (`backend/repositories/crash_cases.py`), which inserts the
crash case and its notification atomically. The responder queue, map review,
and notification bell are read-only views over `crash_cases` / `notifications`
— they have no independent creation path. Every detection path must first pass
`evaluate_crash_case_decision` (`backend/main.py`), which checks, in order:

| # | Gate | Rejection reason | Final decision |
|---|------|------------------|----------------|
| 1 | `vehicleCount >= 1` | `no_vehicle_detected` / `person_only_not_crash` | `ignored` |
| 2 | `sceneValid == true` (vehicle inside `CRASH_ROI_NORMALIZED`) | `vehicle_outside_roi` | `ignored` |
| 3 | classifier class is `accident` | `non_accident` | `ignored` |
| 4 | `crashScore >= CRASH_CASE_THRESHOLD` (default 0.90) | `below_case_threshold` | `ignored` |
| 5 | `motionValid == true` (crash-like vehicle proximity/overlap) | `motion_not_crash_like` | `ignored` |
| 6 | `consecutivePositiveFrames >= CRASH_REQUIRED_CONSECUTIVE_FRAMES` (default 3) | `temporal_not_confirmed` | `waiting` |
| 7 | no `pending_review` / `under_review` case for the same camera | `active_case_exists` | `duplicate_active_case` |
| 8 | cooldown elapsed (`CRASH_ALERT_COOLDOWN_SECONDS`, default 60) | `cooldown_active` | `duplicate_cooldown` |
| ✓ | all gates pass | — | `confirmed_crash` |

**Only `finalDecision == confirmed_crash` may create a case or notification.**
Resolved, false-alarm, dispatched, and confirmed cases do NOT block future
valid crashes — only `pending_review` and `under_review` do.

Detection paths wired through this gate:

- **Live RTSP monitor** (`LiveCameraMonitor.analyze_current_frame`) — keeps its
  temporal window and cooldown on the worker thread.
- **Device-camera loop / stream frame** (`/api/detect/image` with
  `triggerStatus=camera_detection`, `/api/detect/stream-frame`) — stateless
  HTTP requests, so consecutive-frame and cooldown state is held server-side in
  `CameraDecisionTracker`, keyed per camera.
- **Video uploads** (`/api/detect/video`) — per-frame vehicle/ROI/motion
  signals plus a consecutive-positive-frame streak across analyzed frames.
- **Manual image uploads** (`upload_detection`) — explicit one-shot user
  submissions: temporal confirmation and cooldown do not apply, but every
  frame-quality gate (1–5) does.

Every decision emits a structured log line:

```
[decision] cameraId=… vehicleCount=… personCount=… sceneValid=… motionValid=…
crashScore=… consecutivePositiveFrames=… activeCaseExists=… cooldownPassed=…
finalDecision=… rejectionReason=… caseCreated=… notificationCreated=…
```

Configuration (see `.env.example`): `CRASH_UI_THRESHOLD=0.80`,
`CRASH_CASE_THRESHOLD=0.90`, `CRASH_REQUIRED_CONSECUTIVE_FRAMES=3`,
`CRASH_ALERT_COOLDOWN_SECONDS=60`, `CRASH_ROI_NORMALIZED=x1,y1,x2,y2`.

## 2. False-alarm paths blocked

- **Person-only frames** — a high classifier score alone can no longer create
  anything: with zero vehicle boxes the decision is rejected as
  `person_only_not_crash` (or `no_vehicle_detected` when nobody is in frame).
- **Single-frame spikes** — the device-camera loop previously created a case
  from one frame; it now requires 3 consecutive crash-positive frames tracked
  server-side, plus a 60s cooldown after each created case.
- **Video uploads** — previously gated only on accident class + threshold; now
  require in-ROI vehicles with crash-like interaction confirmed across
  consecutive analyzed frames. The legacy in-memory notification fires only
  when a case was actually created.
- **Parked vehicles / normal traffic** — rejected by the motion gate
  (`motion_not_crash_like`): side-by-side vehicles with low IoU do not count as
  crash-like interaction.
- **Out-of-ROI activity** (sidewalks, porches) — rejected as
  `vehicle_outside_roi` when `CRASH_ROI_NORMALIZED` is configured.
- **Duplicates** — an active `pending_review`/`under_review` case for the same
  camera blocks re-creation; the cooldown blocks rapid-fire re-alerts.
- **Debug endpoint** — `/api/debug/create-camera-alert` creates cases
  unconditionally and is now disabled unless `ENABLE_DEBUG_CAMERA_ALERT=true`.
- **Skipped frames create nothing**: no case, no notification, no responder
  queue item, no map review item, and the frontend only raises the
  "Possible Crash Detected" alert when the backend reports `case_created`.

Regression coverage: `backend/tests/test_crash_decision.py` (21 tests) covers
all gates, the tracker, ROI filtering, and repository-level active-case
blocking. Offline validation: `backend/scripts/replay_crash_decision.py`
replays image folders through the identical pipeline without persisting
anything and exports a CSV of every decision.

## 3. Known remaining limitation

**Single-vehicle crashes may be missed.** The motion gate
(`crash_like_vehicle_interaction`) requires at least two vehicle boxes with
strong proximity/overlap, so a vehicle hitting a post/wall, a rollover, or a
lone post-impact stopped vehicle cannot pass gate 5 on any path. This is a
deliberate precision-over-recall trade-off until the model can carry more of
the burden. Additional model limitations:

- The crash classifier (`yolov8n-cls`) still *scores* some person-only and
  indoor frames as `accident`; the gates contain this, but the model needs
  hard negatives (see below).
- Vehicle boxes come from COCO `yolov8n.pt` at 0.40 confidence and can
  hallucinate under night/glare/rain; the temporal + motion gates make this
  hard to convert into a case, but a road-scene detector would reduce noise.
- "Motion" is per-frame geometry (proximity/overlap), not true motion
  analysis (no optical flow or tracking yet).

## 4. Dataset improvement plan

1. Collect the hard-negative and positive categories below into the replay
   layout (`dataset/<category>/frame_0001.jpg …`).
2. Run `python backend/scripts/replay_crash_decision.py dataset --strict` and
   record the CSV as the pre-training baseline.
3. Retrain `train_crash_classifier.py` with the expanded set; keep hard
   negatives at roughly 50–60% of training data, since normal footage
   dominates production.
4. Evaluate on a held-out negative suite: target ~0 frames scored `accident`
   ≥ 0.90 across all hard-negative categories, without dropping recall on the
   positive suite.
5. Re-run the replay tool with `--strict` as the acceptance gate; wire it into
   CI so classifier regressions fail the build.
6. Longer term: teach the *detector* an explicit `accident` class (or add
   tracking/optical flow) so single-vehicle crashes stop depending on the
   two-box interaction heuristic, then relax gate 5 for detector-confirmed
   single-vehicle events.
7. Per production camera, configure `CRASH_ROI_NORMALIZED` so sidewalks and
   porches are excluded outright.

## 5. Recommended hard-negative categories (label `non_accident`)

- person only (near and far from the camera)
- no vehicle at all
- normal CCTV activity
- indoor / porch CCTV
- people near/approaching the camera
- empty road
- normal flowing traffic
- parked vehicles, including side-by-side ("mag tabi") queues
- night / glare / rain / sensor-noise variants of each of the above
- non-road backgrounds

## 6. Recommended positive crash categories (label `accident`)

- real CCTV crash clips (not dashcam-only footage)
- motorcycle crashes
- car-to-car crashes
- multi-vehicle crashes
- single-vehicle crashes (loss of control, rollover)
- vehicle hitting a fixed object (post, wall, barrier)
- post-impact stopped vehicle scenes

For each positive clip, sample 3–5 frames around the impact so the 3-frame
temporal gate sees consistent positives at inference time.
