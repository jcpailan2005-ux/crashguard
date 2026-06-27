# Car Crash Detection System: Design and Research Basis

## 1. System Overview

CrashGuard is a school-demo traffic monitoring system for detecting possible road crashes from uploaded images, uploaded videos, browser camera captures, recorded browser video, sample CCTV media, and live camera frames.

The system is intentionally designed as a responder decision-support tool, not as a fully automatic emergency dispatch system. YOLO detection creates a possible crash case, but a responder must review the evidence before confirming a crash, marking a false alarm, dispatching help, or resolving the case.

## 2. Research Basis

The design follows ideas from Automatic Crash Notification (ACN), Advanced Automatic Crash Notification (AACN), and eCall-style emergency systems.

The European eCall model automatically contacts emergency services after a serious crash and sends the vehicle location to responders. eCall documentation also describes a Minimum Set of Data that can include incident time, precise location, vehicle identification, and whether the call was manually or automatically triggered.

AACN research uses the same core safety idea: reduce the delay between a crash and emergency notification by sending useful crash information to responders. AACN material from transportation and emergency medicine sources emphasizes crash location, vehicle information, injury-risk indicators, and faster EMS response or triage.

CrashGuard adapts those ideas for a camera-based school demo:

- Automatic trigger: YOLO flags a possible crash from media or live camera frames.
- Minimum crash data: the case stores time, location, media evidence, confidence score, detection boxes, source/trigger context, and optional user and vehicle details.
- Human review: the responder confirms the crash before dispatch decisions.
- False alarm handling: the responder can mark a case as `false_alarm`.
- Audit trail: every review action is stored in the case timeline.

Useful references:

- European Commission eCall overview: https://transport.ec.europa.eu/transport-themes/smart-mobility/road/its-directive-and-action-plan/interoperable-eu-wide-ecall_en
- European Road Safety Observatory eCall summary and Minimum Set of Data: https://road-safety.transport.ec.europa.eu/european-road-safety-observatory/statistics-and-analysis-archive/esafety/esafety-measures-unknown-safety-effects/ecall_en
- ITE Advanced Automatic Collision Notification white paper: https://www.ite.org/technical-resources/topics/transportation-system-management-and-operations/transportation-safety-advancement-group/products/advanced-automatic-collision-notification-aacn-white-paper/
- NHTSA/ITS Knowledge Resource ACN and AACN summary: https://www.itskrs.its.dot.gov/2021-b01605

## 3. System Architecture

The system has two main parts:

- Frontend: Next.js App Router, TypeScript, Tailwind CSS, shadcn/ui components, and Leaflet map views.
- Backend: FastAPI, OpenCV, Ultralytics YOLO, and local model weights at `backend/best.pt`.

The frontend sends media to the backend detection API. The backend returns a structured detection response with success status, crash flag, confidence, media type, timestamp, location, detections, and optional annotated media URLs.

The frontend then creates or displays responder cases in Firestore. Firebase Auth identifies the logged-in account, and Firestore `users/{uid}` profiles determine whether the user is a normal user, responder, or admin.

## 4. Crash Detection Flow

The intended detection flow is:

1. User uploads media, captures a photo, records browser video, analyzes sample media, or starts live camera detection.
2. Frontend sends the media to the FastAPI backend.
3. Backend runs YOLO inference.
4. Backend filters detections to road vehicles and crash-related labels.
5. Backend returns the detection result and optional annotated media.
6. If `accident_detected` is true, the frontend creates a Firestore crash case with status `pending_review`.
7. The system creates a notification for responders.
8. The responder reviews the evidence and decides what action to take.

This avoids treating the model output as a final emergency decision.

## 5. Responder Workflow

The responder workflow is:

Crash detected  
-> Create `pending_review` case  
-> Notify responder  
-> Responder reviews photo/video, location, and confidence score  
-> Responder starts review  
-> Responder confirms crash or marks false alarm  
-> Responder contacts user or emergency contact  
-> Responder dispatches help if needed  
-> Responder adds notes  
-> Responder resolves the case

The dashboard supports this through the responder queue, active case list, notifications page, map page, and incident review dialog.

## 6. Case Lifecycle

The case lifecycle is:

`pending_review -> under_review -> confirmed_crash / false_alarm -> dispatched -> resolved`

Meaning of each status:

