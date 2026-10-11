'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  ArrowUpDown,
  Ban,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  Copy,
  FilterX,
  History,
  Layers,
  MapPin,
  Minus,
  Navigation,
  RefreshCw,
  Search,
  X,
  XCircle,
} from 'lucide-react'

import { phase3, type OperationalAssignment } from '@/lib/phase3-api'
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
import { useToast } from '@/hooks/use-toast'

type DatePreset = 'all' | 'today' | 'last7' | 'last30'
type SortField = 'assignedAt' | 'duration' | 'priority' | 'status'
type SortOrder = 'asc' | 'desc'

function formatIncidentToken(id: string): string {
  if (!id) return 'INC-—'
  if (id.startsWith('INC-')) return id
  const clean = id.replace(/[^a-zA-Z0-9]/g, '')
  return `INC-${clean.slice(0, 4).toUpperCase()}`
}

function formatDate(dateStr?: string | null): string {
  if (!dateStr) return '—'
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  } catch {
    return dateStr
  }
}

function formatTime(dateStr?: string | null): string {
  if (!dateStr) return '—'
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

function formatMilestoneTime(dateStr?: string | null): string {
  if (!dateStr) return '—'
  try {
    const d = new Date(dateStr)
    return d.toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return dateStr
  }
}

function getDurationSeconds(start?: string | null, end?: string | null): number | null {
  if (!start || !end) return null
  try {
    const t0 = new Date(start).getTime()
    const t1 = new Date(end).getTime()
    if (isNaN(t0) || isNaN(t1) || t1 < t0) return null
    return Math.round((t1 - t0) / 1000)
  } catch {
    return null
  }
}

function formatDurationSeconds(sec: number | null): string {
  if (sec === null) return '—'
  if (sec < 60) return `${sec}s`
  const m = Math.floor(sec / 60)
  const s = sec % 60
  if (m < 60) return s > 0 ? `${m}m ${s}s` : `${m}m`
  const h = Math.floor(m / 60)
  const remM = m % 60
  return `${h}h ${remM}m`
}

function getAssignmentDuration(item: OperationalAssignment): {
  seconds: number | null
  label: string
} {
  const start = item.assignedAt
  if (item.status === 'DECLINED' && item.declinedAt) {
    const s = getDurationSeconds(start, item.declinedAt)
    return { seconds: s, label: s !== null ? `${formatDurationSeconds(s)} (Declined)` : 'Declined' }
  }
  if (item.status === 'CANCELLED' && item.cancelledAt) {
    const s = getDurationSeconds(start, item.cancelledAt)
    return { seconds: s, label: s !== null ? `${formatDurationSeconds(s)} (Cancelled)` : 'Cancelled' }
  }
  if (item.resolvedAt) {
    const s = getDurationSeconds(start, item.resolvedAt)
    return { seconds: s, label: formatDurationSeconds(s) }
  }
  if (item.arrivedAt) {
    const s = getDurationSeconds(start, item.arrivedAt)
    return { seconds: s, label: `${formatDurationSeconds(s)} (On scene)` }
  }
  if (item.enRouteAt) {
    const s = getDurationSeconds(start, item.enRouteAt)
    return { seconds: s, label: `${formatDurationSeconds(s)} (En route)` }
  }
  return { seconds: null, label: 'In progress' }
}

const PRIORITY_ORDER: Record<string, number> = {
  CRITICAL: 4,
  HIGH: 3,
  MEDIUM: 2,
  LOW: 1,
}

export function ResponseHistoryView({
  title = 'Response History',
  subtitle = 'Review past emergency-response dispatches, arrival velocity, and operational outcomes.',
}: {
  title?: string
  subtitle?: string
}) {
  const { toast } = useToast()
  const [assignments, setAssignments] = useState<OperationalAssignment[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')

  // Filters
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [priorityFilter, setPriorityFilter] = useState('ALL')
  const [datePreset, setDatePreset] = useState<DatePreset>('all')

  // Sorting & Pagination
  const [sortField, setSortField] = useState<SortField>('assignedAt')
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc')
  const [pageSize, setPageSize] = useState<number>(10)
  const [currentPage, setCurrentPage] = useState<number>(1)

  // Expanded Rows (set of assignment IDs)
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())

  // Technical Accordion inside expansion
  const [showTechnical, setShowTechnical] = useState<Record<string, boolean>>({})

  const loadAssignments = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) setRefreshing(true)
    else setLoading(true)
    setError('')
    try {
      const res = await phase3.assignments(true)
      setAssignments(res.assignments ?? [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to synchronize response history.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    void loadAssignments()
  }, [loadAssignments])

  const toggleRow = (id: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleTechnical = (id: string) => {
    setShowTechnical((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  const copyToClipboard = async (text: string, label: string) => {
    try {
      await navigator.clipboard.writeText(text)
      toast({
        title: 'Copied to clipboard',
        description: `${label}: ${text.slice(0, 16)}...`,
      })
    } catch {
      toast({
        title: 'Unable to copy',
        description: 'Clipboard write was blocked by the browser.',
        variant: 'destructive',
      })
    }
  }

  // Summary Metrics Calculation
  const metrics = useMemo(() => {
    const total = assignments.length
    const completed = assignments.filter((a) => a.status === 'RESOLVED').length
    const declined = assignments.filter((a) => a.status === 'DECLINED').length

    let totalDurationSec = 0
    let durationCount = 0
    for (const a of assignments) {
      const end = a.arrivedAt || a.resolvedAt
      if (a.assignedAt && end) {
        const sec = getDurationSeconds(a.assignedAt, end)
        if (sec !== null && sec > 0) {
          totalDurationSec += sec
          durationCount++
        }
      }
    }
    const avgSec = durationCount > 0 ? Math.round(totalDurationSec / durationCount) : null

    return {
      total,
      completed,
      completedRate: total > 0 ? Math.round((completed / total) * 100) : 0,
      declined,
      declinedRate: total > 0 ? Math.round((declined / total) * 100) : 0,
      avgResponseTime: formatDurationSeconds(avgSec),
    }
  }, [assignments])

  // Filter Logic
  const filteredAssignments = useMemo(() => {
    const now = Date.now()
    const query = search.trim().toLowerCase()

    return assignments.filter((item) => {
      // Search
      if (query) {
        const token = formatIncidentToken(item.incidentId).toLowerCase()
        const loc = (item.location ?? '').toLowerCase()
        const status = item.status.toLowerCase()
        const priority = (item.priority ?? '').toLowerCase()
        const responder = (item.responderId ?? '').toLowerCase()
        const dispatcher = (item.dispatcherName ?? '').toLowerCase()
        const reason = (item.declineReason ?? '').toLowerCase()
        const notes = (item.responseNotes ?? '').toLowerCase()

        const match =
          token.includes(query) ||
          loc.includes(query) ||
          status.includes(query) ||
          priority.includes(query) ||
          responder.includes(query) ||
          dispatcher.includes(query) ||
          reason.includes(query) ||
          notes.includes(query)
        if (!match) return false
      }

      // Status
      if (statusFilter !== 'ALL' && item.status !== statusFilter) {
        return false
      }

      // Priority
      if (priorityFilter !== 'ALL') {
        const p = (item.priority ?? '').toUpperCase()
        if (p !== priorityFilter) return false
      }

      // Date Presets
      if (datePreset !== 'all' && item.assignedAt) {
        const time = new Date(item.assignedAt).getTime()
        if (!isNaN(time)) {
          const diffHours = (now - time) / (1000 * 60 * 60)
          if (datePreset === 'today' && diffHours > 24) return false
          if (datePreset === 'last7' && diffHours > 24 * 7) return false
          if (datePreset === 'last30' && diffHours > 24 * 30) return false
        }
      }

      return true
    })
  }, [assignments, search, statusFilter, priorityFilter, datePreset])

  // Sort Logic
  const sortedAssignments = useMemo(() => {
    return [...filteredAssignments].sort((a, b) => {
      let result = 0
      if (sortField === 'assignedAt') {
        const tA = new Date(a.assignedAt).getTime() || 0
        const tB = new Date(b.assignedAt).getTime() || 0
        result = tA - tB
      } else if (sortField === 'duration') {
        const dA = getAssignmentDuration(a).seconds ?? 0
        const dB = getAssignmentDuration(b).seconds ?? 0
        result = dA - dB
      } else if (sortField === 'priority') {
        const pA = PRIORITY_ORDER[(a.priority ?? '').toUpperCase()] ?? 0
        const pB = PRIORITY_ORDER[(b.priority ?? '').toUpperCase()] ?? 0
        result = pA - pB
      } else if (sortField === 'status') {
        result = a.status.localeCompare(b.status)
      }
      return sortOrder === 'asc' ? result : -result
    })
  }, [filteredAssignments, sortField, sortOrder])

  // Pagination Logic
  const totalItems = sortedAssignments.length
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize))
  const paginatedAssignments = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return sortedAssignments.slice(start, start + pageSize)
  }, [sortedAssignments, currentPage, pageSize])

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortOrder('desc')
    }
  }

  const isFiltered =
    search.trim() !== '' ||
    statusFilter !== 'ALL' ||
    priorityFilter !== 'ALL' ||
    datePreset !== 'all'

  const clearFilters = () => {
    setSearch('')
    setStatusFilter('ALL')
    setPriorityFilter('ALL')
    setDatePreset('all')
    setCurrentPage(1)
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <History className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
                {title}
              </h1>
              <p className="text-sm text-muted-foreground">{subtitle}</p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => void loadAssignments(true)}
            disabled={refreshing || loading}
            className="h-9 gap-1.5"
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </Button>
        </div>
      </div>

      {/* Error Alert */}
      {error ? (
        <Card className="border-destructive/30 bg-destructive/5 p-4 text-destructive">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="font-semibold text-sm">Failed to synchronize response records</p>
              <p className="text-xs opacity-90">{error}</p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => void loadAssignments()}
                className="mt-2 h-7 text-xs bg-card text-foreground"
              >
                Try again
              </Button>
            </div>
          </div>
        </Card>
      ) : null}

      {/* Summary KPI Metric Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 sm:gap-4">
        <Card className="border border-border bg-card p-4 shadow-xs">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Total Responses
          </p>
          <p className="mt-1 font-mono text-2xl font-bold text-foreground">
            {loading ? '—' : metrics.total}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">Recorded dispatch events</p>
        </Card>

        <Card className="border border-border bg-card p-4 shadow-xs">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Completed
          </p>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="font-mono text-2xl font-bold text-emerald-600 dark:text-emerald-400">
              {loading ? '—' : metrics.completed}
            </span>
            <span className="text-xs font-semibold text-emerald-600/80">
              ({metrics.completedRate}%)
            </span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">Resolved on-scene</p>
        </Card>

        <Card className="border border-border bg-card p-4 shadow-xs">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Declined
          </p>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="font-mono text-2xl font-bold text-rose-600 dark:text-rose-400">
              {loading ? '—' : metrics.declined}
            </span>
            <span className="text-xs font-semibold text-rose-600/80">
              ({metrics.declinedRate}%)
            </span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">Reassigned / rejected</p>
        </Card>

        <Card className="border border-border bg-card p-4 shadow-xs">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Avg. Response Time
          </p>
          <p className="mt-1 font-mono text-2xl font-bold text-primary">
            {loading ? '—' : metrics.avgResponseTime}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">Dispatch to scene arrival</p>
        </Card>
      </div>

      {/* Toolbar: Search + Faceted Filters */}
      <Card className="border border-border bg-card p-4 shadow-xs space-y-3">
        <div className="grid gap-3 md:grid-cols-[1fr_10rem_10rem_9rem]">
          <div className="relative">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                setCurrentPage(1)
              }}
              placeholder="Search incident, location, responder, notes..."
              className="pl-9 h-9 text-sm"
              aria-label="Search response records"
            />
          </div>

          <Select
            value={statusFilter}
            onValueChange={(val) => {
              setStatusFilter(val)
              setCurrentPage(1)
            }}
          >
            <SelectTrigger className="h-9 text-sm" aria-label="Filter by Status">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All Statuses</SelectItem>
              <SelectItem value="RESOLVED">Resolved</SelectItem>
              <SelectItem value="ARRIVED">Arrived on Scene</SelectItem>
              <SelectItem value="EN_ROUTE">En Route</SelectItem>
              <SelectItem value="RESPONDING">Responding</SelectItem>
              <SelectItem value="ASSIGNED">Assigned</SelectItem>
              <SelectItem value="DECLINED">Declined</SelectItem>
              <SelectItem value="CANCELLED">Cancelled</SelectItem>
            </SelectContent>
          </Select>

          <Select
            value={priorityFilter}
            onValueChange={(val) => {
              setPriorityFilter(val)
              setCurrentPage(1)
            }}
          >
            <SelectTrigger className="h-9 text-sm" aria-label="Filter by Priority">
              <SelectValue placeholder="Priority" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All Priorities</SelectItem>
              <SelectItem value="CRITICAL">Critical</SelectItem>
              <SelectItem value="HIGH">High</SelectItem>
              <SelectItem value="MEDIUM">Medium</SelectItem>
              <SelectItem value="LOW">Low</SelectItem>
            </SelectContent>
          </Select>

          <Select
            value={datePreset}
            onValueChange={(val) => {
              setDatePreset(val as DatePreset)
              setCurrentPage(1)
            }}
          >
            <SelectTrigger className="h-9 text-sm" aria-label="Filter by Date">
              <SelectValue placeholder="Date Range" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Time</SelectItem>
              <SelectItem value="today">Today</SelectItem>
              <SelectItem value="last7">Last 7 Days</SelectItem>
              <SelectItem value="last30">Last 30 Days</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Active Filter Chips Bar */}
        {isFiltered ? (
          <div className="flex flex-wrap items-center gap-2 pt-1 text-xs border-t border-border/50">
            <span className="text-muted-foreground font-medium">Active filters:</span>
            {search.trim() ? (
              <Badge variant="secondary" className="gap-1 font-normal">
                Search: &quot;{search.trim()}&quot;
                <button
                  type="button"
                  onClick={() => setSearch('')}
                  aria-label="Remove search filter"
                >
                  <X className="h-3 w-3 hover:text-foreground" />
                </button>
              </Badge>
            ) : null}
            {statusFilter !== 'ALL' ? (
              <Badge variant="secondary" className="gap-1 font-normal">
                Status: {statusFilter}
                <button
                  type="button"
                  onClick={() => setStatusFilter('ALL')}
                  aria-label="Remove status filter"
                >
                  <X className="h-3 w-3 hover:text-foreground" />
                </button>
              </Badge>
            ) : null}
            {priorityFilter !== 'ALL' ? (
              <Badge variant="secondary" className="gap-1 font-normal">
                Priority: {priorityFilter}
                <button
                  type="button"
                  onClick={() => setPriorityFilter('ALL')}
                  aria-label="Remove priority filter"
                >
                  <X className="h-3 w-3 hover:text-foreground" />
                </button>
              </Badge>
            ) : null}
            {datePreset !== 'all' ? (
              <Badge variant="secondary" className="gap-1 font-normal">
                Range: {datePreset === 'today' ? 'Today' : datePreset === 'last7' ? 'Last 7 Days' : 'Last 30 Days'}
                <button
                  type="button"
                  onClick={() => setDatePreset('all')}
                  aria-label="Remove date range filter"
                >
                  <X className="h-3 w-3 hover:text-foreground" />
                </button>
              </Badge>
            ) : null}
            <Button
              variant="ghost"
              size="sm"
              onClick={clearFilters}
              className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground"
            >
              Reset all
            </Button>
          </div>
        ) : null}
      </Card>

      {/* Result Status Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between text-xs text-muted-foreground">
        <div>
          Showing{' '}
          <span className="font-semibold text-foreground">
            {totalItems === 0 ? 0 : (currentPage - 1) * pageSize + 1}–
            {Math.min(currentPage * pageSize, totalItems)}
          </span>{' '}
          of <span className="font-semibold text-foreground">{totalItems}</span> responses
        </div>
        <div className="flex items-center gap-2">
          <span>Sort by:</span>
          <Select
            value={sortField}
            onValueChange={(v) => {
              setSortField(v as SortField)
              setCurrentPage(1)
            }}
          >
            <SelectTrigger className="h-7 w-36 text-xs bg-background">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="assignedAt">Assigned Time</SelectItem>
              <SelectItem value="duration">Response Time</SelectItem>
              <SelectItem value="priority">Priority</SelectItem>
              <SelectItem value="status">Status</SelectItem>
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setSortOrder((p) => (p === 'asc' ? 'desc' : 'asc'))}
            className="h-7 w-7 p-0"
            aria-label={`Toggle sort direction, currently ${sortOrder}`}
          >
            <ArrowUpDown className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* Desktop Data Table / Mobile Card Switcher */}
      <div className="space-y-4">
        {loading && assignments.length === 0 ? (
          <div className="space-y-2">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="h-16 w-full animate-pulse rounded-lg border border-border bg-card"
              />
            ))}
          </div>
        ) : totalItems === 0 ? (
          <Card className="border border-border bg-card p-12 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
              {isFiltered ? <FilterX className="h-6 w-6" /> : <History className="h-6 w-6" />}
            </div>
            <h3 className="mt-4 text-base font-semibold text-foreground">
              {isFiltered ? 'No matching response records' : 'No response history recorded yet'}
            </h3>
            <p className="mt-1 text-sm text-muted-foreground max-w-sm mx-auto">
              {isFiltered
                ? 'Try adjusting your search terms, status, or date range filters to find past dispatches.'
                : 'When dispatchers assign emergency units and responses are completed or declined, history logs appear here automatically.'}
            </p>
            {isFiltered ? (
              <Button
                variant="outline"
                size="sm"
                onClick={clearFilters}
                className="mt-4 gap-1.5"
              >
                Clear all filters
              </Button>
            ) : null}
          </Card>
        ) : (
          <>
            {/* DESKTOP TABLE VIEW (Hidden on mobile < md) */}
            <div className="hidden md:block rounded-lg border border-border bg-card shadow-xs overflow-hidden">
              <table
                className="w-full text-left text-sm"
                aria-label="Incident response history table"
              >
                <thead className="border-b border-border bg-muted/40 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  <tr>
                    <th scope="col" className="py-3 pl-4 pr-3">
                      Incident
                    </th>
                    <th scope="col" className="px-3 py-3">
                      Type
                    </th>
                    <th
                      scope="col"
                      className="px-3 py-3 cursor-pointer hover:text-foreground"
                      onClick={() => handleSort('priority')}
                    >
                      <div className="flex items-center gap-1">
                        <span>Priority</span>
                        {sortField === 'priority' ? (
                          sortOrder === 'asc' ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />
                        ) : null}
                      </div>
                    </th>
                    <th
                      scope="col"
                      className="px-3 py-3 cursor-pointer hover:text-foreground"
                      onClick={() => handleSort('status')}
                    >
                      <div className="flex items-center gap-1">
                        <span>Status</span>
                        {sortField === 'status' ? (
                          sortOrder === 'asc' ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />
                        ) : null}
                      </div>
                    </th>
                    <th scope="col" className="px-3 py-3">
                      Responder
                    </th>
                    <th
                      scope="col"
                      className="px-3 py-3 cursor-pointer hover:text-foreground"
                      onClick={() => handleSort('assignedAt')}
                    >
                      <div className="flex items-center gap-1">
                        <span>Assigned</span>
                        {sortField === 'assignedAt' ? (
                          sortOrder === 'asc' ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />
                        ) : null}
                      </div>
                    </th>
                    <th
                      scope="col"
                      className="px-3 py-3 text-right cursor-pointer hover:text-foreground"
                      onClick={() => handleSort('duration')}
                    >
                      <div className="flex items-center justify-end gap-1">
                        <span>Response Time</span>
                        {sortField === 'duration' ? (
                          sortOrder === 'asc' ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />
                        ) : null}
                      </div>
                    </th>
                    <th scope="col" className="py-3 pl-3 pr-4 text-center w-12">
                      <span className="sr-only">Details</span>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {paginatedAssignments.map((item) => {
                    const isExpanded = expandedRows.has(item.id)
                    const durationInfo = getAssignmentDuration(item)
                    const incidentToken = formatIncidentToken(item.incidentId)

                    return (
                      <RowGroup
                        key={item.id}
                        item={item}
                        incidentToken={incidentToken}
                        durationInfo={durationInfo}
                        isExpanded={isExpanded}
                        showTech={Boolean(showTechnical[item.id])}
                        onToggleExpand={() => toggleRow(item.id)}
                        onToggleTech={() => toggleTechnical(item.id)}
                        onCopy={copyToClipboard}
                      />
                    )
                  })}
                </tbody>
              </table>
            </div>

            {/* MOBILE STACKED CARDS VIEW (Hidden on md+) */}
            <div className="space-y-3 md:hidden">
              {paginatedAssignments.map((item) => {
                const isExpanded = expandedRows.has(item.id)
                const durationInfo = getAssignmentDuration(item)
                const incidentToken = formatIncidentToken(item.incidentId)

                return (
                  <MobileResponseCard
                    key={item.id}
                    item={item}
                    incidentToken={incidentToken}
                    durationInfo={durationInfo}
                    isExpanded={isExpanded}
                    showTech={Boolean(showTechnical[item.id])}
                    onToggleExpand={() => toggleRow(item.id)}
                    onToggleTech={() => toggleTechnical(item.id)}
                    onCopy={copyToClipboard}
                  />
                )
              })}
            </div>

            {/* Pagination Controls */}
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between pt-2">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span>Rows per page:</span>
                <Select
                  value={String(pageSize)}
                  onValueChange={(v) => {
                    setPageSize(Number(v))
                    setCurrentPage(1)
                  }}
                >
                  <SelectTrigger className="h-8 w-16 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="10">10</SelectItem>
                    <SelectItem value="25">25</SelectItem>
                    <SelectItem value="50">50</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center justify-between sm:justify-end gap-2">
                <span className="text-xs text-muted-foreground mr-2">
                  Page {currentPage} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage <= 1}
                  className="h-8 px-3 text-xs"
                >
                  Previous
                </Button>
                <div className="flex items-center gap-1">
                  {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                    let pageNum = i + 1
                    if (totalPages > 5 && currentPage > 3) {
                      pageNum = currentPage - 2 + i
                      if (pageNum > totalPages) pageNum = totalPages - (4 - i)
                    }
                    return (
                      <Button
                        key={pageNum}
                        variant={currentPage === pageNum ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => setCurrentPage(pageNum)}
                        className="h-8 w-8 p-0 text-xs"
                      >
                        {pageNum}
                      </Button>
                    )
                  })}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage >= totalPages}
                  className="h-8 px-3 text-xs"
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

