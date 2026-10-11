'use client'

import { useCallback, useEffect, useState } from 'react'
import { RefreshCw, UsersRound } from 'lucide-react'

import { PageHeading } from '@/components/page-heading'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { phase3, type ResponderPresence } from '@/lib/phase3-api'
import { formatLastSeen, responderAssignmentLabel, sortRespondersByAvailability } from '@/lib/responder-presence'

export default function ResponderAvailabilityPage() {
  const [rows, setRows] = useState<ResponderPresence[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')

  const refresh = useCallback(async (quiet = false) => {
    if (!quiet) setRefreshing(true)
    try {
      const result = await phase3.responders()
      setRows(sortRespondersByAvailability(result.responders))
      setError('')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not load responder presence.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    void refresh(true)
    const interval = window.setInterval(() => void refresh(true), 25_000)
    return () => window.clearInterval(interval)
  }, [refresh])

  return <>
    <PageHeading title="Responder availability" description="Authenticated presence refreshes automatically every 25 seconds." />
    <div className="mb-4 flex justify-end"><Button variant="outline" size="sm" disabled={refreshing} onClick={() => void refresh()}><RefreshCw className={refreshing ? 'animate-spin' : ''} />{refreshing ? 'Refreshing…' : 'Refresh'}</Button></div>
    {error ? <Alert variant="destructive" className="mb-4"><AlertDescription>{error}</AlertDescription></Alert> : null}
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="border-b bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground"><tr><th className="px-4 py-3">Responder</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Last seen</th><th className="px-4 py-3">Assignment</th></tr></thead>
          <tbody className="divide-y">
            {rows.map((responder) => <tr key={responder.uid} className="transition-colors hover:bg-muted/35">
              <td className="px-4 py-3"><p className="font-medium">{responder.displayName}</p><p className="text-xs text-muted-foreground">{responder.email}</p></td>
              <td className="px-4 py-3"><Badge variant="outline" className={responder.presenceStatus === 'ONLINE' ? 'border-[var(--status-online)] bg-[color:var(--status-online-bg)] text-[var(--status-online)]' : 'text-muted-foreground'}>{responder.presenceStatus === 'ONLINE' ? '● Online' : '○ Offline'}</Badge></td>
              <td className="px-4 py-3 text-muted-foreground">{formatLastSeen(responder.lastSeenAt)}</td>
              <td className="px-4 py-3"><p>{responderAssignmentLabel(responder)}</p><p className="text-xs text-muted-foreground">{responder.availabilityStatus ?? 'OFFLINE'}</p></td>
            </tr>)}
          </tbody>
        </table>
      </div>
      {!loading && rows.length === 0 ? <div className="flex flex-col items-center gap-2 p-10 text-center text-muted-foreground"><UsersRound /><p>No active responder accounts.</p></div> : null}
      {loading ? <div className="p-10 text-center text-muted-foreground">Loading responder presence…</div> : null}
    </Card>
  </>
}
