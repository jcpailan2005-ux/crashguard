import asyncio
from collections import deque
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlparse
from urllib import error as urllib_error
from urllib import request as urllib_request
import base64
import hashlib
import hmac
import json
import os
import ipaddress
import re
import secrets
import shutil
import socket
import threading
import time
import uuid

import cv2
from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
import numpy as np
from pydantic import BaseModel, Field
from ultralytics import YOLO

from backend.db import init_db
from backend.media_store import CRASH_MEDIA_ROOT, public_media_path, store_case_media
from backend.repositories.analytics import cases_by_area, monthly_trend, summary
from backend.repositories.crash_cases import (
    apply_action,
    archive_notification,
    create_crash_case,
    assign_camera,
    delete_camera,
    delete_notification,
    find_unresolved_camera_case,
    get_camera,
    get_camera_by_ip,
    get_user_profile,
    get_user_profile_by_email,
    list_cameras,
    list_crash_cases,
    list_notifications,
    get_crash_case,
    replace_case_evidence,
    seed_demo_camera_data,
    set_camera_active,
    update_user_last_login,
    upsert_user_profile,
    upsert_camera,
)

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
UPLOADS = BASE_DIR / "uploads"
OUTPUTS = BASE_DIR / "outputs"
MODEL_PATH = BASE_DIR / "best.pt"
LOCAL_CAMERA_CONFIG_PATH = BASE_DIR / "local_camera_config.json"

for folder in (UPLOADS, OUTPUTS):
    folder.mkdir(exist_ok=True)
CRASH_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
init_db()
seed_demo_camera_data()

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


def _json_request(url: str, payload: dict, timeout: float = 8.0) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib_request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _decode_jwt_payload_without_trust(token: str) -> dict:
    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError("Invalid token format.")
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    return json.loads(base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8"))


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


SESSION_SECRET = os.getenv("CRASHGUARD_SESSION_SECRET", "crashguard-local-demo-session-secret")
SESSION_TTL_SECONDS = _env_int("CRASHGUARD_SESSION_TTL_SECONDS", 60 * 60 * 24 * 7)
PASSWORD_MIN_LENGTH = _env_int("CRASHGUARD_PASSWORD_MIN_LENGTH", 8)
PASSWORD_HASH_ITERATIONS = _env_int("CRASHGUARD_PASSWORD_HASH_ITERATIONS", 210_000)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode((data + "=" * (-len(data) % 4)).encode("utf-8"))


def hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_HASH_ITERATIONS,
    )
    return digest.hex(), salt.hex()


def verify_password(password: str, password_hash: str | None, password_salt: str | None) -> bool:
    if not password_hash or not password_salt:
        return False
    candidate_hash, _ = hash_password(password, password_salt)
    return hmac.compare_digest(candidate_hash, password_hash)


def safe_user(profile: dict) -> dict:
    return {
        "uid": profile.get("uid"),
        "email": profile.get("email"),
        "displayName": profile.get("displayName") or "",
        "role": profile.get("role") if profile.get("role") in {"user", "responder", "admin"} else "user",
        "areaId": profile.get("areaId"),
        "active": bool(profile.get("isActive", profile.get("active", 1))),
        "createdAt": profile.get("createdAt") or "",
        "updatedAt": profile.get("updatedAt") or "",
        "lastLoginAt": profile.get("lastLoginAt"),
    }


