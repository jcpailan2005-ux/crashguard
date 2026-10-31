"""Build the auditable Phase 8B screening ledger and data-gap reports.

This development-only script never changes runtime code, thresholds, weights,
or training data.  Human contact-sheet decisions below are authoritative;
model scores in candidate_prescreen.csv remain diagnostic assistance only.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
P8B = ROOT / "backend" / "validation" / "phase8b"
P8 = ROOT / "backend" / "validation" / "phase8"
PRESCREEN = P8B / "candidate_prescreen.csv"
MANIFESTS = P8B / "manifests"
REPORTS = P8B / "reports"

PILOT = {
    "CADP-EqzYBBym7ro", "CADP-i6LwdZ9ZsAE", "CADP-NgN5FWA3yGs",
    "CADP-uEbscoDZhDM", "CADP-YSGhwU9XxuY", "CADP-3ItkjSXfP6k",
    "CADP-LuP-qXCZ-eY", "CADP-u6mIIiRku04", "CADP-DrTDtkeGv8Q",
    "CADP-0IPAgFHyRVI",
}

# Human decisions from the generated nine-frame contact sheets. Promotion only
# means the clip is suitable for detailed frame annotation; it is not accepted
# ground truth and is not eligible for baseline evaluation yet.
PROMOTE = {
    "CADP-0IPAgFHyRVI": ("TYPE_A", "Clear fixed-camera multi-vehicle impact and post-impact motion."),
    "CADP-3ItkjSXfP6k": ("TYPE_A", "Fixed intersection view; two collision participants remain visible."),
    "CADP-3p_-1RjvCmw": ("TYPE_A", "Fixed night intersection; approach and collision sequence retained."),
    "CADP-Anm6ftbjNDM": ("TYPE_A", "Fixed night roadway; candidate impact sequence, annotate with low-light caution."),
    "CADP-DrTDtkeGv8Q": ("TYPE_B", "Fixed wet-road view; car and smaller road user are visible through impact."),
    "CADP-EqzYBBym7ro": ("TYPE_A", "Fixed intersection with visible cross-traffic impact and aftermath."),
    "CADP-i6LwdZ9ZsAE": ("TYPE_B", "Fixed elevated view; car and motorcycle/rider interaction is visible."),
    "CADP-LuP-qXCZ-eY": ("TYPE_A", "Fixed snowy intersection; two close collision vehicles are boxable."),
    "CADP-MxiC2UdOzE8": ("TYPE_A", "Fixed highway view with two vehicles in a visible impact sequence."),
    "CADP-niDlcEKeSWk": ("TYPE_A", "Fixed intersection; both crossing vehicles remain visible around contact."),
    "CADP-PomCzaH84GQ": ("TYPE_A", "Fixed intersection event retained as the canonical member of a duplicate cluster."),
    "CADP-QIeJH4MckAA": ("TYPE_C", "High-confidence stationary aftermath candidate with multiple participants visible."),
    "CADP-Szh9Q0RxLKk": ("TYPE_A", "Fixed overhead junction; approach and collision participants are visible."),
    "CADP-tFqV8ac9nLY": ("TYPE_B", "Fixed elevated view; vehicle and small road user are visible around impact."),
    "CADP-uEbscoDZhDM": ("TYPE_B", "Fixed street view; bus and smaller participant remain visible near contact."),
    "CADP-Vn8iNKHoUVE": ("TYPE_A", "Fixed intersection event retained as canonical duplicate-cluster member."),
    "CADP-WTy69_at39U": ("TYPE_B", "Fixed elevated traffic view; circled collision pair remains identifiable."),
    "CADP-YSGhwU9XxuY": ("TYPE_A", "Fixed intersection; truck and car collision is clearly visible."),
    "CADP-YtKuNIcpvlY": ("TYPE_A", "Fixed divided-road view with visible two-vehicle impact sequence."),
    "CADP-ZCQcKnFSJvg": ("TYPE_A", "Fixed junction view; collision participants are visible despite distance."),
    "CADP-zVzXEht1aME": ("TYPE_A", "Fixed night intersection with a reviewable two-vehicle sequence."),
}

DUPLICATES = {
    "CADP-u6mIIiRku04": ("CADP-0IPAgFHyRVI", "Same camera, vehicles, and collision timeline."),
    "CADP-T2PeqBcJn3E": ("CADP-PomCzaH84GQ", "Same Locust/Westfield event."),
    "CADP-SrbylylFcsg": ("CADP-PomCzaH84GQ", "Same Locust/Westfield event."),
    "CADP-3QsW1X6RE4U": ("CADP-Vn8iNKHoUVE", "Same camera, traffic, replay, and collision timeline."),
    "CADP-zXiwhl26DqI": ("CADP-08PPPXtzN4A", "Same elevated highway source/event sequence."),
}

REJECTS = {
    "CADP-08PPPXtzN4A": ("REJECT_SINGLE_VEHICLE", "Only one crash participant is meaningfully boxable."),
    "CADP-3VTdPoH5eGE": ("REJECT_INSUFFICIENT_CONTEXT", "Edited montage/zoom interrupts one continuous fixed-camera event."),
    "CADP-5dwPSzpV9pw": ("REJECT_INSUFFICIENT_CONTEXT", "Compilation contains scene changes and unrelated aftermath shots."),
    "CADP-eDzmET7gLQg": ("REJECT_INSUFFICIENT_CONTEXT", "Multiple unrelated crash clips are concatenated."),
    "CADP-isKhHc3BgvE": ("REJECT_SINGLE_VEHICLE", "Rollover aftermath is visible but a second collision participant is not."),
    "CADP-j4uIYeAFf1M": ("REJECT_NOT_CCTV", "News package mixes surveillance, presenter, and ground-level footage."),
    "CADP-JtGyMlFpszk": ("REJECT_NOT_CCTV", "Broadcast edit rather than a continuous fixed-CCTV sequence."),
    "CADP-knn6D0n9mTk": ("REJECT_TOO_DISTANT", "Very low-resolution night view cannot support reliable two-participant boxes."),
    "CADP-Kw0HCsAp83U": ("REJECT_INSUFFICIENT_CONTEXT", "Compilation changes viewpoint and includes close-up aftermath footage."),
    "CADP-NgN5FWA3yGs": ("REJECT_TOO_DISTANT", "Possible contact is too small/occluded for reliable participant annotation."),
    "CADP-NwiZ3q-702M": ("REJECT_TOO_DISTANT", "Provider highlight is distant and contact is not visually resolvable."),
    "CADP-Ojgdy8b_wf4": ("REJECT_NOT_CCTV", "Rail-car interior event is outside road-traffic CCTV scope."),
    "CADP-oU0PI4QqNEw": ("REJECT_NOT_CCTV", "Rail-car interior event is outside road-traffic CCTV scope."),
    "CADP-pSVdQwMwhK8": ("REJECT_NO_VISIBLE_CONTACT", "Traffic is visible but the collision pair/contact cannot be established."),
    "CADP-t3l79qoMdoo": ("REJECT_NOT_CCTV", "Rail-car interior news clip is outside road-traffic CCTV scope."),
    "CADP-t5uupfbJgIs": ("REJECT_INSUFFICIENT_CONTEXT", "Portrait inserts and scene changes prevent a continuous event annotation."),
    "CADP-VNJiQoDKqAY": ("REJECT_INSUFFICIENT_CONTEXT", "Edited highlights and overlays prevent reliable event boundaries."),
    "CADP-wbAHPwlxdJ4": ("REJECT_INSUFFICIENT_CONTEXT", "Rotated/edited compilation does not preserve one stable camera sequence."),
    "CADP-WUDQ6wSbMOw": ("REJECT_INSUFFICIENT_CONTEXT", "Multiple CCTV segments are concatenated."),
    "CADP-Xx33rnnqyKk": ("REJECT_SINGLE_VEHICLE", "Aftermath centers on one vehicle; collision partner/contact is unavailable."),
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> int:
    MANIFESTS.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    with PRESCREEN.open(encoding="utf-8", newline="") as source:
        candidates = list(csv.DictReader(source))

    reviews = []
    for row in candidates:
        event = row["event_group_id"]
        if row["source"] == "carcrash1cctv":
            state, reason, proposed, duplicate_of = (
                "REJECT_DUPLICATE",
                "Exact source frames occur in the active classifier corpus (TRAIN_SEEN); local copy has no license file.",
                "UNASSIGNED",
                "MODEL1_TRAINING_CORPUS",
            )
        elif event in PROMOTE:
            proposed, reason = PROMOTE[event]
            state, duplicate_of = "PROMOTE_FOR_ANNOTATION", ""
        elif event in DUPLICATES:
            duplicate_of, reason = DUPLICATES[event]
            state, proposed = "REJECT_DUPLICATE", "UNASSIGNED"
        else:
            state, reason = REJECTS[event]
            proposed, duplicate_of = "UNASSIGNED", ""
        reviews.append({
            "candidate_id": event,
            "source": row["source"],
            "source_family": row["source_family"],
            "provenance": row["provenance"],
            "screening_state": state,
            "proposed_type": proposed,
            "duplicate_of": duplicate_of,
            "pilot_member": "YES" if event in PILOT else "NO",
            "human_review_basis": "NINE_FRAME_CONTACT_SHEET",
            "model_ground_truth": "NO",
            "reason": reason,
            "contact_sheet": row["contact_sheet"],
        })

    fields = list(reviews[0])
    with (MANIFESTS / "manual_screening.csv").open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        writer.writerows(reviews)

    assets = []
    for path in sorted((P8B / "incoming" / "cadp_pilot").glob("*.mp4")):
        assets.append({
            "source_id": f"CADP-{path.stem}",
            "filename": path.name,
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path),
            "official_project_url": "https://ankitshah009.github.io/accident_forecasting_traffic_camera.html",
            "official_drive_folder_id": "1b_-BsRsl6OQS1t9r2VlO1i71jzK3f4rQ",
            "license_status": "RESEARCH_USE_CONFIRMED",
        })
    with (MANIFESTS / "source_assets.csv").open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(assets[0]))
        writer.writeheader()
        writer.writerows(assets)

    counts = Counter(row["screening_state"] for row in reviews)
    promoted_types = Counter(row["proposed_type"] for row in reviews if row["screening_state"] == "PROMOTE_FOR_ANNOTATION")
    pilot_rows = [row for row in reviews if row["pilot_member"] == "YES"]
    pilot_promoted = sum(row["screening_state"] == "PROMOTE_FOR_ANNOTATION" for row in pilot_rows)
    weight_hashes = {
        "backend/best.pt": file_sha256(ROOT / "backend" / "best.pt"),
        "backend/models/crash_classifier.pt": file_sha256(ROOT / "backend" / "models" / "crash_classifier.pt"),
    }
    source_metadata_hashes = {
        name: file_sha256(P8B / "source_metadata" / name)
        for name in ("cadp_readme.txt", "cadp_annotations.json", "cadp_durations.txt")
    }
    manifest = {
        "schema_version": 1,
        "phase": "8B",
        "status": "PHASE 8B PARTIALLY COMPLETED — POSITIVE DATA GAP REMAINS",
        "scope": "TARGETED_FIXED_CCTV_POSITIVE_COLLISION_ACQUISITION",
        "runtime_modified": False,
        "training_or_finetuning_performed": False,
        "models_used_as_ground_truth": False,
        "frozen_configuration": {
            "trusted_detection_threshold": 0.40,
            "candidate_detection_threshold": 0.25,
            "temporal_trigger_threshold": 0.62,
            "aftermath_threshold": 0.80,
            "model2_imgsz": 640,
            "weight_sha256": weight_hashes,
        },
        "local_search": {
            "c1_reconstructed_sequences": 29,
            "c1_frames": 897,
            "c1_result": "REJECTED_TRAIN_SEEN_AND_LICENSE_UNKNOWN",
            "c2_static_positive_images": 6191,
            "c2_result": "NOT_TEMPORALLY_RECONSTRUCTABLE_SHUFFLED_STANDALONE_IMAGES",
            "phase8_nexar_positive_candidates_previously_screened": 30,
            "phase8_nexar_promoted_positives": 0,
        },
        "cadp_acquisition": {
            "clips_downloaded": len(assets),
            "bytes_downloaded": sum(row["bytes"] for row in assets),
            "pilot_clips": len(pilot_rows),
            "pilot_promoted_for_annotation": pilot_promoted,
            "pilot_suitability_percent": round(100 * pilot_promoted / len(pilot_rows), 1),
            "bounded_expansion_attempted": 30,
            "bounded_expansion_downloaded": max(0, len(assets) - 20),
            "inaccessible_asset": "o8mh163bTfs.mp4",
            "inaccessible_asset_action": "STOPPED_WITHOUT_BYPASS",
            "stop_reason": "One later public Drive asset was inaccessible; bounded candidate target was already sufficient for screening.",
            "source_metadata_sha256": source_metadata_hashes,
        },
        "screening": {
            "all_candidate_rows": len(reviews),
            "state_counts": dict(sorted(counts.items())),
            "promoted_for_annotation": sum(promoted_types.values()),
            "promoted_type_queue": dict(sorted(promoted_types.items())),
            "fully_annotated_new_events": 0,
            "new_events_run_through_pipeline": 0,
        },
        "corpus": {
            "accepted_positive_events": 1,
            "accepted_negative_events": 20,
            "accepted_type_a": 0,
            "accepted_type_b": 1,
            "accepted_type_c": 0,
            "positive_gap": 19,
            "type_a_gap": 6,
            "type_b_gap": 5,
            "type_c_gap": 6,
            "additional_any_type_gap": 2,
            "freeze_status": "NOT_FROZEN",
        },
        "decision": "F",
        "decision_reason": "No new clip is accepted until six-or-more human-verified participant-pair keyframes and annotation integrity checks pass; therefore baseline evaluation was correctly not run.",
    }
    (P8B / "validation_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    (REPORTS / "source_suitability.md").write_text(f"""# Phase 8B Source Suitability

