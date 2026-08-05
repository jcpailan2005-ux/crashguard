"""Compare two crash-decision replay reports (baseline vs retrained).

Both inputs are CSVs produced by backend/scripts/replay_crash_decision.py.
For each top-level category folder this prints hard-negative false-positive
counts, confirmed-crash recall (incidents confirmed / total incidents),
average crashScore, and an improvement/regression summary.

Usage:

    python backend/scripts/compare_replay_reports.py baseline_report.csv retrained_report.csv [--strict]

With --strict the exit code is 1 when the retrained report has more
hard-negative false positives than the baseline in any category, or when
confirmed-crash recall decreased — so this can gate model acceptance in CI.

This tool only reads CSVs; it never touches the database, models, or backend.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# Must match backend/scripts/replay_crash_decision.py.
HARD_NEGATIVE_FOLDERS = {
    "person_only",
    "no_vehicle",
    "normal_cctv",
    "indoor_or_porch_cctv",
    "empty_road",
    "normal_traffic",
    "parked_vehicle",
    "night_glare_rain_noise",
}
POSITIVE_FOLDER = "confirmed_crash"


def category_of(filename: str) -> str:
    return filename.replace("\\", "/").split("/", 1)[0]


def sequence_of(filename: str) -> str:
    normalized = filename.replace("\\", "/")
    return normalized.rsplit("/", 1)[0] if "/" in normalized else "(root)"


def load_report(path: Path) -> dict[str, dict]:
    """Aggregate one replay CSV into per-category stats."""
    categories: dict[str, dict] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"filename", "crashScore", "finalDecision"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(
                f"{path} is missing expected replay columns: {sorted(missing)}"
            )
        for row in reader:
            category = category_of(row["filename"])
            stats = categories.setdefault(
                category,
                {
                    "frames": 0,
                    "confirmed_frames": 0,
                    "score_sum": 0.0,
                    "sequences": set(),
                    "sequences_confirmed": set(),
                },
            )
            sequence = sequence_of(row["filename"])
            stats["frames"] += 1
            stats["sequences"].add(sequence)
            try:
                stats["score_sum"] += float(row["crashScore"])
            except (TypeError, ValueError):
                pass
            if row["finalDecision"] == "confirmed_crash":
                stats["confirmed_frames"] += 1
                stats["sequences_confirmed"].add(sequence)
    return categories


def average_score(stats: dict | None) -> float:
    if not stats or stats["frames"] == 0:
        return 0.0
    return stats["score_sum"] / stats["frames"]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare baseline vs retrained crash-decision replay reports."
    )
    parser.add_argument("baseline", type=Path, help="Baseline replay CSV.")
    parser.add_argument("retrained", type=Path, help="Retrained replay CSV.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 on any hard-negative FP increase or confirmed-crash recall drop.",
    )
    args = parser.parse_args()

    for path in (args.baseline, args.retrained):
        if not path.is_file():
            print(f"[compare] Report not found: {path}")
            return 2

    baseline = load_report(args.baseline)
    retrained = load_report(args.retrained)
    all_categories = sorted(set(baseline) | set(retrained))

    improvements: list[str] = []
    regressions: list[str] = []
    unchanged: list[str] = []

    print(f"[compare] baseline : {args.baseline}")
    print(f"[compare] retrained: {args.retrained}")

    print("\n=== Hard-negative false positives (confirmed_crash frames; want 0) ===")
    for category in all_categories:
        if category not in HARD_NEGATIVE_FOLDERS:
            continue
        base = baseline.get(category)
        retr = retrained.get(category)
        if base is None or retr is None:
            print(f"{category}: MISSING in {'baseline' if base is None else 'retrained'} report - dataset mismatch?")
            continue
        base_fp = base["confirmed_frames"]
        retr_fp = retr["confirmed_frames"]
        delta = retr_fp - base_fp
        marker = "improved" if delta < 0 else "REGRESSED" if delta > 0 else "unchanged"
        print(
            f"{category}: baseline={base_fp} retrained={retr_fp} delta={delta:+d} ({marker})"
        )
        if delta < 0:
            improvements.append(f"{category}: {base_fp} -> {retr_fp} false positives")
        elif delta > 0:
            regressions.append(f"{category}: false positives rose {base_fp} -> {retr_fp}")
        else:
            unchanged.append(category)

    print("\n=== Confirmed-crash recall (incidents confirmed / total incidents) ===")
    base_pos = baseline.get(POSITIVE_FOLDER)
    retr_pos = retrained.get(POSITIVE_FOLDER)
    if base_pos is None and retr_pos is None:
        print("confirmed_crash: no positive frames in either report.")
    else:
        base_recall = len(base_pos["sequences_confirmed"]) if base_pos else 0
        base_total = len(base_pos["sequences"]) if base_pos else 0
        retr_recall = len(retr_pos["sequences_confirmed"]) if retr_pos else 0
        retr_total = len(retr_pos["sequences"]) if retr_pos else 0
        print(
            f"confirmed_crash: baseline={base_recall}/{base_total} "
            f"retrained={retr_recall}/{retr_total}"
        )
        if retr_recall > base_recall:
            improvements.append(
                f"confirmed_crash recall improved {base_recall}/{base_total} -> {retr_recall}/{retr_total}"
            )
        elif retr_recall < base_recall:
            regressions.append(
                f"confirmed_crash recall dropped {base_recall}/{base_total} -> {retr_recall}/{retr_total}"
            )

    print("\n=== Average crashScore per category (hard negatives should fall) ===")
    for category in all_categories:
        base_avg = average_score(baseline.get(category))
        retr_avg = average_score(retrained.get(category))
        direction = "down" if retr_avg < base_avg else "up" if retr_avg > base_avg else "same"
        print(
            f"{category}: baseline={base_avg:.4f} retrained={retr_avg:.4f} ({direction})"
        )

    print("\n=== Summary ===")
    for entry in improvements:
        print(f"IMPROVED : {entry}")
    for entry in regressions:
        print(f"REGRESSED: {entry}")
    if unchanged:
        print(f"unchanged: {', '.join(unchanged)}")
    if not improvements and not regressions:
        print("No changes between reports.")

    if regressions:
        print("\nVerdict: REGRESSION - retrained model is not acceptable as-is.")
        return 1 if args.strict else 0
    if improvements:
        print("\nVerdict: IMPROVED - hard negatives reduced without recall loss.")
    else:
        print("\nVerdict: NO CHANGE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
