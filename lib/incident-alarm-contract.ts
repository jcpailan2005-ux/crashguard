export interface IncidentAlarmResult {
  incident_created?: boolean
  incidentCreated?: boolean
  incident_id?: string | null
  incidentId?: string | null
  caseId?: string | null
  caseCreated?: boolean | null
  persistenceStatus?: string | null
  persistenceReason?: string | null
  finalDecision?: string | null
  accident_detected?: boolean
  existingCase?: boolean | null
  timestamp?: string
}

/** Backend confirmation owns the decision; UI sample smoothing is display-only. */
export function isCurrentCrashConfirmed(result: IncidentAlarmResult): boolean {
  return result.accident_detected === true && result.finalDecision === 'confirmed_crash'
}

export function collisionResultLabel(result: IncidentAlarmResult): string {
  if (isCurrentCrashConfirmed(result)) return 'Collision detected - review required'
  if (result.finalDecision === 'possible_crash_aftermath') return 'Possible aftermath - review required'
  if (result.finalDecision === 'candidate' || result.finalDecision === 'verifying') return 'Potential collision - verifying'
  if (result.finalDecision === 'possible_crash' || result.accident_detected) return 'Possible crash - review required'
  return 'No collision classified'
}

export class LiveAlarmTracker {
  private seen = new Set<string>()
  private startedAt: number
  constructor(startedAt = Date.now()) { this.startedAt = startedAt }

  consume(result: IncidentAlarmResult): boolean {
    const id = result.incident_id ?? result.incidentId ?? null
    if (!id) return false
    const created = result.incidentCreated === true || result.incident_created === true
    const timestamp = Date.parse(result.timestamp ?? '')
    const fresh = Number.isFinite(timestamp) && timestamp >= this.startedAt
    if (this.seen.has(id)) return false
    if (!fresh || result.existingCase || result.persistenceReason === 'duplicate_active_case') {
      this.seen.add(id)
      return false
    }
    const alarmWorthy = isCurrentCrashConfirmed(result) ||
      (result.finalDecision === 'possible_crash_aftermath' && result.caseCreated === true)
    if (!created || !alarmWorthy) return false
    this.seen.add(id)
    return true
  }
}

// Shared by the selected camera and background tiles, including component remounts.
export const liveAlarmTracker = new LiveAlarmTracker()

export function getOperationalIncidentId(result: IncidentAlarmResult): string | null {
  return result.incident_id ?? result.incidentId ?? result.caseId ?? null
}

export function shouldEmitOperationalAlarm(
  result: IncidentAlarmResult,
  lastAlarmedIncidentId: string | null
): boolean {
  const incidentCreated = result.incident_created === true || result.incidentCreated === true
  const incidentId = result.incident_id ?? result.incidentId ?? null
  return Boolean(incidentCreated && incidentId && incidentId !== lastAlarmedIncidentId &&
    isCurrentCrashConfirmed(result))
}

export interface DispatcherAlarmNotification {
  id: string
  incidentId?: string | null
  type: string
  createdAt: string
}

export interface DispatcherAlarmIncident {
  id: string
  detectionMode: string
  createdAt?: string
  evidenceSummary?: { finalDecision?: unknown }
}

/** Only a newly delivered confirmed collision or saved crash aftermath can trigger once. */
export class DispatcherIncidentAlarmTracker {
  private seen = new Set<string>()
  private readonly startedAt: number
  constructor(startedAt = Date.now()) { this.startedAt = startedAt }

  consume(_notifications: DispatcherAlarmNotification[], incidents: DispatcherAlarmIncident[], notBefore = this.startedAt): string[] {
    const fresh: string[] = []
    // The committed incident is authoritative even if notification delivery is
    // delayed or the two polling snapshots straddle its creation transaction.
    // Persistent, high-confidence aftermath reviews also require an immediate
    // dispatcher response, even though impact was not observed on camera.
    for (const incident of incidents) {
      const decision = incident.evidenceSummary?.finalDecision
      const confirmedCollision = incident.detectionMode === 'temporal_collision' &&
        (decision == null || decision === 'confirmed_crash')
      const crashAftermath = incident.detectionMode === 'aftermath_review' &&
        decision === 'possible_crash_aftermath'
      if (!confirmedCollision && !crashAftermath) continue
      const createdAt = Date.parse(incident.createdAt ?? '')
      if (!Number.isFinite(createdAt) || createdAt < Math.max(this.startedAt, notBefore)) continue
      if (this.seen.has(incident.id)) continue
      this.seen.add(incident.id)
      fresh.push(incident.id)
    }
    return fresh
  }
}
