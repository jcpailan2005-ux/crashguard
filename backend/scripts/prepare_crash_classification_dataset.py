from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "backend" / "datasets" / "crash_classification"
SOURCE_1 = Path(r"C:\Users\Lenovo\Downloads\carcrash1cctv")
SOURCE_2 = Path(r"C:\Users\Lenovo\Downloads\carcrash2cctv")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SPLITS = ("train", "val", "test")
CLASSES = ("accident", "non_accident")
RANDOM_SEED = 20260707


@dataclass(frozen=True)
class Candidate:
    source_dataset: str
    source_path: str
    split: str | None
    label: str


def iter_images(folder: Path) -> Iterable[Path]:
    if not folder.exists():
        return
    for path in sorted(folder.rglob("*")):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path


def verify_image(path: Path) -> tuple[bool, str | None]:
    try:
        with Image.open(path) as image:
            image.verify()
        return True, None
    except Exception as exc:  # noqa: BLE001 - report exact dataset failure
        return False, str(exc)


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_carcrash1() -> list[Candidate]:
    mapping = [
        ("train", "accident", SOURCE_1 / "data" / "train" / "Accident"),
        ("train", "non_accident", SOURCE_1 / "data" / "train" / "Non Accident"),
        ("val", "accident", SOURCE_1 / "data" / "val" / "Accident"),
        ("val", "non_accident", SOURCE_1 / "data" / "val" / "Non Accident"),
        ("test", "accident", SOURCE_1 / "data" / "test" / "Accident"),
        ("test", "non_accident", SOURCE_1 / "data" / "test" / "Non Accident"),
    ]

    candidates: list[Candidate] = []
    for split, label, folder in mapping:
        for path in iter_images(folder):
            candidates.append(
                Candidate(
                    source_dataset="carcrash1cctv",
                    source_path=str(path),
                    split=split,
                    label=label,
                )
            )
    return candidates


def split_candidates(paths: list[Path], label: str) -> list[Candidate]:
    shuffled = list(paths)
    random.Random(RANDOM_SEED + (0 if label == "accident" else 1)).shuffle(shuffled)

    total = len(shuffled)
    train_end = int(total * 0.70)
    val_end = train_end + int(total * 0.15)

    split_paths = {
        "train": shuffled[:train_end],
        "val": shuffled[train_end:val_end],
        "test": shuffled[val_end:],
    }

    candidates: list[Candidate] = []
    for split, split_items in split_paths.items():
        for path in split_items:
            candidates.append(
                Candidate(
                    source_dataset="carcrash2cctv",
                    source_path=str(path),
                    split=split,
                    label=label,
                )
            )
    return candidates


def collect_carcrash2(downsample_non_accident: bool) -> tuple[list[Candidate], dict[str, int]]:
    accident_paths = list(iter_images(SOURCE_2 / "Accident" / "Accident"))
    non_accident_paths = list(iter_images(SOURCE_2 / "NonAccident" / "NonAccident"))

    original_counts = {
        "accident": len(accident_paths),
        "non_accident": len(non_accident_paths),
        "severity_score_excluded": len(list(iter_images(SOURCE_2 / "SeverityScore"))),
    }

    if downsample_non_accident and len(non_accident_paths) > len(accident_paths):
        shuffled = list(non_accident_paths)
        random.Random(RANDOM_SEED).shuffle(shuffled)
        non_accident_paths = sorted(shuffled[: len(accident_paths)])

    candidates = split_candidates(accident_paths, "accident")
    candidates.extend(split_candidates(non_accident_paths, "non_accident"))
    return candidates, original_counts


def destination_name(candidate: Candidate, digest: str) -> str:
    source = Path(candidate.source_path)
    safe_stem = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in source.stem)
    return f"{candidate.source_dataset}_{safe_stem}_{digest[:12]}{source.suffix.lower()}"


