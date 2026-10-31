import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { CameraStatusTracker, cameraCollisionResult } from '../lib/camera-collision-state.ts'
import { incidentEvidence } from '../lib/incident-evidence.ts'
import { fitMediaRect, pixelCoordinatePercent } from '../lib/camera-analysis-view.ts'
import type { CameraMonitoringStatus } from '../lib/api-client.ts'

const at = 1_800_000_000
function status(cameraId = 'A', sequence = 10, sessionId = 'S1', decision = 'candidate', capturedAt = at + sequence): CameraMonitoringStatus {
  return { cameraId, status: 'monitoring-live', latestResult: {
    success: true, accident_detected: decision === 'confirmed_crash', finalDecision: decision,
    timestamp: new Date(capturedAt * 1000).toISOString(), confidence: .99,
    media_type: 'image', location: 'Test', detections: [],
    sourceFrame: { cameraId, sessionId, sequence, capturedAt, capturedMonotonic: sequence, width: 1920, height: 1080 },
  } }
}
const confirmed = () => status('A', 11, 'S1', 'confirmed_crash')

test('stale analyzing cannot overwrite confirmed; wrong camera and retired session are rejected', () => {
  const tracker = new CameraStatusTracker()
  const confirmation = tracker.accept('A', confirmed())
  for (const stale of [status(), status('B', 12), status('A', 11), status('A', 12, 'S1', 'candidate', at)]) {
    assert.equal(tracker.accept('A', stale), confirmation)
  }
  const restart = tracker.accept('A', status('A', 1, 'S2', 'ignored', at + 30))
  assert.equal(tracker.accept('A', status('A', 40)), restart)
  assert.equal(tracker.accept('A', status('A', 1, 'UNSEEN-OLD', 'candidate', at)), restart)
})

test('a missed one-frame confirmation reaches only its camera/session and expires without changing raw inference', () => {
  const incoming = status('A', 12)
  incoming.collisionConfirmation = { result: confirmed().latestResult!, expiresAt: at + 21 }
  assert.equal(cameraCollisionResult(incoming, (at + 15) * 1000)?.finalDecision, 'confirmed_crash')
  assert.equal(incoming.latestResult?.finalDecision, 'candidate')
  assert.equal(cameraCollisionResult(incoming, (at + 22) * 1000)?.finalDecision, 'candidate')
  for (const other of [status('B', 12), status('A', 12, 'S2'), status('A', 12, 'S1', 'possible_crash_aftermath')]) {
    other.collisionConfirmation = incoming.collisionConfirmation
    assert.equal(cameraCollisionResult(other, (at + 15) * 1000), other.latestResult)
  }
})

test('reconnect before the next inference cannot carry confirmation into the replacement camera session', () => {
  const tracker = new CameraStatusTracker()
  tracker.accept('A', confirmed())
  const replacement = { ...confirmed(), latestFrameIdentity: status('A', 1, 'S2', 'ignored', at + 30).latestResult!.sourceFrame }
  const accepted = tracker.accept('A', replacement)
  assert.equal(accepted.latestResult, null)
  assert.equal(cameraCollisionResult(accepted, (at + 30) * 1000), null)
})

test('exact evidence keeps source dimensions and observed class/confidence/track; stale boxes are excluded', () => {
  const frame = confirmed().latestResult!.sourceFrame!
  const exact = { label: 'car', classId: 2, confidence: .96, trackId: 7,
    cameraId: 'A', sessionId: 'S1', sequence: 11, x: 192, y: 108, width: 384, height: 216 }
  const input = { media: { keyFramePath: '/raw.jpg', annotatedPath: '/annotated.jpg' },
    evidenceSummary: { sourceFrame: frame, boxes: [exact, { ...exact, sequence: 10 },
      { ...exact, sessionId: 'old' }, { ...exact, cameraId: 'B' }, { ...exact, observationKind: 'PREDICTED' }] } }
  const evidence = incidentEvidence(input)
  assert.deepEqual(evidence.boxes, [exact])
  assert.equal(evidence.width, 1920)
  assert.equal(evidence.height, 1080)
  for (const [width, height] of [[400, 400], [800, 450], [800, 800]]) {
    const rect: { left: number; top: number; width: number; height: number } = fitMediaRect(evidence.width, evidence.height, width, height, 'contain')!
    assert.equal(pixelCoordinatePercent(exact.x, evidence.width), 10)
    assert.equal(rect.left + exact.x / evidence.width * rect.width, rect.left + rect.width * .1)
    assert.equal(rect.top + exact.y / evidence.height * rect.height, rect.top + rect.height * .1)
    assert.equal(exact.width / evidence.width * rect.width, rect.width * .2)
  }
  const component = readFileSync('components/operational-incident-evidence.tsx', 'utf8')
  assert.match(component, /src === raw && src !== annotated && loaded === src/)
  assert.match(component, /naturalWidth === evidence.width/)
  assert.match(component, /preserveAspectRatio="xMidYMid meet"/)
  assert.doesNotMatch(component, /detectFrom|fetchCamera|inference/)
  assert.match(readFileSync('app/dispatcher/review/page.tsx', 'utf8'), /<OperationalIncidentEvidence incident=\{incident\}/)
})
