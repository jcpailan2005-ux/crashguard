'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { AlertTriangle, Archive, Bell, ImageIcon, RefreshCw, ShieldQuestion } from 'lucide-react'

import { DashboardHeader, Sidebar } from '@/components/dashboard-sidebar'
import { IncidentReviewDialog } from '@/components/incident-review-dialog'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { useAuth } from '@/components/auth-provider'
import {
  archiveNotification,
  getLocalCrashCase,
  getNotifications,
  resolveBackendMediaUrl,
} from '@/lib/api-client'
import { localCaseToCrashCase } from '@/lib/crash-case-mapper'
import { getCrashCase } from '@/lib/crash-case-store'
import { APP_CONFIG } from '@/lib/app-config'
import { useDisplayMode } from '@/lib/display-mode'
import { getFirebaseConfigError, getFirestoreOrNull } from '@/lib/firebase-guards'
import { CrashCase, Notification } from '@/lib/types'

type DateFilter = 'today' | 'last7' | 'last30' | 'all' | 'custom'

function startOfToday() {
  const date = new Date()
  date.setHours(0, 0, 0, 0)
  return date
}

function toDateInputValue(date: Date) {
  return date.toISOString().slice(0, 10)
}

function getDateFilterBounds(filter: DateFilter, customFrom: string, customTo: string) {
  if (filter === 'all') {
    return { from: null as Date | null, to: null as Date | null }
  }

  if (filter === 'custom') {
    const from = customFrom ? new Date(`${customFrom}T00:00:00`) : null
    const to = customTo ? new Date(`${customTo}T23:59:59.999`) : null
    return { from, to }
  }

  const from = startOfToday()
  if (filter === 'last7') from.setDate(from.getDate() - 6)
  if (filter === 'last30') from.setDate(from.getDate() - 29)
  const to = new Date()
  return { from, to }
}

function getNotificationEvidenceUrl(notification: Notification) {
  return resolveBackendMediaUrl(
    notification.annotatedImageUrl ??
      notification.evidenceImageUrl ??
      notification.thumbnailUrl ??
      null
  )
}

function getNotificationStatusLabel(notification: Notification) {
  if (!notification.read && notification.alertLevel === 'review') return 'Needs Review'
  if (notification.read) return 'Reviewed'
  if (notification.alertLevel === 'warning') return 'Warning'
  return 'Notification'
}

