"""Development-only, human-authoritative Phase 8 video annotation helper.

Keys: SPACE play/pause, J/L previous/next frame, A/B participant box,
D distractor, X remove last distractor, P phase, C contact, V/N participant
visibility/occlusion, F confidence, [/] analysis window, 1/2/3 contact
start/peak/end, H aftermath start, S save frame, U undo, R remove frame,
Q save/resume and quit. No source media or production code is modified.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

import cv2


PHASES = ["APPROACH", "PRE_CONTACT", "CONTACT", "POST_IMPACT", "AFTERMATH", "UNKNOWN"]
VISIBILITY = ["VISIBLE_CLEAR", "VISIBLE_PARTIAL", "HEAVILY_OCCLUDED", "NOT_VISIBLE", "OUT_OF_FRAME"]
CONFIDENCE = ["CERTAIN", "PROBABLE", "UNCERTAIN"]
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
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--provenance", choices=("LICENSE_CONFIRMED", "RESEARCH_USE_CONFIRMED", "USER_PROVIDED", "LOCAL_EXISTING"), required=True)
    return parser.parse_args()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def select_box(window: str, frame) -> list[int] | None:
    x, y, width, height = (int(value) for value in cv2.selectROI(window, frame, False, False))
    cv2.destroyWindow(window)
    return [x, y, x + width, y + height] if width > 0 and height > 0 else None


def blank_record(frame_index: int, fps: float, class_a: str, class_b: str) -> dict:
    return {
        "frame_index": frame_index, "timestamp_ms": round(1000 * frame_index / fps) if fps else None,
        "phase": "UNKNOWN", "participant_a_bbox": None, "participant_b_bbox": None,
        "participant_a_vehicle_class": class_a, "participant_b_vehicle_class": class_b,
        "participant_a_visibility": "NOT_VISIBLE", "participant_b_visibility": "NOT_VISIBLE",
        "contact_status": "uncertain", "collision_region": None,
        "distractor_vehicle_boxes": [], "distractor_ids": [], "distractor_motion_notes": [],
        "ground_truth_collision_pair": ["participant_a", "participant_b"],
        "annotation_confidence": "UNCERTAIN", "annotation_source": "HUMAN_VERIFIED", "notes": "",
    }


def main() -> int:
    args = parse_args()
    source = args.source.resolve()
    digest = file_hash(source)
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise SystemExit(f"Could not open {source}")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if args.output.exists():
        payload = json.loads(args.output.read_text(encoding="utf-8"))
        if payload.get("source_sha256") != digest:
            raise SystemExit("Existing annotation hash does not match source")
    else:
        payload = {
            "schema_version": 2, "event_id": args.event_id, "event_type": args.type,
            "source": str(source), "source_sha256": digest,
            "source_provenance": {"source_id": args.source_id, "status": args.provenance},
            "participant_a": args.participant_a, "participant_b": args.participant_b,
            "participant_a_vehicle_class": args.participant_a_class,
            "participant_b_vehicle_class": args.participant_b_class,
            "ground_truth_collision_pair": ["participant_a", "participant_b"],
            "fps": fps, "frame_count": count, "resolution": [width, height],
            "analysis_start": None, "analysis_end": None, "contact_start_frame": None,
            "contact_peak_frame": None, "contact_end_frame": None, "contact_uncertain": True,
            "aftermath_start": None, "dynamic_confirmation_expected": args.type != "TYPE_C",
            "annotations": [],
        }
    annotations = {int(row["frame_index"]): row for row in payload.get("annotations", [])}
    frame_index = min(annotations, default=0)
    playing = False
    undo: list[tuple[int, dict | None]] = []
    window = "CrashGuard Phase 8 annotation"
    try:
        while 0 <= frame_index < count:
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = capture.read()
            if not ok or frame is None:
                break
            current = copy.deepcopy(annotations.get(frame_index, blank_record(frame_index, fps, args.participant_a_class, args.participant_b_class)))
            display = frame.copy()
            status = f"{args.source_id} frame={frame_index}/{count-1} phase={current['phase']} contact={current['contact_status']} conf={current['annotation_confidence']}"
            cv2.putText(display, status, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(display, f"provenance={args.provenance} sha256={digest[:12]}...", (8, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
            for key, color in (("participant_a_bbox", (0, 255, 0)), ("participant_b_bbox", (0, 165, 255))):
                if current.get(key):
                    cv2.rectangle(display, tuple(current[key][:2]), tuple(current[key][2:]), color, 2)
            for box in current.get("distractor_vehicle_boxes", []):
                cv2.rectangle(display, tuple(box[:2]), tuple(box[2:]), (255, 0, 255), 1)
            cv2.imshow(window, display)
            key = cv2.waitKey(30 if playing else 0) & 0xFF
            if key == ord("q"):
                break
            previous = copy.deepcopy(annotations.get(frame_index))
            changed = False
            if key == ord(" "):
                playing = not playing
            elif key in (ord("j"), 81):
                playing = False; frame_index = max(0, frame_index - 1); continue
            elif key in (ord("l"), 83):
                playing = False; frame_index = min(count - 1, frame_index + 1); continue
            elif key in (ord("a"), ord("b")):
                participant = "a" if key == ord("a") else "b"
                box = select_box(f"Participant {participant.upper()}", frame)
                current[f"participant_{participant}_bbox"] = box
                current[f"participant_{participant}_visibility"] = "VISIBLE_CLEAR" if box else "NOT_VISIBLE"
                changed = True
            elif key == ord("d"):
                box = select_box("Distractor", frame)
                if box:
                    number = len(current["distractor_vehicle_boxes"]) + 1
                    current["distractor_vehicle_boxes"].append(box)
                    current["distractor_ids"].append(f"distractor_{number}")
                    current["distractor_motion_notes"].append("Human-marked non-collision vehicle; add motion note during review.")
                    changed = True
            elif key == ord("x") and current["distractor_vehicle_boxes"]:
                current["distractor_vehicle_boxes"].pop(); current["distractor_ids"].pop(); current["distractor_motion_notes"].pop(); changed = True
            elif key == ord("p"):
                current["phase"] = PHASES[(PHASES.index(current["phase"]) + 1) % len(PHASES)]; changed = True
            elif key == ord("c"):
                current["contact_status"] = CONTACT[(CONTACT.index(current["contact_status"]) + 1) % len(CONTACT)]; changed = True
            elif key in (ord("v"), ord("n")):
                participant = "a" if key == ord("v") else "b"
                field = f"participant_{participant}_visibility"
                current[field] = VISIBILITY[(VISIBILITY.index(current[field]) + 1) % len(VISIBILITY)]; changed = True
            elif key == ord("f"):
                current["annotation_confidence"] = CONFIDENCE[(CONFIDENCE.index(current["annotation_confidence"]) + 1) % len(CONFIDENCE)]; changed = True
            elif key == ord("["):
                payload["analysis_start"] = {"frame": frame_index, "timestamp_ms": current["timestamp_ms"]}
            elif key == ord("]"):
                payload["analysis_end"] = {"frame": frame_index, "timestamp_ms": current["timestamp_ms"]}
            elif key in (ord("1"), ord("2"), ord("3")):
                field = {ord("1"): "contact_start_frame", ord("2"): "contact_peak_frame", ord("3"): "contact_end_frame"}[key]
                payload[field] = frame_index
            elif key == ord("h"):
                payload["aftermath_start"] = {"frame": frame_index, "timestamp_ms": current["timestamp_ms"]}
            elif key == ord("s"):
                changed = True
            elif key == ord("r"):
                undo.append((frame_index, previous)); annotations.pop(frame_index, None)
            elif key == ord("u") and undo:
                target_frame, prior = undo.pop()
                if prior is None: annotations.pop(target_frame, None)
                else: annotations[target_frame] = prior
            if changed:
                undo.append((frame_index, previous)); annotations[frame_index] = current
            if playing:
                frame_index += 1
    finally:
        capture.release(); cv2.destroyAllWindows()
    payload["annotations"] = [annotations[key] for key in sorted(annotations)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(payload['annotations'])} keyframes to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
