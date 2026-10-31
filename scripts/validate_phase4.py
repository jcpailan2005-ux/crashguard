"""Replay the fixed Phase 2B corpus through the integrated Phase 4 pair path."""

from __future__ import annotations

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
from scripts.benchmark_phase3_resolution import (
    CONFIGS,
    analyze_frame,
    assign_two,
    box_xyxy,
    iou,
    latency_summary,
    load_positive_frames,
    percentile,
    reset_pipeline,
)

PHASE2B = ROOT / "backend" / "validation" / "phase2b"
PHASE3 = ROOT / "backend" / "validation" / "phase3"
PHASE4 = ROOT / "backend" / "validation" / "phase4"
RESULT_PATH = PHASE4 / "validation_results.json"


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
        return "confirmed_crash" if event.detection_mode == "temporal_collision" else "possible_crash_aftermath"
    return "ignored"


def score_distribution(values: list[float]) -> dict | None:
    if not values:
        return None
    return {
        "count": len(values),
        "mean": round(statistics.fmean(values), 4),
        "median": round(statistics.median(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "p95": round(percentile(values, 0.95), 4),
    }


def selected_matches_ground_truth(selected: dict | None, annotation: dict) -> bool:
    if not selected:
        return False
    a = selected["pairA"]["box"]
    b = selected["pairB"]["box"]
    gt_a = annotation["participant_a_bbox"]
    gt_b = annotation["participant_b_bbox"]
    return bool(
        (iou(a, gt_a) >= 0.20 and iou(b, gt_b) >= 0.20)
        or (iou(a, gt_b) >= 0.20 and iou(b, gt_a) >= 0.20)
    )


def run() -> int:
    positive_manifest = json.loads((PHASE2B / "positive_collision_ground_truth.json").read_text())
    negative_manifest = json.loads((PHASE2B / "negative_replay_manifest.json").read_text())
    baseline = json.loads((PHASE4 / "baseline_results.json").read_text())
    config = CONFIGS["N640"]
    process = psutil.Process()
    process.cpu_percent(None)
    psutil.cpu_percent(None)
    rss_before = process.memory_info().rss / (1024 * 1024)
    all_full_model1_ms: list[float] = []
    all_pair_model1_ms: list[float] = []
    all_total_model1_when_pair_selected_ms: list[float] = []
    all_same_run_without_pair_total_ms: list[float] = []
    all_total_ms: list[float] = []
    positive_pair_scores: list[float] = []
    negative_pair_scores: list[float] = []

    positive_rows = []
    positive_key = "phase4-integrated-positive"
    manager = event_manager()
    try:
        for annotation, native in load_positive_frames(positive_manifest):
            result = analyze_frame(native, config, positive_key, float(annotation["timestamp"]), manager)
            pair = main.classify_collision_pair_regions(
                native,
                result["tiers"],
                full_frame_score=result["model1_score"],
                camera_id=positive_key,
            )
            assignments = assign_two(
                {"A": annotation["participant_a_bbox"], "B": annotation["participant_b_bbox"]},
                list(result["tiers"].raw),
            )
            eligible = {
                name: bool(match and (match[0].get("detectionState") == "TRUSTED" or match[0].get("candidateSupported")))
                for name, match in assignments.items()
            }
            is_actual = selected_matches_ground_truth(pair["selectedPair"], annotation)
            pair_score = pair["pairRegionCrashScore"] if is_actual else None
            if pair_score is not None:
                positive_pair_scores.append(float(pair_score))
            combined_ms = result["timing"]["total_ai_ms"] + pair["pairClassificationMs"]
            all_full_model1_ms.append(result["timing"]["model1_ms"])
            all_same_run_without_pair_total_ms.append(result["timing"]["total_ai_ms"])
            if pair["pairClassificationMs"] > 0:
                all_pair_model1_ms.append(pair["pairClassificationMs"])
                all_total_model1_when_pair_selected_ms.append(
                    result["timing"]["model1_ms"] + pair["pairClassificationMs"]
                )
            all_total_ms.append(combined_ms)
            positive_rows.append(
                {
                    "frame_index": int(annotation["frame_index"]),
                    "full_frame_crash_score": round(result["model1_score"], 4),
                    "participant_eligible": eligible,
                    "collision_pair_available": bool(eligible["A"] and eligible["B"]),
                    "selected_pair_is_collision_pair": is_actual,
                    "selected_pair": pair["selectedPair"],
                    "pair_selection_reason": pair["pairSelectionReason"],
                    "pair_region_coordinates": (
                        pair["pairRegionEvaluations"][0]["crop"] if pair["pairRegionEvaluations"] else None
                    ),
                    "pair_region_crash_score": round(pair_score, 4) if pair_score is not None else None,
                    "visual_evidence_score_diagnostic_only": round(pair["visualEvidenceScore"], 4),
                    "temporal_score": round(result["temporal"].score, 4),
                    "aftermath_score": round(result["aftermath"].score, 4),
                    "final_decision": decision_name(result),
                    "full_frame_model1_ms": round(result["timing"]["model1_ms"], 3),
                    "pair_model1_ms": round(pair["pairClassificationMs"], 3),
                    "combined_total_ai_ms": round(combined_ms, 3),
                }
            )
    finally:
        reset_pipeline(positive_key)

    negative_rows = []
    source_root = Path(negative_manifest["source_root"])
    fps = float(negative_manifest["assumed_source_fps"])
    for sequence in negative_manifest["sequences"]:
        camera_key = f"phase4-integrated-{sequence['sequence_id']}"
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
                pair = main.classify_collision_pair_regions(
                    native,
                    result["tiers"],
                    full_frame_score=result["model1_score"],
                    camera_id=camera_key,
                )
                combined_ms = result["timing"]["total_ai_ms"] + pair["pairClassificationMs"]
                all_full_model1_ms.append(result["timing"]["model1_ms"])
                all_same_run_without_pair_total_ms.append(result["timing"]["total_ai_ms"])
                if pair["pairClassificationMs"] > 0:
                    all_pair_model1_ms.append(pair["pairClassificationMs"])
                    all_total_model1_when_pair_selected_ms.append(
                        result["timing"]["model1_ms"] + pair["pairClassificationMs"]
                    )
                all_total_ms.append(combined_ms)
                if pair["pairRegionCrashScore"] is not None:
                    negative_pair_scores.append(float(pair["pairRegionCrashScore"]))
                rows.append((result, pair))
        finally:
            reset_pipeline(camera_key)
        decisions = [decision_name(result) for result, _pair in rows]
        negative_rows.append(
            {
                "sequence_id": sequence["sequence_id"],
                "category": sequence["category"],
                "frames": len(rows),
                "plausible_pair_frames": sum(bool(pair["selectedPair"]) for _result, pair in rows),
                "highest_full_frame_score": round(max(result["model1_score"] for result, _pair in rows), 4),
                "highest_pair_region_score": round(max((pair["pairRegionCrashScore"] or 0.0) for _result, pair in rows), 4),
                "highest_temporal_score": round(max(result["temporal"].score for result, _pair in rows), 4),
                "confirmed_crash": "confirmed_crash" in decisions,
                "pending_review": "possible_crash_aftermath" in decisions,
                "final_decision": next((value for value in reversed(decisions) if value != "ignored"), "ignored"),
            }
        )

    person_manifest = json.loads((PHASE3 / "person_only_ground_truth.json").read_text())
    person_sample = person_manifest["samples"][0]
    person_native = cv2.imread(person_sample["path"])
    if person_native is None:
        raise RuntimeError("Could not read the fixed person-only regression sample")
    person_key = "phase4-person-only"
    try:
        person_result = analyze_frame(person_native, config, person_key, 0.0)
        person_pair = main.classify_collision_pair_regions(
            person_native,
            person_result["tiers"],
            full_frame_score=person_result["model1_score"],
            camera_id=person_key,
        )
    finally:
        reset_pipeline(person_key)

    positive_distribution = score_distribution(positive_pair_scores)
    negative_distribution = score_distribution(negative_pair_scores)
    after_total = latency_summary(all_total_ms)
    baseline_total = baseline["performance"]["total_ai"]
    pair_calls = len(all_pair_model1_ms)
    total_frames = len(all_total_ms)
    amortized_pair_ms = sum(all_pair_model1_ms) / max(1, total_frames)
    payload = {
        "schema_version": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "configuration": {
            "model2_frame": "native",
            "model2_imgsz": 640,
            "model1_full_frame": [640, 360],
            "pair_context_margin": main.COLLISION_PAIR_CONTEXT_MARGIN,
            "max_pair_classifications_per_frame": main.MAX_COLLISION_PAIR_CLASSIFICATIONS,
            "pair_evidence_authoritative": False,
        },
        "positive": {
            "frames": positive_rows,
            "actual_collision_pair_score_distribution": positive_distribution,
            "final_decision": next((row["final_decision"] for row in reversed(positive_rows) if row["final_decision"] != "ignored"), "ignored"),
        },
        "negative": {
            "frames": sum(row["frames"] for row in negative_rows),
            "sequences": negative_rows,
            "pair_score_distribution": negative_distribution,
            "confirmed_false_crashes": sum(row["confirmed_crash"] for row in negative_rows),
            "pending_review_false_positives": sum(row["pending_review"] for row in negative_rows),
        },
        "person_only": {
            "sample_id": person_sample["sample_id"],
            "person_count": person_result["person_count"],
            "trusted_vehicle_count": len(person_result["tiers"].trusted),
            "supported_candidate_count": len(person_result["tiers"].supported_candidates),
            "selected_pair": person_pair["selectedPair"],
            "pair_region_crash_score": person_pair["pairRegionCrashScore"],
            "passed": person_pair["selectedPair"] is None,
        },
        "score_separation": {
            "positive_mean": round(statistics.fmean(positive_pair_scores), 4),
            "negative_mean": round(statistics.fmean(negative_pair_scores), 4),
            "mean_difference": round(statistics.fmean(positive_pair_scores) - statistics.fmean(negative_pair_scores), 4),
            "assessment": "mixed",
            "decision_use": "diagnostic_only",
        },
        "performance": {
            "baseline_total_ai": baseline_total,
            "after_full_frame_model1": latency_summary(all_full_model1_ms),
            "after_pair_model1_when_selected": latency_summary(all_pair_model1_ms),
            "pair_classifier_calls": pair_calls,
            "frames_replayed": total_frames,
            "pair_call_rate_percent": round(100.0 * pair_calls / max(1, total_frames), 2),
            "amortized_pair_model1_ms_per_frame": round(amortized_pair_ms, 3),
            "total_model1_when_pair_selected": latency_summary(
                all_total_model1_when_pair_selected_ms
            ),
            "same_run_without_pair_total_ai": latency_summary(
                all_same_run_without_pair_total_ms
            ),
            "after_total_ai": after_total,
            "mean_total_ai_delta_ms": round(after_total["mean_ms"] - baseline_total["mean_ms"], 3),
            "after_ai_fps": round(1000.0 / statistics.fmean(all_total_ms), 3),
            "process_cpu_percent_multicore": process.cpu_percent(None),
            "system_cpu_percent": psutil.cpu_percent(None),
            "rss_before_mb": round(rss_before, 3),
            "rss_after_mb": round(process.memory_info().rss / (1024 * 1024), 3),
        },
    }
    PHASE4.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(f"Saved {RESULT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
