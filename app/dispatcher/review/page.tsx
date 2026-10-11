'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Camera,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  ExternalLink,
  FilterX,
  Flame,
  Layers,
  MapPin,
  Minus,
  Radio,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Timer,
  User,
  UserCheck,
  X,
  XCircle,
} from 'lucide-react'

import { useAuth } from '@/components/auth-provider'
import { PageHeading } from '@/components/page-heading'
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
import {
  phase3,
  type OperationalIncident,
  type ResponderPresence,
} from '@/lib/phase3-api'

type ReviewTab = 'all' | 'temporal' | 'aftermath' | 'claimed'
type PriorityLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'

const FALSE_ALARM_PRESETS = [
  'Heavy Traffic Congestion / Slow Flow',
  'Roadside Hazard / Maintenance Vehicle',
  'Optical Glare / Camera Sensor Shadow',
  'Normal Pedestrian / Cyclist Movement',
]

function formatIncidentToken(id: string): string {
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
    if (sec < 60) return 'Just now'
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

export default function ReviewQueuePage() {
  const { profile } = useAuth()
  const { toast } = useToast()

  const [incidents, setIncidents] = useState<OperationalIncident[]>([])
  const [responders, setResponders] = useState<ResponderPresence[]>([])
  const [claimedId, setClaimedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  // Form State for Active Review
  const [selectedPriority, setSelectedPriority] = useState<PriorityLevel>('HIGH')
  const [incidentType, setIncidentType] = useState('Vehicle Collision')
  const [responderId, setResponderId] = useState('')
  const [dispatcherNotes, setDispatcherNotes] = useState('')
  const [falseAlarmReason, setFalseAlarmReason] = useState('')

  // Confirmation Modals
  const [confirmModalOpen, setConfirmModalOpen] = useState(false)
  const [falseAlarmModalOpen, setFalseAlarmModalOpen] = useState(false)

  // Filters & Search
  const [activeTab, setActiveTab] = useState<ReviewTab>('all')
  const [search, setSearch] = useState('')

  const loadData = useCallback(async (isManual = false) => {
    if (isManual) setRefreshing(true)
    else setLoading(true)
    setError('')
    try {
      const [incidentsRes, respondersRes] = await Promise.all([
        phase3.incidents(),
        phase3.responders(),
      ])
      setIncidents(incidentsRes.incidents ?? [])
      setResponders(respondersRes.responders ?? [])

      // Select first available responder by default if none selected
      const available = respondersRes.responders?.find(
        (r) => r.availabilityStatus === 'AVAILABLE' && r.presenceStatus === 'ONLINE'
      )
      if (available && !responderId) {
        setResponderId(available.uid)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to synchronize review queue.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [responderId])

  useEffect(() => {
    void loadData()
  }, [loadData])

  // Periodic polling for new AI detections & responder presence
  useEffect(() => {
    const timer = setInterval(() => {
      void loadData(false)
    }, 20_000)
    return () => clearInterval(timer)
  }, [loadData])

  // Filter for pending / under review queue only
  const pendingQueue = useMemo(() => {
    return incidents.filter(
      (item) => item.reviewStatus === 'PENDING_REVIEW' || item.reviewStatus === 'UNDER_REVIEW'
    )
  }, [incidents])

  // Summary Metrics
  const metrics = useMemo(() => {
    const totalPending = pendingQueue.filter((i) => i.reviewStatus === 'PENDING_REVIEW').length
    const underReview = pendingQueue.filter((i) => i.reviewStatus === 'UNDER_REVIEW').length
    const collisions = pendingQueue.filter((i) => i.detectionMode === 'temporal_collision').length
    const onlineResponders = responders.filter(
      (r) => r.presenceStatus === 'ONLINE' && r.availabilityStatus === 'AVAILABLE'
    ).length

    return { totalPending, underReview, collisions, onlineResponders }
  }, [pendingQueue, responders])

  // Filtered Queue
  const filteredQueue = useMemo(() => {
    const q = search.trim().toLowerCase()

    return pendingQueue.filter((item) => {
      // Tab filter
      if (activeTab === 'temporal' && item.detectionMode !== 'temporal_collision') return false
      if (activeTab === 'aftermath' && item.detectionMode !== 'aftermath_review') return false
      if (activeTab === 'claimed' && claimedId !== item.id) return false

      // Search
      if (q) {
        const token = formatIncidentToken(item.id).toLowerCase()
        const loc = (item.location ?? '').toLowerCase()
        const mode = item.detectionMode.toLowerCase()
        if (!token.includes(q) && !loc.includes(q) && !mode.includes(q)) return false
      }

      return true
    })
  }, [pendingQueue, activeTab, search, claimedId])

  // Claim an incident lease
  const handleClaim = async (incident: OperationalIncident) => {
    setError('')
    try {
      await phase3.claim(incident.id)
      setClaimedId(incident.id)
      // Set sensible defaults based on detection
      setSelectedPriority(incident.detectionMode === 'temporal_collision' ? 'CRITICAL' : 'HIGH')
      setIncidentType(incident.incidentType || 'Vehicle Collision')
      setDispatcherNotes('')
      setFalseAlarmReason('')
      toast({
        title: 'Review case claimed',
        description: `Case ${formatIncidentToken(incident.id)} locked for your review.`,
      })
      await loadData(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Claim lease failed. Case may be held by another operator.')
    }
  }

  // Release claim without decision
  const handleReleaseClaim = () => {
    setClaimedId(null)
    setDispatcherNotes('')
    setFalseAlarmReason('')
    toast({
      title: 'Review case released',
      description: 'Incident returned to general dispatch review queue.',
    })
  }

  // Execute Confirmation & Dispatch
  const executeConfirmAndDispatch = async () => {
    if (!claimedId) return
    setSubmitting(true)
    setError('')
    try {
      await phase3.review(claimedId, {
        decision: 'CONFIRMED',
        priority: selectedPriority,
        incidentType: incidentType.trim() || 'Vehicle Collision',
        notes: dispatcherNotes.trim() || null,
      })

      if (responderId) {
        await phase3.assign(claimedId, responderId)
        const unit = responders.find((r) => r.uid === responderId)
        toast({
          title: 'Incident confirmed & unit dispatched',
          description: `Dispatched ${unit?.displayName || 'unit'} to ${formatIncidentToken(claimedId)}.`,
        })
      } else {
        toast({
          title: 'Incident confirmed',
          description: `Incident ${formatIncidentToken(claimedId)} logged without unit assignment.`,
        })
      }

      setConfirmModalOpen(false)
      setClaimedId(null)
      await loadData(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to confirm incident.')
    } finally {
      setSubmitting(false)
    }
  }

  // Execute False Alarm
  const executeFalseAlarm = async () => {
    if (!claimedId || !falseAlarmReason.trim()) return
    setSubmitting(true)
    setError('')
    try {
      await phase3.review(claimedId, {
        decision: 'FALSE_ALARM',
        falseAlarmReason: falseAlarmReason.trim(),
        notes: dispatcherNotes.trim() || null,
      })

      toast({
        title: 'Marked as false alarm',
        description: `Incident ${formatIncidentToken(claimedId)} dismissed with reason: ${falseAlarmReason}.`,
      })

      setFalseAlarmModalOpen(false)
      setClaimedId(null)
      setFalseAlarmReason('')
      await loadData(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to record false alarm.')
    } finally {
      setSubmitting(false)
    }
  }

  const activeIncident = useMemo(() => {
    return incidents.find((i) => i.id === claimedId)
  }, [incidents, claimedId])

  const assignedResponder = useMemo(() => {
    return responders.find((r) => r.uid === responderId)
  }, [responders, responderId])

  return (
    <div className="space-y-6">
      {/* Page Heading */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
                Incident Review Queue
              </h1>
              <p className="text-sm text-muted-foreground">
                Triage AI-detected vehicle collisions, claim verification locks, and dispatch units in real time.
              </p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => void loadData(true)}
            disabled={refreshing || loading}
            className="h-9 gap-1.5 text-xs"
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            <span>Refresh Queue</span>
          </Button>
        </div>
      </div>

      {/* Error Alert */}
      {error ? (
        <Card className="border-destructive/30 bg-destructive/5 p-4 text-destructive shadow-xs">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="font-semibold text-sm">Review Operation Failed</p>
              <p className="text-xs opacity-90">{error}</p>
            </div>
          </div>
        </Card>
      ) : null}

      {/* Summary KPI Metric Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 sm:gap-4">
        <Card
          onClick={() => setActiveTab('all')}
          className={`cursor-pointer border p-4 shadow-xs transition-colors hover:border-primary/50 ${
            activeTab === 'all' ? 'border-primary/60 bg-primary/[0.02]' : 'border-border bg-card'
          }`}
        >
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Pending Triage
          </p>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="font-mono text-2xl font-bold text-foreground">
              {loading ? '—' : metrics.totalPending}
            </span>
            {metrics.totalPending > 0 ? (
              <span className="flex h-2 w-2 rounded-full bg-amber-500 animate-pulse" />
            ) : null}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">Awaiting dispatcher claim</p>
        </Card>

        <Card
          onClick={() => setActiveTab('temporal')}
          className={`cursor-pointer border p-4 shadow-xs transition-colors hover:border-primary/50 ${
            activeTab === 'temporal' ? 'border-rose-500/60 bg-rose-500/[0.02]' : 'border-border bg-card'
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
          onClick={() => setActiveTab('aftermath')}
          className={`cursor-pointer border p-4 shadow-xs transition-colors hover:border-primary/50 ${
            activeTab === 'aftermath' ? 'border-amber-500/60 bg-amber-500/[0.02]' : 'border-border bg-card'
          }`}
        >
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Aftermath Scenes
          </p>
          <p className="mt-1 font-mono text-2xl font-bold text-amber-600 dark:text-amber-400">
            {loading ? '—' : pendingQueue.length - metrics.collisions}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">Priority 2 stationary wreckage</p>
        </Card>

        <Card className="border border-border bg-card p-4 shadow-xs">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground flex items-center gap-1">
            <Radio className="h-3.5 w-3.5 text-primary" />
            Available Units
          </p>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="font-mono text-2xl font-bold text-primary">
              {loading ? '—' : metrics.onlineResponders}
            </span>
            <span className="text-xs text-muted-foreground">
              of {responders.length} registered
            </span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">Online & ready for dispatch</p>
        </Card>
      </div>

      {/* Toolbar: Segmented Tabs + Omni-Search */}
      <Card className="border border-border bg-card p-4 shadow-xs space-y-3">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
            <Button
              variant={activeTab === 'all' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setActiveTab('all')}
              className="h-8 text-xs font-medium"
            >
              All Queue ({pendingQueue.length})
            </Button>
            <Button
              variant={activeTab === 'temporal' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setActiveTab('temporal')}
              className="h-8 text-xs font-medium gap-1"
            >
              <Flame className="h-3 w-3 text-rose-500" />
              Collisions ({metrics.collisions})
            </Button>
            <Button
              variant={activeTab === 'aftermath' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setActiveTab('aftermath')}
              className="h-8 text-xs font-medium"
            >
              Aftermaths ({pendingQueue.length - metrics.collisions})
            </Button>
            {claimedId ? (
              <Button
                variant={activeTab === 'claimed' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setActiveTab('claimed')}
                className="h-8 text-xs font-medium gap-1 text-primary border-primary/40"
              >
                <Timer className="h-3 w-3" />
                Active Claim (1)
              </Button>
            ) : null}
          </div>

          <div className="relative md:w-72">
            <Search className="absolute left-2.5 top-2 h-4 w-4 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search INC token, camera, or road..."
              className="pl-8 h-8 text-xs"
              aria-label="Search review queue"
            />
          </div>
        </div>
      </Card>

      {/* Review Queue Items */}
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
        ) : filteredQueue.length === 0 ? (
          <Card className="border border-border bg-card p-12 text-center shadow-xs">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
              {search.trim() ? <FilterX className="h-6 w-6" /> : <ShieldCheck className="h-6 w-6" />}
            </div>
            <h3 className="mt-4 text-base font-semibold text-foreground">
              {search.trim() ? 'No matching crash cases' : 'Review Queue Clear'}
            </h3>
            <p className="mt-1 text-sm text-muted-foreground max-w-sm mx-auto">
              {search.trim()
                ? 'Try adjusting your search query or switching tabs.'
                : 'All detected vehicle events have been verified or resolved. New detections will appear automatically.'}
            </p>
            {search.trim() ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSearch('')}
                className="mt-4 text-xs"
              >
                Clear search
              </Button>
            ) : null}
          </Card>
        ) : (
          filteredQueue.map((incident) => {
            const isClaimedByMe = claimedId === incident.id
            const isUnderReviewByOther =
              incident.reviewStatus === 'UNDER_REVIEW' && !isClaimedByMe
            const token = formatIncidentToken(incident.id)
            const confidencePct = Math.round(incident.aiScore * 100)
            const isCollision = incident.detectionMode === 'temporal_collision'

            return (
              <Card
                key={incident.id}
                className={`border bg-card transition-all shadow-xs overflow-hidden ${
                  isClaimedByMe
                    ? 'border-2 border-primary ring-2 ring-primary/20'
                    : isCollision
                    ? 'border-rose-200 dark:border-rose-950/80 hover:border-rose-300'
                    : 'border-border hover:border-border/80'
                }`}
              >
                <div className="p-5 space-y-4">
                  {/* Top Bar: Token, Dual-Path Urgency Tag & Time */}
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between border-b border-border/50 pb-3">
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-bold text-lg text-foreground font-mono">
                          {token}
                        </span>

                        {isCollision ? (
                          <Badge
                            variant="outline"
                            className="gap-1 bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800 text-xs font-bold"
                          >
                            <Flame className="h-3 w-3" />
                            Priority 1 · Confirmed Collision
                          </Badge>
                        ) : (
                          <Badge
                            variant="outline"
                            className="gap-1 bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800 text-xs font-semibold"
                          >
                            <ShieldAlert className="h-3 w-3" />
                            Priority 2 · Possible Crash Aftermath
                          </Badge>
                        )}

                        <span className="text-xs text-muted-foreground">· Detected {formatRelativeTime(incident.detectedAt)}</span>
                      </div>

                      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                        <MapPin className="h-3.5 w-3.5 text-primary shrink-0" />
                        <span className="font-medium text-foreground truncate">
                          {incident.location || 'Location Coordinates Logged'}
                        </span>
                        {incident.latitude && incident.longitude ? (
                          <span className="font-mono text-[11px] opacity-80">
                            ({incident.latitude.toFixed(4)}°, {incident.longitude.toFixed(4)}°)
                          </span>
                        ) : null}
                      </p>
                    </div>

                    {/* Claim Button / Status */}
                    <div className="flex items-center gap-2">
                      {isClaimedByMe ? (
                        <div className="flex items-center gap-2">
                          <Badge className="bg-primary text-primary-foreground gap-1 px-2.5 py-1 text-xs font-semibold">
                            <Timer className="h-3 w-3 animate-spin" />
                            Claim Active
                          </Badge>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleReleaseClaim}
                            className="h-7 text-xs text-muted-foreground hover:text-foreground"
                          >
                            Release
                          </Button>
                        </div>
                      ) : isUnderReviewByOther ? (
                        <Badge
                          variant="secondary"
                          className="gap-1 bg-muted text-muted-foreground text-xs"
                        >
                          <Clock className="h-3 w-3" />
                          Locked by Operator
                        </Badge>
                      ) : (
                        <Button
                          size="sm"
                          onClick={() => void handleClaim(incident)}
                          className="h-8 gap-1.5 text-xs font-semibold"
                        >
                          <span>Claim Review</span>
                          <ArrowRight className="h-3.5 w-3.5" />
                        </Button>
                      )}
                    </div>
                  </div>

                  {/* Incident AI Evidence Gauge & Details Grid */}
                  <div className="grid gap-3 sm:grid-cols-3 text-xs">
                    <div className="rounded-lg border border-border/60 bg-muted/20 p-3 space-y-1.5">
                      <span className="text-muted-foreground font-medium block">AI Verification Score</span>
                      <div className="flex items-center gap-2">
                        <div className="flex-1 bg-muted rounded-full h-2 overflow-hidden">
                          <div
                            className={`h-full rounded-full ${
                              confidencePct >= 85 ? 'bg-rose-500' : 'bg-amber-500'
                            }`}
                            style={{ width: `${confidencePct}%` }}
                          />
                        </div>
                        <span className="font-mono font-bold text-sm text-foreground">
                          {confidencePct}%
                        </span>
                      </div>
                      <span className="text-[10px] text-muted-foreground block">
                        Dual-Path confidence metric
                      </span>
                    </div>

                    <div className="rounded-lg border border-border/60 bg-muted/20 p-3 space-y-1">
                      <span className="text-muted-foreground font-medium block">Detection Mechanism</span>
                      <p className="font-semibold text-foreground">
                        {isCollision
                          ? 'Temporal Collision Path'
                          : 'High-Confidence Aftermath'}
                      </p>
                      <p className="text-[10px] text-muted-foreground">
                        {isCollision ? 'Live collision in motion' : 'Stationary post-impact scene'}
                      </p>
                    </div>

                    <div className="rounded-lg border border-border/60 bg-muted/20 p-3 space-y-1">
                      <span className="text-muted-foreground font-medium block">Dispatch Queue Status</span>
                      <p className="font-semibold text-foreground">
                        {incident.reviewStatus.replace('_', ' ')}
                      </p>
                      <p className="text-[10px] text-muted-foreground">
                        Current workflow stage
                      </p>
                    </div>
                  </div>

                  {/* ACTIVE CLAIM WORKSPACE: Visible only when this incident is claimed by the current operator */}
                  {isClaimedByMe && (
                    <div className="mt-4 rounded-xl border border-primary/40 bg-primary/[0.015] p-4 sm:p-5 space-y-5">
                      <div className="flex items-center justify-between border-b border-border/60 pb-3">
                        <div className="flex items-center gap-2">
                          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
                            <CheckCircle2 className="h-4 w-4" />
                          </div>
                          <div>
                            <h4 className="font-bold text-sm text-foreground">
                              Triage & Dispatch Workspace
                            </h4>
                            <p className="text-xs text-muted-foreground">
                              Confirm incident and assign available units, or reject as a false alarm.
                            </p>
                          </div>
                        </div>
                        <Badge variant="outline" className="font-mono text-[11px] text-primary border-primary/30">
                          15m Single-Winner Lease Active
                        </Badge>
                      </div>

                      {/* Step 1: Emergency Priority Level */}
                      <div className="space-y-2">
                        <label className="text-xs font-semibold text-foreground block">
                          1. Assign Operational Priority:
                        </label>
                        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                          {(['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as PriorityLevel[]).map((p) => {
                            const active = selectedPriority === p
                            let badgeStyles = 'border-border text-muted-foreground'
                            if (active) {
                              if (p === 'CRITICAL') badgeStyles = 'border-rose-600 bg-rose-50 text-rose-700 dark:bg-rose-950 font-bold'
                              else if (p === 'HIGH') badgeStyles = 'border-orange-500 bg-orange-50 text-orange-700 dark:bg-orange-950 font-semibold'
                              else if (p === 'MEDIUM') badgeStyles = 'border-amber-500 bg-amber-50 text-amber-700 dark:bg-amber-950 font-semibold'
                              else badgeStyles = 'border-slate-500 bg-slate-100 text-slate-700 dark:bg-slate-900 font-semibold'
                            }
                            return (
                              <button
                                key={p}
                                type="button"
                                onClick={() => setSelectedPriority(p)}
                                className={`flex items-center justify-center gap-1.5 rounded-lg border py-2 text-xs transition-all ${badgeStyles}`}
                              >
                                {p === 'CRITICAL' ? <AlertTriangle className="h-3.5 w-3.5 text-rose-600" /> : null}
                                {p}
                              </button>
                            )
                          })}
                        </div>
                      </div>

                      {/* Step 2: Incident Type & Unit Selection */}
                      <div className="grid gap-4 sm:grid-cols-2">
                        <div className="space-y-1.5">
                          <label className="text-xs font-semibold text-foreground block">
                            2. Incident Classification:
                          </label>
                          <Input
                            value={incidentType}
                            onChange={(e) => setIncidentType(e.target.value)}
                            placeholder="e.g. Vehicle Collision, Motorcycle Slide"
                            className="h-9 text-xs"
                          />
                        </div>

                        <div className="space-y-1.5">
                          <label className="text-xs font-semibold text-foreground block">
                            3. Immediate Unit Assignment:
                          </label>
                          <Select
                            value={responderId}
                            onValueChange={(val) => setResponderId(val)}
                          >
                            <SelectTrigger className="h-9 text-xs">
                              <SelectValue placeholder="Select Available Unit..." />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="unassigned">
                                Confirm Without Assignment (Hold in Queue)
                              </SelectItem>
                              {responders.map((r) => {
                                const isOnline = r.presenceStatus === 'ONLINE'
                                const isAvail = r.availabilityStatus === 'AVAILABLE'
                                return (
                                  <SelectItem key={r.uid} value={r.uid}>
                                    <div className="flex items-center gap-2">
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
                      </div>

                      {/* Optional Dispatcher Notes */}
                      <div className="space-y-1.5">
                        <label className="text-xs font-semibold text-muted-foreground block">
                          Dispatcher Operational Notes (Optional):
                        </label>
                        <Input
                          value={dispatcherNotes}
                          onChange={(e) => setDispatcherNotes(e.target.value)}
                          placeholder="e.g. 2 vehicles involved in northbound lane, ambulance needed urgently"
                          className="h-9 text-xs"
                        />
                      </div>

                      {/* Action Decision Buttons */}
                      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pt-3 border-t border-border/60">
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => setFalseAlarmModalOpen(true)}
                          className="h-9 gap-1.5 text-xs bg-rose-600 hover:bg-rose-700"
                        >
                          <XCircle className="h-4 w-4" />
                          <span>Reject as False Alarm</span>
                        </Button>

                        <div className="flex items-center gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleReleaseClaim}
                            className="h-9 text-xs text-muted-foreground hover:text-foreground"
                          >
                            Cancel
                          </Button>

                          <Button
                            size="sm"
                            onClick={() => setConfirmModalOpen(true)}
                            className="h-9 gap-1.5 text-xs font-semibold bg-primary hover:bg-primary/90"
                          >
                            <Check className="h-4 w-4" />
                            <span>Confirm & Dispatch Unit</span>
                          </Button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </Card>
            )
          })
        )}
      </div>

      {/* CONFIRMATION MODAL: Replaces raw window.confirm */}
      <AlertDialog open={confirmModalOpen} onOpenChange={setConfirmModalOpen}>
        <AlertDialogContent className="sm:max-w-md">
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-primary" />
              Confirm Emergency Incident
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-3 pt-2 text-xs text-foreground">
                <p>
                  You are about to verify and publish an emergency incident for{' '}
                  <span className="font-bold text-foreground">
                    {activeIncident ? formatIncidentToken(activeIncident.id) : ''}
                  </span>.
                </p>

                <div className="rounded-lg border border-border bg-muted/40 p-3 space-y-1.5 font-mono">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground font-sans">Priority:</span>
                    <span className="font-bold text-rose-600">{selectedPriority}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground font-sans">Incident Type:</span>
                    <span className="font-semibold text-foreground">{incidentType}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground font-sans">Assigned Unit:</span>
                    <span className="font-semibold text-primary">
                      {assignedResponder ? assignedResponder.displayName : 'Held in Unassigned Queue'}
                    </span>
                  </div>
                  {dispatcherNotes ? (
                    <div className="pt-1 border-t border-border/40 font-sans text-muted-foreground">
                      <span className="font-semibold">Notes:</span> {dispatcherNotes}
                    </div>
                  ) : null}
                </div>

                <p className="text-muted-foreground">
                  This action will alert emergency responders and mark the crash as active.
                </p>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={submitting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={submitting}
              onClick={() => void executeConfirmAndDispatch()}
              className="bg-primary hover:bg-primary/90"
            >
              {submitting ? 'Confirming…' : 'Confirm & Dispatch'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* FALSE ALARM MODAL: Fast Reason Presets + Verification */}
      <AlertDialog open={falseAlarmModalOpen} onOpenChange={setFalseAlarmModalOpen}>
        <AlertDialogContent className="sm:max-w-md">
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2 text-rose-600">
              <AlertTriangle className="h-5 w-5" />
              Mark as False Alarm
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-3 pt-2 text-xs text-foreground">
                <p>
                  A verified false-alarm reason is strictly required to dismiss{' '}
                  <span className="font-bold text-foreground">
                    {activeIncident ? formatIncidentToken(activeIncident.id) : ''}
                  </span>.
                </p>

                {/* Quick Presets */}
                <div className="space-y-1.5">
                  <span className="text-muted-foreground font-semibold block text-[11px]">
                    Select Quick Reason:
                  </span>
                  <div className="grid gap-1.5">
                    {FALSE_ALARM_PRESETS.map((preset) => (
                      <button
                        key={preset}
                        type="button"
                        onClick={() => setFalseAlarmReason(preset)}
                        className={`text-left text-xs p-2 rounded-md border transition-all ${
                          falseAlarmReason === preset
                            ? 'border-rose-500 bg-rose-50 text-rose-900 dark:bg-rose-950 font-semibold'
                            : 'border-border bg-card hover:bg-muted/40 text-foreground'
                        }`}
                      >
                        {preset}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Custom / Editable Reason */}
                <div className="space-y-1">
                  <span className="text-muted-foreground font-semibold block text-[11px]">
                    Reason Description (Required):
                  </span>
                  <Input
                    value={falseAlarmReason}
                    onChange={(e) => setFalseAlarmReason(e.target.value)}
                    placeholder="Enter or refine reason for false alarm..."
                    className="h-9 text-xs"
                  />
                </div>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={submitting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={submitting || !falseAlarmReason.trim()}
              onClick={() => void executeFalseAlarm()}
              className="bg-rose-600 hover:bg-rose-700"
            >
              {submitting ? 'Recording…' : 'Dismiss as False Alarm'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
