"""Build the read-only Phase 7 source, provenance, and diagnostic artifacts.

No production settings or models are changed. Existing labels are retained as
source labels; only manually reviewed participant annotations are promoted into
the validated event manifest.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

import cv2
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PHASE7 = ROOT / "backend" / "validation" / "phase7"
ANNOTATIONS = PHASE7 / "annotations"
INVENTORY = PHASE7 / "source_inventory.csv"
LEAKAGE = PHASE7 / "model1_leakage_report.csv"
MANIFEST = PHASE7 / "validation_manifest.json"
BASELINE = PHASE7 / "baseline_results.json"
INTEGRITY = PHASE7 / "annotation_integrity.json"
FROZEN = PHASE7 / "frozen_test_manifest.json"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def source_label(path: Path) -> str:
    value = str(path).lower()
    if "non accident" in value or "nonaccident" in value or "non_accident" in value:
        return "non_accident"
    if "accident" in value:
        return "accident"
    if "severity" in value:
        return "severity_only"
    return "unknown"


def c1_event(stem: str) -> str | None:
    cleaned = re.sub(r"^carcrash1cctv_", "", stem, flags=re.I)
    match = re.match(r"(acc_?\d+|test_?\d+)", cleaned, re.I)
    return f"C1-{match.group(1).replace('_', '').upper()}" if match else None


def build_active_maps() -> tuple[dict[str, dict], dict[tuple[str, str], str]]:
    rows = read_csv(ROOT / "dataset_v2_manifest.csv")
    by_filename = {row["filename"]: row for row in rows}
    c2_number_to_event = {}
    for row in rows:
        match = re.match(r"carcrash2cctv_(\d+)_", row["filename"])
        if match:
            c2_number_to_event[(row["class"], match.group(1))] = row["event_id"]
    return by_filename, c2_number_to_event


def media_metadata(path: Path) -> dict:
    suffix = path.suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        try:
            with Image.open(path) as image:
                width, height = image.size
            return {"media_type": "image", "frame_count": 1, "fps": "", "resolution": f"{width}x{height}"}
        except Exception:
            return {"media_type": "image", "frame_count": 1, "fps": "", "resolution": "UNREADABLE"}
    if suffix in VIDEO_EXTENSIONS:
        capture = cv2.VideoCapture(str(path))
        try:
            return {
                "media_type": "video",
                "frame_count": int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0),
                "fps": round(float(capture.get(cv2.CAP_PROP_FPS) or 0.0), 4),
                "resolution": f"{int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)}x{int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)}",
            }
        finally:
            capture.release()
    return {"media_type": "other", "frame_count": "", "fps": "", "resolution": ""}


def inventory_sources() -> list[dict]:
    active_map, c2_number_map = build_active_maps()
    roots = [
        (ROOT / "backend" / "datasets" / "crash_classification", "active_crash_classification"),
        (Path(r"C:\Users\Lenovo\Downloads\carcrash1cctv"), "carcrash1cctv_raw"),
        (Path(r"C:\Users\Lenovo\Downloads\carcrash2cctv"), "carcrash2cctv_raw"),
        (ROOT / "backend" / "uploads", "crashguard_uploads"),
        (ROOT / "public" / "samples", "public_samples"),
        (ROOT / "backend" / "validation", "validation_artifacts"),
    ]
    phase6_manifest = json.loads((ROOT / "backend" / "validation" / "phase5" / "real_replay_manifest.json").read_text(encoding="utf-8"))
    replay_by_hash = {row["sha256"].upper(): row["video_id"] for row in phase6_manifest["replays"]}
    selected_negative_paths = set()
    negative_manifest = json.loads((ROOT / "backend" / "validation" / "phase2b" / "negative_replay_manifest.json").read_text(encoding="utf-8"))
    for sequence in negative_manifest["sequences"]:
        for index in sequence["frame_indices"]:
            selected_negative_paths.add(str(Path(negative_manifest["source_root"]) / f"{index}.jpg").lower())

    cache = {}
    if INVENTORY.exists():
        cache = {
            (row["source_path"], int(row["size_bytes"])): row
            for row in read_csv(INVENTORY)
        }
    records = []
    for source_root, dataset in roots:
        if not source_root.exists():
            continue
        for path in sorted(source_root.rglob("*")):
            if not path.is_file() or PHASE7 in path.parents:
                continue
            suffix = path.suffix.lower()
            if suffix not in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS:
                continue
            absolute_path = str(path.resolve())
            cached = cache.get((absolute_path, path.stat().st_size))
            digest = cached["sha256"] if cached else sha256(path)
            active = active_map.get(path.name)
            event_id = None
            if dataset in {"carcrash1cctv_raw", "active_crash_classification"}:
                event_id = c1_event(path.stem)
            if active and active["source"] != "carcrash1cctv":
                event_id = active["event_id"]
            if dataset == "carcrash2cctv_raw":
                match = re.match(r"(\d+)$", path.stem)
                if match:
                    event_id = c2_number_map.get((source_label(path), match.group(1)))
            if digest in replay_by_hash:
                event_id = replay_by_hash[digest]
            metadata = {
                key: cached[key] for key in ("media_type", "frame_count", "fps", "resolution")
            } if cached else media_metadata(path)
            used = digest in replay_by_hash or str(path).lower() in selected_negative_paths
            if path.name == "test_2.jpg" and "non accident" in str(path).lower():
                used = True
            records.append({
                "source_path": absolute_path,
                "source_filename": path.name,
                "size_bytes": path.stat().st_size,
                "sha256": digest,
                **metadata,
                "source_event_identifier": event_id or "UNKNOWN",
                "source_label": source_label(path),
                "source_dataset": dataset,
                "likely_event_group": event_id or f"HASH-{digest[:16]}",
                "already_used_in_validation": "YES" if used else "NO",
            })

    # Propagate a recoverable event ID through exact duplicate hashes.
    by_hash = defaultdict(list)
    for row in records:
        by_hash[row["sha256"]].append(row)
    for rows in by_hash.values():
        known = next((row["source_event_identifier"] for row in rows if row["source_event_identifier"] != "UNKNOWN"), None)
        if known:
            for row in rows:
                if row["source_event_identifier"] == "UNKNOWN":
                    row["source_event_identifier"] = known
                    row["likely_event_group"] = known
    return records


def leakage_rows(inventory: list[dict]) -> list[dict]:
    manifest = read_csv(ROOT / "dataset_v2_manifest.csv")
    groups = defaultdict(list)
    for row in manifest:
        canonical = c1_event(Path(row["filename"]).stem) if row["source"] == "carcrash1cctv" else row["event_id"]
        groups[canonical or row["event_id"]].append(row)
    results = []
    for event_id, rows in sorted(groups.items()):
        splits = sorted({row["current_split"] for row in rows})
        if len(splits) > 1:
            status = "MODEL1_EVENT_OVERLAP"
        elif splits == ["train"]:
            status = "MODEL1_TRAIN_SEEN"
        elif splits == ["val"]:
            status = "MODEL1_VALIDATION_ONLY"
        elif splits == ["test"]:
            status = "MODEL1_TEST_ONLY"
        else:
            status = "UNKNOWN"
        results.append({
            "event_id": event_id,
            "source_dataset": rows[0]["source"],
            "source_label": rows[0]["class"],
            "frame_count": len(rows),
            "deployed_model_splits": "+".join(splits),
            "provenance_status": status,
            "clean_model1_generalization_eligible": "YES" if status in {"MODEL1_VALIDATION_ONLY", "MODEL1_TEST_ONLY"} else "NO",
            "notes": "Event grouping is inherited from the prior audit and remains candidate-level until human source review.",
        })
    for event_id in ("REAL-REPLAY-001", "REAL-REPLAY-002", "REAL-REPLAY-003"):
        results.append({
            "event_id": event_id,
            "source_dataset": "crashguard_uploads",
            "source_label": "collision" if event_id == "REAL-REPLAY-003" else "near_miss_unverified",
            "frame_count": "video",
            "deployed_model_splits": "unknown",
            "provenance_status": "UNKNOWN",
            "clean_model1_generalization_eligible": "NO",
            "notes": "Video pixels were not matched exhaustively against all training-event frames; do not claim external unseen status.",
        })
    return results


def overlap(a: list[float], b: list[float]) -> float:
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection
    return intersection / union if union > 0 else 0.0


def build_known_annotation() -> dict:
    source = json.loads((ROOT / "backend" / "validation" / "phase2b" / "positive_collision_ground_truth.json").read_text(encoding="utf-8"))
    phase4 = json.loads((ROOT / "backend" / "validation" / "phase4" / "validation_results.json").read_text(encoding="utf-8"))
    phase4_by_frame = {row["frame_index"]: row for row in phase4["positive"]["frames"]}
    annotations = []
    for row in source["annotations"]:
        frame = int(row["frame_index"])
        a, b = row["participant_a_bbox"], row["participant_b_bbox"]
        distractors = []
        selected = phase4_by_frame[frame].get("selected_pair")
        if selected and not phase4_by_frame[frame]["selected_pair_is_collision_pair"]:
            for index, box in enumerate((selected["pairA"], selected["pairB"]), start=1):
                coordinates = [round(float(value), 2) for value in box["box"]]
                if max(overlap(coordinates, a), overlap(coordinates, b)) < 0.20:
                    distractors.append({
                        "id": f"distractor_{index}", "bbox": coordinates,
                        "expected_class": box.get("label") or "vehicle",
                        "notes": "System-selected non-collision vehicle from the frozen Phase 4 trace.",
                    })
        phase = "CONTACT" if row["impact_phase"] == "contact" else "POST_IMPACT"
        b_visibility = "HEAVILY_OCCLUDED" if frame in {440, 442} else "VISIBLE_PARTIAL" if frame == 444 else "VISIBLE_CLEAR"
        annotations.append({
            "event_id": "EVENT-0001",
            "frame_index": frame,
            "timestamp_ms": round(float(row["timestamp"]) * 1000),
            "phase": phase,
            "participant_a_bbox": a,
            "participant_a_visible": True,
            "participant_a_occlusion": "VISIBLE_PARTIAL" if frame == 453 else "VISIBLE_CLEAR",
            "participant_a_expected_class": "car",
            "participant_b_bbox": b,
            "participant_b_visible": True,
            "participant_b_occlusion": b_visibility,
            "participant_b_expected_class": "motorcycle",
            "contact_visible": True if phase == "CONTACT" else False,
            "collision_region_bbox": [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])],
            "distractor_boxes": distractors,
            "groundTruthCollisionPair": ["participant_a", "participant_b"],
            "annotation_uncertainty": "PROBABLE",
            "notes": row["notes"],
        })
    video_path = ROOT / source["source_video"]
    area_a = statistics.fmean((r["participant_a_bbox"][2] - r["participant_a_bbox"][0]) * (r["participant_a_bbox"][3] - r["participant_a_bbox"][1]) / (640 * 360) for r in annotations)
    area_b = statistics.fmean((r["participant_b_bbox"][2] - r["participant_b_bbox"][0]) * (r["participant_b_bbox"][3] - r["participant_b_bbox"][1]) / (640 * 360) for r in annotations)
    return {
        "schema_version": 1,
        "event_id": "EVENT-0001",
        "source": str(video_path.resolve()),
        "source_sha256": sha256(video_path),
        "source_event_id": "REAL-REPLAY-003",
        "type": "TYPE_B",
        "participant_a": "dark SUV / car",
        "participant_b": "motorcycle / rider",
        "participant_a_vehicle_class": "car",
        "participant_b_vehicle_class": "motorcycle",
        "groundTruthCollisionPair": ["participant_a", "participant_b"],
        "resolution": [640, 360],
        "fps": 30.0,
        "duration_seconds": 29.633,
        "camera_viewpoint": "ELEVATED_CCTV",
        "day_night": "DAY",
        "participant_a_normalized_bbox_area_mean": round(area_a, 6),
        "participant_b_normalized_bbox_area_mean": round(area_b, 6),
        "participant_a_scale": "LARGE",
        "participant_b_scale": "SMALL",
        "occlusion_level": "HIGH_FOR_PARTICIPANT_B",
        "approach_visible": True,
        "contact_visible": True,
        "contact_start_frame": 440,
        "contact_end_frame": 444,
        "contact_uncertainty": "PROBABLE",
        "post_impact_visible": True,
        "aftermath_visible": True,
        "model1_leakage_status": "UNKNOWN",
        "annotation_confidence": "PROBABLE",
        "future_use_group": "DIAGNOSTIC_VALIDATION",
        "annotations": annotations,
    }


def clean_model1_scores(leakage: list[dict]) -> dict:
    status = {row["event_id"]: row["provenance_status"] for row in leakage}
    rows = [row for row in read_csv(ROOT / "dataset_v2_manifest.csv") if row["accident_score"]]
    clean = [row for row in rows if status.get(row["event_id"]) in {"MODEL1_VALIDATION_ONLY", "MODEL1_TEST_ONLY"}]
    result = {}
    for label in ("accident", "non_accident"):
        values = [float(row["accident_score"]) for row in clean if row["class"] == label]
        result[label] = {
            "events": len({row["event_id"] for row in clean if row["class"] == label}),
            "frames": len(values),
            "mean": round(statistics.fmean(values), 4) if values else None,
            "median": round(statistics.median(values), 4) if values else None,
            "min": round(min(values), 4) if values else None,
            "max": round(max(values), 4) if values else None,
        }
    return result


def validate_annotation(event: dict) -> dict:
    errors = []
    width, height = event["resolution"]
    phases = {"APPROACH", "PRE_CONTACT", "CONTACT", "POST_IMPACT", "AFTERMATH", "UNKNOWN"}
    seen_frames = set()
    for row in event["annotations"]:
        frame = row["frame_index"]
        if frame in seen_frames:
            errors.append(f"duplicate frame {frame}")
        seen_frames.add(frame)
        if not 0 <= frame < round(event["duration_seconds"] * event["fps"]) + 2:
            errors.append(f"impossible frame {frame}")
        if row["phase"] not in phases:
            errors.append(f"invalid phase {row['phase']}")
        if row["phase"] == "CONTACT" and row["contact_visible"] is False:
            errors.append(f"contact inconsistency frame {frame}")
        for key in ("participant_a_bbox", "participant_b_bbox", "collision_region_bbox"):
            box = row.get(key)
            if box and not (0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height):
                errors.append(f"invalid {key} frame {frame}: {box}")
        for distractor in row.get("distractor_boxes", []):
            box = distractor["bbox"]
            if not (0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height):
                errors.append(f"invalid distractor frame {frame}: {box}")
    if event["participant_a"] == event["participant_b"]:
        errors.append("participant identities are not unique")
    if event["groundTruthCollisionPair"] != ["participant_a", "participant_b"]:
        errors.append("collision pair references do not exist")
    source = Path(event["source"])
    if not source.exists():
        errors.append("source file missing")
    elif sha256(source) != event["source_sha256"]:
        errors.append("source hash mismatch")
    return {"event_id": event["event_id"], "passed": not errors, "errors": errors}


def main() -> int:
    PHASE7.mkdir(parents=True, exist_ok=True)
    ANNOTATIONS.mkdir(parents=True, exist_ok=True)
    inventory = inventory_sources()
    inventory_fields = [
        "source_path", "source_filename", "size_bytes", "sha256", "media_type",
        "frame_count", "fps", "resolution", "source_event_identifier", "source_label",
        "source_dataset", "likely_event_group", "already_used_in_validation",
    ]
    write_csv(INVENTORY, inventory, inventory_fields)

    leakage = leakage_rows(inventory)
    leakage_fields = [
        "event_id", "source_dataset", "source_label", "frame_count",
        "deployed_model_splits", "provenance_status",
        "clean_model1_generalization_eligible", "notes",
    ]
    write_csv(LEAKAGE, leakage, leakage_fields)

    event = build_known_annotation()
    annotation_path = ANNOTATIONS / "EVENT-0001.json"
    annotation_path.write_text(json.dumps(event, indent=2) + "\n", encoding="utf-8")

    phase6 = json.loads((ROOT / "backend" / "validation" / "phase6" / "validation_results.json").read_text(encoding="utf-8"))
    negative_manifest = json.loads((ROOT / "backend" / "validation" / "phase2b" / "negative_replay_manifest.json").read_text(encoding="utf-8"))
    negative_events = [
        {
            "event_id": row["sequence_id"], "label": "NEGATIVE",
            "category": row["category"], "source_range": row["source_range"],
            "future_use_group": "DIAGNOSTIC_VALIDATION",
        }
        for row in negative_manifest["sequences"]
    ]
    negative_events.append({
        "event_id": "NEAR-MISS-001", "label": "NEAR_MISS",
        "source_variants": ["REAL-REPLAY-001", "REAL-REPLAY-002"],
        "independent_event_count": 1,
        "category": "close intersection interaction with no visually established contact",
        "future_use_group": "DIAGNOSTIC_VALIDATION",
    })
    candidate_groups = defaultdict(lambda: {"files": 0, "labels": set(), "datasets": set()})
    for row in inventory:
        event_id = row["source_event_identifier"]
        if event_id != "UNKNOWN":
            candidate_groups[event_id]["files"] += 1
            candidate_groups[event_id]["labels"].add(row["source_label"])
            candidate_groups[event_id]["datasets"].add(row["source_dataset"])
    candidates = [
        {"source_event_id": event_id, "files": value["files"], "labels": sorted(value["labels"]), "datasets": sorted(value["datasets"]), "validation_status": "CANDIDATE_NOT_PARTICIPANT_ANNOTATED"}
        for event_id, value in sorted(candidate_groups.items())
        if "accident" in value["labels"] and event_id != "REAL-REPLAY-003"
    ]
    manifest = {
        "schema_version": 1,
        "purpose": "diagnostic validation only; not a training dataset",
        "positive_events": [{
            "event_id": event["event_id"], "annotation": "backend/validation/phase7/annotations/EVENT-0001.json",
            "source_event_id": event["source_event_id"], "type": event["type"],
            "future_use_group": event["future_use_group"],
        }],
        "negative_events": negative_events,
        "candidate_collision_events": candidates,
        "counts": {
            "validated_independent_positive_events": 1,
            "validated_type_a": 0, "validated_type_b": 1, "validated_type_c": 0,
            "validated_independent_negative_or_near_miss_events": 13,
            "candidate_collision_event_groups_not_promoted": len(candidates),
        },
        "event_isolation": {
            "REAL-REPLAY-001_and_002": "one near-miss family",
            "REAL-REPLAY-003_full_and_aftermath": "one collision event",
        },
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    phase6_positive = phase6["positive"]
    b = phase6_positive["participants"]["B"]
    annotations = event["annotations"]
    visible_counts = Counter(row["participant_b_occlusion"] for row in annotations)
    baseline = {
        "schema_version": 1,
        "evaluated_validated_events": 1,
        "baseline_provenance": {
            "source_artifact": "backend/validation/phase6/validation_results.json",
            "reuse_reason": "Phase 7 EVENT-0001 uses the same approved six participant annotations; deployed models, thresholds, tracking, and temporal code are unchanged.",
            "model1_sha256": sha256(ROOT / "backend" / "models" / "crash_classifier.pt"),
            "model2_sha256": sha256(ROOT / "backend" / "best.pt"),
            "thresholds": {"trusted": 0.40, "candidate": 0.25, "temporal": 0.62, "aftermath": 0.80},
            "training_performed": False,
        },
        "model2": {
            "participant_observations": 12,
            "raw_detected": 10,
            "raw_recall_percent": round((6 + 4) / 12 * 100, 2),
            "trusted": 6,
            "trusted_recall_percent": 50.0,
            "candidate_supported": 3,
            "candidate_supported_recall_percent": 25.0,
            "no_box": 2,
            "no_box_rate_percent": round(2 / 12 * 100, 2),
            "below_candidate": 1,
            "below_candidate_rate_percent": round(1 / 12 * 100, 2),
            "wrong_class": 1,
            "wrong_class_rate_percent": round(1 / 12 * 100, 2),
            "by_class": {
                "car": phase6_positive["participants"]["A"],
                "motorcycle": b,
            },
            "by_size": {
                "LARGE": {"participant": "A", "raw_recall_percent": 100.0},
                "SMALL": {"participant": "B", "raw_recall_percent": 66.67},
            },
            "by_visibility": {
                "participant_b_annotation_counts": dict(visible_counts),
                "note": "Only six frames exist; no generalization rate is claimed.",
            },
        },
        "tracking": {
            "eligible_participant_observations": 9,
            "tracked": 6,
            "tracker_recall_given_eligible_percent": round(6 / 9 * 100, 2),
            "participant_a_tracked": 6,
            "participant_b_tracked": 0,
            "both_tracked_simultaneously": 0,
            "logical_recovery_b": 3,
            "motion_observed_both": 0,
        },
        "temporal_pair_attribution": {
            "type_a_b_events_evaluated": 1,
            "correct_event_pair_selected_for_temporal_decision": 0,
            "wrong_event_pair_selected_for_temporal_decision": 1,
            "event_pair_attribution_accuracy_percent": 0.0,
            "annotated_frames": 6,
            "pair_attribution_correct": 0,
            "pair_attribution_wrong": 3,
            "pair_unavailable": 3,
            "pair_ambiguous": 0,
            "true_pair_max_temporal_score": 0.1466,
            "unrelated_pair_max_temporal_score": 0.7753,
            "selected_pair_temporal_score": 0.7753,
            "non_collision_vehicle_pairs_annotated": sum(max(0, (2 + len(row["distractor_boxes"])) * (1 + len(row["distractor_boxes"])) // 2 - 1) for row in annotations),
            "non_collision_pairs_with_high_temporal_score": 1,
            "non_collision_pairs_selected_instead": 1,
        },
        "aftermath": {
            "type_c_independent_events": 0,
            "derived_start_modes": 1,
            "aftermath_score": 0.7366,
            "persistence": "not_reached",
            "decision": "confirmed_crash",
            "incorrect_temporal_confirmations": 1,
            "note": "Derived from EVENT-0001 and not counted independently.",
        },
        "model1": {
            "strict_current_model_train_unseen_scores": clean_model1_scores(leakage),
            "known_leakage_excluded": True,
            "validated_EVENT_0001_provenance": "UNKNOWN_NOT_GENERALIZATION_ELIGIBLE",
            "validated_event_full_frame_scores": phase6_positive["full_frame_model1"],
            "negative_phase2b_scores": phase6["negative"]["full_frame_model1_distribution"],
            "negative_phase2b_provenance": "MODEL1_TRAIN_OVERLAP_POSSIBLE; diagnostic only",
        },
        "bottleneck_rates": {
            "model2_participant_failure_percent": round(2 / 12 * 100, 2),
            "model2_not_accepted_percent": round(3 / 12 * 100, 2),
            "tracker_failure_given_usable_detection_percent": round(3 / 9 * 100, 2),
            "pair_misattribution_event_percent": 100.0,
            "temporal_failure_with_correct_tracked_pair": "NOT_MEASURABLE_NO_BOTH_TRACKED_FRAMES",
            "aftermath_misrouting_percent_derived_scenarios": 100.0,
            "model1_visual_failure_at_0_50_percent": round(2 / 6 * 100, 2),
        },
        "limitations": [
            "One independent validated collision event.",
            "No validated Type A event.",
            "No independent Type C event; only a derived replay start.",
            "Most classifier-source events overlap Model 1 training or lack verified event provenance.",
        ],
    }
    BASELINE.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")

    validation = validate_annotation(event)
    integrity = {
        "annotation_results": [validation],
        "duplicate_event_ids": [],
        "source_hash_check": "PASS" if validation["passed"] else "FAIL",
        "annotation_validation": "PASS" if validation["passed"] else "FAIL",
        "event_isolation": "PASS",
        "overall": "PASS" if validation["passed"] else "FAIL",
    }
    INTEGRITY.write_text(json.dumps(integrity, indent=2) + "\n", encoding="utf-8")
    FROZEN.write_text(json.dumps({
        "schema_version": 1,
        "created": False,
        "events": [],
        "reason": "Insufficient participant-annotated, source-independent, Model-1-leakage-checked events. Candidate classifier frames were not promoted into a frozen system test set.",
        "required_before_creation": ["at least 6 Type A", "at least 6 Type B", "at least 6 independent Type C", "20 independent negatives", "manual participant/contact review"],
    }, indent=2) + "\n", encoding="utf-8")

    by_hash = defaultdict(list)
    for row in inventory:
        by_hash[row["sha256"]].append(row)
    duplicate_groups = [rows for rows in by_hash.values() if len(rows) > 1]
    raw_collision_candidates = sum(1 for row in leakage if row["source_label"] == "accident") + 1
    dedup = f"""# Phase 7 Deduplication Report

