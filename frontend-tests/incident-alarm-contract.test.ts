import assert from 'node:assert/strict'
import test from 'node:test'

import {
  DispatcherIncidentAlarmTracker,
  getOperationalIncidentId,
  shouldEmitOperationalAlarm,
} from '../lib/incident-alarm-contract.ts'

const confirmed = { incident_created: true, incident_id: 'CASE-100',
  accident_detected: true, finalDecision: 'confirmed_crash' }

test('AI positive without committed incident emits no operational alarm', () => {
  assert.equal(
    shouldEmitOperationalAlarm(
      { incident_created: false, incident_id: null },
      null
    ),
    false
  )
})

test('accumulating aftermath candidate emits no alarm before persistence', () => {
  assert.equal(
    shouldEmitOperationalAlarm(
      {
        incident_created: false,
        incident_id: null,
      },
      null
    ),
    false
  )
})

test('newly committed incident emits one operational alarm', () => {
  const result = confirmed
  assert.equal(getOperationalIncidentId(result), 'CASE-100')
  assert.equal(shouldEmitOperationalAlarm(result, null), true)
})

test('repeated observation of the same incident emits no repeated alarm', () => {
  const result = {
    incident_created: false,
    duplicate_event: true,
    incident_id: 'CASE-100',
  }
  assert.equal(shouldEmitOperationalAlarm(result, 'CASE-100'), false)
})

test('a distinct committed incident emits a new alarm', () => {
  const result = { ...confirmed, incident_id: 'CASE-101' }
  assert.equal(shouldEmitOperationalAlarm(result, 'CASE-100'), true)
})

test('case creation, analyzing, and aftermath cannot emit an operational alarm', () => {
  assert.equal(shouldEmitOperationalAlarm({ ...confirmed, incident_created: false, caseCreated: true }, null), false)
  assert.equal(shouldEmitOperationalAlarm({ ...confirmed, finalDecision: 'candidate' }, null), false)
  assert.equal(shouldEmitOperationalAlarm({ ...confirmed, finalDecision: 'possible_crash_aftermath' }, null), false)
})

test('dispatcher sounds only once for a fresh confirmed incident identity', () => {
  const tracker = new DispatcherIncidentAlarmTracker(Date.parse('2026-09-29T00:00:00Z'))
  const old = { id: 'OLD', detectionMode: 'temporal_collision', createdAt: '2026-09-28T23:59:00Z' }
  const fresh = { id: 'FRESH', detectionMode: 'temporal_collision', createdAt: '2026-09-29T00:00:01Z' }
  const aftermath = { id: 'AFTERMATH', detectionMode: 'aftermath_review', createdAt: '2026-09-29T00:00:01Z' }
  const notifications = [old, fresh, aftermath].map((incident) => ({
    id: `N-${incident.id}`, incidentId: incident.id, type: 'NEW_CRASH_REVIEW', createdAt: incident.createdAt,
  }))
  assert.deepEqual(tracker.consume(notifications, [old, fresh, aftermath]), ['FRESH'])
  assert.deepEqual(tracker.consume(notifications, [old, fresh, aftermath]), [])
  assert.deepEqual(tracker.consume([{ id: 'DECLINE', incidentId: 'FRESH', type: 'ASSIGNMENT_DECLINED',
    createdAt: '2026-09-29T00:00:02Z' }], [fresh]), [])
})
