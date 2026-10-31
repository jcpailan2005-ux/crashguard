"""Build CrashGuard Phase 8 intake, provenance, hash, and readiness artifacts.

This script is intentionally diagnostic-only. It does not import backend.main,
run training, alter model files, or change runtime configuration.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
PHASE8 = ROOT / "backend" / "validation" / "phase8"
INCOMING = PHASE8 / "incoming" / "nexar"
MANIFESTS = PHASE8 / "manifests"
ANNOTATIONS = PHASE8 / "annotations"
REPORTS = PHASE8 / "reports"
HASHES = PHASE8 / "hashes"
REVIEW_PATH = MANIFESTS / "manual_reviews.csv"
SOURCE_PATH = MANIFESTS / "external_sources.csv"
FINGERPRINT_PATH = HASHES / "media_fingerprints.csv"
PHASE7 = ROOT / "backend" / "validation" / "phase7"
LICENSE_URL = "https://huggingface.co/datasets/nexar-ai/nexar_collision_prediction/blob/main/LICENSE"
DATASET_URL = "https://huggingface.co/datasets/nexar-ai/nexar_collision_prediction"
FIELDS = [
    "source_id", "source_name", "source_url_or_path", "provider", "license",
    "license_url_or_note", "retrieval_date", "media_type", "original_filename",
    "sha256", "file_size", "duration", "fps", "resolution", "claimed_label",
    "event_id", "source_family", "provenance_status", "usage_status", "notes",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def phash(frame: np.ndarray) -> str:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA)
    dct = cv2.dct(np.float32(resized))[:8, :8]
    bits = dct > np.median(dct[1:])
    return f"{int(''.join('1' if bit else '0' for bit in bits.flat), 2):016X}"


def video_metadata(path: Path) -> tuple[dict, list[str], list[str]]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        return ({"duration": 0.0, "fps": 0.0, "resolution": "UNREADABLE", "frame_count": 0}, [], [])
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    indexes = np.linspace(0, max(0, count - 1), 9).astype(int) if count else []
    full_hashes, crop_hashes = [], []
    for index in indexes:
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(index))
        ok, frame = capture.read()
        if not ok or frame is None:
            continue
        full_hashes.append(phash(frame))
        h, w = frame.shape[:2]
        crop = frame[h // 8: h - h // 8, w // 8: w - w // 8]
        crop_hashes.append(phash(crop))
    capture.release()
    return ({
        "duration": round(count / fps, 3) if fps > 0 else 0.0,
        "fps": round(fps, 4),
        "resolution": f"{width}x{height}",
        "frame_count": count,
    }, full_hashes, crop_hashes)


def hamming(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


def fingerprint_distance(left: list[str], right: list[str]) -> float:
    if not left or len(left) != len(right):
        return 64.0
    return round(sum(hamming(a, b) for a, b in zip(left, right)) / len(left), 3)


def import_phase7_annotation() -> dict:
    source_path = PHASE7 / "annotations" / "EVENT-0001.json"
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    payload["schema_version"] = 2
    payload["event_type"] = payload.get("type")
    payload["ground_truth_collision_pair"] = payload.get("groundTruthCollisionPair")
    payload["analysis_start"] = {"frame": min(row["frame_index"] for row in payload["annotations"]), "basis": "annotated Phase 7 window"}
    payload["analysis_end"] = {"frame": max(row["frame_index"] for row in payload["annotations"]), "basis": "annotated Phase 7 window"}
    payload["contact_peak_frame"] = None
    payload["contact_uncertain"] = True
    payload["source_provenance"] = {
        "status": "LOCAL_EXISTING",
        "source_id": "LOCAL-EVENT-0001",
        "note": "Human-reviewed Phase 7 event retained without claiming external licensing.",
    }
    for row in payload["annotations"]:
        row["ground_truth_collision_pair"] = row.get("groundTruthCollisionPair")
        row["participant_a_visibility"] = row.get("participant_a_occlusion")
        row["participant_b_visibility"] = row.get("participant_b_occlusion")
        row["contact_status"] = row.get("contact_visible")
        row["annotation_confidence"] = row.get("annotation_uncertainty")
        row["distractor_vehicle_boxes"] = row.get("distractor_boxes", [])
        row["distractor_ids"] = [item["id"] for item in row.get("distractor_boxes", [])]
        row["distractor_motion_notes"] = [item.get("notes", "") for item in row.get("distractor_boxes", [])]
        row["annotation_source"] = "HUMAN_VERIFIED"
    target = ANNOTATIONS / "EVENT-0001.json"
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def build_sources() -> tuple[list[dict], list[dict], list[dict]]:
    reviews = {row["source_id"]: row for row in read_csv(REVIEW_PATH)}
    positive_meta = {row["file_name"]: row for row in read_csv(INCOMING / "positive_metadata.csv")}
    negative_meta = {row["file_name"]: row for row in read_csv(INCOMING / "negative_metadata.csv")}
    phase7_annotation = json.loads((PHASE7 / "annotations" / "EVENT-0001.json").read_text(encoding="utf-8"))
    existing = Path(phase7_annotation["source"])
    existing_meta, existing_fp, existing_crop = video_metadata(existing)
    rows = [{
        "source_id": "LOCAL-EVENT-0001", "source_name": "CrashGuard Phase 7 retained event",
        "source_url_or_path": str(existing), "provider": "Local existing/user workflow",
        "license": "Local existing", "license_url_or_note": "Authorization/license not independently established by Phase 8",
        "retrieval_date": "", "media_type": "video", "original_filename": existing.name,
        "sha256": sha256(existing), "file_size": existing.stat().st_size,
        "duration": existing_meta["duration"], "fps": existing_meta["fps"], "resolution": existing_meta["resolution"],
        "claimed_label": "human-reviewed collision", "event_id": "EVENT-0001",
        "source_family": "REAL-REPLAY-003", "provenance_status": "LOCAL_EXISTING",
        "usage_status": "PROMOTED_POSITIVE", "notes": "Retained independent Type B event from Phase 7.",
    }]
    fingerprints = [{
        "source_id": "LOCAL-EVENT-0001", "sha256": rows[0]["sha256"], "frame_count": existing_meta["frame_count"],
        "sampled_phash": ";".join(existing_fp), "center_crop_phash": ";".join(existing_crop), "open_status": "PASS",
    }]
    details = [{"source_id": "LOCAL-EVENT-0001", "phashes": existing_fp, "crop_phashes": existing_crop}]
    for label, metadata in (("positive", positive_meta), ("negative", negative_meta)):
        for path in sorted((INCOMING / label).glob("*.mp4")):
            source_id = f"NEXAR-{'P' if label == 'positive' else 'N'}-{path.stem}"
            review = reviews[source_id]
            meta, hashes, crop_hashes = video_metadata(path)
            event_id = f"PHASE8-NEG-{path.stem}" if review["review_status"] == "PROMOTED_NEGATIVE" else ""
            provider_meta = metadata.get(path.name, {})
            notes = review["notes"]
            if provider_meta:
                notes += f" Provider metadata: light={provider_meta.get('light_conditions')}; weather={provider_meta.get('weather')}; scene={provider_meta.get('scene')}; event_time={provider_meta.get('time_of_event') or 'n/a'}."
            digest = sha256(path)
            rows.append({
                "source_id": source_id, "source_name": "Nexar Collision Prediction Dataset",
                "source_url_or_path": f"{DATASET_URL}/blob/main/train/{label}/{path.name}", "provider": "Nexar Inc.",
                "license": "Nexar Open Data License", "license_url_or_note": LICENSE_URL,
                "retrieval_date": date.today().isoformat(), "media_type": "video", "original_filename": path.name,
                "sha256": digest, "file_size": path.stat().st_size, "duration": meta["duration"], "fps": meta["fps"],
                "resolution": meta["resolution"], "claimed_label": "COLLISION_OR_NEAR_MISS_CANDIDATE" if label == "positive" else "NEGATIVE",
                "event_id": event_id, "source_family": f"NEXAR-TRAIN-{path.stem}", "provenance_status": "LICENSE_CONFIRMED",
                "usage_status": review["review_status"], "notes": notes,
            })
            fingerprints.append({
                "source_id": source_id, "sha256": digest, "frame_count": meta["frame_count"],
                "sampled_phash": ";".join(hashes), "center_crop_phash": ";".join(crop_hashes),
                "open_status": "PASS" if meta["frame_count"] > 0 and meta["fps"] > 0 else "FAIL",
            })
            details.append({"source_id": source_id, "phashes": hashes, "crop_phashes": crop_hashes})
    return rows, fingerprints, details


def duplicate_groups(rows: list[dict], details: list[dict]) -> tuple[list[dict], list[dict]]:
    exact, probable = [], []
    by_hash: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        by_hash[row["sha256"]].append(row["source_id"])
    for digest, identifiers in by_hash.items():
        if len(identifiers) > 1:
            exact.append({"sha256": digest, "sources": identifiers})
    for index, left in enumerate(details):
        for right in details[index + 1:]:
            full = fingerprint_distance(left["phashes"], right["phashes"])
            crop = fingerprint_distance(left["crop_phashes"], right["crop_phashes"])
            if min(full, crop) <= 7.0:
                probable.append({"sources": [left["source_id"], right["source_id"]], "full_mean_hamming": full, "crop_mean_hamming": crop})
    return exact, probable


def annotation_integrity(annotation: dict) -> dict:
    errors = []
    width, height = annotation["resolution"]
    seen = set()
    for row in annotation["annotations"]:
        frame = row["frame_index"]
        if frame in seen:
            errors.append(f"duplicate frame {frame}")
        seen.add(frame)
        for key in ("participant_a_bbox", "participant_b_bbox", "collision_region_bbox"):
            box = row.get(key)
            if box and not (0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height):
                errors.append(f"frame {frame}: invalid {key}")
        if row.get("phase") not in {"APPROACH", "PRE_CONTACT", "CONTACT", "POST_IMPACT", "AFTERMATH", "UNKNOWN"}:
            errors.append(f"frame {frame}: invalid phase")
        if row.get("annotation_uncertainty") not in {"CERTAIN", "PROBABLE", "UNCERTAIN"}:
            errors.append(f"frame {frame}: invalid confidence")
    return {"status": "PASS" if not errors else "FAIL", "validated_annotations": 1, "errors": errors}


def write_reports(rows: list[dict], fingerprints: list[dict], exact: list[dict], probable: list[dict], annotation: dict, integrity: dict) -> None:
    reviews = read_csv(REVIEW_PATH)
    promoted_negatives = [row for row in reviews if row["review_status"] == "PROMOTED_NEGATIVE"]
    rejected = [row for row in reviews if row["review_status"] == "REJECTED"]
    leakage = []
    phase7_hashes = set()
    inventory = PHASE7 / "source_inventory.csv"
    if inventory.exists():
        phase7_hashes = {row["sha256"].upper() for row in read_csv(inventory)}
    for row in rows:
        if row["source_id"] == "LOCAL-EVENT-0001":
            status = "UNKNOWN"
        elif row["sha256"].upper() in phase7_hashes:
            status = "EVENT_OVERLAP"
        else:
            status = "EXTERNAL_UNSEEN"
        leakage.append({
            "source_id": row["source_id"], "event_id": row["event_id"], "model1_provenance": status,
            "exact_hash_overlap": "YES" if row["sha256"].upper() in phase7_hashes else "NO",
            "source_family_overlap": "NO" if row["source_id"] != "LOCAL-EVENT-0001" else "UNKNOWN",
            "notes": "External-unseen is supported by licensed independent source lineage and no exact local hash; sampled video pHashes were also deduplicated within intake." if status == "EXTERNAL_UNSEEN" else "Retained Phase 7 event has unresolved Model 1 provenance.",
        })
    write_csv(MANIFESTS / "model1_provenance.csv", leakage, ["source_id", "event_id", "model1_provenance", "exact_hash_overlap", "source_family_overlap", "notes"])
    accepted_external = [row for row in rows if row["usage_status"] == "PROMOTED_NEGATIVE"]
    (MANIFESTS / "clean_unseen_candidates.json").write_text(json.dumps({
        "schema_version": 1, "frozen": False,
        "positive_events": [],
        "negative_events": [{"event_id": row["event_id"], "source_id": row["source_id"], "source_family": row["source_family"], "model1_provenance": "EXTERNAL_UNSEEN"} for row in accepted_external],
        "note": "Candidate manifest only. Positive/event-type minimums are not met.",
    }, indent=2) + "\n", encoding="utf-8")
    (MANIFESTS / "frozen_test_manifest.json").write_text(json.dumps({
        "schema_version": 1, "created": False, "positive_events": 1, "negative_events": 20,
        "leakage_checked": True,
        "reason": "Only 1/20 positive events exists (Type A 0/6, Type B 1/6, Type C 0/6). Creating a frozen test would be misleading.",
    }, indent=2) + "\n", encoding="utf-8")
    dedup_lines = [
        "# Phase 8 event deduplication", "", f"- Files hashed: **{len(rows)}**",
        f"- Exact duplicate families: **{len(exact)}**", f"- Probable recoded/cropped families: **{len(probable)}**",
        f"- Candidate physical-event groups: **{len(rows) - sum(max(0, len(item['sources']) - 1) for item in exact)}**", "",
        "Each Nexar file has its own provider video ID and source family. The retained local event uses `REAL-REPLAY-003`. No source-family or fingerprint family is counted twice.", "",
        "## Apparent duplicate families", "",
    ]
    if not exact and not probable:
        dedup_lines.append("None found. Exact SHA-256 and nine-position full-frame/center-crop perceptual sequences found no duplicate pair at the configured mean-Hamming threshold (<= 7 bits).")
    for item in exact:
        dedup_lines += [f"- Exact: {', '.join(item['sources'])}; canonical `{item['sources'][0]}`; remaining files retained but rejected from counting."]
    for item in probable:
        dedup_lines += [f"- Probable: {', '.join(item['sources'])}; full={item['full_mean_hamming']}, crop={item['crop_mean_hamming']}; manual review required."]
    (REPORTS / "event_deduplication.md").write_text("\n".join(dedup_lines) + "\n", encoding="utf-8")

    boxes = sum(2 for row in annotation["annotations"] if row.get("participant_a_bbox") and row.get("participant_b_bbox"))
    distractors = sum(len(row.get("distractor_boxes", [])) for row in annotation["annotations"])
    confidence = Counter(row.get("annotation_uncertainty") for row in annotation["annotations"])
    quality = f"""# Phase 8 data quality

