"""Safe two-tier vehicle detections for collision analysis.

Trusted detections retain the production vehicle-count semantics. Lower-confidence
candidates are bounded, context-gated evidence and never become trusted merely
because they persist.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Iterable, Mapping


class VehicleDetectionState(StrEnum):
    TRUSTED = "TRUSTED"
    CANDIDATE = "CANDIDATE"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class VehicleTierConfig:
    trusted_threshold: float = 0.40
    candidate_threshold: float = 0.25
    model1_support_threshold: float = 0.60
    persistence_observations: int = 2
    persistence_window_seconds: float = 2.0
    stale_after_seconds: float = 2.0
    trusted_context_seconds: float = 2.0
    proximity_normalized: float = 0.12
    region_match_normalized: float = 0.08
    max_regions_per_camera: int = 64
    max_cameras: int = 512

    def __post_init__(self) -> None:
        if not 0.0 <= self.candidate_threshold < self.trusted_threshold <= 1.0:
            raise ValueError("Candidate threshold must be below the trusted threshold.")
        if not 0.0 <= self.model1_support_threshold <= 1.0:
            raise ValueError("Model 1 support threshold must be between 0 and 1.")
        if self.persistence_observations < 2:
            raise ValueError("Candidate persistence must require at least two observations.")
        if min(self.persistence_window_seconds, self.stale_after_seconds) <= 0:
            raise ValueError("Candidate retention windows must be positive.")
        if min(self.max_regions_per_camera, self.max_cameras) < 1:
            raise ValueError("Candidate state bounds must be positive.")


@dataclass
class _CandidateRegion:
    bbox: tuple[float, float, float, float]
    first_seen: float
    last_seen: float
    observations: deque[float] = field(default_factory=deque)


@dataclass
class _CameraCandidateState:
    regions: list[_CandidateRegion] = field(default_factory=list)
    last_seen: float = 0.0
    last_trusted_at: float | None = None


@dataclass(frozen=True)
class VehicleTierResult:
    raw: tuple[dict, ...]
    trusted: tuple[dict, ...]
    candidates: tuple[dict, ...]
    rejected: tuple[dict, ...]
    supported_candidates: tuple[dict, ...]
    tracker_input: tuple[dict, ...]
    trusted_context_present: bool
    processing_ms: float

    @property
    def raw_count(self) -> int:
        return len(self.raw)


def classify_vehicle_confidence(
    confidence: float, *, trusted_threshold: float, candidate_threshold: float
) -> VehicleDetectionState:
    confidence = float(confidence)
    if confidence >= trusted_threshold:
        return VehicleDetectionState.TRUSTED
    if confidence >= candidate_threshold:
        return VehicleDetectionState.CANDIDATE
    return VehicleDetectionState.REJECTED


def _xyxy(box: Mapping) -> tuple[float, float, float, float]:
    if box.get("box") is not None and len(box["box"]) >= 4:
        return tuple(float(value) for value in box["box"][:4])  # type: ignore[return-value]
    x1 = float(box.get("x") or 0.0)
    y1 = float(box.get("y") or 0.0)
    return (
        x1,
        y1,
        x1 + float(box.get("width") or 0.0),
        y1 + float(box.get("height") or 0.0),
    )


def _center(box: Mapping) -> tuple[float, float]:
    x1, y1, x2, y2 = _xyxy(box)
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def _normalized_center_distance(a: Mapping, b: Mapping, diagonal: float) -> float:
    ax, ay = _center(a)
    bx, by = _center(b)
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5 / max(1.0, diagonal)


def _boxes_near(a: Mapping, b: Mapping, diagonal: float, threshold: float) -> bool:
    ax1, ay1, ax2, ay2 = _xyxy(a)
    bx1, by1, bx2, by2 = _xyxy(b)
    dx = max(0.0, bx1 - ax2, ax1 - bx2)
    dy = max(0.0, by1 - ay2, ay1 - by2)
    # Preserve the original center-distance gate, while treating genuine box
    # overlap as proximity. The latter matters when a small collision
    # participant sits at the edge of a much larger trusted vehicle.
    return (dx == 0.0 and dy == 0.0) or (
        _normalized_center_distance(a, b, diagonal) <= threshold
    )


class VehicleCandidateEvaluator:
    """Classify raw vehicles and admit only corroborated candidates to tracking."""

    def __init__(self, config: VehicleTierConfig | None = None) -> None:
        self.config = config or VehicleTierConfig()
        self._cameras: dict[str, _CameraCandidateState] = {}
        self._lock = threading.RLock()

    def _camera(self, camera_id: str, now: float) -> _CameraCandidateState:
        state = self._cameras.get(camera_id)
        if state is None:
            if len(self._cameras) >= self.config.max_cameras:
                oldest = min(self._cameras, key=lambda key: self._cameras[key].last_seen)
                self._cameras.pop(oldest, None)
            state = _CameraCandidateState()
            self._cameras[camera_id] = state
        state.last_seen = now
        return state

    def evaluate(
        self,
        camera_id: str,
        detections: Iterable[Mapping],
        *,
        classifier_score: float,
        frame_width: int,
        frame_height: int,
        timestamp: float | None = None,
    ) -> VehicleTierResult:
        started = time.perf_counter()
        now = time.monotonic() if timestamp is None else float(timestamp)
        raw: list[dict] = []
        trusted: list[dict] = []
        candidates: list[dict] = []
        rejected: list[dict] = []
        for detection in detections:
            item = dict(detection)
            confidence = float(item.get("confidence", item.get("score", 0.0)) or 0.0)
            tier = classify_vehicle_confidence(
                confidence,
                trusted_threshold=self.config.trusted_threshold,
                candidate_threshold=self.config.candidate_threshold,
            )
            item["detectionState"] = tier.value
            item["supportReasons"] = []
            raw.append(item)
            if tier is VehicleDetectionState.TRUSTED:
                trusted.append(item)
            elif tier is VehicleDetectionState.CANDIDATE:
                candidates.append(item)
            else:
                item["rejectionReason"] = "below_candidate_threshold"
                rejected.append(item)

        diagonal = (max(1, frame_width) ** 2 + max(1, frame_height) ** 2) ** 0.5
        supported: list[dict] = []
        with self._lock:
            state = self._camera(camera_id or "unknown-camera", now)
            state.regions = [
                region
                for region in state.regions
                if now - region.last_seen <= self.config.stale_after_seconds
            ]
            if trusted:
                state.last_trusted_at = now

            matched_region_ids: set[int] = set()
            for candidate in candidates:
                matched = None
                nearest_distance = float("inf")
                for region in state.regions:
                    if id(region) in matched_region_ids:
                        continue
                    region_box = {"box": region.bbox}
                    distance = _normalized_center_distance(candidate, region_box, diagonal)
                    if (
                        distance <= self.config.region_match_normalized
                        and distance < nearest_distance
                    ):
                        matched = region
                        nearest_distance = distance
                if matched is None:
                    matched = _CandidateRegion(
                        bbox=_xyxy(candidate), first_seen=now, last_seen=now
                    )
                    state.regions.append(matched)
                matched_region_ids.add(id(matched))
                matched.bbox = _xyxy(candidate)
                matched.last_seen = now
                matched.observations.append(now)
                while matched.observations and now - matched.observations[0] > self.config.persistence_window_seconds:
                    matched.observations.popleft()

                persistent = len(matched.observations) >= self.config.persistence_observations
                near_trusted = any(
                    _boxes_near(
                        candidate, item, diagonal, self.config.proximity_normalized
                    )
                    for item in trusted
                )
                near_candidate = any(
                    item is not candidate
                    and _boxes_near(
                        candidate, item, diagonal, self.config.proximity_normalized
                    )
                    for item in candidates
                )
                model1 = float(classifier_score) >= self.config.model1_support_threshold
                reasons = []
                if model1:
                    reasons.append("model1")
                if persistent:
                    reasons.append("persistence")
                if near_trusted:
                    reasons.append("trusted_proximity")
                if near_candidate:
                    reasons.append("candidate_pair_proximity")

                # Model 1 alone never admits a low-confidence box. Candidate pairs
                # need all three signals; a trusted neighbour needs one additional
                # signal (classifier or persistence).
                is_supported = (near_trusted and (model1 or persistent)) or (
                    near_candidate and persistent and model1
                )
                candidate["supportReasons"] = reasons
                candidate["candidateSupported"] = is_supported
                if is_supported:
                    supported.append(candidate)
                else:
                    candidate["rejectionReason"] = "no_context_support"

            if len(state.regions) > self.config.max_regions_per_camera:
                state.regions.sort(key=lambda region: region.last_seen, reverse=True)
                del state.regions[self.config.max_regions_per_camera :]
            trusted_context = bool(
                trusted
                or state.last_trusted_at is not None
                and now - state.last_trusted_at <= self.config.trusted_context_seconds
            )

        return VehicleTierResult(
            raw=tuple(raw),
            trusted=tuple(trusted),
            candidates=tuple(candidates),
            rejected=tuple(rejected),
            supported_candidates=tuple(supported),
            tracker_input=tuple([*trusted, *supported]),
            trusted_context_present=trusted_context,
            processing_ms=(time.perf_counter() - started) * 1000.0,
        )

    def reset_camera(self, camera_id: str) -> None:
        with self._lock:
            self._cameras.pop(camera_id or "unknown-camera", None)

    def reset_all(self) -> None:
        with self._lock:
            self._cameras.clear()
