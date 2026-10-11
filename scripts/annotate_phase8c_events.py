"""Interactive, development-only Phase 8C human annotation helper.

All boxes are human-drawn and stored in original source-frame coordinates. Saved
keyframes remain drafts until the guarded VERIFY EVENT action succeeds.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import cv2

ROOT = Path(__file__).resolve().parents[1]
P8C = ROOT / "backend" / "validation" / "phase8c"
QUEUE = P8C / "manifests" / "annotation_queue.csv"
CLASSES = ["car", "motorcycle", "bus", "truck", "bicycle"]
PHASES = ["APPROACH", "PRE_CONTACT", "CONTACT", "POST_IMPACT", "AFTERMATH", "UNKNOWN"]
VISIBILITY = ["VISIBLE_CLEAR", "VISIBLE_PARTIAL", "HEAVILY_OCCLUDED", "NOT_VISIBLE", "OUT_OF_FRAME"]
OCCLUSION = ["NONE", "LOW", "MEDIUM", "HIGH"]
CONTACT = ["NO", "YES", "UNCERTAIN"]
CERTAINTY = ["CERTAIN", "PROBABLE", "UNCERTAIN"]
EVENT_TYPES = ["TYPE_A", "TYPE_B", "TYPE_C"]
REJECTION_CODES = [
    "REJECT_CONTACT_NOT_DEFENSIBLE", "REJECT_PARTICIPANT_UNBOUNDABLE",
    "REJECT_WRONG_EVENT_TYPE", "REJECT_DUPLICATE", "REJECT_INSUFFICIENT_FRAMES",
    "REJECT_NOT_COLLISION", "REJECT_OTHER",
]
LEFT_KEYS = {81, 2424832}
RIGHT_KEYS = {83, 2555904}
DELETE_KEYS = {8, 127, 3014656}
PHASE_KEYS = {
    ord("5"): "APPROACH", ord("6"): "PRE_CONTACT", ord("7"): "CONTACT",
    ord("8"): "POST_IMPACT", ord("9"): "AFTERMATH", ord("0"): "UNKNOWN",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def cycle(values: list[str], value: str) -> str:
    return values[(values.index(value) + 1) % len(values)]


def blank_record(frame_index: int, fps: float, payload: dict) -> dict:
    participants = payload["participants"]
    return {
        "frame_index": frame_index,
        "timestamp_ms": round(1000 * frame_index / fps) if fps else None,
        "phase": "UNKNOWN", "contact_status": "UNCERTAIN", "contact_confidence": "UNCERTAIN",
        "collision_region_bbox": None,
        "participant_observations": {
            "P-A": {"bbox": None, "vehicle_class": participants["P-A"]["vehicle_class"], "visibility": "NOT_VISIBLE", "occlusion": "HIGH"},
            "P-B": {"bbox": None, "vehicle_class": participants["P-B"]["vehicle_class"], "visibility": "NOT_VISIBLE", "occlusion": "HIGH"},
        },
        "distractors": [], "ground_truth_collision_pair": ["P-A", "P-B"],
        "annotation_state": "DRAFT_HUMAN", "notes": "",
    }


def box_valid(box: object, width: int, height: int) -> bool:
    return (isinstance(box, list) and len(box) == 4
            and all(isinstance(value, int) for value in box)
            and 0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height)


@dataclass(frozen=True)
class DisplayTransform:
    source_width: int
    source_height: int
    display_width: int
    display_height: int

    @classmethod
    def fit(cls, source_width: int, source_height: int, max_width: int = 960, max_height: int = 650) -> "DisplayTransform":
        scale = min(max_width / source_width, max_height / source_height)
        return cls(source_width, source_height, max(1, round(source_width * scale)), max(1, round(source_height * scale)))

    def source_to_display(self, box: list[int]) -> list[int]:
        sx, sy = self.display_width / self.source_width, self.display_height / self.source_height
        return [round(box[0] * sx), round(box[1] * sy), round(box[2] * sx), round(box[3] * sy)]

    def display_to_source(self, box: list[int]) -> list[int] | None:
        x1, x2 = sorted((max(0, min(self.display_width, box[0])), max(0, min(self.display_width, box[2]))))
        y1, y2 = sorted((max(0, min(self.display_height, box[1])), max(0, min(self.display_height, box[3]))))
        if x1 == x2 or y1 == y2:
            return None
        sx, sy = self.source_width / self.display_width, self.source_height / self.display_height
        result = [round(x1 * sx), round(y1 * sy), round(x2 * sx), round(y2 * sy)]
        result[0] = max(0, min(self.source_width - 1, result[0]))
        result[1] = max(0, min(self.source_height - 1, result[1]))
        result[2] = max(result[0] + 1, min(self.source_width, result[2]))
        result[3] = max(result[1] + 1, min(self.source_height, result[3]))
        return result if box_valid(result, self.source_width, self.source_height) else None


def verification_errors(payload: dict) -> list[str]:
    errors: list[str] = []
    width, height = payload["resolution"]
    rows = payload.get("annotations", [])
    start, end = payload.get("analysis_start_frame"), payload.get("analysis_end_frame")
    if payload.get("ground_truth_collision_pair") != ["P-A", "P-B"] or not payload.get("ground_truth_pair_verified"):
        errors.append("ground-truth pair has not been explicitly confirmed")
    if not payload.get("event_type_verified"):
        errors.append("event type has not been explicitly accepted")
    if start is None or end is None or not (0 <= start <= end < payload["frame_count"]):
        errors.append("analysis window is missing or invalid")
    if len(rows) < 6:
        errors.append(f"at least 6 saved keyframes required; found {len(rows)}")
    if not payload.get("distractors_reviewed"):
        errors.append("distractor review has not been acknowledged")
    for participant_id in ("P-A", "P-B"):
        participant = payload["participants"].get(participant_id)
        if not participant or participant.get("vehicle_class") not in CLASSES:
            errors.append(f"{participant_id} metadata/class missing")
        if not participant or not participant.get("visual_description", "").strip():
            errors.append(f"{participant_id} visual description missing")
        visible = [row for row in rows if row.get("participant_observations", {}).get(participant_id, {}).get("visibility") in VISIBILITY[:3]]
        if not visible:
            errors.append(f"{participant_id} has no human-boxable observation")
    phases = {row.get("phase") for row in rows}
    if payload["event_type"] == "TYPE_A" and not {"APPROACH", "PRE_CONTACT", "CONTACT", "POST_IMPACT"}.issubset(phases):
        errors.append("Type A needs APPROACH, PRE_CONTACT, CONTACT, and POST_IMPACT observations")
    if payload["event_type"] == "TYPE_A":
        contact_rows = [row for row in rows if row.get("contact_status") == "YES"]
        if not contact_rows:
            errors.append("Type A requires visually defensible YES contact")
        timing = [payload.get(name) for name in ("contact_start_frame", "contact_peak_frame", "contact_end_frame")]
        exact_timing_claimed = any(row.get("contact_confidence") != "UNCERTAIN" for row in contact_rows)
        if (any(value is not None for value in timing) or exact_timing_claimed) and (any(value is None for value in timing) or timing != sorted(timing)):
            errors.append("contact timing must be complete and ordered unless marked UNCERTAIN")
        if any(not box_valid(row.get("collision_region_bbox"), width, height) for row in contact_rows):
            errors.append("every Type A YES-contact observation needs a collision region")
        if contact_rows and not any(all(row["participant_observations"][pid].get("bbox") for pid in ("P-A", "P-B")) for row in contact_rows):
            errors.append("Type A needs both participants boxed in at least one YES-contact observation")
        phase_frames = {phase: [row["frame_index"] for row in rows if row.get("phase") == phase] for phase in PHASES}
        if all(phase_frames[name] for name in ("APPROACH", "PRE_CONTACT", "CONTACT", "POST_IMPACT")):
            if not (min(phase_frames["APPROACH"]) < min(phase_frames["PRE_CONTACT"]) <= min(phase_frames["CONTACT"]) < max(phase_frames["POST_IMPACT"])):
                errors.append("Type A phase order is inconsistent")
    if payload["event_type"] == "TYPE_C" and payload.get("aftermath_start_frame") is None:
        errors.append("Type C requires aftermath_start_frame")
    if payload["event_type"] == "TYPE_C" and payload.get("dynamic_history_available") is not False:
        errors.append("Type C must explicitly set dynamic_history_available=false")
    if payload["event_type"] == "TYPE_C" and sum(row.get("phase") == "AFTERMATH" for row in rows) < 6:
        errors.append("Type C requires at least 6 AFTERMATH observations")
    indexes: set[int] = set()
    for row in rows:
        index = row.get("frame_index")
        if not isinstance(index, int) or not 0 <= index < payload["frame_count"] or index in indexes:
            errors.append(f"invalid or duplicate frame index: {index}")
        indexes.add(index)
        expected = round(1000 * index / payload["fps"]) if isinstance(index, int) and payload.get("fps") else None
        if row.get("timestamp_ms") != expected:
            errors.append(f"timestamp mismatch at frame {index}")
        if isinstance(index, int) and start is not None and end is not None and not start <= index <= end:
            errors.append(f"annotated frame {index} lies outside analysis window")
        if row.get("phase") not in PHASES or row.get("contact_status") not in CONTACT or row.get("contact_confidence") not in CERTAINTY:
            errors.append(f"invalid phase/contact fields at frame {index}")
        for pid in ("P-A", "P-B"):
            observation = row.get("participant_observations", {}).get(pid, {})
            visibility, box = observation.get("visibility"), observation.get("bbox")
            if visibility in VISIBILITY[:3] and not box_valid(box, width, height):
                errors.append(f"{pid} visible without valid box at frame {index}")
            if visibility in VISIBILITY[3:] and box is not None:
                errors.append(f"{pid} non-visible but has box at frame {index}")
            if observation.get("vehicle_class") != payload["participants"][pid].get("vehicle_class"):
                errors.append(f"{pid} class inconsistent at frame {index}")
        distractor_ids = [item.get("id") for item in row.get("distractors", [])]
        if len(distractor_ids) != len(set(distractor_ids)):
            errors.append(f"duplicate distractor IDs at frame {index}")
        for item in row.get("distractors", []):
            if not box_valid(item.get("bbox"), width, height) or item.get("vehicle_class") not in CLASSES:
                errors.append(f"invalid distractor at frame {index}")
    return errors


def pair_confirmation_errors(payload: dict, annotations: dict[int, dict]) -> list[str]:
    """Return reasons the participant pair is not ready for explicit confirmation."""
    errors: list[str] = []
    width, height = payload["resolution"]
    if payload.get("ground_truth_collision_pair") != ["P-A", "P-B"]:
        errors.append("participant identities P-A and P-B are missing")
    for pid in ("P-A", "P-B"):
        participant = payload.get("participants", {}).get(pid, {})
        if not participant.get("visual_description", "").strip():
            errors.append(f"{pid} visual description is missing")
        if participant.get("vehicle_class") not in CLASSES:
            errors.append(f"{pid} vehicle class is missing")
        valid_rows = [
            row for row in annotations.values()
            if box_valid(row.get("participant_observations", {}).get(pid, {}).get("bbox"), width, height)
        ]
        if not valid_rows:
            errors.append(f"{pid} has no saved human-drawn box")
    if annotations and not any(
        all(box_valid(row.get("participant_observations", {}).get(pid, {}).get("bbox"), width, height) for pid in ("P-A", "P-B"))
        for row in annotations.values()
    ):
        errors.append("P-A and P-B are not both boxed on the same saved keyframe")
    return errors


class AnnotationSession:
    """UI state separated from OpenCV for deterministic tests."""
    def __init__(self, payload: dict, fps: float, frame_count: int, transform: DisplayTransform) -> None:
        self.payload, self.fps, self.frame_count, self.transform = payload, fps, frame_count, transform
        self.annotations = {int(row["frame_index"]): copy.deepcopy(row) for row in payload.get("annotations", [])}
        self.drafts: dict[int, dict] = {}
        self.frame_index = min(self.annotations, default=0)
        self.playing = False
        self.mode: str | None = None
        self.selected: tuple[str, int | None] | None = None
        self.drag_start: tuple[int, int] | None = None
        self.drag_end: tuple[int, int] | None = None
        self.help_visible = True
        self.undo_stack: list[dict] = []

    @property
    def current(self) -> dict:
        if self.frame_index not in self.drafts:
            self.drafts[self.frame_index] = copy.deepcopy(self.annotations.get(self.frame_index, blank_record(self.frame_index, self.fps, self.payload)))
        return self.drafts[self.frame_index]

    def snapshot(self) -> None:
        fields = ("analysis_start_frame", "analysis_end_frame", "contact_start_frame", "contact_peak_frame", "contact_end_frame", "aftermath_start_frame", "distractors_reviewed", "ground_truth_pair_verified", "event_type", "event_type_verified", "dynamic_history_available", "participants")
        self.undo_stack.append({"frame": self.frame_index, "draft": copy.deepcopy(self.drafts.get(self.frame_index)), "saved": copy.deepcopy(self.annotations.get(self.frame_index)), "payload": {key: copy.deepcopy(self.payload.get(key)) for key in fields}})

    def undo(self) -> bool:
        if not self.undo_stack:
            return False
        state = self.undo_stack.pop()
        index = state["frame"]
        (self.drafts.pop(index, None) if state["draft"] is None else self.drafts.__setitem__(index, state["draft"]))
        (self.annotations.pop(index, None) if state["saved"] is None else self.annotations.__setitem__(index, state["saved"]))
        self.payload.update(state["payload"])
        self.frame_index = index
        return True

    def navigate(self, delta: int) -> None:
        self.playing = False
        self.frame_index = max(0, min(self.frame_count - 1, self.frame_index + delta))
        self.selected = None

    def jump(self, index: int) -> None:
        self.playing = False
        self.frame_index = max(0, min(self.frame_count - 1, index))
        self.selected = None

    def save_current(self) -> None:
        self.snapshot()
        record = copy.deepcopy(self.current)
        record["annotation_state"] = "DRAFT_HUMAN"
        self.annotations[self.frame_index] = record
        self.drafts[self.frame_index] = copy.deepcopy(record)

    def current_is_dirty(self) -> bool:
        if self.frame_index not in self.drafts:
            return False
        baseline = self.annotations.get(self.frame_index, blank_record(self.frame_index, self.fps, self.payload))
        return self.drafts[self.frame_index] != baseline

    def delete_selected(self) -> bool:
        if not self.selected:
            return False
        self.snapshot()
        kind, item_index = self.selected
        if kind in ("P-A", "P-B"):
            self.current["participant_observations"][kind].update({"bbox": None, "visibility": "NOT_VISIBLE", "occlusion": "HIGH"})
            self.payload["ground_truth_pair_verified"] = False
        elif kind == "collision":
            self.current["collision_region_bbox"] = None
        elif kind == "distractor" and item_index is not None:
            self.current["distractors"].pop(item_index)
        self.selected = None
        return True

    def begin_drag(self, x: int, y: int) -> None:
        if self.playing or self.mode not in {"P-A", "P-B", "distractor", "collision"}:
            return
        self.drag_start = (max(0, min(self.transform.display_width, x)), max(0, min(self.transform.display_height, y)))
        self.drag_end = self.drag_start

    def update_drag(self, x: int, y: int) -> None:
        if self.drag_start is not None:
            self.drag_end = (max(0, min(self.transform.display_width, x)), max(0, min(self.transform.display_height, y)))

    def finish_drag(self, x: int, y: int) -> str | None:
        if self.drag_start is None or self.mode is None:
            return None
        self.update_drag(x, y)
        box = self.transform.display_to_source([*self.drag_start, *self.drag_end])
        self.drag_start = self.drag_end = None
        if box is None:
            return None
        self.snapshot()
        if self.mode in ("P-A", "P-B"):
            self.current["participant_observations"][self.mode].update({"bbox": box, "visibility": "VISIBLE_CLEAR", "occlusion": "NONE"})
            self.payload["ground_truth_pair_verified"] = False
            self.selected = (self.mode, None)
        elif self.mode == "collision":
            self.current["collision_region_bbox"] = box
            self.selected = ("collision", None)
        else:
            ids = [int(item["id"].split("-")[-1]) for item in self.current["distractors"] if item.get("id", "").startswith("D-")]
            self.current["distractors"].append({"id": f"D-{max(ids or [0]) + 1:02d}", "bbox": box, "vehicle_class": "car", "notes": ""})
            self.selected = ("distractor", len(self.current["distractors"]) - 1)
        return self.mode

    def select_at(self, x: int, y: int) -> bool:
        point = self.transform.display_to_source([x, y, min(x + 1, self.transform.display_width), min(y + 1, self.transform.display_height)])
        if not point:
            return False
        px, py = point[:2]
        candidates = [(pid, None, self.current["participant_observations"][pid].get("bbox")) for pid in ("P-A", "P-B")]
        candidates += [("distractor", index, item["bbox"]) for index, item in enumerate(self.current["distractors"])]
        candidates += [("collision", None, self.current.get("collision_region_bbox"))]
        for kind, index, box in reversed(candidates):
            if box and box[0] <= px <= box[2] and box[1] <= py <= box[3]:
                self.selected = (kind, index)
                return True
        self.selected = None
        return False

    def sync_payload(self) -> None:
        self.payload["annotations"] = [self.annotations[index] for index in sorted(self.annotations)]


def prompt_vehicle_class(target: str, current: str, input_fn: Callable[[str], str] = input) -> str:
    choices = " / ".join(f"{i + 1}={name}" for i, name in enumerate(CLASSES))
    answer = input_fn(f"\n{target} vehicle class [{choices}; Enter keeps {current}]: ").strip().lower()
    if answer.isdigit() and 1 <= int(answer) <= len(CLASSES):
        return CLASSES[int(answer) - 1]
    return answer if answer in CLASSES else current


def apply_vehicle_class(session: AnnotationSession, target: str, value: str) -> None:
    if target in ("P-A", "P-B"):
        if session.payload["participants"][target]["vehicle_class"] != value:
            session.payload["ground_truth_pair_verified"] = False
        session.payload["participants"][target]["vehicle_class"] = value
        for row in [*session.annotations.values(), *session.drafts.values()]:
            row["participant_observations"][target]["vehicle_class"] = value
    elif session.selected and session.selected[0] == "distractor":
        session.current["distractors"][session.selected[1]]["vehicle_class"] = value


def draw_box(display, transform: DisplayTransform, box: list[int], label: str, color: tuple[int, int, int], selected: bool) -> None:
    shown = transform.source_to_display(box)
    cv2.rectangle(display, tuple(shown[:2]), tuple(shown[2:]), color, 3 if selected else 2)
    y = max(18, shown[1] - 5)
    cv2.putText(display, label, (shown[0] + 2, y), cv2.FONT_HERSHEY_SIMPLEX, .52, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(display, label, (shown[0] + 2, y), cv2.FONT_HERSHEY_SIMPLEX, .52, color, 1, cv2.LINE_AA)


def render(session: AnnotationSession, frame, event_id: str, message: str = ""):
    display = cv2.resize(frame, (session.transform.display_width, session.transform.display_height))
    current = session.current
    cv2.rectangle(display, (0, 0), (display.shape[1], 78), (0, 0, 0), -1)
    pair_ok = bool(session.payload.get("ground_truth_pair_verified")) and not pair_confirmation_errors(session.payload, session.annotations)
    lines = [
        f"{event_id}  {session.frame_index} / {session.frame_count - 1}  saved={len(session.annotations)}  {'PLAY' if session.playing else 'PAUSED'}  mode={session.mode or 'select'}",
        f"phase={current['phase']} contact={current['contact_status']}/{current['contact_confidence']} pairOK={str(pair_ok).lower()} distractorsOK={str(bool(session.payload.get('distractors_reviewed'))).lower()}",
        f"analysis=[{session.payload.get('analysis_start_frame')},{session.payload.get('analysis_end_frame')}] contact=[{session.payload.get('contact_start_frame')},{session.payload.get('contact_peak_frame')},{session.payload.get('contact_end_frame')}]",
    ]
    for index, value in enumerate(lines):
        cv2.putText(display, value, (7, 22 + index * 23), cv2.FONT_HERSHEY_SIMPLEX, .44, (0, 255, 255) if index == 0 else (240, 240, 240), 1, cv2.LINE_AA)
    for pid, color in (("P-A", (0, 255, 0)), ("P-B", (0, 165, 255))):
        observation = current["participant_observations"][pid]
        if observation.get("bbox"):
            draw_box(display, session.transform, observation["bbox"], f"{pid} {observation['vehicle_class']}", color, session.selected == (pid, None))
    for index, item in enumerate(current["distractors"]):
        draw_box(display, session.transform, item["bbox"], f"{item['id']} {item['vehicle_class']}", (255, 0, 255), session.selected == ("distractor", index))
    if current.get("collision_region_bbox"):
        draw_box(display, session.transform, current["collision_region_bbox"], "COLLISION", (0, 0, 255), session.selected == ("collision", None))
    if session.drag_start and session.drag_end:
        cv2.rectangle(display, session.drag_start, session.drag_end, (255, 255, 0), 2)
    if message:
        cv2.rectangle(display, (0, display.shape[0] - 34), (display.shape[1], display.shape[0]), (0, 0, 0), -1)
        cv2.putText(display, message, (8, display.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 255, 255), 1, cv2.LINE_AA)
    if session.help_visible:
        help_lines = [
            "H help  SPACE play/pause  Left/A previous  Right/D next  J/L -/+10  G jump",
            "1 P-A  2 P-B  3 distractor  4 collision  click select  Del delete  R redraw participant",
            "5 APPROACH  6 PRE_CONTACT  7 CONTACT  8 POST_IMPACT  9 AFTERMATH  0 UNKNOWN",
            "C contact  F confidence  I visibility  O occlusion  , . / contact start peak end",
            "[ analysis start  ] analysis end  X distractors reviewed  P pair  E event type",
            "S save keyframe  U undo  V verify event  ESC save current state and exit",
        ]
        top = 88
        cv2.rectangle(display, (5, top), (display.shape[1] - 5, top + 20 * len(help_lines) + 10), (20, 20, 20), -1)
        for index, value in enumerate(help_lines):
            cv2.putText(display, value, (13, top + 19 + index * 20), cv2.FONT_HERSHEY_SIMPLEX, .42, (235, 235, 235), 1, cv2.LINE_AA)
    return display


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("event_id")
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--participant-a-description", default="")
    parser.add_argument("--participant-b-description", default="")
    parser.add_argument("--reject", choices=REJECTION_CODES)
    parser.add_argument("--rejection-notes", default="")
    return parser.parse_args()


def save_payload(path: Path, session: AnnotationSession) -> None:
    session.sync_payload()
    path.write_text(json.dumps(session.payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    with QUEUE.open(encoding="utf-8", newline="") as source:
        queue = {row["event_id"]: row for row in csv.DictReader(source)}
    if args.event_id not in queue:
        raise SystemExit(f"Unknown Phase 8C event: {args.event_id}")
    source_path = Path(queue[args.event_id]["source_path"])
    annotation_path = P8C / "annotations" / f"{args.event_id}.json"
    payload = json.loads(annotation_path.read_text(encoding="utf-8"))
    if sha256(source_path) != payload["source_sha256"]:
        raise SystemExit("Source hash mismatch")
    if payload["review_state"] == "HUMAN_VERIFIED":
        raise SystemExit("Event is already HUMAN_VERIFIED; create a reviewed revision")
    if args.reject:
        payload.update({"review_state": "REJECTED", "promotion_status": "NOT_PROMOTED", "reviewer": args.reviewer, "verified_at": datetime.now(timezone.utc).isoformat(), "rejection": {"code": args.reject, "notes": args.rejection_notes}})
        annotation_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return 0
    for pid, description in (("P-A", args.participant_a_description), ("P-B", args.participant_b_description)):
        if description:
            payload["participants"][pid]["visual_description"] = description
    capture = cv2.VideoCapture(str(source_path))
    if not capture.isOpened():
        raise SystemExit(f"Could not open {source_path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or payload.get("fps") or 15)
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or payload.get("frame_count") or 0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or payload["resolution"][0])
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or payload["resolution"][1])
    payload.update({"fps": fps, "frame_count": count, "resolution": [width, height]})
    session = AnnotationSession(payload, fps, count, DisplayTransform.fit(width, height))
    window, message, exit_requested, verified = "CrashGuard Phase 8C HUMAN annotation", "", False, False
    cached_index, cached_frame = -1, None

    def mouse(event: int, x: int, y: int, _flags: int, _param: object) -> None:
        if event == cv2.EVENT_LBUTTONDOWN:
            session.begin_drag(x, y) if session.mode else session.select_at(x, y)
        elif event == cv2.EVENT_MOUSEMOVE:
            session.update_drag(x, y)
        elif event == cv2.EVENT_LBUTTONUP:
            completed = session.finish_drag(x, y)
            if completed in ("P-A", "P-B"):
                apply_vehicle_class(session, completed, prompt_vehicle_class(completed, payload["participants"][completed]["vehicle_class"]))
            elif completed == "distractor":
                item = session.current["distractors"][session.selected[1]]
                apply_vehicle_class(session, completed, prompt_vehicle_class(item["id"], item["vehicle_class"]))

    cv2.namedWindow(window, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(window, mouse)
    try:
        while not exit_requested:
            if cached_index != session.frame_index:
                capture.set(cv2.CAP_PROP_POS_FRAMES, session.frame_index)
                ok, cached_frame = capture.read()
                if not ok or cached_frame is None:
                    print(f"Could not read frame {session.frame_index}")
                    break
                cached_index = session.frame_index
            frame = cached_frame
            cv2.imshow(window, render(session, frame, args.event_id, message))
            key = cv2.waitKeyEx(max(1, round(1000 / min(fps, 15))) if session.playing else 20)
            if cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                if session.current_is_dirty():
                    session.save_current()
                exit_requested = True
                continue
            if key == -1:
                if session.playing:
                    if session.frame_index < count - 1:
                        session.frame_index += 1
                    else:
                        session.playing = False
                continue
            low, message = key & 0xFF, ""
            if ord("A") <= low <= ord("Z"):
                low += ord("a") - ord("A")
            if key == 27:
                if session.current_is_dirty():
                    session.save_current()
                exit_requested = True
            elif low == ord(" "): session.playing = not session.playing
            elif key in LEFT_KEYS or low == ord("a"): session.navigate(-1)
            elif key in RIGHT_KEYS or low == ord("d"): session.navigate(1)
            elif low == ord("j"): session.navigate(-10)
            elif low == ord("l"): session.navigate(10)
            elif low == ord("g"):
                try: session.jump(int(input(f"\nJump to frame 0..{count - 1}: ")))
                except ValueError: print("Jump cancelled: enter a whole number")
            elif low in map(ord, "1234"):
                session.playing = False
                session.mode = {ord("1"): "P-A", ord("2"): "P-B", ord("3"): "distractor", ord("4"): "collision"}[low]
                session.selected = None
            elif low in PHASE_KEYS: session.snapshot(); session.current["phase"] = PHASE_KEYS[low]
            elif key in DELETE_KEYS: session.delete_selected()
            elif low == ord("r") and session.selected and session.selected[0] in ("P-A", "P-B"):
                session.playing, session.mode = False, session.selected[0]
                message = f"Redraw {session.mode}: drag a replacement box"
            elif low == ord("u"): session.undo()
            elif low == ord("s"):
                session.save_current(); save_payload(annotation_path, session)
                message = f"Saved keyframe {session.frame_index}; saved={len(session.annotations)}"
            elif low == ord("h"): session.help_visible = not session.help_visible
            elif low == ord("c"): session.snapshot(); session.current["contact_status"] = cycle(CONTACT, session.current["contact_status"])
            elif low == ord("f"): session.snapshot(); session.current["contact_confidence"] = cycle(CERTAINTY, session.current["contact_confidence"])
            elif low in (ord("i"), ord("o")) and session.selected and session.selected[0] in ("P-A", "P-B"):
                session.snapshot(); observation = session.current["participant_observations"][session.selected[0]]
                if low == ord("i"):
                    observation["visibility"] = cycle(VISIBILITY, observation["visibility"])
                    if observation["visibility"] in VISIBILITY[3:]: observation["bbox"] = None
                else: observation["occlusion"] = cycle(OCCLUSION, observation["occlusion"])
            elif low in (ord("["), ord("]")):
                session.snapshot(); payload["analysis_start_frame" if low == ord("[") else "analysis_end_frame"] = session.frame_index
            elif low in (ord(","), ord("."), ord("/")):
                session.snapshot(); payload[{ord(","): "contact_start_frame", ord("."): "contact_peak_frame", ord("/"): "contact_end_frame"}[low]] = session.frame_index
            elif low == ord("x"): session.snapshot(); payload["distractors_reviewed"] = True
            elif low == ord("p"):
                pair_errors = pair_confirmation_errors(payload, session.annotations)
                if pair_errors:
                    print("\nPAIR CONFIRMATION blocked:")
                    for error in pair_errors: print(f"- {error}")
                    message = f"PAIR BLOCKED ({len(pair_errors)} errors; see terminal)"
                elif input("\nConfirm P-A <-> P-B are the actual collision participants? Y/N: ").strip().upper() == "Y":
                    session.snapshot(); payload["ground_truth_collision_pair"] = ["P-A", "P-B"]; payload["ground_truth_pair_verified"] = True
            elif low == ord("e"):
                session.snapshot()
                if payload.get("event_type_verified"): payload["event_type"] = cycle(EVENT_TYPES, payload["event_type"])
                else: payload["event_type_verified"] = True
                payload["dynamic_history_available"] = payload["event_type"] != "TYPE_C"
            elif low == ord("v"):
                session.sync_payload(); errors = verification_errors(payload)
                if errors:
                    print("\nVERIFY EVENT blocked:")
                    for error in errors: print(f"- {error}")
                    message = f"VERIFY BLOCKED ({len(errors)} errors; see terminal)"
                elif input("\nVERIFY EVENT? type YES: ").strip() == "YES":
                    for row in session.annotations.values(): row["annotation_state"] = "HUMAN_VERIFIED"
                    for pid in ("P-A", "P-B"):
                        visible = [index for index, row in session.annotations.items() if row["participant_observations"][pid]["visibility"] not in VISIBILITY[3:]]
                        payload["participants"][pid].update({"first_visible_frame": min(visible), "last_visible_frame": max(visible)})
                    payload.update({"review_state": "HUMAN_VERIFIED", "promotion_status": "READY_FOR_INTEGRITY_VALIDATION", "reviewer": args.reviewer, "verified_at": datetime.now(timezone.utc).isoformat()})
                    verified, exit_requested = True, True
    finally:
        save_payload(annotation_path, session)
        capture.release()
        cv2.destroyAllWindows()
    print(f"Saved {len(session.annotations)} keyframes; state={'HUMAN_VERIFIED' if verified else payload['review_state']} to {annotation_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
