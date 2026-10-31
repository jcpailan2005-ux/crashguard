"""Validate Phase 2 vehicle retention against manual positive and real negatives."""

from __future__ import annotations

import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

import cv2
import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import main
from backend.services.crash_event_state import CrashEventManager


VALIDATION_DIR = ROOT / "backend" / "validation" / "phase2b"
POSITIVE_MANIFEST = VALIDATION_DIR / "positive_collision_ground_truth.json"
NEGATIVE_MANIFEST = VALIDATION_DIR / "negative_replay_manifest.json"
RESULT_PATH = VALIDATION_DIR / "validation_results.json"
IOU_THRESHOLD = 0.20


def iou(a, b) -> float:
    ax1, ay1, ax2, ay2 = (float(value) for value in a)
    bx1, by1, bx2, by2 = (float(value) for value in b)
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if intersection <= 0:
        return 0.0
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - intersection
    return intersection / union if union > 0 else 0.0


def box_xyxy(box: dict) -> list[float]:
    if box.get("box") is not None:
        return [float(value) for value in box["box"][:4]]
    x1, y1 = float(box.get("x") or 0), float(box.get("y") or 0)
    return [
        x1,
        y1,
        x1 + float(box.get("width") or 0),
        y1 + float(box.get("height") or 0),
    ]


def assign_two(gt_boxes: dict[str, list[float]], predictions: list[dict]) -> dict[str, tuple[dict, float] | None]:
    pairs = []
    for participant, gt_box in gt_boxes.items():
        for index, prediction in enumerate(predictions):
            score = iou(gt_box, box_xyxy(prediction))
            if score >= IOU_THRESHOLD:
                pairs.append((score, participant, index))
    pairs.sort(reverse=True)
    assigned_participants = set()
    assigned_predictions = set()
    assignments: dict[str, tuple[dict, float] | None] = {key: None for key in gt_boxes}
    for score, participant, index in pairs:
        if participant in assigned_participants or index in assigned_predictions:
            continue
        assignments[participant] = (predictions[index], score)
        assigned_participants.add(participant)
        assigned_predictions.add(index)
    return assignments


def compatible_label(expected: str, actual: str) -> bool:
    expected = main.normalize_box_label(expected)
    actual = main.normalize_box_label(actual)
    return expected == actual


def classify_match(expected_class: str, match) -> tuple[str, bool]:
    if match is None:
        return "MODEL2_NO_BOX", False
    prediction, _ = match
    if not compatible_label(expected_class, str(prediction.get("label") or "")):
        return "WRONG_CLASS", False
    state = prediction.get("detectionState")
    if state == "TRUSTED":
        return "trusted", True
    if state == "CANDIDATE" and prediction.get("candidateSupported"):
        return "supported_candidate", True
    if state == "CANDIDATE":
        return "CANDIDATE_NOT_SUPPORTED", False
    return "BELOW_CANDIDATE_THRESHOLD", False


def track_match(gt_box, tracks, used_ids: set[int]) -> int | None:
    choices = sorted(
        (
            (iou(gt_box, track.bbox), track.track_id)
            for track in tracks
            if track.track_id not in used_ids
        ),
        reverse=True,
    )
    if not choices or choices[0][0] < IOU_THRESHOLD:
        return None
    used_ids.add(choices[0][1])
    return choices[0][1]


