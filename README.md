# Car Crash Detection System

CrashGuard is a school-demo emergency support system for detecting possible car crashes from uploaded media, browser camera capture, recorded video, sample CCTV media, and live camera frames.

The system uses a Next.js frontend, Firebase Auth for login/role access, local SQLite for crash cases and analytics, local file storage for crash media, and a FastAPI + YOLO backend for crash detection. It is designed to support responder review and decision-making. It is not a certified 911, 112, eCall, EMS, or emergency dispatch system.

## Features

- Image and video upload detection
- Browser camera photo capture
- Browser video recording
- Live camera frame detection
- Annotated image/video preview when backend output is browser-playable
- Responder dashboard with crash case queue
- Local SQLite responder queue and analytics
- Multi-CCTV monitoring grouped by camera area/barangay and road
- Authorized IP camera/live camera connection for responder testing
- Admin camera management for local CCTV records
- Incident map with case locations
- Notifications for possible crash alerts
- Case review dialog with media, location, confidence, notes, and action history
- Firebase Auth roles for normal users, responders, and admins
- Firebase emulator QA seeding for local test accounts and crash cases
- Dark and light theme support

## Local Database and Media Storage

CrashGuard stores local demo records in `data/crashguard.sqlite`. Uploaded videos, key frames, thumbnails, and annotated media are stored as files under `uploads/crash-media/{caseId}/`; SQLite stores only file paths, not raw media blobs.

This local storage layer is for school-demo and QA use. It is not a production incident records system.

## IP Camera Testing

Responders use the CCTV Monitoring page to select assigned camera records. The page supports camera search, barangay/area filtering, road filtering, status filtering, single-camera monitoring, and grid browsing. For compatibility, the page still includes a compact manual IP camera test panel.

Admin users can manage local camera records at `/dashboard/cameras`. Camera records include name, area/barangay, road name, location description, IP address or stream URL, coordinates, active/inactive state, and detection enabled/disabled state.

For Tapo cameras, the IP address alone is not a video stream: an admin must configure the local camera account, password, stream type (`stream1` or `stream2`), and RTSP port in Admin Camera Settings or local environment variables.

The FastAPI backend builds the internal RTSP URL and connects with OpenCV/FFmpeg. The browser does not play RTSP directly, and real camera credentials must not be committed to git. The local file `backend/local_camera_config.json` is ignored for this school-demo workflow.

Protected camera APIs verify Firebase ID tokens. Admin users can access all cameras. Responder users can access cameras assigned to their area or assignment list. Frontend camera routes use stable `cameraId` values where possible instead of raw camera IP addresses.

## Research and Design

The system design is documented in [SYSTEM_DESIGN_AND_RESEARCH.md](SYSTEM_DESIGN_AND_RESEARCH.md).

That document explains the research basis for the workflow, including eCall-style automatic crash notification, important crash data, responder review, false alarm handling, dispatch decision support, crash report history, action logs, and testing metrics.

## Workflow

The intended responder workflow is:

```text
Crash detected
-> Create pending_review case
-> Notify responder
-> Responder reviews photo/video, location, and confidence score
-> Responder starts review
-> Responder confirms crash or marks false alarm
-> Responder contacts user or emergency contact
-> Responder dispatches help if needed
-> Responder adds notes
-> Responder resolves the case
```

## Case Lifecycle

Crash cases follow this lifecycle:

```text
pending_review -> under_review -> confirmed_crash / false_alarm -> dispatched -> resolved
```

Case actions:

- `review_alert`: moves `pending_review` to `under_review`
- `confirm_crash`: moves `under_review` to `confirmed_crash`
- `mark_false_alarm`: moves `under_review` to `false_alarm`
- `dispatch_help`: moves `confirmed_crash` to `dispatched`
- `contact_user`: records contact activity without changing the main status
- `add_notes`: records responder notes without changing the main status
- `resolve_case`: moves `dispatched` or `false_alarm` to `resolved`

## Role Access

Firebase Auth identifies the signed-in account. Firestore `users/{uid}` profiles define access.

Supported roles:

- `user`: can log in and use non-dashboard pages such as samples.
- `responder`: can access protected dashboard pages for the assigned `areaId`.
- `admin`: can access protected dashboard pages across all areas.

Expected user profile fields:

```json
{
  "uid": "firebase-auth-uid",
  "email": "person@example.com",
  "displayName": "Responder Name",
  "role": "responder",
  "active": true,
  "areaId": "talomo",
  "createdAt": "2026-06-19T00:00:00.000Z",
  "updatedAt": "2026-06-19T00:00:00.000Z"
}
```

## Tech Stack

### Frontend