| Source | Availability/provenance | Result |
|---|---|---|
| Local `carcrash1cctv` | 29 reconstructable filename groups; no local license; exact frames occur in Model 1 training corpus | Rejected from unseen evaluation |
| Local `carcrash2cctv` | 6,191 positive stills; adjacent numeric files are shuffled scenes | Static reference only; not a temporal corpus |
| Phase 8 Nexar | 30 provider-positive dashcam candidates already screened | 0 fixed-CCTV positives promoted |
| CADP official preview release | Research/noncommercial use confirmed in saved official README | {len(assets)} clips acquired; {sum(promoted_types.values())} queued for annotation |
| ACCIDENT/CVPR | Kaggle access and competition restrictions; no authenticated local access | Not acquired or bypassed |
| IITH Accident | Author/request route; no directly usable local download established | Manual request required |
| TU-DAT | Publication located; usable official media endpoint not established | Not acquired |
| Hugging Face CC0 traffic accident stills | Static object-detection images, weak event independence | Not used for temporal positives |

The 10-clip CADP pilot produced {pilot_promoted}/10 annotation candidates ({100 * pilot_promoted / 10:.0f}%), exceeding the 30% continuation gate. Expansion was bounded. Provider labels and both model outputs were treated as search aids, never truth.
""", encoding="utf-8")

    (REPORTS / "event_deduplication.md").write_text("""# Phase 8B Event Deduplication