- `pending_review`: YOLO or a live camera workflow created a possible crash case.
- `under_review`: a responder has started reviewing the alert.
- `confirmed_crash`: the responder judged the evidence as a likely real crash.
- `false_alarm`: the responder judged the alert as not a crash.
- `dispatched`: help or follow-up action has been dispatched for a confirmed crash.
- `resolved`: the case is closed after dispatch follow-up or false alarm review.

The action model is:

- `review_alert`: `pending_review` to `under_review`
- `confirm_crash`: `under_review` to `confirmed_crash`
- `mark_false_alarm`: `under_review` to `false_alarm`
- `dispatch_help`: `confirmed_crash` to `dispatched`
- `contact_user`: records contact activity without changing the main status
- `add_notes`: records responder notes without changing the main status
- `resolve_case`: `dispatched` or `false_alarm` to `resolved`

## 7. Data Model

### Detection Response

The backend returns:

- `success`
- `accident_detected`
- `confidence`
- `media_type`
- `timestamp`
- `location`
- `detections`
- `annotated_media_url`
- optional annotated preview/download/key-frame fields

### Firestore Case

Crash cases are stored under `incidents/{caseId}` with fields such as:

- `caseId`
- `detectionId`
- `status`
- `reviewerId`
- `areaId`
- `location`
- `media`
- `confidence`
- `accidentDetected`
- `triggerStatus`
- `detections`
- `user`
- `vehicle`
- `notes`
- `actions`
- `detectedAt`
- `acknowledgedAt`
- `confirmedAt`
- `falseAlarmAt`
- `dispatchedAt`
- `resolvedAt`
- `createdAt`
- `updatedAt`

The `triggerStatus` field explains how the possible crash entered the workflow. Supported demo values are:

- `camera_detection`
- `upload_detection`
- `sample_detection`
- `manual_report`
- `unknown`

Lifecycle timestamps support response-time metrics. `detectedAt` records when the system created the possible crash case, `acknowledgedAt` is set when a responder starts review, `confirmedAt` or `falseAlarmAt` records the review decision, `dispatchedAt` records dispatch action, and `resolvedAt` closes the case.

### Firestore User Profile

User profiles are stored under `users/{uid}`:

- `uid`
- `email`
- `displayName`
- `role`
- `active`
- `areaId`
- `createdAt`
- `updatedAt`

Supported roles:

- `user`: can log in and use non-dashboard pages.
- `responder`: can review cases for an assigned area.
- `admin`: can review cases across all areas.

## 8. UI/UX Design Principles

The UI should be emergency-focused and easy to scan:

- Put pending and active cases first.
- Show status, time, location, confidence, and media evidence clearly.
- Use clear action labels: Start Review, Confirm Crash, False Alarm, Dispatch Help, Contact User, Add Notes, Resolve Case.
- Show only valid actions for the current case state.
- Keep responder notes and action history visible in the review dialog.
- Avoid automatic dispatch from model output alone.
- Prefer concise status badges and tables over decorative screens.
- Separate admin monitoring from responder action workflows.

The incident review dialog should support:

- Case ID
- Time and date
- Location and map-opening action
- Photo/video evidence
- Confidence score
- User details
- Vehicle details
- Current status
- Responder notes
- Action history
- Valid action buttons only

### Admin and Responder UI Design

CrashGuard separates the two main operational views because admin users and responders make different decisions.

Responder UI is built for fast emergency action. It should show the right information at the right time in a compact format:

- Pending review, under-review, confirmed, dispatched, false alarm, and resolved counts.
- Case ID, time, location, confidence score, media availability, current status, and quick action buttons in the responder queue.
- Photo/video evidence, map action, location, date/time, confidence score, user details, vehicle details, status, notes, and action history in the review dialog.
- Only actions valid for the current case state.

Admin UI is built for management and monitoring:

- Total cases, active cases, unresolved cases, false alarm count, and responder activity.
- Cases by area and audit/action history.
- Detection quality metrics, including detection review rate and false alarm rate.
- Future account and area assignment management when production storage/admin screens are added.

Research-based UI principles used in this design:

- Show location, time, media, vehicle/user details, and trigger context close to the decision.
- Do not auto-confirm crash detections from model output alone.
- Use responder review to reduce false alarms.
- Separate admin monitoring from responder action workflow.
- Track detection rate, false alarm rate, mean time to detect, mean time to acknowledge, and mean time to resolve.
- Use lifecycle timestamps to calculate mean time to acknowledge, dispatch, and resolve; show that there is not enough data when timestamps are missing.

