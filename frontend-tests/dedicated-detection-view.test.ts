import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  acceptLiveBoxPacket,
  cameraAnalysisPacketUrl,
  cameraDetectionGridClass,
  clipAnalysisBoxes,
  createLiveBoxCursor,
  fitMediaRect,
  formatCompactFrameAge,
} from '../lib/camera-analysis-view.ts'
import type { LiveBoxPacket } from '../lib/types.ts'

function packet(cameraId: string, sessionId: string, sequence: number): LiveBoxPacket {
  return {
    sourceFrame: {
      cameraId,
      sessionId,
      sequence,
      capturedAt: 1_800_000_000,
      capturedMonotonic: 100,
      width: 640,
      height: 480,
    },
    inferenceStartedAt: 1_800_000_000,
    inferenceFinishedAt: 1_800_000_000.1,
    boxes: [{ label: 'car', confidence: 0.82, x: 10, y: 20, width: 100, height: 80 }],
    imageDataUrl: 'data:image/jpeg;base64,AA==',
    resultAgeMs: 50,
    sourceAgeMs: 80,
    validForMs: 450,
  }
}

test('matching packets render while wrong camera packets are rejected', () => {
  assert.ok(acceptLiveBoxPacket('CAM-A', packet('CAM-A', 'S1', 1), createLiveBoxCursor(), 10, 1000))
  assert.equal(acceptLiveBoxPacket('CAM-A', packet('CAM-B', 'S1', 1), createLiveBoxCursor(), 10, 1000), null)
})

test('single-camera packet reads carry the matching preview ticket and preserve cookie fallback', () => {
  const url = new URL(cameraAnalysisPacketUrl('http://127.0.0.1:8010', 'CAM-A',
    'http://127.0.0.1:8010/api/cameras/CAM-A/events?token=synthetic-test-ticket&boxes_only=true'))
  assert.equal(url.pathname, '/api/cameras/CAM-A/analysis-packet')
  assert.equal(url.searchParams.get('token'), 'synthetic-test-ticket')
  assert.equal(url.searchParams.has('boxes_only'), false)
  assert.equal(new URL(cameraAnalysisPacketUrl('http://127.0.0.1:8010', 'CAM-A', null)).search, '')
})

test('preview tickets cannot be forwarded from another origin or camera', () => {
  for (const eventsUrl of [
    'https://untrusted.example.invalid/api/cameras/CAM-A/events?token=synthetic-test-ticket',
    'http://127.0.0.1:8010/api/cameras/CAM-B/events?token=synthetic-test-ticket',
    'http://127.0.0.1:8010/unrelated?token=synthetic-test-ticket',
  ]) {
    assert.equal(new URL(cameraAnalysisPacketUrl('http://127.0.0.1:8010', 'CAM-A', eventsUrl)).searchParams.has('token'), false)
  }
})

test('duplicate sequences, retired sessions, and stale packets are rejected', () => {
  const cursor = createLiveBoxCursor()
  assert.ok(acceptLiveBoxPacket('CAM-A', packet('CAM-A', 'S1', 1), cursor, 10, 1000))
  assert.equal(acceptLiveBoxPacket('CAM-A', packet('CAM-A', 'S1', 1), cursor, 10, 1010), null)
  assert.ok(acceptLiveBoxPacket('CAM-A', packet('CAM-A', 'S2', 1), cursor, 10, 1020))
  assert.equal(acceptLiveBoxPacket('CAM-A', packet('CAM-A', 'S1', 2), cursor, 10, 1030), null)

  const stale = packet('CAM-A', 'S3', 1)
  stale.resultAgeMs = 510
  assert.equal(acceptLiveBoxPacket('CAM-A', stale, createLiveBoxCursor(), 0, 1000), null)
})

test('box clipping and contain scaling preserve exact-frame coordinates', () => {
  const boxes = clipAnalysisBoxes([
    { label: 'car', confidence: 0.8, x: -10, y: 20, width: 30, height: 40 },
    { label: 'truck', confidence: 0.7, x: 700, y: 20, width: 30, height: 40 },
  ], 640, 480)
  assert.deepEqual(boxes, [{ label: 'car', confidence: 0.8, x: 0, y: 20, width: 20, height: 40 }])
  const rect = fitMediaRect(640, 480, 1000, 500, 'contain')
  assert.ok(rect)
  assert.equal(Math.round(rect.width), 667)
  assert.equal(Math.round(rect.height), 500)
  assert.equal(Math.round(rect.left), 167)
})

test('a delayed exact-frame packet renders as stale within its explicit delivery window', () => {
  const delayed = packet('CAM-A', 'S1', 1)
  delayed.resultAgeMs = 1200
  delayed.validForMs = 0
  delayed.retentionForMs = 3800
  const view = acceptLiveBoxPacket('CAM-A', delayed, createLiveBoxCursor(), 600, 1000)
  assert.ok(view)
  assert.equal(view.packet.imageDataUrl, delayed.imageDataUrl)
  assert.deepEqual(view.packet.boxes, delayed.boxes)
  assert.equal(view.expiresAt, 1000)
  assert.equal(view.retentionExpiresAt, 4200)
})