def create_session_token(profile: dict) -> str:
    now = int(time.time())
    payload = {
        "uid": profile["uid"],
        "email": profile["email"],
        "iat": now,
        "exp": now + SESSION_TTL_SECONDS,
    }
    payload_part = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(
        SESSION_SECRET.encode("utf-8"),
        payload_part.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"{payload_part}.{_b64url_encode(signature)}"


def verify_session_token(token: str) -> dict:
    try:
        payload_part, signature_part = token.split(".", 1)
        expected = hmac.new(
            SESSION_SECRET.encode("utf-8"),
            payload_part.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(_b64url_encode(expected), signature_part):
            raise ValueError("Bad signature.")
        payload = json.loads(_b64url_decode(payload_part).decode("utf-8"))
    except Exception as error:
        raise HTTPException(status_code=401, detail="Invalid session token.") from error

    if int(payload.get("exp") or 0) < int(time.time()):
        raise HTTPException(status_code=401, detail="Session expired.")
    profile = get_user_profile(str(payload.get("uid") or ""))
    if profile is None:
        raise HTTPException(status_code=401, detail="Session user not found.")
    if not bool(profile.get("isActive", 1)):
        raise HTTPException(status_code=403, detail="This account is inactive.")
    return {
        "uid": profile["uid"],
        "email": profile.get("email"),
        "role": profile.get("role") or "user",
        "areaId": profile.get("areaId"),
        "profile": safe_user(profile),
    }


def user_from_sqlite_session(request: Request) -> dict | None:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    token = header.split(" ", 1)[1].strip()
    if not token or token.count(".") != 1:
        return None
    return verify_session_token(token)


def verify_firebase_user(request: Request) -> dict:
    sqlite_user = user_from_sqlite_session(request)
    if sqlite_user is not None:
        return sqlite_user

    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Firebase ID token.")
    token = header.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing Firebase ID token.")

    api_key = (
        os.getenv("FIREBASE_WEB_API_KEY")
        or os.getenv("NEXT_PUBLIC_FIREBASE_API_KEY")
        or os.getenv("FIREBASE_API_KEY")
    )
    emulator_host = os.getenv("FIREBASE_AUTH_EMULATOR_HOST")
    decoded: dict
    try:
        if emulator_host:
            host = emulator_host.replace("http://", "").replace("https://", "")
            decoded = _json_request(
                f"http://{host}/identitytoolkit.googleapis.com/v1/accounts:lookup?key=local",
                {"idToken": token},
            )
            user = (decoded.get("users") or [{}])[0]
            uid = user.get("localId")
            email = user.get("email")
        elif api_key:
            decoded = _json_request(
                f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={api_key}",
                {"idToken": token},
            )
            user = (decoded.get("users") or [{}])[0]
            uid = user.get("localId")
            email = user.get("email")
        else:
            # Local demo fallback: still require a bearer token, then map roles from SQLite.
            # This is not a production verifier; configure FIREBASE_WEB_API_KEY for real verification.
            user = _decode_jwt_payload_without_trust(token)
            uid = user.get("user_id") or user.get("sub") or user.get("uid")
            email = user.get("email")
    except (urllib_error.HTTPError, urllib_error.URLError, ValueError, KeyError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=401, detail="Invalid Firebase ID token.") from error

    if not uid:
        raise HTTPException(status_code=401, detail="Invalid Firebase ID token.")

    local_profile = get_user_profile(uid)
    if local_profile is None:
        role = user.get("role") if user.get("role") in {"user", "responder", "admin"} else "user"
        local_profile = upsert_user_profile(
            {
                "uid": uid,
                "email": email or f"{uid}@local.test",
                "displayName": user.get("displayName") or user.get("name") or "",
                "role": role,
                "areaId": user.get("areaId"),
            }
        )
    return {
        "uid": uid,
        "email": email or local_profile.get("email"),
        "role": local_profile.get("role") or "user",
        "areaId": local_profile.get("areaId"),
        "profile": safe_user(local_profile),
    }


def require_admin(request: Request) -> dict:
    user = verify_firebase_user(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access is required.")
    return user


def require_dashboard_access(request: Request) -> dict:
    user = verify_firebase_user(request)
    if user["role"] not in {"admin", "responder"}:
        raise HTTPException(status_code=403, detail="You do not have permission to access this page.")
    return user


def optional_request_user(request: Request) -> dict | None:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    return verify_firebase_user(request)


def get_user_area_scope(user: dict) -> str | None:
    return user.get("areaId") if user.get("role") == "responder" else None


def can_access_camera(user: dict, camera: dict | None) -> bool:
    if camera is None:
        return False
    if user.get("role") == "admin":
        return True
    if user.get("role") != "responder":
        return False
    area_scope = get_user_area_scope(user)
    if area_scope and camera.get("areaId") == area_scope:
        return True
    assigned = list_cameras(role="responder", user_id=user.get("uid"), area_id=area_scope)
    return any(item["cameraId"] == camera.get("cameraId") for item in assigned)


def require_camera_access(request: Request, camera_id: str) -> tuple[dict, dict]:
    user = verify_firebase_user(request)
    camera = get_camera(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found.")
    if not can_access_camera(user, camera):
        raise HTTPException(status_code=403, detail="You are not authorized to access this camera.")
    return user, camera


# Make generated files inside backend/outputs available to the frontend.
app.mount("/outputs", StaticFiles(directory=str(OUTPUTS)), name="outputs")
app.mount("/uploads/crash-media", StaticFiles(directory=str(CRASH_MEDIA_ROOT)), name="crash-media")

model = YOLO(str(MODEL_PATH))
vehicle_model = None
vehicle_model_error = None
vehicle_model_path = os.getenv("VEHICLE_MODEL_PATH", "yolov8n.pt")
try:
    vehicle_model = YOLO(vehicle_model_path)
except Exception as error:
    vehicle_model_error = str(error)
    print(f"[vehicle-detector] Could not load vehicle model {vehicle_model_path!r}: {error}")


def normalize_detection_label(label: str) -> str:
    return (label or "").strip().lower().replace(" ", "_").replace("-", "_")


# Returned JSON + drawn preview: motor-vehicle road classes and crash labels only (no person, phone, …).
ALLOWED_DETECTION_OUTPUT_LABELS = frozenset(
    {
        "car",
        "truck",
        "bus",
        "van",
        "motorcycle",
        "motorbike",
        "moped",
        "vehicle",
        "accident",
        "crash",
        "collision",
    }
)

# Used for overlap heuristics only (no generic "vehicle" — avoids noisy COCO false positives).
VEHICLE_HEURISTIC_LABELS = frozenset(
    {"car", "truck", "bus", "van", "motorcycle", "motorbike", "moped"}
)


def is_allowed_detection_output_label(label: str) -> bool:
    return normalize_detection_label(label) in ALLOWED_DETECTION_OUTPUT_LABELS


def draw_filtered_detection_overlay(bgr: np.ndarray, results) -> np.ndarray:
    """BGR image with boxes only for allowed classes (excludes person, cell phone, etc.)."""
    img = np.array(bgr, copy=True)
    for res in results:
        if res.boxes is None or len(res.boxes) == 0:
            continue
        for box in res.boxes:
            class_id = int(box.cls[0].item())
            label = str(model.names[class_id])
            if not is_allowed_detection_output_label(label):
                continue
            xyxy = box.xyxy[0].detach().cpu().numpy()
            x1, y1, x2, y2 = int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])
            conf = float(box.conf[0])
            lab_n = normalize_detection_label(label)
            if lab_n in ("accident", "crash", "collision"):
                color = (36, 36, 220)
            else:
                color = (52, 190, 52)
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
            caption = f"{label} {conf:.2f}"
            cv2.putText(
                img,
                caption,
                (x1, max(16, y1 - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.52,
                color,
                2,
                cv2.LINE_AA,
            )
    return img


VEHICLE_BOX_LABELS = frozenset({"car", "motorcycle", "bus", "truck"})


def extract_vehicle_boxes_from_results(results, names, frame: np.ndarray) -> list[dict]:
    boxes: list[dict] = []
    frame_height, frame_width = frame.shape[:2]
    for result in results:
        if result.boxes is None or len(result.boxes) == 0:
            continue
        for raw_box in result.boxes:
            class_id = int(raw_box.cls[0].item())
            label = normalize_detection_label(str(names.get(class_id, class_id)))
            if label == "motorbike":
                label = "motorcycle"
            if label not in VEHICLE_BOX_LABELS:
                continue
            confidence = float(raw_box.conf[0].item())
            if confidence < LIVE_CAMERA_VEHICLE_CONFIDENCE_THRESHOLD:
                continue
            x1, y1, x2, y2 = [float(value) for value in raw_box.xyxy[0].tolist()]
            x1 = max(0.0, min(x1, frame_width))
            x2 = max(0.0, min(x2, frame_width))
            y1 = max(0.0, min(y1, frame_height))
            y2 = max(0.0, min(y2, frame_height))
            width = max(0.0, x2 - x1)
            height = max(0.0, y2 - y1)
            if width <= 0 or height <= 0:
                continue
            boxes.append(
                {
                    "label": label,
                    "confidence": confidence,
                    "x": x1,
                    "y": y1,
                    "width": width,
                    "height": height,
                }
            )
    return boxes


def detect_vehicle_boxes(frame: np.ndarray, fallback_results=None) -> list[dict]:
    """Run a vehicle detector for boxes. Falls back to the active model's boxes."""
    if vehicle_model is not None:
        results = vehicle_model.predict(frame, verbose=False)
        return extract_vehicle_boxes_from_results(
            results,
            getattr(vehicle_model, "names", {}),
            frame,
        )
    if fallback_results is not None:
        return extract_vehicle_boxes_from_results(
            fallback_results,
            getattr(model, "names", {}),
            frame,
        )
    return []


def scale_detection_boxes(boxes: list[dict], *, scale_x: float, scale_y: float) -> list[dict]:
    return [
        {
            **box,
            "x": float(box["x"]) * scale_x,
            "y": float(box["y"]) * scale_y,
            "width": float(box["width"]) * scale_x,
            "height": float(box["height"]) * scale_y,
        }
        for box in boxes
    ]


def draw_detection_boxes_overlay(bgr: np.ndarray, boxes: list[dict]) -> np.ndarray:
    img = np.array(bgr, copy=True)
    for box in boxes:
        x = int(float(box.get("x", 0)))
        y = int(float(box.get("y", 0)))
        width = int(float(box.get("width", 0)))
        height = int(float(box.get("height", 0)))
        label = str(box.get("label") or "vehicle")
        confidence = float(box.get("confidence") or 0)
        if width <= 0 or height <= 0:
            continue
        color = (52, 190, 52)
        cv2.rectangle(img, (x, y), (x + width, y + height), color, 2)
        cv2.putText(
            img,
            f"{label} {confidence:.2f}",
            (x, max(16, y - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            color,
            2,
            cv2.LINE_AA,
        )
    return img


incidents = []
notifications = []
DETECTION_RECORDS_ENABLED = os.getenv("ENABLE_BACKEND_MEMORY_INCIDENTS", "false").lower() == "true"
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif"}
SUPPORTED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/bmp",
    "image/webp",
    "image/gif",
}
SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".avi", ".m4v", ".mkv"}
SUPPORTED_VIDEO_CONTENT_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/webm",
    "video/x-msvideo",
    "video/x-matroska",
}


def log_image(message: str):
    """Keep image route logging consistent and easy to scan in demo runs."""
    print(f"[image] {message}")


def log_video(message: str):
    """Keep video route logging consistent and easy to scan in demo runs."""
    print(f"[video] {message}")


def build_output_url(request: Request, filename: str) -> str:
    """Build a full URL that the frontend can open directly."""
    return f"{str(request.base_url).rstrip('/')}/outputs/{filename}"


def get_output_format(filename: str | None) -> str | None:
    """Return the lowercase file extension without the leading dot."""
    if not filename:
        return None
    suffix = Path(filename).suffix.lower()
    return suffix[1:] if suffix.startswith(".") else suffix or None


def save_upload_file(file: UploadFile) -> Path:
    """Save the uploaded file to backend/uploads and return the saved path."""
    safe_name = f"{uuid.uuid4().hex}_{Path(file.filename or 'upload').name}"
    file_path = UPLOADS / safe_name

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return file_path


def is_supported_image_upload(file: UploadFile) -> bool:
    filename = (file.filename or "").lower()
    suffix = Path(filename).suffix
    content_type = (file.content_type or "").lower()

    return (
        suffix in SUPPORTED_IMAGE_EXTENSIONS
        or content_type in SUPPORTED_IMAGE_CONTENT_TYPES
    )


def is_supported_video_upload(file: UploadFile) -> bool:
    filename = (file.filename or "").lower()
    suffix = Path(filename).suffix
    content_type = (file.content_type or "").lower()

    return (
        suffix in SUPPORTED_VIDEO_EXTENSIONS
        or content_type in SUPPORTED_VIDEO_CONTENT_TYPES
    )


def get_env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def get_env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


ACCIDENT_HEURISTIC_SCORE_THRESHOLD = get_env_float(
    "ACCIDENT_HEURISTIC_SCORE_THRESHOLD", 0.20
)
MOTORCYCLE_OVERLAP_MIN_AREA_THRESHOLD = get_env_float(
    "MOTORCYCLE_OVERLAP_MIN_AREA_THRESHOLD", 0.10
)
MOTORCYCLE_IOU_THRESHOLD = get_env_float("MOTORCYCLE_IOU_THRESHOLD", 0.045)
DEMO_FALLBACK_LATITUDE = get_env_float("DEMO_FALLBACK_LATITUDE", 7.1907)
DEMO_FALLBACK_LONGITUDE = get_env_float("DEMO_FALLBACK_LONGITUDE", 125.4553)
LIVE_CAMERA_DETECTION_INTERVAL_MS = get_env_int("LIVE_CAMERA_DETECTION_INTERVAL_MS", 500)
CRASH_ALERT_CONFIDENCE_THRESHOLD = 0.20


def normalize_confidence_fraction(value: float | int | None) -> float:
    """Return confidence as a 0.0-1.0 fraction, accepting either 0.70 or 70.0."""
    try:
        confidence = float(value or 0)
    except (TypeError, ValueError):
        return 0.0

    if confidence > 1.0:
        confidence = confidence / 100.0

    return max(0.0, min(1.0, confidence))


LIVE_CAMERA_CONFIDENCE_THRESHOLD = CRASH_ALERT_CONFIDENCE_THRESHOLD


def passes_crash_alert_threshold(
    confidence: float | int | None,
    *,
    accident_detected: bool,
) -> bool:
    return bool(
        accident_detected
        and normalize_confidence_fraction(confidence) >= CRASH_ALERT_CONFIDENCE_THRESHOLD
    )
LIVE_CAMERA_VEHICLE_CONFIDENCE_THRESHOLD = get_env_float(
    "LIVE_CAMERA_VEHICLE_CONFIDENCE_THRESHOLD", 0.40
)
LIVE_CAMERA_ALERT_COOLDOWN_SECONDS = get_env_int("LIVE_CAMERA_ALERT_COOLDOWN_SECONDS", 30)
_legacy_active_case_block_minutes = get_env_int("LIVE_CAMERA_ACTIVE_CASE_BLOCK_MINUTES", 0)
LIVE_CAMERA_DUPLICATE_CASE_BLOCK_SECONDS = get_env_int(
    "LIVE_CAMERA_DUPLICATE_CASE_BLOCK_SECONDS",
    get_env_int(
        "LIVE_CAMERA_ACTIVE_CASE_BLOCK_SECONDS",
        _legacy_active_case_block_minutes * 60
        if _legacy_active_case_block_minutes > 0
        else 60,
    ),
)
LIVE_CAMERA_DUPLICATE_CASE_BLOCK_SECONDS = max(
    1,
    min(120, LIVE_CAMERA_DUPLICATE_CASE_BLOCK_SECONDS),
)
LIVE_CAMERA_FRAME_WIDTH = get_env_int("LIVE_CAMERA_FRAME_WIDTH", 640)
LIVE_CAMERA_FRAME_HEIGHT = get_env_int("LIVE_CAMERA_FRAME_HEIGHT", 360)
LIVE_CAMERA_REQUIRED_HITS = get_env_int("LIVE_CAMERA_REQUIRED_HITS", 1)
LIVE_CAMERA_BUFFER_SIZE = get_env_int("LIVE_CAMERA_BUFFER_SIZE", 1)
LIVE_CAMERA_FREEZE_TIMEOUT_SECONDS = get_env_int("LIVE_CAMERA_FREEZE_TIMEOUT_SECONDS", 10)
LIVE_CAMERA_PREVIEW_FPS = get_env_int("LIVE_CAMERA_PREVIEW_FPS", 10)
LIVE_CAMERA_JPEG_QUALITY = get_env_int("LIVE_CAMERA_JPEG_QUALITY", 75)
LIVE_CAMERA_USE_SEPARATE_VEHICLE_MODEL = os.getenv(
    "LIVE_CAMERA_USE_SEPARATE_VEHICLE_MODEL", "true"
).lower() == "true"


def get_video_frame_skip(total_frames: int, fps: float) -> int:
    """Choose a demo-friendly sampling rate while allowing env overrides."""
    try:
        configured_skip = int(os.getenv("VIDEO_FRAME_SKIP", "0"))
    except ValueError:
        configured_skip = 0

    if configured_skip > 0:
        return configured_skip

    target_analysis_fps = get_env_float("VIDEO_ANALYSIS_FPS", 3.0)
    target_analysis_fps = max(0.5, min(target_analysis_fps, fps or 30.0))

    frame_skip = max(1, int(round((fps or 30.0) / target_analysis_fps)))

    if total_frames >= 3600:
        return max(frame_skip, 20)
    if total_frames >= 900:
        return max(frame_skip, 12)
    return max(frame_skip, 8)


def decode_uploaded_image(file_path: Path):
    """Decode a saved upload with OpenCV so invalid image files fail cleanly."""
    try:
        image_bytes = file_path.read_bytes()
    except Exception as error:
        raise ValueError(f"Could not read uploaded image: {error}") from error

    if not image_bytes:
        raise ValueError("The uploaded image file is empty.")

    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("The uploaded file could not be decoded as a valid image.")

    return image


def extract_detections(results) -> tuple[list[dict], bool, float]:
    """Convert YOLO results into API-friendly detection objects."""
    detections = []
    accident_detected = False
    best_confidence = 0.0
    vehicle_candidates: list[tuple[str, float, list[float]]] = []

    def _iou_xyxy(a: list[float], b: list[float]) -> float:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)
        inter_w = max(0.0, inter_x2 - inter_x1)
        inter_h = max(0.0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h
        if inter_area <= 0.0:
            return 0.0
        a_area = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
        b_area = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
        denom = a_area + b_area - inter_area
        return (inter_area / denom) if denom > 0.0 else 0.0

    def _intersection_over_min_area(a: list[float], b: list[float]) -> float:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)
        inter_w = max(0.0, inter_x2 - inter_x1)
        inter_h = max(0.0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h
        if inter_area <= 0.0:
            return 0.0
        a_area = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
        b_area = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
        min_area = min(a_area, b_area)
        return (inter_area / min_area) if min_area > 0.0 else 0.0

    def _edge_distance_xyxy(a: list[float], b: list[float]) -> float:
        """
        Distance (in pixels) between two boxes' edges (0 if overlapping/touching).
        Uses axis-aligned rectangles in xyxy format.
        """
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        dx = 0.0
        if ax2 < bx1:
            dx = bx1 - ax2
        elif bx2 < ax1:
            dx = ax1 - bx2
        dy = 0.0
        if ay2 < by1:
            dy = by1 - ay2
        elif by2 < ay1:
            dy = ay1 - by2
        # If separated in both axes, use Euclidean; else the separating axis distance.
        if dx > 0.0 and dy > 0.0:
            return float((dx * dx + dy * dy) ** 0.5)
        return float(max(dx, dy))

    for result in results:
        if result.boxes is None or len(result.boxes) == 0:
            continue
        for box in result.boxes:
            class_id = int(box.cls[0].item())
            confidence = float(box.conf[0].item())
            label = str(model.names[class_id])
            bounding_box = [float(value) for value in box.xyxy[0].tolist()]
            lab_n = normalize_detection_label(label)

            if is_allowed_detection_output_label(label):
                detections.append(
                    {
                        "label": label,
                        "score": confidence,
                        "box": bounding_box,
                    }
                )

            if lab_n in ("accident", "crash", "collision"):
                accident_detected = True
                best_confidence = max(best_confidence, confidence)
            elif lab_n in VEHICLE_HEURISTIC_LABELS:
                # Heuristic crash inference (no generic "vehicle" here).
                vehicle_candidates.append((label, confidence, bounding_box))

    # Fallback: if the model doesn't have an "accident" class (e.g. COCO weights),
    # infer a possible collision only when two vehicle boxes overlap strongly.
    # Adjacent / side-by-side vehicles (small gap, low IoU) must NOT trigger this path.
    has_accident_class = any(
        str(name).lower() == "accident" for name in getattr(model, "names", {}).values()
    )
    if not accident_detected and not has_accident_class and len(vehicle_candidates) >= 2:
        best_score = 0.0
        best_pair = None
        for i in range(len(vehicle_candidates)):
            _, conf_a, box_a = vehicle_candidates[i]
            for j in range(i + 1, len(vehicle_candidates)):
                _, conf_b, box_b = vehicle_candidates[j]
                # Real crashes often have one very confident vehicle and a weak second box (night, small target).
                if max(conf_a, conf_b) < 0.38 or min(conf_a, conf_b) < 0.12:
                    continue
                iou = _iou_xyxy(box_a, box_b)
                io_min = _intersection_over_min_area(box_a, box_b)
                dist = _edge_distance_xyxy(box_a, box_b)

                # Normalize distance by box scale so this works across resolutions.
                wa = max(1.0, box_a[2] - box_a[0])
                ha = max(1.0, box_a[3] - box_a[1])
                wb = max(1.0, box_b[2] - box_b[0])
                hb = max(1.0, box_b[3] - box_b[1])
                scale = max(wa, ha, wb, hb)
                dist_norm = dist / scale

                # Accident-likeness proxy: rely on real box overlap, not edge distance alone.
                # Parked cars "mag tabi" often have tiny dist_norm but IoU≈0 — those must stay false.
                overlap_signal = max(iou, 0.6 * io_min)

                # "Mag tabi" = malapit ang box pero mababang IoU/io_min — hindi accident.
                strong_overlap = (iou >= 0.24) or (io_min >= 0.40)
                # Totoong lapat ng katawan ng dalawang sasakyan (may IoU at siksik na overlap).
                stacked_overlap = (io_min >= 0.30) and (iou >= 0.055) and (dist_norm <= 0.007)
                contact_like = strong_overlap or stacked_overlap
                if not contact_like:
                    continue

                score = overlap_signal * min(conf_a, conf_b)
                if score > best_score:
                    best_score = score
                    best_pair = (box_a, box_b)

        if best_score >= ACCIDENT_HEURISTIC_SCORE_THRESHOLD and best_pair is not None:
            box_a, box_b = best_pair
            union_box = [
                min(box_a[0], box_b[0]),
                min(box_a[1], box_b[1]),
                max(box_a[2], box_b[2]),
                max(box_a[3], box_b[3]),
            ]
            accident_detected = True
            best_confidence = float(min(0.99, max(0.01, best_score)))
            detections.append(
                {
                    "label": "accident",
                    "score": best_confidence,
                    "box": union_box,
                }
            )

    # Motorcycle vs car/truck: small moto box → low IoU on car, but io_min can show real overlap.
    if not accident_detected and not has_accident_class and len(vehicle_candidates) >= 2:
        _moto = {"motorcycle", "motorbike", "moped"}
        _four = {"car", "truck", "bus", "van"}
        for i in range(len(vehicle_candidates)):
            lab_a, conf_a, box_a = vehicle_candidates[i]
            la = normalize_detection_label(lab_a)
            for j in range(i + 1, len(vehicle_candidates)):
                lab_b, conf_b, box_b = vehicle_candidates[j]
                lb = normalize_detection_label(lab_b)
                if max(conf_a, conf_b) < 0.36 or min(conf_a, conf_b) < 0.10:
                    continue
                if not ((la in _moto and lb in _four) or (lb in _moto and la in _four)):
                    continue
                iou = _iou_xyxy(box_a, box_b)
                io_min = _intersection_over_min_area(box_a, box_b)
                if (
                    io_min >= MOTORCYCLE_OVERLAP_MIN_AREA_THRESHOLD
                    or iou >= MOTORCYCLE_IOU_THRESHOLD
                ) and min(conf_a, conf_b) >= 0.10:
                    union_box = [
                        min(box_a[0], box_b[0]),
                        min(box_a[1], box_b[1]),
                        max(box_a[2], box_b[2]),
                        max(box_a[3], box_b[3]),
                    ]
                    accident_detected = True
                    best_confidence = float(
                        min(
                            0.99,
                            max(0.45, min(conf_a, conf_b) * max(0.35 + iou, io_min)),
                        )
                    )
                    detections.append(
                        {
                            "label": "accident",
                            "score": best_confidence,
                            "box": union_box,
                        }
                    )
                    break
            if accident_detected:
                break

    # Motorcycles are often mislabeled as "car" (small box) next to an SUV/car — still a real crash.
    if not accident_detected and not has_accident_class and len(vehicle_candidates) >= 2:
        _four_like = frozenset({"car", "truck", "bus", "van"})
        for i in range(len(vehicle_candidates)):
            lab_a, conf_a, box_a = vehicle_candidates[i]
            if normalize_detection_label(lab_a) not in _four_like:
                continue
            for j in range(i + 1, len(vehicle_candidates)):
                lab_b, conf_b, box_b = vehicle_candidates[j]
                if normalize_detection_label(lab_b) not in _four_like:
                    continue
                if max(conf_a, conf_b) < 0.34 or min(conf_a, conf_b) < 0.10:
                    continue
                area_a = max(1.0, box_a[2] - box_a[0]) * max(1.0, box_a[3] - box_a[1])
                area_b = max(1.0, box_b[2] - box_b[0]) * max(1.0, box_b[3] - box_b[1])
                area_ratio = min(area_a, area_b) / max(area_a, area_b, 1.0)
                if area_ratio > 0.36:
                    continue
                iou = _iou_xyxy(box_a, box_b)
                io_min = _intersection_over_min_area(box_a, box_b)
                dist = _edge_distance_xyxy(box_a, box_b)
                wa = max(1.0, box_a[2] - box_a[0])
                ha = max(1.0, box_a[3] - box_a[1])
                wb = max(1.0, box_b[2] - box_b[0])
                hb = max(1.0, box_b[3] - box_b[1])
                scale = max(wa, ha, wb, hb)
                dist_norm = dist / scale
                strong = (iou >= 0.19) or (io_min >= 0.30)
                stacked = (io_min >= 0.22) and (iou >= 0.04) and (dist_norm <= 0.0085)
                if not (strong or stacked):
                    continue
                union_box = [
                    min(box_a[0], box_b[0]),
                    min(box_a[1], box_b[1]),
                    max(box_a[2], box_b[2]),
                    max(box_a[3], box_b[3]),
                ]
                accident_detected = True
                best_confidence = float(
                    min(
                        0.99,
                        max(
                            0.48,
                            max(conf_a, conf_b) * max(0.4, 0.5 * io_min + 0.35 * iou),
                        ),
                    )
                )
                detections.append(
                    {
                        "label": "accident",
                        "score": best_confidence,
                        "box": union_box,
                    }
                )
                break
            if accident_detected:
                break

    return detections, accident_detected, best_confidence


def create_incident_record(
    *,
    media_type: str,
    source_file: str,
    accident_detected: bool,
    confidence: float,
    timestamp: str,
    location: str | None = None,
):
    """Legacy demo record path. Firestore is the app source of truth for cases."""
    if not DETECTION_RECORDS_ENABLED:
        return None

    incident_id = f"INC{len(incidents) + 1:04d}"
    if location is None:
        if media_type == "video":
            location = "Uploaded Video"
        elif media_type == "cctv":
            location = "CCTV Stream"
        else:
            location = "Uploaded Image"

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
        "latitude": DEMO_FALLBACK_LATITUDE,
        "longitude": DEMO_FALLBACK_LONGITUDE,
    }
    incidents.append(incident)

    if accident_detected:
        if media_type == "video":
            title_prefix = "video "
        elif media_type == "cctv":
            title_prefix = "CCTV "
        else:
            title_prefix = ""
        notifications.append(
            {
                "id": f"NOT{len(notifications) + 1:04d}",
                "incident_id": incident_id,
                "title": "Possible Crash Pending Review",
                "message": (
                    f"Possible crash detected in {title_prefix}{source_file} "
                    f"({confidence:.2%} confidence). Responder review required."
                ),
                "timestamp": timestamp,
                "alert_level": "review",
                "read": False,
            }
        )


def log_stream(message: str):
    print(f"[stream] {message}")


def build_output_url_from_base(base_url: str, filename: str) -> str:
    return f"{base_url.rstrip('/')}/outputs/{filename}"


def output_url_to_path(url: str | None) -> Path | None:
    if not url:
        return None
    parsed = urlparse(url)
    path = parsed.path if parsed.scheme else url
    prefix = "/outputs/"
    if prefix not in path:
        return None
    filename = path.split(prefix, 1)[1]
    candidate = OUTPUTS / Path(filename).name
    return candidate if candidate.exists() else None


def detections_to_response_boxes(detections: list[dict]) -> list[dict]:
    boxes = []
    for detection in detections:
        raw_box = detection.get("box")
        if not isinstance(raw_box, list) or len(raw_box) != 4:
            continue
        x1, y1, x2, y2 = [float(value) for value in raw_box]
        width = max(0.0, x2 - x1)
        height = max(0.0, y2 - y1)
        if width <= 0 or height <= 0:
            continue
        boxes.append(
            {
                "label": detection.get("label") or "unknown",
                "confidence": float(detection.get("score") or 0),
                "x": x1,
                "y": y1,
                "width": width,
                "height": height,
            }
        )
    return boxes


def persist_sqlite_crash_case(
    *,
    media_type: str,
    source_file: str,
    confidence: float,
    timestamp: str,
    location: str,
    original_path: Path | None,
    annotated_url: str | None,
    annotated_download_url: str | None,
    key_frame_url: str | None,
    trigger_status: str,
    source_camera: str | None = None,
    area_id: str | None = None,
    camera_ip: str | None = None,
    camera_id: str | None = None,
    camera_name: str | None = None,
    barangay: str | None = None,
    road_name: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    assigned_responder_id: str | None = None,
    responder_id: str | None = None,
    boxes: list[dict] | None = None,
) -> dict | None:
    if trigger_status == "camera_detection" and (camera_ip or camera_id or source_camera):
        existing_case = find_unresolved_camera_case(
            camera_ip,
            camera_id,
            source_camera,
            area_id=area_id,
            location=location,
            block_seconds=LIVE_CAMERA_DUPLICATE_CASE_BLOCK_SECONDS,
        )
        if existing_case:
            log_stream(
                "Camera alert blocked by active case "
                f"caseId={existing_case['caseId']} status={existing_case.get('status')} "
                f"areaId={area_id or ''} cameraId={camera_id or ''} "
                f"cameraIp={camera_ip or ''} source={source_camera or ''}"
            )
            existing_case["casePersistenceStatus"] = "blocked_existing_case"
            existing_case["alertBlockedReason"] = (
                f"Alert blocked because an active case already exists for this same recent incident: {existing_case['caseId']}"
            )
            existing_case["activeBlockingCaseId"] = existing_case["caseId"]
            existing_case["activeBlockingStatus"] = existing_case["status"]
            existing_case["createdNotificationId"] = None
            return existing_case

    case_id = f"CASE-{uuid.uuid4().hex[:10].upper()}"
    media_paths = store_case_media(
      case_id,
      original_path=original_path,
      key_frame_path=output_url_to_path(key_frame_url) or output_url_to_path(annotated_url),
      thumbnail_path=output_url_to_path(key_frame_url) or output_url_to_path(annotated_url),
      annotated_path=output_url_to_path(annotated_download_url) or output_url_to_path(annotated_url),
    )
    frame_path = (
        media_paths.get("keyFramePath")
        or media_paths.get("annotatedPath")
        or media_paths.get("thumbnailPath")
    )
    case_item = create_crash_case(
        {
            "caseId": case_id,
            "status": "pending_review",
            "confidence": confidence,
            "detectedAt": timestamp,
            "updatedAt": timestamp,
            "location": location,
            "latitude": latitude if latitude is not None else DEMO_FALLBACK_LATITUDE,
            "longitude": longitude if longitude is not None else DEMO_FALLBACK_LONGITUDE,
            "areaId": area_id,
            "sourceCamera": source_camera or source_file,
            "cameraId": camera_id,
            "cameraName": camera_name or source_camera or source_file,
            "cameraIp": camera_ip,
            "barangay": barangay or area_id,
            "roadName": road_name,
            "assignedResponderId": assigned_responder_id,
            "responderId": responder_id,
            "triggerStatus": trigger_status,
            "accidentDetected": True,
            **media_paths,
        },
        boxes=boxes,
        frame_path=frame_path,
    )
    if case_item is not None:
        case_item["casePersistenceStatus"] = "created"
        log_label = "Camera alert" if trigger_status == "camera_detection" else "Crash case"
        log_stream(
            f"{log_label} saved "
            f"caseId={case_item.get('caseId')} "
            f"notificationId={case_item.get('createdNotificationId')} "
            f"createdAt={timestamp} areaId={area_id or ''} "
            f"cameraId={camera_id or ''} source={source_camera or source_file}"
        )
    else:
        log_label = "Camera alert" if trigger_status == "camera_detection" else "Crash case"
        log_stream(
            f"{log_label} persistence failed "
            f"createdAt={timestamp} areaId={area_id or ''} "
            f"cameraId={camera_id or ''} source={source_camera or source_file}"
        )
    return case_item


def validate_stream_url(url: str) -> None:
    parsed = urlparse(url.strip())
    if parsed.scheme == "demo":
        if not parsed.netloc:
            raise ValueError("Invalid demo camera URL.")
        return
    if parsed.scheme not in ("rtsp", "rtsps", "http", "https"):
        raise ValueError(
            "Unsupported URL scheme. Use rtsp://, rtsps://, http://, or https://."
        )
    if not parsed.netloc:
        raise ValueError("Invalid stream URL (missing host).")
    if not is_authorized_camera_host(parsed.hostname or ""):
        raise ValueError(
            "Camera host is not authorized for this local demo. Use localhost, a private/local camera address, or set AUTHORIZED_CAMERA_HOSTS."
        )


def is_authorized_camera_host(host: str) -> bool:
    normalized = host.strip().lower()
    configured_hosts = {
        item.strip().lower()
        for item in os.getenv("AUTHORIZED_CAMERA_HOSTS", "").split(",")
        if item.strip()
    }
    if normalized in {"localhost", "127.0.0.1", "::1"} or normalized in configured_hosts:
        return True
    try:
        ip = ipaddress.ip_address(normalized)
        return ip.is_private or ip.is_loopback
    except ValueError:
        return normalized.endswith(".local")


def validate_camera_ip(camera_ip: str) -> str:
    trimmed = (camera_ip or "").strip()
    try:
        parsed = ipaddress.ip_address(trimmed)
    except ValueError as error:
        raise ValueError("Invalid IP address. Example: 192.168.1.34") from error
    if parsed.version != 4:
        raise ValueError("Invalid IP address. Example: 192.168.1.34")
    return trimmed


def load_camera_config(include_secret: bool = False) -> dict:
    file_config = {}
    if LOCAL_CAMERA_CONFIG_PATH.exists():
        try:
            file_config = json.loads(LOCAL_CAMERA_CONFIG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            file_config = {}

    username = file_config.get("cameraUsername") or os.getenv("TAPO_CAMERA_USERNAME", "")
    password = file_config.get("cameraPassword") or os.getenv("TAPO_CAMERA_PASSWORD", "")
    stream_type = file_config.get("streamType") or os.getenv("TAPO_STREAM_TYPE", "stream1")
    rtsp_port = file_config.get("rtspPort") or os.getenv("TAPO_RTSP_PORT", "554")

    config = {
        "cameraLabel": file_config.get("cameraLabel") or os.getenv("TAPO_CAMERA_LABEL", "Tapo Camera"),
        "cameraIp": file_config.get("cameraIp") or os.getenv("TAPO_CAMERA_IP", ""),
        "areaId": file_config.get("areaId") or os.getenv("TAPO_CAMERA_AREA_ID", ""),
        "location": file_config.get("location") or os.getenv("TAPO_CAMERA_LOCATION", ""),
        "cameraUsername": username,
        "streamType": stream_type if stream_type in {"stream1", "stream2"} else "stream1",
        "rtspPort": int(rtsp_port or 554),
        "hasCredentials": bool(username and password),
    }
    if include_secret:
        config["cameraPassword"] = password
    else:
        config["cameraPasswordConfigured"] = bool(password)
    return config


def save_camera_config(body) -> dict:
    current = load_camera_config(include_secret=True)
    password = body.cameraPassword if body.cameraPassword else current.get("cameraPassword", "")
    stream_type = body.streamType if body.streamType in {"stream1", "stream2"} else "stream1"
    rtsp_port = body.rtspPort or 554
    config = {
        "cameraLabel": body.cameraLabel or current.get("cameraLabel") or "Tapo Camera",
        "cameraIp": validate_camera_ip(body.cameraIp) if body.cameraIp else "",
        "areaId": body.areaId or "",
        "location": body.location or "",
        "cameraUsername": body.cameraUsername or current.get("cameraUsername") or "",
        "cameraPassword": password,
        "streamType": stream_type,
        "rtspPort": int(rtsp_port),
    }
    LOCAL_CAMERA_CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return load_camera_config(include_secret=False)


def build_tapo_rtsp_url(camera_ip: str) -> str:
    validated_ip = validate_camera_ip(camera_ip)
    config = load_camera_config(include_secret=True)
    username = (config.get("cameraUsername") or "").strip()
    password = config.get("cameraPassword") or ""
    if not username or not password:
        raise ValueError(
            "Camera account is required. Add the Tapo camera username and password in Admin Camera Settings."
        )

    stream_type = config.get("streamType") if config.get("streamType") in {"stream1", "stream2"} else "stream1"
    rtsp_port = int(config.get("rtspPort") or 554)
    safe_username = quote(username, safe="")
    safe_password = quote(password, safe="")
    return f"rtsp://{safe_username}:{safe_password}@{validated_ip}:{rtsp_port}/{stream_type}"


def build_redacted_camera_stream_label(camera_ip: str) -> str:
    config = load_camera_config(include_secret=False)
    stream_type = config.get("streamType") if config.get("streamType") in {"stream1", "stream2"} else "stream1"
    rtsp_port = int(config.get("rtspPort") or 554)
    return f"rtsp://{camera_ip}:{rtsp_port}/{stream_type}"


def resolve_camera_stream_source(body) -> tuple[str, str, str | None]:
    camera_ip = validate_camera_ip(body.cameraIp) if getattr(body, "cameraIp", None) else None
    url = getattr(body, "url", None)
    if camera_ip:
        label = getattr(body, "label", None) or camera_ip
        return build_tapo_rtsp_url(camera_ip), label, camera_ip
    if url:
        return url, stream_source_label(url), None
    raise ValueError("Please enter the camera IP address.")


def stream_source_label(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme == "demo":
        return f"Demo Camera ({parsed.netloc or 'sample-camera'})"
    host = parsed.netloc or "stream"
    return f"CCTV ({host})"


def ensure_stream_host_reachable(url: str, timeout_seconds: float = 4.0) -> None:
    parsed = urlparse(url.strip())
    if parsed.scheme == "demo":
        return
    host = parsed.hostname
    if not host:
        raise ValueError("Invalid stream URL (missing host).")
    default_port = 554 if parsed.scheme in {"rtsp", "rtsps"} else 443 if parsed.scheme == "https" else 80
    port = parsed.port or default_port
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return
    except OSError as error:
        raise ValueError(
            f"Could not reach camera at {host}:{port}. Make sure this computer is on the same network, "
            "the camera IP is correct, and RTSP/HTTP access is enabled."
        ) from error


def demo_camera_frame(label: str) -> np.ndarray:
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    frame[:, :] = (28, 34, 42)
    cv2.rectangle(frame, (90, 460), (1160, 590), (75, 92, 105), -1)
    cv2.line(frame, (90, 525), (1160, 525), (210, 210, 210), 3)
    cv2.rectangle(frame, (300, 390), (520, 510), (52, 145, 220), -1)
    cv2.rectangle(frame, (565, 398), (760, 512), (60, 175, 95), -1)
    cv2.circle(frame, (350, 510), 32, (20, 20, 20), -1)
    cv2.circle(frame, (480, 510), 32, (20, 20, 20), -1)
    cv2.circle(frame, (610, 512), 32, (20, 20, 20), -1)
    cv2.circle(frame, (725, 512), 32, (20, 20, 20), -1)
    cv2.putText(
        frame,
        label,
        (72, 90),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.2,
        (235, 235, 235),
        3,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        "Demo feed - authorized local test source",
        (72, 135),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (190, 205, 215),
        2,
        cv2.LINE_AA,
    )
    return frame


def grab_frame_from_stream_url(url: str) -> np.ndarray:
    validate_stream_url(url)
    parsed = urlparse(url.strip())
    if parsed.scheme == "demo":
        return demo_camera_frame(stream_source_label(url))
    ensure_stream_host_reachable(url)
    cap = cv2.VideoCapture()
    try:
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.open(url.strip(), cv2.CAP_FFMPEG)
        ok, frame = cap.read()
        if not ok or frame is None:
            raise ValueError(
                "Could not read a frame from the stream. "
                "Check the URL, credentials, and that OpenCV can decode this stream."
            )
        return frame
    finally:
        cap.release()


class LiveCameraMonitor:
    def __init__(
        self,
        *,
        monitor_key: str,
        camera_id: str | None,
        camera_ip: str | None,
        stream_url: str,
        label: str,
        area_id: str | None,
        barangay: str | None,
        road_name: str | None,
        latitude: float | None,
        longitude: float | None,
        location: str,
        redacted_stream_url: str,
        output_base: str,
    ) -> None:
        self.monitor_key = monitor_key
        self.camera_id = camera_id
        self.camera_ip = camera_ip
        self.stream_url = stream_url
        self.label = label
        self.area_id = area_id
        self.barangay = barangay
        self.road_name = road_name
        self.latitude = latitude
        self.longitude = longitude
        self.location = location
        self.redacted_stream_url = redacted_stream_url
        self.output_base = output_base
        self.status = "connecting"
        self.message = "Connecting"
        self.latest_frame: np.ndarray | None = None
        self.latest_result: dict | None = None
        self.last_checked_at: str | None = None
        self.last_frame_at: float | None = None
        self.capture_worker_running = False
        self.detection_worker_running = False
        self.last_detection_label = "Waiting"
        self.last_vehicle_count = 0
        self.last_vehicle_labels: list[str] = []
        self.last_error: str | None = None
        self.last_alert_at = 0.0
        self.last_confidence: float | None = None
        self.last_created_case_id: str | None = None
        self.last_created_notification_id: str | None = None
        self.alert_blocked_reason: str | None = None
        self.active_blocking_case_id: str | None = None
        self.reconnecting = False
        self.hit_window = deque(maxlen=max(3, LIVE_CAMERA_REQUIRED_HITS))
        self.running = False
        self.lock = threading.Lock()
        self.capture_thread: threading.Thread | None = None
        self.detection_thread: threading.Thread | None = None

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.capture_thread = threading.Thread(
            target=self._capture_loop,
            name=f"camera-capture-{self.camera_ip}",
            daemon=True,
        )
        self.detection_thread = threading.Thread(
            target=self._detection_loop,
            name=f"camera-detect-{self.camera_ip}",
            daemon=True,
        )
        self.capture_thread.start()
        self.detection_thread.start()

    def stop(self) -> None:
        self.running = False

    def _set_status(self, status: str, message: str) -> None:
        with self.lock:
            self.status = status
            self.message = message

    def _capture_loop(self) -> None:
        self.capture_worker_running = True
        parsed = urlparse(self.stream_url)
        try:
            if parsed.scheme == "demo":
                while self.running:
                    frame = demo_camera_frame(self.label)
                    with self.lock:
                        self.latest_frame = frame
                        self.last_frame_at = time.time()
                        self.last_error = None
                        if self.status in {"connecting", "reconnecting"}:
                            self.status = "demo"
                            self.message = "Demo Mode"
                    time.sleep(0.08)
                return

            while self.running:
                self._set_status("reconnecting", "Reconnecting")
                with self.lock:
                    self.reconnecting = True
                cap = cv2.VideoCapture()
                try:
                    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
                    cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, max(1, LIVE_CAMERA_BUFFER_SIZE))
                    cap.open(self.stream_url, cv2.CAP_FFMPEG)
                    if not cap.isOpened():
                        with self.lock:
                            self.last_error = "Camera stream could not be opened."
                        time.sleep(2)
                        continue
                    self._set_status("monitoring-live", "Monitoring Live")
                    with self.lock:
                        self.reconnecting = False
                    while self.running:
                        ok, frame = cap.read()
                        if not ok or frame is None:
                            with self.lock:
                                self.last_error = "Camera stream returned no frame."
                            self._set_status("connection-lost", "Connection Lost")
                            break
                        with self.lock:
                            self.latest_frame = frame
                            self.last_frame_at = time.time()
                            self.last_error = None
                finally:
                    cap.release()
                time.sleep(1)
        finally:
            self.capture_worker_running = False
            with self.lock:
                self.reconnecting = False

    def seed_first_frame(self, frame: np.ndarray) -> None:
        with self.lock:
            self.latest_frame = frame.copy()
            self.last_frame_at = time.time()
            self.last_error = None
            self.reconnecting = False
            if self.status in {"connecting", "reconnecting"}:
                self.status = "monitoring-live"
                self.message = "Monitoring Live"

    def latest_jpeg(self) -> bytes | None:
        with self.lock:
            frame = None if self.latest_frame is None else self.latest_frame.copy()
        if frame is None:
            return None
        ok, encoded = cv2.imencode(
            ".jpg",
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), LIVE_CAMERA_JPEG_QUALITY],
        )
        return encoded.tobytes() if ok else None

    def mjpeg_stream(self):
        delay = 1 / max(1, LIVE_CAMERA_PREVIEW_FPS)
        while self.running:
            image_bytes = self.latest_jpeg()
            if image_bytes is None:
                time.sleep(delay)
                continue
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Cache-Control: no-store\r\n\r\n"
                + image_bytes
                + b"\r\n"
            )
            time.sleep(delay)

    def snapshot_status(self) -> dict:
        blocking_case = find_unresolved_camera_case(
            self.camera_ip,
            self.camera_id,
            self.label,
            area_id=self.area_id or "demo",
            location=self.location,
            block_seconds=LIVE_CAMERA_DUPLICATE_CASE_BLOCK_SECONDS,
        )
        with self.lock:
            result = self.latest_result
            latest_frame_age = (
                time.time() - self.last_frame_at
                if self.last_frame_at is not None
                else None
            )
            status = self.status
            message = self.message
            frame_width = int(self.latest_frame.shape[1]) if self.latest_frame is not None else None
            frame_height = int(self.latest_frame.shape[0]) if self.latest_frame is not None else None
            latest_frame_url = (
                f"{self.output_base}/api/cameras/"
                f"{quote(self.camera_id or self.camera_ip or self.monitor_key, safe='')}/latest-frame.jpg"
                if self.latest_frame is not None
                else None
            )
            if (
                latest_frame_age is not None
                and latest_frame_age > LIVE_CAMERA_FREEZE_TIMEOUT_SECONDS
                and status in {"monitoring-live", "possible-crash-detected"}
            ):
                status = "connection-lost"
                message = "Connection Lost"
            return {
                "monitorKey": self.monitor_key,
                "cameraIp": self.camera_ip,
                "cameraId": self.camera_id,
                "label": self.label,
                "streamUrlConfigured": bool(self.stream_url),
                "cameraConnected": self.latest_frame is not None and status != "connection-lost",
                "monitoringLive": status in {"monitoring-live", "possible-crash-detected", "demo"},
                "latestFrameReceived": self.latest_frame is not None,
                "latestFrameAvailable": self.latest_frame is not None,
                "latestFrameUrl": latest_frame_url,
                "frameUrl": latest_frame_url,
                "previewUrl": latest_frame_url,
                "frameWidth": frame_width,
                "frameHeight": frame_height,
                "lastFrameTimestamp": (
                    datetime.fromtimestamp(self.last_frame_at).isoformat()
                    if self.last_frame_at is not None
                    else None
                ),
                "lastFrameAt": (
                    datetime.fromtimestamp(self.last_frame_at).isoformat()
                    if self.last_frame_at is not None
                    else None
                ),
                "detectionWorkerRunning": self.detection_worker_running,
                "detectionRunning": self.detection_worker_running,
                "status": status,
                "message": message,
                "lastCheckedAt": self.last_checked_at,
                "lastDetectionAt": self.last_checked_at,
                "confidence": self.last_confidence,
                "lastConfidence": self.last_confidence,
                "lastDetectionLabel": self.last_detection_label,
                "lastResult": self.last_detection_label,
                "vehicleBoxCount": self.last_vehicle_count,
                "vehicleLabels": self.last_vehicle_labels,
                "activePendingCase": bool(blocking_case),
                "activeCaseId": (blocking_case or {}).get("caseId"),
                "activeBlockingCaseId": self.active_blocking_case_id or (blocking_case or {}).get("caseId"),
                "activeBlockingStatus": (blocking_case or {}).get("status"),
                "alertBlockedReason": self.alert_blocked_reason,
                "lastCreatedCaseId": self.last_created_case_id,
                "lastCreatedNotificationId": self.last_created_notification_id,
                "lastError": self.last_error,
                "reconnecting": self.reconnecting or status == "reconnecting",
                "latestResult": result,
                "previewAvailable": self.latest_frame is not None,
                "existingCaseMessage": (
                    self.alert_blocked_reason
                    if result and result.get("existingCase")
                    else None
                ),
            }

    def analyze_current_frame(self, *, manual: bool = False) -> dict:
        with self.lock:
            frame = None if self.latest_frame is None else self.latest_frame.copy()
            last_frame_at = self.last_frame_at
        if frame is None:
            raise ValueError("No live camera frame is available for detection yet.")
        if (
            last_frame_at is not None
            and time.time() - last_frame_at > LIVE_CAMERA_FREEZE_TIMEOUT_SECONDS
        ):
            raise ValueError("Latest camera frame is stale; waiting for reconnect.")

        detection_frame = cv2.resize(
            frame,
            (LIVE_CAMERA_FRAME_WIDTH, LIVE_CAMERA_FRAME_HEIGHT),
            interpolation=cv2.INTER_AREA,
        )
        # Upload detection passes OpenCV-decoded BGR arrays directly to YOLO.
        # Keep the same BGR pipeline here for parity with image uploads.
        results = model.predict(detection_frame, verbose=False)
        detections, accident_detected, confidence = extract_detections(results)
        resized_vehicle_boxes = detect_vehicle_boxes(detection_frame, fallback_results=results)
        response_boxes = scale_detection_boxes(
            resized_vehicle_boxes,
            scale_x=frame.shape[1] / max(1, detection_frame.shape[1]),
            scale_y=frame.shape[0] / max(1, detection_frame.shape[0]),
        )
        checked_at = datetime.now().isoformat()
        best_detection_score = (
            max((item.get("score", 0.0) for item in detections), default=0.0)
            if detections
            else 0.0
        )
        visible_confidence = confidence if accident_detected else best_detection_score
        best_label = (
            max(detections, key=lambda item: item.get("score", 0)).get("label", "No labels")
            if detections
            else "No labels"
        )
        threshold_hit = passes_crash_alert_threshold(
            confidence,
            accident_detected=accident_detected,
        )

        if not manual:
            self.hit_window.append(threshold_hit)
            alert_ready = (
                sum(1 for hit in self.hit_window if hit)
                >= LIVE_CAMERA_REQUIRED_HITS
            )
        else:
            alert_ready = threshold_hit

        result_payload = {
            "success": True,
            "accident_detected": False,
            "caseId": None,
            "confidence": visible_confidence,
            "media_type": "image",
            "timestamp": checked_at,
            "createdAt": checked_at,
            "location": self.location,
            "detections": detections,
            "boxes": response_boxes,
            "annotated_media_url": None,
            "annotated_media_available": False,
            "annotated_media_previewable": False,
            "lastDetectionLabel": best_label,
            "thresholdHit": threshold_hit,
            "requiredThreshold": LIVE_CAMERA_CONFIDENCE_THRESHOLD,
            "threshold": LIVE_CAMERA_CONFIDENCE_THRESHOLD,
            "passedThreshold": threshold_hit,
            "persistenceStatus": "not_attempted",
            "persistenceSkippedReason": None,
            "triggerStatus": "camera_detection",
            "cameraId": self.camera_id,
            "sourceCamera": self.label,
            "areaId": self.area_id or "demo",
            "accidentDetected": False,
            "rawCrashConfidence": confidence,
            "vehicleBoxCount": len(response_boxes),
            "lastCreatedCaseId": self.last_created_case_id,
            "lastCreatedNotificationId": self.last_created_notification_id,
            "alertBlockedReason": None,
            "activeBlockingCaseId": None,
            "activeBlockingStatus": None,
            "vehicleLabels": [
                f"{box['label']} {box['confidence']:.0%}"
                for box in response_boxes
            ],
        }
        status = "monitoring-live"
        message = "Monitoring Live"

        def save_detection_snapshot() -> tuple[Path | None, str | None, Path | None, str | None]:
            key_frame_name = f"live_camera_keyframe_{uuid.uuid4().hex[:8]}.jpg"
            key_frame_path = OUTPUTS / key_frame_name
            key_frame_write_succeeded = bool(cv2.imwrite(str(key_frame_path), frame))
            key_frame_url = (
                build_output_url_from_base(self.output_base, key_frame_name)
                if key_frame_write_succeeded
                else None
            )

            annotated_name = f"live_camera_{uuid.uuid4().hex[:8]}.jpg"
            annotated_path = OUTPUTS / annotated_name
            annotated_frame = draw_detection_boxes_overlay(frame, response_boxes)
            annotated_write_succeeded = bool(cv2.imwrite(str(annotated_path), annotated_frame))
            annotated_url = (
                build_output_url_from_base(self.output_base, annotated_name)
                if annotated_write_succeeded
                else None
            )

            if not key_frame_write_succeeded:
                log_stream(f"Failed to save live camera key frame: {key_frame_path.name}")
            if not annotated_write_succeeded:
                log_stream(f"Failed to save live camera evidence frame: {annotated_path.name}")

            return (
                key_frame_path if key_frame_write_succeeded else None,
                key_frame_url,
                annotated_path if annotated_write_succeeded else None,
                annotated_url,
            )

        if alert_ready:
            existing_case = find_unresolved_camera_case(
                self.camera_ip,
                self.camera_id,
                self.label,
                area_id=self.area_id or "demo",
                location=self.location,
                block_seconds=LIVE_CAMERA_DUPLICATE_CASE_BLOCK_SECONDS,
            )
            cooldown_ready = (
                time.time() - self.last_alert_at
                >= LIVE_CAMERA_ALERT_COOLDOWN_SECONDS
            )
            if existing_case:
                (
                    duplicate_key_frame_path,
                    duplicate_key_frame_url,
                    duplicate_annotated_path,
                    duplicate_annotated_url,
                ) = save_detection_snapshot()
                refreshed_case = replace_case_evidence(
                    existing_case["caseId"],
                    key_frame_path=duplicate_key_frame_path or duplicate_annotated_path,
                    thumbnail_path=duplicate_key_frame_path or duplicate_annotated_path,
                    annotated_path=duplicate_annotated_path,
                    boxes=response_boxes,
                    detected_at=checked_at,
                )
                existing_case = refreshed_case or existing_case
                blocked_reason = (
                    f"Alert blocked because an active case already exists for this same recent incident: {existing_case['caseId']}"
                )
                result_payload.update(
                    {
                        "accident_detected": True,
                        "accidentDetected": True,
                        "caseId": existing_case["caseId"],
                        "existingCase": True,
                        "persistenceStatus": "blocked_existing_case",
                        "activeBlockingCaseId": existing_case["caseId"],
                        "activeBlockingStatus": existing_case["status"],
                        "alertBlockedReason": blocked_reason,
                        "keyFramePath": existing_case.get("keyFramePath"),
                        "annotatedPath": existing_case.get("annotatedPath"),
                        "annotated_media_url": duplicate_annotated_url or duplicate_key_frame_url,
                        "annotated_media_available": bool(duplicate_annotated_url or duplicate_key_frame_url),
                        "annotated_media_previewable": bool(duplicate_annotated_url or duplicate_key_frame_url),
                        "annotated_media_download_url": duplicate_annotated_url or duplicate_key_frame_url,
                        "annotated_key_frame_url": duplicate_key_frame_url or duplicate_annotated_url,
                    }
                )
                status = "possible-crash-detected"
                message = blocked_reason
            elif cooldown_ready:
                key_frame_path, key_frame_url, annotated_path, annotated_url = save_detection_snapshot()
                sqlite_case = persist_sqlite_crash_case(
                    media_type="image",
                    source_file=self.label,
                    confidence=confidence,
                    timestamp=checked_at,
                    location=self.location,
                    original_path=None,
                    annotated_url=annotated_url,
                    annotated_download_url=annotated_url,
                    key_frame_url=key_frame_url or annotated_url,
                    trigger_status="camera_detection",
                    source_camera=self.label,
                    area_id=self.area_id or "demo",
                    camera_ip=self.camera_ip,
                    boxes=response_boxes,
                    camera_id=self.camera_id,
                    camera_name=self.label,
                    barangay=self.barangay,
                    road_name=self.road_name,
                    latitude=self.latitude,
                    longitude=self.longitude,
                )
                created_notification_id = (
                    sqlite_case.get("createdNotificationId")
                    if sqlite_case and sqlite_case.get("casePersistenceStatus") == "created"
                    else None
                )
                persistence_status = (
                    "failed_missing_notification"
                    if sqlite_case
                    and sqlite_case.get("casePersistenceStatus") == "created"
                    and not created_notification_id
                    else sqlite_case.get("casePersistenceStatus")
                    if sqlite_case
                    else "failed"
                )
                persistence_skipped_reason = (
                    "Crash case was saved, but no notification id was returned."
                    if persistence_status == "failed_missing_notification"
                    else "Crash was detected, but the backend could not save a review case."
                    if sqlite_case is None
                    else sqlite_case.get("alertBlockedReason")
                )
                log_stream(
                    "Background camera persistence result: "
                    f"status={persistence_status} caseId={(sqlite_case or {}).get('caseId')} "
                    f"notificationId={created_notification_id} createdAt={checked_at} "
                    f"areaId={self.area_id or 'demo'} cameraId={self.camera_id or ''} "
                    f"skipReason={persistence_skipped_reason or ''}"
                )
                self.last_alert_at = time.time()
                result_payload.update(
                    {
                        "accident_detected": True,
                        "accidentDetected": True,
                        "caseId": sqlite_case["caseId"] if sqlite_case else None,
                        "notificationId": created_notification_id,
                        "status": sqlite_case.get("status") if sqlite_case else None,
                        "casePersistenceStatus": (
                            sqlite_case.get("casePersistenceStatus") if sqlite_case else None
                        ),
                        "persistenceStatus": persistence_status,
                        "persistenceSkippedReason": persistence_skipped_reason,
                        "lastCreatedCaseId": (
                            sqlite_case["caseId"]
                            if sqlite_case and sqlite_case.get("casePersistenceStatus") == "created"
                            else self.last_created_case_id
                        ),
                        "lastCreatedNotificationId": (
                            sqlite_case.get("createdNotificationId")
                            if sqlite_case and sqlite_case.get("casePersistenceStatus") == "created"
                            else self.last_created_notification_id
                        ),
                        "alertBlockedReason": (
                            sqlite_case.get("alertBlockedReason") if sqlite_case else None
                        ),
                        "activeBlockingCaseId": (
                            sqlite_case.get("activeBlockingCaseId") if sqlite_case else None
                        ),
                        "activeBlockingStatus": (
                            sqlite_case.get("activeBlockingStatus") if sqlite_case else None
                        ),
                        "keyFramePath": sqlite_case.get("keyFramePath") if sqlite_case else None,
                        "annotatedPath": sqlite_case.get("annotatedPath") if sqlite_case else None,
                        "annotated_media_url": annotated_url,
                        "annotated_media_available": bool(annotated_url),
                        "annotated_media_previewable": bool(annotated_url),
                        "annotated_media_download_url": annotated_url,
                        "annotated_key_frame_url": key_frame_url or annotated_url,
                        "createdAt": checked_at,
                    }
                )
                status = "possible-crash-detected"
                message = "Possible Crash Detected"
            else:
                result_payload["persistenceStatus"] = "skipped"
                result_payload["persistenceSkippedReason"] = "Detection did not create alert because alert cooldown is active."
                result_payload["alertBlockedReason"] = "Possible crash detected; alert cooldown is active."
                message = result_payload["alertBlockedReason"]
        elif accident_detected and not threshold_hit:
            result_payload["persistenceStatus"] = "skipped"
            result_payload["persistenceSkippedReason"] = (
                "Detection did not create alert because confidence is below the required 20% threshold."
            )
        else:
            result_payload["persistenceStatus"] = "skipped"
            result_payload["persistenceSkippedReason"] = (
                "Detection did not create alert because no crash was detected."
            )

        with self.lock:
            self.last_checked_at = checked_at
            self.last_confidence = visible_confidence
            self.last_detection_label = best_label
            self.alert_blocked_reason = result_payload.get("alertBlockedReason")
            self.active_blocking_case_id = result_payload.get("activeBlockingCaseId")
            if result_payload.get("lastCreatedCaseId"):
                self.last_created_case_id = result_payload.get("lastCreatedCaseId")
            if result_payload.get("lastCreatedNotificationId"):
                self.last_created_notification_id = result_payload.get("lastCreatedNotificationId")
            self.last_vehicle_count = len(response_boxes)
            self.last_vehicle_labels = [
                f"{box['label']} {box['confidence']:.0%}"
                for box in response_boxes
            ]
            self.latest_result = result_payload
            self.last_error = None
            if self.status not in {"connection-lost", "reconnecting"}:
                self.status = status
                self.message = message
        return result_payload

    def _detection_loop(self) -> None:
        self.detection_worker_running = True
        interval_s = max(0.2, LIVE_CAMERA_DETECTION_INTERVAL_MS / 1000)
        try:
            while self.running:
                time.sleep(interval_s)
                try:
                    self.analyze_current_frame(manual=False)
                except ValueError:
                    continue
                except Exception as error:
                    with self.lock:
                        self.last_error = str(error)
                    log_stream(f"Live camera detection failed: {error}")
        finally:
            self.detection_worker_running = False


