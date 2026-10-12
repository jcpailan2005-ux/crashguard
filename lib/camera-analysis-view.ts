import type { DetectionBox, LiveBoxPacket, LiveBoxView, LiveFrameIdentity } from '@/lib/types'

export const FRESHNESS_LIMIT_MS = 500
export const VISUAL_RETENTION_LIMIT_MS = 5000

/** Carry the existing scoped preview ticket only to its matching backend camera. */
export function cameraAnalysisPacketUrl(backendUrl: string, cameraId: string, eventsUrl: string | null): string {
  const base = backendUrl.replace(/\/+$/, '')
  const path = `/api/cameras/${encodeURIComponent(cameraId)}`
  const packet = new URL(`${base}${path}/analysis-packet`)
  if (eventsUrl) {
    const events = new URL(eventsUrl, `${base}/`)
    const ticket = events.searchParams.get('token')
    if (ticket && events.origin === packet.origin && events.pathname === `${path}/events`) {
      packet.searchParams.set('token', ticket)
    }
  }
  return packet.toString()
}

export interface LiveBoxCursor {
  lastFrame: LiveFrameIdentity | null
  retiredSessions: Set<string>
}

export function createLiveBoxCursor(): LiveBoxCursor {
  return { lastFrame: null, retiredSessions: new Set<string>() }
}

export function acceptLiveBoxPacket(
  cameraId: string,
  packet: LiveBoxPacket,
  cursor: LiveBoxCursor,
  transportMs: number,
  now: number,
): LiveBoxView | null {
  const frame = packet.sourceFrame
  const remaining = Math.min(FRESHNESS_LIMIT_MS, packet.validForMs, FRESHNESS_LIMIT_MS - packet.resultAgeMs) - transportMs
  const retainedDelivery = packet.retentionForMs != null
    ? Math.min(packet.retentionForMs, VISUAL_RETENTION_LIMIT_MS - packet.resultAgeMs) - transportMs
    : remaining
  if (
    !frame ||
    !frame.sessionId ||
    !Number.isSafeInteger(frame.sequence) ||
    frame.cameraId !== cameraId ||
    !frame.width || !Number.isFinite(frame.width) || frame.width <= 0 ||
    !frame.height || !Number.isFinite(frame.height) || frame.height <= 0 ||
    !Number.isFinite(packet.resultAgeMs) || packet.resultAgeMs < 0 ||
    !Number.isFinite(packet.validForMs) || packet.validForMs < 0 ||
    !Number.isFinite(transportMs) || transportMs < 0 ||
    !Number.isFinite(remaining) || !Number.isFinite(retainedDelivery) || retainedDelivery <= 0 ||
    !packet.imageDataUrl.startsWith('data:image/jpeg;base64,') ||
    !Array.isArray(packet.boxes)
  ) return null

  if (cursor.retiredSessions.has(frame.sessionId)) return null
  if (
    cursor.lastFrame &&
    (frame.cameraId !== cursor.lastFrame.cameraId ||
      (frame.sessionId === cursor.lastFrame.sessionId && frame.sequence <= cursor.lastFrame.sequence))
  ) return null

  if (cursor.lastFrame && frame.sessionId !== cursor.lastFrame.sessionId) {
    cursor.retiredSessions.add(cursor.lastFrame.sessionId)
    if (cursor.retiredSessions.size > 8) {
      cursor.retiredSessions.delete(cursor.retiredSessions.values().next().value!)
    }
  }
  cursor.lastFrame = frame

  const remainingRetention = packet.retentionForMs != null
    ? retainedDelivery
    : VISUAL_RETENTION_LIMIT_MS - packet.resultAgeMs - transportMs
  return {
    packet: {
      ...packet,
      sourceAgeMs: packet.sourceAgeMs == null ? null : packet.sourceAgeMs + transportMs,
    },
    expiresAt: now + Math.max(0, remaining),
    receivedAt: now,
    retentionExpiresAt: now + Math.max(0, remainingRetention),
  }
}

export function clipAnalysisBoxes(boxes: DetectionBox[], width: number, height: number) {
  return boxes.flatMap((box) => {
    if (
      ![box.x, box.y, box.width, box.height, width, height].every(Number.isFinite) ||
      box.width <= 0 || box.height <= 0 || width <= 0 || height <= 0
    ) return []
    const x = Math.max(0, box.x)
    const y = Math.max(0, box.y)
    const right = Math.min(width, box.x + box.width)
    const bottom = Math.min(height, box.y + box.height)
    return right > x && bottom > y
      ? [{ ...box, x, y, width: right - x, height: bottom - y }]
      : []
  })
}

export function fitMediaRect(
  sourceWidth: number,
  sourceHeight: number,
  width: number,
  height: number,
  fit: 'contain' | 'cover',
) {
  if (![sourceWidth, sourceHeight, width, height].every((value) => Number.isFinite(value) && value > 0)) return null
  const scale = (fit === 'cover' ? Math.max : Math.min)(width / sourceWidth, height / sourceHeight)
  return {
    left: (width - sourceWidth * scale) / 2,
    top: (height - sourceHeight * scale) / 2,
    width: sourceWidth * scale,
    height: sourceHeight * scale,
  }
}

export function formatFrameAge(ageMs: number | null | undefined): string {
  if (ageMs == null || !Number.isFinite(ageMs) || ageMs < 0) return 'age unavailable'
  return ageMs < 1000 ? `${Math.round(ageMs)} ms old` : `${(ageMs / 1000).toFixed(1)} s old`
}

export function formatCompactFrameAge(ageMs: number | null | undefined): string {
  if (ageMs == null || !Number.isFinite(ageMs) || ageMs < 0) return 'age unavailable'
  return `${(ageMs / 1000).toFixed(1)}s`
}

export function cameraDetectionGridClass(cameraCount: number) {
  if (cameraCount === 1) return 'mx-auto grid max-w-5xl grid-cols-1 gap-5'
  if (cameraCount > 4) return 'grid grid-cols-1 gap-5 md:grid-cols-2 2xl:grid-cols-3'
  return 'grid grid-cols-1 gap-5 md:grid-cols-2'
}
