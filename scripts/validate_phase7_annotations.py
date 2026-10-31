"""Validate every Phase 7 event annotation without changing source media."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from build_phase7_dataset import PHASE7, validate_annotation


def main() -> int:
    annotation_dir = PHASE7 / "annotations"
    rows = []
    event_ids = []
    source_hashes = []
    for path in sorted(annotation_dir.glob("*.json")):
        event = json.loads(path.read_text(encoding="utf-8"))
        result = validate_annotation(event)
        result["path"] = str(path)
        rows.append(result)
        event_ids.append(event.get("event_id"))
        source_hashes.append(event.get("source_sha256"))
    duplicate_ids = sorted(key for key, count in Counter(event_ids).items() if count > 1)
    duplicate_hashes = sorted(key for key, count in Counter(source_hashes).items() if count > 1)
    passed = bool(rows) and all(row["passed"] for row in rows) and not duplicate_ids
    payload = {
        "annotation_results": rows,
        "duplicate_event_ids": duplicate_ids,
        "duplicate_source_hashes": duplicate_hashes,
        "source_hash_check": "PASS" if all(not any("hash" in error for error in row["errors"]) for row in rows) else "FAIL",
        "annotation_validation": "PASS" if all(row["passed"] for row in rows) else "FAIL",
        "event_isolation": "PASS" if not duplicate_ids else "FAIL",
        "overall": "PASS" if passed else "FAIL",
    }
    output = PHASE7 / "annotation_integrity.json"
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