function NotificationThumbnail({
  notification,
  onOpen,
}: {
  notification: Notification
  onOpen: () => void
}) {
  const [failed, setFailed] = useState(false)
  const imageUrl = getNotificationEvidenceUrl(notification)
  const canOpen = Boolean(notification.caseId ?? notification.incident_id)

  if (!imageUrl || failed) {
    return (
      <div className="flex h-24 w-full items-center justify-center rounded-md border border-dashed border-border bg-muted text-center text-xs text-muted-foreground sm:w-28">
        <div>
          <ImageIcon className="mx-auto mb-1 h-5 w-5 opacity-60" />
          No image available
        </div>
      </div>
    )
  }

  return (
    <button
      type="button"
      className="h-24 w-full overflow-hidden rounded-md border border-border bg-muted text-left sm:w-28"
      onClick={onOpen}
      disabled={!canOpen}
      aria-label="Open crash evidence"
    >
      <img
        src={imageUrl}
        alt="Crash evidence"
        className="h-full w-full object-cover"
        onError={() => setFailed(true)}
      />
    </button>
  )
}

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [filter, setFilter] = useState<'all' | 'review' | 'recent'>('all')
  const [dateFilter, setDateFilter] = useState<DateFilter>('last7')
  const [customFrom, setCustomFrom] = useState('')
  const [customTo, setCustomTo] = useState('')
  const [loading, setLoading] = useState(true)
  const [storeError, setStoreError] = useState<string | null>(null)
  const [caseLoadError, setCaseLoadError] = useState<string | null>(null)
  const [loadingCaseId, setLoadingCaseId] = useState<string | null>(null)
  const [actionNotificationId, setActionNotificationId] = useState<string | null>(null)
  const [selectedCase, setSelectedCase] = useState<CrashCase | null>(null)
  const { firebaseUser, profile } = useAuth()
  const { isAdvancedMode } = useDisplayMode(profile)
  const isNeedsReviewNotification = (notification: Notification) =>
    !notification.read && notification.alertLevel === 'review'
  const getNotificationTime = (notification: Notification) => {
    const parsed = new Date(notification.createdAt ?? notification.timestamp).getTime()
    return Number.isNaN(parsed) ? 0 : parsed
  }

  const loadNotifications = useCallback((showLoading = false) => {
    if (showLoading) setLoading(true)
    return getNotifications()
      .then((items) => {
        const visibleItems =
          profile?.role === 'responder'
            ? items.filter(
                (item) =>
                  item.alertLevel !== 'review' &&
                  (!item.responderId ||
                    item.responderId === firebaseUser?.uid ||
                    Boolean(profile.areaId && item.areaId === profile.areaId))
              )
            : items
        const sortedItems = [...visibleItems].sort(
          (a, b) => getNotificationTime(b) - getNotificationTime(a)
        )
        console.info('[notifications-page] loaded notifications', {
          count: sortedItems.length,
          newestId: sortedItems[0]?.id ?? null,
          newestTimestamp: sortedItems[0]?.createdAt ?? sortedItems[0]?.timestamp ?? null,
        })
        setNotifications(sortedItems)
        setStoreError(null)
      })
      .catch((error) => {
        setStoreError(error instanceof Error ? error.message : 'Could not load notifications.')
      })
      .finally(() => {
        setLoading(false)
      })
  }, [firebaseUser?.uid, profile])

  useEffect(() => {
    let cancelled = false

    loadNotifications(true).catch(() => {
      if (!cancelled) setLoading(false)
    })

    const intervalId = window.setInterval(() => {
      loadNotifications(false).catch(() => {
        if (!cancelled) setLoading(false)
      })
    }, 4000)

    return () => {
      cancelled = true
      window.clearInterval(intervalId)
    }
  }, [loadNotifications])

  const getFilteredNotifications = () => {
    const { from, to } = getDateFilterBounds(dateFilter, customFrom, customTo)
    const dateFiltered = notifications.filter((notification) => {
      const timestamp = getNotificationTime(notification)
      if (!timestamp) return false
      if (from && timestamp < from.getTime()) return false
      if (to && timestamp > to.getTime()) return false
      return true
    })

    switch (filter) {
      case 'review':
        return dateFiltered.filter(isNeedsReviewNotification)
      case 'recent':
        return dateFiltered.slice(0, 10)
      default:
        return dateFiltered
    }
  }

  const dateFilteredNotifications = (() => {
    const { from, to } = getDateFilterBounds(dateFilter, customFrom, customTo)
    return notifications.filter((notification) => {
      const timestamp = getNotificationTime(notification)
      if (!timestamp) return false
      if (from && timestamp < from.getTime()) return false
      if (to && timestamp > to.getTime()) return false
      return true
    })
  })()

  const getAlertTone = (alertLevel: string) => {
    switch (alertLevel) {
      case 'review':
        return 'border-orange-300 bg-orange-50 text-orange-700 dark:border-orange-900/70 dark:bg-orange-950/30 dark:text-orange-300'
      case 'warning':
        return 'border-orange-300 bg-orange-50 text-orange-700 dark:border-orange-900/70 dark:bg-orange-950/30 dark:text-orange-300'
      default:
        return 'border-border bg-muted text-muted-foreground'
    }
  }

  const getAlertIcon = (alertLevel: string) => {
    switch (alertLevel) {
      case 'review':
        return <ShieldQuestion className="h-5 w-5" />
      case 'warning':
        return <ShieldQuestion className="h-5 w-5" />
      default:
        return <Bell className="h-5 w-5" />
    }
  }

  const openCase = async (caseId: string) => {
    if (!caseId) return
    setCaseLoadError(null)
    setLoadingCaseId(caseId)

    try {
      const db = getFirestoreOrNull()
      const configError = getFirebaseConfigError()
      if (db && !configError && !caseId.startsWith('CASE-')) {
        const caseItem = await getCrashCase(db, caseId)
        if (caseItem) {
          setSelectedCase(caseItem)
          return
        }
      }

      const localCase = await getLocalCrashCase(caseId)
      setSelectedCase(localCaseToCrashCase(localCase))
    } catch {
      setCaseLoadError('Could not load full crash case details.')
    } finally {
      setLoadingCaseId(null)
    }
  }

  const handleArchive = async (notification: Notification) => {
    setStoreError(null)
    setActionNotificationId(notification.id)
    try {
      await archiveNotification(notification.id)
      setNotifications((current) => current.filter((item) => item.id !== notification.id))
    } catch (error) {
      setStoreError(error instanceof Error ? error.message : 'Could not archive notification.')
    } finally {
      setActionNotificationId(null)
    }
  }

  const filteredNotifications = getFilteredNotifications()
  const visibleNotifications = filteredNotifications.slice(0, 3)
  const hiddenNotificationCount = Math.max(0, filteredNotifications.length - visibleNotifications.length)

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <div className="flex-1 md:ml-0">
        <DashboardHeader />

        <main className="max-w-4xl space-y-6 p-6">
          <div>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h1 className="mb-2 text-3xl font-bold">Notifications</h1>
                <p className="text-muted-foreground">
                  Recent crash alerts.
                </p>
              </div>
              <Button
                type="button"
                variant="outline"
                onClick={() => void loadNotifications(true)}
                disabled={loading}
              >
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
            </div>
          </div>

          {storeError ? (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>{storeError}</AlertDescription>
            </Alert>
          ) : null}

          {caseLoadError ? (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>{caseLoadError}</AlertDescription>
            </Alert>
          ) : null}

          <Tabs
            defaultValue="all"
            onValueChange={(v) => {
              setFilter(v as any)
            }}
          >
            <Card className="mb-4 border border-border bg-card p-4">
              <div className="flex flex-wrap items-center gap-2">
                {([
                  ['last7', 'Recent'],
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
                    onClick={() => setDateFilter(value)}
                  >
                    {label}
                  </Button>
                ))}
              </div>
              {dateFilter === 'custom' ? (
                <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
                  <Input
                    type="date"
                    value={customFrom}
                    onChange={(event) => setCustomFrom(event.target.value)}
                    max={customTo || undefined}
                  />
                  <Input
                    type="date"
                    value={customTo}
                    onChange={(event) => setCustomTo(event.target.value)}
                    min={customFrom || undefined}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      if (!customFrom && !customTo) {
                        const today = startOfToday()
                        setCustomFrom(toDateInputValue(today))
                        setCustomTo(toDateInputValue(today))
                      }
                    }}
                  >
                    Apply
                  </Button>
                </div>
              ) : null}
              <p className="mt-3 text-sm text-muted-foreground">
                Showing 3 most recent notifications.{' '}
                {dateFilteredNotifications.length} notification{dateFilteredNotifications.length === 1 ? '' : 's'} match this date filter.
              </p>
            </Card>

            <TabsList className="grid w-full grid-cols-3 border border-border bg-card">
              <TabsTrigger value="all">
                All
                <Badge variant="outline" className="ml-2">
                  {dateFilteredNotifications.length}
                </Badge>
              </TabsTrigger>
              <TabsTrigger value="review">
                Needs Review
                <Badge variant="outline" className="ml-2">
                  {dateFilteredNotifications.filter(isNeedsReviewNotification).length}
                </Badge>
              </TabsTrigger>
              <TabsTrigger value="recent">
                Recent
                <Badge variant="outline" className="ml-2">
                  {Math.min(10, dateFilteredNotifications.length)}
                </Badge>
              </TabsTrigger>
            </TabsList>

            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-muted-foreground">
                Showing {Math.min(3, filteredNotifications.length)} most recent notifications
              </p>
              {filteredNotifications.length > 3 ? (
                <Button
                  asChild
                  type="button"
                  variant="outline"
                >
                  <Link href="/dashboard/notifications/all">See All Notifications</Link>
                </Button>
              ) : null}
            </div>

            <TabsContent value={filter} className="mt-6 space-y-4">
              {loading && notifications.length === 0 ? (
                <Card className="p-8 text-center text-muted-foreground">
                  Loading notifications...
                </Card>
              ) : visibleNotifications.length === 0 ? (
                <Card className="p-8 text-center text-muted-foreground">
                  <Bell className="mx-auto mb-4 h-12 w-12 opacity-50" />
                  <p>No notifications to display</p>
                </Card>
              ) : (
                <div className="space-y-3">
                  {visibleNotifications.map((notification) => (
                    <Card
                      key={notification.id}
                      className="rounded-lg border border-border bg-card p-4 shadow-sm transition-colors hover:border-orange-200 dark:hover:border-orange-900/60"
                    >
                      <div className="grid min-w-0 gap-4 sm:grid-cols-[7rem_2.5rem_minmax(0,1fr)_auto] sm:items-center">
                        <NotificationThumbnail
                          notification={notification}
                          onOpen={() => void openCase(notification.caseId ?? notification.incident_id)}
                        />
                        <div
                          className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-md ${getAlertTone(
                            notification.alertLevel
                          )}`}
                        >
                          {getAlertIcon(notification.alertLevel)}
                        </div>

                        <div className="min-w-0 flex-1">
                          <h3 className="truncate font-semibold">
                            {notification.title || (notification.alertLevel === 'warning' ? 'Crash Incident' : 'Possible Crash Review')}
                          </h3>
                          {isAdvancedMode ? (
                            <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
                              {notification.message || 'Needs Review'}
                            </p>
                          ) : null}
                          <p className="mt-2 text-xs text-muted-foreground">
                            {new Date(notification.createdAt ?? notification.timestamp).toLocaleString()}
                          </p>
                          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                            {notification.sourceCamera || notification.cameraName ? (
                              <span>Camera: {notification.sourceCamera ?? notification.cameraName}</span>
                            ) : null}
                            {notification.areaId ? <span>Area: {notification.areaId}</span> : null}
                          </div>
                          {isAdvancedMode ? (
                            <div className="mt-2 grid gap-1 text-xs text-muted-foreground sm:grid-cols-2">
                              <p className="break-all">notificationId: {notification.id}</p>
                              <p className="break-all">caseId: {notification.caseId ?? notification.incident_id}</p>
                              <p className="break-all">alertLevel: {notification.alertLevel}</p>
                              <p className="break-all">read: {String(notification.read)}</p>
                            </div>
                          ) : null}
                        </div>

                        <div className="flex flex-row items-center gap-2 sm:justify-end">
                          <Badge
                            className={`shrink-0 ${getAlertTone(notification.alertLevel)}`}
                            variant="outline"
                          >
                            {getNotificationStatusLabel(notification)}
                          </Badge>
                          <Button
                            type="button"
                            variant="outline"
                            className="shrink-0"
                            onClick={() => void openCase(notification.caseId ?? notification.incident_id)}
                            disabled={!(notification.caseId ?? notification.incident_id) || loadingCaseId === (notification.caseId ?? notification.incident_id)}
                          >
                            {loadingCaseId === (notification.caseId ?? notification.incident_id) ? 'Loading...' : 'Review'}
                          </Button>
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button
                                type="button"
                                variant="outline"
                                className="shrink-0"
                                disabled={actionNotificationId === notification.id}
                              >
                                <Archive className="h-4 w-4" />
                                Archive
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent className="sm:max-w-md">
                              <AlertDialogHeader>
                                <AlertDialogTitle>Archive this notification?</AlertDialogTitle>
                                <AlertDialogDescription>
                                  This will hide it from the active list. The crash case will remain saved.
                                </AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>Cancel</AlertDialogCancel>
                                <AlertDialogAction onClick={() => void handleArchive(notification)}>
                                  Archive
                                </AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        </div>
                      </div>
                    </Card>
                  ))}
                  {hiddenNotificationCount > 0 ? (
                    <Card className="border border-dashed border-border bg-card/60 p-4 text-center text-sm text-muted-foreground">
                      {hiddenNotificationCount} more matching notification{hiddenNotificationCount === 1 ? '' : 's'} hidden.
                      <Button asChild variant="link" className="ml-1 h-auto p-0">
                        <Link href="/dashboard/notifications/all">See all</Link>
                      </Button>
                    </Card>
                  ) : null}
                </div>
              )}
            </TabsContent>
          </Tabs>
        </main>
      </div>

      <IncidentReviewDialog
        actorId={firebaseUser?.uid ?? 'unknown-user'}
        caseItem={selectedCase}
        onCaseUpdated={(caseItem) => {
          setSelectedCase(caseItem)
          void loadNotifications(false)
        }}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedCase(null)
            void loadNotifications(false)
          }
        }}
        open={selectedCase != null}
      />
    </div>
  )
}