LIVE_CAMERA_WORKERS: dict[str, LiveCameraMonitor] = {}
LIVE_CAMERA_WORKERS_LOCK = threading.Lock()


def live_camera_stream_key(stream_url: str | None) -> str | None:
    if not stream_url:
        return None
    return f"stream:{hashlib.sha1(stream_url.strip().encode('utf-8')).hexdigest()[:16]}"


def live_camera_worker_keys(
    *,
    camera_id: str | None,
    camera_ip: str | None,
    stream_url: str | None,
    label: str | None = None,
) -> list[str]:
    keys: list[str] = []
    for candidate in (
        camera_id,
        camera_ip,
        live_camera_stream_key(stream_url),
        f"source:{label.strip().lower()}" if label and label.strip() else None,
    ):
        if candidate and candidate not in keys:
            keys.append(candidate)
    return keys


def live_camera_primary_key(
    *,
    camera_id: str | None,
    camera_ip: str | None,
    stream_url: str | None,
    label: str | None = None,
) -> str:
    keys = live_camera_worker_keys(
        camera_id=camera_id,
        camera_ip=camera_ip,
        stream_url=stream_url,
        label=label,
    )
    if keys:
        return keys[0]
    return f"stream:{uuid.uuid4().hex}"


def start_live_camera_monitor(
    *,
    camera_id: str | None,
    camera_ip: str | None,
    stream_url: str,
    label: str,
    area_id: str | None,
    barangay: str | None,
    road_name: str | None,
    latitude: float | None,
    longitude: float | None,
    location: str,
    redacted_stream_url: str,
    output_base: str,
    first_frame: np.ndarray | None = None,
) -> LiveCameraMonitor:
    with LIVE_CAMERA_WORKERS_LOCK:
        keys = live_camera_worker_keys(
            camera_id=camera_id,
            camera_ip=camera_ip,
            stream_url=stream_url,
            label=label,
        )
        primary_key = live_camera_primary_key(
            camera_id=camera_id,
            camera_ip=camera_ip,
            stream_url=stream_url,
            label=label,
        )
        existing_workers = {
            LIVE_CAMERA_WORKERS[key]
            for key in keys
            if key in LIVE_CAMERA_WORKERS
        }
        for existing in existing_workers:
            existing.stop()
        for key, worker in list(LIVE_CAMERA_WORKERS.items()):
            if worker in existing_workers:
                LIVE_CAMERA_WORKERS.pop(key, None)
        worker = LiveCameraMonitor(
            monitor_key=primary_key,
            camera_id=camera_id,
            camera_ip=camera_ip,
            stream_url=stream_url,
            label=label,
            area_id=area_id,
            barangay=barangay,
            road_name=road_name,
            latitude=latitude,
            longitude=longitude,
            location=location,
            redacted_stream_url=redacted_stream_url,
            output_base=output_base,
        )
        for key in keys or [primary_key]:
            LIVE_CAMERA_WORKERS[key] = worker
        if primary_key not in LIVE_CAMERA_WORKERS:
            LIVE_CAMERA_WORKERS[primary_key] = worker
        if first_frame is not None:
            worker.seed_first_frame(first_frame)
        worker.start()
        return worker


