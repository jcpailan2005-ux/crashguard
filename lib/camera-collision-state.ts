import type { CameraMonitoringStatus } from './api-client'
import type { DetectionResponse, LiveFrameIdentity } from './types'

export type CollisionConfirmation = { result: DetectionResponse; expiresAt: number }

/** Ordering belongs to the analyzed source, never the current capture slot. */
export class CameraStatusTracker {
  private states = new Map<string, CameraMonitoringStatus>()
  private retired = new Map<string, Set<string>>()

  accept(cameraId: string, incoming: CameraMonitoringStatus): CameraMonitoringStatus {
    const current = this.states.get(cameraId)
    const active = incoming.latestFrameIdentity
    if (active && (active.cameraId !== cameraId || !active.sessionId || !Number.isSafeInteger(active.sequence))) {
      return current ?? { cameraId, status: 'disconnected', latestResult: null }
    }
    if (active && incoming.latestResult?.sourceFrame &&
        incoming.latestResult.sourceFrame.sessionId !== active.sessionId) {
      incoming = { ...incoming, latestResult: null, collisionConfirmation: null }
    }
    const frame = incoming.latestResult?.sourceFrame ?? incoming.latestFrameIdentity
    const previous = current?.latestResult?.sourceFrame ?? current?.latestFrameIdentity
    const retired = this.retired.get(cameraId) ?? new Set<string>()
    const invalid = incoming.cameraId != null && incoming.cameraId !== cameraId ||
      frame && (frame.cameraId !== cameraId || !frame.sessionId || !Number.isSafeInteger(frame.sequence))
    if (invalid) return current ?? { cameraId, status: 'disconnected', latestResult: null }
    if (frame && previous) {
      if (retired.has(frame.sessionId) ||
          frame.sessionId === previous.sessionId && (frame.sequence < previous.sequence ||
            older(frame, previous) || frame.sequence === previous.sequence &&
              current?.latestResult?.finalDecision === 'confirmed_crash' &&
              incoming.latestResult?.finalDecision !== 'confirmed_crash') ||
          frame.sessionId !== previous.sessionId && !newerSession(frame, previous)) return current!
      if (frame.sessionId !== previous.sessionId) retired.add(previous.sessionId)
    } else if (current?.latestResult && incoming.latestResult &&
      Date.parse(incoming.latestResult.timestamp) < Date.parse(current.latestResult.timestamp)) return current
    this.retired.set(cameraId, retired)
    this.states.set(cameraId, incoming)
    return incoming
  }
}

function older(a: LiveFrameIdentity, b: LiveFrameIdentity) {
  return a.capturedAt != null && b.capturedAt != null && a.capturedAt < b.capturedAt
}
function newerSession(a: LiveFrameIdentity, b: LiveFrameIdentity) {
  return a.capturedAt != null && b.capturedAt != null && a.capturedAt > b.capturedAt
}

/** Bounded UI receipt; does not modify the detector's current decision/boxes. */
export function cameraCollisionResult(status: CameraMonitoringStatus, now = Date.now()): DetectionResponse | null {
  const receipt = status.collisionConfirmation
  const frame = status.latestFrameIdentity ?? status.latestResult?.sourceFrame
  const confirmed = receipt?.result
  if (confirmed?.finalDecision === 'confirmed_crash' && confirmed.accident_detected &&
      receipt!.expiresAt * 1000 > now && frame &&
      confirmed.sourceFrame?.cameraId === frame.cameraId &&
      confirmed.sourceFrame?.sessionId === frame.sessionId &&
      confirmed.sourceFrame.sequence <= frame.sequence &&
      status.latestResult?.finalDecision !== 'possible_crash_aftermath') return confirmed
  const result = status.latestResult
  if (frame && result?.sourceFrame &&
      (frame.sessionId !== result.sourceFrame.sessionId || frame.cameraId !== result.sourceFrame.cameraId)) return null
  return result ?? null
}
