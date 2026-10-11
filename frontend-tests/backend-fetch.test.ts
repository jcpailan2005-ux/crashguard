import assert from 'node:assert/strict'
import test from 'node:test'

import {
  BACKEND_CONNECTION_ERROR,
  fetchWithBackendTimeout,
} from '../lib/backend-fetch.ts'

test('a hanging login request times out with a clear backend error', async () => {
  const hangingFetch = (_input: RequestInfo | URL, init?: RequestInit) =>
    new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => {
        reject(new DOMException('Request aborted', 'AbortError'))
      })
    })

  await assert.rejects(
    fetchWithBackendTimeout('http://127.0.0.1:8010/api/v3/auth/login', {}, 5, hangingFetch),
    new Error(BACKEND_CONNECTION_ERROR)
  )
})

test('an unavailable backend produces the same connection error', async () => {
  const unavailableFetch = () => Promise.reject(new TypeError('Failed to fetch'))

  await assert.rejects(
    fetchWithBackendTimeout('http://127.0.0.1:8010/api/v3/auth/login', {}, 100, unavailableFetch),
    new Error(BACKEND_CONNECTION_ERROR)
  )
})

test('HTTP authentication failures remain available to normal error handling', async () => {
  const authenticationFailure = () =>
    Promise.resolve(new Response('{"detail":"Invalid email or password."}', { status: 401 }))

  const response = await fetchWithBackendTimeout(
    'http://127.0.0.1:8010/api/v3/auth/login',
    {},
    100,
    authenticationFailure
  )

  assert.equal(response.status, 401)
  assert.deepEqual(await response.json(), { detail: 'Invalid email or password.' })
})