test('expired delivery, invalid timing, wrong camera and retired sessions remain rejected', () => {
  const delayed = { ...packet('CAM-A', 'S1', 1), resultAgeMs: 4900, validForMs: 0, retentionForMs: 100 }
  assert.equal(acceptLiveBoxPacket('CAM-A', delayed, createLiveBoxCursor(), 101, 1000), null)
  assert.equal(acceptLiveBoxPacket('CAM-B', delayed, createLiveBoxCursor(), 0, 1000), null)
  assert.equal(acceptLiveBoxPacket('CAM-A', { ...delayed, resultAgeMs: NaN }, createLiveBoxCursor(), 0, 1000), null)
  assert.equal(acceptLiveBoxPacket('CAM-A', delayed, createLiveBoxCursor(), -1, 1000), null)
  const cursor = createLiveBoxCursor()
  assert.ok(acceptLiveBoxPacket('CAM-A', packet('CAM-A', 'S1', 1), cursor, 0, 1000))
  assert.ok(acceptLiveBoxPacket('CAM-A', packet('CAM-A', 'S2', 1), cursor, 0, 1100))
  assert.equal(acceptLiveBoxPacket('CAM-A', delayed, cursor, 0, 1200), null)
})

test('responsive grid supports one, two, four, and five camera layouts', () => {
  assert.match(cameraDetectionGridClass(1), /max-w-5xl/)
  assert.match(cameraDetectionGridClass(2), /md:grid-cols-2/)
  assert.match(cameraDetectionGridClass(4), /md:grid-cols-2/)
  assert.match(cameraDetectionGridClass(5), /2xl:grid-cols-3/)
  assert.equal(formatCompactFrameAge(420), '0.4s')
  assert.equal(formatCompactFrameAge(2400), '2.4s')
})

test('dedicated route exposes compact filters, readable boxes, expand, and close controls', () => {
  const route = readFileSync('app/dispatcher/detections/page.tsx', 'utf8')
  const grid = readFileSync('components/camera-detection-grid.tsx', 'utf8')
  assert.match(route, /className="sr-only">Detections/)
  assert.match(route, /<CameraDetectionGrid/)
  assert.doesNotMatch(route, /Back to Live Monitor|PageHeading/)
  assert.match(grid, /value === 'all' \? 'All'/)
  assert.match(grid, /value === 'cctv' \? 'CCTV' : 'USB'/)
  assert.match(grid, /formatCompactFrameAge\(ageMs\)/)
  assert.match(grid, /Synchronized vehicle boxes, labels, and confidence/)
  assert.match(grid, /Math\.round\(confidence \* 100\)/)
  assert.match(grid, /preserveAspectRatio="xMidYMid meet"/)
  assert.match(grid, />\s*<Maximize2[\s\S]*?\/>Expand\s*</)
  assert.match(grid, /Back to all cameras/)
  assert.match(grid, /Capture time:/)
  assert.match(grid, /Frame sequence:/)
})

test('offline cameras remain independent and detections cannot be hidden', () => {
  const grid = readFileSync('components/camera-detection-grid.tsx', 'utf8')
  assert.match(grid, /Promise\.allSettled/)
  assert.match(grid, /return 'OFFLINE'/)
  assert.match(grid, /visibleCameras\.map/)
  assert.match(grid, /const view = useCameraAnalysis\(camera\.cameraId\)/)
  assert.match(grid, /loadedFrameKey === packetKey/)
  assert.doesNotMatch(grid, /setShowDetections|Boxes hidden|Detections OFF/)
  assert.doesNotMatch(grid, /useCameraAnalysis\(camera\.cameraId,\s*showDetections\)/)
})

test('detection page is read-only and the dispatcher sidebar owns navigation', () => {
  const route = readFileSync('app/dispatcher/detections/page.tsx', 'utf8')
  const grid = readFileSync('components/camera-detection-grid.tsx', 'utf8')
  const live = readFileSync('app/dispatcher/live/page.tsx', 'utf8')
  const layout = readFileSync('components/role-layout.tsx', 'utf8')
  const combined = `${route}\n${grid}`
  assert.match(layout, /\['Live Monitor', '\/dispatcher\/live'\], \['Detections', '\/dispatcher\/detections'\], \['New Alerts'/)
  assert.match(layout, /compactCameraPage/)
  assert.doesNotMatch(live, /View all detections|\/dispatcher\/detections|PageHeading/)
  assert.doesNotMatch(combined, /startCctvMonitoring|testDetectionOnCurrentFrame|detectFromCamera|\/monitor\/start/)
  assert.doesNotMatch(combined, /method:\s*['"]POST['"]/)
})

test('analysis fallback remains active until a real boxes event arrives', () => {
  const client = readFileSync('lib/api-client.ts', 'utf8')
  assert.match(client, /events\.onopen = \(\) => \{ void fetchLatest\(\) \}/)
  assert.match(client, /events\.addEventListener\('boxes', \(\) => \{ fallback = false; void fetchLatest\(\) \}\)/)
  assert.doesNotMatch(client, /events\.onopen = \(\) => \{ fallback = false/)
})

test('Live Monitor shows synchronized detections in control-room views', () => {
  const page = readFileSync('app/dispatcher/live/page.tsx', 'utf8')
  const workspace = readFileSync('components/cctv-monitor-workspace.tsx', 'utf8')
  const liveCamera = readFileSync('components/live-camera.tsx', 'utf8')
  assert.match(page, /className="sr-only">Live Monitor/)
  assert.match(workspace, /useState<'single' \| 'grid'>\('grid'\)/)
  assert.match(workspace, /<CameraDetectionSurface cameraId=\{camera.cameraId\}/)
  assert.match(workspace, /alt=\{`\$\{safeCameraName\(camera\)\} live preview`\}/)
  assert.match(liveCamera, /isCctvLive && analysisPacket/)
  assert.match(liveCamera, /loadedAnalysisKey === analysisKey/)
})
