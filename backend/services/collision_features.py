"""Deterministic image-plane motion features used by temporal crash verification."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from backend.services.vehicle_tracking import TrackObservation, TrackState


Vector = tuple[float, float]


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def vector_speed(vector: Vector) -> float:
    return math.hypot(vector[0], vector[1])


def estimate_velocity(
    track: TrackState,
    *,
    max_observations: int = 4,
    exclude_latest: bool = False,
) -> Vector:
    """Return smoothed normalized-image displacement per second.

    This is deliberately not labelled or interpreted as physical speed. The
    endpoints of a short timestamped window suppress frame-to-frame box jitter.
    """
    observations: Sequence[TrackObservation] = tuple(track.history)
    if exclude_latest and observations:
        observations = observations[:-1]
    observations = observations[-max(2, max_observations) :]
    if len(observations) < 2:
        return (0.0, 0.0)
    first = observations[0]
    last = observations[-1]
    elapsed = last.timestamp - first.timestamp
    if elapsed <= 1e-6:
        return (0.0, 0.0)
    return (
        (last.center_x_norm - first.center_x_norm) / elapsed,
        (last.center_y_norm - first.center_y_norm) / elapsed,
    )


def heading_radians(velocity: Vector) -> float | None:
    if vector_speed(velocity) <= 1e-6:
        return None
    return math.atan2(velocity[1], velocity[0])


def heading_change(before: Vector, after: Vector, *, min_speed: float = 0.015) -> float:
    if vector_speed(before) < min_speed or vector_speed(after) < min_speed:
        return 0.0
    before_heading = heading_radians(before)
    after_heading = heading_radians(after)
    if before_heading is None or after_heading is None:
        return 0.0
    difference = abs(after_heading - before_heading)
    return min(difference, 2 * math.pi - difference)


def normalized_velocity_change(before: Vector, after: Vector) -> float:
    baseline = max(vector_speed(before), 0.025)
    return clamp01(math.hypot(after[0] - before[0], after[1] - before[1]) / baseline)


@dataclass(frozen=True)
class PairDistance:
    center_distance: float
    edge_distance: float
    iou: float


def _normalized_bbox(track: TrackState, frame_width: int, frame_height: int):
    x1, y1, x2, y2 = track.bbox
    width = max(1, int(frame_width))
    height = max(1, int(frame_height))
    return x1 / width, y1 / height, x2 / width, y2 / height


def distance_metric(
    track_a: TrackState,
    track_b: TrackState,
    *,
    frame_width: int,
    frame_height: int,
) -> PairDistance:
    """Return normalized image-space distances behind a replaceable interface."""
    ax, ay = track_a.center_normalized
    bx, by = track_b.center_normalized
    center_distance = math.hypot(bx - ax, by - ay)
    ax1, ay1, ax2, ay2 = _normalized_bbox(track_a, frame_width, frame_height)
    bx1, by1, bx2, by2 = _normalized_bbox(track_b, frame_width, frame_height)
    dx = max(bx1 - ax2, ax1 - bx2, 0.0)
    dy = max(by1 - ay2, ay1 - by2, 0.0)
    edge_distance = math.hypot(dx, dy)
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - intersection
    return PairDistance(
        center_distance=center_distance,
        edge_distance=edge_distance,
        iou=(intersection / union) if union > 0.0 else 0.0,
    )


def convergence_score(track_a: TrackState, track_b: TrackState) -> float:
    """Score whether current relative velocity closes the center-to-center vector."""
    ax, ay = track_a.center_normalized
    bx, by = track_b.center_normalized
    relative_position = (bx - ax, by - ay)
    distance = vector_speed(relative_position)
    if distance <= 1e-6:
        return 1.0
    velocity_a = estimate_velocity(track_a)
    velocity_b = estimate_velocity(track_b)
    relative_velocity = (velocity_b[0] - velocity_a[0], velocity_b[1] - velocity_a[1])
    radial_rate = (
        relative_position[0] * relative_velocity[0]
        + relative_position[1] * relative_velocity[1]
    ) / distance
    # 0.08 normalized-image units/s is already a strong closing rate at the
    # default 2 analyzed FPS. Same-direction following yields approximately 0.
    return clamp01((-radial_rate) / 0.08)
