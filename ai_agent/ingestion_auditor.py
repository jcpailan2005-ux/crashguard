"""
Emergency Dispatch Ingestion Auditor — Phase 1
================================================
First line of defense. Audits raw incoming automated alert payloads
for data integrity before passing to the Admin Review queue.

Standard Operating Procedures (Ingestion):
  Condition 1 — Valid Emergency        : PASS TO ADMIN
  Condition 2 — Malformed Data         : REJECT - DEAD PAYLOAD
  Condition 3 — Low-Priority/Maintenance: REROUTE TO IT

Usage (standalone):
    python ai_agent/ingestion_auditor.py

Usage (as module):
    from ai_agent.ingestion_auditor import audit_payload, RawPayload
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
# Enumerations
# ---------------------------------------------------------------------------
class IngestionStatus(str, Enum):
    PASS_TO_ADMIN  = "PASS TO ADMIN"
    DEAD_PAYLOAD   = "REJECT - DEAD PAYLOAD"
    REROUTE_TO_IT  = "REROUTE TO IT"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class RawPayload:
    """Raw incoming alert payload from the automated detection system."""
    incident_id:     Optional[str]
    automated_alert: Optional[str]
    location:        Optional[str]


@dataclass
class IngestionResult:
    """Structured Phase 1 audit result."""
    incident_id:      str
    ingestion_status: IngestionStatus
    reasoning:        str
    audited_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(
            {
                "incident_id":      self.incident_id,
                "ingestion_status": self.ingestion_status.value,
                "reasoning":        self.reasoning,
                "audited_at":       self.audited_at,
            },
            indent=indent,
        )


# ---------------------------------------------------------------------------
# Keyword sets
# ---------------------------------------------------------------------------
_IT_KEYWORDS: tuple[str, ...] = (
    "battery low",
    "camera offline",
    "routine ping",
    "sensor test",
    "maintenance",
    "self-test",
    "scheduled check",
    "heartbeat",
    "system check",
    "connectivity test",
    "firmware update",
    "reboot",
    "low signal",
    "signal lost",
    "offline",
)

_VALID_ALERT_MIN_LENGTH = 5   # characters — anything shorter is treated as corrupt


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------
def _classify(payload: RawPayload) -> tuple[IngestionStatus, str]:
    """
    Apply SOP rules in order of priority.
    Returns (IngestionStatus, reasoning).
    """
    # ── Condition 2 check: missing / corrupt ID ──────────────────────────────
    incident_id = (payload.incident_id or "").strip()
    if not incident_id:
        return (
            IngestionStatus.DEAD_PAYLOAD,
            "Payload is missing a valid `incident_id`. "
            "Under Ingestion SOP Condition 2, this is a dead payload and must be rejected.",
        )

    # ── Condition 2 check: missing / corrupt alert string ────────────────────
    alert = (payload.automated_alert or "").strip()
    if len(alert) < _VALID_ALERT_MIN_LENGTH:
        return (
            IngestionStatus.DEAD_PAYLOAD,
            f"The `automated_alert` field is empty or too short ({len(alert)} chars) "
            "and is treated as corrupted. "
            "Under Ingestion SOP Condition 2, this payload is rejected.",
        )

    # ── Condition 3 check: low-priority / IT maintenance keyword ─────────────
    alert_lower = alert.lower()
    matched_kw = next((kw for kw in _IT_KEYWORDS if kw in alert_lower), None)
    if matched_kw:
        return (
            IngestionStatus.REROUTE_TO_IT,
            f"The alert string contains the maintenance keyword \"{matched_kw}\". "
            "Under Ingestion SOP Condition 3, this payload is rerouted to IT "
            "and must not reach the Dispatch Admin.",
        )

    # ── Condition 2 check: missing location ──────────────────────────────────
    location = (payload.location or "").strip()
    if not location:
        return (
            IngestionStatus.DEAD_PAYLOAD,
            "Payload is missing location data. "
            "Under Ingestion SOP Condition 2, an alert without a location "
            "cannot be actioned and is rejected as a dead payload.",
        )

    # ── Condition 1: all checks passed ───────────────────────────────────────
    return (
        IngestionStatus.PASS_TO_ADMIN,
        f"Payload contains a valid incident_id ('{incident_id}'), "
        f"a recognizable alert string, and location data ('{location}'). "
        "Under Ingestion SOP Condition 1, this payload is cleared and "
        "passed to the Admin Review queue.",
    )


# ---------------------------------------------------------------------------
# Core auditor
# ---------------------------------------------------------------------------
def audit_payload(payload: RawPayload) -> IngestionResult:
    """
    Audit one RawPayload against the Ingestion SOP.

    Parameters
    ----------
    payload : RawPayload
        The raw automated alert data.

    Returns
    -------
    IngestionResult
        Structured Phase 1 audit result ready for JSON serialization.
    """
    incident_id = (payload.incident_id or "MISSING_ID").strip() or "MISSING_ID"
    status, reasoning = _classify(payload)

    # Side-effect logs that mirror real routing actions
    if status == IngestionStatus.PASS_TO_ADMIN:
        logger.info("✅  [PASS TO ADMIN]      %s → Admin Review queue", incident_id)
    elif status == IngestionStatus.DEAD_PAYLOAD:
        logger.warning("💀  [DEAD PAYLOAD]       %s → Rejected, not forwarded", incident_id)
    else:
        logger.info("🔧  [REROUTE TO IT]      %s → IT maintenance queue", incident_id)

    return IngestionResult(
        incident_id=incident_id,
        ingestion_status=status,
        reasoning=reasoning,
    )


# ---------------------------------------------------------------------------
# CLI demo — covers all three SOP conditions
# ---------------------------------------------------------------------------
def _run_demo() -> None:
    test_cases: list[tuple[str, RawPayload]] = [
        (
            "Condition 1 — Valid Emergency",
            RawPayload(
                incident_id="#9921-ECHO",
                automated_alert="Multi-vehicle collision detected by smart intersection camera.",
                location="5th Avenue & Main Street, Northbound Lane",
            ),
        ),
        (
            "Condition 2 — Missing Incident ID",
            RawPayload(
                incident_id="",
                automated_alert="Collision detected at highway junction.",
                location="Highway 7, KM 42",
            ),
        ),
        (
            "Condition 2 — Empty Alert String",
            RawPayload(
                incident_id="#0042-GHOST",
                automated_alert="",
                location="City Hall Intersection",
            ),
        ),
        (
            "Condition 2 — Missing Location",
            RawPayload(
                incident_id="#3390-FOXTROT",
                automated_alert="Pedestrian-vehicle proximity alert.",
                location="",
            ),
        ),
        (
            "Condition 3 — Battery Low (IT Reroute)",
            RawPayload(
                incident_id="#0011-MAINT",
                automated_alert="Camera battery low — power at 8% on Node 4.",
                location="Intersection Cam Node 4",
            ),
        ),
        (
            "Condition 3 — Camera Offline (IT Reroute)",
            RawPayload(
                incident_id="#0022-MAINT",
                automated_alert="Camera offline — no feed from Warehouse District Cam 7.",
                location="Warehouse District",
            ),
        ),
        (
            "Condition 3 — Routine Ping (IT Reroute)",
            RawPayload(
                incident_id="#0033-PING",
                automated_alert="Routine ping from sensor array — all nodes OK.",
                location="Central Hub",
            ),
        ),
    ]

    for label, payload in test_cases:
        print("\n" + "=" * 64)
        print(f"TEST: {label}")
        print("=" * 64)
        result = audit_payload(payload)
        print(result.to_json())


if __name__ == "__main__":
    _run_demo()
