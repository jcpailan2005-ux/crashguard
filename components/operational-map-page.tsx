'use client'
import dynamic from 'next/dynamic'
import { useEffect, useMemo, useState } from 'react'
import { phase3, type OperationalIncident } from '@/lib/phase3-api'
import type { CrashCase } from '@/lib/types'
import type { CaseStatus } from '@/lib/incident-status'
import { PageHeading } from '@/components/page-heading'
import { Card } from '@/components/ui/card'

const LiveMap = dynamic(() => import('@/components/live-map'), { ssr: false })
function statusOf(incident: OperationalIncident): CaseStatus {
  if (incident.state === 'FALSE_ALARM') return 'false_alarm'
  if (incident.state === 'RESOLVED') return 'resolved'
  if (incident.assignmentStatus === 'ARRIVED') return 'arrived'
  if (incident.assignmentStatus === 'RESPONDING') return 'responding'
  if (incident.assignmentId) return 'dispatched'
  if (incident.state === 'CONFIRMED') return 'confirmed_crash'
  return incident.reviewStatus === 'UNDER_REVIEW' ? 'under_review' : 'pending_review'
}
function toCase(incident: OperationalIncident): CrashCase {
  const timestamp = incident.detectedAt
  return {
    caseId: incident.id, detectionId: incident.id, detectionMode: incident.detectionMode,
    status: statusOf(incident), reviewerId: incident.reviewedBy, user: null, vehicle: null,
    location: { label: incident.location ?? 'Unknown location', latitude: incident.latitude ?? 7.1907, longitude: incident.longitude ?? 125.4553, isFallback: incident.latitude == null || incident.longitude == null },
    media: { mediaType: 'cctv', source: 'stream' }, confidence: incident.aiScore,
    notes: '', actions: [], acknowledgedAt: null, confirmedAt: null, createdAt: timestamp,
    detectedAt: timestamp, dispatchedAt: null, falseAlarmAt: null, resolvedAt: null,
    triggerStatus: 'camera_detection', updatedAt: timestamp, accidentDetected: incident.state !== 'FALSE_ALARM',
    detections: [],
  }
}
export function OperationalMapPage() {
  const [incidents, setIncidents] = useState<OperationalIncident[]>([])
  const [selected, setSelected] = useState<CrashCase | null>(null)
  const [error, setError] = useState('')
  useEffect(() => { void phase3.incidents().then((result) => setIncidents(result.incidents)).catch((caught) => setError(caught.message)) }, [])
  const cases = useMemo(() => incidents.map(toCase), [incidents])
  return <><PageHeading title="Incident map" description="Role-scoped incident locations from SQLite. Fallback coordinates are labelled in markers." />{error && <p className="mb-4 text-sm text-destructive">{error}</p>}<Card className="overflow-hidden"><div className="h-[55vh]"><LiveMap cases={cases} selectedCase={selected} /></div></Card><div className="mt-4 grid gap-2 md:grid-cols-2">{cases.map((item) => <button className="rounded-md border p-3 text-left hover:bg-muted" key={item.caseId} onClick={() => setSelected(item)}><span className="font-medium">{item.location.label}</span><span className="block text-xs text-muted-foreground">{item.status.replaceAll('_', ' ')}</span></button>)}</div></>
}
