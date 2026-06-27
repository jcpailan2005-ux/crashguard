export const CASE_STATUSES = [
  'pending_review',
  'under_review',
  'confirmed_crash',
  'false_alarm',
  'dispatched',
  'resolved',
] as const

export type CaseStatus = (typeof CASE_STATUSES)[number]

export const CASE_ACTIONS = [
  'review_alert',
  'confirm_crash',
  'mark_false_alarm',
  'dispatch_help',
  'contact_user',
  'add_notes',
  'resolve_case',
] as const

export type CaseActionType = (typeof CASE_ACTIONS)[number]

export const CASE_STATUS_LABELS: Record<CaseStatus, string> = {
  pending_review: 'Pending Review',
  under_review: 'Under Review',
  confirmed_crash: 'Confirmed Crash',
  false_alarm: 'False Alarm',
  dispatched: 'Dispatched',
  resolved: 'Resolved',
}

export const CASE_ACTION_LABELS: Record<CaseActionType, string> = {
  review_alert: 'Review Alert',
  confirm_crash: 'Confirm Crash',
  mark_false_alarm: 'Mark as False Alarm',
  dispatch_help: 'Dispatch Help',
  contact_user: 'Contact User',
  add_notes: 'Add Notes',
  resolve_case: 'Resolve Case',
}

export const CASE_ACTION_NEXT_STATUS: Partial<Record<CaseActionType, CaseStatus>> = {
  review_alert: 'under_review',
  confirm_crash: 'confirmed_crash',
  mark_false_alarm: 'false_alarm',
  dispatch_help: 'dispatched',
  resolve_case: 'resolved',
}

export const ACTIVE_CASE_STATUSES = new Set<CaseStatus>([
  'pending_review',
  'under_review',
  'confirmed_crash',
  'dispatched',
])

export function isCaseStatus(value: unknown): value is CaseStatus {
  return typeof value === 'string' && CASE_STATUSES.includes(value as CaseStatus)
}

export function getCaseStatusLabel(status: CaseStatus) {
  return CASE_STATUS_LABELS[status]
}