- Next.js 16 App Router
- TypeScript
- Tailwind CSS
- shadcn/ui
- Leaflet
- Firebase Auth and Firestore

### Backend

- FastAPI
- Uvicorn
- OpenCV
- Ultralytics YOLO
- Local YOLO weights at `backend/best.pt`

## Project Structure

```text
app/                         Next.js pages and routes
components/                  UI and feature components
lib/api-client.ts            Frontend backend API wrapper
lib/auth-profile.ts          Firebase profile and role helpers
lib/crash-case-store.ts      Firestore crash case workflow helpers
lib/incident-status.ts       Case statuses and actions
lib/types.ts                 Shared frontend types
backend/main.py              Active FastAPI backend entrypoint
backend/schema.sql           Local SQLite schema for cases, cameras, areas, and assignments
backend/best.pt              Local YOLO model weights
backend/uploads/             Uploaded raw media
backend/outputs/             Annotated backend output
scripts/seed-firestore-qa.mjs Firebase emulator QA seed script
SYSTEM_DESIGN_AND_RESEARCH.md Research and design documentation
```

## Environment Setup

Install Node dependencies:

```powershell
npm install
```

Create or update `.env.local`:

```powershell
NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:8000
NEXT_PUBLIC_USE_MOCK_DATA=false

NEXT_PUBLIC_FIREBASE_API_KEY=your-api-key
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=your-project-id
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=your-project.firebasestorage.app
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=your-sender-id
NEXT_PUBLIC_FIREBASE_APP_ID=your-app-id

NEXT_PUBLIC_USE_FIREBASE_EMULATOR=true
NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST=localhost:9099
NEXT_PUBLIC_FIRESTORE_EMULATOR_HOST=localhost:8080
```

Keep the normal `NEXT_PUBLIC_FIREBASE_*` values set even when using emulators. The frontend still needs them to initialize Firebase, then emulator flags redirect local Auth and Firestore traffic.

## Run Firebase Emulators

Start Auth and Firestore emulators:

```powershell
npx firebase emulators:start --only auth,firestore
```

Default local ports:

- Auth: `localhost:9099`
- Firestore: `localhost:8080`
- Emulator UI: `localhost:4000`

## Seed QA Accounts and Crash Cases

With emulators running, seed local QA data:

```powershell
node scripts/seed-firestore-qa.mjs --emulator
```

The script prints emulator-only credentials for:

- one normal `user`
- one `responder`
- one `admin`

It also creates Firestore user profiles and sample crash cases for responder testing. Do not hard-code these passwords in application code.

Cleanup is available for generated accounts:

```powershell
node scripts/seed-firestore-qa.mjs --emulator --cleanup --user-uid <USER_UID> --responder-uid <RESPONDER_UID> --admin-uid <ADMIN_UID>
```

## Run the Backend

Use the backend virtual environment if it exists:

```powershell
backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

If you are using another Python environment, install backend requirements first:

```powershell
python -m pip install -r backend\requirements.txt
python -m uvicorn backend.main:app --reload
```

Backend URL:

```text
http://127.0.0.1:8000
```

Health check:

```text
http://127.0.0.1:8000/api/health
```

## Run the Frontend

Start the Next.js dev server:

```powershell
npm run dev
```

Open:

```text
http://localhost:3000
```

## Backend API Contract

Confirmed backend endpoints:

```text
GET  /api/health
GET  /api/incidents
GET  /api/notifications
POST /api/detect/image
POST /api/detect/video
```

Detection endpoints accept `multipart/form-data` with a media file and return:

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

## Useful QA Commands

```powershell
node --check scripts\seed-firestore-qa.mjs
npm.cmd run typecheck
npm.cmd run build
python -m py_compile backend\main.py
```

## Routes to Check

```text
/
/login
/dashboard
/dashboard/map
/dashboard/notifications
/dashboard/upload
/samples
```

## Dark and Light Mode

The UI supports dark and light themes through the app theme system and CSS variables in `app/globals.css`. The visual style is designed for a responder dashboard: clear statuses, readable contrast, concise cards, and fast scanning during review.

## Remaining Limitations

- This is a school-demo emergency support system, not a certified emergency dispatch platform.
- It does not integrate with real 911, 112, eCall, PSAP, EMS, or dispatch systems.
- Sample gallery media files may need to be added under `public/samples`.
- Video preview depends on whether the backend machine can write browser-playable output.
- Locations may use fixed or fallback coordinates instead of true source-based location.
- Notifications and incidents depend on the configured Firestore/emulator workflow.
- Mobile browser camera behavior still needs real-device validation.
- Detection quality depends on model weights, input quality, lighting, angle, and traffic conditions.

## License

Built for educational and school-demo purposes.
#   c r a s h g u a r d  
 