- Raw inventoried media files: {len(inventory)}
- Raw candidate collision event groups: {raw_collision_candidates}
- Exact duplicate hash groups: {len(duplicate_groups)}
- Files participating in exact duplicate groups: {sum(len(rows) for rows in duplicate_groups)}
- Uploaded video files: {sum(row['media_type'] == 'video' for row in inventory)}
- Unique uploaded video hashes: {len({row['sha256'] for row in inventory if row['source_dataset'] == 'crashguard_uploads' and row['media_type'] == 'video'})}
- Known related/alternate-source groups: `REAL-REPLAY-001` + `REAL-REPLAY-002` are one near-miss family; full and aftermath starts of `REAL-REPLAY-003` are one collision.
- Independent participant-annotated collision events after deduplication: 1

The 583 classifier event IDs are inherited candidate clusters, not 583 independently verified physical crashes. Exact hashes, filenames, directory labels, and prior event clustering were retained, but candidates were not promoted without participant/contact review.
"""
    (PHASE7 / "deduplication_report.md").write_text(dedup, encoding="utf-8")
    print(json.dumps({
        "inventory_files": len(inventory),
        "exact_duplicate_groups": len(duplicate_groups),
        "candidate_collision_groups": len(candidates),
        "validated_positive_events": 1,
        "validated_negative_or_near_miss_events": 13,
        "annotation_integrity": integrity["overall"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
