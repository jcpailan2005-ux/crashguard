import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import test from 'node:test'

import {
  authenticateAndResolveSession,
  formatLoginError,
} from '../lib/login-lifecycle.ts'

function authUser(role: 'admin' | 'dispatcher' | 'responder') {
  return { active: true, mustChangePassword: false, role }
}

for (const [role, destination] of [
  ['admin', '/admin'],
  ['dispatcher', '/dispatcher'],
  ['responder', '/responder'],
] as const) {
  test(`successful ${role} login verifies the cookie session before redirecting`, async () => {
    const calls: string[] = []
    const result = await authenticateAndResolveSession('user@example.test', 'secret', {
      login: async () => { calls.push('login') },
      currentUser: async () => { calls.push('current-user'); return authUser(role) },
    })

    assert.deepEqual(calls, ['login', 'current-user'])
    assert.equal(result.destination, destination)
    assert.equal(result.user.role, role)
  })
}

test('failed login does not verify a session or produce a navigation target', async () => {
  let currentUserCalled = false
  await assert.rejects(
    authenticateAndResolveSession('known@example.test', 'wrong-password', {
      login: async () => { throw Object.assign(new Error('Invalid email or password.'), { status: 401 }) },
      currentUser: async () => { currentUserCalled = true; return authUser('admin') },
    }),
    /Invalid email or password/
  )
  assert.equal(currentUserCalled, false)
})

test('unsupported database role cannot enter an operational route', async () => {
  await assert.rejects(
    authenticateAndResolveSession('user@example.test', 'secret', {
      login: async () => {},
      currentUser: async () => ({ active: true, mustChangePassword: false, role: 'legacy-user' }),
    }),
    /role is not supported/
  )
})

test('login errors are safe and actionable', () => {
  assert.match(
    formatLoginError(Object.assign(new Error('Invalid email or password.'), { status: 401 })),
    /Invalid email or password/
  )
  assert.equal(
    formatLoginError(new Error('Cannot connect to the CrashGuard backend.')),
    'Cannot connect to the CrashGuard server.'
  )
  assert.equal(
    formatLoginError(Object.assign(new Error('PostgreSQL is unavailable.'), { status: 503 })),
    'Authentication service is temporarily unavailable.'
  )
})

test('active authentication code contains no localStorage session-token path', () => {
  const root = process.cwd()
  const files = [
    'app/login/page.tsx',
    'components/auth-provider.tsx',
    'lib/api-client.ts',
    'lib/phase3-api.ts',
  ]
  const source = files.map((file) => readFileSync(join(root, file), 'utf8')).join('\n')
  assert.equal(source.includes('localStorage'), false)
  assert.equal(source.includes('Bearer ${token}'), false)
  assert.equal(existsSync(join(root, 'lib/session-auth.ts')), false)
})

test('login form does not reset credentials while awaiting or handling a result', () => {
  const source = readFileSync(join(process.cwd(), 'app/login/page.tsx'), 'utf8')
  assert.equal(source.includes('form.reset('), false)
  assert.equal(source.includes("setEmail('')"), false)
  assert.equal(source.includes("setPassword('')"), false)
  assert.match(source, /event\.preventDefault\(\)/)
})
