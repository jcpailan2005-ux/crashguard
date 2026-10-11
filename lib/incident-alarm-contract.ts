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
    if (!created || !isCurrentCrashConfirmed(result)) return false
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
}

/** Only a newly delivered confirmed-collision incident can trigger once. */
export class DispatcherIncidentAlarmTracker {
  private seen = new Set<string>()
  private readonly startedAt: number
  constructor(startedAt = Date.now()) { this.startedAt = startedAt }

  consume(notifications: DispatcherAlarmNotification[], incidents: DispatcherAlarmIncident[]): string[] {
    const byId = new Map(incidents.map((incident) => [incident.id, incident]))
    const fresh: string[] = []
    for (const notification of notifications) {
      if (notification.type !== 'NEW_CRASH_REVIEW' || !notification.incidentId) continue
      const incident = byId.get(notification.incidentId)
      if (!incident || incident.detectionMode !== 'temporal_collision') continue
      const createdAt = Date.parse(incident.createdAt ?? notification.createdAt)
      if (!Number.isFinite(createdAt) || createdAt < this.startedAt) continue
      if (this.seen.has(incident.id)) continue
      this.seen.add(incident.id)
      fresh.push(incident.id)
    }
    return fresh
  }
}
