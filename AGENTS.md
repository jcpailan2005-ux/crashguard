# AGENTS.md

## Project
Car Crash Detection System

## Purpose
This repository is a school-demo traffic monitoring system that uses a Next.js frontend and a FastAPI + YOLO backend to detect vehicles and possible traffic accidents from uploaded media, camera captures, recorded browser video, and continuous live camera frames.

## System Description
The system has two major parts:

1. Frontend
- Next.js 16 App Router
- TypeScript
- Tailwind CSS
- shadcn/ui
- Leaflet for the incident map

2. Backend
- FastAPI
- Uvicorn
- OpenCV
- Ultralytics YOLO
- Local weights at `backend/best.pt`

## High-Level Flow
1. A user uploads an image, captures a photo, records a browser video, or starts live camera detection.
2. The frontend sends media to the FastAPI backend.
3. The backend runs YOLO inference, extracts detections, and optionally saves annotated output to `backend/outputs/`.
4. The backend returns a JSON response containing:
- `success`
- `accident_detected`
- `confidence`
- `media_type`
- `timestamp`
- `location`
- `detections`
- `annotated_media_url`
5. The frontend shows the result in the dashboard UI, preview dialog, notifications list, map, and live history widgets.

## Current Architecture
- `app/` = Next.js pages
- `components/` = UI and feature components
- `lib/api-client.ts` = frontend API wrapper
- `lib/types.ts` = shared frontend response types
- `backend/main.py` = active FastAPI app entrypoint
- `backend/uploads/` = raw uploaded files
- `backend/outputs/` = annotated images/videos
- `backend/best.pt` = YOLO weights

## Confirmed Backend Endpoints
- `GET /api/health`
- `GET /api/incidents`
- `GET /api/notifications`
- `POST /api/detect/image`
- `POST /api/detect/video`

## Response Contract
The frontend is built around this backend shape:

```json
{
  "success": true,
  "accident_detected": true,
  "confidence": 0.91,
  "media_type": "video",
  "timestamp": "2026-04-17T12:30:00Z",
  "location": "Uploaded Video",
  "detections": [
    {
      "label": "vehicle",
      "score": 0.95,
      "box": [100, 120, 220, 260]
    }
  ],
  "annotated_media_url": "http://localhost:8000/outputs/detected_video_001.mp4"
}
```

## What Is Finished
These items are present in the current codebase:

- Landing page exists.
- Main dashboard exists.
- Upload page exists.
- Notifications page exists.
- Live map page exists.
- Settings page exists.
- CCTV samples page exists.
- Frontend API client exists in `lib/api-client.ts`.
- Frontend types exist in `lib/types.ts`.
- Backend health endpoint exists.
- Backend incidents endpoint exists.
- Backend notifications endpoint exists.
- Backend image detection endpoint exists.
- Backend video detection endpoint exists.
- Backend serves `/outputs` as static files.
- Backend loads YOLO from `backend/best.pt`.
- Uploaded images can be processed and annotated output images can be written.
- Uploaded videos can be processed by the backend route.
- Backend stores incidents and notifications in memory.
- End-to-end image detection was verified in the browser UI with the real backend running.
- Upload page accepts both local image and local video files.
- Local video upload works from the Upload page.
- Local videos are sent to `POST /api/detect/video`.
- Backend generates annotated video output for uploaded videos.
- `View Footage` opens the generated annotated video in the browser.
- Browser playback of a real generated annotated video was verified during validation.
- Upload page supports browser camera photo capture.
- Upload page supports browser video recording and sends recorded video to the backend.
- Samples page includes a live camera component for continuous frame detection.
- Live camera view includes timestamp overlay, alert debouncing, and meaningful-history filtering.
- Detection preview dialog exists for annotated images and videos.
- Backend video processing includes codec fallback and frame skipping.

## What Is Partial Or Unfinished
These items are still incomplete, unverified, or mismatched with the intended product:

- If no browser-preview-safe MP4 codec opens on a target machine, video detection still completes but `annotated_media_url` remains `null`, and the UI shows `No annotated footage preview available.` instead of a broken `View Footage` preview.
- Sample gallery media files referenced under `/samples/...` are not present in `public/samples`, so those previews will currently fail unless the files are added.
- The sample gallery "Analyze This Sample" action only redirects to the upload page; it does not send the sample file through the backend.
- Notifications and incidents are in-memory only and reset when the backend restarts.
- Map coordinates are currently fixed placeholder coordinates in backend incident creation, not true source-based locations.
- Live camera detection exists in the frontend, but final end-to-end validation against the real backend still needs confirmation.
- Mobile browser camera behavior still needs real-device validation.
- Production-grade persistent storage is not implemented.
- Stronger retry logic, upload progress, and richer backend failure messaging are still limited.
- There is a duplicate backend file `backend/carc.py`, which can cause confusion about which app is authoritative. Use `backend/main.py`.

## Known Mismatches To Be Honest About
- Some repo documentation claims parts of video processing and live camera are fully verified or production-ready. The codebase still has unverified paths and browser/codec risk, so do not overstate readiness without testing.
- The alert sound path exists, but `public/alert-sound.mp3` is currently a zero-byte file, so sound playback may fail silently or do nothing.