Visual sequence review and contact-sheet perceptual similarity found these same-event clusters:

- `0IPAgFHyRVI` / `u6mIIiRku04` → retain `0IPAgFHyRVI`.
- `PomCzaH84GQ` / `T2PeqBcJn3E` / `SrbylylFcsg` → retain `PomCzaH84GQ`.
- `Vn8iNKHoUVE` / `3QsW1X6RE4U` → retain `Vn8iNKHoUVE`.
- `08PPPXtzN4A` / `zXiwhl26DqI` → both rejected; never count independently.

All 29 C1 sequence groups are also excluded as `TRAIN_SEEN`; source-family independence is not claimed from filenames alone. Exact SHA-256 hashes for acquired CADP assets are in `manifests/source_assets.csv`.
""", encoding="utf-8")

    (P8B / "MANUAL_DATA_REQUEST.md").write_text("""# Manual Data Request — Phase 8B Positive Gap

## Exact remaining need

The accepted corpus remains at **1/20 positives** and **20/20 negatives**. Required: **19 independently sourced, fully annotated positive events**—at least **6 Type A**, **5 additional Type B**, **6 Type C**, plus **2 of any valid type**.

## Minimum package per event

- One continuous, fixed/elevated CCTV clip with no compilation cuts or replay counted twice.
- Source URL/provider, license or permission evidence, stable source-family ID, and SHA-256.
- Visible pre-contact approach and post-impact motion for Type A/B; a stable, unmistakable aftermath for Type C.
- Both collision participants meaningfully visible and boxable.
- Native resolution and frame rate; avoid social-media recompression when an original is available.
- Human annotations on at least 6 representative frames: participant A/B boxes, phase, contact status, visibility/occlusion, collision region, distractors, and confidence.
- Separate camera/location/time identifiers so same-event clips and reposts can be deduplicated.