def get_live_camera_monitor(identifier: str) -> LiveCameraMonitor | None:
    if identifier in LIVE_CAMERA_WORKERS:
        return LIVE_CAMERA_WORKERS[identifier]
    try:
        return LIVE_CAMERA_WORKERS.get(validate_camera_ip(identifier))
    except ValueError:
        return None


def get_requested_or_default_monitor(camera_ip: str | None = None) -> LiveCameraMonitor | None:
    if camera_ip:
        return get_live_camera_monitor(camera_ip)
    with LIVE_CAMERA_WORKERS_LOCK:
        unique_workers = list({id(worker): worker for worker in LIVE_CAMERA_WORKERS.values()}.values())
        if len(unique_workers) == 1:
            return unique_workers[0]
    return None


def image_detection_response_from_bgr(
    output_base: str,
    decoded_image: np.ndarray,
    *,
    incident_media_type: str,
    api_media_type: str,
    source_file: str,
    location_label: str,
    log_fn,
    original_path: Path | None = None,
    area_id: str | None = None,
    trigger_status: str | None = None,
    source_camera: str | None = None,
    camera_ip: str | None = None,
    camera_id: str | None = None,
    camera_name: str | None = None,
    barangay: str | None = None,
    road_name: str | None = None,
    responder_id: str | None = None,
) -> dict:
    log_fn(
        "Image array ready "
        f"width={decoded_image.shape[1]} height={decoded_image.shape[0]}"
    )

    try:
        results = model.predict(decoded_image, verbose=False)
    except Exception as error:
        log_fn(f"YOLO inference failed: {error}")
        raise HTTPException(
            status_code=500,
            detail="Image detection failed during model inference.",
        ) from error

    detections, accident_detected, best_confidence = extract_detections(results)
    response_boxes = detect_vehicle_boxes(decoded_image, fallback_results=results)
    log_fn(
        "Detection complete: "
        f"{len(detections)} objects detected, "
        f"accident={accident_detected}, confidence={best_confidence:.2%}"
    )

    annotated_media_url = None
    annotated_media_available = False
    processing_notes = None
    annotated_media_warning = None
    output_name = f"result_{uuid.uuid4().hex[:8]}.jpg"
    output_path = OUTPUTS / output_name

    try:
        annotated_image = draw_detection_boxes_overlay(decoded_image, response_boxes)
        write_succeeded = bool(cv2.imwrite(str(output_path), annotated_image))
    except Exception as error:
        write_succeeded = False
        log_fn(f"Annotated image generation failed: {error}")

    if write_succeeded and output_path.exists() and output_path.stat().st_size > 0:
        annotated_media_url = build_output_url_from_base(output_base, output_name)
        annotated_media_available = True
        log_fn(f"Annotated image saved to: {output_path}")
    else:
        if output_path.exists():
            output_path.unlink()
        annotated_media_warning = (
            "Image detection completed, but the backend could not save an annotated preview image."
        )
        processing_notes = (
            "Detection succeeded, but no annotated output image was available for browser preview."
        )
        log_fn("Annotated image write failed; returning success without preview output")

    timestamp = datetime.now().isoformat()
    is_camera_detection = (trigger_status or incident_media_type == "cctv") == "camera_detection"
    required_threshold = CRASH_ALERT_CONFIDENCE_THRESHOLD
    passed_threshold = passes_crash_alert_threshold(
        best_confidence,
        accident_detected=accident_detected,
    )
    persistence_status = "not_attempted"
    persistence_skipped_reason = None

    create_incident_record(
        media_type=incident_media_type,
        source_file=source_file,
        accident_detected=accident_detected,
        confidence=best_confidence,
        timestamp=timestamp,
        location=location_label,
    )

    sqlite_case = None
    if not accident_detected:
        persistence_status = "skipped"
        persistence_skipped_reason = "Detection did not create alert because no crash was detected."
    elif not passed_threshold:
        persistence_status = "skipped"
        persistence_skipped_reason = (
            "Detection did not create alert because confidence is below the required 20% threshold."
        )
    else:
        case_area_id = area_id or ("demo" if is_camera_detection else None)
        sqlite_case = persist_sqlite_crash_case(
            media_type=api_media_type,
            source_file=source_file,
            confidence=best_confidence,
            timestamp=timestamp,
            location=location_label,
            original_path=original_path,
            annotated_url=annotated_media_url,
            annotated_download_url=annotated_media_url,
            key_frame_url=annotated_media_url,
            trigger_status=trigger_status or ("camera_detection" if incident_media_type == "cctv" else "upload_detection"),
            source_camera=source_camera or source_file,
            area_id=case_area_id,
            camera_ip=camera_ip,
            camera_id=camera_id,
            camera_name=camera_name or source_camera or source_file,
            barangay=barangay or case_area_id,
            road_name=road_name,
            responder_id=responder_id,
            boxes=response_boxes,
        )
        persistence_status = (
            sqlite_case.get("casePersistenceStatus")
            if sqlite_case
            else "failed"
        )
        if sqlite_case is None:
            persistence_skipped_reason = "Crash was detected, but the backend could not save a review case."
        elif sqlite_case.get("casePersistenceStatus") != "created":
            persistence_skipped_reason = sqlite_case.get("alertBlockedReason")
        elif not sqlite_case.get("createdNotificationId"):
            persistence_status = "failed_missing_notification"
            persistence_skipped_reason = "Crash case was saved, but no notification id was returned."

    created_notification_id = (
        sqlite_case.get("createdNotificationId")
        if sqlite_case and persistence_status == "created"
        else None
    )
    if is_camera_detection:
        log_fn(
            "Camera persistence result: "
            f"accident={accident_detected} confidence={best_confidence:.2%} "
            f"threshold={required_threshold if required_threshold is not None else 'n/a'} "
            f"passed={passed_threshold} status={persistence_status} "
            f"caseId={(sqlite_case or {}).get('caseId')} "
            f"notificationId={created_notification_id} createdAt={timestamp} "
            f"skipReason={persistence_skipped_reason or ''} "
            f"blockedCase={(sqlite_case or {}).get('activeBlockingCaseId') or ''}"
        )

    return {
        "success": True,
        "accident_detected": accident_detected,
        "accidentDetected": accident_detected,
        "caseId": sqlite_case["caseId"] if sqlite_case else None,
        "notificationId": created_notification_id,
        "status": sqlite_case.get("status") if sqlite_case else None,
        "confidence": best_confidence,
        "lastConfidence": best_confidence,
        "rawCrashConfidence": best_confidence,
        "requiredThreshold": required_threshold,
        "threshold": required_threshold,
        "passedThreshold": passed_threshold,
        "persistenceStatus": persistence_status,
        "persistenceSkippedReason": persistence_skipped_reason,
        "triggerStatus": trigger_status or ("camera_detection" if incident_media_type == "cctv" else "upload_detection"),
        "cameraId": camera_id,
        "cameraName": camera_name or source_camera or source_file,
        "sourceCamera": source_camera or source_file,
        "areaId": area_id or ("demo" if is_camera_detection else None),
        "media_type": api_media_type,
        "timestamp": timestamp,
        "createdAt": timestamp,
        "location": location_label,
        "detections": detections,
        "boxes": response_boxes,
        "keyFramePath": sqlite_case.get("keyFramePath") if sqlite_case else None,
        "annotatedPath": sqlite_case.get("annotatedPath") if sqlite_case else None,
        "casePersistenceStatus": sqlite_case.get("casePersistenceStatus") if sqlite_case else persistence_status,
        "alertBlockedReason": sqlite_case.get("alertBlockedReason") if sqlite_case else None,
        "activeBlockingCaseId": sqlite_case.get("activeBlockingCaseId") if sqlite_case else None,
        "activeBlockingStatus": sqlite_case.get("activeBlockingStatus") if sqlite_case else None,
        "annotated_media_url": annotated_media_url,
        "annotated_media_available": annotated_media_available,
        "annotated_media_previewable": annotated_media_available,
        "annotated_media_download_url": annotated_media_url,
        "annotated_media_format": get_output_format(output_name)
        if annotated_media_available
        else None,
        "annotated_media_warning": annotated_media_warning,
        "processing_notes": processing_notes,
    }


