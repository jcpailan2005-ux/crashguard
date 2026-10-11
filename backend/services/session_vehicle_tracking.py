"""Bounded session-owned association of already accepted detector observations.

No inference, classifier, collision decisions, or preview propagation occurs here.
Uncertain associations start new identities rather than assert a physical handoff.
"""
from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
from scipy.optimize import linear_sum_assignment

from backend.services.vehicle_tracking import TrackState, VehicleTrackingService


@dataclass(frozen=True)
class SessionTrackingConfig:
    max_tracks: int = 256
    history_size: int = 16
    max_missed_frames: int = 4
    max_age_seconds: float = 1.5
    prediction_seconds: float = 0.75
    max_center_distance: float = 0.65  # Relative to vehicle box diagonal.
    max_size_ratio: float = 1.8
    missed_observed_iou: float = 0.25
    ambiguity_margin: float = 0.08

    def __post_init__(self):
        if self.max_tracks < 1 or self.history_size < 2 or self.max_missed_frames < 1:
            raise ValueError("Tracking state bounds must be positive; history needs two entries")
        values = (self.max_age_seconds, self.prediction_seconds,
                  self.max_center_distance, self.max_size_ratio, self.ambiguity_margin)
        if not all(math.isfinite(x) and x > 0 for x in values) or self.max_size_ratio <= 1:
            raise ValueError("Tracking association bounds must be finite and positive")
        if not 0 < self.missed_observed_iou <= 1:
            raise ValueError("Miss recovery needs a positive observed-box overlap gate")


@dataclass(frozen=True)
class TrajectoryPoint:
    timestamp: float
    sequence: int
    bbox: tuple[float, float, float, float]
    center: tuple[float, float]
    width: float
    height: float
    detected: bool
    velocity: tuple[float, float]


@dataclass
class SessionTrack:
    state: TrackState
    history: deque[TrajectoryPoint]
    lifecycle: str = "NEW"
    missed_frames: int = 0
    velocity: tuple[float, float] = (0.0, 0.0)
    last_detected_sequence: int = -1


@dataclass(frozen=True)
class SessionTrackingResult:
    boxes: tuple[dict, ...]
    predicted_tracks: tuple[dict, ...]
    retired_track_ids: tuple[int, ...]
    tracking_ms: float


