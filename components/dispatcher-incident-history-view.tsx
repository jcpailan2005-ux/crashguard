'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertCircle,
  AlertOctagon,
  AlertTriangle,
  ArrowUpDown,
  Ban,
  Calendar,
  Camera,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Clock,
  Copy,
  ExternalLink,
  Eye,
  Filter,
  FilterX,
  History,
  Layers,
  MapPin,
  Navigation,
  RefreshCw,
  Search,
  ShieldAlert,
  Sparkles,
  Timer,
  User,
  UserCheck,
  X,
} from 'lucide-react'

import { phase3, type OperationalIncident } from '@/lib/phase3-api'
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
type SortField = 'detectedAt' | 'duration' | 'priority' | 'state' | 'aiScore'
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

function getIncidentDuration(item: OperationalIncident): {
  seconds: number | null
  label: string
} {
  const isFalseAlarm = item.state === 'FALSE_ALARM' || item.reviewStatus === 'FALSE_ALARM'
  if (isFalseAlarm && item.reviewedAt) {
    const s = getDurationSeconds(item.detectedAt, item.reviewedAt)
    return {
      seconds: s,
      label: s !== null ? `${formatDurationSeconds(s)} (Dismissed)` : 'Dismissed',
    }
  }

  if (item.resolvedAt) {
    const s = getDurationSeconds(item.detectedAt, item.resolvedAt)
    return {
      seconds: s,
      label: s !== null ? formatDurationSeconds(s) : 'Resolved',
    }
  }

  if (item.arrivedAt) {
    const s = getDurationSeconds(item.detectedAt, item.arrivedAt)
    return {
      seconds: s,
      label: s !== null ? `${formatDurationSeconds(s)} (On scene)` : 'On scene',
    }
  }

  if (item.assignedAt) {
    return { seconds: null, label: 'In response' }
  }

  if (item.state === 'PENDING_REVIEW' || item.reviewStatus === 'PENDING_REVIEW') {
    return { seconds: null, label: 'Awaiting review' }
  }

  return { seconds: null, label: 'Active' }
}

const PRIORITY_ORDER: Record<string, number> = {
  CRITICAL: 4,
  HIGH: 3,
  MEDIUM: 2,
  LOW: 1,
}

