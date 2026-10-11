import assert from 'node:assert/strict'
import test from 'node:test'

import type { ResponderPresence } from '../lib/phase3-api.ts'
import { formatLastSeen, responderAssignmentLabel, sortRespondersByAvailability } from '../lib/responder-presence.ts'

function responder(overrides: Partial<ResponderPresence>): ResponderPresence {
  return {
    uid: overrides.uid ?? 'id', id: overrides.uid ?? 'id', email: 'r@example.test',
    displayName: overrides.displayName ?? 'Responder', areaId: null,
    availabilityStatus: overrides.availabilityStatus ?? 'AVAILABLE',
    presenceStatus: overrides.presenceStatus ?? 'OFFLINE', lastSeenAt: null,
    lastLoginAt: null, activeAssignmentId: null, activeAssignmentStatus: null,
    activeIncidentId: null, ...overrides,
  }
}

test('online available responders sort before busy and offline responders', () => {
  const rows = sortRespondersByAvailability([
    responder({ uid: 'offline', displayName: 'Offline', presenceStatus: 'OFFLINE' }),
    responder({ uid: 'busy', displayName: 'Busy', presenceStatus: 'ONLINE', activeAssignmentId: 'a1' }),
    responder({ uid: 'available', displayName: 'Available', presenceStatus: 'ONLINE' }),
  ])
  assert.deepEqual(rows.map((row) => row.uid), ['available', 'busy', 'offline'])
})

test('presence labels describe last seen and active assignment without relying on color', () => {
  assert.equal(formatLastSeen('2026-08-21T00:00:00Z', Date.parse('2026-08-21T00:00:25Z')), '25 sec ago')
  assert.equal(responderAssignmentLabel(responder({ activeAssignmentId: 'a1', activeIncidentId: '1234567890', activeAssignmentStatus: 'EN_ROUTE' })), 'Incident 12345678 · EN_ROUTE')
})
