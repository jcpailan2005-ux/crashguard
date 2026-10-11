import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

test('login owns an explicit light visual scope and password visibility control', () => {
  const page = readFileSync('app/login/page.tsx', 'utf8')
  const styles = readFileSync('app/globals.css', 'utf8')
  assert.match(page, /login-light/)
  assert.match(page, /Show password/)
  assert.match(styles, /\.login-light\s*\{/)
  assert.match(styles, /color-scheme:\s*light/)
})

test('alarm preference is persisted and gates both operational alarm surfaces', () => {
  const settings = readFileSync('components/personal-settings-page.tsx', 'utf8')
  const liveCamera = readFileSync('components/live-camera.tsx', 'utf8')
  const upload = readFileSync('app/dashboard/upload/page.tsx', 'utf8')
  assert.match(settings, /alarmAudio/)
  assert.match(liveCamera, /if \(alarmAudioEnabled && profile\?\.role !== 'dispatcher'\)/)
  assert.match(upload, /alarmAudioEnabled\s*&&\s*shouldEmitOperationalAlarm/)
})

test('dispatcher alarm polling and arming live in the persistent dispatcher shell', () => {
  const layout = readFileSync('components/role-layout.tsx', 'utf8')
  const monitor = readFileSync('components/dispatcher-alarm-monitor.tsx', 'utf8')
  const alerts = readFileSync('components/dispatcher-alerts-view.tsx', 'utf8')
  assert.match(layout, /role === 'dispatcher' \? <DispatcherAlarmMonitor/)
  assert.match(monitor, /phase3\.notifications\(\)/)
  assert.match(monitor, /phase3\.incidents\(\)/)
  assert.match(monitor, /window\.setInterval\(\(\) => void poll\(\), 5_000\)/)
  assert.match(monitor, /armAccidentAlertAudio\(\)/)
  assert.doesNotMatch(alerts, /playAccidentAlert|DispatcherIncidentAlarmTracker/)
})

test('responder workspace uses a guarded 25 second authenticated heartbeat', () => {
  const layout = readFileSync('components/role-layout.tsx', 'utf8')
  assert.match(layout, /requestInFlight/)
  assert.match(layout, /phase3\.heartbeat\(\)/)
  assert.match(layout, /25_000/)
})
