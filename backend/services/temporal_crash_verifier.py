"""Explainable before/contact/after vehicle-collision verification."""

from __future__ import annotations

import itertools
import logging
import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from backend.services.collision_features import (
    clamp01,
    convergence_score,
    distance_metric,
    estimate_velocity,
    heading_change,
    normalized_velocity_change,
    vector_speed,
)
from backend.services.vehicle_tracking import TrackState


logger = logging.getLogger(__name__)


DEFAULT_FEATURE_WEIGHTS = {
    # All features are normalized to [0, 1]. Motion dominates: classifier
    # evidence contributes only 5% and can never bypass the required gates.
    "proximity": 0.10,
    "closing": 0.20,
    "convergence": 0.15,
    "contact": 0.15,
    "velocity_change": 0.15,
    "heading_change": 0.10,
    "post_contact": 0.10,
    "classifier": 0.05,
}


@dataclass(frozen=True)
class TemporalCrashConfig:
    min_track_history: int = 3
    interaction_distance_threshold: float = 0.35
    interaction_edge_distance_threshold: float = 0.06
    interaction_iou_threshold: float = 0.01
    min_closing_observations: int = 3
    closing_delta_for_full_score: float = 0.08
    approach_score_threshold: float = 0.40
    convergence_score_threshold: float = 0.20
    contact_iou_threshold: float = 0.02
    contact_edge_distance_threshold: float = 0.012
    post_contact_window_seconds: float = 3.0
    post_contact_min_observations: int = 2
    velocity_change_threshold: float = 0.60
    heading_change_threshold_radians: float = 0.65
    stopped_speed_threshold: float = 0.018
    moving_speed_threshold: float = 0.04
    temporal_crash_threshold: float = 0.62
    pair_retention_seconds: float = 4.0
    distance_history_size: int = 12
    max_cameras: int = 512
    feature_weights: Mapping[str, float] = field(
        default_factory=lambda: dict(DEFAULT_FEATURE_WEIGHTS)
    )

    def __post_init__(self) -> None:
        if self.min_track_history < 2:
            raise ValueError("min_track_history must be at least 2.")
        if self.min_closing_observations < 2:
            raise ValueError("min_closing_observations must be at least 2.")
        if self.post_contact_min_observations < 1:
            raise ValueError("post_contact_min_observations must be positive.")
        if self.distance_history_size < self.min_closing_observations:
            raise ValueError("distance_history_size is too small for closing analysis.")
        if self.max_cameras < 1:
            raise ValueError("max_cameras must be positive.")
        for name in (
            "interaction_distance_threshold",
            "interaction_edge_distance_threshold",
            "interaction_iou_threshold",
            "contact_iou_threshold",
            "contact_edge_distance_threshold",
            "closing_delta_for_full_score",
            "post_contact_window_seconds",
            "pair_retention_seconds",
        ):
            if float(getattr(self, name)) <= 0:
                raise ValueError(f"{name} must be positive.")
        for name in (
            "approach_score_threshold",
            "convergence_score_threshold",
            "velocity_change_threshold",
            "temporal_crash_threshold",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1.")
        if self.heading_change_threshold_radians <= 0 or self.heading_change_threshold_radians > math.pi:
            raise ValueError("heading_change_threshold_radians must be in (0, pi].")
        if self.stopped_speed_threshold < 0 or self.moving_speed_threshold <= 0:
            raise ValueError("Motion thresholds must be non-negative.")
        if set(self.feature_weights) != set(DEFAULT_FEATURE_WEIGHTS):
            raise ValueError("feature_weights must define every documented feature.")
        if any(value < 0 for value in self.feature_weights.values()):
            raise ValueError("Feature weights cannot be negative.")
        if abs(sum(self.feature_weights.values()) - 1.0) > 1e-6:
            raise ValueError("Feature weights must sum to 1.0.")


@dataclass(frozen=True)
class DistanceObservation:
    timestamp: float
    center_distance: float
    edge_distance: float
    iou: float


@dataclass
class InteractionState:
    track_a: int
    track_b: int
    first_seen_near: float
    last_seen_near: float
    last_observed_at: float
    min_distance: float
    max_iou: float
    distance_history: deque[DistanceObservation]
    logical_vehicle_a: str | None = None
    logical_vehicle_b: str | None = None
    latest_observation_strength_a: str = "trusted_track"
    latest_observation_strength_b: str = "trusted_track"
    motion_observed_a: bool = True
    motion_observed_b: bool = True
    state: str = "NONE"
    approach_detected: bool = False
    max_closing_score: float = 0.0
    max_convergence_score: float = 0.0
    possible_contact_at: float | None = None
    pre_contact_velocity_a: tuple[float, float] = (0.0, 0.0)
    pre_contact_velocity_b: tuple[float, float] = (0.0, 0.0)
    post_contact_observations: int = 0
    max_velocity_change_score: float = 0.0
    max_heading_change_score: float = 0.0
    max_stop_score: float = 0.0
    max_classifier_score: float = 0.0
    verified_at: float | None = None
    dismissed_at: float | None = None


@dataclass(frozen=True)
class TemporalCrashDecision:
    is_candidate: bool
    is_verified: bool
    score: float
    involved_track_ids: tuple[int, ...]
    evidence: dict
    contact_timestamp: float | None
    reason: str
    analysis_ms: float
    feature_calculation_ms: float
    temporal_verification_ms: float
    active_pairs: int

    @classmethod
    def idle(cls, *, analysis_ms: float = 0.0, active_pairs: int = 0) -> "TemporalCrashDecision":
        return cls(
            is_candidate=False,
            is_verified=False,
            score=0.0,
            involved_track_ids=(),
            evidence={
                "classifier_score": 0.0,
                "interaction_candidate": False,
                "approach_detected": False,
                "closing_score": 0.0,
                "convergence_score": 0.0,
                "contact_candidate": False,
                "velocity_change_score": 0.0,
                "heading_change_score": 0.0,
                "post_contact_disruption": False,
                "post_contact_score": 0.0,
                "temporal_score": 0.0,
            },
            contact_timestamp=None,
            reason="no_interaction_candidate",
            analysis_ms=analysis_ms,
            feature_calculation_ms=analysis_ms,
            temporal_verification_ms=0.0,
            active_pairs=active_pairs,
        )


class TemporalCrashVerifier:
    """Maintain isolated pair interaction state and verify temporal collisions."""

    def __init__(self, config: TemporalCrashConfig | None = None) -> None:
        self.config = config or TemporalCrashConfig()
        self._interactions: dict[str, dict[tuple[int, int], InteractionState]] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _pair_key(track_a: TrackState, track_b: TrackState) -> tuple[int, int]:
        return tuple(sorted((int(track_a.track_id), int(track_b.track_id))))

    def _is_near(self, distance) -> bool:
        return bool(
            distance.center_distance <= self.config.interaction_distance_threshold
            or distance.edge_distance <= self.config.interaction_edge_distance_threshold
            or distance.iou >= self.config.interaction_iou_threshold
        )

    def _closing_score(self, interaction: InteractionState) -> float:
        observations: Sequence[DistanceObservation] = tuple(interaction.distance_history)
        if len(observations) < self.config.min_closing_observations:
            return 0.0
        distances = [item.center_distance for item in observations]
        decreases = [
            previous - current
            for previous, current in zip(distances, distances[1:])
        ]
        consistent_fraction = sum(delta > 0.002 for delta in decreases) / max(1, len(decreases))
        net_closing = max(0.0, distances[0] - distances[-1])
        return clamp01(net_closing / self.config.closing_delta_for_full_score) * consistent_fraction

    def _proximity_score(self, distance) -> float:
        center_score = 1.0 - distance.center_distance / self.config.interaction_distance_threshold
        edge_score = 1.0 - distance.edge_distance / self.config.interaction_edge_distance_threshold
        overlap_score = distance.iou / max(self.config.contact_iou_threshold, 1e-6)
        return clamp01(max(center_score, edge_score, overlap_score))

    def _score(self, features: Mapping[str, float]) -> float:
        return clamp01(
            sum(
                self.config.feature_weights[name] * clamp01(features[name])
                for name in self.config.feature_weights
            )
        )

    def _decision(
        self,
        interaction: InteractionState,
        *,
        camera_id: str,
        proximity_score: float,
        classifier_score: float,
        analysis_ms: float,
        active_pairs: int,
    ) -> TemporalCrashDecision:
        contact = interaction.possible_contact_at is not None
        post_score = max(
            interaction.max_stop_score,
            0.7 * interaction.max_velocity_change_score
            + 0.3 * interaction.max_heading_change_score,
        )
        features = {
            "proximity": proximity_score,
            "closing": interaction.max_closing_score,
            "convergence": interaction.max_convergence_score,
            "contact": 1.0 if contact else 0.0,
            "velocity_change": interaction.max_velocity_change_score,
            "heading_change": interaction.max_heading_change_score,
            "post_contact": clamp01(post_score),
            "classifier": interaction.max_classifier_score,
        }
        score = self._score(features)
        disruption = bool(
            interaction.max_stop_score >= 1.0
            or interaction.max_velocity_change_score >= self.config.velocity_change_threshold
            or (
                interaction.max_heading_change_score >= 1.0
                and interaction.max_velocity_change_score >= self.config.velocity_change_threshold * 0.6
            )
        )
        enough_post_contact = (
            interaction.post_contact_observations
            >= self.config.post_contact_min_observations
        )
        motion_evidence_complete = bool(
            interaction.motion_observed_a and interaction.motion_observed_b
        )
        verified = bool(
            interaction.state == "VERIFIED"
            or (
                motion_evidence_complete
                and interaction.approach_detected
                and contact
                and enough_post_contact
                and disruption
                and score >= self.config.temporal_crash_threshold
            )
        )
        if verified and interaction.state != "VERIFIED":
            interaction.state = "VERIFIED"
            interaction.verified_at = interaction.last_observed_at
            logger.info(
                "temporal_collision camera=%s camera_pair=%s,%s closing=%.3f convergence=%.3f "
                "contact=true velocity_change=%.3f heading_change=%.3f score=%.3f decision=verified",
                camera_id,
                interaction.track_a,
                interaction.track_b,
                interaction.max_closing_score,
                interaction.max_convergence_score,
                interaction.max_velocity_change_score,
                interaction.max_heading_change_score,
                score,
            )

        evidence = {
            "classifier_score": round(interaction.max_classifier_score, 4),
            "interaction_candidate": True,
            "approach_detected": interaction.approach_detected,
            "closing_score": round(interaction.max_closing_score, 4),
            "convergence_score": round(interaction.max_convergence_score, 4),
            "contact_candidate": contact,
            "velocity_change_score": round(interaction.max_velocity_change_score, 4),
            "heading_change_score": round(interaction.max_heading_change_score, 4),
            "post_contact_observations": interaction.post_contact_observations,
            "post_contact_disruption": disruption,
            "post_contact_score": round(clamp01(post_score), 4),
            "min_normalized_center_distance": round(interaction.min_distance, 4),
            "max_iou": round(interaction.max_iou, 4),
            "temporal_score": round(score, 4),
            "state": interaction.state,
            "logical_vehicle_ids": [
                value
                for value in (
                    interaction.logical_vehicle_a,
                    interaction.logical_vehicle_b,
                )
                if value is not None
            ],
            "observation_strength": [
                interaction.latest_observation_strength_a,
                interaction.latest_observation_strength_b,
            ],
            "motion_observed": [
                interaction.motion_observed_a,
                interaction.motion_observed_b,
            ],
            "motion_evidence_complete": motion_evidence_complete,
            "pair_history_length": len(interaction.distance_history),
        }
        if verified:
            reason = "verified_before_contact_after_pattern"
        elif not interaction.approach_detected:
            reason = "no_consistent_approach"
        elif not contact:
            reason = "no_contact_candidate"
        elif not enough_post_contact:
            reason = "observing_post_contact"
        elif not disruption:
            reason = "no_post_contact_motion_disruption"
        else:
            reason = "temporal_score_below_threshold"
        return TemporalCrashDecision(
            is_candidate=True,
            is_verified=verified,
            score=score,
            involved_track_ids=(interaction.track_a, interaction.track_b),
            evidence=evidence,
            contact_timestamp=interaction.possible_contact_at,
            reason=reason,
            analysis_ms=analysis_ms,
            feature_calculation_ms=0.0,
            temporal_verification_ms=0.0,
            active_pairs=active_pairs,
        )

    def analyze(
        self,
        camera_id: str,
        active_tracks: Sequence[TrackState],
        *,
        classifier_score: float,
        frame_width: int,
        frame_height: int,
        timestamp: float | None = None,
    ) -> TemporalCrashDecision:
        started = time.perf_counter()
        timestamp = time.monotonic() if timestamp is None else float(timestamp)
        camera_id = camera_id or "unknown-camera"
        classifier_score = clamp01(classifier_score)
        with self._lock:
            verification_ms = 0.0
            if camera_id not in self._interactions and len(self._interactions) >= self.config.max_cameras:
                oldest_camera = min(
                    self._interactions,
                    key=lambda key: max(
                        (
                            interaction.last_observed_at
                            for interaction in self._interactions[key].values()
                        ),
                        default=float("-inf"),
                    ),
                )
                self._interactions.pop(oldest_camera, None)
            camera_pairs = self._interactions.setdefault(camera_id, {})
            stale_keys = [
                key
                for key, interaction in camera_pairs.items()
                if timestamp - interaction.last_observed_at > self.config.pair_retention_seconds
            ]
            for key in stale_keys:
                camera_pairs.pop(key, None)

            current_decisions: list[TemporalCrashDecision] = []
            for track_a, track_b in itertools.combinations(active_tracks, 2):
                if track_a.camera_id != camera_id or track_b.camera_id != camera_id:
                    continue
                key = self._pair_key(track_a, track_b)
                distance = distance_metric(
                    track_a,
                    track_b,
                    frame_width=frame_width,
                    frame_height=frame_height,
                )
                interaction = camera_pairs.get(key)
                near = self._is_near(distance)
                if interaction is None and not near:
                    continue
                if interaction is None:
                    interaction = InteractionState(
                        track_a=key[0],
                        track_b=key[1],
                        first_seen_near=timestamp,
                        last_seen_near=timestamp,
                        last_observed_at=timestamp,
                        min_distance=distance.center_distance,
                        max_iou=distance.iou,
                        distance_history=deque(maxlen=self.config.distance_history_size),
                        logical_vehicle_a=getattr(track_a, "logical_vehicle_id", None),
                        logical_vehicle_b=getattr(track_b, "logical_vehicle_id", None),
                    )
                    camera_pairs[key] = interaction

                interaction.logical_vehicle_a = getattr(
                    track_a, "logical_vehicle_id", interaction.logical_vehicle_a
                )
                interaction.logical_vehicle_b = getattr(
                    track_b, "logical_vehicle_id", interaction.logical_vehicle_b
                )
                interaction.latest_observation_strength_a = getattr(
                    track_a, "observation_source", "trusted_track"
                )
                interaction.latest_observation_strength_b = getattr(
                    track_b, "observation_source", "trusted_track"
                )
                interaction.motion_observed_a = bool(
                    getattr(track_a, "motion_observed", True)
                )
                interaction.motion_observed_b = bool(
                    getattr(track_b, "motion_observed", True)
                )

                interaction.last_observed_at = timestamp
                if near:
                    interaction.last_seen_near = timestamp
                interaction.min_distance = min(interaction.min_distance, distance.center_distance)
                interaction.max_iou = max(interaction.max_iou, distance.iou)
                interaction.max_classifier_score = max(
                    interaction.max_classifier_score, classifier_score
                )
                interaction.distance_history.append(
                    DistanceObservation(
                        timestamp=timestamp,
                        center_distance=distance.center_distance,
                        edge_distance=distance.edge_distance,
                        iou=distance.iou,
                    )
                )

                spatial_histories_ready = bool(
                    len(track_a.history) >= self.config.min_track_history
                    and len(track_b.history) >= self.config.min_track_history
                )
                motion_histories_ready = bool(
                    spatial_histories_ready
                    and interaction.motion_observed_a
                    and interaction.motion_observed_b
                )
                closing = (
                    self._closing_score(interaction) if spatial_histories_ready else 0.0
                )
                convergence = (
                    convergence_score(track_a, track_b)
                    if motion_histories_ready
                    else 0.0
                )
                interaction.max_closing_score = max(interaction.max_closing_score, closing)
                interaction.max_convergence_score = max(
                    interaction.max_convergence_score, convergence
                )
                if (
                    motion_histories_ready
                    and closing >= self.config.approach_score_threshold
                    and convergence >= self.config.convergence_score_threshold
                ):
                    interaction.approach_detected = True
                    if interaction.state == "NONE":
                        interaction.state = "APPROACHING"

                contact_geometry = bool(
                    distance.iou >= self.config.contact_iou_threshold
                    or distance.edge_distance <= self.config.contact_edge_distance_threshold
                )
                if (
                    interaction.possible_contact_at is None
                    and interaction.approach_detected
                    and contact_geometry
                ):
                    interaction.possible_contact_at = timestamp
                    interaction.pre_contact_velocity_a = estimate_velocity(
                        track_a, exclude_latest=True
                    )
                    interaction.pre_contact_velocity_b = estimate_velocity(
                        track_b, exclude_latest=True
                    )
                    interaction.state = "CONTACT_CANDIDATE"
                elif (
                    interaction.possible_contact_at is not None
                    and timestamp > interaction.possible_contact_at + 1e-6
                    and interaction.state != "VERIFIED"
                ):
                    if timestamp - interaction.possible_contact_at <= self.config.post_contact_window_seconds:
                        interaction.post_contact_observations += 1
                        # Logical presence without current raw tracking can
                        # extend spatial/contact history, but it cannot create
                        # velocity, heading, or stop evidence.
                        if motion_histories_ready:
                            velocity_a = estimate_velocity(track_a)
                            velocity_b = estimate_velocity(track_b)
                            change_a = normalized_velocity_change(
                                interaction.pre_contact_velocity_a, velocity_a
                            )
                            change_b = normalized_velocity_change(
                                interaction.pre_contact_velocity_b, velocity_b
                            )
                            interaction.max_velocity_change_score = max(
                                interaction.max_velocity_change_score, change_a, change_b
                            )
                            heading_a = heading_change(
                                interaction.pre_contact_velocity_a, velocity_a
                            )
                            heading_b = heading_change(
                                interaction.pre_contact_velocity_b, velocity_b
                            )
                            interaction.max_heading_change_score = max(
                                interaction.max_heading_change_score,
                                clamp01(heading_a / self.config.heading_change_threshold_radians),
                                clamp01(heading_b / self.config.heading_change_threshold_radians),
                            )
                            pre_speeds = (
                                vector_speed(interaction.pre_contact_velocity_a),
                                vector_speed(interaction.pre_contact_velocity_b),
                            )
                            post_speeds = (vector_speed(velocity_a), vector_speed(velocity_b))
                            stop_detected = any(
                                before >= self.config.moving_speed_threshold
                                and after <= self.config.stopped_speed_threshold
                                for before, after in zip(pre_speeds, post_speeds)
                            )
                            interaction.max_stop_score = max(
                                interaction.max_stop_score, 1.0 if stop_detected else 0.0
                            )
                        interaction.state = "POST_CONTACT"
                    elif interaction.state not in {"VERIFIED", "DISMISSED"}:
                        interaction.state = "DISMISSED"
                        interaction.dismissed_at = timestamp

                proximity = self._proximity_score(distance)
                verification_started = time.perf_counter()
                decision = self._decision(
                    interaction,
                    camera_id=camera_id,
                    proximity_score=proximity,
                    classifier_score=classifier_score,
                    analysis_ms=0.0,
                    active_pairs=len(camera_pairs),
                )
                verification_ms += (time.perf_counter() - verification_started) * 1000.0
                logger.debug(
                    "temporal_candidate camera=%s tracks=%s classifier=%.3f closing=%.3f "
                    "convergence=%.3f contact=%s velocity_change=%.3f heading_change=%.3f "
                    "score=%.3f decision=%s",
                    camera_id,
                    decision.involved_track_ids,
                    classifier_score,
                    interaction.max_closing_score,
                    interaction.max_convergence_score,
                    interaction.possible_contact_at is not None,
                    interaction.max_velocity_change_score,
                    interaction.max_heading_change_score,
                    decision.score,
                    decision.reason,
                )
                current_decisions.append(decision)

            elapsed_ms = (time.perf_counter() - started) * 1000.0
            if not current_decisions:
                if not camera_pairs:
                    self._interactions.pop(camera_id, None)
                return TemporalCrashDecision.idle(
                    analysis_ms=elapsed_ms, active_pairs=len(camera_pairs)
                )
            best = max(
                current_decisions,
                key=lambda item: (item.is_verified, item.score),
            )
            return TemporalCrashDecision(
                is_candidate=best.is_candidate,
                is_verified=best.is_verified,
                score=best.score,
                involved_track_ids=best.involved_track_ids,
                evidence=best.evidence,
                contact_timestamp=best.contact_timestamp,
                reason=best.reason,
                analysis_ms=elapsed_ms,
                feature_calculation_ms=max(0.0, elapsed_ms - verification_ms),
                temporal_verification_ms=verification_ms,
                active_pairs=len(camera_pairs),
            )

    def active_pair_count(self, camera_id: str) -> int:
        with self._lock:
            return len(self._interactions.get(camera_id or "unknown-camera", {}))

    def get_interactions(self, camera_id: str) -> tuple[InteractionState, ...]:
        with self._lock:
            return tuple(self._interactions.get(camera_id or "unknown-camera", {}).values())

    def expire_track_ids(self, camera_id: str, track_ids: Sequence[int]) -> None:
        """Drop pair history only after the logical continuity window truly expires."""
        expired = {int(track_id) for track_id in track_ids}
        if not expired:
            return
        camera_id = camera_id or "unknown-camera"
        with self._lock:
            pairs = self._interactions.get(camera_id)
            if pairs is None:
                return
            for key in [key for key in pairs if expired.intersection(key)]:
                pairs.pop(key, None)
            if not pairs:
                self._interactions.pop(camera_id, None)

    def reset_camera(self, camera_id: str) -> None:
        with self._lock:
            self._interactions.pop(camera_id or "unknown-camera", None)

    def reset_all(self) -> None:
        with self._lock:
            self._interactions.clear()
