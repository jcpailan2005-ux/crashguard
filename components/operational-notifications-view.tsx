'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import {
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
  Layers,
  Radio,
  RefreshCw,
  Search,
  ShieldAlert,
  X,
  XCircle,
} from 'lucide-react'

import { phase3, type OperationalNotification } from '@/lib/phase3-api'
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

type NotificationTab = 'all' | 'unread' | 'action_required' | 'read'

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
    if (sec < 60) return 'Just now'
    const min = Math.floor(sec / 60)
    if (min < 60) return `${min}m ago`
    const hours = Math.floor(min / 60)
    if (hours < 24) return `${hours}h ago`
    const days = Math.floor(hours / 24)
    if (days < 7) return `${days}d ago`
    return new Date(dateStr).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  } catch {
    return dateStr
  }
}

function formatExactDateTime(dateStr: string): string {
  try {
    const d = new Date(dateStr)
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return dateStr
  }
}

function cleanNotificationMessage(msg: string): {
  headline: string
  incidentToken: string | null
} {
  // If message contains UUID like "Incident e2de8328-7d5d-44ac... requires dispatcher review."
  const uuidMatch = msg.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i)
  if (uuidMatch) {
    const rawUuid = uuidMatch[0]
    const token = formatIncidentToken(rawUuid)
    const cleaned = msg.replace(rawUuid, token)
    return { headline: cleaned, incidentToken: token }
  }
  return { headline: msg, incidentToken: null }
}

const ACTION_REQUIRED_TYPES = new Set(['NEW_CRASH_REVIEW', 'NEW_ASSIGNMENT', 'ASSIGNMENT_DECLINED'])

