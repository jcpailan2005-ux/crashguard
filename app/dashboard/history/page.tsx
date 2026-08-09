'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  Calendar,
  Clock,
  History as HistoryIcon,
  MapPin,
  Search,
  ShieldCheck,
  User,
  Video,
} from 'lucide-react'

import { useAuth } from '@/components/auth-provider'
import { DashboardHeader, Sidebar } from '@/components/dashboard-sidebar'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { getLocalCrashCases } from '@/lib/api-client'
import { getCaseStatusLabel, getIncidentTitle } from '@/lib/incident-status'
import { getCaseStatusClass } from '@/lib/theme-status'
import { LocalCrashCase } from '@/lib/types'

const PAGE_SIZE = 12
const DISPATCHED_STATUSES = new Set(['dispatched', 'responding', 'arrived', 'resolved'])

type DateFilter = 'recent' | 'today' | 'last30' | 'all' | 'custom'

function toDateInputValue(date: Date) {
  return date.toISOString().slice(0, 10)
}

function getPresetRange(filter: DateFilter) {
  if (filter === 'all' || filter === 'custom') {
    return { fromDate: '', toDate: '' }
  }

  const to = new Date()
  const from = new Date()
  from.setHours(0, 0, 0, 0)
  if (filter === 'recent') from.setDate(from.getDate() - 6)
  if (filter === 'last30') from.setDate(from.getDate() - 29)

  return {
    fromDate: toDateInputValue(from),
    toDate: toDateInputValue(to),
  }
}

function formatDate(dateStr?: string | null): string {
  if (!dateStr) return 'N/A'
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return dateStr
  }
}

function formatTime(dateStr?: string | null): string {
  if (!dateStr) return 'N/A'
  try {
    const d = new Date(dateStr)
    return d.toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return dateStr
  }
}

function formatFullDateTime(dateStr?: string | null): string {
  if (!dateStr) return 'N/A'
  try {
    const d = new Date(dateStr)
    return d.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return dateStr
  }
}

function extractActionTimestamp(
  caseItem: LocalCrashCase,
  actionTypes: string[]
): string | null {
  if (!caseItem.actions || caseItem.actions.length === 0) return null
  const matched = caseItem.actions.find((a) => actionTypes.includes(a.action))
  return matched?.timestamp ?? null
}

