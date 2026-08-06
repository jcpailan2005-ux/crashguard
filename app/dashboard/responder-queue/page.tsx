'use client'

import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'
import { Clock, MapPin, Search } from 'lucide-react'

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
import { getCaseStatusLabel } from '@/lib/incident-status'
import { getCaseStatusClass } from '@/lib/theme-status'
import { LocalCrashCase } from '@/lib/types'

const PAGE_SIZE = 12
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

export default function ResponderQueuePage() {
  const [cases, setCases] = useState<LocalCrashCase[]>([])
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('all')
  const [areaId, setAreaId] = useState('all')
  const [dateFilter, setDateFilter] = useState<DateFilter>('recent')
  const [customFrom, setCustomFrom] = useState('')
  const [customTo, setCustomTo] = useState('')
  const [sort, setSort] = useState('newest')
  const [limit, setLimit] = useState(PAGE_SIZE)
  const [error, setError] = useState('')

  const presetRange = getPresetRange(dateFilter)
  const fromDate = dateFilter === 'custom' ? customFrom : presetRange.fromDate
  const toDate = dateFilter === 'custom' ? customTo : presetRange.toDate

  useEffect(() => {
    getLocalCrashCases({ search, status, areaId, fromDate, toDate, sort, limit })
      .then((data) => {
        setCases(data)
        setError('')
      })
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : 'Could not load queue.')
      })
  }, [areaId, fromDate, limit, search, sort, status, toDate])

  const areas = useMemo(
    () =>
      Array.from(
        new Set(cases.map((caseItem) => caseItem.areaId || caseItem.location || 'Unassigned'))
      ),
    [cases]
  )

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <div className="flex-1 md:ml-0">
        <DashboardHeader />
        <main className="space-y-6 p-6">
          <div>
            <h1 className="text-3xl font-bold">Responder Queue</h1>
            <p className="text-muted-foreground">
              Search, filter, and review local SQLite crash cases.
            </p>
          </div>

          {error ? (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}

          <Card className="border border-border bg-card p-4">
            <div className="grid gap-3 md:grid-cols-[1fr_11rem_11rem_10rem]">
              <div className="relative">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  value={search}
                  onChange={(event) => {
                    setSearch(event.target.value)
                    setLimit(PAGE_SIZE)
                  }}
                  placeholder="Search case, location, camera..."
                  className="pl-9"
                />
              </div>
              <Select value={status} onValueChange={(value) => { setStatus(value); setLimit(PAGE_SIZE) }}>
                <SelectTrigger><SelectValue placeholder="Status" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Dispatched Cases</SelectItem>
                  <SelectItem value="dispatched">Dispatched</SelectItem>
                  <SelectItem value="responding">Responding</SelectItem>
                  <SelectItem value="arrived">Arrived at Scene</SelectItem>
                  <SelectItem value="resolved">Resolved</SelectItem>
                </SelectContent>
              </Select>
              <Select value={areaId} onValueChange={(value) => { setAreaId(value); setLimit(PAGE_SIZE) }}>
                <SelectTrigger><SelectValue placeholder="Area" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Areas</SelectItem>
                  {areas.map((area) => (
                    <SelectItem key={area} value={area}>{area}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={sort} onValueChange={(value) => { setSort(value); setLimit(PAGE_SIZE) }}>
                <SelectTrigger><SelectValue placeholder="Sort" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="newest">Newest</SelectItem>
                  <SelectItem value="oldest">Oldest</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="mt-4 space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                {([
                  ['recent', 'Recent'],
                  ['today', 'Today'],
                  ['last30', 'Last 30 Days'],
                  ['all', 'All'],
                  ['custom', 'Custom'],
                ] as const).map(([value, label]) => (
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
                    Apply
                  </Button>
                </div>
              ) : null}
              <p className="text-sm text-muted-foreground">
                Showing newest crash records first unless Oldest is selected.
              </p>
            </div>
          </Card>

          <div className="grid gap-3">
            {cases.length === 0 ? (
              <Card className="border border-border bg-card p-8 text-center text-muted-foreground">
                No crash records found for this date.
              </Card>
            ) : (
              cases.map((caseItem) => (
                <Card key={caseItem.caseId} className="border border-border bg-card p-4">
                  <div className="grid gap-4 lg:grid-cols-[1fr_auto]">
                    <div className="min-w-0 space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-semibold">{caseItem.caseId}</p>
                        <Badge className={getCaseStatusClass(caseItem.status)} variant="outline">
                          {getCaseStatusLabel(caseItem.status)}
                        </Badge>
                      </div>
                      <p className="truncate text-sm">
                        {caseItem.cameraName || caseItem.sourceCamera || 'No camera label'}
                        {caseItem.barangay ? ` · ${caseItem.barangay}` : ''}
                        {caseItem.roadName ? ` · ${caseItem.roadName}` : caseItem.location ? ` · ${caseItem.location}` : ''}
                      </p>
                      <div className="flex flex-wrap gap-3 text-sm text-muted-foreground">
                        <span className="inline-flex items-center gap-1">
                          <Clock className="h-4 w-4" />
                          {new Date(caseItem.detectedAt).toLocaleString()}
                        </span>
                        <span>{(caseItem.confidence * 100).toFixed(0)}% confidence</span>
                        <span>{caseItem.cameraId || caseItem.sourceCamera || 'No camera label'}</span>
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 lg:justify-end">
                      <Button asChild>
                        <Link href={`/dashboard/map?caseId=${caseItem.caseId}`}>
                          <MapPin className="h-4 w-4" />
                          Review on Map
                        </Link>
                      </Button>
                    </div>
                  </div>
                </Card>
              ))
            )}
          </div>

          {cases.length >= limit ? (
            <div className="flex justify-center">
              <Button variant="outline" onClick={() => setLimit((current) => current + PAGE_SIZE)}>
                Load More
              </Button>
            </div>
          ) : null}
        </main>
      </div>
    </div>
  )
}