export function OperationalNotificationsView({
  role,
  title,
  subtitle,
}: {
  role: 'dispatcher' | 'responder' | 'admin'
  title?: string
  subtitle?: string
}) {
  const { toast } = useToast()
  const [notifications, setNotifications] = useState<OperationalNotification[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [markingAll, setMarkingAll] = useState(false)
  const [error, setError] = useState('')

  // Filter States
  const [activeTab, setActiveTab] = useState<NotificationTab>('all')
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('ALL')

  // Expanded technical IDs (map of notification id -> boolean)
  const [expandedTech, setExpandedTech] = useState<Record<string, boolean>>({})

  const defaultTitle =
    title ??
    (role === 'dispatcher'
      ? 'Dispatcher Notifications'
      : role === 'responder'
      ? 'Responder Notifications'
      : 'System Notifications')

  const defaultSubtitle =
    subtitle ??
    (role === 'dispatcher'
      ? 'Real-time alert feed for AI crash detections, unit dispatch updates, and scene declines.'
      : role === 'responder'
      ? 'Live feed for incident assignments, dispatch milestones, and operational notices.'
      : 'Authoritative operational alerts and privileged system notifications.')

  const loadNotifications = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) setRefreshing(true)
    else setLoading(true)
    setError('')
    try {
      const res = await phase3.notifications()
      setNotifications(res.notifications ?? [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to synchronize notifications.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    void loadNotifications()
  }, [loadNotifications])

  // Mark a single notification as read
  const markAsRead = async (id: string) => {
    // Optimistic UI update
    setNotifications((current) =>
      current.map((item) => (item.id === id ? { ...item, readAt: new Date().toISOString() } : item))
    )
    try {
      await phase3.readNotification(id)
    } catch (err) {
      // Revert if failed
      toast({
        title: 'Failed to mark as read',
        description: err instanceof Error ? err.message : 'Please check your connection.',
        variant: 'destructive',
      })
      void loadNotifications()
    }
  }

  // Mark all unread notifications as read
  const markAllAsRead = async () => {
    const unread = notifications.filter((n) => !n.readAt)
    if (unread.length === 0) return

    setMarkingAll(true)
    // Optimistic UI update
    const nowIso = new Date().toISOString()
    setNotifications((current) =>
      current.map((item) => (item.readAt ? item : { ...item, readAt: nowIso }))
    )

    try {
      await Promise.allSettled(unread.map((item) => phase3.readNotification(item.id)))
      toast({
        title: 'All notifications marked as read',
        description: `Successfully acknowledged ${unread.length} notification${
          unread.length === 1 ? '' : 's'
        }.`,
      })
    } catch {
      toast({
        title: 'Some notifications could not be marked',
        variant: 'destructive',
      })
    } finally {
      setMarkingAll(false)
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
        description: 'Clipboard write was blocked by the browser.',
        variant: 'destructive',
      })
    }
  }

  const toggleTech = (id: string) => {
    setExpandedTech((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  // Summary Metrics
  const metrics = useMemo(() => {
    const total = notifications.length
    const unread = notifications.filter((n) => !n.readAt).length
    const actionRequired = notifications.filter((n) => !n.readAt && ACTION_REQUIRED_TYPES.has(n.type)).length
    const read = total - unread

    return { total, unread, actionRequired, read }
  }, [notifications])

  // Filter Logic
  const filteredNotifications = useMemo(() => {
    const q = search.trim().toLowerCase()

    return notifications.filter((item) => {
      // Tab Filtering
      if (activeTab === 'unread' && item.readAt) return false
      if (activeTab === 'read' && !item.readAt) return false
      if (activeTab === 'action_required' && !ACTION_REQUIRED_TYPES.has(item.type)) return false

      // Type Filter
      if (typeFilter !== 'ALL' && item.type !== typeFilter) return false

      // Search
      if (q) {
        const token = formatIncidentToken(item.incidentId).toLowerCase()
        const titleText = item.title.toLowerCase()
        const msgText = item.message.toLowerCase()
        const typeText = item.type.toLowerCase()

        const match =
          token.includes(q) || titleText.includes(q) || msgText.includes(q) || typeText.includes(q)
        if (!match) return false
      }

      return true
    })
  }, [notifications, activeTab, typeFilter, search])

  const isFiltered = search.trim() !== '' || typeFilter !== 'ALL' || activeTab !== 'all'

  const clearFilters = () => {
    setSearch('')
    setTypeFilter('ALL')
    setActiveTab('all')
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Bell className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
                {defaultTitle}
              </h1>
              {metrics.unread > 0 ? (
                <Badge className="bg-primary text-primary-foreground font-semibold px-2 py-0.5 text-xs">
                  {metrics.unread} new
                </Badge>
              ) : null}
            </div>
            <p className="text-sm text-muted-foreground">{defaultSubtitle}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {metrics.unread > 0 ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => void markAllAsRead()}
              disabled={markingAll || loading}
              className="h-9 gap-1.5 text-xs"
            >
              <CheckCheck className="h-4 w-4 text-primary" />
              <span>{markingAll ? 'Marking…' : 'Mark all as read'}</span>
            </Button>
          ) : null}

          <Button
            variant="outline"
            size="sm"
            onClick={() => void loadNotifications(true)}
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
        <Card className="border-destructive/30 bg-destructive/5 p-4 text-destructive">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="font-semibold text-sm">Failed to synchronize notifications</p>
              <p className="text-xs opacity-90">{error}</p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => void loadNotifications()}
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
        <Card
          onClick={() => setActiveTab('all')}
          className={`cursor-pointer border p-4 shadow-xs transition-colors hover:border-primary/50 ${
            activeTab === 'all' ? 'border-primary/60 bg-primary/[0.02]' : 'border-border bg-card'
          }`}
        >
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Total Alerts
          </p>
          <p className="mt-1 font-mono text-2xl font-bold text-foreground">
            {loading ? '—' : metrics.total}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">Authoritative event log</p>
        </Card>

        <Card
          onClick={() => setActiveTab('unread')}
          className={`cursor-pointer border p-4 shadow-xs transition-colors hover:border-primary/50 ${
            activeTab === 'unread' ? 'border-primary/60 bg-primary/[0.02]' : 'border-border bg-card'
          }`}
        >
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Unread Alerts
          </p>
          <div className="mt-1 flex items-baseline gap-2">
            <span
              className={`font-mono text-2xl font-bold ${
                metrics.unread > 0 ? 'text-primary' : 'text-muted-foreground'
              }`}
            >
              {loading ? '—' : metrics.unread}
            </span>
            {metrics.unread > 0 ? (
              <span className="flex h-2 w-2 rounded-full bg-primary animate-pulse" />
            ) : null}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">Awaiting operator review</p>
        </Card>

        <Card
          onClick={() => setActiveTab('action_required')}
          className={`cursor-pointer border p-4 shadow-xs transition-colors hover:border-primary/50 ${
            activeTab === 'action_required'
              ? 'border-primary/60 bg-primary/[0.02]'
              : 'border-border bg-card'
          }`}
        >
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Action Required
          </p>
          <p className="mt-1 font-mono text-2xl font-bold text-amber-600 dark:text-amber-400">
            {loading ? '—' : metrics.actionRequired}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">Reviews & assignments</p>
        </Card>

        <Card
          onClick={() => setActiveTab('read')}
          className={`cursor-pointer border p-4 shadow-xs transition-colors hover:border-primary/50 ${
            activeTab === 'read' ? 'border-primary/60 bg-primary/[0.02]' : 'border-border bg-card'
          }`}
        >
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Acknowledged
          </p>
          <p className="mt-1 font-mono text-2xl font-bold text-muted-foreground">
            {loading ? '—' : metrics.read}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">Processed & marked read</p>
        </Card>
      </div>

      {/* Toolbar: Segmented Tabs + Search + Type Filter */}
      <Card className="border border-border bg-card p-4 shadow-xs space-y-3">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          {/* Segmented Filter Tabs */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
            <Button
              variant={activeTab === 'all' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setActiveTab('all')}
              className="h-8 text-xs font-medium"
            >
              All ({metrics.total})
            </Button>
            <Button
              variant={activeTab === 'unread' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setActiveTab('unread')}
              className="h-8 text-xs font-medium"
            >
              Unread ({metrics.unread})
            </Button>
            <Button
              variant={activeTab === 'action_required' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setActiveTab('action_required')}
              className="h-8 text-xs font-medium"
            >
              Action Required ({metrics.actionRequired})
            </Button>
            <Button
              variant={activeTab === 'read' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setActiveTab('read')}
              className="h-8 text-xs font-medium"
            >
              Read ({metrics.read})
            </Button>
          </div>

          {/* Search + Category Filter */}
          <div className="flex items-center gap-2">
            <div className="relative flex-1 md:w-64">
              <Search className="absolute left-2.5 top-2 h-4 w-4 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search alerts or INC token..."
                className="pl-8 h-8 text-xs"
                aria-label="Search notifications"
              />
            </div>

            <Select value={typeFilter} onValueChange={(val) => setTypeFilter(val)}>
              <SelectTrigger className="h-8 w-44 text-xs" aria-label="Filter by Notification Type">
                <SelectValue placeholder="Event Type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">All Event Types</SelectItem>
                <SelectItem value="NEW_CRASH_REVIEW">Crash Reviews</SelectItem>
                <SelectItem value="NEW_ASSIGNMENT">New Assignments</SelectItem>
                <SelectItem value="ASSIGNMENT_DECLINED">Declined Assignments</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Active Filter Chips */}
        {isFiltered ? (
          <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-border/50 text-xs">
            <span className="text-muted-foreground font-medium">Active filters:</span>
            {activeTab !== 'all' ? (
              <Badge variant="secondary" className="gap-1 font-normal">
                View: {activeTab.replace('_', ' ')}
                <button type="button" onClick={() => setActiveTab('all')}>
                  <X className="h-3 w-3 hover:text-foreground" />
                </button>
              </Badge>
            ) : null}
            {typeFilter !== 'ALL' ? (
              <Badge variant="secondary" className="gap-1 font-normal">
                Type: {typeFilter}
                <button type="button" onClick={() => setTypeFilter('ALL')}>
                  <X className="h-3 w-3 hover:text-foreground" />
                </button>
              </Badge>
            ) : null}
            {search.trim() ? (
              <Badge variant="secondary" className="gap-1 font-normal">
                Search: &quot;{search.trim()}&quot;
                <button type="button" onClick={() => setSearch('')}>
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

      {/* Notifications List Feed */}
      <div className="space-y-3">
        {loading && notifications.length === 0 ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-24 w-full animate-pulse rounded-lg border border-border bg-card"
              />
            ))}
          </div>
        ) : filteredNotifications.length === 0 ? (
          <Card className="border border-border bg-card p-12 text-center shadow-xs">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
              {isFiltered ? <FilterX className="h-6 w-6" /> : <Bell className="h-6 w-6" />}
            </div>
            <h3 className="mt-4 text-base font-semibold text-foreground">
              {isFiltered ? 'No matching notifications found' : 'You are all caught up!'}
            </h3>
            <p className="mt-1 text-sm text-muted-foreground max-w-sm mx-auto">
              {isFiltered
                ? 'Try clearing your search query or selecting a different filter tab.'
                : 'There are no active or pending alerts for your authenticated account right now.'}
            </p>
            {isFiltered ? (
              <Button
                variant="outline"
                size="sm"
                onClick={clearFilters}
                className="mt-4 gap-1.5 text-xs"
              >
                Clear all filters
              </Button>
            ) : null}
          </Card>
        ) : (
          filteredNotifications.map((notification) => {
            const isUnread = !notification.readAt
            const isTechOpen = Boolean(expandedTech[notification.id])
            const { headline, incidentToken } = cleanNotificationMessage(notification.message)

            return (
              <NotificationCard
                key={notification.id}
                notification={notification}
                isUnread={isUnread}
                headline={headline}
                incidentToken={incidentToken}
                role={role}
                isTechOpen={isTechOpen}
                onToggleTech={() => toggleTech(notification.id)}
                onMarkRead={() => void markAsRead(notification.id)}
                onCopy={copyToClipboard}
              />
            )
          })
        )}
      </div>
    </div>
  )
}