class StreamFrameIn(BaseModel):
    url: str | None = Field(None, min_length=8, max_length=2048)
    cameraId: str | None = None
    label: str | None = None
    cameraIp: str | None = None
    areaId: str | None = None
    location: str | None = None
    cameraType: str | None = None


class AuthRegisterIn(BaseModel):
    email: str
    password: str
    displayName: str | None = None


class AuthLoginIn(BaseModel):
    email: str
    password: str


class CameraConnectionIn(BaseModel):
    cameraIp: str
    cameraId: str | None = None
    label: str | None = None
    areaId: str | None = None
    location: str | None = None


class CameraRecordIn(BaseModel):
    cameraId: str | None = None
    label: str
    cameraIp: str | None = None
    streamUrl: str | None = None
    areaId: str
    barangay: str | None = None
    roadName: str | None = None
    locationDescription: str | None = None
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    cameraType: str | None = None
    status: str | None = None
    isActive: bool = True
    detectionEnabled: bool = True


class CameraAssignmentIn(BaseModel):
    responderId: str
    cameraId: str | None = None
    areaId: str | None = None
    role: str | None = None
    status: str | None = None


class CameraSettingsIn(BaseModel):
    cameraLabel: str | None = None
    cameraIp: str | None = None
    areaId: str | None = None
    location: str | None = None
    cameraUsername: str | None = None
    cameraPassword: str | None = None
    streamType: str | None = None
    rtspPort: int | None = None


