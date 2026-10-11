"""Per-camera ByteTrack integration with bounded, timestamped track history."""

from __future__ import annotations

import threading
import time
from argparse import Namespace
from collections import deque
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

import numpy as np
from ultralytics.engine.results import Boxes
from ultralytics.trackers.basetrack import BaseTrack
from ultralytics.trackers.byte_tracker import BYTETracker


SUPPORTED_VEHICLE_LABELS = frozenset({"bicycle", "car", "motorcycle", "bus", "truck"})
COCO_VEHICLE_CLASS_IDS = {
    "bicycle": 1,
    "car": 2,
    "motorcycle": 3,
    "bus": 5,
    "truck": 7,
}


@dataclass(frozen=True)
class TrackingConfig:
    """ByteTrack and retention settings for analyzed (not preview) frames."""

    min_confidence: float = 0.20
    track_high_threshold: float = 0.35
    track_low_threshold: float = 0.10
    new_track_threshold: float = 0.35
    match_threshold: float = 0.80
    track_buffer_frames: int = 12
    max_age_seconds: float = 3.0
    reset_gap_seconds: float = 6.0
    history_size: int = 16
    nominal_fps: int = 2
    max_cameras: int = 512
    fuse_score: bool = True

    def __post_init__(self) -> None:
        for name in (
            "min_confidence",
            "track_high_threshold",
            "track_low_threshold",
            "new_track_threshold",
            "match_threshold",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1.")
        if self.track_low_threshold > self.track_high_threshold:
            raise ValueError("track_low_threshold cannot exceed track_high_threshold.")
        if self.track_buffer_frames < 1:
            raise ValueError("track_buffer_frames must be positive.")
        if self.max_age_seconds <= 0 or self.reset_gap_seconds <= 0:
            raise ValueError("Track age and reset windows must be positive.")
        if self.history_size < 2:
            raise ValueError("history_size must be at least 2.")
        if self.nominal_fps < 1:
            raise ValueError("nominal_fps must be positive.")
        if self.max_cameras < 1:
            raise ValueError("max_cameras must be positive.")

    def bytetrack_args(self) -> Namespace:
        return Namespace(
            tracker_type="bytetrack",
            track_high_thresh=self.track_high_threshold,
            track_low_thresh=self.track_low_threshold,
            new_track_thresh=self.new_track_threshold,
            match_thresh=self.match_threshold,
            track_buffer=self.track_buffer_frames,
            fuse_score=self.fuse_score,
        )


@dataclass(frozen=True)
class TrackObservation:
    timestamp: float
    bbox: tuple[float, float, float, float]
    center_x: float
    center_y: float
    center_x_norm: float
    center_y_norm: float
    confidence: float


@dataclass
class TrackState:
    track_id: int
    camera_id: str
    class_id: int
    class_name: str
    confidence: float
    bbox: tuple[float, float, float, float]
    center: tuple[float, float]
    center_normalized: tuple[float, float]
    first_seen_at: float
    last_seen_at: float
    history: deque[TrackObservation] = field(default_factory=deque)

    @classmethod
    def create(
        cls,
        *,
        track_id: int,
        camera_id: str,
        class_id: int,
        class_name: str,
        history_size: int,
        timestamp: float,
    ) -> "TrackState":
        return cls(
            track_id=int(track_id),
            camera_id=camera_id,
            class_id=int(class_id),
            class_name=class_name,
            confidence=0.0,
            bbox=(0.0, 0.0, 0.0, 0.0),
            center=(0.0, 0.0),
            center_normalized=(0.0, 0.0),
            first_seen_at=float(timestamp),
            last_seen_at=float(timestamp),
            history=deque(maxlen=history_size),
        )

    def add_observation(
        self,
        *,
        timestamp: float,
        bbox: Sequence[float],
        confidence: float,
        frame_width: int,
        frame_height: int,
    ) -> TrackObservation:
        x1, y1, x2, y2 = (float(value) for value in bbox)
        center_x = (x1 + x2) / 2.0
        center_y = (y1 + y2) / 2.0
        width = max(1, int(frame_width))
        height = max(1, int(frame_height))
        observation = TrackObservation(
            timestamp=float(timestamp),
            bbox=(x1, y1, x2, y2),
            center_x=center_x,
            center_y=center_y,
            center_x_norm=center_x / width,
            center_y_norm=center_y / height,
            confidence=max(0.0, min(1.0, float(confidence))),
        )
        self.class_id = int(self.class_id)
        self.confidence = observation.confidence
        self.bbox = observation.bbox
        self.center = (center_x, center_y)
        self.center_normalized = (
            observation.center_x_norm,
            observation.center_y_norm,
        )
        self.last_seen_at = observation.timestamp
        self.history.append(observation)
        return observation


@dataclass(frozen=True)
class TrackingFrameResult:
    camera_id: str
    active_tracks: tuple[TrackState, ...]
    retained_track_count: int
    tracking_ms: float
    tracker_name: str = "ByteTrack"
    reset_due_to_gap: bool = False


@dataclass
class _CameraTrackerState:
    tracker: BYTETracker
    tracks: dict[int, TrackState] = field(default_factory=dict)
    last_timestamp: float | None = None


class VehicleTrackingService:
    """Own one ByteTrack instance and track-state map per camera.

    Inference happens before this service is called. The lock therefore only
    protects inexpensive tracker/state mutation and does not serialize YOLO.
    """

    def __init__(self, config: TrackingConfig | None = None) -> None:
        self.config = config or TrackingConfig()
        self._cameras: dict[str, _CameraTrackerState] = {}
        self._lock = threading.RLock()

    def _new_tracker(self) -> BYTETracker:
        # Ultralytics resets BaseTrack's process-wide counter in BYTETracker's
        # constructor. Restore it so adding/resetting Camera B cannot reuse an
        # active ID inside Camera A. IDs remain camera-session evidence only.
        previous_count = BaseTrack._count
        tracker = BYTETracker(
            self.config.bytetrack_args(), frame_rate=self.config.nominal_fps
        )
        BaseTrack._count = max(previous_count, BaseTrack._count)
        return tracker

    def _new_camera_state(self) -> _CameraTrackerState:
        return _CameraTrackerState(tracker=self._new_tracker())

    @staticmethod
    def _class_id(detection: Mapping) -> int:
        raw = detection.get("classId", detection.get("class_id"))
        if raw is not None:
            try:
                return int(raw)
            except (TypeError, ValueError):
                pass
        return COCO_VEHICLE_CLASS_IDS.get(str(detection.get("label") or "").lower(), 2)

    @staticmethod
    def _xyxy(detection: Mapping) -> tuple[float, float, float, float]:
        if detection.get("box") is not None and len(detection["box"]) >= 4:
            x1, y1, x2, y2 = detection["box"][:4]
            return float(x1), float(y1), float(x2), float(y2)
        x1 = float(detection.get("x") or 0.0)
        y1 = float(detection.get("y") or 0.0)
        return (
            x1,
            y1,
            x1 + float(detection.get("width") or 0.0),
            y1 + float(detection.get("height") or 0.0),
        )

    def _boxes(self, detections: Iterable[Mapping], frame_shape: tuple[int, int]) -> Boxes:
        rows = []
        for detection in detections:
            confidence = float(detection.get("confidence", detection.get("score", 0.0)) or 0.0)
            label = str(detection.get("label") or "car").lower()
            if confidence < self.config.min_confidence or label not in SUPPORTED_VEHICLE_LABELS:
                continue
            x1, y1, x2, y2 = self._xyxy(detection)
            if x2 <= x1 or y2 <= y1:
                continue
            rows.append((x1, y1, x2, y2, confidence, self._class_id(detection)))
        array = np.asarray(rows, dtype=np.float32)
        if not rows:
            array = np.empty((0, 6), dtype=np.float32)
        return Boxes(array, frame_shape)

    def update(
        self,
        camera_id: str,
        detections: Iterable[Mapping],
        *,
        frame_width: int,
        frame_height: int,
        timestamp: float | None = None,
        frame: np.ndarray | None = None,
    ) -> TrackingFrameResult:
        timestamp = time.monotonic() if timestamp is None else float(timestamp)
        camera_id = camera_id or "unknown-camera"
        started = time.perf_counter()
        reset_due_to_gap = False
        with self._lock:
            state = self._cameras.get(camera_id)
            if state is None:
                if len(self._cameras) >= self.config.max_cameras:
                    oldest_camera = min(
                        self._cameras,
                        key=lambda key: self._cameras[key].last_timestamp
                        if self._cameras[key].last_timestamp is not None
                        else float("-inf"),
                    )
                    self._cameras.pop(oldest_camera, None)
                state = self._new_camera_state()
                self._cameras[camera_id] = state
            elif (
                state.last_timestamp is not None
                and timestamp - state.last_timestamp > self.config.reset_gap_seconds
            ):
                state = self._new_camera_state()
                self._cameras[camera_id] = state
                reset_due_to_gap = True

            boxes = self._boxes(detections, (int(frame_height), int(frame_width)))
            tracked_rows = state.tracker.update(boxes, img=frame)
            active: list[TrackState] = []
            for row in tracked_rows:
                x1, y1, x2, y2 = (float(value) for value in row[:4])
                track_id = int(row[4])
                confidence = float(row[5])
                class_id = int(row[6])
                class_name = next(
                    (name for name, value in COCO_VEHICLE_CLASS_IDS.items() if value == class_id),
                    str(class_id),
                )
                track = state.tracks.get(track_id)
                if track is None:
                    track = TrackState.create(
                        track_id=track_id,
                        camera_id=camera_id,
                        class_id=class_id,
                        class_name=class_name,
                        history_size=self.config.history_size,
                        timestamp=timestamp,
                    )
                    state.tracks[track_id] = track
                track.class_id = class_id
                track.class_name = class_name
                track.add_observation(
                    timestamp=timestamp,
                    bbox=(x1, y1, x2, y2),
                    confidence=confidence,
                    frame_width=frame_width,
                    frame_height=frame_height,
                )
                active.append(track)

            stale_ids = [
                track_id
                for track_id, track in state.tracks.items()
                if timestamp - track.last_seen_at > self.config.max_age_seconds
            ]
            for track_id in stale_ids:
                state.tracks.pop(track_id, None)
            state.last_timestamp = timestamp
            retained_count = len(state.tracks)

        return TrackingFrameResult(
            camera_id=camera_id,
            active_tracks=tuple(active),
            retained_track_count=retained_count,
            tracking_ms=(time.perf_counter() - started) * 1000.0,
            reset_due_to_gap=reset_due_to_gap,
        )

    def get_tracks(self, camera_id: str) -> tuple[TrackState, ...]:
        with self._lock:
            state = self._cameras.get(camera_id)
            return tuple(state.tracks.values()) if state is not None else ()

    def reset_camera(self, camera_id: str) -> None:
        with self._lock:
            self._cameras.pop(camera_id or "unknown-camera", None)

    def reset_all(self) -> None:
        with self._lock:
            self._cameras.clear()
