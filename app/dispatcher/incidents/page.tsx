'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Ban,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  Copy,
  ExternalLink,
  FilterX,
  Flame,
  Layers,
  MapPin,
  Navigation,
  Radio,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  User,
  UserCheck,
  UserX,
  Wifi,
  WifiOff,
  X,
} from 'lucide-react'

import {
  phase3,
  type OperationalIncident,
  type ResponderPresence,
} from '@/lib/phase3-api'
import { responderAssignmentLabel, sortRespondersByAvailability } from '@/lib/responder-presence'
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
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { useToast } from '@/hooks/use-toast'

type IncidentTab = 'all_active' | 'needs_dispatch' | 'en_route' | 'on_scene' | 'resolved'

function formatIncidentToken(id?: string | null): string {
  if (!id) return 'INC-—'
  if (id.startsWith('INC-')) return id
  const clean = id.replace(/[^a-zA-Z0-9]/g, '')
  return `INC-${clean.slice(0, 4).toUpperCase()}`
}

function formatRelativeTime(dateStr?: string | null): string {
  if (!dateStr) return '—'
  try {
    const diffMs = Date.now() - new Date(dateStr).getTime()
    if (isNaN(diffMs)) return dateStr
    const sec = Math.floor(diffMs / 1000)
    if (sec < 60) return `${sec}s ago`
    const min = Math.floor(sec / 60)
    if (min < 60) return `${min}m ago`
    const hours = Math.floor(min / 60)
    if (hours < 24) return `${hours}h ago`
    return new Date(dateStr).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return dateStr
  }
}

