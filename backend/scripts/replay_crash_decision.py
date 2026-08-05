"""Offline crash-decision replay tool.

Replays folders of CCTV images (or extracted video frames) through the exact
per-frame detection + strict crash decision pipeline used by the backend
(`backend.main.evaluate_crash_case_decision` and friends) WITHOUT creating
crash cases, notifications, responder queue items, or map review items.

Usage (from the project root):

    python backend/scripts/replay_crash_decision.py <input_dir> [--output report.csv] [--strict]

Every folder (at any depth) that directly contains images is replayed as an
independent frame sequence (its own temporal window, cooldown, and simulated
active-case state), matching how one camera behaves in production. Frames are
processed in sorted filename order, one simulated second apart. The top-level
folder name is the category used in the summary.

Recommended dataset layout (hard negatives + positives):

    dataset/
      person_only/            # must never reach confirmed_crash
      no_vehicle/
      normal_cctv/
      indoor_or_porch_cctv/
      empty_road/
      normal_traffic/
      parked_vehicle/
      night_glare_rain_noise/
      confirmed_crash/        # real crash incidents; should confirm
        incident_01/          # one subfolder per incident so each one
        incident_02/          # gets its own active-case/cooldown state

With --strict, the exit code is 1 when any hard-negative folder produces a
confirmed_crash decision, so the replay can run as a CI regression gate.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import cv2  # noqa: E402

from backend.main import (  # noqa: E402
    CRASH_CASE_CONFIDENCE_THRESHOLD,
    LIVE_CAMERA_FRAME_HEIGHT,
    LIVE_CAMERA_FRAME_WIDTH,
    LIVE_CAMERA_PERSON_CONFIDENCE_THRESHOLD,
    LIVE_CAMERA_REQUIRED_HITS,
    PERSON_LABELS,
    CameraDecisionTracker,
    classify_crash_frame,
    count_labels_from_results,
    crash_like_vehicle_interaction,
    detect_vehicle_boxes,
    evaluate_crash_case_decision,
    filter_boxes_in_roi,
    model,
    normalize_confidence_fraction,
)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# Folders whose frames must never produce a confirmed_crash decision.
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

CSV_COLUMNS = [
    "filename",
    "vehicleCount",
    "personCount",
    "sceneValid",
    "motionValid",
    "crashScore",
    "consecutiveCrashHits",
    "requiredConsecutiveCrashHits",
    "finalDecision",
    "rejectionReason",
    "caseCreatedAllowed",
    "notificationCreatedAllowed",
]

# One simulated second between frames, mirroring the live monitor cadence.
SIMULATED_FRAME_INTERVAL_SECONDS = 1.0


def list_image_files(folder: Path) -> list[Path]:
    return sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def analyze_frame_signals(frame) -> dict:
    """Compute the same per-frame signals the backend feeds into the decision."""
    detection_frame = cv2.resize(
        frame,
        (LIVE_CAMERA_FRAME_WIDTH, LIVE_CAMERA_FRAME_HEIGHT),
        interpolation=cv2.INTER_AREA,
    )
    results = model.predict(detection_frame, verbose=False)
    classifier_result = classify_crash_frame(detection_frame)
    crash_class = str(classifier_result.get("crashClass") or "unknown")
    crash_score = normalize_confidence_fraction(classifier_result.get("crashConfidence"))
    all_vehicle_boxes = detect_vehicle_boxes(detection_frame, fallback_results=results)
    roi_vehicle_boxes, scene_valid = filter_boxes_in_roi(all_vehicle_boxes, detection_frame)
    person_count = count_labels_from_results(
        results,
        getattr(model, "names", {}),
        PERSON_LABELS,
        min_confidence=LIVE_CAMERA_PERSON_CONFIDENCE_THRESHOLD,
    )
    return {
        "crashClass": crash_class,
        "crashScore": crash_score,
        "vehicleCount": len(roi_vehicle_boxes),
        "personCount": person_count,
        "sceneValid": scene_valid,
        "motionValid": crash_like_vehicle_interaction(roi_vehicle_boxes),
    }


def replay_sequence(sequence_name: str, files: list[Path], input_root: Path) -> list[dict]:
    """Replay one folder as an independent camera sequence. Never persists anything."""
    tracker = CameraDecisionTracker()
    rows: list[dict] = []
    simulated_now = 1_000.0
    active_case_exists = False  # a confirmed decision blocks the rest of the sequence,
    # exactly like a pending_review case would in production.

    for file_path in files:
        frame = cv2.imread(str(file_path))
        relative_name = file_path.relative_to(input_root).as_posix()
        if frame is None:
            print(f"[replay] WARNING: could not decode {relative_name}; skipped.")
            continue

        signals = analyze_frame_signals(frame)
        pre_temporal_positive = bool(
            signals["crashClass"] == "accident"
            and signals["crashScore"] >= CRASH_CASE_CONFIDENCE_THRESHOLD
            and signals["vehicleCount"] > 0
            and signals["sceneValid"]
            and signals["motionValid"]
        )
        consecutive_hits = tracker.record_frame(
            sequence_name, pre_temporal_positive, now=simulated_now
        )
        cooldown_ready = tracker.cooldown_ready(sequence_name, now=simulated_now)

        should_create, rejection_reason, final_decision = evaluate_crash_case_decision(
            crash_class=signals["crashClass"],
            crash_confidence=signals["crashScore"],
            vehicle_count=signals["vehicleCount"],
            person_count=signals["personCount"],
            scene_valid=signals["sceneValid"],
            motion_valid=signals["motionValid"],
            consecutive_positive_frames=consecutive_hits,
            active_case_exists=active_case_exists,
            cooldown_ready=cooldown_ready,
        )
        if should_create:
            # Simulate (do not persist) the production side effects of case creation.
            tracker.mark_alert(sequence_name, now=simulated_now)
            active_case_exists = True

        rows.append(
            {
                "filename": relative_name,
                "vehicleCount": signals["vehicleCount"],
                "personCount": signals["personCount"],
                "sceneValid": signals["sceneValid"],
                "motionValid": signals["motionValid"],
                "crashScore": f"{signals['crashScore']:.4f}",
                "consecutiveCrashHits": consecutive_hits,
                "requiredConsecutiveCrashHits": LIVE_CAMERA_REQUIRED_HITS,
                "finalDecision": final_decision,
                "rejectionReason": rejection_reason or "",
                "caseCreatedAllowed": should_create,
                "notificationCreatedAllowed": should_create,
            }
        )
        simulated_now += SIMULATED_FRAME_INTERVAL_SECONDS

    return rows


def collect_sequences(input_dir: Path) -> list[tuple[str, list[Path]]]:
    """Every directory (at any depth) that directly contains images is one sequence.

    Sequence names are input-relative paths (e.g. "confirmed_crash/incident_01");
    loose images in the input root form their own sequence.
    """
    sequences: list[tuple[str, list[Path]]] = []
    folders = sorted(path for path in input_dir.rglob("*") if path.is_dir())
    for folder in folders:
        files = list_image_files(folder)
        if files:
            sequences.append((folder.relative_to(input_dir).as_posix(), files))
    root_files = list_image_files(input_dir)
    if root_files:
        sequences.append((input_dir.name, root_files))
    return sequences


def category_of(sequence_name: str) -> str:
    return sequence_name.split("/", 1)[0]


def summarize(rows_by_sequence: dict[str, list[dict]], strict: bool) -> int:
    exit_code = 0
    categories: dict[str, dict] = {}
    for sequence_name, rows in rows_by_sequence.items():
        stats = categories.setdefault(
            category_of(sequence_name),
            {"frames": 0, "confirmed": 0, "sequences": 0, "sequences_confirmed": 0},
        )
        confirmed = sum(1 for row in rows if row["finalDecision"] == "confirmed_crash")
        stats["frames"] += len(rows)
        stats["confirmed"] += confirmed
        stats["sequences"] += 1
        stats["sequences_confirmed"] += 1 if confirmed > 0 else 0

    print("\n=== Replay summary (by category) ===")
    for category, stats in sorted(categories.items()):
        line = (
            f"{category}: sequences={stats['sequences']} frames={stats['frames']} "
            f"confirmed_crash={stats['confirmed']} "
            f"sequences_confirmed={stats['sequences_confirmed']}/{stats['sequences']}"
        )
        if category in HARD_NEGATIVE_FOLDERS:
            if stats["confirmed"] > 0:
                line += "  << FALSE POSITIVE: hard-negative category produced confirmed_crash"
                if strict:
                    exit_code = 1
            else:
                line += "  (hard negative OK)"
        elif category == "confirmed_crash" and stats["sequences_confirmed"] == 0:
            line += "  << NOTE: positive crash category never confirmed (recall gap)"
        print(line)
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Replay image folders through the strict crash decision pipeline "
            "and export a CSV report. Creates no cases and no notifications."
        )
    )
    parser.add_argument("input_dir", type=Path, help="Folder of images, or a folder of category subfolders.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("crash_decision_report.csv"),
        help="CSV report path (default: crash_decision_report.csv).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if any hard-negative folder produces confirmed_crash.",
    )
    args = parser.parse_args()

    input_dir = args.input_dir.resolve()
    if not input_dir.is_dir():
        print(f"[replay] Input folder not found: {input_dir}")
        return 2

    sequences = collect_sequences(input_dir)
    if not sequences:
        print(f"[replay] No images found under {input_dir} (extensions: {sorted(IMAGE_EXTENSIONS)}).")
        return 2

    rows_by_sequence: dict[str, list[dict]] = {}
    all_rows: list[dict] = []
    for sequence_name, files in sequences:
        print(f"[replay] Sequence '{sequence_name}': {len(files)} frame(s)")
        rows = replay_sequence(sequence_name, files, input_dir)
        rows_by_sequence[sequence_name] = rows
        all_rows.extend(rows)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"[replay] Wrote {len(all_rows)} row(s) to {args.output}")

    return summarize(rows_by_sequence, strict=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
