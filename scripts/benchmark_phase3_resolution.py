"""Benchmark Phase 3 detector resolutions on the fixed Phase 2B corpus.

This is a development-only replay. It does not alter runtime configuration,
annotations, model weights, thresholds, tracking, or incident persistence.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import main
from backend.services.crash_event_state import CrashEventManager


PHASE2B = ROOT / "backend" / "validation" / "phase2b"
PHASE3 = ROOT / "backend" / "validation" / "phase3"
POSITIVE_MANIFEST = PHASE2B / "positive_collision_ground_truth.json"
NEGATIVE_MANIFEST = PHASE2B / "negative_replay_manifest.json"
RESULT_PATH = PHASE3 / "benchmark_results.json"
IOU_THRESHOLD = 0.20
BASELINE_SIZE = (640, 360)


@dataclass(frozen=True)
class BenchmarkConfig:
    name: str
    frame_size: tuple[int, int] | None
    imgsz: int
    description: str


CONFIGS = {
    "A": BenchmarkConfig("A", (640, 360), 640, "current baseline"),
    "B": BenchmarkConfig("B", (960, 540), 640, "higher source frame only"),
    "C": BenchmarkConfig("C", (960, 540), 768, "moderate detector input"),
    "D": BenchmarkConfig("D", (1280, 720), 960, "higher detector input"),
    "N640": BenchmarkConfig("N640", None, 640, "native-frame control"),
    "N768": BenchmarkConfig("N768", None, 768, "native-frame moderate control"),
    "N960": BenchmarkConfig("N960", None, 960, "native-frame high control"),
}


def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percent
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    fraction = position - low
    return ordered[low] + (ordered[high] - ordered[low]) * fraction


def latency_summary(values: list[float]) -> dict:
    return {
        "mean_ms": round(statistics.fmean(values), 3),
        "median_ms": round(statistics.median(values), 3),
        "p95_ms": round(percentile(values, 0.95), 3),
    }


def box_xyxy(box: dict) -> list[float]:
    if box.get("box") is not None:
        return [float(value) for value in box["box"][:4]]
    x1, y1 = float(box.get("x") or 0.0), float(box.get("y") or 0.0)
    return [
        x1,
        y1,
        x1 + float(box.get("width") or 0.0),
        y1 + float(box.get("height") or 0.0),
    ]


def iou(a, b) -> float:
    ax1, ay1, ax2, ay2 = (float(value) for value in a)
    bx1, by1, bx2, by2 = (float(value) for value in b)
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if intersection <= 0.0:
        return 0.0
    union = (
        max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
        + max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
        - intersection
    )
    return intersection / union if union > 0.0 else 0.0


def assign_two(gt_boxes: dict[str, list[float]], predictions: list[dict]):
    pairs = []
    for participant, gt_box in gt_boxes.items():
        for index, prediction in enumerate(predictions):
            score = iou(gt_box, box_xyxy(prediction))
            if score >= IOU_THRESHOLD:
                pairs.append((score, participant, index))
    pairs.sort(reverse=True)
    assignments = {participant: None for participant in gt_boxes}
    used_participants: set[str] = set()
    used_predictions: set[int] = set()
    for score, participant, index in pairs:
        if participant in used_participants or index in used_predictions:
            continue
        assignments[participant] = (predictions[index], score)
        used_participants.add(participant)
        used_predictions.add(index)
    return assignments


def scale_gt(box: list[float], source_size: tuple[int, int], target_size: tuple[int, int]):
    sx = target_size[0] / source_size[0]
    sy = target_size[1] / source_size[1]
    return [box[0] * sx, box[1] * sy, box[2] * sx, box[3] * sy]


def detector_frame(native: np.ndarray, config: BenchmarkConfig) -> np.ndarray:
    if config.frame_size is None:
        return native.copy()
    return cv2.resize(native, config.frame_size, interpolation=cv2.INTER_AREA)


def baseline_frame(native: np.ndarray) -> np.ndarray:
    return cv2.resize(native, BASELINE_SIZE, interpolation=cv2.INTER_AREA)


def run_vehicle_model(frame: np.ndarray, imgsz: int):
    started = time.perf_counter()
    results = main.vehicle_model.predict(
        frame,
        conf=main.COLLISION_RAW_VEHICLE_CONFIDENCE_FLOOR,
        imgsz=imgsz,
        verbose=False,
    )
    elapsed = (time.perf_counter() - started) * 1000.0
    boxes = main.extract_vehicle_boxes_from_results(
        results, getattr(main.vehicle_model, "names", {}), frame
    )
    return boxes, elapsed


def reset_pipeline(camera_key: str) -> None:
    if hasattr(main, "LOGICAL_VEHICLE_CONTINUITY"):
        main.LOGICAL_VEHICLE_CONTINUITY.reset_camera(camera_key)
    main.VEHICLE_CANDIDATE_EVALUATOR.reset_camera(camera_key)
    main.VEHICLE_TRACKING_SERVICE.reset_camera(camera_key)
    main.TEMPORAL_CRASH_VERIFIER.reset_camera(camera_key)
    main.CRASH_AFTERMATH_DETECTOR.reset_camera(camera_key)


def tier_name(prediction: dict | None) -> tuple[str, bool]:
    if prediction is None:
        return "MODEL2_NO_BOX", False
    state = prediction.get("detectionState")
    if state == "TRUSTED":
        return "trusted", True
    if state == "CANDIDATE" and prediction.get("candidateSupported"):
        return "supported_candidate", True
    if state == "CANDIDATE":
        return "CANDIDATE_NOT_SUPPORTED", False
    return "BELOW_CANDIDATE_THRESHOLD", False


def actual_tensor_shape(frame: np.ndarray, imgsz: int) -> list[int]:
    observed: list[int] = []

    def hook(_module, inputs):
        tensor = inputs[0] if inputs else None
        if hasattr(tensor, "shape"):
            observed[:] = [int(value) for value in tensor.shape]

    handle = main.vehicle_model.model.register_forward_pre_hook(hook)
    try:
        main.vehicle_model.predict(
            frame,
            conf=main.COLLISION_RAW_VEHICLE_CONFIDENCE_FLOOR,
            imgsz=imgsz,
            verbose=False,
        )
    finally:
        handle.remove()
    return observed


def analyze_frame(
    native: np.ndarray,
    config: BenchmarkConfig,
    camera_key: str,
    timestamp: float,
    event_manager: CrashEventManager | None = None,
):
    native_before = native.copy()
    cycle_started = time.perf_counter()
    ai_frame = detector_frame(native, config)
    fixed_frame = baseline_frame(native)

    primary_started = time.perf_counter()
    primary_results = main.model.predict(fixed_frame, verbose=False)
    primary_ms = (time.perf_counter() - primary_started) * 1000.0
    person_count = main.count_labels_from_results(
        primary_results,
        getattr(main.model, "names", {}),
        main.PERSON_LABELS,
        min_confidence=main.LIVE_CAMERA_PERSON_CONFIDENCE_THRESHOLD,
    )

    raw_boxes, model2_ms = run_vehicle_model(ai_frame, config.imgsz)
    model1_started = time.perf_counter()
    classifier = main.classify_crash_frame(fixed_frame)
    model1_ms = (time.perf_counter() - model1_started) * 1000.0
    model1_score = float(classifier.get("accidentProbability") or 0.0)

    tier_started = time.perf_counter()
    tiers = main.VEHICLE_CANDIDATE_EVALUATOR.evaluate(
        camera_key,
        raw_boxes,
        classifier_score=model1_score,
        frame_width=ai_frame.shape[1],
        frame_height=ai_frame.shape[0],
        timestamp=timestamp,
    )
    tier_ms = (time.perf_counter() - tier_started) * 1000.0
    tracking, temporal = main.analyze_vehicle_tracks(
        camera_key,
        list(tiers.tracker_input),
        ai_frame,
        classifier_score=model1_score,
        timestamp=timestamp,
    )
    temporal = main.enforce_candidate_confirmation_safety(temporal, tiers)
    quality = main.analyze_frame_quality(native)
    aftermath = main.CRASH_AFTERMATH_DETECTOR.observe(
        camera_key,
        classifier_score=model1_score,
        vehicle_count=len(tiers.trusted),
        active_tracks=tracking.active_tracks,
        scene_valid=True,
        frame_quality_status=quality["frameQualityStatus"],
        scene_abnormality_score=main.estimate_scene_abnormality(
            tracking.active_tracks, list(tiers.trusted)
        ),
        temporal_collision_active=temporal.is_verified,
        timestamp=timestamp,
    )
    resolved = main.resolve_crash_evidence(temporal, aftermath)
    event = None
    if event_manager is not None:
        positive = bool(
            quality["frameQualityStatus"] == "good"
            and len(tiers.trusted) > 0
            and resolved.should_signal_event
        )
        event = event_manager.observe(
            camera_key,
            positive=positive,
            interaction_candidate=resolved.should_signal_event,
            classifier_score=model1_score,
            now=timestamp,
            detection_mode=resolved.detection_mode,
        )

    if not np.array_equal(native, native_before):
        raise AssertionError("Detector preprocessing mutated the native source frame.")
    return {
        "ai_frame": ai_frame,
        "tiers": tiers,
        "tracking": tracking,
        "temporal": temporal,
        "aftermath": aftermath,
        "resolved": resolved,
        "event": event,
        "person_count": person_count,
        "model1_score": model1_score,
        "timing": {
            "primary_detector_ms": primary_ms,
            "model2_ms": model2_ms,
            "model1_ms": model1_ms,
            "vehicle_tier_ms": tier_ms,
            "tracking_ms": tracking.tracking_ms,
            "total_ai_ms": (time.perf_counter() - cycle_started) * 1000.0,
        },
    }


def load_positive_frames(manifest: dict):
    cap = cv2.VideoCapture(str(ROOT / manifest["source_video"]))
    if not cap.isOpened():
        raise RuntimeError("Could not open the Phase 2B positive collision video.")
    frames = []
    try:
        for annotation in manifest["annotations"]:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(annotation["frame_index"]))
            ok, frame = cap.read()
            if not ok or frame is None:
                raise RuntimeError(f"Could not read frame {annotation['frame_index']}.")
            frames.append((annotation, frame))
    finally:
        cap.release()
    return frames


def positive_replay(config: BenchmarkConfig, manifest: dict, frames) -> dict:
    camera_key = f"phase3-{config.name}-positive"
    observations = {"A": [], "B": []}
    source_size = (int(manifest["frame_width"]), int(manifest["frame_height"]))
    both = 0
    try:
        for annotation, native in frames:
            result = analyze_frame(
                native,
                config,
                camera_key,
                float(annotation["timestamp"]),
            )
            ai_frame = result["ai_frame"]
            target_size = (ai_frame.shape[1], ai_frame.shape[0])
            gt_boxes = {
                "A": scale_gt(annotation["participant_a_bbox"], source_size, target_size),
                "B": scale_gt(annotation["participant_b_bbox"], source_size, target_size),
            }
            assignments = assign_two(gt_boxes, list(result["tiers"].raw))
            retained_this_frame = {}
            for participant in ("A", "B"):
                assignment = assignments[participant]
                prediction, match_iou = assignment if assignment else (None, 0.0)
                tier, retained = tier_name(prediction)
                expected = manifest["participants"][participant]["class"]
                actual = str(prediction.get("label") or "") if prediction else None
                if prediction is None:
                    class_outcome = "no_box"
                elif main.normalize_box_label(actual or "") == main.normalize_box_label(expected):
                    class_outcome = "correct_class"
                elif main.normalize_box_label(actual or "") in main.VEHICLE_BOX_LABELS:
                    class_outcome = "wrong_vehicle_class_but_usable"
                else:
                    class_outcome = "non_vehicle_class"
                observations[participant].append(
                    {
                        "frame_index": int(annotation["frame_index"]),
                        "class": actual,
                        "confidence": (
                            round(float(prediction.get("confidence") or 0.0), 4)
                            if prediction else None
                        ),
                        "iou": round(match_iou, 4),
                        "tier": tier,
                        "retained": retained,
                        "class_outcome": class_outcome,
                    }
                )
                retained_this_frame[participant] = retained
            both += int(retained_this_frame["A"] and retained_this_frame["B"])
    finally:
        reset_pipeline(camera_key)

    summaries = {}
    for participant, rows in observations.items():
        tiers = Counter(row["tier"] for row in rows)
        retained = sum(row["retained"] for row in rows)
        summaries[participant] = {
            "observations": len(rows),
            "raw_detected": sum(row["confidence"] is not None for row in rows),
            "trusted": tiers["trusted"],
            "supported_candidate": tiers["supported_candidate"],
            "candidate_not_supported": tiers["CANDIDATE_NOT_SUPPORTED"],
            "below_candidate_threshold": tiers["BELOW_CANDIDATE_THRESHOLD"],
            "model2_no_box": tiers["MODEL2_NO_BOX"],
            "wrong_class_observations": sum(
                row["class_outcome"] == "wrong_vehicle_class_but_usable" for row in rows
            ),
            "missed": len(rows) - retained,
            "retention_percentage": round(100.0 * retained / max(1, len(rows)), 2),
        }
    return {
        "participant_summaries": summaries,
        "both_participant_observations": both,
        "both_participant_availability_percentage": round(
            100.0 * both / len(manifest["annotations"]), 2
        ),
        "trace": observations,
    }


def negative_replay(config: BenchmarkConfig, manifest: dict) -> tuple[dict, dict]:
    source_root = Path(manifest["source_root"])
    source_fps = float(manifest["assumed_source_fps"])
    timings: dict[str, list[float]] = {
        key: []
        for key in (
            "primary_detector_ms", "model2_ms", "model1_ms", "vehicle_tier_ms",
            "tracking_ms", "total_ai_ms",
        )
    }
    sequence_rows = []
    real_person_only = []
    for sequence in manifest["sequences"]:
        camera_key = f"phase3-{config.name}-{sequence['sequence_id']}"
        manager = CrashEventManager(
            required_positive_observations=main.LIVE_CAMERA_REQUIRED_HITS,
            temporal_window_seconds=main.CRASH_TEMPORAL_WINDOW_SECONDS,
            clear_consecutive_negatives=main.EVENT_CLEAR_CONSECUTIVE_NEGATIVES,
            clear_seconds=main.EVENT_CLEAR_SECONDS,
            cooldown_seconds=main.EVENT_COOLDOWN_SECONDS,
        )
        totals = Counter()
        confirmed = pending = False
        had_candidate = False
        first_index = int(sequence["frame_indices"][0])
        try:
            for frame_index in sequence["frame_indices"]:
                native = cv2.imread(str(source_root / f"{frame_index}.jpg"))
                if native is None:
                    raise RuntimeError(f"Could not read negative frame {frame_index}.")
                timestamp = (int(frame_index) - first_index) / source_fps
                result = analyze_frame(native, config, camera_key, timestamp, manager)
                tiers = result["tiers"]
                event = result["event"]
                if event and event.should_persist:
                    confirmed |= event.detection_mode == "temporal_collision"
                    pending |= event.detection_mode == "aftermath_review"
                totals["frames"] += 1
                totals["trusted"] += len(tiers.trusted)
                totals["candidate"] += len(tiers.candidates)
                totals["supported"] += len(tiers.supported_candidates)
                had_candidate |= bool(
                    tiers.supported_candidates or result["temporal"].is_candidate
                )
                if (
                    not tiers.trusted
                    and not tiers.supported_candidates
                    and result["person_count"] > 0
                ):
                    decision = main.evaluate_crash_case_decision(
                        crash_class="accident" if result["model1_score"] >= 0.5 else "non_accident",
                        crash_confidence=result["model1_score"],
                        vehicle_count=0,
                        supported_candidate_vehicle_count=0,
                        person_count=result["person_count"],
                        scene_valid=True,
                        motion_valid=False,
                        temporal_verified=False,
                        consecutive_positive_frames=0,
                        active_case_exists=False,
                        cooldown_ready=True,
                    )
                    if decision[1] == "person_only_not_crash":
                        real_person_only.append(
                            {"sequence_id": sequence["sequence_id"], "frame_index": frame_index}
                        )
                for key, value in result["timing"].items():
                    timings[key].append(float(value))
        finally:
            reset_pipeline(camera_key)
        sequence_rows.append(
            {
                "sequence_id": sequence["sequence_id"],
                "trusted_vehicle_detections": totals["trusted"],
                "candidate_detections": totals["candidate"],
                "supported_candidates": totals["supported"],
                "confirmed_crash": confirmed,
                "pending_review": pending,
                "candidate_only_activation": had_candidate and not confirmed and not pending,
            }
        )
    negative = {
        "sequences": len(sequence_rows),
        "frames": sum(row["trusted_vehicle_detections"] * 0 + 12 for row in sequence_rows),
        "trusted_vehicle_detections": sum(row["trusted_vehicle_detections"] for row in sequence_rows),
        "candidate_detections": sum(row["candidate_detections"] for row in sequence_rows),
        "supported_candidates": sum(row["supported_candidates"] for row in sequence_rows),
        "confirmed_crash_false_positives": sum(row["confirmed_crash"] for row in sequence_rows),
        "pending_review_false_positives": sum(row["pending_review"] for row in sequence_rows),
        "candidate_only_activations": sum(row["candidate_only_activation"] for row in sequence_rows),
        "real_person_only_frames": real_person_only,
        "sequence_results": sequence_rows,
    }
    return negative, {key: latency_summary(values) for key, values in timings.items()}


def benchmark_config(config: BenchmarkConfig, positive_manifest, positive_frames, negative_manifest):
    sample_native = positive_frames[0][1]
    sample_ai = detector_frame(sample_native, config)
    # Warm all models before memory and sustained timing measurements.
    for _ in range(2):
        main.model.predict(baseline_frame(sample_native), verbose=False)
        run_vehicle_model(sample_ai, config.imgsz)
        main.classify_crash_frame(baseline_frame(sample_native))
    tensor_shape = actual_tensor_shape(sample_ai, config.imgsz)
    process = psutil.Process()
    process.cpu_percent(None)
    psutil.cpu_percent(None)
    rss_warm_mb = process.memory_info().rss / (1024 * 1024)
    started = time.perf_counter()
    positive = positive_replay(config, positive_manifest, positive_frames)
    negative, performance = negative_replay(config, negative_manifest)
    elapsed = time.perf_counter() - started
    rss_after_mb = process.memory_info().rss / (1024 * 1024)
    result = {
        "name": config.name,
        "description": config.description,
        "detection_frame": list(config.frame_size) if config.frame_size else "native",
        "yolo_imgsz": config.imgsz,
        "actual_tensor_shape_nchw": tensor_shape,
        "aspect_ratio_preserved": config.frame_size is None or (
            abs(sample_native.shape[1] / sample_native.shape[0] - config.frame_size[0] / config.frame_size[1])
            < 1e-9
        ),
        "positive": positive,
        "negative": negative,
        "performance": {
            **performance,
            "ai_fps": round(1000.0 / performance["total_ai_ms"]["mean_ms"], 3),
            "process_cpu_percent_multicore": process.cpu_percent(None),
            "system_cpu_percent": psutil.cpu_percent(None),
            "rss_after_warmup_mb": round(rss_warm_mb, 3),
            "rss_after_replay_mb": round(rss_after_mb, 3),
            "wall_seconds": round(elapsed, 3),
        },
    }
    return result


def main_benchmark(selected_names: list[str]) -> int:
    if main.vehicle_model is None:
        raise RuntimeError(f"Vehicle model unavailable: {main.vehicle_model_error}")
    immutable = {
        "trusted": main.LIVE_CAMERA_VEHICLE_CONFIDENCE_THRESHOLD,
        "candidate": main.COLLISION_CANDIDATE_VEHICLE_CONFIDENCE_THRESHOLD,
        "temporal": main.TEMPORAL_CRASH_CONFIG.temporal_crash_threshold,
        "aftermath": main.AFTERMATH_CONFIG.minimum_score,
        "model1_imgsz": main.CRASH_CLASSIFIER_IMAGE_SIZE,
    }
    expected = {"trusted": 0.40, "candidate": 0.25, "temporal": 0.62, "aftermath": 0.80}
    if any(immutable[key] != value for key, value in expected.items()):
        raise RuntimeError(f"Protected threshold changed: {immutable}")
    positive_manifest = json.loads(POSITIVE_MANIFEST.read_text(encoding="utf-8"))
    negative_manifest = json.loads(NEGATIVE_MANIFEST.read_text(encoding="utf-8"))
    positive_frames = load_positive_frames(positive_manifest)
    PHASE3.mkdir(parents=True, exist_ok=True)
    existing = {}
    if RESULT_PATH.exists():
        existing_payload = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
        existing = {row["name"]: row for row in existing_payload.get("configurations", [])}
    for name in selected_names:
        print(f"BENCHMARK {name}: {CONFIGS[name].description}", flush=True)
        existing[name] = benchmark_config(
            CONFIGS[name], positive_manifest, positive_frames, negative_manifest
        )
        payload = {
            "schema_version": 1,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "corpus": {
                "positive_sequence": positive_manifest["sequence_id"],
                "positive_frames": [row["frame_index"] for row in positive_manifest["annotations"]],
                "negative_sequences": len(negative_manifest["sequences"]),
                "negative_frames": sum(len(row["frame_indices"]) for row in negative_manifest["sequences"]),
            },
            "immutable_settings": immutable,
            "configurations": [existing[key] for key in CONFIGS if key in existing],
        }
        RESULT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        summary = existing[name]
        print(
            f"DONE {name}: B={summary['positive']['participant_summaries']['B']['retention_percentage']}% "
            f"both={summary['positive']['both_participant_availability_percentage']}% "
            f"fps={summary['performance']['ai_fps']} "
            f"confirmedFP={summary['negative']['confirmed_crash_false_positives']} "
            f"reviewFP={summary['negative']['pending_review_false_positives']}",
            flush=True,
        )
    print(f"Saved {RESULT_PATH}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "configs", nargs="*", choices=tuple(CONFIGS), default=["A", "B", "C", "D"]
    )
    args = parser.parse_args()
    raise SystemExit(main_benchmark(args.configs))
