"""Bounded CrashGuard-level vehicle identity continuity above ByteTrack."""

from __future__ import annotations

import json
import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

from backend.services.vehicle_tracking import TrackObservation, TrackState


VEHICLE_LABELS = frozenset(
    {"bicycle", "car", "truck", "bus", "van", "motorcycle", "motorbike", "moped", "vehicle"}
)


@dataclass(frozen=True)
class LogicalContinuityConfig:
    max_handoff_seconds: float = 1.0
    max_center_displacement_normalized: float = 0.15
    minimum_size_similarity: float = 0.30
    minimum_handoff_score: float = 0.62
    ambiguity_margin: float = 0.08
    subtype_change_max_displacement_normalized: float = 0.06
    max_prediction_error_normalized: float = 0.12
    history_size: int = 16
    max_identities_per_camera: int = 64
    max_cameras: int = 512
    debug_log: bool = False

    def __post_init__(self) -> None:
        if not 0.0 < self.max_handoff_seconds <= 5.0:
            raise ValueError("Logical handoff window must be in (0, 5] seconds.")
        for name in (
            "max_center_displacement_normalized",
            "minimum_size_similarity",
            "minimum_handoff_score",
            "ambiguity_margin",
            "subtype_change_max_displacement_normalized",
            "max_prediction_error_normalized",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between zero and one.")
        if min(self.history_size, self.max_identities_per_camera, self.max_cameras) < 1:
            raise ValueError("Logical continuity bounds must be positive.")


@dataclass(frozen=True)
class HandoffEvidence:
    score: float
    gap_seconds: float
    center_displacement: float
    spatial_score: float
    iou: float
    size_similarity: float
    class_compatibility: float
    time_score: float
    prediction_score: float
    trajectory_score: float
    collision_region_support: bool
    accepted: bool
    reason: str


@dataclass
class LogicalTrackState:
    """TrackState-compatible logical observation consumed only by collision analysis."""

    track_id: int
    logical_vehicle_id: str
    camera_id: str
    raw_track_id: int | None
    last_raw_track_id: int | None
    state: str
    logical_class: str
    class_name: str
    previous_detector_class: str | None
    confidence: float
    bbox: tuple[float, float, float, float]
    center: tuple[float, float]
    center_normalized: tuple[float, float]
    first_seen_at: float
    last_seen_at: float
    history: deque[TrackObservation]
    observation_source: str
    motion_observed: bool
    has_tracked_motion_history: bool
    collision_region_member: bool = False


@dataclass(frozen=True)
class LogicalContinuityResult:
    camera_id: str
    active_tracks: tuple[LogicalTrackState, ...]
    logical_pairs: tuple[tuple[str, str], ...]
    handoff_attempts: int
    accepted_handoffs: int
    rejected_handoffs: int
    ambiguous_handoffs: int
    provisional_observations: int
    expired_identities: int
    expired_logical_track_ids: tuple[int, ...]
    processing_ms: float
    handoff_matching_ms: float
    diagnostics: tuple[dict, ...]


@dataclass
class _CameraState:
    identities: dict[int, LogicalTrackState] = field(default_factory=dict)
    raw_to_logical: dict[int, int] = field(default_factory=dict)
    next_id: int = 1
    last_timestamp: float | None = None
    last_result: LogicalContinuityResult | None = None


@dataclass(frozen=True)
class _Observation:
    bbox: tuple[float, float, float, float]
    confidence: float
    detector_class: str
    raw_track_id: int | None
    source: str
    collision_region_support: bool
    raw_track: TrackState | None


def _xyxy(item: Mapping) -> tuple[float, float, float, float]:
    if item.get("box") is not None and len(item["box"]) >= 4:
        return tuple(float(value) for value in item["box"][:4])  # type: ignore[return-value]
    x1, y1 = float(item.get("x") or 0.0), float(item.get("y") or 0.0)
    return (
        x1,
        y1,
        x1 + float(item.get("width") or 0.0),
        y1 + float(item.get("height") or 0.0),
    )


def _center(box: Sequence[float]) -> tuple[float, float]:
    return ((float(box[0]) + float(box[2])) / 2.0, (float(box[1]) + float(box[3])) / 2.0)


def _iou(a: Sequence[float], b: Sequence[float]) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - intersection
    return intersection / union if union > 0.0 else 0.0


def _size_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    return min(area_a, area_b) / max(area_a, area_b) if max(area_a, area_b) > 0 else 0.0


def _eligible(detection: Mapping) -> bool:
    label = str(detection.get("label") or "").lower()
    state = str(detection.get("detectionState") or "")
    return label in VEHICLE_LABELS and (
        state == "TRUSTED" or (state == "CANDIDATE" and bool(detection.get("candidateSupported")))
    )


class LogicalVehicleContinuityService:
    def __init__(self, config: LogicalContinuityConfig | None = None) -> None:
        self.config = config or LogicalContinuityConfig()
        self._cameras: dict[str, _CameraState] = {}
        self._lock = threading.RLock()

    def _camera(self, camera_id: str) -> _CameraState:
        state = self._cameras.get(camera_id)
        if state is None:
            if len(self._cameras) >= self.config.max_cameras:
                oldest = min(
                    self._cameras,
                    key=lambda key: self._cameras[key].last_timestamp or float("-inf"),
                )
                self._cameras.pop(oldest, None)
            state = _CameraState()
            self._cameras[camera_id] = state
        return state

    @staticmethod
    def _collision_support(box: Sequence[float], collision_pair_boxes: Sequence[Mapping]) -> bool:
        return any(_iou(box, _xyxy(pair_box)) >= 0.20 for pair_box in collision_pair_boxes)

    def _observations(
        self,
        raw_tracks: Sequence[TrackState],
        detections: Iterable[Mapping],
        collision_pair_boxes: Sequence[Mapping],
    ) -> list[_Observation]:
        eligible = [dict(item) for item in detections if _eligible(item)]
        unused = set(range(len(eligible)))
        observations: list[_Observation] = []
        for track in raw_tracks:
            ranked = sorted(
                ((_iou(track.bbox, _xyxy(eligible[index])), index) for index in unused),
                reverse=True,
            )
            match_index = ranked[0][1] if ranked and ranked[0][0] >= 0.20 else None
            detection = eligible[match_index] if match_index is not None else None
            if match_index is not None:
                unused.remove(match_index)
            bbox = track.bbox
            observations.append(
                _Observation(
                    bbox=bbox,
                    confidence=float(detection.get("confidence") if detection else track.confidence),
                    detector_class=str(detection.get("label") if detection else track.class_name).lower(),
                    raw_track_id=track.track_id,
                    source="trusted_track",
                    collision_region_support=self._collision_support(bbox, collision_pair_boxes),
                    raw_track=track,
                )
            )
        for index in sorted(unused):
            detection = eligible[index]
            bbox = _xyxy(detection)
            observations.append(
                _Observation(
                    bbox=bbox,
                    confidence=float(detection.get("confidence", detection.get("score", 0.0)) or 0.0),
                    detector_class=str(detection.get("label") or "vehicle").lower(),
                    raw_track_id=None,
                    source=(
                        "candidate_supported"
                        if detection.get("detectionState") == "CANDIDATE"
                        else "trusted_untracked"
                    ),
                    collision_region_support=self._collision_support(bbox, collision_pair_boxes),
                    raw_track=None,
                )
            )
        return observations

    def _predicted_center(
        self, identity: LogicalTrackState, timestamp: float, frame_width: int, frame_height: int
    ) -> tuple[float, float]:
        if not identity.has_tracked_motion_history or len(identity.history) < 2:
            return identity.center_normalized
        previous, latest = identity.history[-2], identity.history[-1]
        elapsed = latest.timestamp - previous.timestamp
        if elapsed <= 1e-6:
            return identity.center_normalized
        gap = timestamp - latest.timestamp
        vx = (latest.center_x_norm - previous.center_x_norm) / elapsed
        vy = (latest.center_y_norm - previous.center_y_norm) / elapsed
        return latest.center_x_norm + vx * gap, latest.center_y_norm + vy * gap

    def _handoff_evidence(
        self,
        identity: LogicalTrackState,
        observation: _Observation,
        *,
        timestamp: float,
        frame_width: int,
        frame_height: int,
    ) -> HandoffEvidence:
        gap = timestamp - identity.last_seen_at
        if gap < -1e-6 or gap > self.config.max_handoff_seconds:
            return HandoffEvidence(0, gap, 1, 0, 0, 0, 0, 0, 0, 0, observation.collision_region_support, False, "handoff_window_expired")
        if identity.logical_class != "vehicle" or observation.detector_class not in VEHICLE_LABELS:
            return HandoffEvidence(0, gap, 1, 0, 0, 0, 0, 0, 0, 0, observation.collision_region_support, False, "semantic_group_mismatch")
        old_center = identity.center_normalized
        new_center_px = _center(observation.bbox)
        new_center = (new_center_px[0] / max(1, frame_width), new_center_px[1] / max(1, frame_height))
        displacement = math.hypot(new_center[0] - old_center[0], new_center[1] - old_center[1])
        if displacement > self.config.max_center_displacement_normalized:
            return HandoffEvidence(0, gap, displacement, 0, 0, 0, 0, 0, 0, 0, observation.collision_region_support, False, "spatial_displacement_exceeded")
        size = _size_similarity(identity.bbox, observation.bbox)
        if size < self.config.minimum_size_similarity:
            return HandoffEvidence(0, gap, displacement, 0, 0, size, 0, 0, 0, 0, observation.collision_region_support, False, "size_similarity_below_minimum")
        exact_class = identity.class_name == observation.detector_class
        class_score = 1.0 if exact_class else 0.65
        if not exact_class and displacement > self.config.subtype_change_max_displacement_normalized:
            return HandoffEvidence(0, gap, displacement, 0, 0, size, class_score, 0, 0, 0, observation.collision_region_support, False, "subtype_change_requires_strong_spatial_match")
        predicted = self._predicted_center(identity, timestamp, frame_width, frame_height)
        prediction_error = math.hypot(new_center[0] - predicted[0], new_center[1] - predicted[1])
        if identity.has_tracked_motion_history and prediction_error > self.config.max_prediction_error_normalized:
            return HandoffEvidence(0, gap, displacement, 0, 0, size, class_score, 0, 0, 0, observation.collision_region_support, False, "prediction_error_exceeded")
        trajectory_score = 1.0
        if identity.has_tracked_motion_history and len(identity.history) >= 2:
            previous, latest = identity.history[-2], identity.history[-1]
            old_dx = latest.center_x_norm - previous.center_x_norm
            old_dy = latest.center_y_norm - previous.center_y_norm
            new_dx = new_center[0] - latest.center_x_norm
            new_dy = new_center[1] - latest.center_y_norm
            old_speed, new_displacement = math.hypot(old_dx, old_dy), math.hypot(new_dx, new_dy)
            if old_speed > 0.01 and new_displacement > 0.015:
                cosine = (old_dx * new_dx + old_dy * new_dy) / (old_speed * new_displacement)
                trajectory_score = max(0.0, min(1.0, (cosine + 1.0) / 2.0))
                if cosine < -0.20:
                    return HandoffEvidence(0, gap, displacement, 0, 0, size, class_score, 0, 0, trajectory_score, observation.collision_region_support, False, "trajectory_mismatch")
        spatial = 1.0 - displacement / self.config.max_center_displacement_normalized
        overlap = _iou(identity.bbox, observation.bbox)
        time_score = 1.0 - max(0.0, gap) / self.config.max_handoff_seconds
        prediction_score = 1.0 - min(1.0, prediction_error / self.config.max_prediction_error_normalized)
        score = (
            0.28 * spatial
            + 0.14 * overlap
            + 0.14 * size
            + 0.10 * class_score
            + 0.10 * time_score
            + 0.10 * prediction_score
            + 0.08 * trajectory_score
            + 0.06 * float(observation.collision_region_support)
        )
        accepted = score >= self.config.minimum_handoff_score
        return HandoffEvidence(
            score, gap, displacement, spatial, overlap, size, class_score, time_score,
            prediction_score, trajectory_score, observation.collision_region_support,
            accepted, "accepted" if accepted else "handoff_score_below_minimum",
        )

    def _new_identity(
        self,
        camera: _CameraState,
        camera_id: str,
        observation: _Observation,
        timestamp: float,
        frame_width: int,
        frame_height: int,
    ) -> LogicalTrackState:
        numeric_id = camera.next_id
        camera.next_id += 1
        identity = LogicalTrackState(
            track_id=numeric_id,
            logical_vehicle_id=f"LV-{numeric_id:04d}",
            camera_id=camera_id,
            raw_track_id=observation.raw_track_id,
            last_raw_track_id=observation.raw_track_id,
            state="TRACKED" if observation.raw_track_id is not None else "PROVISIONAL",
            logical_class="vehicle",
            class_name=observation.detector_class,
            previous_detector_class=None,
            confidence=observation.confidence,
            bbox=observation.bbox,
            center=(0.0, 0.0),
            center_normalized=(0.0, 0.0),
            first_seen_at=timestamp,
            last_seen_at=timestamp,
            history=deque(maxlen=self.config.history_size),
            observation_source=observation.source,
            motion_observed=observation.raw_track_id is not None,
            has_tracked_motion_history=observation.raw_track_id is not None,
            collision_region_member=observation.collision_region_support,
        )
        camera.identities[numeric_id] = identity
        self._apply_observation(identity, observation, timestamp, frame_width, frame_height, handoff=False)
        return identity

    @staticmethod
    def _apply_observation(
        identity: LogicalTrackState,
        observation: _Observation,
        timestamp: float,
        frame_width: int,
        frame_height: int,
        *,
        handoff: bool,
    ) -> None:
        previous_raw = identity.raw_track_id
        previous_class = identity.class_name
        x1, y1, x2, y2 = observation.bbox
        center_x, center_y = _center(observation.bbox)
        identity.previous_detector_class = previous_class if previous_class != observation.detector_class else identity.previous_detector_class
        identity.class_name = observation.detector_class
        identity.confidence = observation.confidence
        identity.bbox = observation.bbox
        identity.center = (center_x, center_y)
        identity.center_normalized = (center_x / max(1, frame_width), center_y / max(1, frame_height))
        identity.last_seen_at = timestamp
        identity.raw_track_id = observation.raw_track_id
        if observation.raw_track_id is not None:
            identity.last_raw_track_id = observation.raw_track_id
        identity.state = "TRACKED" if observation.raw_track_id is not None else "PROVISIONAL"
        identity.observation_source = "handoff_recovered" if handoff else observation.source
        identity.motion_observed = observation.raw_track_id is not None
        identity.has_tracked_motion_history = (
            identity.has_tracked_motion_history or observation.raw_track_id is not None
        )
        identity.collision_region_member = observation.collision_region_support
        identity.history.append(
            TrackObservation(
                timestamp=timestamp,
                bbox=(x1, y1, x2, y2),
                center_x=center_x,
                center_y=center_y,
                center_x_norm=identity.center_normalized[0],
                center_y_norm=identity.center_normalized[1],
                confidence=max(0.0, min(1.0, observation.confidence)),
            )
        )
        if previous_raw is not None and observation.raw_track_id is None:
            identity.observation_source = "candidate_supported_handoff"

    def update(
        self,
        camera_id: str,
        raw_tracks: Sequence[TrackState],
        eligible_detections: Iterable[Mapping],
        *,
        frame_width: int,
        frame_height: int,
        timestamp: float | None = None,
        collision_pair_boxes: Sequence[Mapping] = (),
    ) -> LogicalContinuityResult:
        started = time.perf_counter()
        timestamp = time.monotonic() if timestamp is None else float(timestamp)
        camera_id = camera_id or "unknown-camera"
        diagnostics: list[dict] = []
        with self._lock:
            camera = self._camera(camera_id)
            expired_ids = [
                logical_id for logical_id, identity in camera.identities.items()
                if timestamp - identity.last_seen_at > self.config.max_handoff_seconds
            ]
            for logical_id in expired_ids:
                identity = camera.identities.pop(logical_id)
                if identity.raw_track_id is not None:
                    camera.raw_to_logical.pop(identity.raw_track_id, None)
                if identity.last_raw_track_id is not None:
                    camera.raw_to_logical.pop(identity.last_raw_track_id, None)

            observations = self._observations(raw_tracks, eligible_detections, collision_pair_boxes)
            current_raw_ids = {item.raw_track_id for item in observations if item.raw_track_id is not None}
            for identity in camera.identities.values():
                if identity.raw_track_id is not None and identity.raw_track_id not in current_raw_ids:
                    camera.raw_to_logical.pop(identity.raw_track_id, None)
                    identity.last_raw_track_id = identity.raw_track_id
                    identity.raw_track_id = None
                    identity.state = "RECENTLY_LOST"
                    identity.motion_observed = False

            assigned_observations: set[int] = set()
            assigned_identities: set[int] = set()
            active: list[LogicalTrackState] = []
            for index, observation in enumerate(observations):
                if observation.raw_track_id is None:
                    continue
                logical_id = camera.raw_to_logical.get(observation.raw_track_id)
                identity = camera.identities.get(logical_id) if logical_id is not None else None
                if identity is None:
                    continue
                self._apply_observation(identity, observation, timestamp, frame_width, frame_height, handoff=False)
                assigned_observations.add(index)
                assigned_identities.add(identity.track_id)
                active.append(identity)

            matching_started = time.perf_counter()
            candidates: dict[int, list[tuple[HandoffEvidence, int]]] = {}
            attempted_observations: set[int] = set()
            evaluated: dict[int, list[HandoffEvidence]] = {}
            for index, observation in enumerate(observations):
                if index in assigned_observations:
                    continue
                scored = []
                evidence_rows = []
                for logical_id, identity in camera.identities.items():
                    if logical_id in assigned_identities:
                        continue
                    evidence = self._handoff_evidence(
                        identity,
                        observation,
                        timestamp=timestamp,
                        frame_width=frame_width,
                        frame_height=frame_height,
                    )
                    evidence_rows.append(evidence)
                    if evidence.accepted:
                        scored.append((evidence, logical_id))
                if evidence_rows:
                    attempted_observations.add(index)
                evaluated[index] = evidence_rows
                candidates[index] = sorted(scored, key=lambda item: item[0].score, reverse=True)

            ambiguous: set[int] = set()
            for index, scored in candidates.items():
                if len(scored) >= 2 and scored[0][0].score - scored[1][0].score < self.config.ambiguity_margin:
                    ambiguous.add(index)
            requests: dict[int, list[tuple[float, int]]] = {}
            for index, scored in candidates.items():
                if index not in ambiguous and scored:
                    requests.setdefault(scored[0][1], []).append((scored[0][0].score, index))
            for logical_id, requested in requests.items():
                requested.sort(reverse=True)
                if len(requested) >= 2 and requested[0][0] - requested[1][0] < self.config.ambiguity_margin:
                    ambiguous.update(index for _score, index in requested)

            accepted = 0
            ambiguous_count = len(ambiguous)
            for index, observation in enumerate(observations):
                if index in assigned_observations:
                    continue
                scored = candidates[index]
                if index in ambiguous:
                    diagnostics.append({"handoff": False, "reason": "ambiguous_candidates", "rawTrackId": observation.raw_track_id})
                    identity = self._new_identity(camera, camera_id, observation, timestamp, frame_width, frame_height)
                elif scored and scored[0][1] not in assigned_identities:
                    evidence, logical_id = scored[0]
                    identity = camera.identities[logical_id]
                    old_track = identity.last_raw_track_id
                    self._apply_observation(identity, observation, timestamp, frame_width, frame_height, handoff=True)
                    assigned_identities.add(logical_id)
                    accepted += 1
                    diagnostics.append(
                        {
                            "logicalVehicleId": identity.logical_vehicle_id,
                            "oldTrackId": old_track,
                            "newTrackId": observation.raw_track_id,
                            "handoff": True,
                            "handoffScore": round(evidence.score, 4),
                            "gapMs": round(evidence.gap_seconds * 1000.0, 3),
                            "spatialScore": round(evidence.spatial_score, 4),
                            "iou": round(evidence.iou, 4),
                            "sizeScore": round(evidence.size_similarity, 4),
                            "classCompatible": True,
                            "collisionRegionSupport": evidence.collision_region_support,
                            "source": observation.source,
                        }
                    )
                else:
                    # New no-track identities are collision-analysis support,
                    # not a second general-purpose tracker. They start only
                    # when the deterministic Phase 4 pair prefilter places the
                    # eligible observation in the current collision region.
                    if (
                        observation.raw_track_id is None
                        and not observation.collision_region_support
                    ):
                        continue
                    if index in attempted_observations:
                        reasons = [row.reason for row in evaluated.get(index, ())]
                        diagnostics.append(
                            {
                                "handoff": False,
                                "reason": reasons[0] if len(set(reasons)) == 1 else "no_unique_candidate_passed_gates",
                                "rawTrackId": observation.raw_track_id,
                            }
                        )
                    identity = self._new_identity(camera, camera_id, observation, timestamp, frame_width, frame_height)
                    if observation.raw_track_id is None:
                        diagnostics.append(
                            {
                                "logicalVehicleId": identity.logical_vehicle_id,
                                "state": "provisional",
                                "rawTrackId": None,
                                "support": observation.source,
                                "collisionRegionSupport": observation.collision_region_support,
                                "motionObserved": False,
                            }
                        )
                if observation.raw_track_id is not None:
                    camera.raw_to_logical[observation.raw_track_id] = identity.track_id
                assigned_observations.add(index)
                assigned_identities.add(identity.track_id)
                if identity.raw_track_id is not None or identity.collision_region_member:
                    active.append(identity)

            if len(camera.identities) > self.config.max_identities_per_camera:
                removable = sorted(
                    (identity for identity in camera.identities.values() if identity.track_id not in assigned_identities),
                    key=lambda identity: identity.last_seen_at,
                )
                while len(camera.identities) > self.config.max_identities_per_camera and removable:
                    removed = removable.pop(0)
                    camera.identities.pop(removed.track_id, None)
                    if removed.last_raw_track_id is not None:
                        camera.raw_to_logical.pop(removed.last_raw_track_id, None)

            logical_pairs: list[tuple[str, str]] = []
            region_members = [identity for identity in active if identity.collision_region_member]
            if len(region_members) == 2:
                logical_pairs.append(tuple(sorted((region_members[0].logical_vehicle_id, region_members[1].logical_vehicle_id))))
            matching_ms = (time.perf_counter() - matching_started) * 1000.0
            camera.last_timestamp = timestamp
            result = LogicalContinuityResult(
                camera_id=camera_id,
                active_tracks=tuple(active),
                logical_pairs=tuple(logical_pairs),
                handoff_attempts=len(attempted_observations),
                accepted_handoffs=accepted,
                rejected_handoffs=max(0, len(attempted_observations) - accepted),
                ambiguous_handoffs=ambiguous_count,
                provisional_observations=sum(
                    identity.raw_track_id is None
                    and identity.collision_region_member
                    for identity in active
                ),
                expired_identities=len(expired_ids),
                expired_logical_track_ids=tuple(expired_ids),
                processing_ms=(time.perf_counter() - started) * 1000.0,
                handoff_matching_ms=matching_ms,
                diagnostics=tuple(diagnostics),
            )
            camera.last_result = result
            if self.config.debug_log:
                for diagnostic in diagnostics:
                    print("[track-continuity] " + json.dumps({"cameraId": camera_id, **diagnostic}), flush=True)
            return result

    def get_last_result(self, camera_id: str) -> LogicalContinuityResult | None:
        with self._lock:
            state = self._cameras.get(camera_id or "unknown-camera")
            return state.last_result if state else None

    def get_identities(self, camera_id: str) -> tuple[LogicalTrackState, ...]:
        with self._lock:
            state = self._cameras.get(camera_id or "unknown-camera")
            return tuple(state.identities.values()) if state else ()

    def reset_camera(self, camera_id: str) -> None:
        with self._lock:
            self._cameras.pop(camera_id or "unknown-camera", None)

    def reset_all(self) -> None:
        with self._lock:
            self._cameras.clear()
