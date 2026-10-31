"""Validate integrated logical continuity on the fixed positive/negative corpus."""

from __future__ import annotations

import copy
import json
import statistics
import sys
import time
from pathlib import Path

import cv2
import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import main
from backend.services.crash_event_state import CrashEventManager
from backend.services.logical_vehicle_continuity import (
    LogicalContinuityConfig,
    LogicalVehicleContinuityService,
)
from scripts.benchmark_phase3_resolution import (
    CONFIGS,
    analyze_frame,
    assign_two,
    box_xyxy,
    iou,
    latency_summary,
    load_positive_frames,
    reset_pipeline,
)

PHASE2B = ROOT / "backend" / "validation" / "phase2b"
PHASE5 = ROOT / "backend" / "validation" / "phase5"
RESULT_PATH = PHASE5 / "validation_results.json"


def manager() -> CrashEventManager:
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
        return "confirmed_crash" if event.detection_mode == "temporal_collision" else "possible_crash_aftermath"
    return "ignored"


def best_logical_match(gt_box, logical_tracks):
    ranked = sorted(
        ((iou(gt_box, track.bbox), track) for track in logical_tracks),
        key=lambda item: item[0],
        reverse=True,
    )
    return ranked[0][1] if ranked and ranked[0][0] >= 0.20 else None


def raw_id_for_detection(detection, raw_tracks):
    if detection is None:
        return None
    ranked = sorted(
        ((iou(box_xyxy(detection), track.bbox), track.track_id) for track in raw_tracks),
        reverse=True,
    )
    return ranked[0][1] if ranked and ranked[0][0] >= 0.20 else None


def pair_history_for(logical_a, logical_b, interactions):
    if logical_a is None or logical_b is None:
        return 0
    key = tuple(sorted((logical_a.track_id, logical_b.track_id)))
    for interaction in interactions:
        if tuple(sorted((interaction.track_a, interaction.track_b))) == key:
            return len(interaction.distance_history)
    return 0


