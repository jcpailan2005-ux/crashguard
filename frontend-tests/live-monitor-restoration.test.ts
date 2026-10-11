import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { LiveAlarmTracker } from '../lib/incident-alarm-contract.ts'
import { canManageCamera, isProtectedCamera } from '../lib/camera-management-permissions.ts'

const confirmed = { caseId: 'A', incidentId: 'A', accident_detected: true, finalDecision: 'confirmed_crash',
  incidentCreated: true, caseCreated: true, timestamp: '2026-09-15T00:00:01Z' }
const tracker = () => new LiveAlarmTracker(Date.parse('2026-09-15T00:00:00Z'))

test('candidate and aftermath do not alarm; a confirmed transition alarms once', () => {
  const alarms = tracker()
  assert.equal(alarms.consume({ ...confirmed, finalDecision: 'candidate', caseCreated: false }), false)
  assert.equal(alarms.consume({ ...confirmed, finalDecision: 'possible_crash_aftermath' }), false)
  assert.equal(alarms.consume(confirmed), true)
  assert.equal(alarms.consume(confirmed), false)
})
test('duplicate active case never alarms even with a legacy accident boolean', () => {
  assert.equal(tracker().consume({ ...confirmed, existingCase: true }), false)
  assert.equal(tracker().consume({ ...confirmed, persistenceReason: 'duplicate_active_case' }), false)
})
test('separate confirmed event alarms; old event cannot replay after another event', () => {
  const alarms = tracker()
  assert.equal(alarms.consume(confirmed), true)
  assert.equal(alarms.consume({ ...confirmed, caseId: 'B', incidentId: 'B' }), true)
  assert.equal(alarms.consume(confirmed), false)
})
test('polling an already-confirmed event on page load does not alarm', () => {
  assert.equal(new LiveAlarmTracker(Date.parse('2026-09-15T00:01:00Z')).consume(confirmed), false)
  assert.equal(tracker().consume({ ...confirmed, timestamp: undefined }), false)
})
test('camera policy follows server-granted permissions and excludes responders', () => {
  for (const action of ['create', 'update', 'disable'] as const) {
    assert.equal(canManageCamera({ role: 'admin', permissions: [`cameras.${action}`] }, action), true)
    assert.equal(canManageCamera({ role: 'dispatcher', permissions: [] }, action), false)
    assert.equal(canManageCamera({ role: 'dispatcher', permissions: [`cameras.${action}`] }, action), true)
    assert.equal(canManageCamera({ role: 'responder', permissions: [`cameras.${action}`] }, action), false)
  }
})
test('normal cameras are removable and seeded demo identities remain protected', () => {
  assert.equal(isProtectedCamera({ cameraType: 'RTSP' }), false)
  for (const camera of [{ cameraType: 'Demo' }, { cameraIp: 'demo-1' }, { streamUrl: 'demo://1' }]) {
    assert.equal(isProtectedCamera(camera), true)
  }
})
test('both camera surfaces render permission-controlled Add and Remove actions', () => {
  const admin = readFileSync('components/admin-camera-management-table.tsx', 'utf8')
  const live = readFileSync('components/cctv-monitor-workspace.tsx', 'utf8')
  assert.match(admin, /canCreateCamera && <Button[\s\S]*?Add Camera/)
  assert.match(admin, /canDeleteCamera && !isProtectedCamera\(cam\)/)
  assert.match(live, /\{canCreateCamera \? \(/)
  assert.match(live, /canDeleteCamera && !isProtectedCamera\(camera\)/)
  assert.doesNotMatch(live, /if \(isAdmin\) return false/)
})

test('live monitor exposes simultaneous raw camera previews and keeps detections separate', () => {
  const live = readFileSync('components/cctv-monitor-workspace.tsx', 'utf8')
  assert.match(live, /Show all cameras/)
  assert.match(live, /useState<'single' \| 'grid'>\('grid'\)/)
  assert.match(live, /alt=\{`\$\{safeCameraName\(camera\)\} live preview`\}/)
  assert.doesNotMatch(live, /Detections \{showDetections|<CameraTileDetectionView/)
  assert.match(live, /startCctvMonitoring\(camera\.cameraId\)/)
  assert.match(live, /Promise\.allSettled/)
  assert.match(live, /aria-label=\{`Expand \$\{safeCameraName\(camera\)\}`\}/)
})

test('analysis subscription rejects cross-camera and stale-sequence packets', () => {
  const client = readFileSync('lib/api-client.ts', 'utf8')
  const packetGuard = readFileSync('lib/camera-analysis-view.ts', 'utf8')
  assert.match(client, /acceptLiveBoxPacket\(cameraId, packet, cursor, transportMs, now\)/)
  assert.match(packetGuard, /frame\.cameraId !== cameraId/)
  assert.match(packetGuard, /frame\.sequence <= cursor\.lastFrame\.sequence/)
  assert.match(packetGuard, /cursor\.retiredSessions\.has\(frame\.sessionId\)/)
  assert.match(packetGuard, /packet\.imageDataUrl\.startsWith\('data:image\/jpeg;base64,'\)/)
})