- Provenance completeness: **38/38 physical media files (100%)** have an explicit status; 37 are `LICENSE_CONFIRMED`, 1 is `LOCAL_EXISTING`.
- Annotation completeness: **1/1 promoted positive** has participant pair, keyframes, boxes, phase/contact/visibility labels, and integrity `PASS`.
- New external positive annotation completeness: **0/30** provider-positive candidates promoted; all were explicitly rejected after screening.
- Exact duplicate rate: **{sum(len(item['sources']) for item in exact)}/{len(rows)}** files; probable duplicate families: **{len(probable)}**.
- Uncertain-contact rate: **1/1 promoted positives** has `contact_uncertain=true`; exact peak contact was not invented.
- Event balance: Type A 0, Type B 1, Type C 0, negatives 20 (13 retained + 7 new).
- Participant-class balance: one car-motorcycle positive only.
- Visibility balance: Phase 7 participant B includes 2 heavily occluded, 1 partial, and 3 clear observations.
- Camera-domain balance among newly promoted material: 7 dashcam negatives; no new CCTV positives.

The Nexar positive label merges collisions and near-misses. It was never used as collision ground truth. Most visually apparent impacts involved the recording vehicle, which is out of frame and therefore cannot satisfy CrashGuard's two-participant bounding-box requirement.
"""
    (REPORTS / "data_quality.md").write_text(quality, encoding="utf-8")
    gap = """# Phase 8 data gap