// Subcomponent: Desktop Table Row & Expandable Panel
function RowGroup({
  item,
  incidentToken,
  durationInfo,
  isExpanded,
  showTech,
  onToggleExpand,
  onToggleTech,
  onCopy,
}: {
  item: OperationalAssignment
  incidentToken: string
  durationInfo: { seconds: number | null; label: string }
  isExpanded: boolean
  showTech: boolean
  onToggleExpand: () => void
  onToggleTech: () => void
  onCopy: (text: string, label: string) => void
}) {
  return (
    <>
      <tr
        onClick={onToggleExpand}
        className={`cursor-pointer transition-colors hover:bg-muted/40 ${
          isExpanded ? 'bg-muted/30 font-medium' : ''
        }`}
      >
        <td className="py-3.5 pl-4 pr-3">
          <div className="font-semibold text-foreground flex items-center gap-1.5">
            <span>{incidentToken}</span>
          </div>
          <div className="flex items-center gap-1 text-xs text-muted-foreground mt-0.5 max-w-xs truncate">
            <MapPin className="h-3 w-3 shrink-0 text-primary" />
            <span className="truncate">{item.location || 'Location Unspecified'}</span>
          </div>
        </td>

        <td className="px-3 py-3.5">
          <span className="text-xs text-foreground font-medium">
            {item.incidentType || 'Vehicle Collision'}
          </span>
        </td>

        <td className="px-3 py-3.5">
          <PriorityBadge priority={item.priority} />
        </td>

        <td className="px-3 py-3.5">
          <StatusBadge status={item.status} />
        </td>

        <td className="px-3 py-3.5">
          <div className="text-xs font-medium text-foreground">
            {item.responderId ? `Unit ${item.responderId.slice(0, 8)}` : 'Assigned Unit'}
          </div>
          <div className="text-[11px] text-muted-foreground">
            via {item.dispatcherName || 'Central Operations'}
          </div>
        </td>

        <td className="px-3 py-3.5">
          <div className="font-mono text-xs text-foreground">
            {formatDate(item.assignedAt)}
          </div>
          <div className="text-[11px] text-muted-foreground">
            {formatTime(item.assignedAt)}
          </div>
        </td>

        <td className="px-3 py-3.5 text-right">
          <span className="font-mono text-xs font-semibold text-foreground">
            {durationInfo.label}
          </span>
        </td>

        <td className="py-3.5 pl-3 pr-4 text-center">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            aria-expanded={isExpanded}
            aria-label={`${isExpanded ? 'Collapse' : 'Expand'} response details`}
          >
            {isExpanded ? (
              <ChevronUp className="h-4 w-4 text-primary" />
            ) : (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            )}
          </Button>
        </td>
      </tr>

      {/* Expanded Row Panel */}
      {isExpanded ? (
        <tr className="bg-muted/15 border-b border-border">
          <td colSpan={8} className="p-0">
            <div className="p-5 space-y-4">
              {/* Decline Reason Banner */}
              {item.status === 'DECLINED' && (
                <div className="rounded-md border border-rose-200 bg-rose-50/80 dark:border-rose-950 dark:bg-rose-950/40 p-3.5 text-xs text-rose-900 dark:text-rose-200">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="h-4 w-4 shrink-0 text-rose-600 mt-0.5" />
                    <div>
                      <span className="font-bold">ASSIGNMENT DECLINED: </span>
                      <span>{item.declineReason || 'Responder indicated unit was unavailable.'}</span>
                      <p className="mt-1 text-[11px] text-rose-700/80 dark:text-rose-300/80">
                        Operational action: Incident returned to dispatcher queue for immediate reassignment.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Connected Milestone Timeline */}
              <div className="rounded-lg border border-border/70 bg-card p-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3 flex items-center gap-1.5">
                  <Clock className="h-3.5 w-3.5 text-primary" />
                  Response Progression Timeline
                </p>
                <ResponseTimeline item={item} />
              </div>

              {/* Operational Details Grid */}
              <div className="grid gap-3 text-xs sm:grid-cols-3">
                <div className="rounded-lg border border-border/60 bg-card p-3 space-y-1">
                  <span className="text-muted-foreground font-medium">Dispatcher Attribution</span>
                  <p className="font-semibold text-foreground">
                    {item.dispatcherName || 'Central Operations'}
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    Assigned: {formatMilestoneTime(item.assignedAt)}
                  </p>
                </div>

                <div className="rounded-lg border border-border/60 bg-card p-3 space-y-1">
                  <span className="text-muted-foreground font-medium">Scene Resolution</span>
                  <p className="font-semibold text-foreground">
                    {item.outcome || (item.status === 'RESOLVED' ? 'Incident cleared' : 'In progress')}
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    Status: {item.status}
                  </p>
                </div>

                <div className="rounded-lg border border-border/60 bg-card p-3 space-y-1">
                  <span className="text-muted-foreground font-medium">Geographic Location</span>
                  <p className="font-semibold text-foreground truncate">
                    {item.location || 'Coordinates logged'}
                  </p>
                  {item.latitude && item.longitude ? (
                    <p className="font-mono text-[11px] text-muted-foreground">
                      {item.latitude.toFixed(4)}° N, {item.longitude.toFixed(4)}° E
                    </p>
                  ) : (
                    <p className="text-[11px] text-muted-foreground">Camera feed zone</p>
                  )}
                </div>
              </div>

              {/* Responder Notes */}
              {item.responseNotes ? (
                <div className="rounded-md border border-border bg-card p-3 text-xs">
                  <span className="font-semibold text-muted-foreground">Responder Notes: </span>
                  <span className="text-foreground">{item.responseNotes}</span>
                </div>
              ) : null}

              {/* Technical Audit Identifiers (Collapsible) */}
              <div className="border-t border-border/60 pt-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation()
                    onToggleTech()
                  }}
                  className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground gap-1"
                >
                  <Layers className="h-3.5 w-3.5" />
                  <span>Technical Audit Identifiers</span>
                  {showTech ? (
                    <ChevronUp className="h-3 w-3 ml-1" />
                  ) : (
                    <ChevronDown className="h-3 w-3 ml-1" />
                  )}
                </Button>

                {showTech ? (
                  <div className="mt-2 grid gap-2 rounded-md bg-muted/40 p-3 text-xs font-mono sm:grid-cols-2">
                    <div className="flex items-center justify-between gap-2 border-b border-border/40 pb-1 sm:border-b-0 sm:pb-0">
                      <div>
                        <span className="text-[10px] uppercase text-muted-foreground block">
                          Assignment ID
                        </span>
                        <span className="text-foreground select-all">{item.id}</span>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation()
                          onCopy(item.id, 'Assignment ID')
                        }}
                        className="h-6 w-6 p-0"
                        title="Copy Assignment ID"
                      >
                        <Copy className="h-3 w-3 text-muted-foreground" />
                      </Button>
                    </div>

                    <div className="flex items-center justify-between gap-2">
                      <div>
                        <span className="text-[10px] uppercase text-muted-foreground block">
                          Incident UUID
                        </span>
                        <span className="text-foreground select-all">{item.incidentId}</span>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation()
                          onCopy(item.incidentId, 'Incident UUID')
                        }}
                        className="h-6 w-6 p-0"
                        title="Copy Incident UUID"
                      >
                        <Copy className="h-3 w-3 text-muted-foreground" />
                      </Button>
                    </div>

                    {item.responderId ? (
                      <div className="flex items-center justify-between gap-2">
                        <div>
                          <span className="text-[10px] uppercase text-muted-foreground block">
                            Responder UUID
                          </span>
                          <span className="text-foreground select-all">{item.responderId}</span>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation()
                            onCopy(item.responderId, 'Responder ID')
                          }}
                          className="h-6 w-6 p-0"
                          title="Copy Responder ID"
                        >
                          <Copy className="h-3 w-3 text-muted-foreground" />
                        </Button>
                      </div>
                    ) : null}

                    {item.updatedAt ? (
                      <div>
                        <span className="text-[10px] uppercase text-muted-foreground block">
                          Last Database Sync
                        </span>
                        <span className="text-muted-foreground">{item.updatedAt}</span>
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </div>
          </td>
        </tr>
      ) : null}
    </>
  )
}

