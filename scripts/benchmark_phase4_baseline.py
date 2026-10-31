"""Record the immutable pre-Phase-4 full-frame baseline."""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import main
from backend.services.crash_event_state import CrashEventManager
from scripts.benchmark_phase3_resolution import (
    CONFIGS,
    analyze_frame,
    latency_summary,
    load_positive_frames,
    reset_pipeline,
)


PHASE2B = ROOT / "backend" / "validation" / "phase2b"
PHASE4 = ROOT / "backend" / "validation" / "phase4"
RESULT_PATH = PHASE4 / "baseline_results.json"


def event_manager() -> CrashEventManager:
    return CrashEventManager(
        required_positive_observations=main.LIVE_CAMERA_REQUIRED_HITS,
        temporal_window_seconds=main.CRASH_TEMPORAL_WINDOW_SECONDS,
        clear_consecutive_negatives=main.EVENT_CLEAR_CONSECUTIVE_NEGATIVES,
        clear_seconds=main.EVENT_CLEAR_SECONDS,
        cooldown_seconds=main.EVENT_COOLDOWN_SECONDS,
    )


def decision_name(result) -> str:
    event = result["event"]
    if event and event.should_persist:
        return (
            "confirmed_crash"
            if event.detection_mode == "temporal_collision"
            else "possible_crash_aftermath"
        )
    return "ignored"


def main_baseline() -> int:
    config = CONFIGS["N640"]
    positive_manifest = json.loads(
        (PHASE2B / "positive_collision_ground_truth.json").read_text(encoding="utf-8")
    )
    negative_manifest = json.loads(
        (PHASE2B / "negative_replay_manifest.json").read_text(encoding="utf-8")
    )
    positive_frames = load_positive_frames(positive_manifest)
    positive_key = "phase4-baseline-positive"
    positive_manager = event_manager()
    positive_rows = []
    all_model1_ms = []
    all_total_ms = []
    try:
        for annotation, native in positive_frames:
            result = analyze_frame(
                native,
                config,
                positive_key,
                float(annotation["timestamp"]),
                positive_manager,
            )
            positive_rows.append(
                {
                    "frame_index": int(annotation["frame_index"]),
                    "full_frame_crash_score": round(result["model1_score"], 4),
                    "selected_pair": None,
                    "temporal_score": round(result["temporal"].score, 4),
                    "aftermath_score": round(result["aftermath"].score, 4),
                    "final_decision": decision_name(result),
                    "model1_ms": round(result["timing"]["model1_ms"], 3),
                    "total_ai_ms": round(result["timing"]["total_ai_ms"], 3),
                }
            )
            all_model1_ms.append(result["timing"]["model1_ms"])
            all_total_ms.append(result["timing"]["total_ai_ms"])
    finally:
        reset_pipeline(positive_key)

    negative_rows = []
    source_root = Path(negative_manifest["source_root"])
    fps = float(negative_manifest["assumed_source_fps"])
    for sequence in negative_manifest["sequences"]:
        camera_key = f"phase4-baseline-{sequence['sequence_id']}"
        manager = event_manager()
        rows = []
        first_index = int(sequence["frame_indices"][0])
        try:
            for frame_index in sequence["frame_indices"]:
                native = cv2.imread(str(source_root / f"{frame_index}.jpg"))
                if native is None:
                    raise RuntimeError(f"Could not read negative frame {frame_index}")
                timestamp = (int(frame_index) - first_index) / fps
                result = analyze_frame(native, config, camera_key, timestamp, manager)
                rows.append(result)
                all_model1_ms.append(result["timing"]["model1_ms"])
                all_total_ms.append(result["timing"]["total_ai_ms"])
        finally:
            reset_pipeline(camera_key)
        decisions = [decision_name(row) for row in rows]
        negative_rows.append(
            {
                "sequence_id": sequence["sequence_id"],
                "category": sequence["category"],
                "frames": len(rows),
                "full_frame_scores": [round(row["model1_score"], 4) for row in rows],
                "full_frame_score_mean": round(
                    statistics.fmean(row["model1_score"] for row in rows), 4
                ),
                "full_frame_score_max": round(max(row["model1_score"] for row in rows), 4),
                "temporal_score_max": round(max(row["temporal"].score for row in rows), 4),
                "aftermath_score_max": round(max(row["aftermath"].score for row in rows), 4),
                "confirmed_crash": "confirmed_crash" in decisions,
                "pending_review": "possible_crash_aftermath" in decisions,
                "final_decision": next(
                    (value for value in reversed(decisions) if value != "ignored"), "ignored"
                ),
            }
        )

    payload = {
        "schema_version": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "configuration": {
            "model2_frame": "native",
            "model2_imgsz": 640,
            "model1_frame": [640, 360],
            "model1_imgsz": main.CRASH_CLASSIFIER_IMAGE_SIZE,
        },
        "positive": {
            "sequence_id": positive_manifest["sequence_id"],
            "frames": positive_rows,
            "mean_full_frame_score": round(
                statistics.fmean(row["full_frame_crash_score"] for row in positive_rows), 4
            ),
            "max_temporal_score": max(row["temporal_score"] for row in positive_rows),
            "max_aftermath_score": max(row["aftermath_score"] for row in positive_rows),
            "final_decision": next(
                (
                    row["final_decision"]
                    for row in reversed(positive_rows)
                    if row["final_decision"] != "ignored"
                ),
                "ignored",
            ),
        },
        "negative": {
            "sequences": negative_rows,
            "frames": sum(row["frames"] for row in negative_rows),
            "confirmed_false_crashes": sum(row["confirmed_crash"] for row in negative_rows),
            "pending_review_false_positives": sum(row["pending_review"] for row in negative_rows),
            "full_frame_score_distribution": latency_summary(
                [score for row in negative_rows for score in row["full_frame_scores"]]
            ),
            "full_frame_score_min": min(
                score for row in negative_rows for score in row["full_frame_scores"]
            ),
            "full_frame_score_max": max(
                score for row in negative_rows for score in row["full_frame_scores"]
            ),
        },
        "performance": {
            "model1": latency_summary(all_model1_ms),
            "total_ai": latency_summary(all_total_ms),
            "ai_fps": round(1000.0 / statistics.fmean(all_total_ms), 3),
        },
    }
    PHASE4.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(f"Saved {RESULT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_baseline())