class CrashCaseActionIn(BaseModel):
    action: str
    actorId: str | None = None
    notes: str | None = None


class DebugCameraAlertIn(BaseModel):
    cameraId: str | None = "DEVICE-LIVE-CAMERA"
    cameraIp: str | None = None
    sourceCamera: str | None = "Device Live Camera"
    areaId: str | None = "demo"
    location: str | None = "Device Live Camera"
    confidence: float | None = 0.91


def create_video_writer(width: int, height: int, fps: float):
    """
    Try browser-friendly MP4 codecs first, then fall back to AVI-only codecs.
    Returns metadata about the opened writer plus whether the output should be
    exposed to the browser preview flow.
    """
    output_stem = f"detected_video_{uuid.uuid4().hex[:8]}"
    candidates = (
        {"codec": "avc1", "suffix": ".mp4", "browser_preview_safe": True},
        {"codec": "H264", "suffix": ".mp4", "browser_preview_safe": True},
        {"codec": "mp4v", "suffix": ".mp4", "browser_preview_safe": True},
        {"codec": "MJPG", "suffix": ".avi", "browser_preview_safe": False},
    )

    for candidate in candidates:
        output_name = f"{output_stem}{candidate['suffix']}"
        output_path = OUTPUTS / output_name
        log_video(
            "Trying output writer "
            f"codec={candidate['codec']} suffix={candidate['suffix']}"
        )
        try:
            writer = cv2.VideoWriter(
                str(output_path),
                cv2.VideoWriter_fourcc(*candidate["codec"]),
                fps,
                (width, height),
            )
            if writer is not None and writer.isOpened():
                return {
                    "writer": writer,
                    "output_path": output_path,
                    "output_name": output_name,
                    "codec": candidate["codec"],
                    "browser_preview_safe": candidate["browser_preview_safe"],
                }
            if writer is not None:
                writer.release()
            log_video(f"Codec {candidate['codec']} could not open a writer")
            if output_path.exists():
                output_path.unlink()
        except Exception as error:
            log_video(f"Codec {candidate['codec']} failed: {error}")
            if output_path.exists():
                output_path.unlink()
            continue

    log_video(
        "Warning: all video codecs failed. Annotated output will not be generated."
    )
    return {
        "writer": None,
        "output_path": None,
        "output_name": None,
        "codec": None,
        "browser_preview_safe": False,
    }


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def validate_auth_email(email: str) -> str:
    normalized = normalize_email(email)
    if not EMAIL_RE.match(normalized):
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    return normalized


def validate_auth_password(password: str) -> str:
    if len(password or "") < PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {PASSWORD_MIN_LENGTH} characters.",
        )
    return password


def auth_response(profile: dict, token: str | None = None) -> dict:
    payload = {"user": safe_user(profile)}
    if token:
        payload["token"] = token
    return payload


@app.post("/api/auth/register")
def auth_register(body: AuthRegisterIn):
    email = validate_auth_email(body.email)
    password = validate_auth_password(body.password)
    if get_user_profile_by_email(email) is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    timestamp = datetime.now().isoformat()
    password_hash, password_salt = hash_password(password)
    profile = upsert_user_profile(
        {
            "uid": f"USR-{uuid.uuid4().hex}",
            "email": email,
            "displayName": (body.displayName or email.split("@", 1)[0]).strip(),
            "role": "user",
            "areaId": None,
            "passwordHash": password_hash,
            "passwordSalt": password_salt,
            "isActive": True,
            "createdAt": timestamp,
            "updatedAt": timestamp,
        }
    )
    token = create_session_token(profile)
    return auth_response(profile, token)


@app.post("/api/auth/login")
def auth_login(body: AuthLoginIn):
    email = validate_auth_email(body.email)
    profile = get_user_profile_by_email(email)
    if profile is None or not verify_password(body.password, profile.get("passwordHash"), profile.get("passwordSalt")):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not bool(profile.get("isActive", 1)):
        raise HTTPException(status_code=403, detail="This account is inactive.")

    timestamp = datetime.now().isoformat()
    update_user_last_login(profile["uid"], timestamp)
    profile = get_user_profile(profile["uid"]) or profile
    token = create_session_token(profile)
    return auth_response(profile, token)


@app.get("/api/auth/me")
def auth_me(request: Request):
    user = verify_firebase_user(request)
    return {"user": user["profile"]}


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
    }


@app.get("/api/crash-cases")
def api_crash_cases(
    request: Request,
    status: str | None = None,
    areaId: str | None = None,
    search: str | None = None,
    date: str | None = None,
    fromDate: str | None = None,
    toDate: str | None = None,
    sort: str = "newest",
    limit: int = 100,
    offset: int = 0,
):
    require_dashboard_access(request)
    return list_crash_cases(
        status=status,
        area_id=areaId,
        search=search,
        date=date,
        from_date=fromDate,
        to_date=toDate,
        sort=sort,
        limit=max(1, min(limit, 200)),
        offset=max(0, offset),
    )


@app.get("/api/crash-cases/{case_id}")
def api_crash_case(case_id: str, request: Request):
    require_dashboard_access(request)
    case_item = get_crash_case(case_id)
    if case_item is None:
        raise HTTPException(status_code=404, detail="Crash case not found.")
    return case_item


@app.post("/api/crash-cases/{case_id}/actions")
def api_crash_case_action(case_id: str, request: Request, body: CrashCaseActionIn):
    require_dashboard_access(request)
    try:
        return apply_action(case_id, body.action, body.actorId, body.notes)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Crash case not found.") from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/analytics/summary")
def api_analytics_summary(request: Request):
    require_admin(request)
    return summary()


@app.get("/api/analytics/monthly")
def api_analytics_monthly(request: Request):
    require_admin(request)
    return monthly_trend()


@app.get("/api/analytics/areas")
def api_analytics_areas(request: Request):
    require_admin(request)
    return cases_by_area()


def validate_camera_record_payload(body: CameraRecordIn) -> None:
    if not body.label.strip():
        raise HTTPException(status_code=400, detail="Camera name is required.")
    if not body.areaId.strip():
        raise HTTPException(status_code=400, detail="Area or barangay is required.")
    if not body.cameraIp and not body.streamUrl:
        raise HTTPException(status_code=400, detail="Either camera IP address or stream URL is required.")
    if body.cameraIp:
        try:
            validate_camera_ip(body.cameraIp)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
    if body.streamUrl:
        try:
            validate_stream_url(body.streamUrl)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
    if body.latitude is not None and not (-90 <= body.latitude <= 90):
        raise HTTPException(status_code=400, detail="Latitude must be between -90 and 90.")
    if body.longitude is not None and not (-180 <= body.longitude <= 180):
        raise HTTPException(status_code=400, detail="Longitude must be between -180 and 180.")


def require_camera_record_editor(request: Request, area_id: str) -> dict:
    user = require_dashboard_access(request)
    if user["role"] == "admin":
        return user
    area_scope = get_user_area_scope(user)
    if area_scope and area_id == area_scope:
        return user
    raise HTTPException(
        status_code=403,
        detail="Responders can only save cameras for their assigned area.",
    )


def camera_record_payload(body: CameraRecordIn, camera_ip: str | None) -> dict:
    return {
        "cameraId": body.cameraId,
        "label": body.label.strip(),
        "cameraIp": camera_ip,
        "areaId": body.areaId,
        "barangay": body.barangay or body.areaId,
        "roadName": body.roadName,
        "locationDescription": body.locationDescription,
        "location": body.location or body.locationDescription or body.roadName,
        "latitude": body.latitude,
        "longitude": body.longitude,
        "streamUrl": body.streamUrl or (build_redacted_camera_stream_label(camera_ip) if camera_ip else None),
        "cameraType": body.cameraType or ("Tapo RTSP" if camera_ip else "Stream"),
        "status": body.status or "offline",
        "isActive": body.isActive,
        "detectionEnabled": body.detectionEnabled,
    }


@app.get("/api/cameras")
def api_cameras(request: Request):
    user = verify_firebase_user(request)
    return list_cameras(
        role=user["role"],
        user_id=user["uid"],
        area_id=user.get("areaId"),
        include_inactive=user["role"] == "admin",
    )


@app.post("/api/cameras")
def api_create_camera(request: Request, body: CameraRecordIn):
    validate_camera_record_payload(body)
    require_camera_record_editor(request, body.areaId)
    camera_ip = validate_camera_ip(body.cameraIp) if body.cameraIp else None
    return upsert_camera(camera_record_payload(body, camera_ip))


@app.put("/api/cameras/{camera_id}")
def api_update_camera(camera_id: str, request: Request, body: CameraRecordIn):
    existing_camera = get_camera(camera_id)
    if existing_camera is None:
        raise HTTPException(status_code=404, detail="Camera not found.")
    validate_camera_record_payload(body)
    user = require_camera_record_editor(request, body.areaId)
    if user["role"] != "admin" and not can_access_camera(user, existing_camera):
        raise HTTPException(status_code=403, detail="You are not authorized to update this camera.")
    body.cameraId = camera_id
    camera_ip = validate_camera_ip(body.cameraIp) if body.cameraIp else None
    return upsert_camera(camera_record_payload(body, camera_ip))


@app.delete("/api/cameras/{camera_id}")
def api_delete_camera(camera_id: str, request: Request):
    require_admin(request)
    if get_camera(camera_id) is None:
        raise HTTPException(status_code=404, detail="Camera not found.")
    delete_camera(camera_id)
    return {"ok": True, "cameraId": camera_id, "status": "inactive"}


@app.post("/api/cameras/{camera_id}/enable")
def api_enable_camera(camera_id: str, request: Request):
    require_admin(request)
    camera = set_camera_active(camera_id, True)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found.")
    return camera


@app.post("/api/cameras/{camera_id}/disable")
def api_disable_camera(camera_id: str, request: Request):
    require_admin(request)
    camera = set_camera_active(camera_id, False)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found.")
    return camera


@app.post("/api/camera-assignments")
def api_assign_camera(request: Request, body: CameraAssignmentIn):
    require_admin(request)
    if body.cameraId and get_camera(body.cameraId) is None:
        raise HTTPException(status_code=404, detail="Camera not found.")
    return assign_camera(
        {
            "responderId": body.responderId,
            "cameraId": body.cameraId,
            "areaId": body.areaId,
            "role": body.role or "viewer",
            "status": body.status or "active",
        }
    )


@app.get("/api/cameras/{camera_id}")
def api_camera_by_id(camera_id: str, request: Request):
    _, camera = require_camera_access(request, camera_id)
    return camera


@app.get("/api/incidents")
def get_incidents():
    return incidents[::-1]


@app.get("/api/notifications")
def get_notifications(request: Request):
    user = None
    try:
        user = verify_firebase_user(request)
    except HTTPException as error:
        header = request.headers.get("authorization", "")
        if header.lower().startswith("bearer "):
            raise error

    if user and user.get("role") == "user":
        raise HTTPException(status_code=403, detail="You do not have permission to access this page.")

    local_notifications = list_notifications(
        role=user.get("role") if user else None,
        responder_id=user.get("uid") if user else None,
        area_id=user.get("areaId") if user else None,
    )
    if local_notifications or user:
        newest = local_notifications[0] if local_notifications else {}
        print(
            "[notifications] returning sqlite "
            f"count={len(local_notifications)} "
            f"newestId={newest.get('notificationId')} "
            f"newestCreatedAt={newest.get('createdAt')} "
            f"role={(user or {}).get('role')} areaId={(user or {}).get('areaId')}"
        )
        return local_notifications
    legacy_notifications = sorted(
        notifications,
        key=lambda item: item.get("timestamp") or "",
        reverse=True,
    )
    newest = legacy_notifications[0] if legacy_notifications else {}
    print(
        "[notifications] returning legacy "
        f"count={len(legacy_notifications)} "
        f"newestId={newest.get('id')} "
        f"newestCreatedAt={newest.get('timestamp')}"
    )
    return legacy_notifications


