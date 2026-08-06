import { CaseStatus } from '@/lib/incident-status'

export const CASE_STATUS_CLASSES: Record<CaseStatus, string> = {
  pending_review:
    'border-[var(--status-pending)] bg-[color:var(--status-pending-bg)] text-[var(--status-pending)]',
  under_review:
    'border-[var(--status-under-review)] bg-[color:var(--status-under-review-bg)] text-[var(--status-under-review)]',
  confirmed_crash:
    'border-[var(--status-confirmed)] bg-[color:var(--status-confirmed-bg)] text-[var(--status-confirmed)]',
  false_alarm:
    'border-[var(--status-false-alarm)] bg-[color:var(--status-false-alarm-bg)] text-[var(--status-false-alarm)]',
  dispatched:
    'border-[var(--status-dispatched)] bg-[color:var(--status-dispatched-bg)] text-[var(--status-dispatched)]',
  responding:
    'border-[var(--status-dispatched)] bg-[color:var(--status-dispatched-bg)] text-[var(--status-dispatched)]',
  arrived:
    'border-[var(--status-confirmed)] bg-[color:var(--status-confirmed-bg)] text-[var(--status-confirmed)]',
  resolved:
    'border-[var(--status-resolved)] bg-[color:var(--status-resolved-bg)] text-[var(--status-resolved)]',
}

export function getCaseStatusClass(status: CaseStatus) {
  return CASE_STATUS_CLASSES[status]
}
