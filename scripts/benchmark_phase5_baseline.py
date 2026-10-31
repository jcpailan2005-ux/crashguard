"""Capture the immutable pre-Phase-5 tracking and temporal trace."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import main
from backend.services.crash_event_state import CrashEventManager
from scripts.benchmark_phase3_resolution import (
    CONFIGS,
    analyze_frame,
    assign_two,
    box_xyxy,
    iou,
    load_positive_frames,
    reset_pipeline,
)

PHASE2B = ROOT / "backend" / "validation" / "phase2b"
PHASE5 = ROOT / "backend" / "validation" / "phase5"
RESULT_PATH = PHASE5 / "baseline_tracking.json"


def event_manager() -> CrashEventManager:
    return CrashEventManager(
        required_positive_observations=main.LIVE_CAMERA_REQUIRED_HITS,
        temporal_window_seconds=main.CRASH_TEMPORAL_WINDOW_SECONDS,
        clear_consecutive_negatives=main.EVENT_CLEAR_CONSECUTIVE_NEGATIVES,
        clear_seconds=main.EVENT_CLEAR_SECONDS,
        cooldown_seconds=main.EVENT_COOLDOWN_SECONDS,
    )


def raw_track_id(detection: dict, tracks) -> int | None:
    matches = [
        (iou(box_xyxy(detection), track.bbox), track.track_id)
        for track in tracks
        if iou(box_xyxy(detection), track.bbox) >= 0.20
    ]
    return max(matches, default=(0.0, None))[1]


def run() -> int:
    manifest = json.loads(
        (PHASE2B / "positive_collision_ground_truth.json").read_text(encoding="utf-8")
    )
    camera_key = "phase5-baseline-positive"
    manager = event_manager()
    rows = []
    try:
        for annotation, native in load_positive_frames(manifest):
            result = analyze_frame(
                native,
                CONFIGS["N640"],
                camera_key,
                float(annotation["timestamp"]),
                manager,
            )
            assignments = assign_two(
                {
                    "A": annotation["participant_a_bbox"],
                    "B": annotation["participant_b_bbox"],
                },
                list(result["tiers"].raw),
            )
            pair = main.classify_collision_pair_regions(
                native,
                result["tiers"],
                full_frame_score=result["model1_score"],
                camera_id=camera_key,
            )
            participants = {}
            for name, match in assignments.items():
                detection = match[0] if match else None
                bbox = box_xyxy(detection) if detection else None
                participants[name] = {
                    "raw_detection": detection,
                    "tier": detection.get("detectionState") if detection else "MODEL2_NO_BOX",
                    "raw_track_id": (
                        raw_track_id(detection, result["tracking"].active_tracks)
                        if detection else None
                    ),
                    "bbox": bbox,
                    "confidence": detection.get("confidence") if detection else None,
                    "center": (
                        [(bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0]
                        if bbox else None
                    ),
                    "width": bbox[2] - bbox[0] if bbox else None,
                    "height": bbox[3] - bbox[1] if bbox else None,
                    "class": detection.get("label") if detection else None,
                    "logical_vehicle_id": None,
                }
            interactions = main.TEMPORAL_CRASH_VERIFIER.get_interactions(camera_key)
            rows.append(
                {
                    "frame_index": int(annotation["frame_index"]),
                    "timestamp": float(annotation["timestamp"]),
                    "raw_vehicle_detections": list(result["tiers"].raw),
                    "participants": participants,
                    "active_raw_tracks": [
                        {
                            "raw_track_id": track.track_id,
                            "bbox": list(track.bbox),
                            "class": track.class_name,
                            "confidence": track.confidence,
                            "history_length": len(track.history),
                        }
                        for track in result["tracking"].active_tracks
                    ],
                    "selected_collision_pair": pair["selectedPair"],
                    "selected_pair_is_ground_truth": bool(
                        pair["selectedPair"]
                        and (
                            (
                                iou(pair["selectedPair"]["pairA"]["box"], annotation["participant_a_bbox"]) >= 0.20
                                and iou(pair["selectedPair"]["pairB"]["box"], annotation["participant_b_bbox"]) >= 0.20
                            )
                            or (
                                iou(pair["selectedPair"]["pairA"]["box"], annotation["participant_b_bbox"]) >= 0.20
                                and iou(pair["selectedPair"]["pairB"]["box"], annotation["participant_a_bbox"]) >= 0.20
                            )
                        )
                    ),
                    "temporal_pair_history_lengths": [
                        len(interaction.distance_history) for interaction in interactions
                    ],
                    "temporal_score": round(result["temporal"].score, 4),
                    "final_decision": (
                        "confirmed_crash"
                        if result["event"] and result["event"].should_persist
                        and result["event"].detection_mode == "temporal_collision"
                        else "possible_crash_aftermath"
                        if result["event"] and result["event"].should_persist
                        else "ignored"
                    ),
                }
            )
    finally:
        reset_pipeline(camera_key)
    payload = {
        "schema_version": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "phase": "pre_phase5",
        "logical_identity_layer_present": False,
        "frames": rows,
        "maximum_temporal_score": max(row["temporal_score"] for row in rows),
        "maximum_pair_history_length": max(
            (length for row in rows for length in row["temporal_pair_history_lengths"]),
            default=0,
        ),
    }
    PHASE5.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(f"Saved {RESULT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
