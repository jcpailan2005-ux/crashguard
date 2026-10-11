"""Run persistence-free before/near/after-impact Phase 5 video replays.

The production video detection function is used, but file copying, annotated-video
writing, incident persistence, and notification persistence are replaced with
no-op adapters. This isolates detector behavior from operational data stores.
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
from starlette.datastructures import UploadFile


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

OUTPUT_DIR = BACKEND_DIR / "validation" / "phase5"
MANIFEST_PATH = OUTPUT_DIR / "real_replay_manifest.json"


def slice_video(source: Path, destination: Path, start_seconds: float) -> None:
    capture = cv2.VideoCapture(str(source))
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 30.0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    capture.set(cv2.CAP_PROP_POS_MSEC, start_seconds * 1000.0)
    writer = cv2.VideoWriter(
        str(destination), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
    )
    if not writer.isOpened():
        capture.release()
        raise RuntimeError("OpenCV could not create a temporary replay slice")
    try:
        while True:
            ok, frame = capture.read()
            if not ok or frame is None:
                break
            writer.write(frame)
    finally:
        capture.release()
        writer.release()


async def run_replay(path: Path, replay_name: str) -> dict:
    import backend.main as app_module

    upload_file = UploadFile(filename=f"{replay_name}.mp4", file=path.open("rb"))
    request = SimpleNamespace(base_url="http://phase5-validation.local")
    no_writer = {
        "writer": None,
        "output_path": None,
        "output_name": None,
        "browser_preview_safe": False,
        "codec": None,
    }
    started = time.perf_counter()
    try:
        with (
            patch.object(app_module, "save_upload_file", return_value=path),
            patch.object(app_module, "create_video_writer", return_value=no_writer),
            patch.object(app_module, "persist_sqlite_crash_case", return_value=None),
            patch.object(app_module, "create_incident_record", return_value=None),
        ):
            result = await app_module.detect_video(request, upload_file)
    finally:
        await upload_file.close()
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    performance = result.get("performance") or {}
    detected_event = result.get("eventState") in {"CONFIRMED", "ACTIVE"}
    return {
        "actual_detection_mode": result.get("detectionMode"),
        "actual_final_decision": result.get("finalDecision"),
        "detected_event": detected_event,
        "event_state": result.get("eventState"),
        "persistence_exercised": False,
        "persistence_status": "INTENTIONALLY_BYPASSED_FOR_DATABASE_SAFETY",
        "rejection_reason": result.get("rejectionReason"),
        "max_classifier_score": result.get("crashScore"),
        "temporal_score": result.get("temporalCrashScore"),
        "aftermath_score": result.get("aftermathScore"),
        "aftermath_state": result.get("aftermathState"),
        "vehicle_count": result.get("vehicleCount"),
        "frame_quality_status": result.get("frameQualityStatus"),
        "analysis_wall_time_ms": round(elapsed_ms, 3),
        "mean_stage_performance_ms": performance,
    }


async def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    replay = next(item for item in manifest["replays"] if item["video_id"] == "REAL-REPLAY-003")
    source = PROJECT_DIR / replay["source_file"]
    scenarios = [
        {
            "scenario": "before_impact",
            "start_seconds": 0.0,
            "estimated_impact_seconds_in_source": 15.5,
            "expected_detection_mode": "temporal_collision",
        },
        {
            "scenario": "near_impact",
            "start_seconds": 13.0,
            "estimated_impact_seconds_in_source": 15.5,
            "expected_detection_mode": "temporal_collision",
        },
        {
            "scenario": "after_impact",
            "start_seconds": 17.0,
            "estimated_impact_seconds_in_source": 15.5,
            "expected_detection_mode": "aftermath_review",
        },
    ]
    results = []
    with tempfile.TemporaryDirectory(prefix="crashguard-phase5-") as temp_name:
        temp_dir = Path(temp_name)
        for scenario in scenarios:
            if scenario["start_seconds"] == 0.0:
                replay_path = source
            else:
                replay_path = temp_dir / f"{scenario['scenario']}.mp4"
                slice_video(source, replay_path, float(scenario["start_seconds"]))
            actual = await run_replay(replay_path, str(scenario["scenario"]))
            results.append({**scenario, **actual})

    payload = {
        "source_video_id": replay["video_id"],
        "source_provenance": "public CCTV-style clip; provenance not independently authenticated",
        "ground_truth_basis": "human visual inspection of contact sheet",
        "impact_time_precision": "estimated; no authoritative annotation supplied",
        "operational_persistence_policy": "disabled because configured PostgreSQL database is not isolated crashguard_test",
        "scenarios": results,
    }
    (OUTPUT_DIR / "replay_results.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
