import assert from 'node:assert/strict'
import test from 'node:test'
import { homeForRole, legacyDashboardRedirect, routeBelongsToRole } from '../lib/role-routing.ts'

test('each operational role has a distinct landing route', () => {
  assert.equal(homeForRole('admin'), '/admin')
  assert.equal(homeForRole('DISPATCHER'), '/dispatcher')
  assert.equal(homeForRole('responder'), '/responder')
})

test('unknown and legacy roles cannot enter an operational workspace', () => {
  assert.equal(homeForRole('user'), '/login')
  assert.equal(homeForRole(undefined), '/login')
})

test('role route ownership does not accept another role tree', () => {
  assert.equal(routeBelongsToRole('/dispatcher/review', 'dispatcher'), true)
  assert.equal(routeBelongsToRole('/admin/users', 'dispatcher'), false)
  assert.equal(routeBelongsToRole('/responder/history', 'responder'), true)
})

test('legacy settings redirect to the authenticated role settings without loops', () => {
  assert.equal(legacyDashboardRedirect('/dashboard/settings', 'admin'), '/admin/settings')
  assert.equal(legacyDashboardRedirect('/dashboard/settings', 'dispatcher'), '/dispatcher/settings')
  assert.equal(legacyDashboardRedirect('/dashboard/settings', 'responder'), '/responder/settings')
  assert.equal(legacyDashboardRedirect('/admin/settings', 'admin'), null)
})

test('legacy dispatcher monitor redirects to the role-owned live monitor', () => {
  assert.equal(legacyDashboardRedirect('/dashboard/ip-camera', 'dispatcher'), '/dispatcher/live')
  assert.equal(legacyDashboardRedirect('/dashboard/ip-camera', 'admin'), '/admin/cameras')
  assert.equal(legacyDashboardRedirect('/dashboard/ip-camera', 'responder'), '/responder')
})