## Practical Error And Failure Modes
This section is not mathematically exhaustive, but it covers the current major errors and likely failure cases in this repo.

### Frontend and Environment Errors
- `NEXT_PUBLIC_BACKEND_URL` points to the wrong backend.
- FastAPI server is not running.
- Frontend cannot reach backend due to network error.
- Browser fetch fails and `detectFromFile()` throws: `Could not reach the backend at ...`
- Backend returns non-200 and frontend surfaces the backend `detail` message.
- `GET /api/incidents` fails and frontend silently falls back to mock incidents.
- `GET /api/notifications` fails and frontend silently falls back to mock notifications.
- `GET /api/health` fails and frontend reports backend status as error.
- CORS is misconfigured if frontend origin does not match `FRONTEND_ORIGINS`.

### Upload Page Errors
- User runs detection with no selected media.
- User selects a file that is neither an image nor a video and gets `Please select an image or video file.`
- Backend returns a detection error and upload page shows the thrown message.
- A video detection can succeed without preview footage if the backend cannot produce a browser-preview-safe MP4, and the upload page shows `No annotated footage preview available.`

### Camera Capture Errors
- Browser does not support camera access.
- User denies camera permission.
- No camera is available on the device.
- Camera is already in use by another app.
- Requested camera constraints are unsupported.
- Camera preview element is not ready when capture is attempted.
- Canvas context cannot be created.
- Capture returns no blob.
- Browser does not support `MediaRecorder`.
- Recording is stopped before it actually starts.
- Recording produces no chunks and therefore no saved video file.
- Live preview fails to autoplay.

### Live Camera Detection Errors
- Live camera starts but backend is unreachable.
- Continuous frame capture runs slower than the configured interval.
- Multiple live requests could overlap if guard logic regresses; current code prevents this with `requestInFlightRef`.
- Alerts may not play because the browser blocks autoplay or because the alert sound file is empty.
- Meaningful detections may be filtered out if scores are below the current threshold.
- History may miss repeated events by design because duplicate entries are throttled.

### Backend Startup Errors
- `backend/best.pt` is missing or corrupt.
- Ultralytics or OpenCV dependencies are missing from the backend environment.
- Backend is launched from the wrong directory and relative resources fail.
- A future agent runs `backend/carc.py` instead of `backend/main.py` and gets a different code path than expected.

### Backend Detection Errors
- Image detection can fail and return `Image detection failed: ...`
- Video detection can fail and return `Video detection failed: ...`
- Uploaded video cannot be opened.
- Uploaded video has invalid dimensions.
- Uploaded video has no readable frames.
- Output folders are missing or unwritable.
- OpenCV `VideoWriter` cannot open any codec.
- Backend completes video detection but returns `annotated_media_url: null` because no writer opened.
- YOLO may return no detections even when the UI expects meaningful output.

### Video Output And Playback Errors
- Codec fallback now tries `avc1`, `H264`, and `mp4v` for `.mp4`, then falls back to `MJPG` in `.avi`.
- If only the AVI fallback works, the backend does not return `annotated_media_url`, so the frontend avoids showing a broken browser preview.
- A generated MP4 preview was verified in-browser on the validation machine, but machines without a working MP4 writer will still miss preview footage.
- The preview dialog can only show browser-playable video formats.
- Long videos may still process slowly on CPU even with frame skipping.

### Data Quality And UX Errors
- Notifications disappear after backend restart because storage is in memory.
- Incident map may show placeholder coordinates instead of true locations.
- Confidence can be `0` for non-accident detections because backend confidence is only raised by label `accident`.
- "No accident detected" does not necessarily mean "no vehicles found"; it only means no `accident` label was flagged.
- Sample gallery cards may show broken media if the sample assets are missing.
- Some pages use mock fallback data, which can hide backend integration problems during demos.

## Priority Tasks For Future Agents
1. Add real sample assets or remove broken `/samples/...` references.
2. Verify end-to-end recorded video upload and live camera flows with the actual backend.
3. Replace in-memory incidents and notifications with persistent storage if history must survive restarts.
4. Decide whether placeholder map coordinates should become real locations or remain demo data.
5. Replace the zero-byte alert sound with a real audio asset.

## Working Rules For Future Agents
- Be honest about what is implemented versus what is only documented.
- Prefer `backend/main.py` as the active backend app.
- Do not move backend code into the frontend root.
- Keep API response fields compatible with the existing frontend types.
- Prefer targeted fixes instead of full rewrites.
- Do not claim video playback is solved unless an actual generated annotated video was tested in the browser.
- Do not add noisy history entries like `No labels`, `0%`, or `Normal` unless explicitly requested.
- Keep the school-demo UX simple and stable.

## Run Commands
### Backend
```powershell
cd C:\Users\wapak\Downloads\CARCRASH\backend
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
uvicorn main:app --reload --port 8000
```

### Frontend
```powershell
cd C:\Users\wapak\Downloads\CARCRASH
npm run dev
```

## Final Note
When documentation and runtime behavior disagree, trust the code and fresh testing over older status reports.
