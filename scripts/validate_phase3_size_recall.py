"""Measure raw Model 2 recall by manually annotated vehicle size band."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.benchmark_phase3_resolution import (
    CONFIGS,
    IOU_THRESHOLD,
    box_xyxy,
    detector_frame,
    iou,
    run_vehicle_model,
)


MANIFEST_PATH = ROOT / "backend" / "validation" / "phase3" / "small_vehicle_ground_truth.json"
RESULT_PATH = ROOT / "backend" / "validation" / "phase3" / "small_vehicle_results.json"


def size_band(box, frame_width: int, frame_height: int) -> str:
    area = max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])
    ratio = area / max(1.0, frame_width * frame_height)
    if ratio < 0.005:
        return "very_small_distant"
    if ratio < 0.015:
        return "small"
    if ratio < 0.06:
        return "medium"
    return "large"


def scale_box(box, source_size, target_size):
    sx, sy = target_size[0] / source_size[0], target_size[1] / source_size[1]
    return [box[0] * sx, box[1] * sy, box[2] * sx, box[3] * sy]


def assign_frame(annotations, predictions, source_size, target_size):
    pairs = []
    for annotation_index, annotation in enumerate(annotations):
        target_box = scale_box(annotation["bbox"], source_size, target_size)
        for prediction_index, prediction in enumerate(predictions):
            score = iou(target_box, box_xyxy(prediction))
            if score >= IOU_THRESHOLD:
                pairs.append((score, annotation_index, prediction_index))
    pairs.sort(reverse=True)
    matches = {}
    used_annotations = set()
    used_predictions = set()
    for score, annotation_index, prediction_index in pairs:
        if annotation_index in used_annotations or prediction_index in used_predictions:
            continue
        matches[annotation_index] = (predictions[prediction_index], score)
        used_annotations.add(annotation_index)
        used_predictions.add(prediction_index)
    return matches


def evaluate_config(config_name: str, manifest: dict) -> dict:
    config = CONFIGS[config_name]
    source_root = Path(manifest["source_root"])
    source_size = tuple(manifest["native_frame_size"])
    by_frame = defaultdict(list)
    for annotation in manifest["annotations"]:
        by_frame[int(annotation["frame_index"])].append(annotation)
    counts = defaultdict(Counter)
    trace = []
    latencies = []
    for frame_index, annotations in by_frame.items():
        native = cv2.imread(str(source_root / f"{frame_index}.jpg"))
        if native is None:
            raise RuntimeError(f"Could not read frame {frame_index}.")
        ai_frame = detector_frame(native, config)
        predictions, latency = run_vehicle_model(ai_frame, config.imgsz)
        latencies.append(latency)
        target_size = (ai_frame.shape[1], ai_frame.shape[0])
        matches = assign_frame(annotations, predictions, source_size, target_size)
        for index, annotation in enumerate(annotations):
            band = size_band(annotation["bbox"], source_size[0], source_size[1])
            match = matches.get(index)
            counts[band]["ground_truth"] += 1
            if match:
                prediction, score = match
                counts[band]["detected"] += 1
                trace.append(
                    {
                        "frame_index": frame_index,
                        "size_band": band,
                        "expected_class": annotation["class"],
                        "detected_class": prediction.get("label"),
                        "confidence": round(float(prediction.get("confidence") or 0.0), 4),
                        "iou": round(score, 4),
                    }
                )
            else:
                trace.append(
                    {
                        "frame_index": frame_index,
                        "size_band": band,
                        "expected_class": annotation["class"],
                        "detected_class": None,
                        "confidence": None,
                        "iou": 0.0,
                    }
                )
    bands = {}
    for band in ("very_small_distant", "small", "medium", "large"):
        ground_truth = counts[band]["ground_truth"]
        detected = counts[band]["detected"]
        bands[band] = {
            "ground_truth": ground_truth,
            "detected": detected,
            "recall_percentage": round(100.0 * detected / max(1, ground_truth), 2),
        }
    total_gt = sum(row["ground_truth"] for row in bands.values())
    total_detected = sum(row["detected"] for row in bands.values())
    return {
        "config": config_name,
        "detection_frame": list(config.frame_size) if config.frame_size else "native",
        "yolo_imgsz": config.imgsz,
        "bands": bands,
        "overall": {
            "ground_truth": total_gt,
            "detected": total_detected,
            "recall_percentage": round(100.0 * total_detected / max(1, total_gt), 2),
        },
        "mean_model2_ms": round(sum(latencies) / max(1, len(latencies)), 3),
        "trace": trace,
    }


def main(selected_names: list[str]) -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    results = []
    for name in selected_names:
        print(f"SIZE RECALL {name}", flush=True)
        results.append(evaluate_config(name, manifest))
    payload = {
        "schema_version": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "manifest": str(MANIFEST_PATH.relative_to(ROOT)),
        "iou_threshold": IOU_THRESHOLD,
        "configurations": results,
    }
    RESULT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({row["config"]: row["bands"] for row in results}, indent=2))
    print(f"Saved {RESULT_PATH}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("configs", nargs="*", choices=tuple(CONFIGS), default=list(CONFIGS))
    args = parser.parse_args()
    raise SystemExit(main(args.configs))
