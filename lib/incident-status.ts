export const CASE_STATUSES = [
  'pending_review',
  'under_review',
  'confirmed_crash',
  'false_alarm',
  'dispatched',
  'responding',
  'arrived',
  'resolved',
] as const

export type CaseStatus = (typeof CASE_STATUSES)[number]

export const CASE_ACTIONS = [
  'review_alert',
  'confirm_crash',
  'mark_false_alarm',
  'dispatch_help',
  'accept_dispatch',
  'arrive_scene',
  'contact_user',
  'add_notes',
  'resolve_case',
] as const

export type CaseActionType = (typeof CASE_ACTIONS)[number]

export const CASE_STATUS_LABELS: Record<CaseStatus, string> = {
  pending_review: 'Pending Review',
  under_review: 'Under Review',
  confirmed_crash: 'Verified Crash',
  false_alarm: 'False Alarm',
  dispatched: 'Dispatched',
  responding: 'Responding',
  arrived: 'Arrived at Scene',
  resolved: 'Resolved',
}

export const CASE_ACTION_LABELS: Record<CaseActionType, string> = {
  review_alert: 'Start Review',
  confirm_crash: 'Verify Crash',
  mark_false_alarm: 'False Alarm',
  dispatch_help: 'Approve & Dispatch',
  accept_dispatch: 'Accept Dispatch',
  arrive_scene: 'Mark Arrived',
  contact_user: 'Contact User',
  add_notes: 'Add Notes',
  resolve_case: 'Resolve Case',
}

export const CASE_ACTION_NEXT_STATUS: Partial<Record<CaseActionType, CaseStatus>> = {
  review_alert: 'under_review',
  confirm_crash: 'confirmed_crash',
  mark_false_alarm: 'false_alarm',
  dispatch_help: 'dispatched',
  accept_dispatch: 'responding',
  arrive_scene: 'arrived',
  resolve_case: 'resolved',
}

export const ACTIVE_CASE_STATUSES = new Set<CaseStatus>([
  'pending_review',
  'under_review',
  'confirmed_crash',
  'dispatched',
  'responding',
  'arrived',
])

export function isCaseStatus(value: unknown): value is CaseStatus {
  return typeof value === 'string' && CASE_STATUSES.includes(value as CaseStatus)
}

export function getCaseStatusLabel(status: CaseStatus) {
  return CASE_STATUS_LABELS[status]
}