export default function DispatcherIncidentsPage() {
  const { toast } = useToast()
  const [incidents, setIncidents] = useState<OperationalIncident[]>([])
  const [responders, setResponders] = useState<ResponderPresence[]>([])
  const [selectedResponder, setSelectedResponder] = useState<Record<string, string>>({})
  const [busyIncidentId, setBusyIncidentId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')

  // Modals
  const [cancelModalIncident, setCancelModalIncident] = useState<OperationalIncident | null>(null)
  const [offlineWarningIncident, setOfflineWarningIncident] = useState<{
    incident: OperationalIncident
    responder: ResponderPresence
  } | null>(null)

  // Filters & Search
  const [activeTab, setActiveTab] = useState<IncidentTab>('all_active')
  const [search, setSearch] = useState('')

  // Expanded technical metadata map
  const [expandedTech, setExpandedTech] = useState<Record<string, boolean>>({})

  const loadData = useCallback(async (isManual = false) => {
    if (isManual) setRefreshing(true)
    else setLoading(true)
    setError('')
    try {
      const [incidentRes, responderRes] = await Promise.all([
        phase3.incidents(),
        phase3.responders(),
      ])
      setIncidents(incidentRes.incidents ?? [])
      const sorted = sortRespondersByAvailability(responderRes.responders ?? [])
      setResponders(sorted)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not refresh incident operations.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    void loadData()
  }, [loadData])

  // Periodic polling every 15 seconds
  useEffect(() => {
    const timer = setInterval(() => void loadData(false), 15_000)
    return () => clearInterval(timer)
  }, [loadData])

  const responderById = useMemo(() => {
    return new Map(responders.map((r) => [r.uid, r]))
  }, [responders])

  // Active non-false-alarm incidents
  const operationalIncidents = useMemo(() => {
    return incidents.filter((i) => i.state !== 'FALSE_ALARM')
  }, [incidents])

  // Summary Metrics
  const metrics = useMemo(() => {
    const totalActive = operationalIncidents.filter(
      (i) => i.state === 'ACTIVE_RESPONSE' || i.state === 'CONFIRMED'
    ).length

    const needsDispatch = operationalIncidents.filter(
      (i) => i.state === 'CONFIRMED' && !i.assignmentId
    ).length

    const enRoute = operationalIncidents.filter(
      (i) => i.assignmentStatus === 'EN_ROUTE'
    ).length

    const onScene = operationalIncidents.filter(
      (i) => i.assignmentStatus === 'ARRIVED' || i.assignmentStatus === 'RESPONDING'
    ).length

    const resolved = operationalIncidents.filter((i) => i.state === 'RESOLVED').length

    return { totalActive, needsDispatch, enRoute, onScene, resolved }
  }, [operationalIncidents])

  // Filtered Incidents Feed
  const filteredIncidents = useMemo(() => {
    const q = search.trim().toLowerCase()

    return operationalIncidents.filter((incident) => {
      // Tab filter
      if (activeTab === 'all_active' && incident.state === 'RESOLVED') return false
      if (activeTab === 'needs_dispatch' && (incident.state !== 'CONFIRMED' || incident.assignmentId)) return false
      if (activeTab === 'en_route' && incident.assignmentStatus !== 'EN_ROUTE') return false
      if (
        activeTab === 'on_scene' &&
        incident.assignmentStatus !== 'ARRIVED' &&
        incident.assignmentStatus !== 'RESPONDING'
      ) return false
      if (activeTab === 'resolved' && incident.state !== 'RESOLVED') return false

      // Search
      if (q) {
        const token = formatIncidentToken(incident.id).toLowerCase()
        const loc = (incident.location ?? '').toLowerCase()
        const state = incident.state.toLowerCase()
        const responder = (incident.responderName ?? '').toLowerCase()

        if (!token.includes(q) && !loc.includes(q) && !state.includes(q) && !responder.includes(q)) {
          return false
        }
      }

      return true
    })
  }, [operationalIncidents, activeTab, search])

  // Assign or Reassign Unit Execution
  const executeAssignment = async (incident: OperationalIncident, responderUid: string) => {
    setBusyIncidentId(incident.id)
    setError('')
    try {
      if (incident.assignmentId) {
        await phase3.reassign(incident.id, responderUid)
        const unit = responderById.get(responderUid)
        toast({
          title: 'Unit reassigned',
          description: `Successfully reassigned ${unit?.displayName || 'unit'} to ${formatIncidentToken(incident.id)}.`,
        })
      } else {
        await phase3.assign(incident.id, responderUid)
        const unit = responderById.get(responderUid)
        toast({
          title: 'Unit dispatched',
          description: `Dispatched ${unit?.displayName || 'unit'} to ${formatIncidentToken(incident.id)}.`,
        })
      }
      await loadData(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Dispatch operation failed.')
    } finally {
      setBusyIncidentId(null)
    }
  }

  // Pre-dispatch verification
  const handleAssignClick = (incident: OperationalIncident) => {
    const responderUid = selectedResponder[incident.id] || responders[0]?.uid
    if (!responderUid) return

    const responder = responderById.get(responderUid)
    if (responder?.presenceStatus === 'OFFLINE') {
      setOfflineWarningIncident({ incident, responder })
      return
    }

    void executeAssignment(incident, responderUid)
  }

  // Cancel Assignment Execution
  const executeCancelAssignment = async () => {
    if (!cancelModalIncident?.assignmentId) return
    const id = cancelModalIncident.id
    const assignmentId = cancelModalIncident.assignmentId

    setBusyIncidentId(id)
    setError('')
    try {
      await phase3.cancel(assignmentId)
      toast({
        title: 'Assignment cancelled',
        description: `Cancelled response for ${formatIncidentToken(id)}. Case returned to confirmed queue.`,
      })
      setCancelModalIncident(null)
      await loadData(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Cancel dispatch failed.')
    } finally {
      setBusyIncidentId(null)
    }
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
        variant: 'destructive',
      })
    }
  }

  const toggleTech = (id: string) => {
    setExpandedTech((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  const isFiltered = search.trim() !== '' || activeTab !== 'all_active'

  const clearFilters = () => {
    setSearch('')
    setActiveTab('all_active')
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Activity className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
                  Active Incident Control
                </h1>
                <Badge
                  variant="outline"
                  className="bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 font-mono text-[10px] tracking-wider uppercase font-bold"
                >
                  ● Real-Time Control
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground">
                Command desk for verified crash emergencies, responder unit transit, and on-scene resolution.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button asChild variant="outline" size="sm" className="h-9 gap-1.5 text-xs">
            <Link href="/dispatcher/map">
              <MapPin className="h-3.5 w-3.5 text-primary" />
              <span>Incident Map</span>
            </Link>
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => void loadData(true)}
            disabled={refreshing || loading}
            className="h-9 gap-1.5 text-xs"
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </Button>
        </div>
      </div>

      {/* Error Alert */}
      {error ? (
        <Card className="border-destructive/30 bg-destructive/5 p-4 text-destructive shadow-xs">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="font-semibold text-sm">Dispatch Operation Error</p>
              <p className="text-xs opacity-90">{error}</p>
            </div>
          </div>
        </Card>
      ) : null}

      {/* Summary KPI Metric Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 sm:gap-4">
        <Card
          onClick={() => setActiveTab('all_active')}
          className={`cursor-pointer border p-4 shadow-xs transition-colors hover:border-primary/50 ${
            activeTab === 'all_active' ? 'border-primary/60 bg-primary/[0.02]' : 'border-border bg-card'
          }`}
        >
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Active Emergencies
          </p>
          <p className="mt-1 font-mono text-2xl font-bold text-foreground">
            {loading ? '—' : metrics.totalActive}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">Open verified crash events</p>
        </Card>

        <Card
          onClick={() => setActiveTab('needs_dispatch')}
          className={`cursor-pointer border p-4 shadow-xs transition-colors hover:border-primary/50 ${
            activeTab === 'needs_dispatch' ? 'border-rose-500/60 bg-rose-500/[0.02]' : 'border-border bg-card'
          }`}
        >
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground flex items-center gap-1">
            <AlertTriangle className="h-3.5 w-3.5 text-rose-500" />
            Needs Unit Dispatch
          </p>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="font-mono text-2xl font-bold text-rose-600 dark:text-rose-400">
              {loading ? '—' : metrics.needsDispatch}
            </span>
            {metrics.needsDispatch > 0 ? (
              <span className="flex h-2 w-2 rounded-full bg-rose-500 animate-pulse" />
            ) : null}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">Confirmed, awaiting unit</p>
        </Card>

        <Card
          onClick={() => setActiveTab('en_route')}
          className={`cursor-pointer border p-4 shadow-xs transition-colors hover:border-primary/50 ${
            activeTab === 'en_route' ? 'border-blue-500/60 bg-blue-500/[0.02]' : 'border-border bg-card'
          }`}
        >
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground flex items-center gap-1">
            <Navigation className="h-3.5 w-3.5 text-blue-500" />
            Units En Route
          </p>
          <p className="mt-1 font-mono text-2xl font-bold text-blue-600 dark:text-blue-400">
            {loading ? '—' : metrics.enRoute}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">Responders traveling to scene</p>
        </Card>

        <Card
          onClick={() => setActiveTab('on_scene')}
          className={`cursor-pointer border p-4 shadow-xs transition-colors hover:border-primary/50 ${
            activeTab === 'on_scene' ? 'border-teal-500/60 bg-teal-500/[0.02]' : 'border-border bg-card'
          }`}
        >
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground flex items-center gap-1">
            <MapPin className="h-3.5 w-3.5 text-teal-600" />
            On-Scene Operations
          </p>
          <p className="mt-1 font-mono text-2xl font-bold text-teal-600 dark:text-teal-400">
            {loading ? '—' : metrics.onScene}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">Active scene triage & clearance</p>
        </Card>
      </div>

      {/* Toolbar: Segmented Tabs + Omni-Search */}
      <Card className="border border-border bg-card p-4 shadow-xs space-y-3">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
            <Button
              variant={activeTab === 'all_active' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setActiveTab('all_active')}
              className="h-8 text-xs font-medium"
            >
              All Active ({metrics.totalActive})
            </Button>
            <Button
              variant={activeTab === 'needs_dispatch' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setActiveTab('needs_dispatch')}
              className="h-8 text-xs font-medium gap-1"
            >
              <AlertTriangle className="h-3 w-3 text-rose-500" />
              Needs Dispatch ({metrics.needsDispatch})
            </Button>
            <Button
              variant={activeTab === 'en_route' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setActiveTab('en_route')}
              className="h-8 text-xs font-medium"
            >
              En Route ({metrics.enRoute})
            </Button>
            <Button
              variant={activeTab === 'on_scene' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setActiveTab('on_scene')}
              className="h-8 text-xs font-medium"
            >
              On Scene ({metrics.onScene})
            </Button>
            <Button
              variant={activeTab === 'resolved' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setActiveTab('resolved')}
              className="h-8 text-xs font-medium"
            >
              Resolved ({metrics.resolved})
            </Button>
          </div>

          <div className="relative md:w-72">
            <Search className="absolute left-2.5 top-2 h-4 w-4 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search INC token, road, or unit..."
              className="pl-8 h-8 text-xs"
              aria-label="Search active incidents"
            />
          </div>
        </div>
      </Card>

      {/* Incidents List Feed */}
      <div className="space-y-4">
        {loading && incidents.length === 0 ? (
          <div className="space-y-3">
            {[1, 2].map((i) => (
              <div
                key={i}
                className="h-36 w-full animate-pulse rounded-lg border border-border bg-card"
              />
            ))}
          </div>
        ) : filteredIncidents.length === 0 ? (
          <Card className="border border-border bg-card p-12 text-center shadow-xs">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
              {search.trim() ? <FilterX className="h-6 w-6" /> : <ShieldCheck className="h-6 w-6" />}
            </div>
            <h3 className="mt-4 text-base font-semibold text-foreground">
              {search.trim() ? 'No matching incidents found' : 'No Incidents in this Category'}
            </h3>
            <p className="mt-1 text-sm text-muted-foreground max-w-sm mx-auto">
              {search.trim()
                ? 'Try adjusting your search terms or selecting a different tab.'
                : 'All response teams are synchronized. New verified incidents will appear automatically.'}
            </p>
            {isFiltered ? (
              <Button
                variant="outline"
                size="sm"
                onClick={clearFilters}
                className="mt-4 text-xs"
              >
                Clear all filters
              </Button>
            ) : null}
          </Card>
        ) : (
          filteredIncidents.map((incident) => {
            const token = formatIncidentToken(incident.id)
            const isCollision = incident.detectionMode === 'temporal_collision'
            const isBusy = busyIncidentId === incident.id
            const isTechOpen = Boolean(expandedTech[incident.id])
            const selectedUid = selectedResponder[incident.id] || responders[0]?.uid || ''
            const chosenResponder = responderById.get(selectedUid)

            return (
              <Card
                key={incident.id}
                className={`border bg-card transition-all shadow-xs overflow-hidden ${
                  incident.state === 'CONFIRMED' && !incident.assignmentId
                    ? 'border-2 border-rose-500/80 ring-2 ring-rose-500/10'
                    : incident.state === 'ACTIVE_RESPONSE'
                    ? 'border-border hover:border-primary/40'
                    : 'border-border opacity-85'
                }`}
              >
                <div className="p-5 space-y-4">
                  {/* Top Bar: Incident Token, Dual-Path Tag & Priority */}
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between border-b border-border/50 pb-3">
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono font-bold text-lg text-foreground">
                          {token}
                        </span>

                        <PriorityBadge priority={incident.priority} />

                        {isCollision ? (
                          <Badge
                            variant="outline"
                            className="gap-1 bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 text-xs font-bold"
                          >
                            <Flame className="h-3 w-3" />
                            Priority 1 Collision
                          </Badge>
                        ) : (
                          <Badge
                            variant="outline"
                            className="gap-1 bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 text-xs font-semibold"
                          >
                            <ShieldAlert className="h-3 w-3" />
                            Aftermath Scene
                          </Badge>
                        )}

                        <span className="text-xs text-muted-foreground">
                          · Detected {formatRelativeTime(incident.detectedAt)}
                        </span>
                      </div>

                      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                        <MapPin className="h-3.5 w-3.5 text-primary shrink-0" />
                        <span className="font-medium text-foreground">
                          {incident.location || 'Intersection Logged'}
                        </span>
                        {incident.latitude && incident.longitude ? (
                          <Link
                            href="/dispatcher/map"
                            className="inline-flex items-center gap-0.5 text-primary hover:underline ml-1 font-mono text-[11px]"
                          >
                            <span>({incident.latitude.toFixed(4)}°, {incident.longitude.toFixed(4)}°)</span>
                            <ExternalLink className="h-2.5 w-2.5" />
                          </Link>
                        ) : null}
                      </p>
                    </div>

                    {/* Overall Incident State Badge */}
                    <div className="flex items-center gap-2">
                      <Badge
                        variant="outline"
                        className="px-2.5 py-1 text-xs font-semibold uppercase tracking-wider"
                      >
                        State: {incident.state.replace('_', ' ')}
                      </Badge>
                    </div>
                  </div>

                  {/* Incident Lifecycle Milestone Stepper */}
                  <div className="rounded-lg border border-border/70 bg-muted/20 p-3.5">
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-2.5">
                      Response Lifecycle Progression
                    </p>
                    <LifecycleStepper incident={incident} />
                  </div>

                  {/* Dispatcher Unit Control Bar (Visible for active/confirmed incidents) */}
                  {incident.state !== 'RESOLVED' && (
                    <div className="rounded-xl border border-border bg-card p-4 space-y-3">
                      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                        <div className="flex items-center gap-2">
                          <Radio className="h-4 w-4 text-primary" />
                          <span className="font-semibold text-xs text-foreground">
                            {incident.assignmentId ? 'Active Responder Unit:' : 'Deploy Available Unit:'}
                          </span>
                          {incident.responderName ? (
                            <Badge className="bg-primary/10 text-primary border-primary/20 text-xs font-semibold">
                              {incident.responderName}
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="text-xs text-rose-600 border-rose-200">
                              Unassigned — Action Required
                            </Badge>
                          )}
                        </div>

                        {incident.assignmentStatus ? (
                          <span className="font-mono text-xs text-muted-foreground">
                            Current Stage: <span className="font-bold text-foreground">{incident.assignmentStatus}</span>
                          </span>
                        ) : null}
                      </div>

                      {/* Responder Selection & Dispatch Triggers */}
                      <div className="flex flex-col sm:flex-row sm:items-center gap-2 pt-2 border-t border-border/50">
                        <div className="flex-1">
                          <Select
                            value={selectedUid}
                            onValueChange={(val) =>
                              setSelectedResponder((curr) => ({ ...curr, [incident.id]: val }))
                            }
                          >
                            <SelectTrigger className="h-9 text-xs">
                              <SelectValue placeholder="Select Responder Unit..." />
                            </SelectTrigger>
                            <SelectContent>
                              {responders.map((r) => {
                                const isOnline = r.presenceStatus === 'ONLINE'
                                const isAvail = r.availabilityStatus === 'AVAILABLE'

                                return (
                                  <SelectItem key={r.uid} value={r.uid}>
                                    <div className="flex items-center gap-2">
                                      <div
                                        className={`h-2 w-2 rounded-full ${
                                          isOnline ? 'bg-emerald-500' : 'bg-muted-foreground/40'
                                        }`}
                                      />
                                      <span className="font-semibold">{r.displayName}</span>
                                      <span className="text-muted-foreground text-[11px]">
                                        ({r.areaId || 'Central'})
                                      </span>
                                      <span
                                        className={`text-[10px] px-1.5 py-0.5 rounded ${
                                          isAvail
                                            ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 font-semibold'
                                            : 'bg-muted text-muted-foreground'
                                        }`}
                                      >
                                        {r.availabilityStatus || 'OFFLINE'}
                                      </span>
                                    </div>
                                  </SelectItem>
                                )
                              })}
                            </SelectContent>
                          </Select>
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          <Button
                            size="sm"
                            disabled={!responders.length || isBusy}
                            onClick={() => handleAssignClick(incident)}
                            className="h-9 gap-1.5 text-xs font-semibold bg-primary hover:bg-primary/90"
                          >
                            <Radio className="h-3.5 w-3.5" />
                            <span>{isBusy ? 'Dispatching…' : incident.assignmentId ? 'Reassign Unit' : 'Dispatch Unit'}</span>
                          </Button>

                          {incident.assignmentId ? (
                            <Button
                              variant="destructive"
                              size="sm"
                              disabled={isBusy}
                              onClick={() => setCancelModalIncident(incident)}
                              className="h-9 gap-1 text-xs"
                            >
                              <Ban className="h-3.5 w-3.5" />
                              <span>Cancel</span>
                            </Button>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Technical & Audit Identifiers Collapsible */}
                  <div className="pt-2 border-t border-border/50">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => toggleTech(incident.id)}
                      className="h-6 p-0 text-[11px] text-muted-foreground hover:text-foreground gap-1"
                    >
                      <Layers className="h-3 w-3" />
                      <span>Technical Audit Identifiers</span>
                      {isTechOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                    </Button>

                    {isTechOpen ? (
                      <div className="mt-2 rounded-md bg-muted/40 p-2.5 text-xs font-mono grid gap-2 sm:grid-cols-2">
                        <div className="flex items-center justify-between gap-2 border-b border-border/40 pb-1 sm:border-b-0 sm:pb-0">
                          <div className="truncate">
                            <span className="text-[10px] uppercase text-muted-foreground block">
                              Incident UUID
                            </span>
                            <span className="text-foreground truncate select-all">{incident.id}</span>
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => copyToClipboard(incident.id, 'Incident UUID')}
                            className="h-6 w-6 p-0 shrink-0"
                            title="Copy Incident UUID"
                          >
                            <Copy className="h-3 w-3 text-muted-foreground" />
                          </Button>
                        </div>

                        {incident.assignmentId ? (
                          <div className="flex items-center justify-between gap-2">
                            <div className="truncate">
                              <span className="text-[10px] uppercase text-muted-foreground block">
                                Assignment UUID
                              </span>
                              <span className="text-foreground truncate select-all">{incident.assignmentId}</span>
                            </div>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => copyToClipboard(incident.assignmentId!, 'Assignment UUID')}
                              className="h-6 w-6 p-0 shrink-0"
                              title="Copy Assignment UUID"
                            >
                              <Copy className="h-3 w-3 text-muted-foreground" />
                            </Button>
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                </div>
              </Card>
            )
          })
        )}
      </div>

      {/* CANCEL ASSIGNMENT MODAL: Replaces window.confirm */}
      <AlertDialog
        open={Boolean(cancelModalIncident)}
        onOpenChange={(open) => {
          if (!open) setCancelModalIncident(null)
        }}
      >
        <AlertDialogContent className="sm:max-w-md">
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2 text-rose-600">
              <AlertTriangle className="h-5 w-5" />
              Cancel Responder Assignment
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-3 pt-2 text-xs text-foreground">
                <p>
                  Are you sure you want to cancel the active response for incident{' '}
                  <span className="font-bold text-foreground font-mono">
                    {cancelModalIncident ? formatIncidentToken(cancelModalIncident.id) : ''}
                  </span>?
                </p>
                <div className="rounded-lg border border-border bg-muted/40 p-3 text-muted-foreground space-y-1">
                  <p>• The currently assigned responder unit will be released.</p>
                  <p>• The incident will revert to confirmed state awaiting reassignment.</p>
                </div>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep Assignment</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => void executeCancelAssignment()}
              className="bg-rose-600 hover:bg-rose-700"
            >
              Confirm Cancellation
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* OFFLINE RESPONDER WARNING MODAL: Replaces window.confirm */}
      <AlertDialog
        open={Boolean(offlineWarningIncident)}
        onOpenChange={(open) => {
          if (!open) setOfflineWarningIncident(null)
        }}
      >
        <AlertDialogContent className="sm:max-w-md">
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2 text-amber-600">
              <WifiOff className="h-5 w-5" />
              Responder Currently Offline
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-3 pt-2 text-xs text-foreground">
                <p>
                  Unit{' '}
                  <span className="font-bold text-foreground">
                    {offlineWarningIncident?.responder.displayName}
                  </span>{' '}
                  is currently flagged as <span className="font-semibold text-rose-600">OFFLINE</span>.
                </p>
                <p className="text-muted-foreground">
                  The responder may not receive push notifications until they reconnect. Do you want to dispatch this unit anyway?
                </p>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Choose Another Unit</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (offlineWarningIncident) {
                  const { incident, responder } = offlineWarningIncident
                  setOfflineWarningIncident(null)
                  void executeAssignment(incident, responder.uid)
                }
              }}
              className="bg-amber-600 hover:bg-amber-700"
            >
              Dispatch Anyway
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function PriorityBadge({ priority }: { priority?: string | null }) {
  const p = (priority || '').toUpperCase()

  if (p === 'CRITICAL') {
    return (
      <Badge
        variant="outline"
        className="gap-1 bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 text-xs font-bold"
      >
        <AlertTriangle className="h-3 w-3 text-rose-600" />
        CRITICAL
      </Badge>
    )
  }
  if (p === 'HIGH') {
    return (
      <Badge
        variant="outline"
        className="gap-1 bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-950/40 text-xs font-semibold"
      >
        HIGH
      </Badge>
    )
  }
  if (p === 'MEDIUM') {
    return (
      <Badge
        variant="outline"
        className="gap-1 bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 text-xs font-medium"
      >
        MEDIUM
      </Badge>
    )
  }
  return (
    <Badge variant="outline" className="text-xs text-muted-foreground">
      {priority || 'LOW'}
    </Badge>
  )
}

// Lifecycle Stepper Subcomponent
function LifecycleStepper({ incident }: { incident: OperationalIncident }) {
  const hasAssigned = Boolean(incident.assignmentId)
  const isEnRoute =
    incident.assignmentStatus === 'EN_ROUTE' ||
    incident.assignmentStatus === 'ARRIVED' ||
    incident.assignmentStatus === 'RESPONDING' ||
    incident.state === 'RESOLVED'
  const isArrived =
    incident.assignmentStatus === 'ARRIVED' ||
    incident.assignmentStatus === 'RESPONDING' ||
    incident.state === 'RESOLVED'
  const isResolved = incident.state === 'RESOLVED'

  const stages = [
    { label: 'Detected', active: true, done: true },
    { label: 'Confirmed', active: true, done: incident.state !== 'AWAITING_REVIEW' },
    { label: 'Assigned', active: hasAssigned, done: hasAssigned },
    { label: 'En Route', active: isEnRoute, done: isEnRoute },
    { label: 'On Scene', active: isArrived, done: isArrived },
    { label: 'Resolved', active: isResolved, done: isResolved },
  ]

  return (
    <div className="grid grid-cols-6 gap-1 text-center">
      {stages.map((st, idx) => (
        <div key={st.label} className="space-y-1">
          <div
            className={`h-1.5 rounded-full transition-all ${
              st.done
                ? 'bg-emerald-500'
                : st.active
                ? 'bg-primary animate-pulse'
                : 'bg-muted'
            }`}
          />
          <span
            className={`text-[10px] block font-semibold truncate ${
              st.done
                ? 'text-foreground'
                : st.active
                ? 'text-primary'
                : 'text-muted-foreground/60'
            }`}
          >
            {st.label}
          </span>
        </div>
      ))}
    </div>
  )
}
