import type {
  DispatcherIncidentAlarmTracker,
  DispatcherAlarmIncident,
  DispatcherAlarmNotification,
} from './incident-alarm-contract'

/** Shared production seam for polling and deterministic fixture tests. */
export function enqueueFreshDispatcherAlarms(
  tracker: DispatcherIncidentAlarmTracker,
  notifications: DispatcherAlarmNotification[],
  incidents: DispatcherAlarmIncident[],
  armed: boolean,
  pending: Promise<void>,
  attempt: (incidentId: string) => Promise<void>
): { pending: Promise<void>; eligible: string[]; attempted: string[] } {
  const eligible = tracker.consume(notifications, incidents)
  const attempted = armed ? eligible : []
  for (const incidentId of attempted) {
    // An earlier failed attempt must not suppress the next new incident.
    pending = pending.catch(() => undefined).then(() => attempt(incidentId))
  }
  return { pending, eligible, attempted }
}
