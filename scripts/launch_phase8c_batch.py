"""Launch one Phase 8C batch sequentially for a human reviewer."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
P8C = ROOT / "backend" / "validation" / "phase8c"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, choices=range(1, 6), required=True)
    parser.add_argument("--reviewer", required=True)
    args = parser.parse_args()
    path = P8C / "annotation_batches" / f"batch_{args.batch:02d}.csv"
    with path.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    for index, row in enumerate(rows, 1):
        annotation_path = P8C / "annotations" / f"{row['event_id']}.json"
        payload = json.loads(annotation_path.read_text(encoding="utf-8"))
        if payload["review_state"] in {"HUMAN_VERIFIED", "REJECTED"}:
            print(f"[{index}/{len(rows)}] skip final disposition: {row['event_id']}")
            continue
        print(f"\n[{index}/{len(rows)}] {row['event_id']} ({row['screened_type']})")
        print(f"Contact sheet: {row['contact_sheet']}")
        description_a = payload["participants"]["P-A"]["visual_description"] or input("P-A visual description: ").strip()
        description_b = payload["participants"]["P-B"]["visual_description"] or input("P-B visual description: ").strip()
        command = [
            sys.executable, str(ROOT / "scripts" / "annotate_phase8c_events.py"), row["event_id"],
            "--reviewer", args.reviewer,
            "--participant-a-description", description_a,
            "--participant-b-description", description_b,
        ]
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
