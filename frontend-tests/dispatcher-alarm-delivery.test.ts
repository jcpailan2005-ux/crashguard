import assert from 'node:assert/strict'
import test from 'node:test'
import { DispatcherIncidentAlarmTracker } from '../lib/incident-alarm-contract.ts'
import { enqueueFreshDispatcherAlarms } from '../lib/dispatcher-alarm-delivery.ts'

const started = Date.parse('2026-09-29T00:00:00Z')
const incident = (id: string, mode = 'temporal_collision', createdAt = '2026-09-29T00:00:01Z') =>
  ({ id, detectionMode: mode, createdAt })
const notification = (id: string, type = 'NEW_CRASH_REVIEW') =>
  ({ id: `N-${id}`, incidentId: id, type, createdAt: '2026-09-29T00:00:01Z' })

test('a confirmed incident automatically attempts once, repeats stay silent, a second incident attempts once', async () => {
  const tracker = new DispatcherIncidentAlarmTracker(started)
  const played: string[] = []
  const attempt = async (id: string) => { played.push(id) }
  let pending = Promise.resolve()
  let result = enqueueFreshDispatcherAlarms(tracker, [notification('A')], [incident('A')], true, pending, attempt)
  pending = result.pending
  await pending
  assert.deepEqual(result.attempted, ['A'])
  assert.deepEqual(played, ['A'])
  result = enqueueFreshDispatcherAlarms(tracker, [notification('A')], [incident('A')], true, pending, attempt)
  pending = result.pending
  await pending
  assert.deepEqual(result.attempted, [])
  result = enqueueFreshDispatcherAlarms(tracker, [notification('A'), notification('B')],
    [incident('A'), incident('B')], true, pending, attempt)
  await result.pending
  assert.deepEqual(played, ['A', 'B'])
})

test('unarmed, old, aftermath, decline, and analyzing fixtures make no play attempt', async () => {
  const tracker = new DispatcherIncidentAlarmTracker(started)
  const played: string[] = []
  const attempt = async (id: string) => { played.push(id) }
  const result = enqueueFreshDispatcherAlarms(tracker,
    [notification('UNARMED'), notification('OLD'), notification('AFTERMATH'), notification('DECLINE', 'ASSIGNMENT_DECLINED')],
    [incident('UNARMED'), incident('OLD', 'temporal_collision', '2026-09-28T23:59:59Z'),
      incident('AFTERMATH', 'aftermath_review'), incident('DECLINE')], false, Promise.resolve(), attempt)
  await result.pending
  assert.deepEqual(result.attempted, [])
  const analyzing = enqueueFreshDispatcherAlarms(tracker, [], [], true, result.pending, attempt)
  await analyzing.pending
  assert.deepEqual(played, [])
})