## 9. Safety and False Alarm Handling

Crash detection models can produce false positives from unusual road scenes, occlusions, damaged vehicles, reflections, or poor camera angles. For that reason, CrashGuard uses responder review as a safety layer.

Important safety behaviors:

- Every automatic crash result starts as `pending_review`, not confirmed.
- Responders can mark false alarms.
- Responder notes explain why a decision was made.
- Action history records who changed the case and when.
- Confidence score is shown as decision support, not as proof.
- Missing media preview should not block review if downloadable evidence or case data is still available.

## 10. Testing Metrics

The system should be evaluated with both technical and workflow metrics.

Detection quality metrics:

- Detection rate: percentage of known crash samples detected as crashes.
- False alarm rate: percentage of normal traffic samples incorrectly flagged as crashes.
- Precision: percentage of detected crash alerts that are true crashes after review.
- Recall: percentage of true crash samples that are detected.
- Mean time to detect: average time from media submission or frame capture to backend response.
- Mean time to review: average time from `pending_review` to `under_review`.
- Mean time to dispatch decision: average time from `pending_review` to `dispatched` or `false_alarm`.

Workflow metrics:

- Number of pending cases.
- Number of confirmed crashes.
- Number of false alarms.
- Number of dispatched cases.
- Number of resolved cases.
- Cases missing location, media, user, or vehicle details.

## 11. Remaining Limitations

Current known limitations:

- This is a school-demo system, not a certified emergency service.
- It does not integrate with real PSAP, 911, 112, eCall, EMS, or dispatch systems.
- Location data may use placeholder or area-based fallback coordinates.
- User and vehicle details are optional and may be missing.
- Firestore data is suitable for QA/demo use, not production incident records.
- Detection quality depends on model weights, camera angle, media quality, lighting, and codec support.
- Video preview can be unavailable if the machine cannot write browser-preview-safe MP4 output.
- The current trigger context is inferred from media source and `accidentDetected`; a production system should use an explicit trigger status field.

## Design Summary

CrashGuard follows the main safety pattern of crash notification research: detect quickly, send useful crash data, notify responders, and support rapid human decision-making. The system should remain simple: detection creates a review case, responders decide, and the action history preserves the reasoning behind each case outcome.

## 12. Map-Based Evidence Review Flow

The detection popup is only an entry point. It gives the responder a quick signal that a possible crash was detected, with the key frame, confidence score, and detection time. It does not ask the responder to confirm, dispatch, contact users, or resolve a case inside the popup.

The responder decision happens on the interactive map. Opening the map with a case ID shows the crash location, confidence score, time detected, key frame or media evidence, and camera/source context in one focused review panel. This supports situational awareness by keeping location, time, media evidence, and source context together.

The map review panel supports two primary decisions while the case is awaiting review:

- Legit Crash: moves a pending case through review and confirms it as `confirmed_crash`.
- False Alarm: moves a pending case through review and marks it as `false_alarm`.

Both decisions create action history entries and timestamps. Dispatch actions stay out of the map review panel until a crash is confirmed, reducing the chance of treating an unreviewed detection as a verified emergency.

## 13. Local SQLite Database and Media Storage

The local demo system stores structured crash data in `data/crashguard.sqlite`. This includes crash case status, confidence score, detection time, location, trigger status, responder decisions, notifications, camera records, analytics summaries, and action history.

Media files are stored outside the database under `uploads/crash-media/{caseId}/`. The database stores only paths such as `original.mp4`, `keyframe.jpg`, `thumbnail.jpg`, and `annotated.mp4`. This keeps the database small and makes media easier to inspect or replace during local QA.

Firebase Auth remains responsible for login and role access. SQLite is used for local crash records, responder queue data, notifications, and analytics. This is appropriate for a school-demo environment, but production emergency systems would need durable storage, backups, access controls, audit retention, and formal dispatch integrations.

## 14. Authorized IP Camera / Live Camera Review

Responder testing can come from uploaded media, browser camera capture, or authorized IP camera/live camera feeds. The IP camera flow is designed for situational awareness: responders enter the authorized camera IP address, and the backend builds the internal RTSP stream URL from that IP plus the locally configured camera account. For Tapo cameras, the IP address alone is not a video stream; RTSP access must be enabled in the Tapo app and a camera username, password, stream type (`stream1` or `stream2`), and RTSP port must be configured by an admin.