export function DispatcherIncidentHistoryView({
  title = 'Incident History Ledger',
  subtitle = 'Authoritative operational record of detected vehicle collisions, review decisions, and emergency response resolutions.',
}: {
  title?: string
  subtitle?: string
}) {
  const { toast } = useToast()
  const [incidents, setIncidents] = useState<OperationalIncident[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')

  // Filters
  const [search, setSearch] = useState('')
  const [stateFilter, setStateFilter] = useState('ALL')
  const [priorityFilter, setPriorityFilter] = useState('ALL')
  const [detectionModeFilter, setDetectionModeFilter] = useState('ALL')
  const [datePreset, setDatePreset] = useState<DatePreset>('all')

  // Sorting & Pagination
  const [sortField, setSortField] = useState<SortField>('detectedAt')
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc')
  const [pageSize, setPageSize] = useState<number>(10)
  const [currentPage, setCurrentPage] = useState<number>(1)

  // Expanded Rows (set of incident IDs)
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())

  // Technical Accordion inside expansion
  const [showTechnical, setShowTechnical] = useState<Record<string, boolean>>({})

  const loadIncidents = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) setRefreshing(true)
    else setLoading(true)
    setError('')
    try {
      const res = await phase3.incidents()
      setIncidents(res.incidents ?? [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to synchronize incident audit history.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    void loadIncidents()
  }, [loadIncidents])

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
        description: `${label}: ${text.slice(0, 18)}...`,
      })
    } catch {
      toast({
        title: 'Unable to copy',
        description: 'Clipboard access was blocked by the browser.',
        variant: 'destructive',
      })
    }
  }

  // Summary Metrics
  const metrics = useMemo(() => {
    const total = incidents.length
    const resolved = incidents.filter(
      (i) => i.state === 'RESOLVED' || i.state === 'CLOSED' || Boolean(i.resolvedAt)
    ).length
    const falseAlarms = incidents.filter(
      (i) => i.state === 'FALSE_ALARM' || i.reviewStatus === 'FALSE_ALARM'
    ).length

    let totalResolutionSec = 0
    let resolutionCount = 0

    for (const inc of incidents) {
      if (inc.resolvedAt && inc.detectedAt) {
        const sec = getDurationSeconds(inc.detectedAt, inc.resolvedAt)
        if (sec !== null && sec > 0) {
          totalResolutionSec += sec
          resolutionCount++
        }
      }
    }

    const avgSec = resolutionCount > 0 ? Math.round(totalResolutionSec / resolutionCount) : null

    return {
      total,
      resolved,
      resolvedRate: total > 0 ? Math.round((resolved / total) * 100) : 0,
      falseAlarms,
      falseAlarmRate: total > 0 ? Math.round((falseAlarms / total) * 100) : 0,
      avgResolutionTime: formatDurationSeconds(avgSec),
    }
  }, [incidents])

  // Filter Logic
  const filteredIncidents = useMemo(() => {
    const now = Date.now()
    const query = search.trim().toLowerCase()

    return incidents.filter((item) => {
      // Search
      if (query) {
        const token = formatIncidentToken(item.id).toLowerCase()
        const location = (item.location ?? '').toLowerCase()
        const type = (item.incidentType ?? '').toLowerCase()
        const state = (item.state ?? '').toLowerCase()
        const priority = (item.priority ?? '').toLowerCase()
        const reviewer = (item.reviewedBy ?? '').toLowerCase()
        const responder = (item.responderName ?? item.responderId ?? '').toLowerCase()
        const reason = (item.falseAlarmReason ?? '').toLowerCase()
        const notes = (item.dispatcherNotes ?? '').toLowerCase()

        const matches =
          token.includes(query) ||
          location.includes(query) ||
          type.includes(query) ||
          state.includes(query) ||
          priority.includes(query) ||
          reviewer.includes(query) ||
          responder.includes(query) ||
          reason.includes(query) ||
          notes.includes(query)

        if (!matches) return false
      }

      // State Filter
      if (stateFilter !== 'ALL') {
        if (stateFilter === 'RESOLVED') {
          if (item.state !== 'RESOLVED' && item.state !== 'CLOSED' && !item.resolvedAt) return false
        } else if (stateFilter === 'FALSE_ALARM') {
          if (item.state !== 'FALSE_ALARM' && item.reviewStatus !== 'FALSE_ALARM') return false
        } else if (stateFilter === 'ACTIVE') {
          const isResolved = item.state === 'RESOLVED' || item.state === 'CLOSED' || Boolean(item.resolvedAt)
          const isFalse = item.state === 'FALSE_ALARM' || item.reviewStatus === 'FALSE_ALARM'
          if (isResolved || isFalse) return false
        } else if (stateFilter === 'PENDING_REVIEW') {
          if (item.reviewStatus !== 'PENDING_REVIEW' && item.state !== 'PENDING_REVIEW') return false
        }
      }

      // Priority Filter
      if (priorityFilter !== 'ALL') {
        const p = (item.priority ?? '').toUpperCase()
        if (p !== priorityFilter) return false
      }

      // Detection Mode Filter
      if (detectionModeFilter !== 'ALL') {
        if (item.detectionMode !== detectionModeFilter) return false
      }

      // Date Range Presets
      if (datePreset !== 'all' && item.detectedAt) {
        const time = new Date(item.detectedAt).getTime()
        if (!isNaN(time)) {
          const diffHours = (now - time) / (1000 * 60 * 60)
          if (datePreset === 'today' && diffHours > 24) return false
          if (datePreset === 'last7' && diffHours > 24 * 7) return false
          if (datePreset === 'last30' && diffHours > 24 * 30) return false
        }
      }

      return true
    })
  }, [incidents, search, stateFilter, priorityFilter, detectionModeFilter, datePreset])

  // Sort Logic
  const sortedIncidents = useMemo(() => {
    return [...filteredIncidents].sort((a, b) => {
      let result = 0
      if (sortField === 'detectedAt') {
        const tA = new Date(a.detectedAt).getTime() || 0
        const tB = new Date(b.detectedAt).getTime() || 0
        result = tA - tB
      } else if (sortField === 'duration') {
        const dA = getIncidentDuration(a).seconds ?? 0
        const dB = getIncidentDuration(b).seconds ?? 0
        result = dA - dB
      } else if (sortField === 'priority') {
        const pA = PRIORITY_ORDER[(a.priority ?? '').toUpperCase()] ?? 0
        const pB = PRIORITY_ORDER[(b.priority ?? '').toUpperCase()] ?? 0
        result = pA - pB
      } else if (sortField === 'aiScore') {
        result = (a.aiScore || 0) - (b.aiScore || 0)
      } else if (sortField === 'state') {
        result = (a.state ?? '').localeCompare(b.state ?? '')
      }
      return sortOrder === 'asc' ? result : -result
    })
  }, [filteredIncidents, sortField, sortOrder])

  // Pagination Logic
  const totalItems = sortedIncidents.length
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize))
  const paginatedIncidents = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return sortedIncidents.slice(start, start + pageSize)
  }, [sortedIncidents, currentPage, pageSize])

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
    stateFilter !== 'ALL' ||
    priorityFilter !== 'ALL' ||
    detectionModeFilter !== 'ALL' ||
    datePreset !== 'all'

  const clearFilters = () => {
    setSearch('')
    setStateFilter('ALL')
    setPriorityFilter('ALL')
    setDetectionModeFilter('ALL')
    setDatePreset('all')
    setCurrentPage(1)
  }

  // Visual helper badge formatters
  const renderPriorityBadge = (priority?: string | null) => {
    const p = (priority ?? 'MEDIUM').toUpperCase()
    if (p === 'CRITICAL') {
      return (
        <Badge
          variant="outline"
          className="border-rose-300 bg-rose-50 text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-400 font-semibold gap-1 text-xs"
        >
          <AlertOctagon className="h-3 w-3 shrink-0" />
          Critical
        </Badge>
      )
    }
    if (p === 'HIGH') {
      return (
        <Badge
          variant="outline"
          className="border-orange-300 bg-orange-50 text-orange-700 dark:border-orange-900/60 dark:bg-orange-950/30 dark:text-orange-400 font-medium gap-1 text-xs"
        >
          <AlertTriangle className="h-3 w-3 shrink-0" />
          High
        </Badge>
      )
    }
    if (p === 'LOW') {
      return (
        <Badge
          variant="outline"
          className="border-slate-300 bg-slate-50 text-slate-600 dark:border-slate-800 dark:bg-slate-900/40 dark:text-slate-400 font-medium gap-1 text-xs"
        >
          Low
        </Badge>
      )
    }
    return (
      <Badge
        variant="outline"
        className="border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-400 font-medium gap-1 text-xs"
      >
        Medium
      </Badge>
    )
  }

  const renderStateBadge = (item: OperationalIncident) => {
    const isFalseAlarm = item.state === 'FALSE_ALARM' || item.reviewStatus === 'FALSE_ALARM'
    if (isFalseAlarm) {
      return (
        <Badge
          variant="outline"
          className="border-slate-300 bg-slate-100 text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 font-medium gap-1 text-xs"
        >
          <Ban className="h-3 w-3 shrink-0" />
          False Alarm
        </Badge>
      )
    }

    if (item.state === 'RESOLVED' || item.state === 'CLOSED' || Boolean(item.resolvedAt)) {
      return (
        <Badge
          variant="outline"
          className="border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-400 font-medium gap-1 text-xs"
        >
          <CheckCircle2 className="h-3 w-3 shrink-0" />
          Resolved
        </Badge>
      )
    }

    if (item.arrivedAt) {
      return (
        <Badge
          variant="outline"
          className="border-blue-300 bg-blue-50 text-blue-700 dark:border-blue-900/60 dark:bg-blue-950/30 dark:text-blue-400 font-medium gap-1 text-xs"
        >
          <MapPin className="h-3 w-3 shrink-0" />
          On Scene
        </Badge>
      )
    }

    if (item.enRouteAt || item.assignmentStatus === 'EN_ROUTE') {
      return (
        <Badge
          variant="outline"
          className="border-sky-300 bg-sky-50 text-sky-700 dark:border-sky-900/60 dark:bg-sky-950/30 dark:text-sky-400 font-medium gap-1 text-xs"
        >
          <Navigation className="h-3 w-3 shrink-0" />
          En Route
        </Badge>
      )
    }

    if (item.assignmentId || item.state === 'ASSIGNED') {
      return (
        <Badge
          variant="outline"
          className="border-primary/40 bg-primary/10 text-primary font-medium gap-1 text-xs"
        >
          <UserCheck className="h-3 w-3 shrink-0" />
          Assigned
        </Badge>
      )
    }

    if (item.reviewStatus === 'CONFIRMED' || item.state === 'CONFIRMED') {
      return (
        <Badge
          variant="outline"
          className="border-teal-300 bg-teal-50 text-teal-700 dark:border-teal-900/60 dark:bg-teal-950/30 dark:text-teal-400 font-medium gap-1 text-xs"
        >
          <Check className="h-3 w-3 shrink-0" />
          Confirmed
        </Badge>
      )
    }

    return (
      <Badge
        variant="outline"
        className="border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-400 font-medium gap-1 text-xs"
      >
        <Eye className="h-3 w-3 shrink-0" />
        Under Review
      </Badge>
    )
  }

  const renderDetectionModeBadge = (mode: string) => {
    if (mode === 'temporal_collision') {
      return (
        <span className="inline-flex items-center gap-1 rounded bg-rose-50 px-1.5 py-0.5 text-[11px] font-semibold text-rose-700 border border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-900/40">
          <ShieldAlert className="h-3 w-3 shrink-0" />
          Temporal Collision (P1)
        </span>
      )
    }
    return (
      <span className="inline-flex items-center gap-1 rounded bg-blue-50 px-1.5 py-0.5 text-[11px] font-medium text-blue-700 border border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-900/40">
        <Sparkles className="h-3 w-3 shrink-0" />
        Aftermath Scene (P2)
      </span>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
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
            onClick={() => void loadIncidents(true)}
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
              <p className="font-semibold text-sm">Failed to synchronize incident audit records</p>
              <p className="text-xs opacity-90">{error}</p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => void loadIncidents()}
                className="mt-2 h-7 text-xs bg-card text-foreground"
              >
                Try again
              </Button>
            </div>
          </div>
        </Card>
      ) : null}

      {/* Summary Metric KPI Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 sm:gap-4">
        <Card className="border border-border bg-card p-4 shadow-xs">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Total Incident Logs
          </p>
          <p className="mt-1 font-mono text-2xl font-bold text-foreground">
            {loading ? '—' : metrics.total}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">Authoritative audit ledger</p>
        </Card>

        <Card className="border border-border bg-card p-4 shadow-xs">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Resolved Emergencies
          </p>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="font-mono text-2xl font-bold text-emerald-600 dark:text-emerald-400">
              {loading ? '—' : metrics.resolved}
            </span>
            <span className="text-xs font-semibold text-emerald-600/80">
              ({metrics.resolvedRate}%)
            </span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">Completed scene closures</p>
        </Card>

        <Card className="border border-border bg-card p-4 shadow-xs">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            False Alarms Dismissed
          </p>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="font-mono text-2xl font-bold text-slate-700 dark:text-slate-300">
              {loading ? '—' : metrics.falseAlarms}
            </span>
            <span className="text-xs font-semibold text-muted-foreground">
              ({metrics.falseAlarmRate}%)
            </span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">Verified & dismissed</p>
        </Card>

        <Card className="border border-border bg-card p-4 shadow-xs">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Avg. Resolution Time
          </p>
          <p className="mt-1 font-mono text-2xl font-bold text-primary">
            {loading ? '—' : metrics.avgResolutionTime}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">Detection to scene clearance</p>
        </Card>
      </div>

      {/* Faceted Toolbar */}
      <Card className="border border-border bg-card p-4 shadow-xs space-y-3">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[1fr_9rem_9rem_11rem_9rem]">
          {/* Omni Search */}
          <div className="relative sm:col-span-2 lg:col-span-1">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                setCurrentPage(1)
              }}
              placeholder="Search token, street, reviewer, responder, notes..."
              className="pl-9 h-9 text-sm"
              aria-label="Search incidents"
            />
          </div>

          {/* State Filter */}
          <Select
            value={stateFilter}
            onValueChange={(val) => {
              setStateFilter(val)
              setCurrentPage(1)
            }}
          >
            <SelectTrigger className="h-9 text-sm" aria-label="Filter by State">
              <SelectValue placeholder="State" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All States</SelectItem>
              <SelectItem value="RESOLVED">Resolved / Closed</SelectItem>
              <SelectItem value="FALSE_ALARM">False Alarm Dismissed</SelectItem>
              <SelectItem value="ACTIVE">Active Response</SelectItem>
              <SelectItem value="PENDING_REVIEW">Awaiting Review</SelectItem>
            </SelectContent>
          </Select>

          {/* Priority Filter */}
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

          {/* Detection Mode */}
          <Select
            value={detectionModeFilter}
            onValueChange={(val) => {
              setDetectionModeFilter(val)
              setCurrentPage(1)
            }}
          >
            <SelectTrigger className="h-9 text-sm" aria-label="Filter by Detection Mode">
              <SelectValue placeholder="Detection Mode" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All Detection Modes</SelectItem>
              <SelectItem value="temporal_collision">Temporal Collision (P1)</SelectItem>
              <SelectItem value="aftermath_review">Aftermath Scene (P2)</SelectItem>
            </SelectContent>
          </Select>

          {/* Date Presets */}
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
              <SelectItem value="today">Last 24 Hours</SelectItem>
              <SelectItem value="last7">Last 7 Days</SelectItem>
              <SelectItem value="last30">Last 30 Days</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Active Filter Chips */}
        {isFiltered ? (
          <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-border text-xs">
            <span className="text-muted-foreground flex items-center gap-1 font-medium">
              <Filter className="h-3.5 w-3.5" />
              Active Filters:
            </span>

            {search.trim() ? (
              <Badge variant="secondary" className="gap-1 font-normal py-0.5">
                Search: &quot;{search}&quot;
                <X
                  className="h-3 w-3 cursor-pointer hover:text-foreground"
                  onClick={() => setSearch('')}
                />
              </Badge>
            ) : null}

            {stateFilter !== 'ALL' ? (
              <Badge variant="secondary" className="gap-1 font-normal py-0.5">
                State: {stateFilter.replace('_', ' ')}
                <X
                  className="h-3 w-3 cursor-pointer hover:text-foreground"
                  onClick={() => setStateFilter('ALL')}
                />
              </Badge>
            ) : null}

            {priorityFilter !== 'ALL' ? (
              <Badge variant="secondary" className="gap-1 font-normal py-0.5">
                Priority: {priorityFilter}
                <X
                  className="h-3 w-3 cursor-pointer hover:text-foreground"
                  onClick={() => setPriorityFilter('ALL')}
                />
              </Badge>
            ) : null}

            {detectionModeFilter !== 'ALL' ? (
              <Badge variant="secondary" className="gap-1 font-normal py-0.5">
                Mode: {detectionModeFilter === 'temporal_collision' ? 'Temporal (P1)' : 'Aftermath (P2)'}
                <X
                  className="h-3 w-3 cursor-pointer hover:text-foreground"
                  onClick={() => setDetectionModeFilter('ALL')}
                />
              </Badge>
            ) : null}

            {datePreset !== 'all' ? (
              <Badge variant="secondary" className="gap-1 font-normal py-0.5">
                Range:{' '}
                {datePreset === 'today'
                  ? 'Last 24 Hours'
                  : datePreset === 'last7'
                  ? 'Last 7 Days'
                  : 'Last 30 Days'}
                <X
                  className="h-3 w-3 cursor-pointer hover:text-foreground"
                  onClick={() => setDatePreset('all')}
                />
              </Badge>
            ) : null}

            <Button
              variant="ghost"
              size="sm"
              onClick={clearFilters}
              className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground ml-auto"
            >
              <FilterX className="h-3.5 w-3.5 mr-1" />
              Reset all
            </Button>
          </div>
        ) : null}
      </Card>

      {/* Main Content Area */}
      {loading ? (
        <Card className="border border-border p-12 text-center">
          <div className="flex flex-col items-center justify-center gap-3">
            <RefreshCw className="h-8 w-8 animate-spin text-primary" />
            <p className="text-sm font-medium text-foreground">Synchronizing Incident History...</p>
            <p className="text-xs text-muted-foreground">
              Retrieving authoritative SQLite incident audit logs and response timelines
            </p>
          </div>
        </Card>
      ) : sortedIncidents.length === 0 ? (
        <Card className="border border-border p-12 text-center">
          <div className="flex flex-col items-center justify-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
              <History className="h-6 w-6" />
            </div>
            <div className="space-y-1">
              <h3 className="font-semibold text-base text-foreground">
                {isFiltered ? 'No matching incident records' : 'Incident history ledger is empty'}
              </h3>
              <p className="text-xs text-muted-foreground max-w-sm">
                {isFiltered
                  ? 'Try clearing or relaxing your search query or status filters.'
                  : 'New verified collisions and false-alarm determinations will automatically log here for operational audit.'}
              </p>
            </div>
            {isFiltered ? (
              <Button variant="outline" size="sm" onClick={clearFilters} className="mt-2 text-xs">
                Clear all filters
              </Button>
            ) : null}
          </div>
        </Card>
      ) : (
        <div className="space-y-4">
          {/* Desktop Table View */}
          <div className="hidden md:block overflow-hidden rounded-lg border border-border bg-card shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border bg-muted/50 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  <tr>
                    <th scope="col" className="py-3 px-4">
                      Incident & Location
                    </th>
                    <th scope="col" className="py-3 px-4">
                      Mode & Type
                    </th>
                    <th
                      scope="col"
                      className="py-3 px-4 cursor-pointer hover:text-foreground select-none"
                      onClick={() => handleSort('priority')}
                    >
                      <div className="flex items-center gap-1.5">
                        <span>Priority</span>
                        <ArrowUpDown className="h-3 w-3" />
                      </div>
                    </th>
                    <th
                      scope="col"
                      className="py-3 px-4 cursor-pointer hover:text-foreground select-none"
                      onClick={() => handleSort('state')}
                    >
                      <div className="flex items-center gap-1.5">
                        <span>Status</span>
                        <ArrowUpDown className="h-3 w-3" />
                      </div>
                    </th>
                    <th scope="col" className="py-3 px-4">
                      Personnel Involved
                    </th>
                    <th
                      scope="col"
                      className="py-3 px-4 cursor-pointer hover:text-foreground select-none"
                      onClick={() => handleSort('detectedAt')}
                    >
                      <div className="flex items-center gap-1.5">
                        <span>Detected</span>
                        <ArrowUpDown className="h-3 w-3" />
                      </div>
                    </th>
                    <th
                      scope="col"
                      className="py-3 px-4 cursor-pointer hover:text-foreground select-none"
                      onClick={() => handleSort('duration')}
                    >
                      <div className="flex items-center gap-1.5">
                        <span>Duration</span>
                        <ArrowUpDown className="h-3 w-3" />
                      </div>
                    </th>
                    <th scope="col" className="py-3 px-4 text-right">
                      Audit Details
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {paginatedIncidents.map((item) => {
                    const isExpanded = expandedRows.has(item.id)
                    const durationInfo = getIncidentDuration(item)
                    const token = formatIncidentToken(item.id)
                    const isFalseAlarm =
                      item.state === 'FALSE_ALARM' || item.reviewStatus === 'FALSE_ALARM'

                    return (
                      <tr key={item.id} className="group hover:bg-muted/30 transition-colors">
                        <td colSpan={8} className="p-0">
                          <div>
                            {/* Main Row */}
                            <div className="flex items-center w-full py-3.5 px-4 text-sm">
                              {/* Col 1: Incident & Location (25%) */}
                              <div className="w-[25%] pr-4 space-y-1">
                                <div className="flex items-center gap-2">
                                  <span className="font-mono text-xs font-bold text-foreground bg-muted px-1.5 py-0.5 rounded border border-border">
                                    {token}
                                  </span>
                                  <span className="text-[11px] text-muted-foreground font-mono">
                                    {Math.round((item.aiScore || 0) * 100)}% AI Conf
                                  </span>
                                </div>
                                <div className="flex items-center gap-1.5 text-xs text-foreground font-medium truncate">
                                  <MapPin className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                                  <span className="truncate">
                                    {item.location || 'Camera Station / CCTV'}
                                  </span>
                                </div>
                              </div>

                              {/* Col 2: Mode & Type (16%) */}
                              <div className="w-[16%] pr-3 space-y-1">
                                <div>{renderDetectionModeBadge(item.detectionMode)}</div>
                                <div className="text-xs text-muted-foreground capitalize">
                                  {(item.incidentType || 'Collision').replace('_', ' ')}
                                </div>
                              </div>

                              {/* Col 3: Priority (11%) */}
                              <div className="w-[11%] pr-3">
                                {renderPriorityBadge(item.priority)}
                              </div>

                              {/* Col 4: Status (14%) */}
                              <div className="w-[14%] pr-3">
                                {renderStateBadge(item)}
                              </div>

                              {/* Col 5: Personnel Involved (14%) */}
                              <div className="w-[14%] pr-3 text-xs space-y-1">
                                {item.reviewedBy ? (
                                  <div className="flex items-center gap-1 text-foreground truncate">
                                    <UserCheck className="h-3 w-3 shrink-0 text-muted-foreground" />
                                    <span className="truncate" title={`Reviewer: ${item.reviewedBy}`}>
                                      {item.reviewedBy}
                                    </span>
                                  </div>
                                ) : (
                                  <span className="text-muted-foreground">No reviewer</span>
                                )}
                                {item.responderName ? (
                                  <div className="flex items-center gap-1 text-primary font-medium truncate">
                                    <Navigation className="h-3 w-3 shrink-0" />
                                    <span className="truncate" title={`Responder: ${item.responderName}`}>
                                      {item.responderName}
                                    </span>
                                  </div>
                                ) : null}
                              </div>

                              {/* Col 6: Detected (10%) */}
                              <div className="w-[10%] pr-3 text-xs">
                                <p className="font-medium text-foreground">
                                  {formatDate(item.detectedAt)}
                                </p>
                                <p className="text-muted-foreground font-mono">
                                  {formatTime(item.detectedAt)}
                                </p>
                              </div>

                              {/* Col 7: Duration (10%) */}
                              <div className="w-[10%] pr-3 text-xs">
                                <span
                                  className={`font-mono font-medium ${
                                    isFalseAlarm
                                      ? 'text-muted-foreground'
                                      : durationInfo.seconds !== null
                                      ? 'text-emerald-700 dark:text-emerald-400'
                                      : 'text-amber-700 dark:text-amber-400'
                                  }`}
                                >
                                  {durationInfo.label}
                                </span>
                              </div>

                              {/* Col 8: Actions (fit) */}
                              <div className="ml-auto text-right">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => toggleRow(item.id)}
                                  className="h-8 w-8 p-0"
                                  aria-label={isExpanded ? 'Collapse audit details' : 'Expand audit details'}
                                >
                                  {isExpanded ? (
                                    <ChevronUp className="h-4 w-4" />
                                  ) : (
                                    <ChevronDown className="h-4 w-4" />
                                  )}
                                </Button>
                              </div>
                            </div>

                            {/* Expanded Detail Accordion */}
                            {isExpanded ? (
                              <div className="border-t border-border/80 bg-muted/20 p-5 space-y-5">
                                {/* False Alarm Banner */}
                                {isFalseAlarm ? (
                                  <div className="rounded-md border border-amber-200 bg-amber-50/70 p-4 dark:border-amber-900/50 dark:bg-amber-950/20">
                                    <div className="flex items-start gap-3">
                                      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">
                                        <Ban className="h-4 w-4" />
                                      </div>
                                      <div className="space-y-1">
                                        <div className="flex items-center gap-2">
                                          <h4 className="text-xs font-bold uppercase tracking-wider text-amber-900 dark:text-amber-300">
                                            Dismissed as False Alarm
                                          </h4>
                                          {item.reviewedAt ? (
                                            <span className="text-xs text-amber-700 dark:text-amber-400">
                                              at {formatMilestoneTime(item.reviewedAt)} (
                                              {formatDate(item.reviewedAt)})
                                            </span>
                                          ) : null}
                                        </div>
                                        <p className="text-sm font-semibold text-amber-950 dark:text-amber-100">
                                          Reason: {item.falseAlarmReason || 'No specific reason documented'}
                                        </p>
                                        <p className="text-xs text-amber-800 dark:text-amber-300">
                                          Reviewed and dismissed by dispatcher:{' '}
                                          <span className="font-semibold">
                                            {item.reviewedBy || 'Authoritative Dispatcher'}
                                          </span>
                                        </p>
                                      </div>
                                    </div>
                                  </div>
                                ) : null}

                                {/* 5-Stage Incident Timeline */}
                                <div className="space-y-3">
                                  <div className="flex items-center justify-between">
                                    <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                                      <Clock className="h-3.5 w-3.5" />
                                      Operational Milestone Progression
                                    </h4>
                                    <span className="text-xs text-muted-foreground">
                                      Detection to Scene Clearance
                                    </span>
                                  </div>

                                  <div className="relative border-l-2 border-border ml-3.5 pl-6 space-y-4 py-1">
                                    {/* Milestone 1: Detected */}
                                    <div className="relative group/ms">
                                      <div className="absolute -left-[31px] top-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-primary text-primary-foreground">
                                        <Camera className="h-3 w-3" />
                                      </div>
                                      <div className="flex items-baseline justify-between gap-4">
                                        <div>
                                          <p className="text-xs font-semibold text-foreground">
                                            Collision Detected by AI
                                          </p>
                                          <p className="text-[11px] text-muted-foreground">
                                            {item.detectionMode === 'temporal_collision'
                                              ? 'Dynamic Temporal Collision Detection (Priority 1)'
                                              : 'High-Confidence Stationary Aftermath (Priority 2)'}{' '}
                                            • AI Score: {Math.round((item.aiScore || 0) * 100)}%
                                          </p>
                                        </div>
                                        <span className="font-mono text-xs text-muted-foreground shrink-0">
                                          {formatMilestoneTime(item.detectedAt)}
                                        </span>
                                      </div>
                                    </div>

                                    {/* Milestone 2: Reviewed */}
                                    <div className="relative group/ms">
                                      <div
                                        className={`absolute -left-[31px] top-0.5 flex h-5 w-5 items-center justify-center rounded-full ${
                                          isFalseAlarm
                                            ? 'bg-slate-500 text-white'
                                            : item.reviewedAt || item.reviewedBy
                                            ? 'bg-emerald-600 text-white'
                                            : 'bg-muted text-muted-foreground'
                                        }`}
                                      >
                                        {isFalseAlarm ? (
                                          <Ban className="h-3 w-3" />
                                        ) : item.reviewedAt || item.reviewedBy ? (
                                          <Check className="h-3 w-3" />
                                        ) : (
                                          <Eye className="h-3 w-3" />
                                        )}
                                      </div>
                                      <div className="flex items-baseline justify-between gap-4">
                                        <div>
                                          <p className="text-xs font-semibold text-foreground">
                                            {isFalseAlarm
                                              ? 'Dispatcher Verification (False Alarm)'
                                              : 'Dispatcher Review & Confirmation'}
                                          </p>
                                          <p className="text-[11px] text-muted-foreground">
                                            {item.reviewedBy
                                              ? `Processed by ${item.reviewedBy}`
                                              : 'Pending dispatcher confirmation'}
                                          </p>
                                        </div>
                                        <span className="font-mono text-xs text-muted-foreground shrink-0">
                                          {formatMilestoneTime(item.reviewedAt || item.reviewStartedAt)}
                                        </span>
                                      </div>
                                    </div>

                                    {/* Milestone 3: Unit Dispatched */}
                                    {!isFalseAlarm ? (
                                      <div className="relative group/ms">
                                        <div
                                          className={`absolute -left-[31px] top-0.5 flex h-5 w-5 items-center justify-center rounded-full ${
                                            item.assignedAt || item.responderId
                                              ? 'bg-primary text-primary-foreground'
                                              : 'bg-muted text-muted-foreground'
                                          }`}
                                        >
                                          <Navigation className="h-3 w-3" />
                                        </div>
                                        <div className="flex items-baseline justify-between gap-4">
                                          <div>
                                            <p className="text-xs font-semibold text-foreground">
                                              Unit Dispatched
                                            </p>
                                            <p className="text-[11px] text-muted-foreground">
                                              {item.responderName
                                                ? `Assigned to ${item.responderName}`
                                                : item.responderId
                                                ? `Unit ID: ${item.responderId.slice(0, 8)}`
                                                : 'No responder assigned'}
                                            </p>
                                          </div>
                                          <span className="font-mono text-xs text-muted-foreground shrink-0">
                                            {formatMilestoneTime(item.assignedAt)}
                                          </span>
                                        </div>
                                      </div>
                                    ) : null}

                                    {/* Milestone 4: Unit Arrived */}
                                    {!isFalseAlarm ? (
                                      <div className="relative group/ms">
                                        <div
                                          className={`absolute -left-[31px] top-0.5 flex h-5 w-5 items-center justify-center rounded-full ${
                                            item.arrivedAt
                                              ? 'bg-blue-600 text-white'
                                              : 'bg-muted text-muted-foreground'
                                          }`}
                                        >
                                          <MapPin className="h-3 w-3" />
                                        </div>
                                        <div className="flex items-baseline justify-between gap-4">
                                          <div>
                                            <p className="text-xs font-semibold text-foreground">
                                              On-Scene Arrival
                                            </p>
                                            <p className="text-[11px] text-muted-foreground">
                                              {item.arrivedAt
                                                ? 'Emergency unit arrived at collision scene'
                                                : 'Unit in transit'}
                                            </p>
                                          </div>
                                          <span className="font-mono text-xs text-muted-foreground shrink-0">
                                            {formatMilestoneTime(item.arrivedAt)}
                                          </span>
                                        </div>
                                      </div>
                                    ) : null}

                                    {/* Milestone 5: Incident Resolution */}
                                    <div className="relative group/ms">
                                      <div
                                        className={`absolute -left-[31px] top-0.5 flex h-5 w-5 items-center justify-center rounded-full ${
                                          isFalseAlarm
                                            ? 'bg-slate-400 text-white'
                                            : item.resolvedAt
                                            ? 'bg-emerald-600 text-white'
                                            : 'bg-muted text-muted-foreground'
                                        }`}
                                      >
                                        <CheckCircle2 className="h-3 w-3" />
                                      </div>
                                      <div className="flex items-baseline justify-between gap-4">
                                        <div>
                                          <p className="text-xs font-semibold text-foreground">
                                            {isFalseAlarm
                                              ? 'Audit Case Closed (False Alarm)'
                                              : 'Incident Scene Cleared & Resolved'}
                                          </p>
                                          <p className="text-[11px] text-muted-foreground">
                                            {isFalseAlarm
                                              ? 'Review completed and logged'
                                              : item.resolvedAt
                                              ? 'Traffic flow restored & operational handoff finished'
                                              : 'Response currently in progress'}
                                          </p>
                                        </div>
                                        <span className="font-mono text-xs text-muted-foreground shrink-0">
                                          {formatMilestoneTime(item.resolvedAt || (isFalseAlarm ? item.reviewedAt : null))}
                                        </span>
                                      </div>
                                    </div>
                                  </div>
                                </div>

                                {/* Dispatcher & Operational Notes */}
                                <div className="grid gap-4 sm:grid-cols-2 pt-2 border-t border-border/60">
                                  <div className="space-y-1.5">
                                    <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                                      Dispatcher Notes & Context
                                    </h4>
                                    <p className="text-xs text-foreground bg-card p-3 rounded border border-border">
                                      {item.dispatcherNotes || 'No dispatcher notes recorded.'}
                                    </p>
                                  </div>

                                  <div className="space-y-1.5">
                                    <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                                      Location & Coordinates
                                    </h4>
                                    <div className="text-xs text-foreground bg-card p-3 rounded border border-border space-y-1">
                                      <p className="font-medium">{item.location || 'Stationary Camera'}</p>
                                      {item.latitude && item.longitude ? (
                                        <div className="flex items-center justify-between pt-1">
                                          <span className="font-mono text-[11px] text-muted-foreground">
                                            {item.latitude.toFixed(5)}, {item.longitude.toFixed(5)}
                                          </span>
                                          <a
                                            href={`https://www.google.com/maps?q=${item.latitude},${item.longitude}`}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="inline-flex items-center gap-1 text-[11px] text-primary hover:underline"
                                          >
                                            <span>Open Map</span>
                                            <ExternalLink className="h-3 w-3" />
                                          </a>
                                        </div>
                                      ) : (
                                        <p className="text-[11px] text-muted-foreground">
                                          No GPS coordinates recorded
                                        </p>
                                      )}
                                    </div>
                                  </div>
                                </div>

                                {/* Collapsible Technical Identifiers */}
                                <div className="pt-2 border-t border-border/60">
                                  <button
                                    type="button"
                                    onClick={() => toggleTechnical(item.id)}
                                    className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground hover:text-foreground transition-colors"
                                  >
                                    <Layers className="h-3.5 w-3.5" />
                                    <span>Technical UUIDs & Database Identifiers</span>
                                    <ChevronRight
                                      className={`h-3 w-3 transition-transform ${
                                        showTechnical[item.id] ? 'rotate-90' : ''
                                      }`}
                                    />
                                  </button>

                                  {showTechnical[item.id] ? (
                                    <div className="mt-2.5 grid gap-2 sm:grid-cols-2 font-mono text-xs bg-muted/40 p-3 rounded border border-border">
                                      <div className="flex items-center justify-between gap-2">
                                        <span className="text-muted-foreground">Incident ID:</span>
                                        <div className="flex items-center gap-1">
                                          <span className="text-foreground truncate max-w-[140px]">
                                            {item.id}
                                          </span>
                                          <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => copyToClipboard(item.id, 'Incident ID')}
                                            className="h-6 w-6 p-0"
                                            title="Copy Incident UUID"
                                          >
                                            <Copy className="h-3 w-3" />
                                          </Button>
                                        </div>
                                      </div>

                                      {item.reviewCaseId ? (
                                        <div className="flex items-center justify-between gap-2">
                                          <span className="text-muted-foreground">Review Case ID:</span>
                                          <div className="flex items-center gap-1">
                                            <span className="text-foreground truncate max-w-[140px]">
                                              {item.reviewCaseId}
                                            </span>
                                            <Button
                                              variant="ghost"
                                              size="sm"
                                              onClick={() =>
                                                copyToClipboard(item.reviewCaseId!, 'Review Case ID')
                                              }
                                              className="h-6 w-6 p-0"
                                              title="Copy Review Case UUID"
                                            >
                                              <Copy className="h-3 w-3" />
                                            </Button>
                                          </div>
                                        </div>
                                      ) : null}

                                      {item.assignmentId ? (
                                        <div className="flex items-center justify-between gap-2">
                                          <span className="text-muted-foreground">Assignment ID:</span>
                                          <div className="flex items-center gap-1">
                                            <span className="text-foreground truncate max-w-[140px]">
                                              {item.assignmentId}
                                            </span>
                                            <Button
                                              variant="ghost"
                                              size="sm"
                                              onClick={() =>
                                                copyToClipboard(item.assignmentId!, 'Assignment ID')
                                              }
                                              className="h-6 w-6 p-0"
                                              title="Copy Assignment UUID"
                                            >
                                              <Copy className="h-3 w-3" />
                                            </Button>
                                          </div>
                                        </div>
                                      ) : null}

                                      {item.detectorEventId ? (
                                        <div className="flex items-center justify-between gap-2">
                                          <span className="text-muted-foreground">Detector Event ID:</span>
                                          <div className="flex items-center gap-1">
                                            <span className="text-foreground truncate max-w-[140px]">
                                              {item.detectorEventId}
                                            </span>
                                            <Button
                                              variant="ghost"
                                              size="sm"
                                              onClick={() =>
                                                copyToClipboard(
                                                  item.detectorEventId!,
                                                  'Detector Event ID'
                                                )
                                              }
                                              className="h-6 w-6 p-0"
                                              title="Copy Detector Event UUID"
                                            >
                                              <Copy className="h-3 w-3" />
                                            </Button>
                                          </div>
                                        </div>
                                      ) : null}
                                    </div>
                                  ) : null}
                                </div>
                              </div>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Mobile Stacked Card View (< 768px) */}
          <div className="md:hidden space-y-3">
            {paginatedIncidents.map((item) => {
              const isExpanded = expandedRows.has(item.id)
              const durationInfo = getIncidentDuration(item)
              const token = formatIncidentToken(item.id)
              const isFalseAlarm =
                item.state === 'FALSE_ALARM' || item.reviewStatus === 'FALSE_ALARM'

              return (
                <Card key={item.id} className="border border-border p-4 shadow-xs space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold bg-muted px-1.5 py-0.5 rounded border border-border">
                        {token}
                      </span>
                      {renderPriorityBadge(item.priority)}
                    </div>
                    <div>{renderStateBadge(item)}</div>
                  </div>

                  <div className="space-y-1 text-xs">
                    <div className="flex items-center gap-1.5 font-medium text-foreground">
                      <MapPin className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                      <span>{item.location || 'Camera Station / CCTV'}</span>
                    </div>
                    <div className="flex items-center justify-between text-muted-foreground pt-1">
                      <span>{renderDetectionModeBadge(item.detectionMode)}</span>
                      <span className="font-mono">{Math.round((item.aiScore || 0) * 100)}% AI</span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-xs pt-2 border-t border-border">
                    <div className="text-muted-foreground">
                      <span>{formatDate(item.detectedAt)}</span> •{' '}
                      <span className="font-mono">{formatTime(item.detectedAt)}</span>
                    </div>
                    <span className="font-mono font-medium text-foreground">
                      {durationInfo.label}
                    </span>
                  </div>

                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => toggleRow(item.id)}
                    className="w-full text-xs h-8 gap-1"
                  >
                    <span>{isExpanded ? 'Hide Audit Details' : 'View Audit Details'}</span>
                    {isExpanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                  </Button>

                  {/* Expanded mobile details */}
                  {isExpanded ? (
                    <div className="space-y-4 pt-3 border-t border-border">
                      {isFalseAlarm ? (
                        <div className="rounded border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/20 dark:text-amber-300">
                          <p className="font-bold uppercase tracking-wider">Dismissed as False Alarm</p>
                          <p className="mt-1 font-semibold">{item.falseAlarmReason || 'No reason provided'}</p>
                          <p className="mt-1 opacity-80">By: {item.reviewedBy || 'Dispatcher'}</p>
                        </div>
                      ) : null}

                      <div className="space-y-2 text-xs">
                        <p className="font-semibold text-muted-foreground uppercase tracking-wider text-[11px]">
                          Milestones
                        </p>
                        <div className="space-y-1.5 border-l-2 border-border ml-2 pl-3">
                          <div>
                            <p className="font-medium text-foreground">Detected</p>
                            <p className="text-muted-foreground font-mono text-[11px]">
                              {formatMilestoneTime(item.detectedAt)}
                            </p>
                          </div>
                          <div>
                            <p className="font-medium text-foreground">Reviewed</p>
                            <p className="text-muted-foreground font-mono text-[11px]">
                              {formatMilestoneTime(item.reviewedAt || item.reviewStartedAt)}
                            </p>
                          </div>
                          {item.assignedAt ? (
                            <div>
                              <p className="font-medium text-foreground">Dispatched</p>
                              <p className="text-muted-foreground font-mono text-[11px]">
                                {formatMilestoneTime(item.assignedAt)}
                              </p>
                            </div>
                          ) : null}
                          {item.resolvedAt ? (
                            <div>
                              <p className="font-medium text-foreground">Resolved</p>
                              <p className="text-muted-foreground font-mono text-[11px]">
                                {formatMilestoneTime(item.resolvedAt)}
                              </p>
                            </div>
                          ) : null}
                        </div>
                      </div>

                      {item.dispatcherNotes ? (
                        <div className="text-xs space-y-1">
                          <p className="font-semibold text-muted-foreground uppercase tracking-wider text-[11px]">
                            Dispatcher Notes
                          </p>
                          <p className="p-2 rounded bg-muted/40 text-foreground border border-border">
                            {item.dispatcherNotes}
                          </p>
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </Card>
              )
            })}
          </div>

          {/* IBM Carbon Style Pagination Controls */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between py-2 text-xs text-muted-foreground">
            <div className="flex items-center gap-2">
              <span>Rows per page:</span>
              <Select
                value={String(pageSize)}
                onValueChange={(val) => {
                  setPageSize(Number(val))
                  setCurrentPage(1)
                }}
              >
                <SelectTrigger className="h-8 w-16 text-xs" aria-label="Rows per page">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="10">10</SelectItem>
                  <SelectItem value="25">25</SelectItem>
                  <SelectItem value="50">50</SelectItem>
                </SelectContent>
              </Select>
              <span>
                Showing {totalItems > 0 ? (currentPage - 1) * pageSize + 1 : 0}–
                {Math.min(currentPage * pageSize, totalItems)} of {totalItems} incidents
              </span>
            </div>

            <div className="flex items-center gap-1">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(1)}
                disabled={currentPage <= 1}
                className="h-8 px-2.5 text-xs"
              >
                First
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage <= 1}
                className="h-8 px-2.5 text-xs"
              >
                Previous
              </Button>
              <span className="px-2 text-foreground font-medium">
                Page {currentPage} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage >= totalPages}
                className="h-8 px-2.5 text-xs"
              >
                Next
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(totalPages)}
                disabled={currentPage >= totalPages}
                className="h-8 px-2.5 text-xs"
              >
                Last
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