## Acquisition priorities

1. Type A: clear two-car fixed-intersection impacts (6 accepted events needed).
2. Type C: stationary multi-vehicle aftermath with both participants visible (6 needed).
3. Type B: vehicle–motorcycle or heavily occluded second participant (5 additional needed).

## Current annotation queue

Phase 8B has **21 CADP clips promoted for detailed annotation**, but none is accepted yet. Annotate these before acquiring more. Reject any clip if frame-level review reveals a cut, replay-only evidence, no visible contact, or an unboxable second participant.
""", encoding="utf-8")

    (P8B / "final_report.md").write_text(f"""# Phase 8B Final Report

## Status

**PHASE 8B PARTIALLY COMPLETED — POSITIVE DATA GAP REMAINS**

## What was searched

Local C1/C2 datasets, the existing classifier corpus, prior Phase 8 Nexar candidates, and authoritative external fixed-camera sources were checked. C1 yielded 29 temporal filename groups but is training-seen and license-unclear. C2 contains shuffled standalone stills, so numeric adjacency is not a defensible sequence. CADP was the only immediately usable official fixed-camera source with saved research-use terms.

## Candidate counts

- CADP clips acquired and hashed: **{len(assets)}**
- Local C1 sequence candidates explicitly dispositioned: **29**
- Total screening ledger rows: **{len(reviews)}**
- CADP clips promoted only for detailed annotation: **{sum(promoted_types.values())}** ({dict(sorted(promoted_types.items()))})
- New fully annotated/accepted events: **0**
- New events evaluated through the unchanged pipeline: **0**