The system does not scan networks, bypass camera passwords, or hard-code real camera credentials. Local testing should use authorized private/local camera IP addresses and credentials stored in environment variables or `backend/local_camera_config.json`, which is ignored by git.

Camera detections create `pending_review` cases with `triggerStatus = camera_detection`, `sourceCamera`, `cameraIp`, `detectedAt`, confidence, and area/location metadata where available. They are not automatically confirmed. The responder reviews the evidence on the map and then chooses Legit Crash or False Alarm.

After an authorized camera connection succeeds, live monitoring starts automatically. The responder does not manually start or stop detection from the main page. The system checks frames at a safe interval, creates only `pending_review` alerts, and uses duplicate prevention so an unresolved alert from the same camera is reused instead of creating a new crash case every frame. If the camera connection drops, the UI shows connection-lost/reconnecting states while the system retries safely against the same manually entered camera IP.

For smoother real-time monitoring, the live preview and AI detection run as separate loops. A camera capture worker reads from the RTSP stream continuously and keeps only the latest frame, dropping old frames to avoid buffer lag. The preview uses that latest available frame and does not wait for YOLO inference. A detection worker samples the latest frame at a configured interval, resizes it for faster inference, applies a confidence threshold, requires repeated hits before alerting, and respects per-camera cooldown/active-case checks. This reduces lag, avoids unstable one-frame alerts, and keeps the responder UI responsive.

Local tuning values include `LIVE_CAMERA_DETECTION_INTERVAL_MS`, `LIVE_CAMERA_CONFIDENCE_THRESHOLD`, `LIVE_CAMERA_ALERT_COOLDOWN_SECONDS`, `LIVE_CAMERA_FRAME_WIDTH`, `LIVE_CAMERA_FRAME_HEIGHT`, `LIVE_CAMERA_REQUIRED_HITS`, and `LIVE_CAMERA_BUFFER_SIZE`. During local testing, the defaults are intentionally permissive (`1000 ms`, `0.30` confidence, `1` required hit, `30 s` cooldown) so teams can verify that the live detection worker is receiving frames and creating pending-review alerts before tightening thresholds. Live frames use the same OpenCV/BGR image path used by upload detection, then resize for faster inference. For Tapo cameras, `stream2` may be preferred when Wi-Fi or CPU resources make `stream1` too heavy. Wi-Fi strength, camera bitrate, and local CPU performance still affect preview smoothness and detection latency.

Crash confidence and vehicle box drawing are separate. The crash detector decides whether the frame should create a possible-crash review case. A vehicle object detector identifies car, motorcycle, bus, and truck boxes for responder context. The UI draws boxes only when the detector returns real coordinates; it does not invent boxes when a model returns only classification confidence.

## 15. Multi-CCTV Monitoring Design

The CCTV monitoring workflow now treats cameras as managed records instead of one manually typed stream. A barangay or area can contain many CCTV cameras, each with a stable `cameraId`, camera name, area/barangay, road name, location description, coordinates, stream metadata, online/offline status, active flag, and detection-enabled flag.

Responders should monitor only cameras assigned to their area or explicitly assigned camera list. Admin users can manage all cameras, including enabling/disabling cameras and editing camera metadata. Backend camera APIs enforce this role scope with Firebase ID tokens; frontend role hiding is not the only protection.

Frontend routes should use `cameraId` instead of raw camera IP addresses wherever possible. The backend can still keep the camera IP or RTSP URL internally so it can connect to OpenCV/FFmpeg, but responders should interact with safe camera records such as `CAM-TALOMO-CROSSING`.

When a live camera detection creates a case, the case stores the camera ID, camera name, area/barangay, road name, coordinates, timestamp, confidence, source frame, and `pending_review` status. Notifications and responder queues should clearly say which camera and road produced the possible crash alert, for example: "Possible crash detected from Talomo Crossing CCTV, Talomo, McArthur Highway."

The monitoring UI supports both single-camera review and grid browsing. The single view focuses on the selected camera preview, status, detection confidence, coordinates, and latest event. The grid view gives responders a fast overview of assigned cameras without forcing every camera into a heavy live preview at once.
