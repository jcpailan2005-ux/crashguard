# Inference and bounding-box delivery audit

## Finding

The object detector loads and runs. The initial fresh Bago frame showed a wall
and cables, so zero vehicle boxes were correct for that input. After the user
restored ordinary traffic, the existing live worker reported **10 accepted
vehicle boxes**, while **all 30 analysis-packet HTTP reads over 12 seconds
returned null**. Those requests succeeded without HTTP errors; transport median
was 133 ms and maximum 1000 ms.

The packet endpoint discarded its exact image/boxes after only **500 ms**,
including a second expiration check after JPEG encoding. The frontend also
rejected delivery outside that window. Model work, other analysis stages,
encoding and transport can exceed that interval. The backend could therefore
detect vehicles while the display received no boxes. Successful SSE delivery
also disabled fallback polling even when the subsequent packet read missed its
deadline.

## Model and dependency check

The installed backend environment has Ultralytics 8.4.38, PyTorch 2.11.0,
Torchvision 0.26.0, NumPy 2.4.4 and OpenCV 4.13.0.92. The primary detector
`backend/best.pt` loads with task `detect` and 80 classes. The local
`yolov8n.pt` is byte-identical, so its primary results are reused. The separate
`backend/models/crash_classifier.pt` loads with task `classify`; neither loader
reported an error.
The same virtual environment's `pip check` reports **No broken requirements found**.

Two bounded detector checks used one primary inference call per image, with no
duplicate vehicle inference:

- Current wall/cables probe: zero raw detections and zero accepted vehicles.
- Previously verified Bago normal-traffic control: nine raw detections (seven
  cars, one truck, one traffic light), with **six accepted vehicle boxes** at the
  unchanged 0.40 vehicle threshold. This was a historical control, not the fresh
  traffic validation.

The fresh ordinary-traffic probe was visually inspected before the live reload.
No collision recording or protected source was opened. All model and packet
diagnostic evidence is local under
`backend/validation/inference_box_delivery_20261012/`.

## Correction

`LiveCameraMonitor.latest_box_packet` now retains an exact analyzed image and its
boxes for **up to five seconds for delivery**. `validForMs` still expires at
500 ms; the additive `retentionForMs` provides the separate delivery deadline.
The frontend accepts explicitly retained packets as **stale**, preserves exact
image/box pairing and still rejects expired delivery, wrong cameras, duplicate
sequences and retired sessions. Older packets lacking the explicit retention
field retain the original freshness rules.

Failed, null and rejected packet reads restore bounded polling instead of
assuming that an open SSE connection delivered usable boxes. No detector weights,
confidence thresholds, ROI rules, tracker association logic, inference scheduler,
collision criteria, ledger, alarms or SQLite schema were changed by this audit.
Retention is display-only and creates no new DETECTED observation or crash proof.

The user still reported missing boxes in the expanded/single-camera view after
the initial restart. The served frontend was checked: it contained the new
retention/rendering code and used backend port 8010. The single-camera subscription
used a signed event URL, but the subsequent packet fetch omitted that existing
ticket. Packet reads now carry the matching scoped ticket, with strict backend
origin and camera-path checks so tickets cannot be forwarded elsewhere. Cookie
authentication remains supported. The single view now displays packet/access/
image errors and a detected-object count instead of silently falling back to raw
video. After refreshing the expanded Bago view, the user confirmed:
**Bounding boxes are visible**.

The backend was restarted with the approved Bago monitor restored. A temporary
local launcher reads the actual worker packets for 25 seconds; it adds no model
calls. Access-request URLs are not logged by that launcher because preview query
strings contain short-lived credentials. The initial combined restart command
was rejected by automatic approval review; separate preparation and a verified,
single-listener restart succeeded.

## Verification and limits

- Running worker after reload: **119 samples, 105 packets, 104 with vehicle
  boxes**, maximum **10 boxes**. Three positive packets had expired freshness
  but remained explicitly deliverable. The first successful source image and
  its annotated boxes were saved and visually inspected.
- These before/after windows are not identical scene or load replays. Only Bago
  was explicitly restored by the launcher; the delivery-window regression tests
  establish the delayed-packet behavior independently of throughput changes.
- Focused backend regressions: **100 passed, 0 failed, 1 preserved pair-safety
  XFAIL** (101 tests). Packet tests cover fresh/retained/expired delivery, exact
  pixels and metadata, and reconnect isolation.
- Frontend: **61 passed, 0 failed**, including scoped-ticket propagation and
  rejection of tickets from another origin or camera. TypeScript check passed.
- Backend health returns HTTP 200. The running backend continues to use SQLite.
- Tracker, pair ledger and known pair-safety XFAIL remain unchanged. Nothing
  staged, committed or pushed.

The old preview ticket became invalid on the backend restart, so a subsequent
command-line HTTP check was not authenticated. It is not counted as an inference
or delivery failure after the fix. The post-reload figures above come from the
real running worker. Refreshing the browser obtains a current preview ticket;
normal authenticated packet polling also supplies the exact-frame view.

Automated live browser inspection was unavailable through the UI control tools.
The user manually confirmed visible boxes in the expanded Bago view after the
scoped-ticket fix. Object inference, exact-frame delivery and that display path
are verified; a fresh positive FOBOS scene was not validated in this task.
collision-classifier accuracy is not established by this check. In particular,
the classifier produced high accident probabilities on ordinary traffic in the
existing live logs. That is a model-quality/calibration concern, not evidence of
a missing dependency; temporal confirmation safeguards remain in place.
