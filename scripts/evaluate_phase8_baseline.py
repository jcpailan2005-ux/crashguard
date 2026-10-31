"""Replay promoted Phase 8 negatives through the unchanged frozen pipeline.

The replay is diagnostic-only: it uses isolated in-memory event managers and
never calls incident/notification persistence or training code.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import cv2


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_phase6 import CONFIGS, analyze_frame, event_manager, frozen_configuration, reset_pipeline
from backend import main


PHASE8 = ROOT / "backend" / "validation" / "phase8"
OUTPUT = PHASE8 / "new_negative_baseline.json"


def main_run() -> int:
    with (PHASE8 / "manifests" / "manual_reviews.csv").open(encoding="utf-8", newline="") as source:
        reviews = [row for row in csv.DictReader(source) if row["review_status"] == "PROMOTED_NEGATIVE"]
    rows = []
    for review in reviews:
        identifier = review["source_id"].split("-")[-1]
        path = PHASE8 / "incoming" / "nexar" / "negative" / f"{identifier}.mp4"
        capture = cv2.VideoCapture(str(path))
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        stride = max(1, round(fps / 3.0))
        camera_key = f"phase8-negative-{identifier}"
        manager = event_manager()
        frame_index = -1
        processed = 0
        max_full = max_pair = max_temporal = max_aftermath = 0.0
        confirmed = review_fp = 0
        high_temporal_observations = 0
        try:
            while True:
                ok, frame = capture.read()
                if not ok or frame is None:
                    break
                frame_index += 1
                if frame_index % stride:
                    continue
                result = analyze_frame(frame, CONFIGS["N640"], camera_key, frame_index / fps, manager)
                pair = main.classify_collision_pair_regions(frame, result["tiers"], full_frame_score=result["model1_score"], camera_id=camera_key)
                processed += 1
                max_full = max(max_full, float(result["model1_score"]))
                if pair["pairRegionCrashScore"] is not None:
                    max_pair = max(max_pair, float(pair["pairRegionCrashScore"]))
                max_temporal = max(max_temporal, float(result["temporal"].score))
                max_aftermath = max(max_aftermath, float(result["aftermath"].score))
                high_temporal_observations += result["temporal"].score >= 0.62
                event = result.get("event")
                if event and event.should_persist:
                    confirmed += event.detection_mode == "temporal_collision"
                    review_fp += event.detection_mode == "aftermath_review"
        finally:
            capture.release()
            reset_pipeline(camera_key)
        decision = "confirmed_crash" if confirmed else "possible_crash_aftermath" if review_fp else "ignored"
        row = {
            "event_id": f"PHASE8-NEG-{identifier}", "source_id": review["source_id"],
            "negative_subtype": review["negative_subtype"], "frames_processed": processed,
            "sample_rate_fps": round(fps / stride, 3), "maximum_full_frame_model1": round(max_full, 4),
            "maximum_pair_region_model1": round(max_pair, 4), "maximum_temporal_score": round(max_temporal, 4),
            "maximum_aftermath_score": round(max_aftermath, 4),
            "wrong_pair_high_temporal_observations": high_temporal_observations,
            "final_decision": decision,
        }
        rows.append(row)
        print(json.dumps(row), flush=True)
    payload = {
        "schema_version": 1, "pipeline": "CURRENT_UNCHANGED_CRASHGUARD", "sampling": "approximately 3 decoded frames/second",
        "frozen_configuration": frozen_configuration(), "events": rows,
        "summary": {
            "independent_negatives": len(rows),
            "confirmed_false_crashes": sum(row["final_decision"] == "confirmed_crash" for row in rows),
            "pending_review_false_positives": sum(row["final_decision"] == "possible_crash_aftermath" for row in rows),
            "wrong_pair_high_temporal_events": sum(row["maximum_temporal_score"] >= 0.62 for row in rows),
            "high_model1_events": sum(row["maximum_full_frame_model1"] >= 0.8 for row in rows),
            "high_pair_region_events": sum(row["maximum_pair_region_model1"] >= 0.8 for row in rows),
        },
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_run())