export default function HistoryPage() {
  const router = useRouter()
  const { profile, loading: authLoading } = useAuth()
  const [cases, setCases] = useState<LocalCrashCase[]>([])
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('all')
  const [areaId, setAreaId] = useState('all')
  const [dateFilter, setDateFilter] = useState<DateFilter>('all')
  const [customFrom, setCustomFrom] = useState('')
  const [customTo, setCustomTo] = useState('')
  const [sort, setSort] = useState('newest')
  const [limit, setLimit] = useState(PAGE_SIZE)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (authLoading) return
    if (!profile || profile.role !== 'responder') {
      router.replace('/dashboard')
    }
  }, [authLoading, profile, router])

  const presetRange = getPresetRange(dateFilter)
  const fromDate = dateFilter === 'custom' ? customFrom : presetRange.fromDate
  const toDate = dateFilter === 'custom' ? customTo : presetRange.toDate

  const fetchHistory = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await getLocalCrashCases({
        search,
        status,
        areaId,
        fromDate,
        toDate,
        sort,
        limit,
      })
      // Strictly enforce Responder History rule: Dispatched, Responding, Arrived, Resolved cases ONLY
      const historyOnly = data.filter((item) => DISPATCHED_STATUSES.has(item.status))
      setCases(historyOnly)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load history.')
    } finally {
      setLoading(false)
    }
  }, [areaId, fromDate, limit, search, sort, status, toDate])

  useEffect(() => {
    if (authLoading || !profile || profile.role !== 'responder') return
    void fetchHistory()
  }, [authLoading, fetchHistory, profile])

  const areas = useMemo(
    () =>
      Array.from(
        new Set(
          cases
            .map((c) => c.areaId || c.location || 'Unassigned')
            .filter(Boolean)
        )
      ),
    [cases]
  )

  if (authLoading || !profile || profile.role !== 'responder') {
    return null
  }

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <div className="flex-1 md:ml-0">
        <DashboardHeader />
        <main className="space-y-6 p-6">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <HistoryIcon className="h-7 w-7 text-primary" />
                <h1 className="text-3xl font-bold">Responder History</h1>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                Automatic record of dispatched, responding, arrived, and resolved incident responses.
              </p>
            </div>
            <Badge variant="outline" className="w-fit text-xs font-semibold uppercase tracking-wider">
              {cases.length} {cases.length === 1 ? 'Record' : 'Records'}
            </Badge>
          </div>

          {error ? (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}

          {/* Filters Card */}
          <Card className="border border-border bg-card p-4 space-y-4">
            <div className="grid gap-3 md:grid-cols-[1fr_11rem_11rem_10rem]">
              <div className="relative">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  value={search}
                  onChange={(event) => {
                    setSearch(event.target.value)
                    setLimit(PAGE_SIZE)
                  }}
                  placeholder="Search Case ID, location, camera, responder..."
                  className="pl-9"
                />
              </div>
              <Select
                value={status}
                onValueChange={(value) => {
                  setStatus(value)
                  setLimit(PAGE_SIZE)
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Dispatched Statuses</SelectItem>
                  <SelectItem value="dispatched">Dispatched</SelectItem>
                  <SelectItem value="responding">Responding</SelectItem>
                  <SelectItem value="arrived">Arrived at Scene</SelectItem>
                  <SelectItem value="resolved">Resolved</SelectItem>
                </SelectContent>
              </Select>
              <Select
                value={areaId}
                onValueChange={(value) => {
                  setAreaId(value)
                  setLimit(PAGE_SIZE)
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Area" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Areas</SelectItem>
                  {areas.map((area) => (
                    <SelectItem key={area} value={area}>
                      {area}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select
                value={sort}
                onValueChange={(value) => {
                  setSort(value)
                  setLimit(PAGE_SIZE)
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Sort" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="newest">Newest First</SelectItem>
                  <SelectItem value="oldest">Oldest First</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                {(
                  [
                    ['all', 'All Time'],
                    ['today', 'Today'],
                    ['recent', 'Last 7 Days'],
                    ['last30', 'Last 30 Days'],
                    ['custom', 'Custom Range'],
                  ] as const
                ).map(([value, label]) => (
                  <Button
                    key={value}
                    type="button"
                    size="sm"
                    variant={dateFilter === value ? 'default' : 'outline'}
                    onClick={() => {
                      setDateFilter(value)
                      setLimit(PAGE_SIZE)
                    }}
                  >
                    {label}
                  </Button>
                ))}
              </div>

              {dateFilter === 'custom' ? (
                <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
                  <Input
                    type="date"
                    value={customFrom}
                    onChange={(event) => {
                      setCustomFrom(event.target.value)
                      setLimit(PAGE_SIZE)
                    }}
                    max={customTo || undefined}
                  />
                  <Input
                    type="date"
                    value={customTo}
                    onChange={(event) => {
                      setCustomTo(event.target.value)
                      setLimit(PAGE_SIZE)
                    }}
                    min={customFrom || undefined}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      if (!customFrom && !customTo) {
                        const today = toDateInputValue(new Date())
                        setCustomFrom(today)
                        setCustomTo(today)
                      }
                    }}
                  >
                    Apply Range
                  </Button>
                </div>
              ) : null}
            </div>
          </Card>

          {/* History Case Cards List (READ ONLY) */}
          <div className="grid gap-4">
            {loading && cases.length === 0 ? (
              <Card className="border border-border bg-card p-8 text-center text-muted-foreground">
                Loading responder history records...
              </Card>
            ) : cases.length === 0 ? (
              <Card className="border border-border bg-card p-8 text-center text-muted-foreground">
                No responder history records found for the selected filters.
              </Card>
            ) : (
              cases.map((caseItem) => {
                const cameraName =
                  caseItem.cameraName || caseItem.sourceCamera || 'CCTV Camera'
                const locationLabel =
                  caseItem.location || caseItem.areaId || 'Location Not Specified'
                const confidencePct = `${Math.round((caseItem.confidence ?? 0.8) * 100)}%`
                const responderAssigned =
                  caseItem.assignedResponderId ||
                  caseItem.responderId ||
                  profile?.email ||
                  'Assigned Responder'

                const dispatchTime =
                  caseItem.dispatchedAt ||
                  extractActionTimestamp(caseItem, ['dispatch_help'])
                const arrivalTime = extractActionTimestamp(caseItem, [
                  'arrive_scene',
                  'accept_dispatch',
                ])
                const resolvedTime =
                  caseItem.resolvedAt ||
                  extractActionTimestamp(caseItem, ['resolve_case'])

                return (
                  <Card
                    key={caseItem.caseId}
                    className="border border-border bg-card p-5 transition-colors hover:border-border/80"
                  >
                    <div className="space-y-4">
                      {/* Header Row */}
                      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border/60 pb-3">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-bold text-lg text-foreground">
                              Crash Incident
                            </span>
                            <span className="font-mono text-sm text-muted-foreground">
                              · {caseItem.caseId}
                            </span>
                          </div>
                          <p className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
                            <Calendar className="h-3.5 w-3.5" />
                            <span>Date: {formatDate(caseItem.detectedAt)}</span>
                            <span className="mx-1">|</span>
                            <Clock className="h-3.5 w-3.5" />
                            <span>Time: {formatTime(caseItem.detectedAt)}</span>
                          </p>
                        </div>
                        <Badge
                          className={`${getCaseStatusClass(caseItem.status)} text-xs px-3 py-1`}
                          variant="outline"
                        >
                          {getCaseStatusLabel(caseItem.status)}
                        </Badge>
                      </div>

                      {/* Content Grid */}
                      <div className="grid gap-3 text-sm sm:grid-cols-2 md:grid-cols-3">
                        <div className="space-y-1">
                          <p className="text-xs font-medium text-muted-foreground">
                            Camera Name
                          </p>
                          <p className="flex items-center gap-1.5 font-medium">
                            <Video className="h-4 w-4 text-primary shrink-0" />
                            <span className="truncate">{cameraName}</span>
                          </p>
                        </div>

                        <div className="space-y-1">
                          <p className="text-xs font-medium text-muted-foreground">
                            Location
                          </p>
                          <p className="flex items-center gap-1.5 font-medium">
                            <MapPin className="h-4 w-4 text-primary shrink-0" />
                            <span className="truncate">{locationLabel}</span>
                          </p>
                        </div>

                        <div className="space-y-1">
                          <p className="text-xs font-medium text-muted-foreground">
                            AI Confidence
                          </p>
                          <p className="flex items-center gap-1.5 font-medium">
                            <ShieldCheck className="h-4 w-4 text-emerald-500 shrink-0" />
                            <span>{confidencePct}</span>
                          </p>
                        </div>

                        <div className="space-y-1">
                          <p className="text-xs font-medium text-muted-foreground">
                            Responder Assigned
                          </p>
                          <p className="flex items-center gap-1.5 font-medium">
                            <User className="h-4 w-4 text-blue-500 shrink-0" />
                            <span className="truncate">{responderAssigned}</span>
                          </p>
                        </div>

                        <div className="space-y-1">
                          <p className="text-xs font-medium text-muted-foreground">
                            Dispatch Time
                          </p>
                          <p className="font-mono text-xs">
                            {formatFullDateTime(dispatchTime)}
                          </p>
                        </div>

                        {arrivalTime ? (
                          <div className="space-y-1">
                            <p className="text-xs font-medium text-muted-foreground">
                              Arrival Time
                            </p>
                            <p className="font-mono text-xs text-amber-500">
                              {formatFullDateTime(arrivalTime)}
                            </p>
                          </div>
                        ) : null}

                        {resolvedTime ? (
                          <div className="space-y-1">
                            <p className="text-xs font-medium text-muted-foreground">
                              Resolved Time
                            </p>
                            <p className="font-mono text-xs text-emerald-500">
                              {formatFullDateTime(resolvedTime)}
                            </p>
                          </div>
                        ) : null}
                      </div>

                      {caseItem.notes ? (
                        <div className="rounded-md border border-border bg-muted/30 p-3 text-xs">
                          <span className="font-semibold text-muted-foreground">
                            Resolution / Case Notes:{' '}
                          </span>
                          <span>{caseItem.notes}</span>
                        </div>
                      ) : null}
                    </div>
                  </Card>
                )
              })
            )}
          </div>

          {cases.length >= limit ? (
            <div className="flex justify-center pt-2">
              <Button variant="outline" onClick={() => setLimit((current) => current + PAGE_SIZE)}>
                Load More History Records
              </Button>
            </div>
          ) : null}
        </main>
      </div>
    </div>
  )
}
