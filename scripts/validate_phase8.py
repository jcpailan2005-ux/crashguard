"""Validate Phase 8 intake artifacts and protected-configuration claims."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PHASE8 = ROOT / "backend" / "validation" / "phase8"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> int:
    errors = []
    required = [
        PHASE8 / "manifests" / "external_sources.csv",
        PHASE8 / "manifests" / "clean_unseen_candidates.json",
        PHASE8 / "manifests" / "frozen_test_manifest.json",
        PHASE8 / "hashes" / "media_fingerprints.csv",
        PHASE8 / "reports" / "event_deduplication.md",
        PHASE8 / "reports" / "data_quality.md",
        PHASE8 / "reports" / "data_gap.md",
        PHASE8 / "reports" / "final_report.md",
        PHASE8 / "baseline_results.json",
        PHASE8 / "annotation_integrity.json",
    ]
    errors.extend(f"missing {path}" for path in required if not path.exists())
    if errors:
        print("\n".join(errors)); return 1
    with (PHASE8 / "manifests" / "external_sources.csv").open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    allowed_provenance = {"LICENSE_CONFIRMED", "RESEARCH_USE_CONFIRMED", "USER_PROVIDED", "LOCAL_EXISTING", "LICENSE_UNKNOWN", "REJECTED_PROVENANCE"}
    seen_hashes, seen_ids = {}, set()
    for row in rows:
        if row["source_id"] in seen_ids: errors.append(f"duplicate source_id {row['source_id']}")
        seen_ids.add(row["source_id"])
        if row["provenance_status"] not in allowed_provenance: errors.append(f"bad provenance {row['source_id']}")
        if not row["sha256"]: errors.append(f"missing hash {row['source_id']}")
        if row["sha256"] in seen_hashes: errors.append(f"unresolved exact duplicate {row['source_id']} and {seen_hashes[row['sha256']]}")
        seen_hashes[row["sha256"]] = row["source_id"]
        local = PHASE8 / "incoming" / "nexar" / ("positive" if "-P-" in row["source_id"] else "negative") / row["original_filename"]
        if row["source_id"].startswith("NEXAR-"):
            if not local.exists(): errors.append(f"missing media {local}")
            elif sha256(local) != row["sha256"]: errors.append(f"hash mismatch {row['source_id']}")
    annotation = json.loads((PHASE8 / "annotations" / "EVENT-0001.json").read_text(encoding="utf-8"))
    if annotation.get("ground_truth_collision_pair") != ["participant_a", "participant_b"]: errors.append("missing ground-truth pair")
    if not annotation.get("analysis_start") or not annotation.get("analysis_end"): errors.append("missing analysis window")
    integrity = json.loads((PHASE8 / "annotation_integrity.json").read_text(encoding="utf-8"))
    if integrity.get("status") != "PASS": errors.append("annotation integrity failed")
    baseline = json.loads((PHASE8 / "baseline_results.json").read_text(encoding="utf-8"))
    thresholds = baseline["baseline_provenance"]["thresholds"]
    if thresholds != {"trusted": 0.4, "candidate": 0.25, "temporal": 0.62, "aftermath": 0.8}: errors.append(f"threshold mismatch {thresholds}")
    frozen = json.loads((PHASE8 / "manifests" / "frozen_test_manifest.json").read_text(encoding="utf-8"))
    if frozen.get("created") is not False: errors.append("frozen set must not be created")
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "sources": len(rows), "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