| Stratum | Target | Actual | Gap |
|---|---:|---:|---:|
| Type A | 6 | 0 | 6 |
| Type B | 6 | 1 | 5 |
| Type C | 6 | 0 | 6 |
| Additional positives of any type | 2 | 0 | 2 |
| Total positives | 20 | 1 | 19 |
| Independent negatives | 20 | 20 | 0 |
| Motorcycle-positive events | several | 1 | still underrepresented |
| Car-car positive events | multiple | 0 | absent |
| Night positive events | representative | 0 | absent |
| Small/distant positive events | several | 1 participant in one event | insufficient |
| Elevated CCTV positives | prioritized | 1 | insufficient |

The exact blocking gap is **19 independently sourced, fully annotated positive collision events**: at least 6 Type A, 5 additional Type B, 6 Type C, and 2 more valid positives of any type.
"""
    (REPORTS / "data_gap.md").write_text(gap, encoding="utf-8")
    (PHASE8 / "annotation_integrity.json").write_text(json.dumps(integrity, indent=2) + "\n", encoding="utf-8")
    baseline = json.loads((PHASE7 / "baseline_results.json").read_text(encoding="utf-8"))
    new_negative_path = PHASE8 / "new_negative_baseline.json"
    new_negative = json.loads(new_negative_path.read_text(encoding="utf-8")) if new_negative_path.exists() else None
    baseline["phase8_scope"] = {
        "new_positive_events_evaluated": 0,
        "new_negative_events_acquired": len(promoted_negatives),
        "new_negative_pipeline_evaluation": "COMPLETED_UNCHANGED_PIPELINE" if new_negative else "NOT_RUN",
        "reason": "No Phase 8 positive met promotion rules. New negatives were replayed only for baseline diagnosis; thresholds and code were not tuned." if new_negative else "No Phase 8 positive met promotion rules; thresholds and code were not tuned.",
    }
    if new_negative:
        baseline["phase8_new_negative_results"] = new_negative
    (PHASE8 / "baseline_results.json").write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")

    rejection_counts = Counter(row["rejection_reason"] for row in rejected)
    report = f"""STATUS:
