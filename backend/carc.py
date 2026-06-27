from datetime import datetime
from pathlib import Path
import os
import shutil
import uuid

import cv2
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from ultralytics import YOLO

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
UPLOADS = BASE_DIR / "uploads"
OUTPUTS = BASE_DIR / "outputs"
MODEL_PATH = BASE_DIR / "best.pt"

for folder in (UPLOADS, OUTPUTS):
    folder.mkdir(exist_ok=True)

frontend_origins = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Make generated files inside backend/outputs available to the frontend.
app.mount("/outputs", StaticFiles(directory=str(OUTPUTS)), name="outputs")

model = YOLO(str(MODEL_PATH))

incidents = []
notifications = []


def build_output_url(request: Request, filename: str) -> str:
    """Build a full URL that the frontend can open directly."""
    return f"{str(request.base_url).rstrip('/')}/outputs/{filename}"


def save_upload_file(file: UploadFile) -> Path:
    """Save the uploaded file to backend/uploads and return the saved path."""
    safe_name = f"{uuid.uuid4().hex}_{Path(file.filename or 'upload').name}"
    file_path = UPLOADS / safe_name

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return file_path


def extract_detections(results) -> tuple[list[dict], bool, float]:
    """Convert YOLO results into API-friendly detection objects."""
    detections = []
    accident_detected = False
    best_confidence = 0.0

    for result in results:
        for box in result.boxes:
            class_id = int(box.cls[0].item())
            confidence = float(box.conf[0].item())
            label = str(model.names[class_id])
            bounding_box = [float(value) for value in box.xyxy[0].tolist()]

            detections.append(
                {
                    "label": label,
                    "score": confidence,
                    "box": bounding_box,
                }
            )

            if label.lower() == "accident":
                accident_detected = True
                best_confidence = max(best_confidence, confidence)

    return detections, accident_detected, best_confidence


def create_incident_record(
    *,
    media_type: str,
    source_file: str,
    accident_detected: bool,
    confidence: float,
    timestamp: str,
):
    """Store each processed upload so the dashboard keeps working."""
    incident_id = f"INC{len(incidents) + 1:04d}"
    location = "Uploaded Video" if media_type == "video" else "Uploaded Image"

    incident = {
        "id": incident_id,
        "timestamp": timestamp,
        "detectedAt": timestamp,
        "location": location,
        "confidence": confidence,
        "media_type": media_type,
        "status": "pending_review" if accident_detected else "processed",
        "triggerStatus": (
            "camera_detection"
            if media_type == "cctv"
            else "upload_detection"
            if media_type in ("image", "video")
            else "unknown"
        ),
        "accident_detected": accident_detected,
        "source_file": source_file,
        "latitude": 7.1907,
        "longitude": 125.4553,
    }
    incidents.append(incident)

    if accident_detected:
        title_prefix = "video " if media_type == "video" else ""
        notifications.append(
            {
                "id": f"NOT{len(notifications) + 1:04d}",
                "incident_id": incident_id,
                "title": "Possible Crash Detected",
                "message": (
                    f"Possible crash detected in {title_prefix}{source_file} "
                    f"({confidence:.2%} confidence)"
                ),
                "timestamp": timestamp,
                "alert_level": "review",
                "read": False,
            }
        )


def create_video_writer(width: int, height: int, fps: float):
    """
    Try a few MP4 codecs so the saved file is more likely to play in the browser.
    Returns the opened writer, output path, and filename.
    """
    output_name = f"detected_video_{uuid.uuid4().hex[:8]}.mp4"
    output_path = OUTPUTS / output_name

    for codec in ("avc1", "H264", "mp4v"):
        writer = cv2.VideoWriter(
            str(output_path),
            cv2.VideoWriter_fourcc(*codec),
            fps,
            (width, height),
        )
        if writer.isOpened():
            return writer, output_path, output_name
        writer.release()

    return None, output_path, output_name


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
    }


@app.get("/api/incidents")
def get_incidents():
    return incidents[::-1]


@app.get("/api/notifications")
def get_notifications():
    return notifications[::-1]


@app.post("/api/detect/image")
async def detect_image(request: Request, file: UploadFile = File(...)):
    try:
        file_path = save_upload_file(file)

        # Run detection once on the uploaded image and draw the result.
        results = model.predict(str(file_path), verbose=False)
        detections, accident_detected, best_confidence = extract_detections(results)

        annotated_image = results[0].plot()
        output_name = f"result_{uuid.uuid4().hex[:8]}.jpg"
        output_path = OUTPUTS / output_name
        cv2.imwrite(str(output_path), annotated_image)

        timestamp = datetime.now().isoformat()
        create_incident_record(
            media_type="image",
            source_file=file.filename or "uploaded_image",
            accident_detected=accident_detected,
            confidence=best_confidence,
            timestamp=timestamp,
        )

        return {
            "success": True,
            "accident_detected": accident_detected,
            "confidence": best_confidence,
            "media_type": "image",
            "timestamp": timestamp,
            "location": "Uploaded Image",
            "detections": detections,
            "annotated_media_url": build_output_url(request, output_name),
        }
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Image detection failed: {error}")


@app.post("/api/detect/video")
async def detect_video(request: Request, file: UploadFile = File(...)):
    file_path = None
    cap = None
    writer = None
    output_path = None
    output_name = None

    try:
        file_path = save_upload_file(file)
        cap = cv2.VideoCapture(str(file_path))

        if not cap.isOpened():
            raise HTTPException(status_code=400, detail="Could not open uploaded video.")

        fps = cap.get(cv2.CAP_PROP_FPS) or 0
        if fps <= 0:
            fps = 20.0

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        if width <= 0 or height <= 0:
            raise HTTPException(status_code=400, detail="Uploaded video has invalid dimensions.")

        # Create the annotated output video inside backend/outputs.
        writer, output_path, output_name = create_video_writer(width, height, fps)

        accident_detected = False
        best_confidence = 0.0
        detection_samples = []
        max_detection_samples = 20
        processed_frames = 0

        while True:
            success, frame = cap.read()
            if not success:
                break

            processed_frames += 1

            # Detect objects in the current frame, then draw boxes and labels.
            results = model.predict(frame, verbose=False)
            frame_detections, frame_has_accident, frame_best_confidence = extract_detections(results)
            annotated_frame = results[0].plot()

            if writer is not None:
                writer.write(annotated_frame)

            if len(detection_samples) < max_detection_samples:
                remaining_slots = max_detection_samples - len(detection_samples)
                detection_samples.extend(frame_detections[:remaining_slots])

            if frame_has_accident:
                accident_detected = True
                best_confidence = max(best_confidence, frame_best_confidence)

        if processed_frames == 0:
            raise HTTPException(status_code=400, detail="Uploaded video has no readable frames.")

        timestamp = datetime.now().isoformat()
        create_incident_record(
            media_type="video",
            source_file=file.filename or "uploaded_video",
            accident_detected=accident_detected,
            confidence=best_confidence,
            timestamp=timestamp,
        )

        annotated_media_url = None
        if writer is not None and output_path is not None and output_path.exists():
            annotated_media_url = build_output_url(request, output_name)

        return {
            "success": True,
            "accident_detected": accident_detected,
            "confidence": best_confidence,
            "media_type": "video",
            "timestamp": timestamp,
            "location": "Uploaded Video",
            "detections": detection_samples,
            "annotated_media_url": annotated_media_url,
        }
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Video detection failed: {error}")
    finally:
        if cap is not None:
            cap.release()
        if writer is not None:
            writer.release()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
