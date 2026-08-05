"""Cleanup tool for crash cases created before the strict decision gates existed.

Finds pending_review / under_review cases that have NO recorded vehicle
detection boxes. Every current creation path (live monitor, image detection,
video detection, debug endpoint) always attaches vehicle boxes when it saves
a case, so a case with zero boxes on record is a strong signal it was
created by an old, unfixed code path — almost certainly a person-only or
no-vehicle false positive like the ones this audit targets.

This tool NEVER deletes anything. By default it only prints what it would
do (dry run). Pass --apply to actually transition matching cases through the
existing case state machine to false_alarm:

    pending_review --(review_alert)--> under_review --(mark_false_alarm)--> false_alarm

Usage:

    # Dry run — list suspect cases, change nothing.
    python backend/scripts/mark_suspect_cases_false_alarm.py

    # Actually mark them false_alarm (still no deletion).
    python backend/scripts/mark_suspect_cases_false_alarm.py --apply

    # Narrow scope.
    python backend/scripts/mark_suspect_cases_false_alarm.py --apply --camera-id CAM-TALOMO-CROSSING --limit 20
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.db import init_db  # noqa: E402
from backend.repositories.crash_cases import (  # noqa: E402
    apply_action,
    get_crash_case,
    list_crash_cases,
)

SCOPED_STATUSES = ("pending_review", "under_review")
DEFAULT_ACTOR_ID = "audit-script"
AUDIT_NOTE = (
    "Marked false_alarm by mark_suspect_cases_false_alarm.py: no vehicle "
    "detection boxes were ever recorded for this case, which the current "
    "pipeline always attaches when a real vehicle-involved crash is "
    "confirmed. Likely a person-only/no-vehicle false positive from before "
    "the strict crash decision gates."
)


def find_suspect_cases(
    *,
    status_filter: tuple[str, ...],
    camera_id: str | None,
    area_id: str | None,
    before: str | None,
    limit: int,
) -> list[dict]:
    suspects: list[dict] = []
    for status in status_filter:
        candidates = list_crash_cases(
            status=status,
            area_id=area_id or "all",
            to_date=before,
            sort="oldest",
            limit=max(limit * 4, 200),
        )
        for candidate in candidates:
            if camera_id and candidate.get("cameraId") != camera_id:
                continue
            full_case = get_crash_case(candidate["caseId"])
            if full_case is None:
                continue
            if full_case.get("boxes"):
                continue  # has recorded vehicle evidence — not a suspect
            suspects.append(full_case)
            if len(suspects) >= limit:
                return suspects
    return suspects


def describe(case: dict) -> str:
    return (
        f"caseId={case['caseId']} status={case['status']} "
        f"cameraId={case.get('cameraId') or 'unknown'} "
        f"sourceCamera={case.get('sourceCamera') or 'unknown'} "
        f"confidence={case.get('confidence')} "
        f"detectedAt={case.get('detectedAt')} "
        f"boxes={len(case.get('boxes') or [])}"
    )


def apply_false_alarm(case: dict, actor_id: str) -> None:
    case_id = case["caseId"]
    status = case["status"]
    if status == "pending_review":
        apply_action(case_id, "review_alert", actor_id, AUDIT_NOTE)
        status = "under_review"
    if status == "under_review":
        apply_action(case_id, "mark_false_alarm", actor_id, AUDIT_NOTE)
    else:
        print(f"  SKIPPED {case_id}: unexpected status {status!r} after review_alert; left untouched.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Find (and optionally mark false_alarm) pending/under-review crash "
            "cases with no recorded vehicle evidence. Never deletes anything."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually transition matching cases to false_alarm. Without this, dry run only.",
    )
    parser.add_argument("--camera-id", default=None, help="Only consider this camera.")
    parser.add_argument("--area-id", default=None, help="Only consider this area.")
    parser.add_argument(
        "--before",
        default=None,
        help="Only consider cases detected on/before this date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--status",
        default="pending_review,under_review",
        help="Comma-separated statuses to scan (default: pending_review,under_review).",
    )
    parser.add_argument("--limit", type=int, default=100, help="Max cases to process.")
    parser.add_argument("--actor-id", default=DEFAULT_ACTOR_ID, help="Actor id recorded on the action.")
    args = parser.parse_args()

    init_db()

    status_filter = tuple(
        status.strip() for status in args.status.split(",") if status.strip()
    )
    unknown = [status for status in status_filter if status not in SCOPED_STATUSES]
    if unknown:
        print(f"[cleanup] Refusing unsupported status filter(s): {unknown}. Allowed: {SCOPED_STATUSES}")
        return 2

    suspects = find_suspect_cases(
        status_filter=status_filter,
        camera_id=args.camera_id,
        area_id=args.area_id,
        before=args.before,
        limit=args.limit,
    )

    if not suspects:
        print("[cleanup] No suspect cases found (no vehicle-evidence-free pending/under-review cases).")
        return 0

    print(f"[cleanup] Found {len(suspects)} suspect case(s) with zero recorded vehicle boxes:")
    for case in suspects:
        print(f"  {describe(case)}")

    if not args.apply:
        print(
            "\n[cleanup] Dry run only - nothing was changed. "
            "Re-run with --apply to mark these cases false_alarm (no deletion)."
        )
        return 0

    print(f"\n[cleanup] Applying false_alarm to {len(suspects)} case(s) as actor={args.actor_id!r} ...")
    for case in suspects:
        apply_false_alarm(case, args.actor_id)
        print(f"  DONE {case['caseId']} -> false_alarm")

    print("[cleanup] Complete. No rows were deleted; all cases remain in case history.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
