'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Activity, Camera, Radio, ShieldCheck, UsersRound } from 'lucide-react'

import { PageHeading } from '@/components/page-heading'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { phase3 } from '@/lib/phase3-api'

export default function AdminHome() {
  const [summary, setSummary] = useState<Record<string, unknown>>({})
  const [onlineResponders, setOnlineResponders] = useState(0)

  useEffect(() => {
    let cancelled = false
    const refresh = async () => {
      const [analytics, presence] = await Promise.all([phase3.analytics(), phase3.responders()])
      if (!cancelled) {
        setSummary(analytics)
        setOnlineResponders(presence.responders.filter((responder) => responder.presenceStatus === 'ONLINE').length)
      }
    }
    void refresh()
    const interval = window.setInterval(() => void refresh(), 30_000)
    return () => { cancelled = true; window.clearInterval(interval) }
  }, [])

  const metrics = [
    { label: 'Active cameras', value: summary.activeCameras ?? '—', icon: Camera },
    { label: 'Active users', value: summary.activeUsers ?? '—', icon: UsersRound },
    { label: 'Online responders', value: onlineResponders, icon: Radio },
    { label: 'Incidents today', value: summary.incidentsToday ?? '—', icon: Activity },
    { label: 'Pending reviews', value: summary.pendingReviews ?? '—', icon: ShieldCheck },
    { label: 'Active responses', value: summary.activeResponses ?? '—', icon: Activity },
  ]
  return <>
    <PageHeading title="System administration" description="Operational health, access governance, infrastructure, and audit visibility." />
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{metrics.map(({ label, value, icon: Icon }) => <Card className="p-5" key={label}><div className="flex items-center justify-between"><p className="text-sm text-muted-foreground">{label}</p><Icon className="h-5 w-5 text-primary" /></div><p className="mt-3 text-3xl font-bold">{String(value)}</p></Card>)}</div>
    <div className="mt-6 grid gap-4 md:grid-cols-3"><QuickLink href="/admin/users" title="User management" text="Accounts, roles, areas, and access status." /><QuickLink href="/admin/cameras" title="Camera management" text="Configure and monitor CCTV infrastructure." /><QuickLink href="/admin/audit-logs" title="Audit trail" text="Review meaningful authentication and operational actions." /></div>
  </>
}

function QuickLink({ href, title, text }: { href: string; title: string; text: string }) {
  return <Card className="p-5"><h2 className="font-semibold">{title}</h2><p className="my-3 text-sm text-muted-foreground">{text}</p><Button asChild variant="outline" size="sm"><Link href={href}>Open</Link></Button></Card>
}