def validate_positive(manifest: dict) -> dict:
    video_path = ROOT / manifest["source_video"]
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open positive video: {video_path}")
    camera_key = "phase2b-positive"
    participant_classes = {
        key: value["class"] for key, value in manifest["participants"].items()
    }
    observations = {"A": [], "B": []}
    both_available = 0
    failure_counts = Counter()
    tracker_dropped = 0
    try:
        for annotation in manifest["annotations"]:
            frame_index = int(annotation["frame_index"])
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError(f"Could not read positive frame {frame_index}")
            raw_boxes = main.detect_vehicle_boxes(frame)
            classifier = main.classify_crash_frame(frame)
            model1_score = float(classifier.get("accidentProbability") or 0.0)
            tiers = main.VEHICLE_CANDIDATE_EVALUATOR.evaluate(
                camera_key,
                raw_boxes,
                classifier_score=model1_score,
                frame_width=frame.shape[1],
                frame_height=frame.shape[0],
                timestamp=float(annotation["timestamp"]),
            )
            tracking, temporal = main.analyze_vehicle_tracks(
                camera_key,
                list(tiers.tracker_input),
                frame,
                classifier_score=model1_score,
                timestamp=float(annotation["timestamp"]),
            )
            temporal = main.enforce_candidate_confirmation_safety(temporal, tiers)
            gt_boxes = {
                "A": annotation["participant_a_bbox"],
                "B": annotation["participant_b_bbox"],
            }
            assignments = assign_two(gt_boxes, list(tiers.raw))
            frame_retained = {}
            used_track_ids: set[int] = set()
            for participant in ("A", "B"):
                match = assignments[participant]
                status, retained = classify_match(participant_classes[participant], match)
                prediction, match_iou = match if match is not None else (None, 0.0)
                tracker_id = track_match(
                    gt_boxes[participant], tracking.active_tracks, used_track_ids
                ) if retained else None
                tracker_failure = retained and tracker_id is None
                if status.isupper():
                    failure_counts[status] += 1
                if tracker_failure:
                    failure_counts["TRACKER_DROPPED"] += 1
                    tracker_dropped += 1
                observations[participant].append(
                    {
                        "frame_index": frame_index,
                        "timestamp": annotation["timestamp"],
                        "impact_phase": annotation["impact_phase"],
                        "ground_truth_bbox": gt_boxes[participant],
                        "raw_detection_confidence": (
                            round(float(prediction.get("confidence") or 0.0), 4)
                            if prediction is not None
                            else None
                        ),
                        "raw_detection_class": prediction.get("label") if prediction else None,
                        "iou": round(match_iou, 4),
                        "tier": status,
                        "retained": retained,
                        "tracker_id": tracker_id,
                        "logical_identity": participant,
                        "tracker_dropped": tracker_failure,
                        "model1_score": round(model1_score, 4),
                        "temporal_score": round(temporal.score, 4),
                    }
                )
                frame_retained[participant] = retained
            if frame_retained.get("A") and frame_retained.get("B"):
                both_available += 1
    finally:
        cap.release()
        main.VEHICLE_CANDIDATE_EVALUATOR.reset_camera(camera_key)
        main.VEHICLE_TRACKING_SERVICE.reset_camera(camera_key)
        main.TEMPORAL_CRASH_VERIFIER.reset_camera(camera_key)
        main.CRASH_AFTERMATH_DETECTOR.reset_camera(camera_key)

    summaries = {}
    for participant, rows in observations.items():
        counts = Counter(row["tier"] for row in rows)
        retained = sum(1 for row in rows if row["retained"])
        summaries[participant] = {
            "ground_truth_observations": len(rows),
            "raw_detected": sum(1 for row in rows if row["raw_detection_confidence"] is not None),
            "trusted": counts["trusted"],
            "supported_candidate": counts["supported_candidate"],
            "below_candidate_threshold": counts["BELOW_CANDIDATE_THRESHOLD"],
            "candidate_not_supported": counts["CANDIDATE_NOT_SUPPORTED"],
            "model2_no_box": counts["MODEL2_NO_BOX"],
            "wrong_class": counts["WRONG_CLASS"],
            "tracker_dropped": sum(1 for row in rows if row["tracker_dropped"]),
            "retained": retained,
            "retention_percentage": round(100.0 * retained / max(1, len(rows)), 2),
        }
    return {
        "sequence_id": manifest["sequence_id"],
        "annotated_frames": len(manifest["annotations"]),
        "participant_summaries": summaries,
        "both_participant_observations": both_available,
        "both_participant_availability_percentage": round(
            100.0 * both_available / max(1, len(manifest["annotations"])), 2
        ),
        "failure_breakdown": dict(failure_counts),
        "trace": observations,
    }


