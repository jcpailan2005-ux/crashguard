'use client'

import { getLocalCrashCases } from '@/lib/api-client'
import { localCaseToCrashCase } from '@/lib/crash-case-mapper'
import type { CrashCase } from '@/lib/types'

/** Poll the authenticated SQLite-backed API; no browser database credentials. */
export function subscribeCrashCases(
  onCases: (cases: CrashCase[]) => void,
  onError: (error: Error) => void,
  areaId?: string | null
): () => void {
  let stopped = false
  let inFlight = false
  const poll = async () => {
    if (stopped || inFlight) return
    inFlight = true
    try {
      const cases = await getLocalCrashCases({ limit: 200 })
      if (!stopped) onCases(cases.map(localCaseToCrashCase).filter(item =>
        !areaId || item.location.areaId === areaId))
    } catch (error) {
      if (!stopped) onError(error instanceof Error ? error : new Error('Could not load crash cases.'))
    } finally { inFlight = false }
  }
  void poll()
  const timer = window.setInterval(() => void poll(), 4000)
  return () => { stopped = true; window.clearInterval(timer) }
}

export function summarizeCaseCounts(cases: CrashCase[]) {
  const today = new Date().toDateString()
  return {
    pendingReview: cases.filter(
      (c) => c.status === 'pending_review'
    ).length,
    underReview: cases.filter((c) => c.status === 'under_review').length,
    confirmedCrashes: cases.filter((c) => c.status === 'confirmed_crash').length,
    dispatchedCases: cases.filter((c) => c.status === 'dispatched').length,
    falseAlarms: cases.filter((c) => c.status === 'false_alarm').length,
    resolvedToday: cases.filter(
      (c) => c.status === 'resolved' && new Date(c.updatedAt).toDateString() === today
    ).length,
  }
}