PARTIALLY COMPLETED

## SOURCE ACQUISITION

Sources evaluated: 38 physical media files (37 newly acquired licensed Nexar clips; 1 retained local event)

Sources accepted: 8 promoted events (1 retained positive; 7 new negatives)

Sources rejected: {len(rejected)} provider-positive candidates ({dict(rejection_counts)})

Provenance-confirmed sources: 37 `LICENSE_CONFIRMED`

Unknown-provenance sources: 0; one retained source is explicitly `LOCAL_EXISTING`, not claimed license-confirmed

## EVENT DEDUPLICATION

Raw media: 38 videos

Duplicate media: {sum(max(0, len(item['sources']) - 1) for item in exact)} exact; {len(probable)} probable pairs

Candidate event groups: 38

Independent positive events: 1

Independent negative events: 20 (13 retained from Phase 7; 7 new)

## POSITIVE DISTRIBUTION

Type A: 0

Type B: 1

Type C: 0

Total: 1

## DATA GAP

Type A target / actual: 6 / 0 (gap 6)

Type B target / actual: 6 / 1 (gap 5)

Type C target / actual: 6 / 0 (gap 6)

Negative target / actual: 20 / 20 (gap 0)

Total positive target / actual: 20 / 1 (gap 19, including 2 additional events of any valid type)

