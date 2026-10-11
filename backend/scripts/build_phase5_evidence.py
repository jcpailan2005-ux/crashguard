"""Build credential-free Phase 5 evidence from locally available camera/media data.

This script deliberately does not infer crash ground truth. It inventories sources,
deduplicates replay files by content, records measurable stream metadata, and creates
contact sheets for a human validation pass.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))
OUTPUT_DIR = BACKEND_DIR / "validation" / "phase5"
CONTACT_SHEET_DIR = OUTPUT_DIR / "contact_sheets"
UPLOAD_DIR = BACKEND_DIR / "uploads"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_json(name: str, payload: object) -> None:
    (OUTPUT_DIR / name).write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def video_metadata(path: Path) -> dict:
    capture = cv2.VideoCapture(str(path))
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        fourcc_value = int(capture.get(cv2.CAP_PROP_FOURCC) or 0)
        codec = "".join(chr((fourcc_value >> (8 * index)) & 0xFF) for index in range(4))
        duration = frame_count / fps if fps > 0 else None
        return {
            "resolution": {"width": width, "height": height},
            "fps": round(fps, 3),
            "frame_count": frame_count,
            "duration_seconds": round(duration, 3) if duration is not None else None,
            "codec": codec.strip("\\x00") or None,
        }
    finally:
        capture.release()


def make_contact_sheet(path: Path, output_path: Path, samples: int = 12) -> None:
    capture = cv2.VideoCapture(str(path))
    frame_count = max(1, int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 1))
    frames: list[np.ndarray] = []
    try:
        for index, frame_number in enumerate(np.linspace(0, frame_count - 1, samples).astype(int)):
            capture.set(cv2.CAP_PROP_POS_FRAMES, int(frame_number))
            ok, frame = capture.read()
            if not ok or frame is None:
                continue
            frame = cv2.resize(frame, (320, 180), interpolation=cv2.INTER_AREA)
            cv2.putText(
                frame,
                f"sample {index + 1}/{samples} frame {frame_number}",
                (8, 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.43,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            frames.append(frame)
    finally:
        capture.release()
    if not frames:
        raise RuntimeError(f"No readable frames in {path.name}")
    blank = np.zeros_like(frames[0])
    while len(frames) < samples:
        frames.append(blank.copy())
    rows = [np.hstack(frames[offset : offset + 4]) for offset in range(0, samples, 4)]
    if not cv2.imwrite(str(output_path), np.vstack(rows)):
        raise RuntimeError(f"Could not write {output_path}")


def load_camera_inventory() -> list[dict]:
    # Importing here keeps the script's media-only helpers independently reusable.
    from backend.main import list_cameras, load_camera_config

    local_config = load_camera_config(include_secret=False)
    records = []
    for camera in list_cameras(include_inactive=True):
        camera_id = str(camera.get("cameraId") or "")
        local_match = bool(
            local_config.get("cameraIp")
            and camera.get("cameraIp") == local_config.get("cameraIp")
        )
        records.append(
            {
                "camera_id": camera_id,
                "camera_name": camera.get("label"),
                "area": camera.get("areaId"),
                "source_type": "real_rtsp" if camera.get("cameraIp") else "unconfigured_record",
                "rtsp_url_present": bool(camera.get("cameraIp") or camera.get("streamUrl")),
                "credentials_configured": bool(local_match and local_config.get("hasCredentials")),
                "resolution": None,
                "fps": None,
                "codec": None,
                "stream_profile": local_config.get("streamType") if local_match else None,
                "day_night_capability": "UNVERIFIED",
                "camera_angle": "UNVERIFIED",
                "road_direction": "UNVERIFIED",
                "estimated_traffic_density": "UNVERIFIED",
                "online_state": camera.get("status") or "unknown",
                "active": bool(camera.get("isActive")),
                "detection_enabled": bool(camera.get("detectionEnabled")),
                "validation_status": "NOT_TESTED",
            }
        )
    return records


def build_replay_manifest() -> list[dict]:
    groups: dict[str, list[Path]] = {}
    for path in sorted(UPLOAD_DIR.glob("*.mp4")):
        groups.setdefault(sha256(path), []).append(path)

    manifest = []
    for index, (digest, paths) in enumerate(groups.items(), start=1):
        representative = paths[0]
        metadata = video_metadata(representative)
        video_id = f"REAL-REPLAY-{index:03d}"
        contact_sheet = CONTACT_SHEET_DIR / f"{video_id.lower()}-contact-sheet.jpg"
        make_contact_sheet(representative, contact_sheet)
        manifest.append(
            {
                "video_id": video_id,
                "sha256": digest,
                "duplicate_file_count": len(paths),
                "source_file": str(representative.relative_to(PROJECT_DIR)).replace("\\", "/"),
                "camera_source": "uploaded video; provenance unverified",
                **metadata,
                "event_start_seconds": None,
                "impact_time_seconds": None,
                "event_end_seconds": None,
                "vehicles_involved": None,
                "expected_detection_mode": "UNVERIFIED_PENDING_HUMAN_GROUND_TRUTH",
                "expected_incident": None,
                "notes": "Content-deduplicated local upload. Filename and pixels alone do not establish real-world provenance.",
                "contact_sheet": str(contact_sheet.relative_to(PROJECT_DIR)).replace("\\", "/"),
            }
        )
    return manifest


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CONTACT_SHEET_DIR.mkdir(parents=True, exist_ok=True)
    inventory = load_camera_inventory()
    manifest = build_replay_manifest()
    write_json(
        "camera_inventory.json",
        {"generated_at": utc_now(), "credential_policy": "secrets omitted", "cameras": inventory},
    )
    write_json(
        "real_replay_manifest.json",
        {"generated_at": utc_now(), "ground_truth_policy": "human annotation required", "replays": manifest},
    )
    print(f"Wrote {len(inventory)} camera records and {len(manifest)} unique replay records to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
