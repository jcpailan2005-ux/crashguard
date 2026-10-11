"""Development-only OpenCV helper for Phase 7 collision annotations.

The helper never changes source media. It supports resuming an event JSON file
and saves only explicitly selected boxes/labels; detector output is not treated
as ground truth.

Keys: SPACE pause/play, A/B select participant, D add distractor, P phase,
C contact status, V participant-A visibility, N participant-B visibility,
S save frame, R remove frame annotation, Q quit and save.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2


PHASES = ["APPROACH", "PRE_CONTACT", "CONTACT", "POST_IMPACT", "AFTERMATH", "UNKNOWN"]
VISIBILITY = ["VISIBLE_CLEAR", "VISIBLE_PARTIAL", "HEAVILY_OCCLUDED", "NOT_VISIBLE", "OUT_OF_FRAME"]
CONTACT = [False, True, "uncertain"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--event-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--type", choices=("TYPE_A", "TYPE_B", "TYPE_C"), required=True)
    parser.add_argument("--participant-a", required=True)
    parser.add_argument("--participant-b", required=True)
    parser.add_argument("--participant-a-class", required=True)
    parser.add_argument("--participant-b-class", required=True)
    return parser.parse_args()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def select_box(window: str, frame) -> list[int] | None:
    x, y, width, height = (int(value) for value in cv2.selectROI(window, frame, False, False))
    if width <= 0 or height <= 0:
        return None
    return [x, y, x + width, y + height]


def blank_record(frame_index: int, fps: float) -> dict:
    return {
        "frame_index": frame_index,
        "timestamp_ms": round(1000.0 * frame_index / fps) if fps > 0 else None,
        "phase": "UNKNOWN",
        "participant_a_bbox": None,
        "participant_a_visible": False,
        "participant_a_occlusion": "NOT_VISIBLE",
        "participant_a_expected_class": None,
        "participant_b_bbox": None,
        "participant_b_visible": False,
        "participant_b_occlusion": "NOT_VISIBLE",
        "participant_b_expected_class": None,
        "contact_visible": "uncertain",
        "collision_region_bbox": None,
        "distractor_boxes": [],
        "groundTruthCollisionPair": ["participant_a", "participant_b"],
        "annotation_uncertainty": "UNCERTAIN",
        "notes": "",
    }


def main() -> int:
    args = parse_args()
    source = args.source.resolve()
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise SystemExit(f"Could not open {source}")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if args.output.exists():
        payload = json.loads(args.output.read_text(encoding="utf-8"))
        if payload.get("source_sha256") != file_hash(source):
            raise SystemExit("Existing annotation source hash does not match")
    else:
        payload = {
            "schema_version": 1,
            "event_id": args.event_id,
            "source": str(source),
            "source_sha256": file_hash(source),
            "type": args.type,
            "participant_a": args.participant_a,
            "participant_b": args.participant_b,
            "participant_a_vehicle_class": args.participant_a_class,
            "participant_b_vehicle_class": args.participant_b_class,
            "fps": fps,
            "frame_count": frame_count,
            "resolution": [width, height],
            "annotations": [],
        }
    annotations = {int(row["frame_index"]): row for row in payload.get("annotations", [])}
    frame_index = min(annotations, default=0)
    playing = False
    phase_index = 5
    contact_index = 2
    visibility_a = visibility_b = 3
    current = copy_record = None
    window = "CrashGuard Phase 7 annotation"
    try:
        while 0 <= frame_index < frame_count:
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = capture.read()
            if not ok or frame is None:
                break
            current = json.loads(json.dumps(annotations.get(frame_index, blank_record(frame_index, fps))))
            current["participant_a_expected_class"] = args.participant_a_class
            current["participant_b_expected_class"] = args.participant_b_class
            display = frame.copy()
            cv2.putText(display, f"frame={frame_index}/{frame_count - 1} phase={current['phase']} contact={current['contact_visible']}", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
            cv2.putText(display, "SPACE play A/B participants D distractor P phase C contact V/N visibility S save R remove Q quit", (8, height - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1)
            for key, color in (("participant_a_bbox", (0, 255, 0)), ("participant_b_bbox", (0, 165, 255))):
                box = current.get(key)
                if box:
                    cv2.rectangle(display, tuple(box[:2]), tuple(box[2:]), color, 2)
            for item in current.get("distractor_boxes", []):
                cv2.rectangle(display, tuple(item["bbox"][:2]), tuple(item["bbox"][2:]), (255, 0, 255), 1)
            cv2.imshow(window, display)
            key = cv2.waitKey(30 if playing else 0) & 0xFF
            if key == ord("q"):
                break
            if key == ord(" "):
                playing = not playing
            elif key == ord("a"):
                current["participant_a_bbox"] = select_box("Participant A", frame)
                current["participant_a_visible"] = current["participant_a_bbox"] is not None
                annotations[frame_index] = current
            elif key == ord("b"):
                current["participant_b_bbox"] = select_box("Participant B", frame)
                current["participant_b_visible"] = current["participant_b_bbox"] is not None
                annotations[frame_index] = current
            elif key == ord("d"):
                box = select_box("Distractor vehicle", frame)
                if box:
                    current["distractor_boxes"].append({"id": f"distractor_{len(current['distractor_boxes']) + 1}", "bbox": box, "expected_class": "vehicle", "notes": ""})
                    annotations[frame_index] = current
            elif key == ord("p"):
                phase_index = (PHASES.index(current["phase"]) + 1) % len(PHASES)
                current["phase"] = PHASES[phase_index]
                annotations[frame_index] = current
            elif key == ord("c"):
                contact_index = (CONTACT.index(current["contact_visible"]) + 1) % len(CONTACT)
                current["contact_visible"] = CONTACT[contact_index]
                annotations[frame_index] = current
            elif key == ord("v"):
                visibility_a = (VISIBILITY.index(current["participant_a_occlusion"]) + 1) % len(VISIBILITY)
                current["participant_a_occlusion"] = VISIBILITY[visibility_a]
                current["participant_a_visible"] = VISIBILITY[visibility_a] not in {"NOT_VISIBLE", "OUT_OF_FRAME"}
                annotations[frame_index] = current
            elif key == ord("n"):
                visibility_b = (VISIBILITY.index(current["participant_b_occlusion"]) + 1) % len(VISIBILITY)
                current["participant_b_occlusion"] = VISIBILITY[visibility_b]
                current["participant_b_visible"] = VISIBILITY[visibility_b] not in {"NOT_VISIBLE", "OUT_OF_FRAME"}
                annotations[frame_index] = current
            elif key == ord("s"):
                annotations[frame_index] = current
            elif key == ord("r"):
                annotations.pop(frame_index, None)
            elif key in (81, ord("j")):
                playing = False
                frame_index = max(0, frame_index - 1)
                continue
            elif key in (83, ord("l")):
                playing = False
                frame_index = min(frame_count - 1, frame_index + 1)
                continue
            if playing:
                frame_index += 1
    finally:
        capture.release()
        cv2.destroyAllWindows()
    payload["annotations"] = [annotations[key] for key in sorted(annotations)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(payload['annotations'])} frames to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
