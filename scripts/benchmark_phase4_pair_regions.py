"""Benchmark 10/20/30% native vehicle-pair context margins before integration."""

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
from backend.services.collision_pair_classifier import (
    CollisionPairConfig,
    build_pair_region,
    select_plausible_pairs,
    supporting_visual_evidence,
)
from backend.services.crash_event_state import CrashEventManager
from scripts.benchmark_phase3_resolution import (
    CONFIGS,
    analyze_frame,
    assign_two,
    box_xyxy,
    iou,
    load_positive_frames,
    percentile,
    reset_pipeline,
)


PHASE2B = ROOT / "backend" / "validation" / "phase2b"
PHASE4 = ROOT / "backend" / "validation" / "phase4"
RESULT_PATH = PHASE4 / "pair_margin_benchmark.json"
MARGINS = (0.10, 0.20, 0.30)


def distribution(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "mean": None, "median": None, "min": None, "max": None, "p95": None}
    return {
        "count": len(values),
        "mean": round(statistics.fmean(values), 4),
        "median": round(statistics.median(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "p95": round(percentile(values, 0.95), 4),
    }


def manager() -> CrashEventManager:
    return CrashEventManager(
        required_positive_observations=main.LIVE_CAMERA_REQUIRED_HITS,
        temporal_window_seconds=main.CRASH_TEMPORAL_WINDOW_SECONDS,
        clear_consecutive_negatives=main.EVENT_CLEAR_CONSECUTIVE_NEGATIVES,
        clear_seconds=main.EVENT_CLEAR_SECONDS,
        cooldown_seconds=main.EVENT_COOLDOWN_SECONDS,
    )


def classify_regions(native, pairs, full_score: float):
    rows = {}
    for margin in MARGINS:
        config = CollisionPairConfig(max_pairs_per_frame=1, context_margin=margin)
        region = build_pair_region(native, pairs[0], config=config) if pairs else None
        if region is None or not region.valid:
            rows[str(margin)] = {
                "valid": False,
                "coordinates": region.coordinates if region else None,
                "reason": region.reason if region else "no_plausible_pair",
                "pair_region_score": None,
                "visual_evidence_score": round(full_score, 4),
                "model1_ms": 0.0,
            }
            continue
        started = time.perf_counter()
        classified = main.classify_crash_frame(region.crop)
        latency = (time.perf_counter() - started) * 1000.0
        pair_score = float(classified.get("accidentProbability") or 0.0)
        rows[str(margin)] = {
            "valid": True,
            "coordinates": list(region.coordinates),
            "dimensions": [
                region.coordinates[2] - region.coordinates[0],
                region.coordinates[3] - region.coordinates[1],
            ],
            "reason": region.reason,
            "pair_region_score": round(pair_score, 4),
            "visual_evidence_score": round(
                supporting_visual_evidence(full_score, pair_score), 4
            ),
            "model1_ms": round(latency, 3),
        }
    return rows


def pair_matches_ground_truth(pair, annotation) -> bool:
    if pair is None:
        return False
    gt_a, gt_b = annotation["participant_a_bbox"], annotation["participant_b_bbox"]
    a_box, b_box = box_xyxy(pair.pair_a), box_xyxy(pair.pair_b)
    return bool(
        (iou(a_box, gt_a) >= 0.20 and iou(b_box, gt_b) >= 0.20)
        or (iou(a_box, gt_b) >= 0.20 and iou(b_box, gt_a) >= 0.20)
    )


def main_benchmark() -> int:
    positive_manifest = json.loads(
        (PHASE2B / "positive_collision_ground_truth.json").read_text(encoding="utf-8")
    )
    negative_manifest = json.loads(
        (PHASE2B / "negative_replay_manifest.json").read_text(encoding="utf-8")
    )
    config = CONFIGS["N640"]
    process = psutil.Process()
    process.cpu_percent(None)
    psutil.cpu_percent(None)
    rss_before = process.memory_info().rss / (1024 * 1024)
    positive_rows = []
    positive_key = "phase4-pair-positive"
    try:
        for annotation, native in load_positive_frames(positive_manifest):
            result = analyze_frame(native, config, positive_key, float(annotation["timestamp"]), manager())
            pairs = select_plausible_pairs(
                result["tiers"].tracker_input,
                frame_width=native.shape[1],
                frame_height=native.shape[0],
                config=CollisionPairConfig(max_pairs_per_frame=1),
            )
            assignments = assign_two(
                {"A": annotation["participant_a_bbox"], "B": annotation["participant_b_bbox"]},
                list(result["tiers"].raw),
            )
            participant_eligible = {
                key: bool(
                    match
                    and (
                        match[0].get("detectionState") == "TRUSTED"
                        or match[0].get("candidateSupported")
                    )
                )
                for key, match in assignments.items()
            }
            positive_rows.append(
                {
                    "frame_index": int(annotation["frame_index"]),
                    "full_frame_score": round(result["model1_score"], 4),
                    "participant_eligible": participant_eligible,
                    "pair_selected": bool(pairs),
                    "selected_pair_is_ground_truth_pair": pair_matches_ground_truth(
                        pairs[0] if pairs else None, annotation
                    ),
                    "selection": (
                        {
                            "source": pairs[0].source,
                            "reason": pairs[0].selection_reason,
                            "score": round(pairs[0].selection_score, 4),
                            "edge_distance_normalized": round(pairs[0].edge_distance_normalized, 4),
                            "center_distance_normalized": round(pairs[0].center_distance_normalized, 4),
                            "iou": round(pairs[0].iou, 4),
                            "pair_a": pairs[0].pair_a,
                            "pair_b": pairs[0].pair_b,
                        }
                        if pairs else None
                    ),
                    "margins": classify_regions(native, pairs, result["model1_score"]),
                    "temporal_score": round(result["temporal"].score, 4),
                    "aftermath_score": round(result["aftermath"].score, 4),
                    "baseline_total_ai_ms": round(result["timing"]["total_ai_ms"], 3),
                }
            )
    finally:
        reset_pipeline(positive_key)

    negative_sequences = []
    negative_pair_scores = {str(margin): [] for margin in MARGINS}
    pair_latencies = {str(margin): [] for margin in MARGINS}
    source_root = Path(negative_manifest["source_root"])
    fps = float(negative_manifest["assumed_source_fps"])
    for sequence in negative_manifest["sequences"]:
        camera_key = f"phase4-pair-{sequence['sequence_id']}"
        event_manager = manager()
        first_index = int(sequence["frame_indices"][0])
        pair_count = 0
        max_full = max_pair = max_temporal = 0.0
        confirmed = pending = False
        try:
            for frame_index in sequence["frame_indices"]:
                native = cv2.imread(str(source_root / f"{frame_index}.jpg"))
                if native is None:
                    raise RuntimeError(f"Could not read negative frame {frame_index}")
                timestamp = (int(frame_index) - first_index) / fps
                result = analyze_frame(native, config, camera_key, timestamp, event_manager)
                pairs = select_plausible_pairs(
                    result["tiers"].tracker_input,
                    frame_width=native.shape[1],
                    frame_height=native.shape[0],
                    config=CollisionPairConfig(max_pairs_per_frame=1),
                )
                margin_rows = classify_regions(native, pairs, result["model1_score"])
                pair_count += int(bool(pairs))
                max_full = max(max_full, result["model1_score"])
                max_temporal = max(max_temporal, result["temporal"].score)
                for margin, row in margin_rows.items():
                    if row["pair_region_score"] is not None:
                        negative_pair_scores[margin].append(row["pair_region_score"])
                        pair_latencies[margin].append(row["model1_ms"])
                        max_pair = max(max_pair, row["pair_region_score"])
                event = result["event"]
                if event and event.should_persist:
                    confirmed |= event.detection_mode == "temporal_collision"
                    pending |= event.detection_mode == "aftermath_review"
        finally:
            reset_pipeline(camera_key)
        negative_sequences.append(
            {
                "sequence_id": sequence["sequence_id"],
                "category": sequence["category"],
                "plausible_pairs_selected": pair_count,
                "highest_full_frame_score": round(max_full, 4),
                "highest_pair_region_score_across_margins": round(max_pair, 4),
                "highest_temporal_score": round(max_temporal, 4),
                "confirmed_crash": confirmed,
                "pending_review": pending,
                "final_decision": (
                    "confirmed_crash" if confirmed else "possible_crash_aftermath" if pending else "ignored"
                ),
            }
        )

    positive_distributions = {}
    for margin in MARGINS:
        key = str(margin)
        scores = [
            row["margins"][key]["pair_region_score"]
            for row in positive_rows
            if row["selected_pair_is_ground_truth_pair"]
            and row["margins"][key]["pair_region_score"] is not None
        ]
        positive_distributions[key] = distribution(scores)
    payload = {
        "schema_version": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "configuration": {
            "model2_frame": "native",
            "model2_imgsz": 640,
            "max_pairs_per_frame": 1,
            "margins_tested": list(MARGINS),
        },
        "positive": {
            "frames": positive_rows,
            "pair_score_distributions": positive_distributions,
        },
        "negative": {
            "sequences": negative_sequences,
            "frames": sum(len(row["frame_indices"]) for row in negative_manifest["sequences"]),
            "pair_score_distributions": {
                margin: distribution(scores) for margin, scores in negative_pair_scores.items()
            },
            "pair_model1_latency_distributions": {
                margin: distribution(values) for margin, values in pair_latencies.items()
            },
            "confirmed_false_crashes": sum(row["confirmed_crash"] for row in negative_sequences),
            "pending_review_false_positives": sum(row["pending_review"] for row in negative_sequences),
        },
        "performance": {
            "process_cpu_percent_multicore": process.cpu_percent(None),
            "system_cpu_percent": psutil.cpu_percent(None),
            "rss_before_mb": round(rss_before, 3),
            "rss_after_mb": round(process.memory_info().rss / (1024 * 1024), 3),
        },
    }
    RESULT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(f"Saved {RESULT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_benchmark())