// Subcomponent: Mobile Card View
function MobileResponseCard({
  item,
  incidentToken,
  durationInfo,
  isExpanded,
  showTech,
  onToggleExpand,
  onToggleTech,
  onCopy,
}: {
  item: OperationalAssignment
  incidentToken: string
  durationInfo: { seconds: number | null; label: string }
  isExpanded: boolean
  showTech: boolean
  onToggleExpand: () => void
  onToggleTech: () => void
  onCopy: (text: string, label: string) => void
}) {
  return (
    <Card className="border border-border bg-card p-4 shadow-xs">
      <div className="flex items-start justify-between gap-2 border-b border-border/50 pb-2.5">
        <div>
          <span className="font-bold text-base text-foreground">{incidentToken}</span>
          <p className="text-xs text-muted-foreground mt-0.5 flex items-center gap-1">
            <MapPin className="h-3 w-3 text-primary shrink-0" />
            <span className="truncate">{item.location || 'Location Unspecified'}</span>
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <StatusBadge status={item.status} />
          <PriorityBadge priority={item.priority} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 py-3 text-xs">
        <div>
          <span className="text-muted-foreground block text-[11px]">Assigned</span>
          <span className="font-mono text-foreground">{formatDate(item.assignedAt)}</span>
          <span className="text-[11px] text-muted-foreground block">
            {formatTime(item.assignedAt)}
          </span>
        </div>
        <div>
          <span className="text-muted-foreground block text-[11px]">Response Time</span>
          <span className="font-mono font-semibold text-foreground">{durationInfo.label}</span>
        </div>
        <div className="col-span-2">
          <span className="text-muted-foreground text-[11px]">Responder: </span>
          <span className="font-medium text-foreground">
            {item.responderId ? `Unit ${item.responderId.slice(0, 8)}` : 'Assigned Unit'}
          </span>
          <span className="text-muted-foreground text-[11px]">
            {' '}
            (via {item.dispatcherName || 'Central'})
          </span>
        </div>
      </div>

      <Button
        variant="outline"
        size="sm"
        onClick={onToggleExpand}
        className="w-full h-8 text-xs justify-between"
      >
        <span>{isExpanded ? 'Hide Details' : 'View Timeline & Details'}</span>
        {isExpanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
      </Button>

      {isExpanded ? (
        <div className="mt-3 space-y-3 pt-3 border-t border-border/60 text-xs">
          {item.status === 'DECLINED' && (
            <div className="rounded-md border border-rose-200 bg-rose-50 p-2.5 text-rose-900 dark:bg-rose-950/40 dark:text-rose-200">
              <span className="font-bold">DECLINED: </span>
              {item.declineReason || 'Responder unavailable'}
            </div>
          )}

          <div className="rounded-lg border border-border/70 bg-muted/20 p-3">
            <p className="text-[11px] font-semibold uppercase text-muted-foreground mb-2">
              Timeline
            </p>
            <ResponseTimeline item={item} />
          </div>

          {item.responseNotes ? (
            <div className="rounded-md border border-border bg-muted/20 p-2.5">
              <span className="font-semibold text-muted-foreground">Notes: </span>
              <span>{item.responseNotes}</span>
            </div>
          ) : null}

          {/* Collapsible Tech IDs on Mobile */}
          <div className="pt-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={onToggleTech}
              className="h-6 px-1 text-xs text-muted-foreground"
            >
              <span>{showTech ? 'Hide Technical IDs' : 'Show Technical IDs'}</span>
            </Button>
            {showTech ? (
              <div className="mt-2 space-y-1.5 rounded-md bg-muted/50 p-2 text-[11px] font-mono">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground truncate">ID: {item.id.slice(0, 16)}…</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onCopy(item.id, 'Assignment ID')}
                    className="h-5 px-1 text-[10px]"
                  >
                    Copy
                  </Button>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground truncate">INC: {item.incidentId.slice(0, 16)}…</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onCopy(item.incidentId, 'Incident UUID')}
                    className="h-5 px-1 text-[10px]"
                  >
                    Copy
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </Card>
  )
}

// Subcomponent: Response Timeline Stepper
function ResponseTimeline({ item }: { item: OperationalAssignment }) {
  const isDeclined = item.status === 'DECLINED'

  const stages = [
    {
      key: 'assigned',
      label: 'Assigned',
      time: item.assignedAt,
      actor: 'Dispatcher',
      active: true,
      success: true,
    },
    {
      key: 'accepted',
      label: isDeclined ? 'Declined' : 'Accepted',
      time: isDeclined ? item.declinedAt : item.acceptedAt,
      actor: 'Responder',
      active: Boolean(isDeclined ? item.declinedAt : item.acceptedAt),
      success: !isDeclined,
      failed: isDeclined,
    },
    {
      key: 'enroute',
      label: 'En Route',
      time: item.enRouteAt,
      actor: 'Unit Transit',
      active: Boolean(item.enRouteAt),
      success: true,
      skipped: isDeclined,
    },
    {
      key: 'arrived',
      label: 'Arrived',
      time: item.arrivedAt,
      actor: 'On Scene',
      active: Boolean(item.arrivedAt),
      success: true,
      skipped: isDeclined,
    },
    {
      key: 'resolved',
      label: 'Resolved',
      time: item.resolvedAt,
      actor: 'Closed',
      active: Boolean(item.resolvedAt),
      success: true,
      skipped: isDeclined,
    },
  ]

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-5 sm:gap-2">
      {stages.map((st, idx) => {
        let circleClass = 'border-border bg-muted text-muted-foreground'
        if (st.failed) {
          circleClass = 'border-rose-500 bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300'
        } else if (st.active && st.success) {
          circleClass = 'border-emerald-500 bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
        } else if (st.skipped) {
          circleClass = 'border-border/40 bg-muted/20 text-muted-foreground/40'
        }

        return (
          <div key={st.key} className="flex sm:flex-col items-start gap-2.5 sm:gap-1.5 relative">
            <div className="flex items-center gap-2">
              <div
                className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-semibold ${circleClass}`}
              >
                {st.failed ? (
                  <X className="h-3.5 w-3.5" />
                ) : st.active ? (
                  <Check className="h-3.5 w-3.5" />
                ) : (
                  <span>{idx + 1}</span>
                )}
              </div>
              <span
                className={`text-xs font-semibold sm:hidden ${
                  st.failed
                    ? 'text-rose-600'
                    : st.active
                    ? 'text-foreground'
                    : 'text-muted-foreground/60'
                }`}
              >
                {st.label}
              </span>
            </div>

            <div className="min-w-0 flex-1">
              <span
                className={`hidden sm:block text-xs font-semibold ${
                  st.failed
                    ? 'text-rose-600'
                    : st.active
                    ? 'text-foreground'
                    : 'text-muted-foreground/60'
                }`}
              >
                {st.label}
              </span>
              <p className="font-mono text-[11px] text-muted-foreground">
                {st.time ? formatMilestoneTime(st.time) : '—'}
              </p>
              <p className="text-[10px] text-muted-foreground/80">{st.actor}</p>
            </div>
          </div>
        )
      })}
    </div>
  )
}

// Subcomponent: Restrained Status Badge
function StatusBadge({ status }: { status: string }) {
  const norm = (status || '').toUpperCase()

  if (norm === 'RESOLVED') {
    return (
      <Badge
        variant="outline"
        className="gap-1 bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800 text-[11px] font-semibold"
      >
        <CheckCircle2 className="h-3 w-3" />
        Resolved
      </Badge>
    )
  }
  if (norm === 'ARRIVED') {
    return (
      <Badge
        variant="outline"
        className="gap-1 bg-teal-50 text-teal-700 border-teal-200 dark:bg-teal-950/40 dark:text-teal-300 dark:border-teal-800 text-[11px] font-semibold"
      >
        <MapPin className="h-3 w-3" />
        Arrived
      </Badge>
    )
  }
  if (norm === 'EN_ROUTE') {
    return (
      <Badge
        variant="outline"
        className="gap-1 bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800 text-[11px] font-semibold"
      >
        <Navigation className="h-3 w-3" />
        En Route
      </Badge>
    )
  }
  if (norm === 'RESPONDING') {
    return (
      <Badge
        variant="outline"
        className="gap-1 bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/40 dark:text-indigo-300 dark:border-indigo-800 text-[11px] font-semibold"
      >
        <ActivityIcon className="h-3 w-3" />
        Responding
      </Badge>
    )
  }
  if (norm === 'ASSIGNED') {
    return (
      <Badge
        variant="outline"
        className="gap-1 bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800 text-[11px] font-semibold"
      >
        <Clock className="h-3 w-3" />
        Assigned
      </Badge>
    )
  }
  if (norm === 'DECLINED') {
    return (
      <Badge
        variant="outline"
        className="gap-1 bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800 text-[11px] font-semibold"
      >
        <XCircle className="h-3 w-3" />
        Declined
      </Badge>
    )
  }
  if (norm === 'CANCELLED') {
    return (
      <Badge
        variant="outline"
        className="gap-1 bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-900 dark:text-slate-300 dark:border-slate-800 text-[11px] font-semibold"
      >
        <Ban className="h-3 w-3" />
        Cancelled
      </Badge>
    )
  }
  return (
    <Badge variant="outline" className="text-[11px] font-normal">
      {status}
    </Badge>
  )
}

function ActivityIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      {...props}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
    </svg>
  )
}

// Subcomponent: Restrained Priority Badge
function PriorityBadge({ priority }: { priority?: string | null }) {
  const norm = (priority || '').toUpperCase()

  if (norm === 'CRITICAL') {
    return (
      <Badge
        variant="outline"
        className="gap-1 bg-red-50 text-red-700 border-red-200 dark:bg-red-950/40 dark:text-red-300 dark:border-red-800 text-[11px] font-bold"
      >
        <AlertTriangle className="h-3 w-3" />
        CRITICAL
      </Badge>
    )
  }
  if (norm === 'HIGH') {
    return (
      <Badge
        variant="outline"
        className="gap-1 bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-950/40 dark:text-orange-300 dark:border-orange-800 text-[11px] font-semibold"
      >
        <ChevronUp className="h-3 w-3" />
        HIGH
      </Badge>
    )
  }
  if (norm === 'MEDIUM') {
    return (
      <Badge
        variant="outline"
        className="gap-1 bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800 text-[11px] font-medium"
      >
        <Minus className="h-3 w-3" />
        MEDIUM
      </Badge>
    )
  }
  if (norm === 'LOW') {
    return (
      <Badge
        variant="outline"
        className="gap-1 bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-900 dark:text-slate-400 dark:border-slate-800 text-[11px] font-normal"
      >
        <ChevronDown className="h-3 w-3" />
        LOW
      </Badge>
    )
  }
  return (
    <span className="text-xs text-muted-foreground font-mono">
      {priority || '—'}
    </span>
  )
}
