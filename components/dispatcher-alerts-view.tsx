'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Bell,
  Check,
  CheckCheck,
  ChevronDown,
  ChevronUp,
  Clock,
  Copy,
  ExternalLink,
  FilterX,
  Flame,
  Layers,
  MapPin,
  Radio,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  X,
  XCircle,
} from 'lucide-react'

import {
  phase3,
  type OperationalIncident,
  type OperationalNotification,
} from '@/lib/phase3-api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useToast } from '@/hooks/use-toast'

type AlertTab = 'active' | 'collisions' | 'declined' | 'cleared' | 'all'

interface EnrichedAlert extends OperationalNotification {
  incident?: OperationalIncident
}

function formatIncidentToken(id?: string | null): string {
  if (!id) return 'INC-—'
  if (id.startsWith('INC-')) return id
  const clean = id.replace(/[^a-zA-Z0-9]/g, '')
  return `INC-${clean.slice(0, 4).toUpperCase()}`
}

function formatRelativeTime(dateStr: string): string {
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

export function DispatcherAlertsView() {
  const { toast } = useToast()
  const [alerts, setAlerts] = useState<OperationalNotification[]>([])
  const [incidents, setIncidents] = useState<OperationalIncident[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')

  // Filters & Search
  const [activeTab, setActiveTab] = useState<AlertTab>('active')
  const [search, setSearch] = useState('')

  // Collapsible Technical Identifiers
  const [expandedTech, setExpandedTech] = useState<Record<string, boolean>>({})

  const loadData = useCallback(async (isManual = false) => {
    if (isManual) setRefreshing(true)
    else setLoading(true)
    setError('')
    try {
      const [notifsRes, incidentsRes] = await Promise.all([
        phase3.notifications(),
        phase3.incidents(),
      ])
      setAlerts(notifsRes.notifications ?? [])
      setIncidents(incidentsRes.incidents ?? [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to synchronize alerts.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    void loadData()
  }, [loadData])

  // Periodic polling every 15 seconds for live alarms
  useEffect(() => {
    const timer = setInterval(() => {
      void loadData(false)
    }, 15_000)
    return () => clearInterval(timer)
  }, [loadData])

  // Build Enriched Alerts Map
  const incidentsById = useMemo(() => {
    const map = new Map<string, OperationalIncident>()
    for (const inc of incidents) {
      map.set(inc.id, inc)
    }
    return map
  }, [incidents])

  const enrichedAlerts: EnrichedAlert[] = useMemo(() => {
    return alerts.map((a) => ({
      ...a,
      incident: a.incidentId ? incidentsById.get(a.incidentId) : undefined,
    }))
  }, [alerts, incidentsById])

  // Determine if active Priority 1 collision alerts exist
  const activeP1Count = useMemo(() => {
    return enrichedAlerts.filter(
      (a) =>
        !a.readAt &&
        (a.incident?.detectionMode === 'temporal_collision' || a.type === 'ASSIGNMENT_DECLINED')
    ).length
  }, [enrichedAlerts])

  // Acknowledge a single alert
  const handleAcknowledge = async (id: string) => {
    // Optimistic UI update
    setAlerts((curr) =>
      curr.map((item) => (item.id === id ? { ...item, readAt: new Date().toISOString() } : item))
    )
    try {
      await phase3.readNotification(id)
      toast({
        title: 'Alert acknowledged',
        description: 'Alarm silenced and logged in acknowledged history.',
      })
    } catch {
      void loadData()
    }
  }

  // Acknowledge all unread alerts
  const handleAcknowledgeAll = async () => {
    const unread = alerts.filter((a) => !a.readAt)
    if (unread.length === 0) return

    const nowIso = new Date().toISOString()
    setAlerts((curr) => curr.map((item) => (item.readAt ? item : { ...item, readAt: nowIso })))

    try {
      await Promise.allSettled(unread.map((item) => phase3.readNotification(item.id)))
      toast({
        title: 'All alarms acknowledged',
        description: `Cleared ${unread.length} active emergency alert${
          unread.length === 1 ? '' : 's'
        }.`,
      })
    } catch {
      void loadData()
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

  // Summary Metrics
  const metrics = useMemo(() => {
    const active = enrichedAlerts.filter((a) => !a.readAt).length
    const collisions = enrichedAlerts.filter(
      (a) => !a.readAt && a.incident?.detectionMode === 'temporal_collision'
    ).length
    const declined = enrichedAlerts.filter(
      (a) => !a.readAt && a.type === 'ASSIGNMENT_DECLINED'
    ).length
    const cleared = enrichedAlerts.filter((a) => a.readAt).length

    return { active, collisions, declined, cleared }
  }, [enrichedAlerts])

  // Filtered Alerts Feed
  const filteredAlerts = useMemo(() => {
    const q = search.trim().toLowerCase()

    return enrichedAlerts.filter((alert) => {
      // Tab Filtering
      if (activeTab === 'active' && alert.readAt) return false
      if (activeTab === 'collisions' && (alert.readAt || alert.incident?.detectionMode !== 'temporal_collision')) {
        return false
      }
      if (activeTab === 'declined' && (alert.readAt || alert.type !== 'ASSIGNMENT_DECLINED')) {
        return false
      }
      if (activeTab === 'cleared' && !alert.readAt) return false

      // Search
      if (q) {
        const token = formatIncidentToken(alert.incidentId).toLowerCase()
        const title = alert.title.toLowerCase()
        const msg = alert.message.toLowerCase()
        const loc = (alert.incident?.location ?? '').toLowerCase()

        if (!token.includes(q) && !title.includes(q) && !msg.includes(q) && !loc.includes(q)) {
          return false
        }
      }

      return true
    })
  }, [enrichedAlerts, activeTab, search])

  const isFiltered = search.trim() !== '' || activeTab !== 'active'

  const clearFilters = () => {
    setSearch('')
    setActiveTab('active')
  }

  return (
    <div className="space-y-6">
      {/* Live Broadcast Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="relative flex h-10 w-10 items-center justify-center rounded-lg bg-rose-500/10 text-rose-600">
              <Radio className="h-5 w-5" />
              {activeP1Count > 0 ? (
                <span className="absolute -top-1 -right-1 flex h-3 w-3">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-rose-500" />
                </span>
              ) : null}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
                  Live Emergency Alerts
                </h1>
                <Badge
                  variant="outline"
                  className="bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 font-mono text-[10px] tracking-wider uppercase font-bold"
                >
                  ● Live Feed
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground">
                Real-time emergency broadcast console for AI collisions, unit declines, and siren alarms.
              </p>
            </div>
          </div>
        </div>

        {/* Audio Siren Toggle & Quick Actions */}
        <div className="flex items-center gap-2">
          {metrics.active > 0 ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => void handleAcknowledgeAll()}
              className="h-9 gap-1.5 text-xs"
            >
              <CheckCheck className="h-4 w-4 text-primary" />
              <span>Acknowledge All</span>
            </Button>
          ) : null}

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
              <p className="font-semibold text-sm">Alert Feed Disrupted</p>
              <p className="text-xs opacity-90">{error}</p>
            </div>
          </div>
        </Card>
      ) : null}

      {/* Summary KPI Metric Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 sm:gap-4">
        <Card
          onClick={() => setActiveTab('active')}
          className={`cursor-pointer border p-4 shadow-xs transition-colors hover:border-primary/50 ${
            activeTab === 'active' ? 'border-primary/60 bg-primary/[0.02]' : 'border-border bg-card'
          }`}
        >
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Active Alarms
          </p>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="font-mono text-2xl font-bold text-foreground">
              {loading ? '—' : metrics.active}
            </span>
            {metrics.active > 0 ? (
              <span className="flex h-2 w-2 rounded-full bg-rose-500 animate-pulse" />
            ) : null}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">Unacknowledged emergency events</p>
        </Card>

        <Card
          onClick={() => setActiveTab('collisions')}
          className={`cursor-pointer border p-4 shadow-xs transition-colors hover:border-primary/50 ${
            activeTab === 'collisions' ? 'border-rose-500/60 bg-rose-500/[0.02]' : 'border-border bg-card'
          }`}
        >
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground flex items-center gap-1">
            <Flame className="h-3.5 w-3.5 text-rose-600" />
            Live Collisions
          </p>
          <p className="mt-1 font-mono text-2xl font-bold text-rose-600 dark:text-rose-400">
            {loading ? '—' : metrics.collisions}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">Priority 1 dynamic impacts</p>
        </Card>

        <Card
          onClick={() => setActiveTab('declined')}
          className={`cursor-pointer border p-4 shadow-xs transition-colors hover:border-primary/50 ${
            activeTab === 'declined' ? 'border-amber-500/60 bg-amber-500/[0.02]' : 'border-border bg-card'
          }`}
        >
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground flex items-center gap-1">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
            Declined Units
          </p>
          <p className="mt-1 font-mono text-2xl font-bold text-amber-600 dark:text-amber-400">
            {loading ? '—' : metrics.declined}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">Requires unit reassignment</p>
        </Card>

        <Card
          onClick={() => setActiveTab('cleared')}
          className={`cursor-pointer border p-4 shadow-xs transition-colors hover:border-primary/50 ${
            activeTab === 'cleared' ? 'border-primary/60 bg-primary/[0.02]' : 'border-border bg-card'
          }`}
        >
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Acknowledged
          </p>
          <p className="mt-1 font-mono text-2xl font-bold text-muted-foreground">
            {loading ? '—' : metrics.cleared}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">Logged & silenced alarms</p>
        </Card>
      </div>

      {/* Toolbar: Segmented Tabs + Omni-Search */}
      <Card className="border border-border bg-card p-4 shadow-xs space-y-3">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
            <Button
              variant={activeTab === 'active' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setActiveTab('active')}
              className="h-8 text-xs font-medium"
            >
              Active Alarms ({metrics.active})
            </Button>
            <Button
              variant={activeTab === 'collisions' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setActiveTab('collisions')}
              className="h-8 text-xs font-medium gap-1"
            >
              <Flame className="h-3 w-3 text-rose-500" />
              Collisions ({metrics.collisions})
            </Button>
            <Button
              variant={activeTab === 'declined' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setActiveTab('declined')}
              className="h-8 text-xs font-medium gap-1"
            >
              <AlertTriangle className="h-3 w-3 text-amber-500" />
              Declined ({metrics.declined})
            </Button>
            <Button
              variant={activeTab === 'cleared' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setActiveTab('cleared')}
              className="h-8 text-xs font-medium"
            >
              Acknowledged ({metrics.cleared})
            </Button>
            <Button
              variant={activeTab === 'all' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setActiveTab('all')}
              className="h-8 text-xs font-medium"
            >
              All Logs ({enrichedAlerts.length})
            </Button>
          </div>

          <div className="relative md:w-72">
            <Search className="absolute left-2.5 top-2 h-4 w-4 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search INC token, road, or alarm..."
              className="pl-8 h-8 text-xs"
              aria-label="Search alerts"
            />
          </div>
        </div>
      </Card>

      {/* Emergency Alerts Feed */}
      <div className="space-y-4">
        {loading && alerts.length === 0 ? (
          <div className="space-y-3">
            {[1, 2].map((i) => (
              <div
                key={i}
                className="h-32 w-full animate-pulse rounded-lg border border-border bg-card"
              />
            ))}
          </div>
        ) : filteredAlerts.length === 0 ? (
          <Card className="border border-border bg-card p-12 text-center shadow-xs">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
              {search.trim() ? <FilterX className="h-6 w-6" /> : <ShieldCheck className="h-6 w-6" />}
            </div>
            <h3 className="mt-4 text-base font-semibold text-foreground">
              {search.trim() ? 'No matching emergency alerts' : 'No Active Alarms'}
            </h3>
            <p className="mt-1 text-sm text-muted-foreground max-w-sm mx-auto">
              {search.trim()
                ? 'Try adjusting your search terms or selecting a different tab.'
                : 'All traffic monitoring feeds and responder assignments are operating normally.'}
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
          filteredAlerts.map((alert) => {
            const isUnread = !alert.readAt
            const incident = alert.incident
            const isCollision = incident?.detectionMode === 'temporal_collision'
            const isDeclined = alert.type === 'ASSIGNMENT_DECLINED'
            const isP1 = isCollision || isDeclined
            const token = formatIncidentToken(alert.incidentId)
            const confidencePct = incident ? Math.round(incident.aiScore * 100) : null
            const isTechOpen = Boolean(expandedTech[alert.id])

            return (
              <Card
                key={alert.id}
                className={`border bg-card transition-all shadow-xs overflow-hidden ${
                  isUnread && isP1
                    ? 'border-2 border-rose-500 ring-2 ring-rose-500/20 dark:border-rose-700'
                    : isUnread
                    ? 'border-l-4 border-l-amber-500 border-t-border border-r-border border-b-border'
                    : 'border-border opacity-85'
                }`}
              >
                <div className="p-5 space-y-4">
                  {/* Top Bar: Urgency Classification & Time */}
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between border-b border-border/50 pb-3">
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono font-bold text-base text-foreground">
                          {token}
                        </span>

                        {isCollision ? (
                          <Badge
                            variant="outline"
                            className="gap-1 bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800 text-xs font-bold"
                          >
                            <Flame className="h-3 w-3" />
                            Priority 1 Collision Alarm
                          </Badge>
                        ) : isDeclined ? (
                          <Badge
                            variant="outline"
                            className="gap-1 bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800 text-xs font-bold"
                          >
                            <AlertTriangle className="h-3 w-3" />
                            Unit Declined — Immediate Reassign
                          </Badge>
                        ) : (
                          <Badge
                            variant="outline"
                            className="gap-1 bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800 text-xs font-semibold"
                          >
                            <ShieldAlert className="h-3 w-3" />
                            Priority 2 Aftermath Verification
                          </Badge>
                        )}

                        {isUnread ? (
                          <span className="inline-flex items-center gap-1 font-mono text-[11px] font-bold text-rose-600 dark:text-rose-400 uppercase tracking-wider">
                            <span className="h-2 w-2 rounded-full bg-rose-500 animate-pulse" />
                            Active Alarm
                          </span>
                        ) : (
                          <span className="text-xs text-muted-foreground">
                            Acknowledged
                          </span>
                        )}

                        <span className="text-xs text-muted-foreground">
                          · {formatRelativeTime(alert.createdAt)}
                        </span>
                      </div>

                      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                        <MapPin className="h-3.5 w-3.5 text-primary shrink-0" />
                        <span className="font-medium text-foreground">
                          {incident?.location || 'Camera Zone Coordinates Logged'}
                        </span>
                        {incident?.latitude && incident?.longitude ? (
                          <span className="font-mono text-[11px] opacity-80">
                            ({incident.latitude.toFixed(4)}°, {incident.longitude.toFixed(4)}°)
                          </span>
                        ) : null}
                      </p>
                    </div>

                    {/* Quick Triage Actions */}
                    <div className="flex items-center gap-2">
                      {alert.type === 'NEW_CRASH_REVIEW' ? (
                        <Button asChild size="sm" className="h-8 gap-1.5 text-xs font-semibold">
                          <Link href="/dispatcher/review">
                            <span>Triage & Claim Review</span>
                            <ArrowRight className="h-3.5 w-3.5" />
                          </Link>
                        </Button>
                      ) : alert.type === 'ASSIGNMENT_DECLINED' ? (
                        <Button asChild size="sm" className="h-8 gap-1.5 text-xs font-semibold bg-amber-600 hover:bg-amber-700">
                          <Link href="/dispatcher/incidents">
                            <span>Reassign Responder</span>
                            <ArrowRight className="h-3.5 w-3.5" />
                          </Link>
                        </Button>
                      ) : null}

                      {isUnread ? (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => void handleAcknowledge(alert.id)}
                          className="h-8 gap-1 text-xs"
                          title="Silence and acknowledge this alert"
                        >
                          <Check className="h-3.5 w-3.5 text-primary" />
                          <span>Acknowledge</span>
                        </Button>
                      ) : (
                        <Badge variant="secondary" className="gap-1 text-[11px] font-normal">
                          <Check className="h-3 w-3 text-muted-foreground" />
                          Cleared
                        </Badge>
                      )}
                    </div>
                  </div>

                  {/* Operational Context Banner */}
                  <div className="rounded-lg border border-border/70 bg-muted/20 p-3 text-xs">
                    <p className="text-foreground font-medium leading-relaxed">
                      {alert.message}
                    </p>
                  </div>

                  {/* AI Evidence Metrics Grid */}
                  {incident ? (
                    <div className="grid gap-3 sm:grid-cols-3 text-xs">
                      <div className="rounded-lg border border-border/60 bg-card p-3 space-y-1">
                        <span className="text-muted-foreground font-medium block">
                          AI Verification Confidence
                        </span>
                        <div className="flex items-center gap-2">
                          <div className="flex-1 bg-muted rounded-full h-2 overflow-hidden">
                            <div
                              className={`h-full rounded-full ${
                                confidencePct && confidencePct >= 85 ? 'bg-rose-500' : 'bg-amber-500'
                              }`}
                              style={{ width: `${confidencePct || 0}%` }}
                            />
                          </div>
                          <span className="font-mono font-bold text-sm text-foreground">
                            {confidencePct}%
                          </span>
                        </div>
                      </div>

                      <div className="rounded-lg border border-border/60 bg-card p-3 space-y-1">
                        <span className="text-muted-foreground font-medium block">
                          Detection Pathway
                        </span>
                        <p className="font-semibold text-foreground">
                          {isCollision
                            ? 'Dynamic Collision Path (P1)'
                            : 'High-Confidence Aftermath (P2)'}
                        </p>
                      </div>

                      <div className="rounded-lg border border-border/60 bg-card p-3 space-y-1">
                        <span className="text-muted-foreground font-medium block">
                          Current Incident State
                        </span>
                        <p className="font-semibold text-foreground">
                          {incident.state.replace('_', ' ')}
                        </p>
                      </div>
                    </div>
                  ) : null}

                  {/* Technical Identifiers Collapsible Drawer */}
                  <div className="pt-2 border-t border-border/50">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => toggleTech(alert.id)}
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
                              Alert ID
                            </span>
                            <span className="text-foreground truncate select-all">{alert.id}</span>
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => copyToClipboard(alert.id, 'Alert ID')}
                            className="h-6 w-6 p-0 shrink-0"
                            title="Copy Alert ID"
                          >
                            <Copy className="h-3 w-3 text-muted-foreground" />
                          </Button>
                        </div>

                        {alert.incidentId ? (
                          <div className="flex items-center justify-between gap-2">
                            <div className="truncate">
                              <span className="text-[10px] uppercase text-muted-foreground block">
                                Incident UUID
                              </span>
                              <span className="text-foreground truncate select-all">{alert.incidentId}</span>
                            </div>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => copyToClipboard(alert.incidentId!, 'Incident UUID')}
                              className="h-6 w-6 p-0 shrink-0"
                              title="Copy Incident UUID"
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
    </div>
  )
}
