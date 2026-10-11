"""Isolated, bounded pair-owned hit bookkeeping; not a collision verifier.

The caller must supply identities backed by real accepted detections. This
module never invents vehicles, associates boxes, or authorizes an incident.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class PairHitState:
    pair_id: tuple[int, int]
    first_observation: int
    last_observation: int
    first_at: float
    last_at: float
    supporting_observations: deque[int] = field(default_factory=lambda: deque(maxlen=16))
    qualifying_observations: deque[int] = field(default_factory=lambda: deque(maxlen=16))
    hit_times: deque[float] = field(default_factory=lambda: deque(maxlen=16))
    classifier_evidence: deque[float] = field(default_factory=lambda: deque(maxlen=16))
    geometry_evidence: deque[bool] = field(default_factory=lambda: deque(maxlen=16))
    interaction_evidence: deque[bool] = field(default_factory=lambda: deque(maxlen=16))
    streak: int = 0
    window_start: float | None = None
    expires_at: float = 0.0
    confirmed: bool = False


class PairHitLedger:
    """Independent 3-hit/5-second histories for externally verified pair IDs."""

    def __init__(self, *, window_seconds: float = 5.0, required_hits: int = 3,
                 max_pairs: int = 64) -> None:
        if window_seconds <= 0 or required_hits < 1 or max_pairs < 1:
            raise ValueError("Pair ledger bounds must be positive")
        self.window_seconds = window_seconds
        self.required_hits = required_hits
        self.max_pairs = max_pairs
        self._pairs: dict[tuple[int, int], PairHitState] = {}

    def observe(self, pair: tuple[int, int], *, sequence: int, timestamp: float,
                qualified: bool, classifier_score: float = 0.0,
                geometry: bool = False, interaction: bool = False) -> PairHitState:
        if len(pair) != 2 or pair[0] == pair[1]:
            raise ValueError("A pair needs two distinct observed track identities")
        key = tuple(sorted((int(pair[0]), int(pair[1]))))
        self.expire(timestamp)
        state = self._pairs.get(key)
        if state is not None and sequence <= state.last_observation:
            return state  # duplicate/out-of-order observations cannot add hits
        if state is None:
            if len(self._pairs) >= self.max_pairs:
                oldest = min(self._pairs, key=lambda item: self._pairs[item].last_at)
                self._pairs.pop(oldest)
            state = PairHitState(key, sequence, sequence, timestamp, timestamp)
            self._pairs[key] = state
        state.last_observation = sequence
        state.last_at = timestamp
        state.expires_at = timestamp + self.window_seconds
        state.supporting_observations.append(sequence)
        state.classifier_evidence.append(float(classifier_score))
        state.geometry_evidence.append(bool(geometry))
        state.interaction_evidence.append(bool(interaction))
        if not qualified:
            state.streak = 0
            state.window_start = None
            state.hit_times.clear()
            return state
        while state.hit_times and timestamp - state.hit_times[0] > self.window_seconds:
            state.hit_times.popleft()
        state.hit_times.append(timestamp)
        state.qualifying_observations.append(sequence)
        state.streak = len(state.hit_times)
        state.window_start = state.hit_times[0]
        return state

    def ready(self, pair: tuple[int, int]) -> bool:
        state = self._pairs.get(tuple(sorted(pair)))
        return bool(state and state.streak >= self.required_hits)

    def expire(self, timestamp: float) -> None:
        for key in [key for key, state in self._pairs.items() if timestamp > state.expires_at]:
            self._pairs.pop(key)

    def expire_track(self, track_id: int) -> None:
        for key in [key for key in self._pairs if track_id in key]:
            self._pairs.pop(key)

    def reset(self) -> None:
        self._pairs.clear()

    @property
    def active_pair_count(self) -> int:
        return len(self._pairs)
