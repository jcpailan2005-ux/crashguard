# Crash Case Workflow Test Cases

## Case Lifecycle

1. Positive detection creates pending review
- Run image, video, sample, or live-camera detection with `accident_detected: true`.
- Expected: Firestore `incidents/{caseId}` is created with `status: pending_review`.
- Expected: `actions[0].action` is `review_alert`.
- Expected: notification title is `Possible Crash Pending Review`.

2. Responder confirms crash
- Open a pending case and choose `Review Alert`.
- Expected: status changes to `under_review`.
- Expected: action log records actor ID, previous status, next status, and timestamp.
- Choose `Confirm Crash`.
- Expected: status changes to `confirmed_crash`.
- Expected: action log records actor ID, previous status, next status, and timestamp.

3. Responder marks false alarm
- Open a pending case and choose `Mark as False Alarm`.
- Expected: status changes to `false_alarm`.
- Expected: case is removed from active map markers.

4. Dispatch records notes and responder ID
- Add action notes, then choose `Dispatch Help`.
- Expected: status changes to `dispatched`.
- Expected: action log includes responder UID and dispatch notes.

5. Resolve requires notes
- Try `Resolve Case` with an empty notes field.
- Expected: UI shows an error and status does not change.
- Add a resolution note and retry.
- Expected: status changes to `resolved` and notes are appended.

## Data Consistency

6. One incident store
- Create cases from upload, camera capture, sample analysis, and live camera.
- Expected: all operational cases are written to Firestore `incidents`.
- Expected: dashboard, notifications, and map read the same case IDs.
- Expected: backend `/api/incidents` is not required for responder workflow.

7. Missing Firebase config
- Remove `NEXT_PUBLIC_FIREBASE_*` values and load dashboard, notifications, map, and samples.
- Expected: pages show a readable Firebase configuration error.
- Expected: app does not crash from `db` being null.

8. Map coordinates
- Create a case with area coordinates.
- Expected: marker appears at the configured area coordinate.
- Create a case without area.
- Expected: marker uses fallback coordinates and the UI labels them as fallback.

## UI And Theme

9. Light and dark readability
- Toggle light and dark mode.
- Expected: dashboard, cards, badges, buttons, map list, dialogs, forms, and errors remain readable.
- Expected: layout, spacing, icons, and button placement do not change between modes.

10. Detection quality metrics
- For a labeled validation set, record detection rate, false alarm rate, and mean time to detect.
- Expected: reports include all three metrics before claiming model quality.
