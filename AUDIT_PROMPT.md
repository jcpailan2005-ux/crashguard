Review this project as a senior full-stack engineer performing a production-minded audit for a school-friendly car crash detection system.

Project context:
- Frontend: Next.js 16 + TypeScript + Tailwind + shadcn/ui
- Backend: FastAPI + Ultralytics YOLO + OpenCV
- Main use case: upload image/video, detect crashes, store incidents/notifications, and preview annotated output
- Recent feature: uploaded videos now generate full annotated output footage for "View Footage"

Audit goals:
1. Find bugs, regressions, broken flows, and unsafe assumptions.
2. Check whether image upload, video upload, incident listing, notifications, and preview flows are connected correctly.
3. Review backend video-processing logic for correctness, performance, file handling, cleanup, codec/browser compatibility, and API consistency.
4. Review frontend preview logic for image/video output handling, URL resolution, fallback behavior, and UI edge cases.
5. Check TypeScript, React, FastAPI, and Python code for maintainability and beginner-friendliness.
6. Identify missing validation, missing error handling, and missing tests.
7. Flag any security issues, especially around uploads, static file serving, CORS, and trusting file names/paths.
8. Flag deployment issues and environment/configuration problems.

How to respond:
- Start with findings only.
- Order findings by severity: critical, high, medium, low.
- For each finding, include:
  - title
  - severity
  - why it matters
  - exact file reference(s)
  - recommended fix
- After findings, include:
  - open questions / assumptions
  - testing gaps
  - quick wins
- If no issue is found in an area, say so briefly.

Focus areas:
- backend/main.py
- app/dashboard/upload/page.tsx
- components/media-preview-dialog.tsx
- lib/api-client.ts
- lib/types.ts
- any related config or upload/preview code paths

Important:
- Do not spend time redesigning the UI unless it affects correctness or usability.
- Keep recommendations practical and copy-pasteable when possible.
- Assume this code may be reviewed by a beginner, so prefer clear fixes over overly abstract advice.
~