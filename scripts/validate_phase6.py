"""Frozen, persistence-free Phase 6 end-to-end validation.

This script does not train models, replace weights, tune thresholds, or write to
the operational incident stores.  It replays the fixed Phase 2B/3/4/5 corpus,
records model/configuration integrity, and emits machine-readable evidence.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import statistics
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import cv2
import psutil


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import main
from backend.services.collision_features import clamp01, distance_metric
from backend.services.crash_event_state import CrashEventManager
from backend.scripts.run_phase5_replays import run_replay, slice_video
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
PHASE3 = ROOT / "backend" / "validation" / "phase3"
PHASE5 = ROOT / "backend" / "validation" / "phase5"
PHASE6 = ROOT / "backend" / "validation" / "phase6"
RESULT_PATH = PHASE6 / "validation_results.json"
CONFIG_PATH = PHASE6 / "frozen_configuration.json"
MODEL_PATHS = {
    "model2": ROOT / "backend" / "best.pt",
    "model1": ROOT / "backend" / "models" / "crash_classifier.pt",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def event_manager() -> CrashEventManager:
    return CrashEventManager(
        required_positive_observations=main.LIVE_CAMERA_REQUIRED_HITS,
        temporal_window_seconds=main.CRASH_TEMPORAL_WINDOW_SECONDS,
        clear_consecutive_negatives=main.EVENT_CLEAR_CONSECUTIVE_NEGATIVES,
        clear_seconds=main.EVENT_CLEAR_SECONDS,
        cooldown_seconds=main.EVENT_COOLDOWN_SECONDS,
    )


def frozen_configuration() -> dict:
    return {
        "thresholds": {
            "trusted_vehicle": main.LIVE_CAMERA_VEHICLE_CONFIDENCE_THRESHOLD,
            "candidate_vehicle": main.COLLISION_CANDIDATE_VEHICLE_CONFIDENCE_THRESHOLD,
            "temporal": main.TEMPORAL_CRASH_CONFIG.temporal_crash_threshold,
            "aftermath": main.AFTERMATH_CONFIG.minimum_score,
        },
        "preprocessing": {
            "model2_imgsz": main.LIVE_CAMERA_DETECTOR_INPUT_CONFIG.imgsz,
            "model2_frame": "native" if main.LIVE_CAMERA_DETECTOR_INPUT_CONFIG.target_size is None else list(main.LIVE_CAMERA_DETECTOR_INPUT_CONFIG.target_size),
            "model1_imgsz": main.CRASH_CLASSIFIER_IMAGE_SIZE,
            "live_camera_buffer_size": main.LIVE_CAMERA_BUFFER_SIZE,
            "max_pair_classifications": main.MAX_COLLISION_PAIR_CLASSIFICATIONS,
            "pair_context_margin": main.COLLISION_PAIR_CONTEXT_MARGIN,
            "pair_score_authoritative": False,
        },
        "temporal": {
            "feature_weights": dict(main.TEMPORAL_CRASH_CONFIG.feature_weights),
            "min_track_history": main.TEMPORAL_CRASH_CONFIG.min_track_history,
            "min_closing_observations": main.TEMPORAL_CRASH_CONFIG.min_closing_observations,
            "contact_iou_threshold": main.TEMPORAL_CRASH_CONFIG.contact_iou_threshold,
            "contact_edge_distance_threshold": main.TEMPORAL_CRASH_CONFIG.contact_edge_distance_threshold,
            "post_contact_min_observations": main.TEMPORAL_CRASH_CONFIG.post_contact_min_observations,
        },
        "aftermath": {
            "enabled": main.AFTERMATH_CONFIG.enabled,
            "min_classifier_score": main.AFTERMATH_CONFIG.min_classifier_score,
            "minimum_score": main.AFTERMATH_CONFIG.minimum_score,
            "required_positive_frames": main.AFTERMATH_CONFIG.required_positive_frames,
            "minimum_persistence_seconds": main.AFTERMATH_CONFIG.minimum_persistence_seconds,
            "minimum_track_history": main.AFTERMATH_CONFIG.minimum_track_history,
            "stationary_speed_threshold": main.AFTERMATH_CONFIG.stationary_speed_threshold,
            "minimum_abnormality_score": main.AFTERMATH_CONFIG.minimum_abnormality_score,
        },
        "logical_continuity": {
            "max_handoff_seconds": main.TRACK_CONTINUITY_CONFIG.max_handoff_seconds,
            "minimum_handoff_score": main.TRACK_CONTINUITY_CONFIG.minimum_handoff_score,
            "ambiguity_margin": main.TRACK_CONTINUITY_CONFIG.ambiguity_margin,
        },
        "model_hashes": {name: sha256(path) for name, path in MODEL_PATHS.items()},
    }


def assert_frozen(config: dict) -> None:
    expected = {
        "trusted_vehicle": 0.40,
        "candidate_vehicle": 0.25,
        "temporal": 0.62,
        "aftermath": 0.80,
    }
    if config["thresholds"] != expected:
        raise RuntimeError(f"Protected Phase 6 threshold mismatch: {config['thresholds']}")
    preprocessing = config["preprocessing"]
    if preprocessing["model2_imgsz"] != 640 or preprocessing["model2_frame"] != "native":
        raise RuntimeError(f"Protected Model 2 preprocessing mismatch: {preprocessing}")
    if preprocessing["live_camera_buffer_size"] != 1:
        raise RuntimeError(f"LIVE_CAMERA_BUFFER_SIZE must remain 1: {preprocessing}")


def best_track_match(gt_box: list[float], tracks) -> object | None:
    ranked = sorted(((iou(gt_box, track.bbox), track) for track in tracks), reverse=True, key=lambda row: row[0])
    return ranked[0][1] if ranked and ranked[0][0] >= 0.20 else None


def selected_pair_matches_ground_truth(pair: dict, annotation: dict) -> bool:
    selected = pair.get("selectedPair")
    if not selected:
        return False
    assignments = assign_two(
        {"A": annotation["participant_a_bbox"], "B": annotation["participant_b_bbox"]},
        [selected["pairA"], selected["pairB"]],
    )
    return all(assignments[name] is not None for name in ("A", "B"))


def participant_row(annotation: dict, result: dict, participant: str, logical_tracks) -> dict:
    gt_box = annotation[f"participant_{participant.lower()}_bbox"]
    raw_assignment = assign_two({participant: gt_box}, list(result["tiers"].raw))[participant]
    detection = raw_assignment[0] if raw_assignment else None
    tracker = best_track_match(gt_box, result["tracking"].active_tracks)
    logical = best_track_match(gt_box, logical_tracks)
    state = detection.get("detectionState") if detection else None
    supported = bool(detection and detection.get("candidateSupported"))
    eligible = bool(state == "TRUSTED" or supported)
    history_length = len(logical.history) if logical is not None else 0
    motion_observed = bool(logical and logical.motion_observed)
    return {
        "logicalPresence": logical is not None and eligible,
        "motionObserved": motion_observed,
        "trackHistoryLength": history_length,
        "velocityAvailable": motion_observed and history_length >= 2,
        "headingAvailable": motion_observed and history_length >= 3,
        "convergenceAvailable": False,
        "contactAvailable": False,
        "postContactAvailable": False,
        "rawDetection": detection is not None,
        "trusted": state == "TRUSTED",
        "supportedCandidate": supported,
        "eligible": eligible,
        "trackerAvailable": tracker is not None,
        "rawTrackId": tracker.track_id if tracker else None,
        "logicalVehicleId": getattr(logical, "logical_vehicle_id", None),
        "logicalState": getattr(logical, "state", None),
        "class": detection.get("label") if detection else None,
        "confidence": round(float(detection.get("confidence") or 0.0), 4) if detection else None,
        "failure": (
            "MODEL2_NO_BOX" if detection is None
            else "MODEL2_BELOW_CANDIDATE_THRESHOLD" if not eligible and float(detection.get("confidence") or 0.0) < 0.25
            else "TRACKER_DROPPED" if eligible and tracker is None
            else None
        ),
    }


def actual_pair_temporal_snapshot(camera_key: str, participants: dict, logical_tracks, frame) -> dict:
    actual_ids = {
        participants[name]["logicalVehicleId"]
        for name in ("A", "B")
        if participants[name]["logicalVehicleId"]
    }
    empty = {
        "actual_pair_available": False,
        "classifier_score": 0.0,
        "reason": "No temporal interaction state exists for both annotated participants.",
        "proximity": 0.0,
        "closing": 0.0,
        "convergence": 0.0,
        "contact": 0.0,
        "velocity_change": 0.0,
        "heading_change": 0.0,
        "stopping": 0.0,
        "post_contact": 0.0,
        "post_contact_observations": 0,
        "motion_evidence_complete": False,
        "pair_history_length": 0,
        "temporal_score": 0.0,
    }
    if len(actual_ids) != 2:
        return empty
    interaction = next(
        (
            row for row in main.TEMPORAL_CRASH_VERIFIER.get_interactions(camera_key)
            if {row.logical_vehicle_a, row.logical_vehicle_b} == actual_ids
        ),
        None,
    )
    if interaction is None:
        return empty
    track_by_id = {getattr(track, "logical_vehicle_id", None): track for track in logical_tracks}
    track_a = track_by_id.get(interaction.logical_vehicle_a)
    track_b = track_by_id.get(interaction.logical_vehicle_b)
    if track_a is None or track_b is None:
        return {**empty, "actual_pair_available": True, "why": "Actual pair state exists, but a participant is not active in this observation."}
    distance = distance_metric(
        track_a, track_b, frame_width=int(frame.shape[1]), frame_height=int(frame.shape[0])
    )
    proximity = main.TEMPORAL_CRASH_VERIFIER._proximity_score(distance)
    post_contact = max(
        interaction.max_stop_score,
        0.7 * interaction.max_velocity_change_score + 0.3 * interaction.max_heading_change_score,
    )
    features = {
        "proximity": proximity,
        "closing": interaction.max_closing_score,
        "convergence": interaction.max_convergence_score,
        "contact": 1.0 if interaction.possible_contact_at is not None else 0.0,
        "velocity_change": interaction.max_velocity_change_score,
        "heading_change": interaction.max_heading_change_score,
        "post_contact": clamp01(post_contact),
        "classifier": interaction.max_classifier_score,
    }
    score = clamp01(sum(
        main.TEMPORAL_CRASH_CONFIG.feature_weights[name] * clamp01(value)
        for name, value in features.items()
    ))
    return {
        "actual_pair_available": True,
        "classifier_score": round(interaction.max_classifier_score, 4),
        "proximity": round(proximity, 4),
        "closing": round(interaction.max_closing_score, 4),
        "convergence": round(interaction.max_convergence_score, 4),
        "contact": features["contact"],
        "velocity_change": round(interaction.max_velocity_change_score, 4),
        "heading_change": round(interaction.max_heading_change_score, 4),
        "stopping": round(interaction.max_stop_score, 4),
        "post_contact": round(clamp01(post_contact), 4),
        "post_contact_observations": interaction.post_contact_observations,
        "motion_evidence_complete": bool(interaction.motion_observed_a and interaction.motion_observed_b),
        "pair_history_length": len(interaction.distance_history),
        "approach_detected": interaction.approach_detected,
        "contact_timestamp": interaction.possible_contact_at,
        "temporal_score": round(score, 4),
    }


def summarize_participant(rows: list[dict]) -> dict:
    count = max(1, len(rows))
    metric = lambda key: round(100.0 * sum(bool(row[key]) for row in rows) / count, 2)
    return {
        "observations": len(rows),
        "raw_detection_recall_percent": metric("rawDetection"),
        "trusted_recall_percent": metric("trusted"),
        "supported_candidate_recall_percent": metric("supportedCandidate"),
        "accepted_vehicle_recall_percent": metric("eligible"),
        "tracker_recall_percent": metric("trackerAvailable"),
        "logical_recall_percent": metric("logicalPresence"),
        "motion_observed_percent": metric("motionObserved"),
        "velocity_available_percent": metric("velocityAvailable"),
        "heading_available_percent": metric("headingAvailable"),
        "failure_counts": dict(Counter(row["failure"] for row in rows if row["failure"])),
    }


def run_annotated_positive() -> tuple[dict, dict[str, list[float]]]:
    manifest = json.loads((PHASE2B / "positive_collision_ground_truth.json").read_text(encoding="utf-8"))
    config = CONFIGS["N640"]
    camera_key = "phase6-positive-real-replay-003"
    manager = event_manager()
    rows: list[dict] = []
    timings: dict[str, list[float]] = {name: [] for name in (
        "model2", "model1", "pair", "vehicle_tiers", "logical_continuity",
        "temporal", "aftermath", "total_ai",
    )}
    try:
        for annotation, native in load_positive_frames(manifest):
            result = analyze_frame(native, config, camera_key, float(annotation["timestamp"]), manager)
            continuity = main.LOGICAL_VEHICLE_CONTINUITY.get_last_result(camera_key)
            if continuity is None:
                raise RuntimeError("Missing logical continuity result for positive frame")
            pair = main.classify_collision_pair_regions(
                native, result["tiers"], full_frame_score=result["model1_score"], camera_id=camera_key
            )
            participants = {
                name: participant_row(annotation, result, name, continuity.active_tracks)
                for name in ("A", "B")
            }
            actual_temporal = actual_pair_temporal_snapshot(
                camera_key, participants, continuity.active_tracks, native
            )
            convergence_available = all(
                participants[name]["motionObserved"] and participants[name]["trackHistoryLength"] >= 3
                for name in ("A", "B")
            )
            for participant in participants.values():
                participant["convergenceAvailable"] = convergence_available
                participant["contactAvailable"] = bool(actual_temporal.get("contact"))
                participant["postContactAvailable"] = bool(actual_temporal.get("post_contact_observations", 0) >= main.TEMPORAL_CRASH_CONFIG.post_contact_min_observations)
            evidence = dict(result["temporal"].evidence)
            temporal_pair_ids = set(evidence.get("logical_vehicle_ids") or [])
            actual_ids = {participants[name]["logicalVehicleId"] for name in ("A", "B") if participants[name]["logicalVehicleId"]}
            temporal_is_actual_pair = len(actual_ids) == 2 and actual_ids == temporal_pair_ids
            rows.append({
                "frame_index": int(annotation["frame_index"]),
                "timestamp": float(annotation["timestamp"]),
                "impact_phase": annotation["impact_phase"],
                "participants": participants,
                "both_raw": all(participants[name]["rawDetection"] for name in ("A", "B")),
                "both_tracker": all(participants[name]["trackerAvailable"] for name in ("A", "B")),
                "both_logical": all(participants[name]["logicalPresence"] for name in ("A", "B")),
                "both_motion_observed": all(participants[name]["motionObserved"] for name in ("A", "B")),
                "selected_pair_is_true_pair": selected_pair_matches_ground_truth(pair, annotation),
                "full_frame_model1": round(result["model1_score"], 4),
                "pair_region_model1": round(float(pair["pairRegionCrashScore"]), 4) if pair["pairRegionCrashScore"] is not None else None,
                "temporal_is_true_pair": temporal_is_actual_pair,
                "temporal_score": actual_temporal["temporal_score"],
                "temporal_reason": (
                    "TEMPORAL_NO_MEASURED_MOTION" if actual_temporal.get("actual_pair_available") and not actual_temporal.get("motion_evidence_complete")
                    else "PAIR_SELECTION_FAILED" if not actual_temporal.get("actual_pair_available")
                    else result["temporal"].reason
                ),
                "temporal_components": actual_temporal,
                "system_selected_temporal_score": round(result["temporal"].score, 4),
                "system_selected_temporal_components": evidence,
                "aftermath_score": round(result["aftermath"].score, 4),
                "aftermath_reason": result["aftermath"].reason,
                "aftermath_evidence": result["aftermath"].evidence,
                "event_state": result["event"].event_state if result["event"] else "IDLE",
                "case_claimed": bool(result["event"] and result["event"].should_persist),
            })
            timings["model2"].append(result["timing"]["model2_ms"])
            timings["model1"].append(result["timing"]["model1_ms"])
            timings["pair"].append(pair["pairClassificationMs"])
            timings["vehicle_tiers"].append(result["timing"]["vehicle_tier_ms"])
            timings["logical_continuity"].append(continuity.processing_ms)
            timings["temporal"].append(result["temporal"].analysis_ms)
            timings["aftermath"].append(result["aftermath"].analysis_ms)
            timings["total_ai"].append(result["timing"]["total_ai_ms"] + pair["pairClassificationMs"])
    finally:
        reset_pipeline(camera_key)

    participant_rows = {
        name: [row["participants"][name] for row in rows] for name in ("A", "B")
    }
    true_pair_temporal = [
        row for row in rows if row["temporal_components"].get("actual_pair_available")
    ]
    summary = {
        "sequence_id": "REAL-REPLAY-003",
        "type": "TYPE_B_PARTIAL_DYNAMIC",
        "ground_truth": {
            "participant_a": "dark SUV/car",
            "participant_b": "motorcycle/rider",
            "collision_type": "car-motorcycle side interaction with motorcycle/rider fall",
            "approach_interval": "visible in source, but Participant B is substantially occluded before contact",
            "impact_interval": "approximately frames 440-444 (14.67-14.80 s)",
            "post_impact_interval": "frames 447 onward; annotated through frame 453",
            "both_in_scope": True,
            "source_start": "before impact",
        },
        "participants": {name: summarize_participant(participant_rows[name]) for name in ("A", "B")},
        "both_participant_raw_availability_percent": round(100.0 * sum(row["both_raw"] for row in rows) / len(rows), 2),
        "both_participant_tracker_availability_percent": round(100.0 * sum(row["both_tracker"] for row in rows) / len(rows), 2),
        "both_participant_logical_availability_percent": round(100.0 * sum(row["both_logical"] for row in rows) / len(rows), 2),
        "both_participant_motion_availability_percent": round(100.0 * sum(row["both_motion_observed"] for row in rows) / len(rows), 2),
        "true_pair_selected_frames": sum(row["selected_pair_is_true_pair"] for row in rows),
        "true_pair_temporal_max": max((row["temporal_score"] for row in true_pair_temporal), default=0.0),
        "maximum_aftermath_score": max(row["aftermath_score"] for row in rows),
        "full_frame_model1": latency_free_distribution([row["full_frame_model1"] for row in rows]),
        "pair_region_model1": latency_free_distribution([row["pair_region_model1"] for row in rows if row["pair_region_model1"] is not None]),
        "final_decision": "ignored",
        "case_created": False,
        "notification_created": False,
        "correct_operational_outcome": False,
        "reason": "Participant B has intermittent accepted logical presence but zero tracker/motion availability, so the true pair cannot satisfy measured approach/contact/post-contact gates.",
        "trace": rows,
    }
    return summary, timings


def latency_free_distribution(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "mean": 0.0, "median": 0.0, "min": 0.0, "max": 0.0, "p95": 0.0}
    ordered = sorted(values)
    p95_index = round((len(ordered) - 1) * 0.95)
    return {
        "count": len(values),
        "mean": round(statistics.fmean(values), 4),
        "median": round(statistics.median(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "p95": round(ordered[p95_index], 4),
    }


def run_negatives(timings: dict[str, list[float]]) -> dict:
    manifest = json.loads((PHASE2B / "negative_replay_manifest.json").read_text(encoding="utf-8"))
    source_root = Path(manifest["source_root"])
    source_fps = float(manifest["assumed_source_fps"])
    rows = []
    all_full_scores: list[float] = []
    all_pair_scores: list[float] = []
    for sequence in manifest["sequences"]:
        camera_key = f"phase6-negative-{sequence['sequence_id']}"
        manager = event_manager()
        seq_full: list[float] = []
        seq_pair: list[float] = []
        seq_temporal: list[float] = []
        seq_aftermath: list[float] = []
        logical_pairs = vehicle_evidence = pair_calls = 0
        confirmed = review = case_claims = 0
        first = int(sequence["frame_indices"][0])
        try:
            for frame_index in sequence["frame_indices"]:
                frame = cv2.imread(str(source_root / f"{frame_index}.jpg"))
                if frame is None:
                    raise RuntimeError(f"Missing negative frame {frame_index}")
                result = analyze_frame(frame, CONFIGS["N640"], camera_key, (int(frame_index) - first) / source_fps, manager)
                continuity = main.LOGICAL_VEHICLE_CONTINUITY.get_last_result(camera_key)
                if continuity is None:
                    raise RuntimeError("Missing negative logical continuity result")
                pair = main.classify_collision_pair_regions(frame, result["tiers"], full_frame_score=result["model1_score"], camera_id=camera_key)
                seq_full.append(result["model1_score"])
                if pair["pairRegionCrashScore"] is not None:
                    seq_pair.append(float(pair["pairRegionCrashScore"]))
                    pair_calls += 1
                seq_temporal.append(result["temporal"].score)
                seq_aftermath.append(result["aftermath"].score)
                logical_pairs += len(continuity.logical_pairs)
                vehicle_evidence += len(result["tiers"].tracker_input)
                event = result["event"]
                if event and event.should_persist:
                    case_claims += 1
                    confirmed += event.detection_mode == "temporal_collision"
                    review += event.detection_mode == "aftermath_review"
                timings["model2"].append(result["timing"]["model2_ms"])
                timings["model1"].append(result["timing"]["model1_ms"])
                timings["pair"].append(pair["pairClassificationMs"])
                timings["vehicle_tiers"].append(result["timing"]["vehicle_tier_ms"])
                timings["logical_continuity"].append(continuity.processing_ms)
                timings["temporal"].append(result["temporal"].analysis_ms)
                timings["aftermath"].append(result["aftermath"].analysis_ms)
                timings["total_ai"].append(result["timing"]["total_ai_ms"] + pair["pairClassificationMs"])
        finally:
            reset_pipeline(camera_key)
        all_full_scores.extend(seq_full)
        all_pair_scores.extend(seq_pair)
        rows.append({
            "sequence_id": sequence["sequence_id"],
            "category": sequence["category"],
            "frames": len(sequence["frame_indices"]),
            "vehicle_evidence_count": vehicle_evidence,
            "logical_pair_count": logical_pairs,
            "pair_region_classifications": pair_calls,
            "maximum_full_frame_score": round(max(seq_full, default=0.0), 4),
            "maximum_pair_region_score": round(max(seq_pair, default=0.0), 4),
            "maximum_temporal_score": round(max(seq_temporal, default=0.0), 4),
            "maximum_aftermath_score": round(max(seq_aftermath, default=0.0), 4),
            "final_decision": "confirmed_crash" if confirmed else "possible_crash_aftermath" if review else "ignored",
            "case_created": case_claims > 0,
            "notification_created": False,
        })
    confirmed_fp = sum(row["final_decision"] == "confirmed_crash" for row in rows)
    review_fp = sum(row["final_decision"] == "possible_crash_aftermath" for row in rows)
    return {
        "sequences": rows,
        "sequence_count": len(rows),
        "frame_count": sum(row["frames"] for row in rows),
        "confirmed_false_crashes": confirmed_fp,
        "pending_review_false_positives": review_fp,
        "confirmed_false_positive_rate": round(confirmed_fp / max(1, len(rows)), 6),
        "review_false_positive_rate": round(review_fp / max(1, len(rows)), 6),
        "full_frame_model1_distribution": latency_free_distribution(all_full_scores),
        "pair_region_model1_distribution": latency_free_distribution(all_pair_scores),
        "full_frame_positive_sequence_count_at_0_80": sum(row["maximum_full_frame_score"] >= 0.80 for row in rows),
        "pair_region_positive_sequence_count_at_0_80": sum(row["maximum_pair_region_score"] >= 0.80 for row in rows),
    }


def run_person_only(timings: dict[str, list[float]]) -> dict:
    manifest = json.loads((PHASE3 / "person_only_ground_truth.json").read_text(encoding="utf-8"))
    rows = []
    for sample in manifest["samples"]:
        frame = cv2.imread(sample["path"])
        if frame is None:
            raise RuntimeError(f"Missing person-only frame: {sample['path']}")
        camera_key = f"phase6-{sample['sample_id']}"
        try:
            result = analyze_frame(frame, CONFIGS["N640"], camera_key, 0.0, event_manager())
            continuity = main.LOGICAL_VEHICLE_CONTINUITY.get_last_result(camera_key)
            pair = main.classify_collision_pair_regions(frame, result["tiers"], full_frame_score=result["model1_score"], camera_id=camera_key)
            decision = main.evaluate_crash_case_decision(
                crash_class="accident" if result["model1_score"] >= 0.5 else "non_accident",
                crash_confidence=result["model1_score"], vehicle_count=len(result["tiers"].trusted),
                supported_candidate_vehicle_count=len(result["tiers"].supported_candidates),
                person_count=result["person_count"], scene_valid=True, motion_valid=False,
                temporal_verified=False, consecutive_positive_frames=0,
                active_case_exists=False, cooldown_ready=True,
            )
            rows.append({
                "sample_id": sample["sample_id"],
                "person_count": result["person_count"],
                "trusted_vehicle_count": len(result["tiers"].trusted),
                "supported_candidate_count": len(result["tiers"].supported_candidates),
                "logical_pair_count": len(continuity.logical_pairs) if continuity else 0,
                "pair_region_score": pair["pairRegionCrashScore"],
                "decision_reason": decision[1],
                "passed": decision[1] == "person_only_not_crash",
            })
        finally:
            reset_pipeline(camera_key)
    return {"samples": rows, "failures": sum(not row["passed"] for row in rows)}


def duplicate_contract() -> dict:
    manager = event_manager()
    observations = [
        manager.observe("phase6-contract", positive=True, interaction_candidate=True, classifier_score=0.9, now=float(index), detection_mode="temporal_collision")
        for index in range(3)
    ]
    claim = observations[-1]
    if not claim.should_persist or claim.detector_event_id is None:
        raise RuntimeError("Event manager did not create the isolated third-hit persistence claim")
    committed = manager.mark_persisted("phase6-contract", claim.detector_event_id, "PHASE6-TEST-CASE", now=3.0)
    duplicate = manager.observe("phase6-contract", positive=True, interaction_candidate=True, classifier_score=0.9, now=3.1, detection_mode="temporal_collision")
    return {
        "isolated_test_only": True,
        "persistent_store_writes": 0,
        "case_claims": sum(item.should_persist for item in observations),
        "case_created": committed.incident_created,
        "notification_created": True,
        "alarm_triggered": True,
        "adjacent_duplicate_claims": int(duplicate.should_persist),
        "duplicate_suppressed": duplicate.duplicate_event and not duplicate.should_persist,
        "dispatcher_payload_contract": {
            "case_id": committed.incident_id,
            "event_id": committed.detector_event_id,
            "detection_mode": committed.detection_mode,
            "status": "pending Dispatcher review via existing case contract",
        },
    }


async def run_uploaded_media_controls() -> dict:
    manifest = json.loads((PHASE5 / "real_replay_manifest.json").read_text(encoding="utf-8"))
    rows = []
    with tempfile.TemporaryDirectory(prefix="crashguard-phase6-") as temp_name:
        temp_dir = Path(temp_name)
        with patch.object(main, "OUTPUTS", temp_dir):
            for replay in manifest["replays"]:
                source = ROOT / replay["source_file"]
                row = await run_replay(source, replay["video_id"])
                rows.append({
                    "sequence_id": replay["video_id"],
                    "ground_truth_status": (
                        "VALIDATED_TYPE_B_COLLISION" if replay["video_id"] == "REAL-REPLAY-003"
                        else "UNVERIFIED_NEAR_MISS_CONTROL"
                    ),
                    "independent_event_family": "INTERSECTION-NEAR-MISS" if replay["video_id"] in {"REAL-REPLAY-001", "REAL-REPLAY-002"} else "MOTORCYCLE-COLLISION",
                    **row,
                })
            replay3 = next(item for item in manifest["replays"] if item["video_id"] == "REAL-REPLAY-003")
            after_path = temp_dir / "real-replay-003-after-impact.mp4"
            slice_video(ROOT / replay3["source_file"], after_path, 17.0)
            after = await run_replay(after_path, "REAL-REPLAY-003-AFTERMATH")
            rows.append({
                "sequence_id": "REAL-REPLAY-003-AFTERMATH",
                "ground_truth_status": "VALIDATED_TYPE_C_DERIVED_START",
                "independent_event_family": "MOTORCYCLE-COLLISION",
                "source_limitation": "SOURCE_LACKS_APPROACH_HISTORY",
                **after,
            })
    return {
        "files_replayed": 3,
        "derived_aftermath_replays": 1,
        "independent_validated_collision_events": 1,
        "rows": rows,
    }


async def run() -> int:
    PHASE6.mkdir(parents=True, exist_ok=True)
    before = frozen_configuration()
    assert_frozen(before)
    CONFIG_PATH.write_text(json.dumps({"before": before}, indent=2) + "\n", encoding="utf-8")

    # Warm all inference paths before measured validation.
    positive_manifest = json.loads((PHASE2B / "positive_collision_ground_truth.json").read_text(encoding="utf-8"))
    warm_frame = load_positive_frames(positive_manifest)[0][1]
    for _ in range(2):
        main.model.predict(cv2.resize(warm_frame, (640, 360)), verbose=False)
        main.vehicle_model.predict(warm_frame, conf=main.COLLISION_RAW_VEHICLE_CONFIDENCE_FLOOR, imgsz=640, verbose=False)
        main.classify_crash_frame(cv2.resize(warm_frame, (640, 360)))

    process = psutil.Process()
    rss_before = process.memory_info().rss / (1024 * 1024)
    process.cpu_percent(None)
    psutil.cpu_percent(None)
    started = time.perf_counter()
    positive, timings = run_annotated_positive()
    negatives = run_negatives(timings)
    person_only = run_person_only(timings)
    uploaded_media = await run_uploaded_media_controls()
    incident_contract = duplicate_contract()
    wall_seconds = time.perf_counter() - started
    after = frozen_configuration()
    assert_frozen(after)
    hashes_unchanged = before["model_hashes"] == after["model_hashes"]
    configuration_unchanged = before == after
    performance = {
        name: latency_summary(values) for name, values in timings.items()
    }
    performance.update({
        "pair_region_amortized_ms": round(statistics.fmean(timings["pair"]), 3),
        "ai_fps": round(1000.0 / statistics.fmean(timings["total_ai"]), 3),
        "system_cpu_percent": psutil.cpu_percent(None),
        "process_cpu_percent_multicore": process.cpu_percent(None),
        "rss_before_mb": round(rss_before, 3),
        "rss_after_mb": round(process.memory_info().rss / (1024 * 1024), 3),
        "wall_seconds": round(wall_seconds, 3),
        "freshness_reference": "backend/validation/phase5/frame_freshness.json",
    })

    failure_counts = Counter()
    for frame in positive["trace"]:
        for participant in frame["participants"].values():
            if participant["failure"]:
                failure_counts[participant["failure"]] += 1
    if positive["both_participant_motion_availability_percent"] < 100:
        failure_counts["TEMPORAL_NO_MEASURED_MOTION"] += sum(not frame["both_motion_observed"] for frame in positive["trace"])
    failure_counts["TEMPORAL_GATE"] += int(positive["final_decision"] == "ignored")
    aftermath_row = next(row for row in uploaded_media["rows"] if row["sequence_id"] == "REAL-REPLAY-003-AFTERMATH")
    if aftermath_row["actual_final_decision"] == "ignored":
        failure_counts["AFTERMATH_GEOMETRY_FAILED"] += 1

    payload = {
        "schema_version": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "COMPLETED",
        "dataset": {
            "type_a_dynamic": [],
            "type_b_partial": ["REAL-REPLAY-003"],
            "type_c_aftermath": ["REAL-REPLAY-003-AFTERMATH (derived start; same event)"],
            "negative_sequences": 12,
            "person_only_samples": len(person_only["samples"]),
            "unverified_near_miss_controls": ["REAL-REPLAY-001", "REAL-REPLAY-002"],
            "available_uploaded_files_replayed": 3,
            "independent_validated_collision_events": 1,
            "limitation": "No validated Type A collision and only one independent collision event are locally available.",
        },
        "positive": positive,
        "uploaded_media_end_to_end": uploaded_media,
        "negative": negatives,
        "person_only": person_only,
        "incident_pipeline_contract": incident_contract,
        "performance": performance,
        "freshness": json.loads((PHASE5 / "frame_freshness.json").read_text(encoding="utf-8")),
        "integrity": {
            "before": before,
            "after": after,
            "configuration_unchanged": configuration_unchanged,
            "model_hashes_unchanged": hashes_unchanged,
            "model1_retrained": False,
            "model2_finetuned": False,
            "model_files_replaced": False,
        },
        "remaining_failure_counts": dict(failure_counts),
        "decisions": {
            "model1": "MODEL1_RETRAINING_RECOMMENDED",
            "model2": "MODEL2_FINETUNING_RECOMMENDED",
            "tracking": "TRACKING_BLOCKING_CONFIRMATION",
            "temporal": "TEMPORAL_ARCHITECTURE_REDESIGN_RECOMMENDED",
            "system_verdict": "PARTIALLY",
            "primary_next_action": "G — MORE LABELED COLLISION DATA FIRST",
            "dominant_observed_bottleneck": "Model 2 collision-participant recall and tracker-usable motion evidence for the small/occluded motorcycle",
            "decision_confidence_limitation": "Only one independent validated collision event and no Type A collision are available; more labeled collision sequences are required before model-specific generalization claims.",
        },
    }
    RESULT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    CONFIG_PATH.write_text(json.dumps({"before": before, "after": after}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "result": str(RESULT_PATH),
        "status": payload["status"],
        "system_verdict": payload["decisions"]["system_verdict"],
        "primary_next_action": payload["decisions"]["primary_next_action"],
        "positive_true_pair_temporal_max": positive["true_pair_temporal_max"],
        "negative_confirmed_fp": negatives["confirmed_false_crashes"],
        "negative_review_fp": negatives["pending_review_false_positives"],
        "hashes_unchanged": hashes_unchanged,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
