'use client'

import { useEffect, useMemo, useState } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Activity, Clock, ShieldCheck, XCircle } from 'lucide-react'

import { DashboardHeader, Sidebar } from '@/components/dashboard-sidebar'
import { PermissionMessage } from '@/components/permission-message'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Card } from '@/components/ui/card'
import { useAuth } from '@/components/auth-provider'
import {
  getAnalyticsSummary,
  getAreaAnalytics,
  getMonthlyAnalytics,
} from '@/lib/api-client'
import {
  AnalyticsSummary,
  AreaAnalyticsPoint,
  MonthlyAnalyticsPoint,
} from '@/lib/types'

function formatDuration(seconds: number | null) {
  if (seconds == null) return 'Not enough data'
  const minutes = Math.round(seconds / 60)
  if (minutes < 1) return '<1 min'
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return rest ? `${hours}h ${rest}m` : `${hours}h`
}

export default function AnalyticsPage() {
  const { profile } = useAuth()
  const isAdmin = profile?.role === 'admin'
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null)
  const [monthly, setMonthly] = useState<MonthlyAnalyticsPoint[]>([])
  const [areas, setAreas] = useState<AreaAnalyticsPoint[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    if (!isAdmin) return

    Promise.all([
      getAnalyticsSummary(),
      getMonthlyAnalytics(),
      getAreaAnalytics(),
    ])
      .then(([summaryData, monthlyData, areaData]) => {
        setSummary(summaryData)
        setMonthly(monthlyData)
        setAreas(areaData)
        setError('')
      })
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : 'Could not load analytics.')
      })
  }, [isAdmin])

  const decisionData = useMemo(
    () => [
      { name: 'Confirmed', value: summary?.confirmedCrashes ?? 0 },
      { name: 'False Alarms', value: summary?.falseAlarms ?? 0 },
    ],
    [summary]
  )

  if (!isAdmin) {
    return <PermissionMessage />
  }

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <div className="flex-1 md:ml-0">
        <DashboardHeader />
        <main className="space-y-6 p-6">
          <div>
            <h1 className="text-3xl font-bold">Analytics</h1>
            <p className="text-muted-foreground">
              Local SQLite crash detection metrics for review quality and response time.
            </p>
          </div>

          {error ? (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {[
              ['Detections This Month', summary?.detectionsThisMonth ?? 0, <Activity key="i" className="h-5 w-5" />],
              ['Detections This Year', summary?.detectionsThisYear ?? 0, <Activity key="y" className="h-5 w-5" />],
              ['Confirmed Crashes', summary?.confirmedCrashes ?? 0, <ShieldCheck key="c" className="h-5 w-5" />],
              ['False Alarms', summary?.falseAlarms ?? 0, <XCircle key="f" className="h-5 w-5" />],
            ].map(([label, value, icon]) => (
              <Card key={label as string} className="border border-border bg-card p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm text-muted-foreground">{label as string}</p>
                    <p className="mt-2 text-3xl font-bold">{value as number}</p>
                  </div>
                  <div className="rounded-md bg-muted p-2 text-muted-foreground">{icon}</div>
                </div>
              </Card>
            ))}
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <Card className="border border-border bg-card p-4">
              <div className="mb-4 flex items-center gap-2">
                <Clock className="h-5 w-5 text-muted-foreground" />
                <h2 className="font-semibold">Average Response Times</h2>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-md border border-border bg-background/50 p-4">
                  <p className="text-sm text-muted-foreground">Average Review Time</p>
                  <p className="mt-2 text-2xl font-bold">
                    {formatDuration(summary?.averageReviewTimeSeconds ?? null)}
                  </p>
                </div>
                <div className="rounded-md border border-border bg-background/50 p-4">
                  <p className="text-sm text-muted-foreground">Average Resolve Time</p>
                  <p className="mt-2 text-2xl font-bold">
                    {formatDuration(summary?.averageResolveTimeSeconds ?? null)}
                  </p>
                </div>
              </div>
            </Card>

            <Card className="border border-border bg-card p-4">
              <h2 className="mb-4 font-semibold">Confirmed vs False Alarms</h2>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={decisionData} dataKey="value" nameKey="name" outerRadius={80} label />
                    <Tooltip />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
            <Card className="border border-border bg-card p-4">
              <h2 className="mb-4 font-semibold">Monthly Crash Detection Trend</h2>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={monthly}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="month" />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Legend />
                    <Area type="monotone" dataKey="detections" stroke="var(--primary)" fill="var(--primary)" fillOpacity={0.2} />
                    <Area type="monotone" dataKey="confirmedCrashes" stroke="var(--status-confirmed)" fill="var(--status-confirmed)" fillOpacity={0.15} />
                    <Area type="monotone" dataKey="falseAlarms" stroke="var(--status-false-alarm)" fill="var(--status-false-alarm)" fillOpacity={0.15} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </Card>

            <Card className="border border-border bg-card p-4">
              <h2 className="mb-4 font-semibold">Cases by Area / Location</h2>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={areas}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="area" />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Bar dataKey="cases" fill="var(--primary)" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>
        </main>
      </div>
    </div>
  )
}