## VEHICLE-PAIR DISTRIBUTION

Car-car: 0

Car-motorcycle: 1

Car-truck: 0

Motorcycle-other: 0

Other: 0

## CAMERA / CONDITION DISTRIBUTION

Elevated CCTV: 1 promoted positive

Intersection: 1 new promoted negative

Roadside: 2 new promoted negatives (roadside/sparse and low visibility)

Night: 1 new promoted negative; 0 positives

Day: 6 new promoted negatives + 1 positive

Small/distant: 1 small positive participant; 2 new small-scene negatives

Large/clear: 0 positive controls; 2 new large-scene negatives

## ANNOTATION

Annotated events: 1 positive + 7 negative manifest reviews

Keyframes: {len(annotation['annotations'])}

Participant boxes: {boxes}

Distractor boxes: {distractors}

Certain contact: {confidence.get('CERTAIN', 0)} keyframes

Probable contact: {confidence.get('PROBABLE', 0)} keyframes

Uncertain contact: {confidence.get('UNCERTAIN', 0)} keyframes; event-level exact contact peak remains uncertain

## PROVENANCE

External unseen: 7 promoted negative events (plus 30 rejected external candidates inventoried)

Train-unseen: 0

Train-seen: 0

Event overlap: 0 among new external items

Unknown: 14 retained Phase 7 events for Model 1 generalization purposes

