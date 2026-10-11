"""Per-camera detector-event lifecycle for Phase 1 crash verification.

Detector state is intentionally independent from dispatcher review status. A
pending review case may outlive the physical event that produced it; after the
scene clears, the same camera can therefore start a new detector event.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime


EVENT_STATES = {
    "IDLE",
    "CANDIDATE",
    "VERIFYING",
    "CONFIRMED",
    "ACTIVE",
    "CLEARED",
    "COOLDOWN",
}


@dataclass
class DetectorEvent:
    event_id: str
    camera_id: str
    state: str
    started_at: float
    confirmed_at: float | None = None
    cleared_at: float | None = None
    incident_id: str | None = None
    positive_times: deque[float] = field(default_factory=deque)
    consecutive_negatives: int = 0
    clear_started_at: float | None = None
    persistence_in_progress: bool = False
    persistence_error: str | None = None
    last_seen_at: float = 0.0
    detection_mode: str | None = None


@dataclass(frozen=True)
class EventObservation:
    camera_id: str
    event_state: str
    detector_event_id: str | None
    incident_id: str | None
    positive_history: int
    should_persist: bool = False
    incident_created: bool = False
    duplicate_event: bool = False
    previous_state: str | None = None
    persistence_error: str | None = None
    detection_mode: str | None = None


class CrashEventManager:
    """Own detector-event state and persistence claims for each camera."""

    MAX_TRACKED_CAMERAS = 512

    def __init__(
        self,
        *,
        required_positive_observations: int,
        temporal_window_seconds: float,
        clear_consecutive_negatives: int,
        clear_seconds: float,
        cooldown_seconds: float,
    ) -> None:
        self.required_positive_observations = max(2, required_positive_observations)
        self.temporal_window_seconds = max(0.1, temporal_window_seconds)
        self.clear_consecutive_negatives = max(1, clear_consecutive_negatives)
        self.clear_seconds = max(0.0, clear_seconds)
        self.cooldown_seconds = max(0.0, cooldown_seconds)
        self._events: dict[str, DetectorEvent] = {}
        self._lock = threading.RLock()

    def _log(
        self,
        *,
        camera_id: str,
        event: DetectorEvent | None,
        previous_state: str | None,
        classifier_score: float | None = None,
        incident_created: bool = False,
        duplicate_event: bool = False,
        persistence_result: str | None = None,
        error: str | None = None,
    ) -> None:
        timestamp = datetime.now().isoformat()
        print(
            "[crash-event] "
            f"timestamp={timestamp} "
            f"camera={camera_id} "
            f"event={(event.event_id if event else 'none')} "
            f"incident={(event.incident_id if event and event.incident_id else 'none')} "
            f"detectionMode={(event.detection_mode if event and event.detection_mode else 'none')} "
            f"previousState={previous_state or 'none'} "
            f"newState={(event.state if event else 'IDLE')} "
            f"classifierScore={(f'{classifier_score:.4f}' if classifier_score is not None else 'none')} "
            f"positiveHistory={(len(event.positive_times) if event else 0)} "
            f"duplicateEvent={duplicate_event} "
            f"incidentCreated={incident_created} "
            f"persistenceResult={persistence_result or 'none'} "
            f"error={error or 'none'}"
        )

    def _result(
        self,
        camera_id: str,
        event: DetectorEvent | None,
        *,
        previous_state: str | None = None,
        should_persist: bool = False,
        incident_created: bool = False,
        duplicate_event: bool = False,
    ) -> EventObservation:
        return EventObservation(
            camera_id=camera_id,
            event_state=event.state if event else "IDLE",
            detector_event_id=event.event_id if event else None,
            incident_id=event.incident_id if event else None,
            positive_history=len(event.positive_times) if event else 0,
            should_persist=should_persist,
            incident_created=incident_created,
            duplicate_event=duplicate_event,
            previous_state=previous_state,
            persistence_error=event.persistence_error if event else None,
            detection_mode=event.detection_mode if event else None,
        )

    def _start_event(
        self,
        camera_id: str,
        now: float,
        classifier_score: float,
        detection_mode: str | None = None,
    ) -> EventObservation:
        if len(self._events) >= self.MAX_TRACKED_CAMERAS and camera_id not in self._events:
            oldest_camera = min(
                self._events,
                key=lambda key: self._events[key].last_seen_at,
            )
            self._events.pop(oldest_camera, None)
        event = DetectorEvent(
            event_id=str(uuid.uuid4()),
            camera_id=camera_id,
            state="CANDIDATE",
            started_at=now,
            positive_times=deque([now]),
            last_seen_at=now,
            detection_mode=detection_mode,
        )
        self._events[camera_id] = event
        self._log(
            camera_id=camera_id,
            event=event,
            previous_state="IDLE",
            classifier_score=classifier_score,
        )
        return self._result(camera_id, event, previous_state="IDLE")

    def observe(
        self,
        camera_id: str,
        *,
        positive: bool,
        interaction_candidate: bool,
        classifier_score: float,
        now: float | None = None,
        detection_mode: str | None = None,
    ) -> EventObservation:
        """Record one gated observation.

        ``positive`` represents classifier + quality + vehicle + ROI gates.
        Static box proximity is only ``interaction_candidate`` evidence. Both
        are needed to advance the conservative Phase-1 temporal verifier.
        """
        now = time.time() if now is None else now
        camera_id = camera_id or "unknown-camera"
        qualified = bool(positive and interaction_candidate)

        with self._lock:
            event = self._events.get(camera_id)
            if event is None:
                if qualified:
                    return self._start_event(
                        camera_id, now, classifier_score, detection_mode
                    )
                return self._result(camera_id, None)

            event.last_seen_at = now
            previous_state = event.state

            if event.state in {"CLEARED", "COOLDOWN"}:
                event.state = "COOLDOWN"
                cooldown_started = event.cleared_at if event.cleared_at is not None else now
                if now - cooldown_started < self.cooldown_seconds:
                    return self._result(
                        camera_id,
                        event,
                        previous_state=previous_state,
                        duplicate_event=qualified,
                    )
                self._events.pop(camera_id, None)
                if qualified:
                    return self._start_event(
                        camera_id, now, classifier_score, detection_mode
                    )
                return self._result(camera_id, None, previous_state="COOLDOWN")

            if event.state in {"CONFIRMED", "ACTIVE"}:
                if qualified:
                    event.consecutive_negatives = 0
                    event.clear_started_at = None
                    should_persist = (
                        event.state == "CONFIRMED"
                        and event.incident_id is None
                        and not event.persistence_in_progress
                    )
                    if should_persist:
                        event.persistence_in_progress = True
                    duplicate = not should_persist
                    if duplicate or should_persist:
                        self._log(
                            camera_id=camera_id,
                            event=event,
                            previous_state=previous_state,
                            classifier_score=classifier_score,
                            duplicate_event=duplicate,
                            persistence_result="retry_claimed" if should_persist else None,
                        )
                    return self._result(
                        camera_id,
                        event,
                        previous_state=previous_state,
                        should_persist=should_persist,
                        duplicate_event=duplicate,
                    )

                event.consecutive_negatives += 1
                if event.clear_started_at is None:
                    event.clear_started_at = now
                clear_elapsed = now - event.clear_started_at
                if (
                    event.consecutive_negatives >= self.clear_consecutive_negatives
                    and clear_elapsed >= self.clear_seconds
                ):
                    event.state = "CLEARED"
                    event.cleared_at = now
                    event.positive_times.clear()
                    event.persistence_in_progress = False
                    self._log(
                        camera_id=camera_id,
                        event=event,
                        previous_state=previous_state,
                        classifier_score=classifier_score,
                        persistence_result="event_cleared",
                    )
                return self._result(camera_id, event, previous_state=previous_state)

            if not qualified:
                self._events.pop(camera_id, None)
                self._log(
                    camera_id=camera_id,
                    event=None,
                    previous_state=previous_state,
                    classifier_score=classifier_score,
                    persistence_result="candidate_reset",
                )
                return self._result(camera_id, None, previous_state=previous_state)

            event.positive_times.append(now)
            if (
                detection_mode == "temporal_collision"
                and event.state != "ACTIVE"
            ):
                event.detection_mode = "temporal_collision"
            while (
                event.positive_times
                and now - event.positive_times[0] > self.temporal_window_seconds
            ):
                event.positive_times.popleft()

            if len(event.positive_times) >= self.required_positive_observations:
                event.state = "CONFIRMED"
                event.confirmed_at = now
                event.persistence_in_progress = True
                should_persist = True
            else:
                event.state = "VERIFYING"
                should_persist = False

            self._log(
                camera_id=camera_id,
                event=event,
                previous_state=previous_state,
                classifier_score=classifier_score,
                persistence_result="claimed" if should_persist else None,
            )
            return self._result(
                camera_id,
                event,
                previous_state=previous_state,
                should_persist=should_persist,
            )

    def mark_persisted(
        self,
        camera_id: str,
        detector_event_id: str,
        incident_id: str,
        *,
        now: float | None = None,
    ) -> EventObservation:
        now = time.time() if now is None else now
        with self._lock:
            event = self._events.get(camera_id)
            if event is None or event.event_id != detector_event_id:
                raise ValueError("Detector event is no longer active for this camera.")
            previous_state = event.state
            event.state = "ACTIVE"
            event.incident_id = incident_id
            event.persistence_in_progress = False
            event.persistence_error = None
            event.last_seen_at = now
            self._log(
                camera_id=camera_id,
                event=event,
                previous_state=previous_state,
                incident_created=True,
                persistence_result="committed",
            )
            return self._result(
                camera_id,
                event,
                previous_state=previous_state,
                incident_created=True,
            )

    def mark_persistence_failed(
        self,
        camera_id: str,
        detector_event_id: str,
        error: str,
        *,
        now: float | None = None,
    ) -> EventObservation:
        now = time.time() if now is None else now
        with self._lock:
            event = self._events.get(camera_id)
            if event is None or event.event_id != detector_event_id:
                raise ValueError("Detector event is no longer active for this camera.")
            previous_state = event.state
            event.state = "CONFIRMED"
            event.persistence_in_progress = False
            event.persistence_error = error
            event.last_seen_at = now
            self._log(
                camera_id=camera_id,
                event=event,
                previous_state=previous_state,
                persistence_result="failed",
                error=error,
            )
            return self._result(camera_id, event, previous_state=previous_state)

    def snapshot(self, camera_id: str) -> EventObservation:
        with self._lock:
            return self._result(camera_id, self._events.get(camera_id))

    def reset_camera(self, camera_id: str) -> None:
        """Forget detector identity when a camera source is explicitly stopped."""
        with self._lock:
            self._events.pop(camera_id or "unknown-camera", None)

    def reset_all(self) -> None:
        with self._lock:
            self._events.clear()
