"""Single precedence point for temporal-collision and aftermath evidence."""

from __future__ import annotations

from dataclasses import dataclass

from backend.services.crash_aftermath_detector import AftermathDecision
from backend.services.temporal_crash_verifier import TemporalCrashDecision


@dataclass(frozen=True)
class ResolvedCrashEvidence:
    detection_mode: str
    should_signal_event: bool
    is_candidate: bool
    final_decision: str | None
    score: float
    reason: str


def resolve_crash_evidence(
    temporal: TemporalCrashDecision,
    aftermath: AftermathDecision,
) -> ResolvedCrashEvidence:
    """Prefer observed collision evidence and emit at most one event signal."""
    if temporal.is_verified:
        return ResolvedCrashEvidence(
            detection_mode="temporal_collision",
            should_signal_event=True,
            is_candidate=True,
            final_decision="confirmed_crash",
            score=temporal.score,
            reason="verified_temporal_collision",
        )
    if aftermath.review_candidate:
        return ResolvedCrashEvidence(
            detection_mode="aftermath_review",
            should_signal_event=True,
            is_candidate=True,
            final_decision="possible_crash_aftermath",
            score=aftermath.score,
            reason="persistent_crash_aftermath",
        )
    return ResolvedCrashEvidence(
        detection_mode="none",
        should_signal_event=False,
        is_candidate=bool(temporal.is_candidate or aftermath.is_suspected),
        final_decision=None,
        score=max(temporal.score, aftermath.score),
        reason=(aftermath.reason if aftermath.is_suspected else temporal.reason),
    )
