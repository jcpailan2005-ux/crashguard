"""Replay visually verified person-only media through Phase 3 configurations."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import main
from scripts.benchmark_phase3_resolution import CONFIGS, detector_frame, run_vehicle_model


MANIFEST_PATH = ROOT / "backend" / "validation" / "phase3" / "person_only_ground_truth.json"
RESULT_PATH = ROOT / "backend" / "validation" / "phase3" / "person_only_results.json"


def evaluate_sample(sample: dict, config_name: str) -> dict:
    config = CONFIGS[config_name]
    native = cv2.imread(sample["path"])
    if native is None:
        raise RuntimeError(f"Could not read {sample['path']}")
    primary = main.model.predict(native, verbose=False)
    person_count = main.count_labels_from_results(
        primary,
        getattr(main.model, "names", {}),
        main.PERSON_LABELS,
        min_confidence=main.LIVE_CAMERA_PERSON_CONFIDENCE_THRESHOLD,
    )
    classifier = main.classify_crash_frame(native)
    model1_score = float(classifier.get("accidentProbability") or 0.0)
    camera_key = f"phase3-person-only-{sample['sample_id']}-{config_name}"
    max_trusted = max_supported = 0
    try:
        # Repetition deliberately exercises persistence against a static artifact.
        for timestamp in (0.0, 0.5, 1.0):
            ai_frame = detector_frame(native, config)
            boxes, _ = run_vehicle_model(ai_frame, config.imgsz)
            tiers = main.VEHICLE_CANDIDATE_EVALUATOR.evaluate(
                camera_key,
                boxes,
                classifier_score=model1_score,
                frame_width=ai_frame.shape[1],
                frame_height=ai_frame.shape[0],
                timestamp=timestamp,
            )
            max_trusted = max(max_trusted, len(tiers.trusted))
            max_supported = max(max_supported, len(tiers.supported_candidates))
    finally:
        main.VEHICLE_CANDIDATE_EVALUATOR.reset_camera(camera_key)
    _, reason, decision = main.evaluate_crash_case_decision(
        crash_class="accident" if model1_score >= 0.5 else "non_accident",
        crash_confidence=model1_score,
        vehicle_count=max_trusted,
        supported_candidate_vehicle_count=max_supported,
        person_count=person_count,
        scene_valid=True,
        motion_valid=False,
        temporal_verified=False,
        consecutive_positive_frames=0,
        active_case_exists=False,
        cooldown_ready=True,
    )
    passed = bool(
        person_count >= sample["visual_ground_truth"]["person_count_minimum"]
        and max_trusted == 0
        and max_supported == 0
        and reason == "person_only_not_crash"
    )
    return {
        "sample_id": sample["sample_id"],
        "config": config_name,
        "person_count": person_count,
        "max_trusted_vehicle_count": max_trusted,
        "max_supported_candidate_vehicle_count": max_supported,
        "reason": reason,
        "decision": decision,
        "pass": passed,
    }


def main_validation() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    rows = [
        evaluate_sample(sample, config_name)
        for sample in manifest["samples"]
        for config_name in CONFIGS
    ]
    payload = {
        "schema_version": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "results": rows,
    }
    RESULT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if all(row["pass"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main_validation())
