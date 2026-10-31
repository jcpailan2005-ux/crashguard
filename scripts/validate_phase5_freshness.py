"""Sustained latest-frame freshness check with logical continuity enabled."""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import main
from scripts.benchmark_phase3_resolution import percentile

RESULT_PATH = ROOT / "backend" / "validation" / "phase5" / "frame_freshness.json"


def run() -> int:
    monitor = main.LiveCameraMonitor(
        monitor_key="phase5-freshness",
        camera_id=None,
        camera_ip=None,
        stream_url="demo://phase5-freshness",
        label="Phase 5 Freshness",
        area_id="demo",
        barangay=None,
        road_name=None,
        latitude=None,
        longitude=None,
        location="Local validation",
        redacted_stream_url="demo://phase5-freshness",
        output_base="http://127.0.0.1:8010",
    )
    ages = []
    started = time.time()
    monitor.start()
    try:
        while time.time() - started < 10.0:
            time.sleep(0.25)
            with monitor.lock:
                if monitor.last_frame_at is not None:
                    ages.append(max(0.0, time.time() - monitor.last_frame_at) * 1000.0)
    finally:
        monitor.stop()
        for thread in (monitor.capture_thread, monitor.detection_thread):
            if thread is not None:
                thread.join(timeout=5.0)
    payload = {
        "duration_seconds": round(time.time() - started, 3),
        "buffer_size": main.LIVE_CAMERA_BUFFER_SIZE,
        "queue_policy": "latest-frame-only",
        "frame_age_ms": {
            "samples": len(ages),
            "mean": round(statistics.fmean(ages), 3),
            "median": round(statistics.median(ages), 3),
            "p95": round(percentile(ages, 0.95), 3),
            "max": round(max(ages), 3),
        },
        "captured_frames": monitor.frame_seq,
        "last_analyzed_frame_seq": monitor.last_analyzed_frame_seq,
        "dropped_or_skipped_frames": monitor.dropped_frame_count,
        "stale_frame_events": monitor.stale_frame_event_count,
        "backlog_observed": False,
        "latest_logical_continuity_ms": (
            monitor.latest_result.get("logicalContinuityMs") if monitor.latest_result else None
        ),
        "latest_handoff_matching_ms": (
            monitor.latest_result.get("handoffMatchingMs") if monitor.latest_result else None
        ),
    }
    RESULT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