@app.post("/api/notifications/{notification_id}/archive")
def api_archive_notification(notification_id: str, request: Request):
    user = require_dashboard_access(request)
    if user["role"] not in {"admin", "responder"}:
        raise HTTPException(status_code=403, detail="Responder or admin access is required.")
    if not archive_notification(notification_id):
        raise HTTPException(status_code=404, detail="Notification not found.")
    return {"notificationId": notification_id, "archived": True}


@app.delete("/api/notifications/{notification_id}")
def api_delete_notification(notification_id: str, request: Request):
    require_admin(request)
    if not delete_notification(notification_id):
        raise HTTPException(status_code=404, detail="Notification not found.")
    return {"notificationId": notification_id, "deleted": True}


@app.post("/api/debug/create-camera-alert")
def api_debug_create_camera_alert(request: Request, body: DebugCameraAlertIn):
    user = require_dashboard_access(request)
    if user["role"] not in {"admin", "responder"}:
        raise HTTPException(status_code=403, detail="Responder or admin access is required.")

    created_at = datetime.now().isoformat()
    camera_id = (body.cameraId or "DEVICE-LIVE-CAMERA").strip() or "DEVICE-LIVE-CAMERA"
    source_camera = (body.sourceCamera or "Device Live Camera").strip() or "Device Live Camera"
    area_id = (body.areaId or "demo").strip() or "demo"
    location = (body.location or source_camera).strip() or source_camera
    confidence = max(0.0, min(1.0, float(body.confidence or 0.91)))
    case_id = f"CASE-{uuid.uuid4().hex[:10].upper()}"

    evidence_path = None
    worker = None
    try:
        worker = get_requested_or_default_monitor(body.cameraIp)
    except ValueError:
        worker = None

    if worker is not None:
        with worker.lock:
            frame = None if worker.latest_frame is None else worker.latest_frame.copy()
        if frame is not None:
            candidate = OUTPUTS / f"debug_camera_alert_{uuid.uuid4().hex[:8]}.jpg"
            if cv2.imwrite(str(candidate), frame):
                evidence_path = candidate

    if evidence_path is None:
        sample_path = BASE_DIR.parent / "public" / "samples" / "accident-01.jpg"
        if sample_path.exists():
            evidence_path = sample_path

    media_paths = store_case_media(
        case_id,
        original_path=None,
        key_frame_path=evidence_path,
        thumbnail_path=evidence_path,
        annotated_path=None,
    )
    case_item = create_crash_case(
        {
            "caseId": case_id,
            "status": "pending_review",
            "confidence": confidence,
            "detectedAt": created_at,
            "updatedAt": created_at,
            "location": location,
            "latitude": DEMO_FALLBACK_LATITUDE,
            "longitude": DEMO_FALLBACK_LONGITUDE,
            "areaId": area_id,
            "sourceCamera": source_camera,
            "cameraId": camera_id,
            "cameraName": source_camera,
            "cameraIp": body.cameraIp,
            "barangay": area_id,
            "triggerStatus": "camera_detection",
            "accidentDetected": True,
            **media_paths,
        },
        boxes=[],
        frame_path=media_paths.get("keyFramePath"),
    )
    return {
        "caseId": case_item["caseId"],
        "notificationId": case_item.get("createdNotificationId"),
        "createdAt": created_at,
        "keyFramePath": case_item.get("keyFramePath"),
    }


@app.post("/api/detect/image")
async def detect_image(
    request: Request,
    file: UploadFile = File(...),
    triggerStatus: str | None = Form(default=None),
    sourceCamera: str | None = Form(default=None),
    areaId: str | None = Form(default=None),
    cameraId: str | None = Form(default=None),
    cameraName: str | None = Form(default=None),
    cameraIp: str | None = Form(default=None),
    location: str | None = Form(default=None),
):
    file_path = None
    try:
        if file is None:
            log_image("Request did not include an uploaded file")
            raise HTTPException(status_code=400, detail="No image file was uploaded.")

        if not file.filename:
            log_image("Uploaded image was missing a filename")
            raise HTTPException(status_code=400, detail="No image file was uploaded.")

        log_image(f"\nStarting image detection for: {file.filename}")

        if not is_supported_image_upload(file):
            log_image(
                "Rejected unsupported image upload "
                f"filename={file.filename!r} content_type={file.content_type!r}"
            )
            raise HTTPException(
                status_code=400,
                detail=(
                    "Unsupported image type. Please upload a JPG, PNG, BMP, WEBP, or GIF image."
                ),
            )

        file_path = save_upload_file(file)
        log_image(f"File saved to: {file_path}")

        try:
            decoded_image = decode_uploaded_image(file_path)
        except ValueError as error:
            log_image(f"Image decode failed: {error}")
            raise HTTPException(status_code=400, detail=str(error)) from error

        log_image(
            "Image decoded successfully "
            f"width={decoded_image.shape[1]} height={decoded_image.shape[0]}"
        )

        output_base = str(request.base_url).rstrip("/")
        is_camera_detection = triggerStatus == "camera_detection"
        request_user = optional_request_user(request)
        user_area_id = request_user.get("areaId") if request_user else None
        effective_area_id = areaId or (user_area_id if is_camera_detection else None)
        if is_camera_detection and not effective_area_id:
            effective_area_id = "demo"
        effective_source_camera = (
            sourceCamera
            or cameraName
            or ("Device Live Camera" if is_camera_detection else None)
        )
        if is_camera_detection:
            log_image(
                "Camera image detection request: "
                f"areaId={effective_area_id or ''} cameraId={cameraId or ''} "
                f"cameraName={cameraName or ''} sourceCamera={effective_source_camera or ''} "
                f"cameraIp={cameraIp or ''} user={(request_user or {}).get('uid', '')}"
            )
        return image_detection_response_from_bgr(
            output_base,
            decoded_image,
            incident_media_type="cctv" if is_camera_detection else "image",
            api_media_type="image",
            source_file=file.filename or "uploaded_image",
            location_label=location or ("Live Camera" if is_camera_detection else "Uploaded Image"),
            log_fn=log_image,
            original_path=file_path,
            area_id=effective_area_id,
            trigger_status=triggerStatus if is_camera_detection else None,
            source_camera=effective_source_camera,
            camera_ip=cameraIp,
            camera_id=cameraId,
            camera_name=cameraName or sourceCamera,
            barangay=effective_area_id,
            responder_id=request_user.get("uid") if request_user and is_camera_detection else None,
        )
    except HTTPException:
        raise
    except Exception as error:
        log_image(f"Detection error: {error}")
        raise HTTPException(status_code=500, detail=f"Image detection failed: {error}")


def _detect_stream_frame_sync(base_url: str, body: StreamFrameIn) -> dict:
    try:
        stream_url, fallback_label, camera_ip = resolve_camera_stream_source(body)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    label = body.label or fallback_label
    location = body.location or body.areaId or "Authorized Camera"
    camera_id = body.cameraId
    if not camera_id and body.url:
        camera_id = f"STREAM-{hashlib.sha1(body.url.strip().encode('utf-8')).hexdigest()[:10].upper()}"
    log_stream(f"Capturing frame from stream source={label}")
    try:
        frame = grab_frame_from_stream_url(stream_url)
    except ValueError as error:
        log_stream(f"Stream open/read failed: {error}")
        raise HTTPException(
            status_code=400,
            detail="Unable to connect. Check that RTSP is enabled, the camera account is correct, and the camera is on the same network.",
        ) from error

    upsert_camera(
        {
            "cameraId": camera_id,
            "label": label,
            "cameraIp": camera_ip,
            "areaId": body.areaId or "demo",
            "location": location,
            "streamUrl": build_redacted_camera_stream_label(camera_ip) if camera_ip else body.url,
            "cameraType": body.cameraType or "Tapo RTSP",
            "status": "connected",
        }
    )

    return image_detection_response_from_bgr(
        base_url,
        frame,
        incident_media_type="cctv",
        api_media_type="image",
        source_file=label,
        location_label=location,
        log_fn=log_stream,
        original_path=None,
        area_id=body.areaId or "demo",
        trigger_status="camera_detection",
        source_camera=label,
        camera_ip=camera_ip,
        camera_id=camera_id,
        camera_name=label,
        barangay=body.areaId or "demo",
    )


def _test_camera_connection_sync(body: CameraConnectionIn, output_base: str) -> dict:
    try:
        stream_url, fallback_label, camera_ip = resolve_camera_stream_source(body)
        frame = grab_frame_from_stream_url(stream_url)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    label = body.label or fallback_label
    location = body.location or body.areaId or "Authorized Camera"
    camera = upsert_camera(
        {
            "cameraId": body.cameraId,
            "label": label,
            "cameraIp": camera_ip,
            "areaId": body.areaId,
            "barangay": body.areaId,
            "location": location,
            "streamUrl": build_redacted_camera_stream_label(camera_ip),
            "cameraType": "Tapo RTSP",
            "status": "connected",
        }
    )
    worker = start_live_camera_monitor(
        camera_id=camera["cameraId"],
        camera_ip=camera_ip,
        stream_url=stream_url,
        label=label,
        area_id=body.areaId,
        barangay=camera.get("barangay"),
        road_name=camera.get("roadName"),
        latitude=camera.get("latitude"),
        longitude=camera.get("longitude"),
        location=location,
        redacted_stream_url=build_redacted_camera_stream_label(camera_ip),
        output_base=output_base,
        first_frame=frame,
    )
    return {
        "connected": True,
        "cameraId": camera["cameraId"],
        "cameraIp": camera_ip,
        "label": label,
        "width": int(frame.shape[1]),
        "height": int(frame.shape[0]),
        "status": worker.snapshot_status()["status"],
        "message": "Live monitoring started.",
    }


@app.get("/api/camera-settings")
def api_camera_settings(request: Request):
    require_admin(request)
    return load_camera_config(include_secret=False)


@app.post("/api/camera-settings")
def api_save_camera_settings(request: Request, body: CameraSettingsIn):
    require_admin(request)
    try:
        return save_camera_config(body)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/cameras/test-connection")
async def api_test_camera_connection(request: Request, body: CameraConnectionIn):
    user = verify_firebase_user(request)
    if user["role"] not in {"admin", "responder"}:
        raise HTTPException(status_code=403, detail="Responder or admin access is required.")
    if body.cameraId:
        camera = get_camera(body.cameraId)
        if camera and not can_access_camera(user, camera):
            raise HTTPException(status_code=403, detail="You are not authorized to access this camera.")
    try:
        output_base = str(request.base_url).rstrip("/")
        return await asyncio.to_thread(_test_camera_connection_sync, body, output_base)
    except HTTPException as error:
        if error.detail == "Camera account is required. Add the Tapo camera username and password in Admin Camera Settings.":
            raise
        raise HTTPException(
            status_code=400,
            detail="Unable to connect. Check that RTSP is enabled, the camera account is correct, and the camera is on the same network.",
        ) from error


def resolve_camera_identifier(identifier: str) -> dict | None:
    camera = get_camera(identifier)
    if camera:
        return camera
    try:
        return get_camera_by_ip(validate_camera_ip(identifier))
    except ValueError:
        return None


def monitor_for_camera(camera: dict) -> LiveCameraMonitor | None:
    for key in live_camera_worker_keys(
        camera_id=camera.get("cameraId"),
        camera_ip=camera.get("cameraIp"),
        stream_url=camera.get("streamUrl"),
        label=camera.get("label"),
    ):
        worker = get_live_camera_monitor(key)
        if worker:
            return worker
    camera_ip = camera.get("cameraIp")
    return get_live_camera_monitor(camera_ip) if camera_ip else None


def stop_live_camera_monitor(worker: LiveCameraMonitor) -> None:
    worker.stop()
    with LIVE_CAMERA_WORKERS_LOCK:
        for key, candidate in list(LIVE_CAMERA_WORKERS.items()):
            if candidate is worker:
                LIVE_CAMERA_WORKERS.pop(key, None)


def resolve_saved_camera_stream(camera: dict) -> tuple[str, str | None]:
    camera_ip = camera.get("cameraIp")
    if camera_ip:
        return build_tapo_rtsp_url(camera_ip), camera_ip
    stream_url = (camera.get("streamUrl") or "").strip()
    if stream_url:
        validate_stream_url(stream_url)
        return stream_url, None
    raise ValueError("Camera stream is not configured.")


@app.post("/api/cameras/{camera_id}/monitor/start")
async def api_start_camera_monitor(camera_id: str, request: Request):
    _, camera = require_camera_access(request, camera_id)
    if not camera.get("isActive"):
        raise HTTPException(status_code=400, detail="Camera is inactive.")
    if not camera.get("detectionEnabled"):
        raise HTTPException(status_code=400, detail="Detection is disabled for this camera.")
    try:
        stream_url, camera_ip = resolve_saved_camera_stream(camera)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    try:
        frame = await asyncio.to_thread(grab_frame_from_stream_url, stream_url)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    worker = start_live_camera_monitor(
        camera_id=camera["cameraId"],
        camera_ip=camera_ip,
        stream_url=stream_url,
        label=camera["label"],
        area_id=camera.get("areaId"),
        barangay=camera.get("barangay"),
        road_name=camera.get("roadName"),
        latitude=camera.get("latitude"),
        longitude=camera.get("longitude"),
        location=camera.get("location") or camera.get("locationDescription") or camera.get("roadName") or camera["label"],
        redacted_stream_url=(
            build_redacted_camera_stream_label(camera_ip)
            if camera_ip
            else stream_source_label(stream_url)
        ),
        output_base=str(request.base_url).rstrip("/"),
        first_frame=frame,
    )
    upsert_camera({
        **camera,
        "cameraIp": camera_ip,
        "streamUrl": camera.get("streamUrl") or (build_redacted_camera_stream_label(camera_ip) if camera_ip else stream_url),
        "status": "monitoring",
        "isActive": True,
        "detectionEnabled": True,
        "updatedAt": datetime.now().isoformat(),
    })
    return worker.snapshot_status()


@app.post("/api/cameras/{camera_id}/monitor/stop")
def api_stop_camera_monitor(camera_id: str, request: Request):
    _, camera = require_camera_access(request, camera_id)
    worker = monitor_for_camera(camera)
    if worker:
        stop_live_camera_monitor(worker)
    upsert_camera({**camera, "status": "offline", "updatedAt": datetime.now().isoformat()})
    return {"ok": True, "cameraId": camera_id, "status": "offline"}


@app.get("/api/cameras/{camera_identifier}/status")
def api_live_camera_status(camera_identifier: str, request: Request):
    user = verify_firebase_user(request)
    camera = resolve_camera_identifier(camera_identifier)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found.")
    if not can_access_camera(user, camera):
        raise HTTPException(status_code=403, detail="You are not authorized to access this camera.")
    worker = monitor_for_camera(camera)
    if worker is None:
        return {
            "cameraId": camera["cameraId"],
            "status": "disconnected",
            "message": "Camera is not connected.",
            "previewAvailable": False,
            "latestResult": None,
        }
    return worker.snapshot_status()


