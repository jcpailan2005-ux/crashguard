"""Persistent static crash-scene review detection, separate from impact verification."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Sequence

from backend.services.collision_features import clamp01, estimate_velocity, vector_speed
from backend.services.vehicle_tracking import TrackState


AFTERMATH_STATES = {"NONE", "SUSPECTED", "PERSISTENT", "REVIEW_CANDIDATE", "ACTIVE", "CLEARED"}


@dataclass(frozen=True)
class AftermathConfig:
    enabled: bool = True
    min_classifier_score: float = 0.80
    high_confidence_classifier_threshold: float = 0.90
    minimum_score: float = 0.80
    required_positive_frames: int = 6
    window_seconds: float = 10.0
    minimum_persistence_seconds: float = 2.5
    clear_seconds: float = 2.0
    clear_consecutive_negatives: int = 3
    cooldown_seconds: float = 30.0
    session_gap_seconds: float = 6.0
    minimum_track_history: int = 3
    stationary_speed_threshold: float = 0.018
    minimum_abnormality_score: float = 0.35
    history_size: int = 24
    max_cameras: int = 512

    def __post_init__(self) -> None:
        for name in (
            "min_classifier_score",
            "high_confidence_classifier_threshold",
            "minimum_score",
            "minimum_abnormality_score",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1.")
        if self.required_positive_frames < 2:
            raise ValueError("required_positive_frames must be at least 2.")
        if self.minimum_track_history < 2:
            raise ValueError("minimum_track_history must be at least 2.")
        if self.history_size < self.required_positive_frames:
            raise ValueError("history_size must cover required_positive_frames.")
        for name in (
            "window_seconds",
            "minimum_persistence_seconds",
            "clear_seconds",
            "cooldown_seconds",
            "session_gap_seconds",
            "stationary_speed_threshold",
        ):
            if float(getattr(self, name)) < 0.0:
                raise ValueError(f"{name} cannot be negative.")
        if self.window_seconds <= 0.0:
            raise ValueError("window_seconds must be positive.")
        if self.clear_consecutive_negatives < 1 or self.max_cameras < 1:
            raise ValueError("Clear count and camera limit must be positive.")


@dataclass
class _AftermathState:
    state: str = "NONE"
    positive_times: deque[float] = field(default_factory=deque)
    first_positive_at: float | None = None
    last_observed_at: float = 0.0
    track_signature: tuple[int, ...] = ()
    consecutive_negatives: int = 0
    clear_started_at: float | None = None
    cleared_at: float | None = None


@dataclass(frozen=True)
class AftermathDecision:
    camera_id: str
    state: str
    is_suspected: bool
    is_persistent: bool
    review_candidate: bool
    score: float
    classifier_score: float
    positive_observations: int
    persistence_seconds: float
    track_ids: tuple[int, ...]
    evidence: dict
    reason: str
    rejection_reasons: tuple[str, ...]
    analysis_ms: float


def estimate_scene_abnormality(
    active_tracks: Sequence[TrackState] = (),
    detection_boxes: Sequence[dict] = (),
) -> float:
    """Lightweight image-plane abnormality evidence, independent of the classifier.

    Evaluates both tracked vehicles and current raw YOLO detection boxes.
    Supports:
    1. Severe orientation distortion (e.g. overturned/on-side vehicles).
    2. Vehicle-to-vehicle contact/overlap: IoU, intersection over min area (IoMin),
       and close edge distance relative to vehicle scale.
    """
    boxes_xyxy: list[tuple[float, float, float, float]] = []

    # Collect from active tracks
    for track in active_tracks:
        x1, y1, x2, y2 = track.bbox
        if x2 > x1 and y2 > y1:
            boxes_xyxy.append((float(x1), float(y1), float(x2), float(y2)))

    # Also collect from raw detection boxes (converting x, y, width, height if needed)
    for raw_box in detection_boxes:
        if "x" in raw_box and "width" in raw_box:
            bx1 = float(raw_box["x"])
            by1 = float(raw_box["y"])
            bx2 = bx1 + float(raw_box["width"])
            by2 = by1 + float(raw_box["height"])
        elif "box" in raw_box:
            bx1, by1, bx2, by2 = [float(v) for v in raw_box["box"]]
        elif "bbox" in raw_box:
            bx1, by1, bx2, by2 = [float(v) for v in raw_box["bbox"]]
        else:
            continue
        if bx2 > bx1 and by2 > by1:
            # Avoid exact duplicate of existing box
            is_dup = any(
                abs(bx1 - ex1) < 5 and abs(by1 - ey1) < 5 and abs(bx2 - ex2) < 5 and abs(by2 - ey2) < 5
                for ex1, ey1, ex2, ey2 in boxes_xyxy
            )
            if not is_dup:
                boxes_xyxy.append((bx1, by1, bx2, by2))

    if not boxes_xyxy:
        return 0.0

    # 1. Orientation score (unusual aspect ratio, e.g. rolled or crushed tall)
    orientation_score = 0.0
    for x1, y1, x2, y2 in boxes_xyxy:
        width = max(1.0, x2 - x1)
        height = max(1.0, y2 - y1)
        aspect_ratio = width / height
        orientation_score = max(orientation_score, clamp01((1.15 - aspect_ratio) / 0.55))

    # 2. Multi-vehicle overlap & contact geometry
    contact_score = 0.0
    for index, (ax1, ay1, ax2, ay2) in enumerate(boxes_xyxy):
        area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
        wa = max(1.0, ax2 - ax1)
        ha = max(1.0, ay2 - ay1)
        for bx1, by1, bx2, by2 in boxes_xyxy[index + 1 :]:
            area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
            wb = max(1.0, bx2 - bx1)
            hb = max(1.0, by2 - by1)
            scale = max(wa, ha, wb, hb)

            inter_w = max(0.0, min(ax2, bx2) - max(ax1, bx1))
            inter_h = max(0.0, min(ay2, by2) - max(ay1, by1))
            intersection = inter_w * inter_h
            union = area_a + area_b - intersection
            min_area = min(area_a, area_b)

            iou = (intersection / union) if union > 0.0 else 0.0
            io_min = (intersection / min_area) if min_area > 0.0 else 0.0

            # Edge distance in pixels
            dx = max(0.0, max(ax1, bx1) - min(ax2, bx2)) if min(ax2, bx2) < max(ax1, bx1) else 0.0
            dy = max(0.0, max(ay1, by1) - min(ay2, by2)) if min(ay2, by2) < max(ay1, by1) else 0.0
            edge_dist = (dx * dx + dy * dy) ** 0.5 if (dx > 0 and dy > 0) else max(dx, dy)
            dist_norm = edge_dist / scale

            # Strong proximity / contact if touching or very close
            overlap_val = clamp01(iou / 0.18)
            iomin_val = clamp01(io_min / 0.25)
            proximity_val = clamp01((0.06 - dist_norm) / 0.06) if dist_norm <= 0.06 else 0.0

            contact_score = max(contact_score, overlap_val, iomin_val, proximity_val)

    return max(orientation_score, contact_score)


class CrashAftermathDetector:
    """Detect a persistent, stationary crash-like scene for human review.

    This service does not assert that impact occurred. It uses the existing
    crash-scene classifier, real tracked vehicles, low normalized motion, and
    multi-frame persistence. No damage geometry is fabricated.
    """

    def __init__(self, config: AftermathConfig | None = None) -> None:
        self.config = config or AftermathConfig()
        self._states: dict[str, _AftermathState] = {}
        self._lock = threading.RLock()

    def _decision(
        self,
        camera_id: str,
        state: _AftermathState | None,
        *,
        classifier_score: float,
        score: float,
        track_ids: tuple[int, ...],
        max_speed: float | None,
        vehicle_count: int,
        reason: str,
        abnormality_score: float = 0.0,
        started: float,
    ) -> AftermathDecision:
        current_state = state.state if state is not None else "NONE"
        positive_observations = len(state.positive_times) if state is not None else 0
        persistence_seconds = (
            max(0.0, state.last_observed_at - state.first_positive_at)
            if state is not None and state.first_positive_at is not None
            else 0.0
        )
        return AftermathDecision(
            camera_id=camera_id,
            state=current_state,
            is_suspected=current_state in {"SUSPECTED", "PERSISTENT", "REVIEW_CANDIDATE", "ACTIVE"},
            is_persistent=current_state in {"PERSISTENT", "REVIEW_CANDIDATE", "ACTIVE"},
            review_candidate=current_state in {"REVIEW_CANDIDATE", "ACTIVE"},
            score=score,
            classifier_score=classifier_score,
            positive_observations=positive_observations,
            persistence_seconds=persistence_seconds,
            track_ids=track_ids,
            evidence={
                "classifier_score": round(classifier_score, 4),
                "vehicle_count": int(vehicle_count),
                "track_ids": list(track_ids),
                "stationary": max_speed is not None
                and max_speed <= self.config.stationary_speed_threshold,
                "max_normalized_speed": round(max_speed, 5) if max_speed is not None else None,
                "required_positive_frames": self.config.required_positive_frames,
                "positive_observations": positive_observations,
                "minimum_persistence_seconds": self.config.minimum_persistence_seconds,
                "persistence_seconds": round(persistence_seconds, 3),
                "aftermath_score": round(score, 4),
                "scene_abnormality_score": round(abnormality_score, 4),
                "minimum_abnormality_score": self.config.minimum_abnormality_score,
            },
            reason=reason,
            rejection_reasons=(
                ()
                if reason in {"persistent_crash_aftermath", "active_aftermath_incident"}
                else (reason,)
            ),
            analysis_ms=(time.perf_counter() - started) * 1000.0,
        )

    def observe(
        self,
        camera_id: str,
        *,
        classifier_score: float,
        vehicle_count: int,
        active_tracks: Sequence[TrackState],
        scene_valid: bool,
        frame_quality_status: str,
        scene_abnormality_score: float,
        temporal_collision_active: bool = False,
        timestamp: float | None = None,
    ) -> AftermathDecision:
        started = time.perf_counter()
        now = time.monotonic() if timestamp is None else float(timestamp)
        camera_id = camera_id or "unknown-camera"
        classifier_score = clamp01(classifier_score)
        abnormality_score = clamp01(scene_abnormality_score)
        usable_tracks = tuple(
            track
            for track in active_tracks
            if track.camera_id == camera_id
            and len(track.history) >= self.config.minimum_track_history
        )
        track_ids = tuple(sorted(track.track_id for track in usable_tracks))
        # Provisional logical presence may preserve the aftermath signature,
        # but only currently tracked observations may contribute motion or
        # stationary evidence. This prevents an untracked candidate from
        # becoming an invented zero-velocity measurement.
        motion_tracks = tuple(
            track for track in usable_tracks if getattr(track, "motion_observed", True)
        )
        speeds = [vector_speed(estimate_velocity(track)) for track in motion_tracks]
        max_speed = max(speeds) if speeds else None
        stationary = bool(
            speeds and max_speed is not None and max_speed <= self.config.stationary_speed_threshold
        )
        # High-confidence aftermath path vs standard geometric aftermath path
        is_high_confidence = bool(classifier_score >= self.config.high_confidence_classifier_threshold)
        if is_high_confidence:
            score = clamp01(
                0.55 * classifier_score
                + 0.30 * (1.0 if stationary else 0.0)
                + 0.10 * abnormality_score
                + 0.05 * (1.0 if vehicle_count >= 2 else 0.0)
            )
        else:
            # A second vehicle is supporting evidence, never a requirement.
            score = clamp01(
                0.45 * classifier_score
                + 0.20 * (1.0 if stationary else 0.0)
                + 0.30 * abnormality_score
                + 0.05 * (1.0 if vehicle_count >= 2 else 0.0)
            )

        if not self.config.enabled:
            reason = "aftermath_disabled"
        elif temporal_collision_active:
            reason = "temporal_collision_already_active"
        elif frame_quality_status != "good":
            reason = "quality_gate_failed"
        elif not scene_valid:
            reason = "roi_gate_failed"
        elif vehicle_count < 1:
            reason = "no_vehicle_detected"
        elif not usable_tracks:
            reason = "insufficient_track_history"
        elif not stationary:
            reason = "normal_vehicle_motion"
        elif classifier_score < self.config.min_classifier_score:
            reason = "classifier_below_threshold"
        elif not is_high_confidence and abnormality_score < self.config.minimum_abnormality_score:
            reason = "insufficient_abnormal_geometry"
        elif score < self.config.minimum_score:
            reason = "low_aftermath_score"
        else:
            reason = "positive"
        positive = reason == "positive"

        with self._lock:
            state = self._states.get(camera_id)
            if state is not None and (
                now < state.last_observed_at
                or now - state.last_observed_at > self.config.session_gap_seconds
            ):
                state = None
                self._states.pop(camera_id, None)
            if state is None:
                if len(self._states) >= self.config.max_cameras:
                    oldest = min(
                        self._states,
                        key=lambda key: self._states[key].last_observed_at,
                    )
                    self._states.pop(oldest, None)
                state = _AftermathState(
                    positive_times=deque(maxlen=self.config.history_size),
                    last_observed_at=now,
                )
                self._states[camera_id] = state
            state.last_observed_at = now

            if temporal_collision_active:
                state.state = "NONE"
                state.positive_times.clear()
                state.first_positive_at = None
                state.track_signature = ()
                return self._decision(
                    camera_id, state, classifier_score=classifier_score, score=score,
                    track_ids=track_ids, max_speed=max_speed, vehicle_count=vehicle_count,
                    reason=reason, abnormality_score=abnormality_score, started=started,
                )

            if state.state == "CLEARED":
                cleared_at = state.cleared_at if state.cleared_at is not None else now
                if now - cleared_at < self.config.cooldown_seconds:
                    return self._decision(
                        camera_id,
                        state,
                        classifier_score=classifier_score,
                        score=score,
                        track_ids=track_ids,
                        max_speed=max_speed,
                        vehicle_count=vehicle_count,
                        reason="aftermath_cooldown",
                        started=started,
                    )
                state = _AftermathState(
                    positive_times=deque(maxlen=self.config.history_size),
                    last_observed_at=now,
                )
                self._states[camera_id] = state

            if state.state in {"REVIEW_CANDIDATE", "ACTIVE"}:
                if positive:
                    state.consecutive_negatives = 0
                    state.clear_started_at = None
                    return self._decision(
                        camera_id,
                        state,
                        classifier_score=classifier_score,
                        score=score,
                        track_ids=state.track_signature,
                        max_speed=max_speed,
                        vehicle_count=vehicle_count,
                        reason=("active_aftermath_incident" if state.state == "ACTIVE" else "persistent_crash_aftermath"),
                        abnormality_score=abnormality_score,
                        started=started,
                    )
                state.consecutive_negatives += 1
                if state.clear_started_at is None:
                    state.clear_started_at = now
                if (
                    state.consecutive_negatives >= self.config.clear_consecutive_negatives
                    and now - state.clear_started_at >= self.config.clear_seconds
                ):
                    state.state = "CLEARED"
                    state.cleared_at = now
                    state.positive_times.clear()
                    state.first_positive_at = None
                    return self._decision(
                        camera_id,
                        state,
                        classifier_score=classifier_score,
                        score=score,
                        track_ids=track_ids,
                        max_speed=max_speed,
                        vehicle_count=vehicle_count,
                        reason="aftermath_cleared",
                        abnormality_score=abnormality_score,
                        started=started,
                    )
                return self._decision(
                    camera_id,
                    state,
                    classifier_score=classifier_score,
                    score=score,
                    track_ids=state.track_signature,
                    max_speed=max_speed,
                    vehicle_count=vehicle_count,
                    reason="aftermath_clearing",
                    abnormality_score=abnormality_score,
                    started=started,
                )

            if not positive:
                state.state = "NONE"
                state.positive_times.clear()
                state.first_positive_at = None
                state.track_signature = ()
                return self._decision(
                    camera_id,
                    state,
                    classifier_score=classifier_score,
                    score=score,
                    track_ids=track_ids,
                    max_speed=max_speed,
                    vehicle_count=vehicle_count,
                    reason=reason,
                    abnormality_score=abnormality_score,
                    started=started,
                )

            if state.track_signature and state.track_signature != track_ids:
                state.positive_times.clear()
                state.first_positive_at = None
            state.track_signature = track_ids
            if state.first_positive_at is None:
                state.first_positive_at = now
            state.positive_times.append(now)
            while state.positive_times and now - state.positive_times[0] > self.config.window_seconds:
                state.positive_times.popleft()
            if state.positive_times and state.first_positive_at < state.positive_times[0]:
                state.first_positive_at = state.positive_times[0]
            persistence = now - (
                state.first_positive_at if state.first_positive_at is not None else now
            )
            if (
                len(state.positive_times) >= self.config.required_positive_frames
                and persistence >= self.config.minimum_persistence_seconds
            ):
                state.state = "REVIEW_CANDIDATE"
                reason = "persistent_crash_aftermath"
            elif len(state.positive_times) >= 2:
                state.state = "PERSISTENT"
                reason = "insufficient_aftermath_persistence"
            else:
                state.state = "SUSPECTED"
                reason = "insufficient_aftermath_persistence"
            return self._decision(
                camera_id,
                state,
                classifier_score=classifier_score,
                score=score,
                track_ids=track_ids,
                max_speed=max_speed,
                vehicle_count=vehicle_count,
                reason=reason,
                abnormality_score=abnormality_score,
                started=started,
            )

    def snapshot(self, camera_id: str) -> str:
        with self._lock:
            state = self._states.get(camera_id or "unknown-camera")
            return state.state if state is not None else "NONE"

    def reset_camera(self, camera_id: str) -> None:
        with self._lock:
            self._states.pop(camera_id or "unknown-camera", None)

    def mark_active(self, camera_id: str) -> None:
        with self._lock:
            state = self._states.get(camera_id or "unknown-camera")
            if state is not None and state.state == "REVIEW_CANDIDATE":
                state.state = "ACTIVE"

    def reset_all(self) -> None:
        with self._lock:
            self._states.clear()
