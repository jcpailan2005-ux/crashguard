'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Camera,
  CheckCircle2,
  Clock,
  ExternalLink,
  Flame,
  Layers,
  MapPin,
  Radio,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Timer,
  User,
  Users,
  Video,
  Wifi,
  WifiOff,
} from 'lucide-react'

import {
  phase3,
  type OperationalIncident,
  type OperationalNotification,
  type ResponderPresence,
} from '@/lib/phase3-api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

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

export default function DispatcherHome() {
  const [incidents, setIncidents] = useState<OperationalIncident[]>([])
  const [responders, setResponders] = useState<ResponderPresence[]>([])
  const [notifications, setNotifications] = useState<OperationalNotification[]>([])
  const [cameras, setCameras] = useState<Array<Record<string, unknown>>>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')

  // Queue View Tab in Dashboard
  const [queueTab, setQueueTab] = useState<'pending' | 'active'>('pending')

  const loadData = useCallback(async (isManual = false) => {
    if (isManual) setRefreshing(true)
    else setLoading(true)
    setError('')
    try {
      const [incRes, respRes, notifRes, camRes] = await Promise.all([
        phase3.incidents(),
        phase3.responders(),
        phase3.notifications(),
        phase3.cameras().catch(() => ({ cameras: [] })),
      ])
      setIncidents(incRes.incidents ?? [])
      setResponders(respRes.responders ?? [])
      setNotifications(notifRes.notifications ?? [])
      setCameras(camRes.cameras ?? [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to synchronize command center data.')
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

  // Calculated Metrics
  const pendingCases = useMemo(() => {
    return incidents.filter(
      (i) => i.reviewStatus === 'PENDING_REVIEW' || i.reviewStatus === 'UNDER_REVIEW'
    )
  }, [incidents])

  const activeResponses = useMemo(() => {
    return incidents.filter(
      (i) => i.state === 'ACTIVE_RESPONSE' || i.state === 'CONFIRMED'
    )
  }, [incidents])

  const temporalCollisionsCount = useMemo(() => {
    return pendingCases.filter((i) => i.detectionMode === 'temporal_collision').length
  }, [pendingCases])

  const onlineResponders = useMemo(() => {
    return responders.filter((r) => r.presenceStatus === 'ONLINE')
  }, [responders])

  const availableResponders = useMemo(() => {
    return onlineResponders.filter((r) => r.availabilityStatus === 'AVAILABLE')
  }, [onlineResponders])

  // Incoming Urgent Alerts (Unread crash reviews or declined assignments)
  const urgentAlerts = useMemo(() => {
    return notifications.filter(
      (n) => !n.readAt && (n.type === 'NEW_CRASH_REVIEW' || n.type === 'ASSIGNMENT_DECLINED')
    )
  }, [notifications])

  return (
    <div className="space-y-6">
      {/* Command Operations Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Activity className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
                  Operations Command Hub
                </h1>
                <Badge
                  variant="outline"
                  className="bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 font-mono text-[10px] tracking-wider uppercase font-bold"
                >
                  ● Active Monitor
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground">
                Central emergency coordination desk for AI collision triage, fleet dispatch, and camera telemetry.
              </p>
            </div>
          </div>
        </div>

        {/* Quick Launch Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          <Button asChild variant="outline" size="sm" className="h-9 gap-1.5 text-xs">
            <Link href="/dispatcher/alerts">
              <AlertTriangle className="h-3.5 w-3.5 text-rose-500" />
              <span>Alerts Feed</span>
              {urgentAlerts.length > 0 ? (
                <span className="rounded-full bg-rose-500 text-white px-1.5 py-0.2 text-[10px] font-bold">
                  {urgentAlerts.length}
                </span>
              ) : null}
            </Link>
          </Button>

          <Button asChild size="sm" className="h-9 gap-1.5 text-xs bg-primary hover:bg-primary/90">
            <Link href="/dispatcher/review">
              <ShieldCheck className="h-4 w-4" />
              <span>Review Queue</span>
              {pendingCases.length > 0 ? (
                <span className="rounded-full bg-white/20 px-1.5 py-0.2 text-[10px] font-bold">
                  {pendingCases.length}
                </span>
              ) : null}
            </Link>
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => void loadData(true)}
            disabled={refreshing || loading}
            className="h-9 gap-1 text-xs"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {/* Error Alert */}
      {error ? (
        <Card className="border-destructive/30 bg-destructive/5 p-4 text-destructive shadow-xs">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="font-semibold text-sm">Telemetry Feed Disrupted</p>
              <p className="text-xs opacity-90">{error}</p>
            </div>
          </div>
        </Card>
      ) : null}

      {/* Incoming Critical Alert Ticker Banner */}
      {urgentAlerts.length > 0 ? (
        <div className="rounded-lg border-2 border-rose-500/80 bg-rose-50/90 dark:bg-rose-950/40 p-4 shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div className="flex items-start sm:items-center gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-rose-600 text-white animate-pulse">
                <Flame className="h-5 w-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-bold text-sm text-rose-950 dark:text-rose-200">
                    {urgentAlerts.length} URGENT EMERGENCY ALERT{urgentAlerts.length === 1 ? '' : 'S'}
                  </span>
                  <span className="text-xs text-rose-700 dark:text-rose-300 font-medium">
                    · Immediate Dispatcher Action Required
                  </span>
                </div>
                <p className="text-xs text-rose-900/90 dark:text-rose-200/90 mt-0.5">
                  {urgentAlerts[0]?.title}: {urgentAlerts[0]?.message}
                </p>
              </div>
            </div>

            <Button asChild size="sm" className="h-8 gap-1.5 text-xs bg-rose-600 hover:bg-rose-700 text-white shrink-0 font-semibold">
              <Link href="/dispatcher/review">
                <span>Triage Incident Now</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </Button>
          </div>
        </div>
      ) : null}

      {/* Core Operational KPI Metrics Grid (4 Primary Cards) */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 sm:gap-4">
        {/* Metric 1: Pending Reviews */}
        <Card className="border border-border bg-card p-4 shadow-xs">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span className="font-medium uppercase tracking-wider">Pending Triage</span>
            <ShieldAlert className="h-4 w-4 text-amber-500" />
          </div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="font-mono text-2xl font-bold text-foreground">
              {loading ? '—' : pendingCases.length}
            </span>
            {temporalCollisionsCount > 0 ? (
              <Badge className="bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950 text-[10px] font-bold gap-1">
                <Flame className="h-2.5 w-2.5" />
                {temporalCollisionsCount} P1
              </Badge>
            ) : null}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">Unclaimed collision cases</p>
        </Card>

        {/* Metric 2: Active Responses */}
        <Card className="border border-border bg-card p-4 shadow-xs">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span className="font-medium uppercase tracking-wider">Active Responses</span>
            <Activity className="h-4 w-4 text-primary" />
          </div>
          <p className="mt-1 font-mono text-2xl font-bold text-foreground">
            {loading ? '—' : activeResponses.length}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">Units deployed on-scene</p>
        </Card>

        {/* Metric 3: Responder Fleet Readiness */}
        <Card className="border border-border bg-card p-4 shadow-xs">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span className="font-medium uppercase tracking-wider">Fleet Readiness</span>
            <Radio className="h-4 w-4 text-primary" />
          </div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="font-mono text-2xl font-bold text-emerald-600 dark:text-emerald-400">
              {loading ? '—' : availableResponders.length}
            </span>
            <span className="text-xs text-muted-foreground">
              avail of {onlineResponders.length} online
            </span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">Ready for instant dispatch</p>
        </Card>

        {/* Metric 4: CCTV Telemetry */}
        <Card className="border border-border bg-card p-4 shadow-xs">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span className="font-medium uppercase tracking-wider">CCTV Streams</span>
            <Video className="h-4 w-4 text-primary" />
          </div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="font-mono text-2xl font-bold text-foreground">
              {loading ? '—' : cameras.length}
            </span>
            <Badge variant="outline" className="text-[10px] text-emerald-600 border-emerald-200">
              Active
            </Badge>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">Live detector camera feeds</p>
        </Card>
      </div>

      {/* Main Dual-Column Operational Workspace */}
      <div className="grid gap-6 lg:grid-cols-12">
        {/* Left Column (60% on desktop): Incidents & Review Queue */}
        <div className="space-y-4 lg:col-span-7">
          <Card className="border border-border bg-card shadow-xs">
            {/* Header & Segmented Switcher */}
            <div className="flex items-center justify-between border-b border-border/60 p-4">
              <div className="flex items-center gap-2">
                <Button
                  variant={queueTab === 'pending' ? 'default' : 'ghost'}
                  size="sm"
                  onClick={() => setQueueTab('pending')}
                  className="h-8 text-xs font-semibold"
                >
                  Pending Review ({pendingCases.length})
                </Button>
                <Button
                  variant={queueTab === 'active' ? 'default' : 'ghost'}
                  size="sm"
                  onClick={() => setQueueTab('active')}
                  className="h-8 text-xs font-semibold"
                >
                  Active Dispatches ({activeResponses.length})
                </Button>
              </div>

              <Button asChild variant="ghost" size="sm" className="h-7 text-xs text-muted-foreground hover:text-foreground gap-1">
                <Link href={queueTab === 'pending' ? '/dispatcher/review' : '/dispatcher/incidents'}>
                  <span>Full View</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </Button>
            </div>

            {/* List Content */}
            <div className="divide-y divide-border/60 p-2">
              {loading && incidents.length === 0 ? (
                <div className="p-6 text-center text-xs text-muted-foreground">
                  Synchronizing incident queue…
                </div>
              ) : queueTab === 'pending' ? (
                pendingCases.length === 0 ? (
                  <div className="p-8 text-center text-xs text-muted-foreground space-y-1">
                    <CheckCircle2 className="h-6 w-6 text-emerald-500 mx-auto mb-2" />
                    <p className="font-semibold text-sm text-foreground">Review Queue Clear</p>
                    <p>No crash candidates are awaiting verification.</p>
                  </div>
                ) : (
                  pendingCases.slice(0, 4).map((incident) => {
                    const token = formatIncidentToken(incident.id)
                    const isCollision = incident.detectionMode === 'temporal_collision'
                    const confidence = Math.round(incident.aiScore * 100)

                    return (
                      <div
                        key={incident.id}
                        className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-3 transition-colors hover:bg-muted/30 rounded-md"
                      >
                        <div className="space-y-1 min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-sm font-mono text-foreground">
                              {token}
                            </span>
                            {isCollision ? (
                              <Badge variant="outline" className="bg-rose-50 text-rose-700 border-rose-200 text-[10px] font-bold">
                                Priority 1 Collision
                              </Badge>
                            ) : (
                              <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200 text-[10px] font-medium">
                                Aftermath Scene
                              </Badge>
                            )}
                            <span className="text-[11px] text-muted-foreground">
                              · {confidence}% AI
                            </span>
                          </div>

                          <p className="text-xs text-muted-foreground flex items-center gap-1 truncate">
                            <MapPin className="h-3 w-3 text-primary shrink-0" />
                            <span className="truncate">{incident.location || 'Location Logged'}</span>
                          </p>
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          <span className="text-[11px] font-mono text-muted-foreground">
                            {formatRelativeTime(incident.detectedAt)}
                          </span>
                          <Button asChild size="sm" className="h-7 text-xs font-semibold">
                            <Link href="/dispatcher/review">
                              Triage
                            </Link>
                          </Button>
                        </div>
                      </div>
                    )
                  })
                )
              ) : (
                activeResponses.length === 0 ? (
                  <div className="p-8 text-center text-xs text-muted-foreground space-y-1">
                    <p className="font-semibold text-sm text-foreground">No Active Dispatches</p>
                    <p>No responders are currently deployed on-scene.</p>
                  </div>
                ) : (
                  activeResponses.slice(0, 4).map((incident) => {
                    const token = formatIncidentToken(incident.id)

                    return (
                      <div
                        key={incident.id}
                        className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-3 transition-colors hover:bg-muted/30 rounded-md"
                      >
                        <div className="space-y-1 min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-sm font-mono text-foreground">
                              {token}
                            </span>
                            <Badge variant="outline" className="bg-primary/10 text-primary border-primary/30 text-[10px] font-semibold">
                              {incident.state}
                            </Badge>
                          </div>
                          <p className="text-xs text-muted-foreground flex items-center gap-1 truncate">
                            <MapPin className="h-3 w-3 text-primary shrink-0" />
                            <span className="truncate">{incident.location || 'Location Logged'}</span>
                          </p>
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          <Badge variant="secondary" className="text-[11px]">
                            {incident.responderName ? `Unit: ${incident.responderName}` : 'Assigned Unit'}
                          </Badge>
                          <Button asChild variant="outline" size="sm" className="h-7 text-xs">
                            <Link href="/dispatcher/incidents">
                              Track
                            </Link>
                          </Button>
                        </div>
                      </div>
                    )
                  })
                )
              )}
            </div>
          </Card>

          {/* Quick Dispatcher Operations Shortcuts */}
          <div className="grid gap-3 sm:grid-cols-3">
            <Card className="p-4 border border-border bg-card shadow-xs transition-colors hover:border-primary/50">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-sm text-foreground">Live CCTV Monitor</span>
                <Video className="h-4 w-4 text-primary" />
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Observe continuous traffic feeds and AI bounding box telemetry.
              </p>
              <Button asChild variant="outline" size="sm" className="mt-3 w-full h-8 text-xs">
                <Link href="/dispatcher/live">Open Live Streams</Link>
              </Button>
            </Card>

            <Card className="p-4 border border-border bg-card shadow-xs transition-colors hover:border-primary/50">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-sm text-foreground">Incident Map</span>
                <MapPin className="h-4 w-4 text-primary" />
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Geographic spatial overview of active crash sites and cameras.
              </p>
              <Button asChild variant="outline" size="sm" className="mt-3 w-full h-8 text-xs">
                <Link href="/dispatcher/map">View GIS Map</Link>
              </Button>
            </Card>

            <Card className="p-4 border border-border bg-card shadow-xs transition-colors hover:border-primary/50">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-sm text-foreground">Response History</span>
                <Clock className="h-4 w-4 text-primary" />
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Audit past dispatches, arrival speeds, and resolution notes.
              </p>
              <Button asChild variant="outline" size="sm" className="mt-3 w-full h-8 text-xs">
                <Link href="/dispatcher/history">Open History</Link>
              </Button>
            </Card>
          </div>
        </div>

        {/* Right Column (40% on desktop): Fleet Board & Camera Telemetry */}
        <div className="space-y-4 lg:col-span-5">
          {/* Responder Fleet Presence Board */}
          <Card className="border border-border bg-card shadow-xs p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-border/60 pb-2.5">
              <div className="flex items-center gap-2">
                <Radio className="h-4 w-4 text-primary" />
                <h3 className="font-semibold text-sm text-foreground">
                  Responder Fleet Board
                </h3>
              </div>
              <Button asChild variant="ghost" size="sm" className="h-6 text-xs text-muted-foreground hover:text-foreground">
                <Link href="/dispatcher/responders">Manage</Link>
              </Button>
            </div>

            <div className="space-y-2">
              {responders.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-4">
                  No responders registered.
                </p>
              ) : (
                responders.slice(0, 5).map((r) => {
                  const isOnline = r.presenceStatus === 'ONLINE'
                  const isAvail = r.availabilityStatus === 'AVAILABLE'

                  return (
                    <div
                      key={r.uid}
                      className="flex items-center justify-between p-2 rounded-md bg-muted/20 border border-border/40 text-xs"
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <div
                          className={`h-2 w-2 rounded-full shrink-0 ${
                            isOnline ? 'bg-emerald-500' : 'bg-muted-foreground/40'
                          }`}
                        />
                        <div className="min-w-0">
                          <p className="font-semibold text-foreground truncate">
                            {r.displayName}
                          </p>
                          <p className="text-[10px] text-muted-foreground">
                            {r.areaId || 'Central Area'}
                          </p>
                        </div>
                      </div>

                      <Badge
                        variant="outline"
                        className={`text-[10px] font-semibold ${
                          isAvail
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300'
                            : isOnline
                            ? 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300'
                            : 'bg-muted text-muted-foreground'
                        }`}
                      >
                        {r.availabilityStatus || 'OFFLINE'}
                      </Badge>
                    </div>
                  )
                })
              )}
            </div>
          </Card>

          {/* CCTV Camera Telemetry Panel */}
          <Card className="border border-border bg-card shadow-xs p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-border/60 pb-2.5">
              <div className="flex items-center gap-2">
                <Camera className="h-4 w-4 text-primary" />
                <h3 className="font-semibold text-sm text-foreground">
                  CCTV Camera Network
                </h3>
              </div>
              <Badge variant="outline" className="font-mono text-[10px]">
                {cameras.length} Feeds
              </Badge>
            </div>

            <div className="space-y-2">
              {cameras.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-4">
                  No active CCTV cameras configured.
                </p>
              ) : (
                cameras.slice(0, 4).map((cam, idx) => {
                  const camName = String(cam.name || `Camera ${idx + 1}`)
                  const camLoc = String(cam.location || 'Intersection')
                  const fps = cam.fps ? `${cam.fps} FPS` : '30 FPS'

                  return (
                    <div
                      key={String(cam.id || idx)}
                      className="flex items-center justify-between p-2 rounded-md bg-muted/20 border border-border/40 text-xs"
                    >
                      <div className="space-y-0.5 min-w-0">
                        <p className="font-medium text-foreground truncate">{camName}</p>
                        <p className="text-[10px] text-muted-foreground truncate">{camLoc}</p>
                      </div>
                      <div className="text-right">
                        <Badge variant="secondary" className="text-[10px] font-mono">
                          {fps}
                        </Badge>
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
