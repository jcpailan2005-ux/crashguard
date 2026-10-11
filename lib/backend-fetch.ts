export const BACKEND_CONNECTION_ERROR = 'Cannot connect to the CrashGuard backend.'
export const LOGIN_REQUEST_TIMEOUT_MS = 10_000

type FetchImplementation = (
  input: RequestInfo | URL,
  init?: RequestInit
) => Promise<Response>

export async function fetchWithBackendTimeout(
  input: RequestInfo | URL,
  init: RequestInit = {},
  timeoutMs = LOGIN_REQUEST_TIMEOUT_MS,
  fetchImplementation: FetchImplementation = globalThis.fetch
): Promise<Response> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  try {
    return await fetchImplementation(input, {
      ...init,
      signal: controller.signal,
    })
  } catch (error) {
    if (controller.signal.aborted || error instanceof TypeError) {
      throw new Error(BACKEND_CONNECTION_ERROR)
    }
    throw error
  } finally {
    clearTimeout(timeoutId)
  }
}