def run() -> int:
    positive_manifest = json.loads((PHASE2B / "positive_collision_ground_truth.json").read_text())
    negative_manifest = json.loads((PHASE2B / "negative_replay_manifest.json").read_text())
    baseline = json.loads((PHASE5 / "baseline_tracking.json").read_text())
    config = CONFIGS["N640"]
    process = psutil.Process()
    process.cpu_percent(None)
    psutil.cpu_percent(None)
    rss_before = process.memory_info().rss / (1024 * 1024)
    logical_ms: list[float] = []
    handoff_ms: list[float] = []
    temporal_ms: list[float] = []
    total_ms: list[float] = []
    positive_snapshots = []
    positive_rows = []
    positive_key = "phase5-integrated-positive"
    event_manager = manager()
    try:
        for annotation, native in load_positive_frames(positive_manifest):
            result = analyze_frame(native, config, positive_key, float(annotation["timestamp"]), event_manager)
            continuity = main.LOGICAL_VEHICLE_CONTINUITY.get_last_result(positive_key)
            if continuity is None:
                raise RuntimeError("Logical continuity result was not produced")
            pair = main.classify_collision_pair_regions(
                native, result["tiers"], full_frame_score=result["model1_score"], camera_id=positive_key
            )
            assignments = assign_two(
                {"A": annotation["participant_a_bbox"], "B": annotation["participant_b_bbox"]},
                list(result["tiers"].raw),
            )
            participant_rows = {}
            logical_matches = {}
            for name in ("A", "B"):
                detection = assignments[name][0] if assignments[name] else None
                eligible = bool(
                    detection and (
                        detection.get("detectionState") == "TRUSTED"
                        or detection.get("candidateSupported")
                    )
                )
                logical = best_logical_match(annotation[f"participant_{name.lower()}_bbox"], continuity.active_tracks) if eligible else None
                logical_matches[name] = logical
                participant_rows[name] = {
                    "detection_available": detection is not None,
                    "eligible_phase2_evidence": eligible,
                    "tier": detection.get("detectionState") if detection else "MODEL2_NO_BOX",
                    "supported_candidate": bool(detection and detection.get("candidateSupported")),
                    "raw_track_id": raw_id_for_detection(detection, result["tracking"].active_tracks),
                    "logical_vehicle_id": logical.logical_vehicle_id if logical else None,
                    "logical_state": logical.state if logical else None,
                    "motion_observed": logical.motion_observed if logical else False,
                    "observation_source": logical.observation_source if logical else None,
                    "logical_history_length": len(logical.history) if logical else 0,
                    "bbox": box_xyxy(detection) if detection else None,
                    "class": detection.get("label") if detection else None,
                    "confidence": detection.get("confidence") if detection else None,
                }
            interactions = main.TEMPORAL_CRASH_VERIFIER.get_interactions(positive_key)
            combined_ms = result["timing"]["total_ai_ms"] + pair["pairClassificationMs"]
            logical_ms.append(continuity.processing_ms)
            handoff_ms.append(continuity.handoff_matching_ms)
            temporal_ms.append(result["temporal"].analysis_ms)
            total_ms.append(combined_ms)
            positive_snapshots.append(
                {
                    "timestamp": float(annotation["timestamp"]),
                    "tracks": copy.deepcopy(result["tracking"].active_tracks),
                    "detections": copy.deepcopy(result["tiers"].tracker_input),
                    "collision_pair_boxes": tuple(
                        evaluation
                        for evaluation in (
                            pair["selectedPair"]["pairA"] if pair["selectedPair"] else None,
                            pair["selectedPair"]["pairB"] if pair["selectedPair"] else None,
                        )
                        if evaluation is not None
                    ),
                }
            )
            positive_rows.append(
                {
                    "frame_index": int(annotation["frame_index"]),
                    "timestamp": float(annotation["timestamp"]),
                    "participants": participant_rows,
                    "logical_collision_pairs": [list(value) for value in continuity.logical_pairs],
                    "pair_history_length": pair_history_for(logical_matches["A"], logical_matches["B"], interactions),
                    "handoff_attempts": continuity.handoff_attempts,
                    "accepted_handoffs": continuity.accepted_handoffs,
                    "rejected_handoffs": continuity.rejected_handoffs,
                    "ambiguous_handoffs": continuity.ambiguous_handoffs,
                    "provisional_observations": continuity.provisional_observations,
                    "temporal_score_before": next(row["temporal_score"] for row in baseline["frames"] if row["frame_index"] == int(annotation["frame_index"])),
                    "temporal_score_after": round(result["temporal"].score, 4),
                    "temporal_reason": result["temporal"].reason,
                    "final_decision": decision_name(result),
                    "logical_continuity_ms": round(continuity.processing_ms, 4),
                    "handoff_matching_ms": round(continuity.handoff_matching_ms, 4),
                }
            )
    finally:
        reset_pipeline(positive_key)

    window_rows = []
    for window in (0.5, 1.0, 1.5):
        service = LogicalVehicleContinuityService(LogicalContinuityConfig(max_handoff_seconds=window))
        b_ids = []
        for snapshot, row in zip(positive_snapshots, positive_rows):
            result = service.update(
                "window-test", snapshot["tracks"], snapshot["detections"],
                frame_width=640, frame_height=360, timestamp=snapshot["timestamp"],
                collision_pair_boxes=snapshot["collision_pair_boxes"],
            )
            if row["participants"]["B"]["eligible_phase2_evidence"]:
                match = best_logical_match(row["participants"]["B"]["bbox"], result.active_tracks)
                b_ids.append(match.logical_vehicle_id if match else None)
        window_rows.append(
            {
                "max_handoff_seconds": window,
                "participant_b_logical_ids": b_ids,
                "continuity_when_evidence_exists": len(set(b_ids)) == 1 and None not in b_ids,
                "retention_risk": "lowest" if window == 0.5 else "balanced" if window == 1.0 else "highest",
            }
        )

    negative_rows = []
    source_root = Path(negative_manifest["source_root"])
    fps = float(negative_manifest["assumed_source_fps"])
    for sequence in negative_manifest["sequences"]:
        camera_key = f"phase5-negative-{sequence['sequence_id']}"
        event_manager = manager()
        counters = {"attempts": 0, "accepted": 0, "rejected": 0, "ambiguous": 0, "provisional": 0, "pairs": 0}
        decisions = []
        first_index = int(sequence["frame_indices"][0])
        try:
            for frame_index in sequence["frame_indices"]:
                native = cv2.imread(str(source_root / f"{frame_index}.jpg"))
                if native is None:
                    raise RuntimeError(f"Could not read negative frame {frame_index}")
                timestamp = (int(frame_index) - first_index) / fps
                result = analyze_frame(native, config, camera_key, timestamp, event_manager)
                continuity = main.LOGICAL_VEHICLE_CONTINUITY.get_last_result(camera_key)
                if continuity is None:
                    raise RuntimeError("Missing negative continuity result")
                pair = main.classify_collision_pair_regions(
                    native, result["tiers"], full_frame_score=result["model1_score"], camera_id=camera_key
                )
                counters["attempts"] += continuity.handoff_attempts
                counters["accepted"] += continuity.accepted_handoffs
                counters["rejected"] += continuity.rejected_handoffs
                counters["ambiguous"] += continuity.ambiguous_handoffs
                counters["provisional"] += continuity.provisional_observations
                counters["pairs"] += len(continuity.logical_pairs)
                logical_ms.append(continuity.processing_ms)
                handoff_ms.append(continuity.handoff_matching_ms)
                temporal_ms.append(result["temporal"].analysis_ms)
                total_ms.append(result["timing"]["total_ai_ms"] + pair["pairClassificationMs"])
                decisions.append(decision_name(result))
        finally:
            reset_pipeline(camera_key)
        negative_rows.append(
            {
                "sequence_id": sequence["sequence_id"],
                "category": sequence["category"],
                **counters,
                "confirmed_crash": "confirmed_crash" in decisions,
                "pending_review": "possible_crash_aftermath" in decisions,
                "final_decision": next((value for value in reversed(decisions) if value != "ignored"), "ignored"),
            }
        )

    b_rows = [row for row in positive_rows if row["participants"]["B"]["eligible_phase2_evidence"]]
    b_ids = [row["participants"]["B"]["logical_vehicle_id"] for row in b_rows]
    payload = {
        "schema_version": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "configuration": {
            "max_handoff_seconds": main.TRACK_CONTINUITY_CONFIG.max_handoff_seconds,
            "max_displacement_normalized": main.TRACK_CONTINUITY_CONFIG.max_center_displacement_normalized,
            "minimum_size_similarity": main.TRACK_CONTINUITY_CONFIG.minimum_size_similarity,
            "minimum_handoff_score": main.TRACK_CONTINUITY_CONFIG.minimum_handoff_score,
            "ambiguity_margin": main.TRACK_CONTINUITY_CONFIG.ambiguity_margin,
            "max_identities_per_camera": main.TRACK_CONTINUITY_CONFIG.max_identities_per_camera,
            "model2_imgsz": 640,
            "model2_frame": "native",
        },
        "handoff_window_benchmark": window_rows,
        "positive": {
            "frames": positive_rows,
            "physical_both_participant_availability_percent": 50.0,
            "logical_both_participant_availability_when_phase2_evidence_exists_percent": round(100.0 * sum(bool(row["participants"]["A"]["logical_vehicle_id"] and row["participants"]["B"]["logical_vehicle_id"]) for row in b_rows) / max(1, len(b_rows)), 2),
            "participant_b_logical_ids_when_evidence_exists": b_ids,
            "participant_b_continuity": len(set(b_ids)) == 1 and None not in b_ids,
            "maximum_pair_history_length": max(row["pair_history_length"] for row in positive_rows),
            "maximum_temporal_score_before": baseline["maximum_temporal_score"],
            "maximum_temporal_score_after": max(row["temporal_score_after"] for row in positive_rows),
            "final_decision": next((row["final_decision"] for row in reversed(positive_rows) if row["final_decision"] != "ignored"), "ignored"),
        },
        "negative": {
            "sequences": negative_rows,
            "frames": sum(len(row["frame_indices"]) for row in negative_manifest["sequences"]),
            "handoff_attempts": sum(row["attempts"] for row in negative_rows),
            "accepted_handoffs": sum(row["accepted"] for row in negative_rows),
            "rejected_handoffs": sum(row["rejected"] for row in negative_rows),
            "ambiguous_handoffs": sum(row["ambiguous"] for row in negative_rows),
            "provisional_observations": sum(row["provisional"] for row in negative_rows),
            "logical_collision_pairs": sum(row["pairs"] for row in negative_rows),
            "confirmed_false_crashes": sum(row["confirmed_crash"] for row in negative_rows),
            "pending_review_false_positives": sum(row["pending_review"] for row in negative_rows),
        },
        "performance": {
            "logical_continuity": latency_summary(logical_ms),
            "handoff_matching": latency_summary(handoff_ms),
            "temporal": latency_summary(temporal_ms),
            "total_ai": latency_summary(total_ms),
            "ai_fps": round(1000.0 / statistics.fmean(total_ms), 3),
            "process_cpu_percent_multicore": process.cpu_percent(None),
            "system_cpu_percent": psutil.cpu_percent(None),
            "rss_before_mb": round(rss_before, 3),
            "rss_after_mb": round(process.memory_info().rss / (1024 * 1024), 3),
        },
    }
    PHASE5.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(f"Saved {RESULT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