class SessionVehicleTracker:
    """Owned/serialized by one live worker's lock; never a global ID registry.

    reset is a lifecycle operation, never triggered by an arriving frame. A late
    session therefore cannot roll a current tracker back to a retired session.
    Integer IDs are local and meaningful only with camera_id and session_id.
    """

    def __init__(self, camera_id: str, session_id: str,
                 config: SessionTrackingConfig | None = None):
        self.camera_id = camera_id
        self.config = config or SessionTrackingConfig()
        self.reset(session_id)

    def reset(self, session_id: str | None):
        self.session_id = session_id
        self.tracks: dict[int, SessionTrack] = {}
        self.next_id = 1
        self.last_sequence = -1
        self.last_timestamp: float | None = None
        self.frame_shape: tuple[int, int] | None = None

    def _prediction(self, track: SessionTrack, timestamp: float):
        dt = min(max(0.0, timestamp - track.state.last_seen_at), self.config.prediction_seconds)
        dx, dy = (v * dt for v in track.velocity)
        x1, y1, x2, y2 = track.state.bbox
        return x1 + dx, y1 + dy, x2 + dx, y2 + dy

    def _association_costs(self, candidates, boxes, labels, timestamp):
        # Vectorized bounded geometry avoids a Python loop for each pair. Labels,
        # not model-specific class numbers, establish compatibility.
        a = np.asarray([self._prediction(t, timestamp) for t in candidates])[:, None, :]
        b = np.asarray(boxes)[None, :, :]
        aw, ah, bw, bh = a[..., 2]-a[..., 0], a[..., 3]-a[..., 1], b[..., 2]-b[..., 0], b[..., 3]-b[..., 1]
        size_ratio = np.maximum.reduce([aw/bw, bw/aw, ah/bh, bh/ah])
        displacement = np.hypot((a[..., 0]+a[..., 2]-b[..., 0]-b[..., 2])/2,
                                (a[..., 1]+a[..., 3]-b[..., 1]-b[..., 3])/2)
        distance = displacement / np.maximum(1.0, np.maximum(np.hypot(aw, ah), np.hypot(bw, bh)))
        intersection = np.maximum(0, np.minimum(a[..., 2], b[..., 2])-np.maximum(a[..., 0], b[..., 0])) * np.maximum(
            0, np.minimum(a[..., 3], b[..., 3])-np.maximum(a[..., 1], b[..., 1]))
        iou = intersection / np.maximum(1.0, aw*ah+bw*bh-intersection)
        compatible = np.asarray([t.state.class_name for t in candidates])[:, None] == np.asarray(labels)[None, :]
        valid = compatible & (size_ratio <= self.config.max_size_ratio) & (distance <= self.config.max_center_distance)
        # A lost broad box must not claim a different nearby vehicle merely
        # because its extrapolated center is plausible. Recovery needs support
        # from both the last real observation and the motion prediction.
        observed = np.asarray([t.state.bbox for t in candidates])[:, None, :]
        ow, oh = observed[..., 2]-observed[..., 0], observed[..., 3]-observed[..., 1]
        old_intersection = np.maximum(0, np.minimum(observed[..., 2], b[..., 2])-np.maximum(observed[..., 0], b[..., 0])) * np.maximum(
            0, np.minimum(observed[..., 3], b[..., 3])-np.maximum(observed[..., 1], b[..., 1]))
        old_iou = old_intersection / np.maximum(1.0, ow*oh+bw*bh-old_intersection)
        missed = np.asarray([t.missed_frames > 0 for t in candidates])[:, None]
        valid &= ~missed | ((old_iou >= self.config.missed_observed_iou) & (iou >= 0.10))
        return np.where(valid, 0.65*(1-iou)+0.35*distance/self.config.max_center_distance, 1e6)

    def _packet(self, track: SessionTrack, bbox, *, detected: bool, sequence: int, timestamp: float):
        x1, y1, x2, y2 = bbox
        return dict(cameraId=self.camera_id, sessionId=self.session_id,
                    trackId=track.state.track_id, label=track.state.class_name,
                    confidence=track.state.confidence, x=x1, y=y1, width=x2-x1, height=y2-y1,
                    sequence=sequence, capturedMonotonic=timestamp,
                    lastDetectedSequence=track.last_detected_sequence,
                    observationKind="DETECTED" if detected else "PREDICTED",
                    detected=detected, collisionObservation=detected, trackLifecycle=track.lifecycle)

    def update(self, session_id: str, sequence: int, timestamp: float,
               detections: Sequence[Mapping], *, frame_width: int, frame_height: int):
        started = time.perf_counter()
        if session_id != self.session_id or self.session_id is None:
            raise ValueError("Discarded tracker observation from retired camera session")
        if (sequence <= self.last_sequence or not math.isfinite(timestamp)
                or (self.last_timestamp is not None and timestamp < self.last_timestamp)):
            raise ValueError("Duplicate or late tracker observation")
        if frame_width <= 0 or frame_height <= 0 or len(detections) > self.config.max_tracks:
            raise ValueError("Tracking frame exceeds bounded capacity or has invalid dimensions")
        # Reuse the existing tested detector-coordinate parser and TrackState.
        boxes = [VehicleTrackingService._xyxy(d) for d in detections]
        if any(not all(math.isfinite(v) for v in b) or b[2] <= b[0] or b[3] <= b[1] for b in boxes):
            raise ValueError("Invalid accepted vehicle box")
        labels = [str(d.get("label") or "vehicle").lower() for d in detections]
        retired = []
        shape = (frame_width, frame_height)
        for tid, track in list(self.tracks.items()):
            if (timestamp-track.state.last_seen_at > self.config.max_age_seconds
                    or track.missed_frames >= self.config.max_missed_frames
                    or (self.frame_shape is not None and self.frame_shape != shape)):
                track.lifecycle = "RETIRED"
                retired.append(tid)
                del self.tracks[tid]
        candidates = list(self.tracks.values())
        matches = {}
        if candidates and boxes:
            costs = self._association_costs(candidates, boxes, labels, timestamp)
            rows, cols = linear_sum_assignment(costs)
            selected_costs = costs[rows, cols]
            limits = selected_costs + self.config.ambiguity_margin
            # Reject ties/ambiguous crossings on either side of assignment.
            row_unique = np.sum(costs[rows, :] <= limits[:, None], axis=1) == 1
            col_unique = np.sum(costs[:, cols] <= limits[None, :], axis=0) == 1
            for r, c, cost, unique in zip(rows, cols, selected_costs, row_unique & col_unique):
                if cost >= 1e6 or not unique:
                    continue
                matches[int(c)] = candidates[r]
        matched_ids = {t.state.track_id for t in matches.values()}
        unmatched = [t for t in candidates if t.state.track_id not in matched_ids]
        # Preserve all accepted detections; evict missed continuity first at capacity.
        needed = len(boxes)-len(matches)
        for track in sorted(unmatched, key=lambda t: t.state.last_seen_at):
            if len(self.tracks)+needed <= self.config.max_tracks:
                break
            tid = track.state.track_id
            track.lifecycle = "RETIRED"
            retired.append(tid)
            del self.tracks[tid]
        output = []
        for index, (detection, bbox, label) in enumerate(zip(detections, boxes, labels)):
            track = matches.get(index)  # Only current-frame association, never identity.
            if track is None:
                state = TrackState.create(track_id=self.next_id, camera_id=self.camera_id,
                    class_id=VehicleTrackingService._class_id(detection), class_name=label,
                    history_size=self.config.history_size, timestamp=timestamp)
                track = SessionTrack(state, deque(maxlen=self.config.history_size))
                self.tracks[self.next_id] = track
                self.next_id += 1
            else:
                dt = timestamp-track.state.last_seen_at
                cx, cy = (bbox[0]+bbox[2])/2, (bbox[1]+bbox[3])/2
                if dt > 0:
                    track.velocity = ((cx-track.state.center[0])/dt, (cy-track.state.center[1])/dt)
                track.lifecycle = "ACTIVE"
            track.missed_frames = 0
            track.last_detected_sequence = sequence
            track.state.add_observation(timestamp=timestamp, bbox=bbox,
                confidence=float(detection.get("confidence", detection.get("score", 0.0))),
                frame_width=frame_width, frame_height=frame_height)
            track.history.append(TrajectoryPoint(timestamp, sequence, bbox, track.state.center,
                bbox[2]-bbox[0], bbox[3]-bbox[1], True, track.velocity))
            # Preserve exact detector coordinates/class/confidence and array order.
            packet = self._packet(track, bbox, detected=True, sequence=sequence, timestamp=timestamp)
            output.append({**packet, **dict(detection), "trackId": track.state.track_id})
        predicted = []
        for track in unmatched:
            if track.state.track_id not in self.tracks:
                continue
            track.missed_frames += 1
            if track.missed_frames >= self.config.max_missed_frames:
                track.lifecycle = "RETIRED"
                retired.append(track.state.track_id)
                del self.tracks[track.state.track_id]
                continue
            track.lifecycle = "TEMPORARILY_MISSED"
            bbox = self._prediction(track, timestamp)
            center = ((bbox[0]+bbox[2])/2, (bbox[1]+bbox[3])/2)
            track.history.append(TrajectoryPoint(timestamp, sequence, bbox, center,
                bbox[2]-bbox[0], bbox[3]-bbox[1], False, track.velocity))
            predicted.append(self._packet(track, bbox, detected=False, sequence=sequence, timestamp=timestamp))
        self.last_sequence, self.last_timestamp, self.frame_shape = sequence, timestamp, shape
        return SessionTrackingResult(tuple(output), tuple(predicted), tuple(retired),
                                     (time.perf_counter()-started)*1000)
