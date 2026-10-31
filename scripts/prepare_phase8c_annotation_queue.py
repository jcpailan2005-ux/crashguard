"""Prepare Phase 8C human-annotation queues from the 21 Phase 8B promotions.

This script creates draft metadata only. It never creates ground-truth boxes,
marks human verification, promotes an event, or invokes the runtime pipeline.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path

import cv2


ROOT = Path(__file__).resolve().parents[1]
P8B = ROOT / "backend" / "validation" / "phase8b"
P8C = ROOT / "backend" / "validation" / "phase8c"
QUEUE = P8C / "manifests" / "annotation_queue.csv"

BATCHES = {
    1: ["CADP-0IPAgFHyRVI", "CADP-EqzYBBym7ro", "CADP-YSGhwU9XxuY", "CADP-LuP-qXCZ-eY", "CADP-niDlcEKeSWk"],
    2: ["CADP-3ItkjSXfP6k", "CADP-MxiC2UdOzE8", "CADP-Szh9Q0RxLKk", "CADP-YtKuNIcpvlY", "CADP-ZCQcKnFSJvg"],
    3: ["CADP-PomCzaH84GQ", "CADP-Vn8iNKHoUVE", "CADP-3p_-1RjvCmw", "CADP-Anm6ftbjNDM", "CADP-zVzXEht1aME"],
    4: ["CADP-DrTDtkeGv8Q", "CADP-i6LwdZ9ZsAE", "CADP-tFqV8ac9nLY", "CADP-uEbscoDZhDM", "CADP-WTy69_at39U"],
    5: ["CADP-QIeJH4MckAA"],
}

PAIR_GUESSES = {
    "CADP-YSGhwU9XxuY": "car-truck",
    "CADP-Anm6ftbjNDM": "car-truck",
    "CADP-DrTDtkeGv8Q": "car-motorcycle",
    "CADP-i6LwdZ9ZsAE": "car-motorcycle",
    "CADP-tFqV8ac9nLY": "car-motorcycle",
    "CADP-uEbscoDZhDM": "bus-motorcycle",
    "CADP-WTy69_at39U": "car-motorcycle",
    "CADP-QIeJH4MckAA": "car-motorcycle",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> int:
    for folder in ("annotations", "annotation_batches", "reports", "manifests", "baseline", "contact_sheets", "qa"):
        (P8C / folder).mkdir(parents=True, exist_ok=True)

    existing_queue = {}
    if QUEUE.exists():
        with QUEUE.open(encoding="utf-8", newline="") as source:
            existing_queue = {row["event_id"]: row for row in csv.DictReader(source)}
    with (P8B / "manifests" / "manual_screening.csv").open(encoding="utf-8", newline="") as source:
        promoted = {row["candidate_id"]: row for row in csv.DictReader(source) if row["screening_state"] == "PROMOTE_FOR_ANNOTATION"}
    with (P8B / "candidate_prescreen.csv").open(encoding="utf-8", newline="") as source:
        prescreen = {row["event_group_id"]: row for row in csv.DictReader(source)}
    ordered = [event for batch in BATCHES.values() for event in batch]
    if len(ordered) != 21 or len(set(ordered)) != 21 or set(ordered) != set(promoted):
        raise SystemExit("Phase 8C batch definitions do not exactly match the 21 Phase 8B promotions")

    queue_rows = []
    for batch_number, batch in BATCHES.items():
        for position, source_id in enumerate(batch, 1):
            source_row = prescreen[source_id]
            review = promoted[source_id]
            source_path = Path(source_row["source_path"])
            if not source_path.is_file():
                raise SystemExit(f"Missing source media: {source_path}")
            event_id = f"PHASE8C-{source_id}"
            prior = existing_queue.get(event_id, {})
            target_sheet = P8C / "contact_sheets" / f"{event_id}.jpg"
            shutil.copy2(Path(source_row["contact_sheet"]), target_sheet)
            pair = PAIR_GUESSES.get(source_id, "car-car")
            queue_rows.append({
                "event_id": event_id,
                "source_id": source_id,
                "source_path": str(source_path.resolve()),
                "screened_type": review["proposed_type"],
                "priority": f"BATCH_{batch_number}_ORDER_{position}",
                "vehicle_pair_guess": pair,
                "camera_type": "FIXED_ELEVATED_CCTV",
                "frame_count": source_row["frame_count"],
                "resolution": source_row["resolution"],
                "contact_sheet": str(target_sheet.resolve()),
                "annotation_status": prior.get("annotation_status", "NOT_STARTED"),
                "review_status": prior.get("review_status", "AWAITING_HUMAN_REVIEW"),
                "promotion_status": prior.get("promotion_status", "NOT_PROMOTED"),
                "rejection_reason": prior.get("rejection_reason", ""),
                "notes": review["reason"],
            })
            annotation_path = P8C / "annotations" / f"{event_id}.json"
            if not annotation_path.exists():
                capture = cv2.VideoCapture(str(source_path))
                fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
                frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
                height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
                capture.release()
                class_a, class_b = pair.split("-", 1)
                payload = {
                    "schema_version": 3,
                    "phase": "8C",
                    "event_id": event_id,
                    "source_id": source_id,
                    "source": str(source_path.resolve()),
                    "source_sha256": sha256(source_path),
                    "source_provenance": "RESEARCH_USE_CONFIRMED",
                    "screened_type": review["proposed_type"],
                    "event_type": review["proposed_type"],
                    "event_type_verified": False,
                    "event_type_justification": review["reason"],
                    "review_state": "AWAITING_HUMAN_REVIEW",
                    "promotion_status": "NOT_PROMOTED",
                    "reviewer": None,
                    "verified_at": None,
                    "ground_truth_collision_pair": ["P-A", "P-B"],
                    "ground_truth_pair_verified": False,
                    "participants": {
                        "P-A": {"vehicle_class": class_a, "visual_description": "", "first_visible_frame": None, "last_visible_frame": None},
                        "P-B": {"vehicle_class": class_b, "visual_description": "", "first_visible_frame": None, "last_visible_frame": None},
                    },
                    "fps": fps,
                    "frame_count": frame_count,
                    "resolution": [width, height],
                    "analysis_start_frame": None,
                    "analysis_end_frame": None,
                    "contact_start_frame": None,
                    "contact_peak_frame": None,
                    "contact_end_frame": None,
                    "contact_confidence": "UNCERTAIN",
                    "dynamic_history_available": review["proposed_type"] != "TYPE_C",
                    "aftermath_start_frame": None,
                    "distractors_reviewed": False,
                    "annotations": [],
                    "rejection": None,
                }
                annotation_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    fields = list(queue_rows[0])
    with QUEUE.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        writer.writerows(queue_rows)
    for batch_number in BATCHES:
        rows = [row for row in queue_rows if row["priority"].startswith(f"BATCH_{batch_number}_")]
        with (P8C / "annotation_batches" / f"batch_{batch_number:02d}.csv").open("w", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    models = {
        "backend/best.pt": sha256(ROOT / "backend" / "best.pt"),
        "backend/models/crash_classifier.pt": sha256(ROOT / "backend" / "models" / "crash_classifier.pt"),
    }
    manifest = {
        "schema_version": 1,
        "phase": "8C",
        "status": "PHASE 8C PARTIALLY COMPLETED — HUMAN ANNOTATION REQUIRED",
        "queue_count": len(queue_rows),
        "batch_sizes": {str(number): len(events) for number, events in BATCHES.items()},
        "human_verified": 0,
        "awaiting_human_review": 21,
        "promoted_validation_events": 0,
        "baseline_status": "BLOCKED_UNTIL_HUMAN_VERIFIED_PROMOTION",
        "production_runtime_files_modified": [],
        "models_retrained_or_replaced": False,
        "model_sha256": models,
        "frozen_configuration": {
            "trusted": 0.40,
            "candidate": 0.25,
            "temporal": 0.62,
            "aftermath": 0.80,
            "model2_imgsz": 640,
            "decoded_frame_path": "NATIVE",
        },
    }
    (P8C / "manifests" / "phase8c_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (P8C / "baseline" / "status.json").write_text(json.dumps({
        "status": "NOT_RUN",
        "reason": "No Phase 8C event is HUMAN_VERIFIED and PROMOTED_VALIDATION_EVENT.",
        "circular_ground_truth_prevented": True,
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"queue": len(queue_rows), "batches": {n: len(v) for n, v in BATCHES.items()}, "status": manifest["status"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
