'use client'

import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  BarChart3,
  ClipboardCheck,
  Clock,
  ListChecks,
  MapPin,
  ShieldQuestion,
  Truck,
  XCircle,
} from 'lucide-react'

import { useAuth } from '@/components/auth-provider'
import { DashboardHeader, Sidebar } from '@/components/dashboard-sidebar'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { subscribeCrashCases, summarizeCaseCounts } from '@/lib/crash-case-store'
import { getFirebaseConfigError, getFirestoreOrNull } from '@/lib/firebase-guards'
import { CrashCase } from '@/lib/types'

const STAT_CARDS = [
  {
    key: 'pendingReview',
    label: 'Pending Review',
    icon: <ShieldQuestion className="h-5 w-5" />,
    tone: 'text-[var(--status-pending)] bg-[color:var(--status-pending-bg)]',
  },
  {
    key: 'underReview',
    label: 'Under Review',
    icon: <Clock className="h-5 w-5" />,
    tone: 'text-[var(--status-under-review)] bg-[color:var(--status-under-review-bg)]',
  },
  {
    key: 'confirmedCrashes',
    label: 'Confirmed Crashes',
    icon: <AlertTriangle className="h-5 w-5" />,
    tone: 'text-[var(--status-confirmed)] bg-[color:var(--status-confirmed-bg)]',
  },
  {
    key: 'dispatchedCases',
    label: 'Dispatched Cases',
    icon: <Truck className="h-5 w-5" />,
    tone: 'text-[var(--status-dispatched)] bg-[color:var(--status-dispatched-bg)]',
  },
  {
    key: 'falseAlarms',
    label: 'False Alarms',
    icon: <XCircle className="h-5 w-5" />,
    tone: 'text-[var(--status-false-alarm)] bg-[color:var(--status-false-alarm-bg)]',
  },
  {
    key: 'resolvedToday',
    label: 'Resolved Today',
    icon: <ClipboardCheck className="h-5 w-5" />,
    tone: 'text-[var(--status-resolved)] bg-[color:var(--status-resolved-bg)]',
  },
] as const

export default function DashboardPage() {
  const [cases, setCases] = useState<CrashCase[]>([])
  const [loading, setLoading] = useState(true)
  const [storeError, setStoreError] = useState<string | null>(null)
  const { profile } = useAuth()

  useEffect(() => {
    const db = getFirestoreOrNull()
    const configError = getFirebaseConfigError()

    if (!db || configError) {
      setStoreError(configError ?? 'Firestore is not ready.')
      setLoading(false)
      return
    }

    return subscribeCrashCases(
      db,
      (nextCases) => {
        setCases(nextCases)
        setStoreError(null)
        setLoading(false)
      },
      (error) => {
        setStoreError(error.message)
        setLoading(false)
      },
      profile?.role === 'responder' ? profile.areaId : null
    )
  }, [profile])

  const counts = useMemo(() => summarizeCaseCounts(cases), [cases])

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <div className="flex-1 md:ml-0">
        <DashboardHeader />
        <main className="space-y-6 p-6">
          <div>
            <h1 className="text-3xl font-bold">Dashboard</h1>
            <p className="text-muted-foreground">
              Summary view for crash review workload and local analytics.
            </p>
          </div>

          {storeError ? (
            <Alert variant="destructive">
              <AlertTitle>Incident store unavailable</AlertTitle>
              <AlertDescription>{storeError}</AlertDescription>
            </Alert>
          ) : null}

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
            {STAT_CARDS.map((item) => (
              <Card key={item.key} className="border border-border bg-card p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm text-muted-foreground">{item.label}</p>
                    <p className="mt-2 text-3xl font-bold">
                      {loading ? '-' : counts[item.key]}
                    </p>
                  </div>
                  <div className={`rounded-md p-2 ${item.tone}`}>{item.icon}</div>
                </div>
              </Card>
            ))}
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <Card className="border border-border bg-card p-5">
              <ListChecks className="mb-3 h-8 w-8 text-muted-foreground" />
              <h2 className="font-semibold">Responder Queue</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Search, filter, and review local SQLite crash cases.
              </p>
              <Button asChild className="mt-4 w-full">
                <Link href="/dashboard/responder-queue">Open Responder Queue</Link>
              </Button>
            </Card>

            <Card className="border border-border bg-card p-5">
              <MapPin className="mb-3 h-8 w-8 text-muted-foreground" />
              <h2 className="font-semibold">Map Review</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Review location, media evidence, and source context on the map.
              </p>
              <Button asChild variant="outline" className="mt-4 w-full">
                <Link href="/dashboard/map">Open Map Review</Link>
              </Button>
            </Card>

            <Card className="border border-border bg-card p-5">
              <BarChart3 className="mb-3 h-8 w-8 text-muted-foreground" />
              <h2 className="font-semibold">Analytics</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                View local detection trends, false alarms, and response-time metrics.
              </p>
              <Button asChild variant="outline" className="mt-4 w-full">
                <Link href="/dashboard/analytics">View Analytics</Link>
              </Button>
            </Card>
          </div>
        </main>
      </div>
    </div>
  )
}
