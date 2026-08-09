# Multi-CCTV QA Checklist

This checklist is for local school-demo validation of the CCTV monitoring phase.

- Admin can open `/dashboard/ip-camera` and see live camera feeds.
- Responder can open `/dashboard/ip-camera` and see only assigned area/camera records.
- Normal user cannot access dashboard camera pages.
- Missing or invalid Firebase token returns `401` from protected camera APIs.
- Unauthorized camera access returns `403`.
- Missing camera ID returns `404`.
- Camera records can be selected by stable `cameraId`.
- Frontend preview/status calls use `cameraId` routes where possible.
- Grid view loads multiple assigned cameras without horizontal overflow.
- Single camera view shows preview placeholder when monitoring is off.
- Offline camera state appears clearly.
- Detection disabled state appears clearly.
- Crash alert stores and shows exact camera, barangay, road, timestamp, and confidence.
- Notifications link to the correct crash case.
- Responder queue shows the correct camera source.
- Map review uses camera coordinates when available.

Remaining local-demo note: real CCTV validation still depends on authorized camera credentials, RTSP access, camera network quality, and local CPU/GPU performance.
