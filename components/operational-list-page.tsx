'use client'
import { useEffect, useState } from 'react'
import { phase3 } from '@/lib/phase3-api'
import { PageHeading } from '@/components/page-heading'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

type Source = 'incidents' | 'notifications' | 'audit' | 'analytics' | 'settings' | 'assignments'
const COPY: Record<Source, [string, string]> = {
  incidents: ['Incidents', 'Authoritative PostgreSQL incident records and current workflow state.'],
  notifications: ['Notifications', 'Alerts addressed to your authenticated account.'],
  audit: ['Audit logs', 'Immutable records of privileged and operational actions.'],
  analytics: ['Operational analytics', 'Live counts computed from authoritative records.'],
  settings: ['AI settings', 'Audited detector settings safe for operational adjustment.'],
  assignments: ['Response history', 'Completed, declined, and cancelled assignments for this responder.'],
}
export function OperationalListPage({ source }: { source: Source }) {
  const [rows, setRows] = useState<Array<Record<string, unknown>>>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const loadNotifications = () =>
    phase3.notifications().then((result) => setRows(result.notifications as unknown as Array<Record<string, unknown>>))
  useEffect(() => { void (async () => {
    try {
      if (source === 'incidents') setRows((await phase3.incidents()).incidents as unknown as Array<Record<string, unknown>>)
      else if (source === 'notifications') await loadNotifications()
      else if (source === 'audit') setRows((await phase3.auditLogs()).auditLogs)
      else if (source === 'settings') setRows((await phase3.settings()).settings)
      else if (source === 'assignments') setRows((await phase3.assignments(true)).assignments as unknown as Array<Record<string, unknown>>)
      else setRows(Object.entries(await phase3.analytics()).map(([metric, value]) => ({ metric, value })))
    } catch (e) { setError(e instanceof Error ? e.message : 'Unable to load records') }
    finally { setLoading(false) }
  })() }, [source])
  return <><PageHeading title={COPY[source][0]} description={COPY[source][1]} />{error && <p className="mb-4 text-sm text-destructive">{error}</p>}{loading ? <Card className="p-8 text-center text-muted-foreground">Loading…</Card> : <div className="space-y-3">{rows.map((row, index) => <Card className="p-4" key={String(row.id ?? row.metric ?? index)}><div className="grid gap-2 text-sm md:grid-cols-3">{Object.entries(row).filter(([, value]) => typeof value !== 'object').slice(0, 9).map(([key, value]) => <div key={key}><span className="text-xs capitalize text-muted-foreground">{key.replaceAll('_', ' ')}</span><p className="break-words">{String(value ?? '-')}</p></div>)}</div>{source === 'notifications' && !row.readAt && <Button className="mt-3" variant="outline" onClick={() => void phase3.readNotification(String(row.id)).then(loadNotifications)}>Mark read</Button>}</Card>)}{rows.length === 0 && !error && <Card className="p-8 text-center text-muted-foreground">No records yet.</Card>}</div>}</>
}