@app.get("/api/camera/status")
def api_live_camera_status_default(cameraIp: str | None = None):
    try:
        worker = get_requested_or_default_monitor(cameraIp)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if worker is None:
        return {
            "cameraConnected": False,
            "monitoringLive": False,
            "detectionRunning": False,
            "latestFrameAvailable": False,
            "lastFrameAt": None,
            "lastDetectionAt": None,
            "lastConfidence": None,
            "lastResult": "No camera connected",
            "lastError": None,
            "activeCaseId": None,
            "status": "disconnected",
            "message": "Camera is not connected.",
            "previewAvailable": False,
            "latestResult": None,
        }
    status = worker.snapshot_status()
    status["lastFrameAt"] = status.get("lastFrameTimestamp")
    return status


@app.get("/api/cameras/{camera_identifier}/latest-frame.jpg")
def api_live_camera_latest_frame(camera_identifier: str, request: Request):
    user = verify_firebase_user(request)
    camera = resolve_camera_identifier(camera_identifier)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found.")
    if not can_access_camera(user, camera):
        raise HTTPException(status_code=403, detail="You are not authorized to access this camera.")
    worker = monitor_for_camera(camera)
    if worker is None:
        raise HTTPException(status_code=404, detail="Camera is not connected.")
    image_bytes = worker.latest_jpeg()
    if image_bytes is None:
        raise HTTPException(status_code=404, detail="No camera frame is available yet.")
    return Response(
        content=image_bytes,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/cameras/{camera_identifier}/preview.mjpeg")
def api_live_camera_preview_mjpeg(camera_identifier: str, request: Request):
    user = verify_firebase_user(request)
    camera = resolve_camera_identifier(camera_identifier)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found.")
    if not can_access_camera(user, camera):
        raise HTTPException(status_code=403, detail="You are not authorized to access this camera.")
    worker = monitor_for_camera(camera)
    if worker is None:
        raise HTTPException(status_code=404, detail="Camera is not connected.")
    return StreamingResponse(
        worker.mjpeg_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store"},
    )


@app.post("/api/cameras/{camera_identifier}/test-detection")
def api_live_camera_test_detection(camera_identifier: str, request: Request):
    user = verify_firebase_user(request)
    camera = resolve_camera_identifier(camera_identifier)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found.")
    if not can_access_camera(user, camera):
        raise HTTPException(status_code=403, detail="You are not authorized to access this camera.")
    worker = monitor_for_camera(camera)
    if worker is None:
        raise HTTPException(status_code=404, detail="Camera is not connected.")
    try:
        return worker.analyze_current_frame(manual=True)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        log_stream(f"Manual live camera detection failed: {error}")
        raise HTTPException(
            status_code=500,
            detail=f"Manual live camera detection failed: {error}",
        ) from error


@app.post("/api/camera/test-detection")
def api_live_camera_test_detection_default(cameraIp: str | None = None):
    try:
        worker = get_requested_or_default_monitor(cameraIp)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if worker is None:
        return {
            "frameAvailable": False,
            "confidence": None,
            "result": "No camera connected",
            "error": "Camera is not connected.",
        }
    try:
        result = worker.analyze_current_frame(manual=True)
        return {
            **result,
            "frameAvailable": True,
            "result": result.get("lastDetectionLabel") or "No labels",
            "error": None,
        }
    except ValueError as error:
        return {
            "frameAvailable": False,
            "confidence": None,
            "result": "No frame",
            "error": str(error),
        }
    except Exception as error:
        log_stream(f"Manual live camera detection failed: {error}")
        return {
            "frameAvailable": True,
            "confidence": None,
            "result": "Detection error",
            "error": str(error),
        }


@app.post("/api/detect/stream-frame")
async def detect_stream_frame(request: Request, body: StreamFrameIn):
    """
    Grab one frame from an RTSP / HTTP(S) stream and run the same YOLO
    pipeline as uploaded images (used for CCTV-style monitoring from the UI).
    """
    base_url = str(request.base_url).rstrip("/")
    try:
        return await asyncio.to_thread(_detect_stream_frame_sync, base_url, body)
    except HTTPException:
        raise
    except Exception as error:
        log_stream(f"Detection error: {error}")
        raise HTTPException(
            status_code=500, detail=f"Stream frame detection failed: {error}"
        ) from error


@app.post("/api/detect/video")
async def detect_video(request: Request, file: UploadFile = File(...)):
    file_path = None
    cap = None
    writer = None
    output_path = None
    output_name = None
    output_url = None
    browser_preview_safe = False
    processing_notes = None

    try:
        if file is None:
            log_video("Request did not include an uploaded file")
            raise HTTPException(status_code=400, detail="No video file was uploaded.")

        if not file.filename:
            log_video("Uploaded video was missing a filename")
            raise HTTPException(status_code=400, detail="No video file was uploaded.")

        log_video(f"\nStarting video detection for: {file.filename}")

        if not is_supported_video_upload(file):
            log_video(
                "Rejected unsupported video upload "
                f"filename={file.filename!r} content_type={file.content_type!r}"
            )
            raise HTTPException(
                status_code=400,
                detail=(
                    "Unsupported video type. Please upload an MP4, MOV, WEBM, AVI, M4V, or MKV video."
                ),
            )

        file_path = save_upload_file(file)
        log_video(f"File saved to: {file_path}")
        
        cap = cv2.VideoCapture(str(file_path))

        if not cap.isOpened():
            log_video("Could not open uploaded video file")
            raise HTTPException(status_code=400, detail="Could not open uploaded video.")

        fps = cap.get(cv2.CAP_PROP_FPS) or 0
        if fps <= 0:
            fps = 20.0

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        if width <= 0 or height <= 0:
            log_video(f"Invalid video dimensions: {width}x{height}")
            raise HTTPException(status_code=400, detail="Uploaded video has invalid dimensions.")

        log_video(f"Video opened: width={width}, height={height}, fps={fps:.2f}")

        # Create the annotated output video inside backend/outputs.
        writer_info = create_video_writer(width, height, fps)
        writer = writer_info["writer"]
        output_path = writer_info["output_path"]
        output_name = writer_info["output_name"]
        browser_preview_safe = bool(writer_info["browser_preview_safe"])

        if writer is None:
            log_video("Video writer was not created. Annotated output will not be generated.")
        else:
            log_video(f"Codec used: {writer_info['codec']}")
            log_video(f"Output file path: {output_path}")

        accident_detected = False
        best_confidence = 0.0
        best_key_frame = None
        best_key_frame_time_s = None
        detection_samples = []
        detection_box_samples = []
        max_detection_samples = 20
        processed_frames = 0
        frame_count = 0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        frame_skip = get_video_frame_skip(total_frames, fps)

        log_video(f"Total frames: {total_frames}, frame_skip: {frame_skip}")
        last_annotated_frame = None

        while True:
            success, frame = cap.read()
            if not success:
                break

            frame_count += 1

            # Process the first frame, then sample the rest for faster CPU demos.
            should_process_frame = frame_count == 1 or (frame_count - 1) % frame_skip == 0
            if not should_process_frame:
                # Reuse previous annotated frame for skipped frames (if available)
                if writer is not None and last_annotated_frame is not None:
                    writer.write(last_annotated_frame)
                continue

            processed_frames += 1

            # Detect objects in the current frame, then draw boxes and labels.
            results = model.predict(frame, verbose=False)
            frame_detections, frame_has_accident, frame_best_confidence = extract_detections(results)
            frame_boxes = detect_vehicle_boxes(frame, fallback_results=results)
            annotated_frame = draw_detection_boxes_overlay(frame, frame_boxes)
            last_annotated_frame = annotated_frame

            if writer is not None:
                writer.write(annotated_frame)

            if len(detection_samples) < max_detection_samples:
                remaining_slots = max_detection_samples - len(detection_samples)
                detection_samples.extend(frame_detections[:remaining_slots])
                detection_box_samples.extend(frame_boxes[:remaining_slots])

            if frame_has_accident:
                accident_detected = True
                if frame_best_confidence >= best_confidence:
                    best_key_frame = annotated_frame
                    try:
                        best_key_frame_time_s = float(
                            (cap.get(cv2.CAP_PROP_POS_MSEC) or 0.0) / 1000.0
                        )
                    except Exception:
                        best_key_frame_time_s = None
                best_confidence = max(best_confidence, frame_best_confidence)

        if processed_frames == 0:
            log_video("No readable frames found in uploaded video")
            raise HTTPException(status_code=400, detail="Uploaded video has no readable frames.")

        log_video(
            "Processed "
            f"{processed_frames}/{frame_count} frames "
            f"(skipped {frame_count - processed_frames} for speed)"
        )
        log_video(
            "Detection summary: "
            f"accident_detected={accident_detected}, confidence={best_confidence:.2%}"
        )

        timestamp = datetime.now().isoformat()
        create_incident_record(
            media_type="video",
            source_file=file.filename or "uploaded_video",
            accident_detected=accident_detected,
            confidence=best_confidence,
            timestamp=timestamp,
        )

        annotated_media_url = None
        annotated_key_frame_url = None
        annotated_key_frame_time_s_out = None
        annotated_media_warning = None
        annotated_media_previewable = False
        if writer is not None:
            writer.release()
            writer = None

        if output_path is not None and output_path.exists():
            output_size = output_path.stat().st_size
            log_video(f"Output file size: {output_size} bytes")

            if output_size == 0:
                output_path.unlink()
                log_video("Output file was empty and has been removed.")
            elif output_name is not None:
                output_url = build_output_url(request, output_name)
                if browser_preview_safe:
                    annotated_media_url = output_url
                    annotated_media_previewable = True
                    log_video(
                        "Previewable annotated output generated successfully "
                        f"with codec {writer_info['codec']}"
                    )
                    if writer_info["codec"] == "mp4v":
                        annotated_media_warning = (
                            "Annotated footage was generated as MP4, but playback can still vary by browser and codec support."
                        )
                        processing_notes = (
                            "OpenCV saved an MP4 fallback using mp4v. This often previews in browsers, but playback still varies by machine and browser."
                        )
                else:
                    log_video(
                        "Annotated output was generated in a non-previewable fallback format"
                    )
                    annotated_media_warning = (
                        "Annotated footage was generated, but this format is not reliably previewable in the browser on all machines."
                    )
                    processing_notes = (
                        "Detection completed and an annotated output file was saved, but it was not returned as a browser preview because the available codec/format was not considered reliably preview-safe."
                    )

        # Always try to write one representative accident frame for the UI.
        if best_key_frame is not None:
            key_name = f"accident_frame_{uuid.uuid4().hex[:8]}.jpg"
            key_path = OUTPUTS / key_name
            try:
                wrote = bool(cv2.imwrite(str(key_path), best_key_frame))
            except Exception as error:
                wrote = False
                log_video(f"Key frame write failed: {error}")

            if wrote and key_path.exists() and key_path.stat().st_size > 0:
                annotated_key_frame_url = build_output_url(request, key_name)
                annotated_key_frame_time_s_out = best_key_frame_time_s
                log_video(f"Key accident frame saved to: {key_path}")
            else:
                if key_path.exists():
                    key_path.unlink()

        if output_url is None and writer_info["writer"] is None:
            annotated_media_warning = (
                "Video detection completed, but the backend could not create an annotated output file with any available codec."
            )
            processing_notes = (
                "The uploaded video was analyzed successfully, but OpenCV could not open any configured writer codec for annotated output generation on this machine."
            )
        elif output_url is None and output_name is not None:
            annotated_media_warning = (
                "Video detection completed, but the backend could not produce a previewable annotated output file."
            )
            processing_notes = (
                "An annotated output filename was reserved, but no browser-preview-safe video could be returned from the available codec path."
            )

        if annotated_media_url:
            log_video(f"annotated_media_url returned: yes ({annotated_media_url})")
        elif output_path is not None and output_path.exists():
            log_video(
                "annotated_media_url returned: no "
                "(output exists but was not marked browser-preview-safe)"
            )
        else:
            log_video("annotated_media_url returned: no")

        required_threshold = CRASH_ALERT_CONFIDENCE_THRESHOLD
        passed_threshold = passes_crash_alert_threshold(
            best_confidence,
            accident_detected=accident_detected,
        )
        persistence_status = "not_attempted"
        persistence_skipped_reason = None
        sqlite_case = None
        if not accident_detected:
            persistence_status = "skipped"
            persistence_skipped_reason = "Detection did not create alert because no crash was detected."
        elif not passed_threshold:
            persistence_status = "skipped"
            persistence_skipped_reason = (
                "Detection did not create alert because confidence is below the required 20% threshold."
            )
        else:
            sqlite_case = persist_sqlite_crash_case(
                media_type="video",
                source_file=file.filename or "uploaded_video",
                confidence=best_confidence,
                timestamp=timestamp,
                location="Uploaded Video",
                original_path=file_path,
                annotated_url=annotated_media_url,
                annotated_download_url=output_url,
                key_frame_url=annotated_key_frame_url,
                trigger_status="upload_detection",
                source_camera=file.filename or "uploaded_video",
                boxes=detection_box_samples,
            )
            persistence_status = (
                sqlite_case.get("casePersistenceStatus")
                if sqlite_case
                else "failed"
            )
            if sqlite_case is None:
                persistence_skipped_reason = "Crash was detected, but the backend could not save a review case."
            elif sqlite_case.get("casePersistenceStatus") != "created":
                persistence_skipped_reason = sqlite_case.get("alertBlockedReason")
            elif not sqlite_case.get("createdNotificationId"):
                persistence_status = "failed_missing_notification"
                persistence_skipped_reason = "Crash case was saved, but no notification id was returned."

        created_notification_id = (
            sqlite_case.get("createdNotificationId")
            if sqlite_case and persistence_status == "created"
            else None
        )

        return {
            "success": True,
            "accident_detected": accident_detected,
            "caseId": sqlite_case["caseId"] if sqlite_case else None,
            "notificationId": created_notification_id,
            "confidence": best_confidence,
            "lastConfidence": best_confidence,
            "rawCrashConfidence": best_confidence,
            "requiredThreshold": required_threshold,
            "threshold": required_threshold,
            "passedThreshold": passed_threshold,
            "persistenceStatus": persistence_status,
            "persistenceSkippedReason": persistence_skipped_reason,
            "casePersistenceStatus": sqlite_case.get("casePersistenceStatus") if sqlite_case else persistence_status,
            "alertBlockedReason": sqlite_case.get("alertBlockedReason") if sqlite_case else None,
            "activeBlockingCaseId": sqlite_case.get("activeBlockingCaseId") if sqlite_case else None,
            "activeBlockingStatus": sqlite_case.get("activeBlockingStatus") if sqlite_case else None,
            "triggerStatus": "upload_detection",
            "media_type": "video",
            "timestamp": timestamp,
            "location": "Uploaded Video",
            "detections": detection_samples,
            "boxes": detection_box_samples,
            "annotated_media_url": annotated_media_url,
            "annotated_media_available": output_url is not None,
            "annotated_media_previewable": annotated_media_previewable,
            "annotated_media_download_url": output_url,
            "annotated_key_frame_url": annotated_key_frame_url,
            "annotated_key_frame_time_s": annotated_key_frame_time_s_out,
            "annotated_media_format": get_output_format(output_name),
            "annotated_media_warning": annotated_media_warning,
            "processing_notes": processing_notes,
        }
    except HTTPException:
        raise
    except Exception as error:
        log_video(f"Detection error: {error}")
        raise HTTPException(status_code=500, detail=f"Video detection failed: {error}")
    finally:
        if cap is not None:
            cap.release()
        if writer is not None:
            writer.release()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