def validate_negatives(manifest: dict) -> dict:
    source_root = Path(manifest["source_root"])
    source_fps = float(manifest["assumed_source_fps"])
    process = psutil.Process()
    process.cpu_percent(None)
    rss_before = process.memory_info().rss / (1024 * 1024)
    sequence_results = []
    candidate_costs = []
    total_cycle_costs = []
    real_person_only_frames = []
    for sequence in manifest["sequences"]:
        camera_key = f"phase2b-{sequence['sequence_id']}"
        event_manager = CrashEventManager(
            required_positive_observations=main.LIVE_CAMERA_REQUIRED_HITS,
            temporal_window_seconds=main.CRASH_TEMPORAL_WINDOW_SECONDS,
            clear_consecutive_negatives=main.EVENT_CLEAR_CONSECUTIVE_NEGATIVES,
            clear_seconds=main.EVENT_CLEAR_SECONDS,
            cooldown_seconds=main.EVENT_COOLDOWN_SECONDS,
        )
        totals = Counter()
        max_model1 = max_temporal = max_aftermath = 0.0
        had_supported_candidate = had_temporal_candidate = False
        confirmed = pending_review = False
        final_decision = "ignored"
        first_frame = int(sequence["frame_indices"][0])
        for frame_index in sequence["frame_indices"]:
            cycle_started = time.perf_counter()
            frame = cv2.imread(str(source_root / f"{frame_index}.jpg"))
            if frame is None:
                raise RuntimeError(f"Could not read negative frame {frame_index}")
            frame = cv2.resize(
                frame,
                (main.LIVE_CAMERA_FRAME_WIDTH, main.LIVE_CAMERA_FRAME_HEIGHT),
                interpolation=cv2.INTER_AREA,
            )
            object_results = main.model.predict(frame, verbose=False)
            person_count = main.count_labels_from_results(
                object_results,
                getattr(main.model, "names", {}),
                main.PERSON_LABELS,
                min_confidence=main.LIVE_CAMERA_PERSON_CONFIDENCE_THRESHOLD,
            )
            raw_boxes = main.detect_vehicle_boxes(frame, fallback_results=object_results)
            classifier = main.classify_crash_frame(frame)
            model1_score = float(classifier.get("accidentProbability") or 0.0)
            timestamp = (int(frame_index) - first_frame) / source_fps
            tiers = main.VEHICLE_CANDIDATE_EVALUATOR.evaluate(
                camera_key,
                raw_boxes,
                classifier_score=model1_score,
                frame_width=frame.shape[1],
                frame_height=frame.shape[0],
                timestamp=timestamp,
            )
            tracking, temporal = main.analyze_vehicle_tracks(
                camera_key,
                list(tiers.tracker_input),
                frame,
                classifier_score=model1_score,
                timestamp=timestamp,
            )
            temporal = main.enforce_candidate_confirmation_safety(temporal, tiers)
            quality = main.analyze_frame_quality(frame)
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
            if event.should_persist:
                if event.detection_mode == "temporal_collision":
                    confirmed = True
                    final_decision = "confirmed_crash"
                elif event.detection_mode == "aftermath_review":
                    pending_review = True
                    final_decision = "possible_crash_aftermath"
            totals["frames"] += 1
            totals["raw"] += len(tiers.raw)
            totals["trusted"] += len(tiers.trusted)
            totals["candidate"] += len(tiers.candidates)
            totals["supported"] += len(tiers.supported_candidates)
            totals["rejected"] += len(tiers.rejected)
            totals["persons"] += person_count
            max_model1 = max(max_model1, model1_score)
            max_temporal = max(max_temporal, temporal.score)
            max_aftermath = max(max_aftermath, aftermath.score)
            had_supported_candidate |= bool(tiers.supported_candidates)
            had_temporal_candidate |= temporal.is_candidate
            if not tiers.trusted and not tiers.supported_candidates and person_count > 0:
                decision = main.evaluate_crash_case_decision(
                    crash_class="accident" if model1_score >= 0.5 else "non_accident",
                    crash_confidence=model1_score,
                    vehicle_count=0,
                    supported_candidate_vehicle_count=0,
                    person_count=person_count,
                    scene_valid=True,
                    motion_valid=False,
                    temporal_verified=False,
                    consecutive_positive_frames=0,
                    active_case_exists=False,
                    cooldown_ready=True,
                )
                if decision[1] == "person_only_not_crash":
                    real_person_only_frames.append(
                        {"sequence_id": sequence["sequence_id"], "frame_index": frame_index}
                    )
            candidate_costs.append(tiers.processing_ms)
            total_cycle_costs.append((time.perf_counter() - cycle_started) * 1000.0)
        candidate_only = bool(
            (had_supported_candidate or had_temporal_candidate)
            and not confirmed
            and not pending_review
        )
        if final_decision == "ignored" and candidate_only:
            final_decision = "candidate_only"
        sequence_results.append(
            {
                "sequence_id": sequence["sequence_id"],
                "category": sequence["category"],
                "frame_count": totals["frames"],
                "trusted_vehicle_detections": totals["trusted"],
                "candidate_detections": totals["candidate"],
                "supported_candidates": totals["supported"],
                "rejected_detections": totals["rejected"],
                "person_detections": totals["persons"],
                "max_model1_score": round(max_model1, 4),
                "max_temporal_score": round(max_temporal, 4),
                "max_aftermath_score": round(max_aftermath, 4),
                "confirmed_crash": confirmed,
                "pending_review": pending_review,
                "candidate_only_activation": candidate_only,
                "final_decision": final_decision,
            }
        )
        main.VEHICLE_CANDIDATE_EVALUATOR.reset_camera(camera_key)
        main.VEHICLE_TRACKING_SERVICE.reset_camera(camera_key)
        main.TEMPORAL_CRASH_VERIFIER.reset_camera(camera_key)
        main.CRASH_AFTERMATH_DETECTOR.reset_camera(camera_key)

    rss_after = process.memory_info().rss / (1024 * 1024)
    return {
        "independent_sequences": len(sequence_results),
        "frames": sum(row["frame_count"] for row in sequence_results),
        "confirmed_crash_false_positives": sum(row["confirmed_crash"] for row in sequence_results),
        "pending_review_false_positives": sum(row["pending_review"] for row in sequence_results),
        "candidate_only_activations": sum(row["candidate_only_activation"] for row in sequence_results),
        "real_person_only_frames": real_person_only_frames,
        "performance": {
            "mean_candidate_processing_ms": round(statistics.fmean(candidate_costs), 4),
            "mean_total_ai_cycle_ms": round(statistics.fmean(total_cycle_costs), 3),
            "ai_fps": round(1000.0 / statistics.fmean(total_cycle_costs), 3),
            "rss_before_mb": round(rss_before, 3),
            "rss_after_mb": round(rss_after, 3),
            "process_cpu_percent": process.cpu_percent(None),
        },
        "sequences": sequence_results,
    }


