"""Development-only OpenCV helper for two-participant collision annotations.

Example:
    python scripts/annotate_collision_participants.py video.mp4 \
        --frames 440,442,444,447,450,453 --output ground_truth.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("--frames", required=True, help="Comma-separated zero-based frames")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--participant-a-class", default="car")
    parser.add_argument("--participant-b-class", default="motorcycle")
    return parser.parse_args()


def xywh_to_xyxy(roi: tuple[int, int, int, int]) -> list[int]:
    x, y, width, height = roi
    return [int(x), int(y), int(x + width), int(y + height)]


def select_participant(frame, label: str) -> list[int] | None:
    display = frame.copy()
    cv2.putText(
        display,
        f"Select {label}; ENTER accepts, C cancels",
        (10, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (0, 0, 255),
        2,
        cv2.LINE_AA,
    )
    roi = tuple(int(value) for value in cv2.selectROI(label, display, False, False))
    cv2.destroyWindow(label)
    if roi[2] <= 0 or roi[3] <= 0:
        return None
    return xywh_to_xyxy(roi)


def main() -> int:
    args = parse_args()
    frame_indices = [int(value.strip()) for value in args.frames.split(",") if value.strip()]
    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        raise SystemExit(f"Could not open video: {args.video}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    annotations = []
    try:
        for frame_index in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = cap.read()
            if not ok:
                print(f"Skipping unreadable frame {frame_index}")
                continue
            participant_a = select_participant(frame, "Participant A")
            if participant_a is None:
                print(f"Skipping frame {frame_index}: Participant A was not selected")
                continue
            participant_b = select_participant(frame, "Participant B")
            if participant_b is None:
                print(f"Skipping frame {frame_index}: Participant B was not selected")
                continue
            annotations.append(
                {
                    "frame_index": frame_index,
                    "timestamp": round(frame_index / fps, 4) if fps > 0 else None,
                    "participant_a_bbox": participant_a,
                    "participant_b_bbox": participant_b,
                    "participant_a_class": args.participant_a_class,
                    "participant_b_class": args.participant_b_class,
                    "impact_phase": "unassigned",
                    "notes": "",
                }
            )
    finally:
        cap.release()
        cv2.destroyAllWindows()

    payload = {
        "schema_version": 1,
        "sequence_id": args.video.stem,
        "source_video": str(args.video),
        "frame_width": width,
        "frame_height": height,
        "fps": fps,
        "annotation_method": "manual OpenCV selectROI",
        "annotations": annotations,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(annotations)} annotated frames to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
