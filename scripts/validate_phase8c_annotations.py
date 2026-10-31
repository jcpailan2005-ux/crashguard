"""Validate Phase 8C annotations and promote only verified, valid events."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.annotate_phase8c_events import verification_errors

P8B = ROOT / "backend" / "validation" / "phase8b"
P8C = ROOT / "backend" / "validation" / "phase8c"
QUEUE = P8C / "manifests" / "annotation_queue.csv"
VALID_REJECTIONS = {
    "REJECT_CONTACT_NOT_DEFENSIBLE", "REJECT_PARTICIPANT_UNBOUNDABLE",
    "REJECT_WRONG_EVENT_TYPE", "REJECT_DUPLICATE", "REJECT_INSUFFICIENT_FRAMES",
    "REJECT_NOT_COLLISION", "REJECT_OTHER",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def base_errors(payload: dict, queue_row: dict) -> list[str]:
    errors = []
    source = Path(payload.get("source", ""))
    if payload.get("event_id") != queue_row["event_id"]:
        errors.append("event_id mismatch")
    if payload.get("source_id") != queue_row["source_id"]:
        errors.append("source_id mismatch")
    if not source.is_file():
        errors.append("source media missing")
    elif sha256(source) != payload.get("source_sha256"):
        errors.append("source hash mismatch")
    if payload.get("source_provenance") != "RESEARCH_USE_CONFIRMED":
        errors.append("provenance not accepted")
    if payload.get("frame_count", 0) <= 0 or len(payload.get("resolution", [])) != 2:
        errors.append("invalid media metadata")
    if payload.get("ground_truth_collision_pair") != ["P-A", "P-B"]:
        errors.append("participant references invalid")
    if set(payload.get("participants", {})) != {"P-A", "P-B"}:
        errors.append("participant IDs are missing or non-unique")
    return errors


def main() -> int:
    with QUEUE.open(encoding="utf-8", newline="") as source:
        queue = list(csv.DictReader(source))
    phase_manifest = json.loads((P8C / "manifests" / "phase8c_manifest.json").read_text(encoding="utf-8"))
    phase8b = json.loads((P8B / "validation_manifest.json").read_text(encoding="utf-8"))
    results = []
    source_hashes: dict[str, str] = {}
    for row in queue:
        annotation_path = P8C / "annotations" / f"{row['event_id']}.json"
        errors = []
        if not annotation_path.is_file():
            results.append({"event_id": row["event_id"], "status": "FAIL", "errors": ["annotation file missing"], "keyframes": 0})
            continue
        payload = json.loads(annotation_path.read_text(encoding="utf-8"))
        errors.extend(base_errors(payload, row))
        digest = payload.get("source_sha256", "")
        if digest in source_hashes and source_hashes[digest] != row["event_id"]:
            errors.append(f"exact duplicate physical source of {source_hashes[digest]}")
        source_hashes[digest] = row["event_id"]
        review_state = payload.get("review_state")
        if review_state == "HUMAN_VERIFIED":
            errors.extend(verification_errors(payload))
            if any(annotation.get("annotation_state") != "HUMAN_VERIFIED" for annotation in payload.get("annotations", [])):
                errors.append("verified event contains non-verified keyframes")
            status = "PASS" if not errors else "FAIL"
            payload["promotion_status"] = "PROMOTED_VALIDATION_EVENT" if status == "PASS" else "NOT_PROMOTED"
            row["annotation_status"] = "HUMAN_VERIFIED" if status == "PASS" else "IN_PROGRESS"
            row["review_status"] = "HUMAN_VERIFIED" if status == "PASS" else "AWAITING_HUMAN_REVIEW"
            row["promotion_status"] = payload["promotion_status"]
            row["rejection_reason"] = ""
            annotation_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        elif review_state == "REJECTED":
            code = (payload.get("rejection") or {}).get("code")
            if code not in VALID_REJECTIONS or not payload.get("reviewer"):
                errors.append("invalid rejection disposition")
            status = "REJECTED" if not errors else "FAIL"
            row["annotation_status"] = "REJECTED"
            row["review_status"] = "REJECTED"
            row["promotion_status"] = "NOT_PROMOTED"
            row["rejection_reason"] = code or ""
        else:
            status = "AWAITING_HUMAN_REVIEW" if not errors else "FAIL"
            row["annotation_status"] = "IN_PROGRESS" if payload.get("annotations") else "NOT_STARTED"
            row["review_status"] = "AWAITING_HUMAN_REVIEW"
            row["promotion_status"] = "NOT_PROMOTED"
        results.append({
            "event_id": row["event_id"],
            "screened_type": row["screened_type"],
            "review_state": review_state,
            "status": status,
            "keyframes": len(payload.get("annotations", [])),
            "errors": errors,
        })

    with QUEUE.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(queue[0]))
        writer.writeheader()
        writer.writerows(queue)
    live_hashes = {
        "backend/best.pt": sha256(ROOT / "backend" / "best.pt"),
        "backend/models/crash_classifier.pt": sha256(ROOT / "backend" / "models" / "crash_classifier.pt"),
    }
    integrity_errors = []
    if live_hashes != phase_manifest["model_sha256"] or live_hashes != phase8b["frozen_configuration"]["weight_sha256"]:
        integrity_errors.append("deployed model hash changed")
    expected = {"trusted": 0.40, "candidate": 0.25, "temporal": 0.62, "aftermath": 0.80, "model2_imgsz": 640, "decoded_frame_path": "NATIVE"}
    if phase_manifest["frozen_configuration"] != expected:
        integrity_errors.append("frozen configuration changed")
    counts = Counter(result["status"] for result in results)
    verified = [result for result in results if result["status"] == "PASS"]
    overall = "PASS" if len(verified) == 21 and not integrity_errors else "PENDING_HUMAN_REVIEW" if not integrity_errors and not counts["FAIL"] else "FAIL"
    report = {
        "schema_version": 1,
        "overall_integrity": overall,
        "queue_count": len(queue),
        "status_counts": dict(sorted(counts.items())),
        "promoted_validation_events": len(verified),
        "verified_type_counts": dict(sorted(Counter(result["screened_type"] for result in verified).items())),
        "model_hashes_verified": not any("model hash" in error for error in integrity_errors),
        "thresholds_verified": not any("configuration" in error for error in integrity_errors),
        "integrity_errors": integrity_errors,
        "events": results,
    }
    (P8C / "qa" / "annotation_integrity.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    phase_manifest["human_verified"] = len(verified)
    phase_manifest["awaiting_human_review"] = counts["AWAITING_HUMAN_REVIEW"]
    phase_manifest["promoted_validation_events"] = len(verified)
    phase_manifest["status"] = (
        "PHASE 8C PARTIALLY COMPLETED — TYPE A DIAGNOSTICS READY, CORPUS GAP REMAINS"
        if report["verified_type_counts"].get("TYPE_A", 0) >= 6
        else "PHASE 8C PARTIALLY COMPLETED — HUMAN ANNOTATION REQUIRED"
    )
    phase_manifest["baseline_status"] = (
        "READY_FOR_FROZEN_REPLAY" if report["verified_type_counts"].get("TYPE_A", 0) >= 6
        else "BLOCKED_UNTIL_SIX_HUMAN_VERIFIED_TYPE_A_EVENTS"
    )
    (P8C / "manifests" / "phase8c_manifest.json").write_text(json.dumps(phase_manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("overall_integrity", "queue_count", "status_counts", "promoted_validation_events", "model_hashes_verified", "thresholds_verified")}, indent=2))
    return 1 if overall == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