def prepare_dataset(output_root: Path, downsample_non_accident: bool) -> dict:
    if output_root.exists() and any(output_root.iterdir()):
        raise SystemExit(f"Output folder already exists and is not empty: {output_root}")

    output_root.mkdir(parents=True, exist_ok=True)
    for split in SPLITS:
        for label in CLASSES:
            (output_root / split / label).mkdir(parents=True, exist_ok=True)

    candidates = collect_carcrash1()
    carcrash2_candidates, carcrash2_original_counts = collect_carcrash2(downsample_non_accident)
    candidates.extend(carcrash2_candidates)

    valid_by_hash: dict[str, list[Candidate]] = defaultdict(list)
    skipped_corrupted: list[dict] = []

    for candidate in candidates:
        path = Path(candidate.source_path)
        ok, error = verify_image(path)
        if not ok:
            skipped_corrupted.append({**asdict(candidate), "error": error})
            continue
        digest = hash_file(path)
        valid_by_hash[digest].append(candidate)

    conflict_hashes = {
        digest
        for digest, items in valid_by_hash.items()
        if len({item.label for item in items}) > 1
    }

    cross_label_conflicts = []
    for digest in sorted(conflict_hashes):
        cross_label_conflicts.append(
            {
                "hash": digest,
                "items": [asdict(item) for item in valid_by_hash[digest]],
            }
        )

    copied_counts: dict[str, Counter] = {split: Counter() for split in SPLITS}
    skipped_duplicate_same_label: list[dict] = []
    copied_records: list[dict] = []

    for digest in sorted(valid_by_hash):
        items = valid_by_hash[digest]
        if digest in conflict_hashes:
            continue

        # Deterministic priority: keep predefined carcrash1 splits, then carcrash2 split.
        items = sorted(
            items,
            key=lambda item: (
                item.source_dataset,
                SPLITS.index(item.split or "train"),
                item.label,
                item.source_path,
            ),
        )
        chosen = items[0]
        if len(items) > 1:
            for duplicate in items[1:]:
                skipped_duplicate_same_label.append(
                    {
                        "hash": digest,
                        "kept": asdict(chosen),
                        "skipped": asdict(duplicate),
                    }
                )

        if chosen.split is None:
            continue

        source = Path(chosen.source_path)
        dest = output_root / chosen.split / chosen.label / destination_name(chosen, digest)
        shutil.copy2(source, dest)
        copied_counts[chosen.split][chosen.label] += 1
        copied_records.append(
            {
                "hash": digest,
                "source": asdict(chosen),
                "destination": str(dest),
            }
        )

    report = {
        "output_root": str(output_root),
        "sources": {
            "carcrash1cctv": str(SOURCE_1),
            "carcrash2cctv": str(SOURCE_2),
        },
        "settings": {
            "downsample_carcrash2_non_accident": downsample_non_accident,
            "random_seed": RANDOM_SEED,
            "severity_score_excluded": True,
        },
        "carcrash2_original_counts": carcrash2_original_counts,
        "candidate_count": len(candidates),
        "copied_counts": {
            split: {label: copied_counts[split][label] for label in CLASSES}
            for split in SPLITS
        },
        "skipped_duplicate_images": len(skipped_duplicate_same_label),
        "skipped_corrupted_images": len(skipped_corrupted),
        "cross_label_conflicts": len(cross_label_conflicts),
        "skipped_duplicate_same_label": skipped_duplicate_same_label,
        "skipped_corrupted": skipped_corrupted,
        "cross_label_conflict_items": cross_label_conflicts,
        "copied_records": copied_records,
    }

    (output_root / "dataset_preparation_report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    (output_root / "dataset_preparation_report.md").write_text(
        render_markdown_report(report),
        encoding="utf-8",
    )

    return report


def render_markdown_report(report: dict) -> str:
    lines = [
        "# Crash Classification Dataset Preparation Report",
        "",
        f"Output path: `{report['output_root']}`",
        "",
        "## Settings",
        "",
        f"- Downsampled carcrash2 non-accident: `{report['settings']['downsample_carcrash2_non_accident']}`",
        f"- Random seed: `{report['settings']['random_seed']}`",
        "- SeverityScore folders excluded: `True`",
        "",
        "## Copied Images",
        "",
        "| Split | accident | non_accident |",
        "| --- | ---: | ---: |",
    ]
    for split in SPLITS:
        counts = report["copied_counts"][split]
        lines.append(f"| {split} | {counts['accident']} | {counts['non_accident']} |")

    lines.extend(
        [
            "",
            "## Skipped",
            "",
            f"- Duplicate same-label images skipped: {report['skipped_duplicate_images']}",
            f"- Corrupted/unreadable images skipped: {report['skipped_corrupted_images']}",
            f"- Cross-label conflict hash groups skipped: {report['cross_label_conflicts']}",
            "",
            "## carcrash2 Original Counts",
            "",
        ]
    )
    for label, count in report["carcrash2_original_counts"].items():
        lines.append(f"- {label}: {count}")

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Original downloaded datasets were not modified.",
            "- Current YOLO `data.yaml` was not modified.",
            "- No training was started.",
            "- This dataset is prepared for image classification, not YOLO object detection.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--keep-full-non-accident",
        action="store_true",
        help="Do not downsample carcrash2 non-accident images.",
    )
    args = parser.parse_args()

    report = prepare_dataset(
        output_root=args.output_root,
        downsample_non_accident=not args.keep_full_non_accident,
    )
    print(json.dumps({
        "output_root": report["output_root"],
        "copied_counts": report["copied_counts"],
        "skipped_duplicate_images": report["skipped_duplicate_images"],
        "skipped_corrupted_images": report["skipped_corrupted_images"],
        "cross_label_conflicts": report["cross_label_conflicts"],
    }, indent=2))


if __name__ == "__main__":
    main()
