import type { ResponderPresence } from '@/lib/phase3-api'

export function responderPresenceRank(responder: ResponderPresence): number {
  if (
    responder.presenceStatus === 'ONLINE' &&
    !responder.activeAssignmentId &&
    responder.availabilityStatus === 'AVAILABLE'
  ) return 0
  if (responder.presenceStatus === 'ONLINE') return 1
  return 3
}

export function sortRespondersByAvailability(
  responders: readonly ResponderPresence[]
): ResponderPresence[] {
  return [...responders].sort((left, right) =>
    responderPresenceRank(left) - responderPresenceRank(right) ||
    left.displayName.localeCompare(right.displayName)
  )
}

export function responderAssignmentLabel(responder: ResponderPresence): string {
  if (!responder.activeAssignmentId) return 'Available'
  const incident = responder.activeIncidentId?.slice(0, 8)
  return incident
    ? `Incident ${incident} · ${responder.activeAssignmentStatus ?? 'Assigned'}`
    : responder.activeAssignmentStatus ?? 'Assigned'
}

export function formatLastSeen(lastSeenAt: string | null, now = Date.now()): string {
  if (!lastSeenAt) return 'Never'
  const elapsedSeconds = Math.max(0, Math.floor((now - new Date(lastSeenAt).getTime()) / 1000))
  if (!Number.isFinite(elapsedSeconds)) return 'Unknown'
  if (elapsedSeconds < 10) return 'Now'
  if (elapsedSeconds < 60) return `${elapsedSeconds} sec ago`
  const minutes = Math.floor(elapsedSeconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.floor(minutes / 60)
  return `${hours} hr ago`
}
