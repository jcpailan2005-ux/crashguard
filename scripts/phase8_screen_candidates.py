"""Create non-ground-truth contact sheets for manual Phase 8 intake review.

The sheets are review aids only.  They never create or promote annotations.
Positive candidates are sampled around the provider's event timestamp; negative
candidates are sampled across their full duration.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
PHASE8 = ROOT / "backend" / "validation" / "phase8"
NEXAR = PHASE8 / "incoming" / "nexar"
OUTPUT = PHASE8 / "derived" / "contact_sheets"


def metadata(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return {row["file_name"]: row for row in csv.DictReader(source)}


def read_at(capture: cv2.VideoCapture, seconds: float):
    capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, seconds) * 1000.0)
    ok, frame = capture.read()
    return frame if ok else None


def sheet_for(path: Path, event_seconds: float | None) -> np.ndarray | None:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        return None
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = count / fps if fps > 0 else 0.0
    if event_seconds is None:
        times = np.linspace(max(0.0, duration * 0.05), max(0.0, duration * 0.95), 9)
    else:
        times = [event_seconds + offset for offset in (-2.0, -1.25, -0.6, -0.2, 0.0, 0.25, 0.7, 1.3, 2.0)]
    tiles = []
    for seconds in times:
        frame = read_at(capture, min(max(0.0, float(seconds)), max(0.0, duration - 0.01)))
        if frame is None:
            frame = np.zeros((360, 640, 3), dtype=np.uint8)
        frame = cv2.resize(frame, (320, 180), interpolation=cv2.INTER_AREA)
        cv2.rectangle(frame, (0, 0), (320, 24), (0, 0, 0), -1)
        cv2.putText(frame, f"{path.stem}  t={max(0.0, float(seconds)):.2f}s", (7, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(frame)
    capture.release()
    rows = [np.hstack(tiles[index:index + 3]) for index in range(0, 9, 3)]
    return np.vstack(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    positive = metadata(NEXAR / "positive_metadata.csv")
    made = 0
    for label in ("positive", "negative"):
        for path in sorted((NEXAR / label).glob("*.mp4")):
            target = OUTPUT / f"{label}_{path.stem}.jpg"
            if target.exists() and not args.overwrite:
                continue
            event = None
            if label == "positive" and path.name in positive:
                raw = positive[path.name].get("time_of_event", "")
                event = float(raw) if raw else None
            sheet = sheet_for(path, event)
            if sheet is not None:
                cv2.imwrite(str(target), sheet, [cv2.IMWRITE_JPEG_QUALITY, 91])
                made += 1
    for label in ("positive", "negative"):
        sheets = sorted(OUTPUT.glob(f"{label}_*.jpg"))
        for page_number, start in enumerate(range(0, len(sheets), 12), 1):
            page_tiles = []
            for path in sheets[start:start + 12]:
                image = cv2.imread(str(path))
                image = cv2.resize(image, (480, 270), interpolation=cv2.INTER_AREA)
                cv2.rectangle(image, (0, 0), (480, 28), (0, 0, 0), -1)
                cv2.putText(image, path.stem, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2, cv2.LINE_AA)
                page_tiles.append(image)
            while len(page_tiles) < 12:
                page_tiles.append(np.zeros((270, 480, 3), dtype=np.uint8))
            page = np.vstack([np.hstack(page_tiles[index:index + 4]) for index in range(0, 12, 4)])
            cv2.imwrite(str(OUTPUT / f"_{label}_overview_{page_number}.jpg"), page, [cv2.IMWRITE_JPEG_QUALITY, 93])
    # A denser whole-clip screen is required before accepting provider-labeled
    # negatives; nine overview samples alone could miss a brief collision.
    for path in sorted((NEXAR / "negative").glob("*.mp4")):
        capture = cv2.VideoCapture(str(path))
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration = count / fps if fps > 0 else 0.0
        tiles = []
        for seconds in np.linspace(0.0, max(0.0, duration - 0.01), 40):
            frame = read_at(capture, float(seconds))
            if frame is None:
                frame = np.zeros((144, 256, 3), dtype=np.uint8)
            frame = cv2.resize(frame, (256, 144), interpolation=cv2.INTER_AREA)
            cv2.rectangle(frame, (0, 0), (256, 20), (0, 0, 0), -1)
            cv2.putText(frame, f"{path.stem} t={seconds:.1f}s", (5, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.39, (255, 255, 255), 1, cv2.LINE_AA)
            tiles.append(frame)
        capture.release()
        dense = np.vstack([np.hstack(tiles[index:index + 5]) for index in range(0, 40, 5)])
        cv2.imwrite(str(OUTPUT / f"_negative_dense_{path.stem}.jpg"), dense, [cv2.IMWRITE_JPEG_QUALITY, 92])
    print(f"Created {made} review sheets in {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
