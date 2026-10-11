'use client'

import { useCallback, useEffect, useState } from 'react'
import { Clock3, MapPin, Radio, ShieldCheck } from 'lucide-react'

import { PageHeading } from '@/components/page-heading'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { phase3, type OperationalAssignment } from '@/lib/phase3-api'

const NEXT: Record<string, { status: string; label: string }> = {
  ASSIGNED: { status: 'ACCEPTED', label: 'Accept assignment' },
  ACCEPTED: { status: 'EN_ROUTE', label: 'Mark en route' },
  EN_ROUTE: { status: 'ARRIVED', label: 'Mark arrived' },
  ARRIVED: { status: 'RESPONDING', label: 'Start response' },
  RESPONDING: { status: 'RESOLVED', label: 'Resolve incident' },
}

export default function ResponderHome() {
  const [assignments, setAssignments] = useState<OperationalAssignment[]>([])
  const [notes, setNotes] = useState('')
  const [outcome, setOutcome] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const refresh = useCallback(async () => {
    try {
      const result = await phase3.assignments()
      setAssignments(result.assignments)
      setError('')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not load your assignment.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
    const interval = window.setInterval(() => void refresh(), 15_000)
    return () => window.clearInterval(interval)
  }, [refresh])

  const setAvailability = async (status: 'AVAILABLE' | 'OFFLINE') => {
    if (busy) return
    setBusy('availability')
    setError('')
    setMessage('')
    try {
      await phase3.availability(status)
      setMessage(status === 'AVAILABLE' ? 'You are available for dispatch.' : 'You are unavailable for new dispatches.')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Availability update failed.')
    } finally {
      setBusy(null)
    }
  }

  const transition = async (assignment: OperationalAssignment, status: string, extra: Record<string, unknown> = {}) => {
    if (busy) return
    setBusy(assignment.id)
    setError('')
    setMessage('')
    try {
      await phase3.transition(assignment.id, status, extra)
      setNotes('')
      setOutcome('')
      setMessage(`Assignment updated to ${status.replaceAll('_', ' ')}.`)
      await refresh()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Assignment update failed.')
    } finally {
      setBusy(null)
    }
  }

  return <>
    <PageHeading title="Response workspace" description="New assignments and dispatcher updates appear automatically." />
    <div className="mb-5 flex flex-wrap items-center gap-2"><Button variant="outline" disabled={Boolean(busy)} onClick={() => void setAvailability('AVAILABLE')}><Radio />Available</Button><Button variant="outline" disabled={Boolean(busy) || assignments.length > 0} onClick={() => void setAvailability('OFFLINE')}>Unavailable</Button><Badge variant="outline" className="ml-auto border-[var(--status-online)] bg-[color:var(--status-online-bg)] text-[var(--status-online)]">Authenticated presence active</Badge></div>
    {error ? <Alert variant="destructive" className="mb-4"><AlertDescription>{error}</AlertDescription></Alert> : null}
    {message ? <Alert className="mb-4"><AlertDescription>{message}</AlertDescription></Alert> : null}
    <div className="space-y-4">
      {assignments.map((assignment) => {
        const next = NEXT[assignment.status]
        const resolving = next?.status === 'RESOLVED'
        const isBusy = busy === assignment.id
        return <Card className="overflow-hidden" key={assignment.id}>
          <div className="border-b bg-muted/35 p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-lg font-semibold">{assignment.incidentType ?? 'Traffic incident'}</p><p className="mt-1 flex items-center gap-1.5 text-sm text-muted-foreground"><MapPin className="h-4 w-4" />{assignment.location ?? 'Location pending'}</p></div><Badge>{assignment.status.replaceAll('_', ' ')}</Badge></div></div>
          <div className="grid gap-4 p-5 sm:grid-cols-3"><Info icon={ShieldCheck} label="Priority" value={assignment.priority ?? 'Unassigned'} /><Info icon={Clock3} label="Assigned" value={new Date(assignment.assignedAt).toLocaleString()} /><Info icon={Radio} label="Dispatcher" value={assignment.dispatcherName ?? 'Dispatch operations'} /></div>
          {assignment.status === 'RESPONDING' ? <div className="grid gap-3 border-t p-5 sm:grid-cols-2"><Input aria-label="Response notes" placeholder="Response notes (required)" value={notes} onChange={(event) => setNotes(event.target.value)} /><Input aria-label="Response outcome" placeholder="Outcome (required)" value={outcome} onChange={(event) => setOutcome(event.target.value)} /></div> : null}
          <div className="flex flex-wrap gap-2 border-t p-5">{next ? <Button disabled={Boolean(busy) || (resolving && (!notes.trim() || !outcome.trim()))} onClick={() => void transition(assignment, next.status, resolving ? { notes, outcome } : {})}>{isBusy ? 'Updating…' : next.label}</Button> : null}{assignment.status === 'ASSIGNED' ? <Button variant="destructive" disabled={Boolean(busy)} onClick={() => void transition(assignment, 'DECLINED', { declineReason: 'Responder unavailable' })}>Decline</Button> : null}</div>
        </Card>
      })}
      {!loading && assignments.length === 0 ? <Card className="p-10 text-center"><Radio className="mx-auto mb-3 text-muted-foreground" /><p className="font-medium">No active assignment</p><p className="mt-1 text-sm text-muted-foreground">Stay available. New dispatches will appear here automatically.</p></Card> : null}
      {loading ? <Card className="p-10 text-center text-muted-foreground">Loading your assignment…</Card> : null}
    </div>
  </>
}

function Info({ icon: Icon, label, value }: { icon: typeof Clock3; label: string; value: string }) {
  return <div><p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground"><Icon className="h-3.5 w-3.5" />{label}</p><p className="mt-1 text-sm font-medium">{value}</p></div>
}