def main_validation() -> int:
    if main.LIVE_CAMERA_VEHICLE_CONFIDENCE_THRESHOLD != 0.40:
        raise RuntimeError("Trusted threshold changed; Phase 2B validation aborted.")
    if main.COLLISION_CANDIDATE_VEHICLE_CONFIDENCE_THRESHOLD != 0.25:
        raise RuntimeError("Candidate threshold changed; Phase 2B validation aborted.")
    if main.TEMPORAL_CRASH_CONFIG.temporal_crash_threshold != 0.62:
        raise RuntimeError("Temporal threshold changed; Phase 2B validation aborted.")
    if main.AFTERMATH_CONFIG.minimum_score != 0.80:
        raise RuntimeError("Aftermath threshold changed; Phase 2B validation aborted.")
    positive = json.loads(POSITIVE_MANIFEST.read_text(encoding="utf-8"))
    negative = json.loads(NEGATIVE_MANIFEST.read_text(encoding="utf-8"))
    result = {
        "schema_version": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "thresholds": {"normal": 0.40, "candidate": 0.25, "temporal": 0.62, "aftermath": 0.80},
        "analysis_resolution": [
            main.LIVE_CAMERA_FRAME_WIDTH,
            main.LIVE_CAMERA_FRAME_HEIGHT,
        ],
        "positive": validate_positive(positive),
        "negative": validate_negatives(negative),
    }
    RESULT_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"Saved: {RESULT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_validation())