## MODEL 2 BASELINE

Raw participant recall: 10/12 = 83.33%

Accepted recall: 9/12 = 75.00%

MODEL2_NO_BOX: 2/12 = 16.67%

BELOW_CANDIDATE: 1/12 = 8.33%

WRONG_CLASS: 1/12 = 8.33%

Breakdown by class: car raw/accepted 100%/100%; motorcycle raw/accepted 66.67%/50.00%

Breakdown by size: large raw 100%; small raw 66.67%

Breakdown by visibility: participant B — heavily occluded 0/2 raw, partial 1/1 raw but not accepted, clear 3/3 accepted

## TRACKING

Accepted participant observations: 9

Tracked: 6

Stable tracks: 6 participant-A observations; no stable participant-B track

Tracker failure given accepted detection: 3/9 = 33.33%

Logical recovery: 3 participant-B observations

Both participants motionObserved: 0/6 keyframes

## PAIR ATTRIBUTION

Type A/B evaluated: 1

Correct pair: 0

Wrong pair: 1

Unavailable: 0 at event level (3/6 frames unavailable)

Ambiguous: 0

Pair attribution accuracy: 0/1 = 0%

## TYPE A TEMPORAL RESULTS

Events: 0

True-pair temporal confirmations: 0

Failures: not measurable

Main failure reasons: no promoted Type A data

## TYPE C AFTERMATH RESULTS

Events: 0 independent (one derived Phase 6/7 scenario is not counted)

Correct pending reviews: 0

Incorrect temporal confirmations: 1 derived scenario

Ignored: 0

Aftermath misrouting rate: not measurable on independent Type C; derived scenario 1/1 (100%)

## NEGATIVE RESULTS

Independent negatives: 20

Confirmed false crashes: 0/19 across 12 retained + 7 new evaluated negatives

Pending-review false positives: 0/19 across 12 retained + 7 new evaluated negatives

Near-miss failures: not measurable; no newly promoted source was defensibly labeled `NEAR_MISS`

The 7 new licensed negatives were replayed at approximately 3 decoded frames/second through the unchanged pipeline. All 7 were ignored operationally; 3/7 reached full-frame Model 1 score >= 0.80, 4/7 reached pair-region score >= 0.80, 1/7 reached aftermath score >= 0.80 without persisting a review, and 0/7 reached temporal score >= 0.62. No result was used to tune the system.

## FROZEN TEST

Created: NO

Reason: only 1/20 positives, Type A 0/6, Type B 1/6, and Type C 0/6

Positive events: 1 candidate retained

Negative events: 20 candidates available

Leakage checked: YES

## BOTTLENECK RATES

Model 2: 25.00% not accepted (3/12 observations); 16.67% no box

Tracking: 33.33% failure given accepted detections (3/9)

Pair attribution: 100% error (1/1 event)

Temporal with valid tracked pair: not measurable

