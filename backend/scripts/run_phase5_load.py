"""Short representative multi-camera CPU load test with latest-frame semantics."""

from __future__ import annotations

import json
import statistics
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import psutil


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

OUTPUT_DIR = BACKEND_DIR / "validation" / "phase5"
MANIFEST_PATH = OUTPUT_DIR / "real_replay_manifest.json"


@dataclass
class CameraSlot:
    camera_id: str
    frame: object
    lock: threading.Lock = field(default_factory=threading.Lock)
    generation: int = 0
    captured_at: float = field(default_factory=time.perf_counter)
    processed_generation: int = 0
    dropped_frames: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    frame_ages_ms: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return round(ordered[index], 3)


def analyze_frame(camera_id: str, frame, timestamp: float) -> None:
    import backend.main as app_module

    quality = app_module.analyze_frame_quality(frame)
    results = app_module.model.predict(frame, verbose=False)
    classifier = app_module.classify_crash_frame(frame)
    score = app_module.normalize_confidence_fraction(
        classifier.get("accidentProbability", classifier.get("crashConfidence"))
    )
    boxes = app_module.detect_vehicle_boxes(frame, fallback_results=results)
    roi_boxes, scene_valid = app_module.filter_boxes_in_roi(boxes, frame)
    tracking, temporal = app_module.analyze_vehicle_tracks(
        camera_id, roi_boxes, frame, classifier_score=score, timestamp=timestamp
    )
    app_module.CRASH_AFTERMATH_DETECTOR.observe(
        camera_id,
        classifier_score=score,
        vehicle_count=len(roi_boxes),
        active_tracks=tracking.active_tracks,
        scene_valid=scene_valid,
        frame_quality_status=quality["frameQualityStatus"],
        scene_abnormality_score=app_module.estimate_scene_abnormality(tracking.active_tracks),
        temporal_collision_active=temporal.is_verified,
        timestamp=timestamp,
    )


def producer(slot: CameraSlot, stop: threading.Event, source_frames: list) -> None:
    index = 0
    while not stop.wait(0.1):
        with slot.lock:
            slot.frame = source_frames[index % len(source_frames)]
            slot.generation += 1
            slot.captured_at = time.perf_counter()
        index += 1


def consumer(slot: CameraSlot, stop: threading.Event) -> None:
    while not stop.wait(0.5):
        with slot.lock:
            frame = slot.frame.copy()
            generation = slot.generation
            captured_at = slot.captured_at
        skipped = max(0, generation - slot.processed_generation - 1)
        slot.dropped_frames += skipped
        slot.processed_generation = generation
        started = time.perf_counter()
        try:
            analyze_frame(slot.camera_id, frame, started)
            finished = time.perf_counter()
            slot.latencies_ms.append((finished - started) * 1000.0)
            slot.frame_ages_ms.append((finished - captured_at) * 1000.0)
        except Exception as error:  # evidence collection must record contention failures
            slot.errors.append(f"{type(error).__name__}: {error}")


def load_source_frames() -> list:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source = PROJECT_DIR / manifest["replays"][2]["source_file"]
    capture = cv2.VideoCapture(str(source))
    frames = []
    try:
        for seconds in (2.0, 8.0, 14.0, 16.0, 20.0, 25.0):
            capture.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000.0)
            ok, frame = capture.read()
            if ok and frame is not None:
                frames.append(frame)
    finally:
        capture.release()
    if not frames:
        raise RuntimeError("No representative replay frames could be decoded")
    return frames


def run_scenario(camera_count: int, frames: list, duration_seconds: float = 8.0) -> dict:
    import backend.main as app_module

    slots = [CameraSlot(f"phase5-load-{camera_count}-{index + 1}", frames[index % len(frames)]) for index in range(camera_count)]
    stop = threading.Event()
    threads = []
    for slot in slots:
        threads.extend(
            [
                threading.Thread(target=producer, args=(slot, stop, frames), daemon=True),
                threading.Thread(target=consumer, args=(slot, stop), daemon=True),
            ]
        )
    process = psutil.Process()
    rss_start = process.memory_info().rss
    process.cpu_percent(None)
    system_cpu_start = psutil.cpu_percent(None)
    started = time.perf_counter()
    for thread in threads:
        thread.start()
    time.sleep(duration_seconds)
    stop.set()
    for thread in threads:
        thread.join(timeout=10.0)
    elapsed = time.perf_counter() - started
    process_cpu = process.cpu_percent(None)
    system_cpu_end = psutil.cpu_percent(None)
    rss_end = process.memory_info().rss
    latencies = [value for slot in slots for value in slot.latencies_ms]
    ages = [value for slot in slots for value in slot.frame_ages_ms]
    errors = [error for slot in slots for error in slot.errors]
    for slot in slots:
        app_module.VEHICLE_TRACKING_SERVICE.reset_camera(slot.camera_id)
        app_module.TEMPORAL_CRASH_VERIFIER.reset_camera(slot.camera_id)
        app_module.CRASH_AFTERMATH_DETECTOR.reset_camera(slot.camera_id)
        app_module.CRASH_EVENT_MANAGER.reset_camera(slot.camera_id)
    return {
        "camera_count": camera_count,
        "duration_seconds": round(elapsed, 3),
        "representative_sources": True,
        "real_rtsp_sources": False,
        "latest_frame_slot_size": 1,
        "completed_cycles": len(latencies),
        "effective_camera_fps": round(len(latencies) / max(0.001, elapsed) / camera_count, 3),
        "process_cpu_percent_all_cores": round(process_cpu, 1),
        "system_cpu_percent_start": round(system_cpu_start, 1),
        "system_cpu_percent_end": round(system_cpu_end, 1),
        "rss_start_mb": round(rss_start / 1024 / 1024, 3),
        "rss_end_mb": round(rss_end / 1024 / 1024, 3),
        "rss_growth_mb": round((rss_end - rss_start) / 1024 / 1024, 3),
        "median_full_cycle_ms": round(statistics.median(latencies), 3) if latencies else None,
        "p95_full_cycle_ms": percentile(latencies, 0.95),
        "median_frame_age_ms": round(statistics.median(ages), 3) if ages else None,
        "p95_frame_age_ms": percentile(ages, 0.95),
        "dropped_input_frames": sum(slot.dropped_frames for slot in slots),
        "queue_length": 0,
        "worker_errors": errors,
    }


def main() -> None:
    frames = load_source_frames()
    scenarios = [run_scenario(count, frames) for count in (1, 2, 4, 8)]
    payload = {
        "test_type": "short representative replay load; not real RTSP soak",
        "target_processing_fps_per_camera": 2.0,
        "source_frame_rate_fps": 10.0,
        "scenarios": scenarios,
        "sustained_30_minute_memory_test": "NOT_RUN",
    }
    (OUTPUT_DIR / "performance_results.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