## Corpus balance and gap

Accepted corpus is unchanged: Type A **0/6**, Type B **1/6**, Type C **0/6**, all positives **1/20**, negatives **20/20**. Exact positive gap: **19** events (6 Type A, 5 additional Type B, 6 Type C, and 2 additional positives of any valid type). The corpus is **not frozen**.

## Pipeline findings

No new pipeline finding is claimed. Running unannotated candidates would turn model output into circular ground truth, so the unchanged baseline was intentionally not run. Thresholds, tracking, temporal logic, runtime code, Model 1, and Model 2 remained unchanged; hashes are recorded in `validation_manifest.json`.

## Ranked current blockers

1. Frame-level human participant-pair annotation for the 21 promoted CADP candidates.
2. Type C scarcity: only one current queue candidate is a plausible aftermath case.
3. Deduplication/source-family verification for edited or reposted CCTV media.
4. Resolution/occlusion quality for motorcycle and distant-intersection events.

## Recommendation

**F — corpus not frozen because data remains insufficient.** Complete six-frame-or-greater human annotations and integrity validation for the current CADP queue first. Only accepted events may enter the unchanged Phase 8 baseline.
""", encoding="utf-8")

    print(json.dumps({"reviews": len(reviews), "assets": len(assets), "states": counts, "promoted_types": promoted_types}, default=dict, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