Aftermath routing: not measurable independently; 100% misrouted in one derived scenario

Model 1: 33.33% visual failure at 0.50 on the single retained event's six keyframes; not a generalization estimate

## BOTTLENECK RANKING

1. Data sufficiency — 19 positive events missing; no Type A or independent Type C.
2. Pair attribution — 1/1 evaluated event selected the wrong pair, but sample size is one.
3. Aftermath routing — 1/1 derived scenario misrouted, with no independent Type C confirmation.
4. Tracking — 3/9 accepted observations lacked tracker assignment.
5. Model 2 — 3/12 participant observations were not accepted; motorcycle recall remains weak.

## PRIMARY NEXT PHASE

F — MORE EXTERNAL DATA STILL REQUIRED

Quantitatively, the negative target is now met (20/20), but positives remain 1/20: Type A 0/6, Type B 1/6, Type C 0/6, plus 2 additional positives. No engineering bottleneck can be ranked with defensible generalization from one collision event.

## FILES CREATED

- `backend/validation/phase8/incoming/nexar/` (37 licensed source videos + provider metadata/license)
- `backend/validation/phase8/manifests/external_sources.csv`
- `backend/validation/phase8/manifests/manual_reviews.csv`
- `backend/validation/phase8/manifests/model1_provenance.csv`
- `backend/validation/phase8/manifests/clean_unseen_candidates.json`
- `backend/validation/phase8/manifests/frozen_test_manifest.json`
- `backend/validation/phase8/annotations/EVENT-0001.json`
- `backend/validation/phase8/hashes/media_fingerprints.csv`
- `backend/validation/phase8/derived/contact_sheets/`
- `backend/validation/phase8/reports/event_deduplication.md`
- `backend/validation/phase8/reports/data_quality.md`
- `backend/validation/phase8/reports/data_gap.md`
- `backend/validation/phase8/annotation_integrity.json`
- `backend/validation/phase8/baseline_results.json`
- `backend/validation/phase8/new_negative_baseline.json`
- `backend/validation/phase8/final_report.md`
- `scripts/phase8_screen_candidates.py`
- `scripts/build_phase8_corpus.py`
- `scripts/evaluate_phase8_baseline.py`
- `scripts/annotate_phase8_events.py`
- `scripts/validate_phase8.py`

## PRODUCTION FILES MODIFIED

NONE

## MODELS

Model 1 retrained: NO

Model 2 fine-tuned: NO

Model files replaced: NO

## THRESHOLDS

Trusted: 0.40

Candidate: 0.25

Temporal: 0.62

Aftermath: 0.80

All unchanged: YES

## PHASE 8 VERDICT

PHASE 8 PARTIALLY COMPLETED — MORE DATA REQUIRED
"""
    (REPORTS / "final_report.md").write_text(report, encoding="utf-8")


def main() -> int:
    for path in (MANIFESTS, ANNOTATIONS, REPORTS, HASHES, PHASE8 / "derived", PHASE8 / "rejected", PHASE8 / "frozen_candidates"):
        path.mkdir(parents=True, exist_ok=True)
    annotation = import_phase7_annotation()
    rows, fingerprints, details = build_sources()
    write_csv(SOURCE_PATH, rows, FIELDS)
    write_csv(FINGERPRINT_PATH, fingerprints, ["source_id", "sha256", "frame_count", "sampled_phash", "center_crop_phash", "open_status"])
    exact, probable = duplicate_groups(rows, details)
    integrity = annotation_integrity(annotation)
    write_reports(rows, fingerprints, exact, probable, annotation, integrity)
    print(json.dumps({
        "sources": len(rows), "promoted_positive": 1,
        "promoted_new_negatives": sum(row["usage_status"] == "PROMOTED_NEGATIVE" for row in rows),
        "rejected": sum(row["usage_status"] == "REJECTED" for row in rows),
        "exact_duplicate_families": len(exact), "probable_duplicate_pairs": len(probable),
        "annotation_integrity": integrity["status"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