function NotificationCard({
  notification,
  isUnread,
  headline,
  incidentToken,
  role,
  isTechOpen,
  onToggleTech,
  onMarkRead,
  onCopy,
}: {
  notification: OperationalNotification
  isUnread: boolean
  headline: string
  incidentToken: string | null
  role: 'dispatcher' | 'responder' | 'admin'
  isTechOpen: boolean
  onToggleTech: () => void
  onMarkRead: () => void
  onCopy: (text: string, label: string) => void
}) {
  const meta = getNotificationMeta(notification.type)

  // Primary Action Configuration
  let primaryAction: { label: string; href: string } | null = null

  if (role === 'dispatcher') {
    if (notification.type === 'NEW_CRASH_REVIEW') {
      primaryAction = { label: 'Review Incident', href: '/dispatcher/review' }
    } else if (notification.type === 'ASSIGNMENT_DECLINED') {
      primaryAction = { label: 'Reassign Unit', href: '/dispatcher/incidents' }
    }
  } else if (role === 'responder') {
    if (notification.type === 'NEW_ASSIGNMENT') {
      primaryAction = { label: 'View Assignment', href: '/responder/assignment' }
    }
  }

  return (
    <Card
      className={`border bg-card transition-all shadow-xs overflow-hidden ${
        isUnread
          ? 'border-l-4 border-l-primary border-t-border border-r-border border-b-border bg-primary/[0.015]'
          : 'border-border opacity-90'
      }`}
    >
      <div className="p-4 sm:p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          {/* Main Content Area */}
          <div className="flex items-start gap-3 min-w-0 flex-1">
            <div className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border ${meta.iconContainerClass}`}>
              {meta.icon}
            </div>

            <div className="min-w-0 flex-1 space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold text-sm text-foreground">
                  {notification.title}
                </span>

                <Badge variant="outline" className={`text-[11px] font-medium gap-1 ${meta.badgeClass}`}>
                  {meta.label}
                </Badge>

                {incidentToken ? (
                  <Badge variant="secondary" className="font-mono text-[11px]">
                    {incidentToken}
                  </Badge>
                ) : null}

                {isUnread ? (
                  <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-primary">
                    <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                    Unread
                  </span>
                ) : null}
              </div>

              <p className="text-xs text-foreground/90 leading-relaxed break-words">
                {headline}
              </p>

              <div className="flex items-center gap-2 pt-1 text-[11px] text-muted-foreground font-mono">
                <Clock className="h-3 w-3" />
                <span title={formatExactDateTime(notification.createdAt)}>
                  {formatRelativeTime(notification.createdAt)}
                </span>
                {notification.readAt ? (
                  <>
                    <span>•</span>
                    <span className="text-muted-foreground/80 font-sans">
                      Read {formatRelativeTime(notification.readAt)}
                    </span>
                  </>
                ) : null}
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2 shrink-0 sm:self-center">
            {primaryAction ? (
              <Button asChild size="sm" className="h-8 gap-1 text-xs">
                <Link href={primaryAction.href}>
                  <span>{primaryAction.label}</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </Button>
            ) : null}

            {isUnread ? (
              <Button
                variant="outline"
                size="sm"
                onClick={onMarkRead}
                className="h-8 gap-1 text-xs text-foreground"
                title="Mark this notification as read"
              >
                <Check className="h-3.5 w-3.5 text-primary" />
                <span className="hidden sm:inline">Mark read</span>
              </Button>
            ) : (
              <span className="hidden sm:inline-flex items-center gap-1 text-xs text-muted-foreground px-2 py-1">
                <Check className="h-3.5 w-3.5 text-muted-foreground/60" />
                Read
              </span>
            )}
          </div>
        </div>

        {/* Collapsible Technical Metadata Drawer */}
        <div className="mt-3 pt-2.5 border-t border-border/50 flex flex-col gap-1.5">
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggleTech}
            className="h-6 w-fit p-0 text-[11px] text-muted-foreground hover:text-foreground gap-1"
          >
            <Layers className="h-3 w-3" />
            <span>Technical Identifiers</span>
            {isTechOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          </Button>

          {isTechOpen ? (
            <div className="rounded-md bg-muted/40 p-2.5 text-xs font-mono grid gap-2 sm:grid-cols-2">
              <div className="flex items-center justify-between gap-2 border-b border-border/40 pb-1 sm:border-b-0 sm:pb-0">
                <div className="truncate">
                  <span className="text-[10px] uppercase text-muted-foreground block">
                    Notification ID
                  </span>
                  <span className="text-foreground truncate select-all">{notification.id}</span>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onCopy(notification.id, 'Notification ID')}
                  className="h-6 w-6 p-0 shrink-0"
                  title="Copy Notification ID"
                >
                  <Copy className="h-3 w-3 text-muted-foreground" />
                </Button>
              </div>

              {notification.incidentId ? (
                <div className="flex items-center justify-between gap-2">
                  <div className="truncate">
                    <span className="text-[10px] uppercase text-muted-foreground block">
                      Incident UUID
                    </span>
                    <span className="text-foreground truncate select-all">{notification.incidentId}</span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onCopy(notification.incidentId!, 'Incident UUID')}
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
}

function getNotificationMeta(type: string): {
  label: string
  icon: React.ReactNode
  badgeClass: string
  iconContainerClass: string
} {
  switch (type) {
    case 'NEW_CRASH_REVIEW':
      return {
        label: 'Crash Review',
        icon: <ShieldAlert className="h-4 w-4 text-amber-600" />,
        badgeClass: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800',
        iconContainerClass: 'bg-amber-500/10 border-amber-200 dark:border-amber-900',
      }
    case 'NEW_ASSIGNMENT':
      return {
        label: 'Dispatch Assignment',
        icon: <Radio className="h-4 w-4 text-primary" />,
        badgeClass: 'bg-teal-50 text-teal-700 border-teal-200 dark:bg-teal-950/40 dark:text-teal-300 dark:border-teal-800',
        iconContainerClass: 'bg-primary/10 border-primary/20',
      }
    case 'ASSIGNMENT_DECLINED':
      return {
        label: 'Unit Declined',
        icon: <AlertTriangle className="h-4 w-4 text-rose-600" />,
        badgeClass: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800',
        iconContainerClass: 'bg-rose-500/10 border-rose-200 dark:border-rose-900',
      }
    default:
      return {
        label: 'Operational Alert',
        icon: <Bell className="h-4 w-4 text-muted-foreground" />,
        badgeClass: 'bg-muted text-muted-foreground border-border',
        iconContainerClass: 'bg-muted border-border',
      }
  }
}
