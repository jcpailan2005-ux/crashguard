"""Fail-fast validation for Phase 8B acquisition artifacts."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
P8B = ROOT / "backend" / "validation" / "phase8b"
ALLOWED = {
    "PROMOTE_FOR_ANNOTATION", "REJECT_NOT_CCTV", "REJECT_NO_VISIBLE_CONTACT",
    "REJECT_SINGLE_VEHICLE", "REJECT_TOO_DISTANT", "REJECT_DUPLICATE",
    "REJECT_INSUFFICIENT_CONTEXT", "NEEDS_REVIEW",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest.upper()


def main() -> int:
    manifest = json.loads((P8B / "validation_manifest.json").read_text(encoding="utf-8"))
    with (P8B / "manifests" / "manual_screening.csv").open(encoding="utf-8", newline="") as source:
        reviews = list(csv.DictReader(source))
    with (P8B / "manifests" / "source_assets.csv").open(encoding="utf-8", newline="") as source:
        assets = list(csv.DictReader(source))
    assert len(reviews) == manifest["screening"]["all_candidate_rows"]
    assert all(row["screening_state"] in ALLOWED for row in reviews)
    assert not any(row["screening_state"] == "NEEDS_REVIEW" for row in reviews)
    assert all(row["model_ground_truth"] == "NO" for row in reviews)
    assert len(assets) == manifest["cadp_acquisition"]["clips_downloaded"]
    for row in assets:
        path = P8B / "incoming" / "cadp_pilot" / row["filename"]
        assert path.is_file() and path.stat().st_size == int(row["bytes"])
        assert sha256(path) == row["sha256"]
    weights = manifest["frozen_configuration"]["weight_sha256"]
    assert sha256(ROOT / "backend" / "best.pt") == weights["backend/best.pt"]
    assert sha256(ROOT / "backend" / "models" / "crash_classifier.pt") == weights["backend/models/crash_classifier.pt"]
    for name, expected in manifest["cadp_acquisition"]["source_metadata_sha256"].items():
        assert sha256(P8B / "source_metadata" / name) == expected
    assert manifest["screening"]["fully_annotated_new_events"] == 0
    assert manifest["screening"]["new_events_run_through_pipeline"] == 0
    assert manifest["corpus"]["freeze_status"] == "NOT_FROZEN"
    assert manifest["decision"] == "F"
    print(json.dumps({"status": "PASS", "review_rows": len(reviews), "asset_hashes_verified": len(assets), "weight_hashes_verified": 2}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
