"""
Emergency Dispatch Audit System
================================
Evaluates incoming accident reports against the Admin's manual assessment
and triggers the correct system action for Responder notifications.

Standard Operating Procedures (SOP):
  Condition A — Verified Accident : Approve dispatch, trigger notification.
  Condition B — False Alarm       : Reject dispatch, cancel notification.
  Condition C — Pending Review    : Hold notification until Admin acts.

Usage (standalone):
    python ai_agent/dispatch_audit.py

Usage (as a module):
    from ai_agent.dispatch_audit import process_incident, IncidentReport
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations — enforces value compliance at the type level
# ---------------------------------------------------------------------------
class EventStatus(str, Enum):
    VERIFIED_ACCIDENT = "Verified Accident"
    FALSE_ALARM = "False Alarm"
    PENDING_REVIEW = "Pending Review"


class AdminAction(str, Enum):
    CONFIRMED = "Confirmed"
    FLAGGED_AS_FALSE = "Flagged as False"
    PENDING = "Pending"


class SystemAction(str, Enum):
    DISPATCH_SENT = "Dispatch Notification Sent to Responder"
    NOTIFICATION_CANCELLED = "Notification Cancelled"
    NOTIFICATION_HELD = "Notification Held"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class IncidentReport:
    """Raw input received by the audit controller."""
    incident_id: str
    automated_alert: str
    admin_assessment: str


@dataclass
class AuditDecision:
    """Structured output of the audit evaluation."""
    incident_id: str
    event_status: EventStatus
    admin_action: AdminAction
    system_action: SystemAction
    reasoning: str
    evaluated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_json(self, indent: int = 2) -> str:
        """Serialize to a strict JSON string (no extra keys)."""
        return json.dumps(
            {
                "incident_id": self.incident_id,
                "event_status": self.event_status.value,
                "admin_action": self.admin_action.value,
                "system_action": self.system_action.value,
                "reasoning": self.reasoning,
                "evaluated_at": self.evaluated_at,
            },
            indent=indent,
        )


# ---------------------------------------------------------------------------
# Mock notification functions
# ---------------------------------------------------------------------------
def send_notification(incident_id: str, alert: str) -> None:
    """
    MOCK — In production, replace with a real push notification,
    SMS gateway, radio dispatch API, or webhook call.
    """
    logger.info(
        "📡  [NOTIFICATION SENT] Responder alerted for incident %s | Alert: %s",
        incident_id,
        alert,
    )


def cancel_notification(incident_id: str) -> None:
    """
    MOCK — In production, replace with logic that revokes a pending
    notification token or marks the alert as suppressed in the queue.
    """
    logger.info(
        "🚫  [NOTIFICATION CANCELLED] Dispatch suppressed for incident %s",
        incident_id,
    )


def hold_notification(incident_id: str) -> None:
    """
    MOCK — In production, replace with logic that queues the notification
    and waits for a subsequent Admin decision webhook/callback.
    """
    logger.info(
        "⏸️   [NOTIFICATION HELD] Awaiting Admin decision for incident %s",
        incident_id,
    )


# ---------------------------------------------------------------------------
# Keyword sets — drives the SOP classifier
# ---------------------------------------------------------------------------
_CONFIRM_KEYWORDS: tuple[str, ...] = (
    "confirmed",
    "confirm",
    "verified",
    "actual accident",
    "real accident",
    "crash confirmed",
    "collision confirmed",
    "real crash",
    "immediate assistance required",
    "dispatch required",
    "send help",
    "responders needed",
)

_FALSE_ALARM_KEYWORDS: tuple[str, ...] = (
    "false alarm",
    "not an accident",
    "no accident",
    "test alert",
    "drill",
    "simulation",
    "no crash",
    "no collision",
    "no incident",
    "cancel",
    "disregard",
    "flag",
    "flagged",
    "reject",
)


def _classify_assessment(admin_assessment: str) -> tuple[AdminAction, EventStatus, SystemAction, str]:
    """
    Classify the Admin Assessment text against SOP conditions.

    Returns (admin_action, event_status, system_action, reasoning).
    Defaults to Condition C (Pending Review) for any ambiguous input.
    """
    text = admin_assessment.strip().lower()

    # Guard: empty or missing assessment → Condition C
    if not text:
        return (
            AdminAction.PENDING,
            EventStatus.PENDING_REVIEW,
            SystemAction.NOTIFICATION_HELD,
            "Admin Assessment is empty or missing. Under Condition C of the SOP, "
            "missing data defaults to Pending Review and the notification is held.",
        )

    # Condition B check first — false alarm takes precedence over ambiguous confirms
    if any(kw in text for kw in _FALSE_ALARM_KEYWORDS):
        return (
            AdminAction.FLAGGED_AS_FALSE,
            EventStatus.FALSE_ALARM,
            SystemAction.NOTIFICATION_CANCELLED,
            "The Admin Assessment contains a false alarm or test flag. "
            "Under Condition B of the SOP, the dispatch is rejected and the "
            "Responder notification is explicitly cancelled.",
        )

    # Condition A — confirmed accident
    if any(kw in text for kw in _CONFIRM_KEYWORDS):
        return (
            AdminAction.CONFIRMED,
            EventStatus.VERIFIED_ACCIDENT,
            SystemAction.DISPATCH_SENT,
            "The Admin Assessment confirms an actual accident occurred. "
            "Under Condition A of the SOP, the dispatch is approved and the "
            "notification is immediately sent to the Responder.",
        )

    # Condition C — unrecognized or ambiguous assessment
    return (
        AdminAction.PENDING,
        EventStatus.PENDING_REVIEW,
        SystemAction.NOTIFICATION_HELD,
        "The Admin Assessment could not be unambiguously mapped to Condition A or B. "
        "Under Condition C of the SOP, the notification is held until a clear "
        "Admin decision is provided.",
    )


# ---------------------------------------------------------------------------
# Core processor
# ---------------------------------------------------------------------------
def process_incident(report: IncidentReport) -> AuditDecision:
    """
    Evaluate one IncidentReport against the SOP and trigger the
    appropriate mock notification action.

    Parameters
    ----------
    report : IncidentReport
        The incoming accident report.

    Returns
    -------
    AuditDecision
        Structured audit result ready for JSON serialization.
    """
    # Validate incident_id
    incident_id = (report.incident_id or "PENDING_INPUT").strip() or "PENDING_INPUT"

    # If incident_id itself is missing, force Condition C regardless of assessment
    if incident_id == "PENDING_INPUT":
        admin_action = AdminAction.PENDING
        event_status = EventStatus.PENDING_REVIEW
        system_action = SystemAction.NOTIFICATION_HELD
        reasoning = (
            "Incident ID is missing. Under Condition C of the SOP, "
            "missing data defaults to Pending Review and the notification is held."
        )
    else:
        admin_action, event_status, system_action, reasoning = _classify_assessment(
            report.admin_assessment
        )

    # --- Side effects: trigger mock notification functions ---
    if system_action == SystemAction.DISPATCH_SENT:
        send_notification(incident_id, report.automated_alert)
    elif system_action == SystemAction.NOTIFICATION_CANCELLED:
        cancel_notification(incident_id)
    else:
        hold_notification(incident_id)

    return AuditDecision(
        incident_id=incident_id,
        event_status=event_status,
        admin_action=admin_action,
        system_action=system_action,
        reasoning=reasoning,
    )


# ---------------------------------------------------------------------------
# CLI demo — runs three representative test cases
# ---------------------------------------------------------------------------
def _run_demo() -> None:
    test_cases: list[IncidentReport] = [
        # Condition A — Verified Accident
        IncidentReport(
            incident_id="#9921-ECHO",
            automated_alert=(
                "Multi-vehicle collision detected by smart intersection camera "
                "at 5th and Main."
            ),
            admin_assessment=(
                "Admin manually reviewed the live camera feed and confirmed a "
                "two-car crash blocking the northbound lane. "
                "Immediate assistance required."
            ),
        ),
        # Condition B — False Alarm
        IncidentReport(
            incident_id="#7743-BRAVO",
            automated_alert="Collision alert triggered at Warehouse District Cam 4.",
            admin_assessment=(
                "Admin reviewed footage. This is a false alarm — vehicles were "
                "merging normally. No dispatch needed."
            ),
        ),
        # Condition C — Pending Review
        IncidentReport(
            incident_id="#5501-DELTA",
            automated_alert="Pedestrian-vehicle proximity alert near City Hall.",
            admin_assessment="",  # Admin has not yet assessed
        ),
    ]

    for report in test_cases:
        print("\n" + "=" * 60)
        print(f"Processing Incident: {report.incident_id}")
        print("=" * 60)
        decision = process_incident(report)
        print(decision.to_json())


if __name__ == "__main__":
    _run_demo()
