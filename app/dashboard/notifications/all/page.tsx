'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import {
  AlertTriangle,
  Archive,
  ArrowLeft,
  Bell,
  ImageIcon,
  RefreshCw,
  Search,
  ShieldQuestion,
  Trash2,
} from 'lucide-react'

import { DashboardHeader, Sidebar } from '@/components/dashboard-sidebar'
import { IncidentReviewDialog } from '@/components/incident-review-dialog'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
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
  deleteNotification,
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

type DateFilter = 'recent' | 'today' | 'last30' | 'all' | 'custom'
type StatusFilter = 'all' | 'needs_review' | 'read' | 'unread'

function startOfToday() {
  const date = new Date()
  date.setHours(0, 0, 0, 0)
  return date
}

function toDateInputValue(date: Date) {
  return date.toISOString().slice(0, 10)
}

function getDateFilterBounds(filter: DateFilter, customFrom: string, customTo: string) {
  if (filter === 'all') return { from: null as Date | null, to: null as Date | null }

  if (filter === 'custom') {
    return {
      from: customFrom ? new Date(`${customFrom}T00:00:00`) : null,
      to: customTo ? new Date(`${customTo}T23:59:59.999`) : null,
    }
  }

  const from = startOfToday()
  if (filter === 'recent') from.setDate(from.getDate() - 6)
  if (filter === 'last30') from.setDate(from.getDate() - 29)
  return { from, to: new Date() }
}

function getNotificationTime(notification: Notification) {
  const parsed = new Date(notification.createdAt ?? notification.timestamp).getTime()
  return Number.isNaN(parsed) ? 0 : parsed
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

function getAlertTone(alertLevel: string) {
  switch (alertLevel) {
    case 'review':
    case 'warning':
      return 'border-orange-300 bg-orange-50 text-orange-700 dark:border-orange-900/70 dark:bg-orange-950/30 dark:text-orange-300'
    default:
      return 'border-border bg-muted text-muted-foreground'
  }
}

function EvidenceThumbnail({
  notification,
  onOpen,
}: {
  notification: Notification
  onOpen: () => void
}) {
  const [failed, setFailed] = useState(false)
  const imageUrl = getNotificationEvidenceUrl(notification)
  const hasVideoOnly = !imageUrl && notification.hasEvidence && Boolean(notification.mediaUrl)
  const canOpen = Boolean(notification.caseId ?? notification.incident_id)

  if (!imageUrl || failed) {
    return (
      <button
        type="button"
        className="flex h-24 w-full items-center justify-center rounded-md border border-dashed border-border bg-muted text-center text-xs text-muted-foreground sm:w-32"
        onClick={onOpen}
        disabled={!canOpen}
      >
        <div>
          <ImageIcon className="mx-auto mb-1 h-5 w-5 opacity-60" />
          {hasVideoOnly ? 'Video evidence' : 'No image available'}
        </div>
      </button>
    )
  }

  return (
    <button
      type="button"
      className="h-24 w-full overflow-hidden rounded-md border border-border bg-muted text-left sm:w-32"
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

export default function AllNotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [dateFilter, setDateFilter] = useState<DateFilter>('recent')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [customFrom, setCustomFrom] = useState('')
  const [customTo, setCustomTo] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const [loading, setLoading] = useState(true)
  const [storeError, setStoreError] = useState<string | null>(null)
  const [caseLoadError, setCaseLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [loadingCaseId, setLoadingCaseId] = useState<string | null>(null)
  const [actionNotificationId, setActionNotificationId] = useState<string | null>(null)
  const [selectedCase, setSelectedCase] = useState<CrashCase | null>(null)
  const { firebaseUser, profile } = useAuth()
  const { isAdvancedMode } = useDisplayMode(profile)
  const role = String(profile?.role ?? '').toLowerCase()
  const canDelete = role === 'admin' && isAdvancedMode

  const loadNotifications = useCallback((showLoading = false) => {
    if (showLoading) setLoading(true)
    return getNotifications()
      .then((items) => {
        const visibleItems =
          role === 'responder'
            ? items.filter(
                (item) =>
                  !item.responderId ||
                  item.responderId === firebaseUser?.uid ||
                  Boolean(profile?.areaId && item.areaId === profile.areaId)
              )
            : items
        setNotifications([...visibleItems].sort((a, b) => getNotificationTime(b) - getNotificationTime(a)))
        setStoreError(null)
      })
      .catch((error) => {
        setStoreError(error instanceof Error ? error.message : 'Could not load notifications.')
      })
      .finally(() => setLoading(false))
  }, [firebaseUser?.uid, profile?.areaId, role])

  useEffect(() => {
    void loadNotifications(true)
  }, [loadNotifications])

  const filteredNotifications = useMemo(() => {
    const { from, to } = getDateFilterBounds(dateFilter, customFrom, customTo)
    const query = searchTerm.trim().toLowerCase()

    return notifications.filter((notification) => {
      const timestamp = getNotificationTime(notification)
      if (!timestamp) return false
      if (from && timestamp < from.getTime()) return false
      if (to && timestamp > to.getTime()) return false

      if (statusFilter === 'needs_review' && (notification.read || notification.alertLevel !== 'review')) {
        return false
      }
      if (statusFilter === 'read' && !notification.read) return false
      if (statusFilter === 'unread' && notification.read) return false

      if (!query) return true
      const searchable = [
        notification.title,
        notification.message,
        notification.sourceCamera,
        notification.cameraName,
        notification.areaId,
        getNotificationStatusLabel(notification),
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      return searchable.includes(query)
    })
  }, [customFrom, customTo, dateFilter, notifications, searchTerm, statusFilter])

  const openCase = async (caseId: string) => {
    if (!caseId) return
    setCaseLoadError(null)
    setLoadingCaseId(caseId)

    try {
      if (caseId.startsWith('CASE-')) {
        const localCase = await getLocalCrashCase(caseId)
        setSelectedCase(localCaseToCrashCase(localCase))
        return
      }

      if (!APP_CONFIG.useMockData) {
        throw new Error('Only SQLite crash cases can be opened from notifications.')
      }

      const db = getFirestoreOrNull()
      const configError = getFirebaseConfigError()
      if (!db || configError) {
        throw new Error(configError ?? 'Firestore is not ready.')
      }

      setSelectedCase(await getCrashCase(db, caseId))
    } catch {
      setCaseLoadError('Could not load full crash case details.')
    } finally {
      setLoadingCaseId(null)
    }
  }

  const handleArchive = async (notification: Notification) => {
    setActionError(null)
    setActionNotificationId(notification.id)
    try {
      await archiveNotification(notification.id)
      setNotifications((current) => current.filter((item) => item.id !== notification.id))
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Could not archive notification.')
    } finally {
      setActionNotificationId(null)
    }
  }

  const handleDelete = async (notification: Notification) => {
    if (!canDelete) return
    setActionError(null)
    setActionNotificationId(notification.id)
    try {
      await deleteNotification(notification.id)
      setNotifications((current) => current.filter((item) => item.id !== notification.id))
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Could not delete notification.')
    } finally {
      setActionNotificationId(null)
    }
  }

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <div className="flex-1 md:ml-0">
        <DashboardHeader />

        <main className="max-w-6xl space-y-6 p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <Button asChild variant="ghost" className="-ml-3 mb-2">
                <Link href="/dashboard/notifications">
                  <ArrowLeft className="h-4 w-4" />
                  Back to Recent
                </Link>
              </Button>
              <h1 className="mb-2 text-3xl font-bold">All Notifications</h1>
              <p className="text-muted-foreground">
                Crash records and review alerts.
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

          {storeError || caseLoadError || actionError ? (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>{storeError ?? caseLoadError ?? actionError}</AlertDescription>
            </Alert>
          ) : null}

          <Card className="space-y-4 border border-border bg-card p-4">
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
                  onClick={() => setDateFilter(value)}
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

            <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto]">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                  placeholder="Search camera, area, or status"
                  className="pl-9"
                />
              </div>
              <div className="flex flex-wrap gap-2">
                {([
                  ['all', 'All Statuses'],
                  ['needs_review', 'Needs Review'],
                  ['unread', 'Unread'],
                  ['read', 'Reviewed'],
                ] as const).map(([value, label]) => (
                  <Button
                    key={value}
                    type="button"
                    size="sm"
                    variant={statusFilter === value ? 'default' : 'outline'}
                    onClick={() => setStatusFilter(value)}
                  >
                    {label}
                  </Button>
                ))}
              </div>
            </div>

            <p className="text-sm text-muted-foreground">
              Showing {filteredNotifications.length} matching notification{filteredNotifications.length === 1 ? '' : 's'}, newest first.
            </p>
          </Card>

          {loading && notifications.length === 0 ? (
            <Card className="p-8 text-center text-muted-foreground">Loading notifications...</Card>
          ) : filteredNotifications.length === 0 ? (
            <Card className="p-8 text-center text-muted-foreground">
              <Bell className="mx-auto mb-4 h-12 w-12 opacity-50" />
              <p>No notifications found for this filter.</p>
            </Card>
          ) : (
            <div className="space-y-3">
              {filteredNotifications.map((notification) => {
                const caseId = notification.caseId ?? notification.incident_id
                return (
                  <Card
                    key={notification.id}
                    className="rounded-lg border border-border bg-card p-4 shadow-sm"
                  >
                    <div className="grid gap-4 lg:grid-cols-[8rem_minmax(0,1fr)_auto] lg:items-center">
                      <EvidenceThumbnail
                        notification={notification}
                        onOpen={() => void openCase(caseId)}
                      />

                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <div
                            className={`flex h-9 w-9 items-center justify-center rounded-md ${getAlertTone(
                              notification.alertLevel
                            )}`}
                          >
                            <ShieldQuestion className="h-5 w-5" />
                          </div>
                          <div className="min-w-0">
                            <h3 className="truncate font-semibold">
                              {notification.title || (notification.alertLevel === 'warning' ? 'Crash Incident' : 'Possible Crash Review')}
                            </h3>
                            <p className="text-sm text-muted-foreground">
                              {new Date(notification.createdAt ?? notification.timestamp).toLocaleString()}
                            </p>
                          </div>
                        </div>

                        <div className="mt-3 grid gap-1 text-sm text-muted-foreground sm:grid-cols-2">
                          <p>Camera/source: {notification.sourceCamera ?? notification.cameraName ?? 'Unknown camera'}</p>
                          <p>Area: {notification.areaId ?? 'Unknown area'}</p>
                          <p>Status: {getNotificationStatusLabel(notification)}</p>
                        </div>

                        {isAdvancedMode ? (
                          <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">
                            {notification.message || 'Needs Review'}
                          </p>
                        ) : null}

                        {isAdvancedMode ? (
                          <div className="mt-3 grid gap-1 text-xs text-muted-foreground sm:grid-cols-2">
                            <p className="break-all">notificationId: {notification.id}</p>
                            <p className="break-all">caseId: {caseId}</p>
                            <p className="break-all">cameraId: {notification.cameraId ?? 'null'}</p>
                            <p className="break-all">triggerStatus: {notification.triggerStatus ?? 'null'}</p>
                            <p className="break-all">alertLevel: {notification.alertLevel}</p>
                            <p className="break-all">read: {String(notification.read)}</p>
                            <p className="break-all">mediaUrl: {notification.mediaUrl ?? 'null'}</p>
                            <p className="break-all">evidenceImageUrl: {notification.evidenceImageUrl ?? 'null'}</p>
                          </div>
                        ) : null}
                      </div>

                      <div className="flex flex-wrap items-center gap-2 lg:justify-end">
                        <Badge className={getAlertTone(notification.alertLevel)} variant="outline">
                          {getNotificationStatusLabel(notification)}
                        </Badge>
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => void openCase(caseId)}
                          disabled={!caseId || loadingCaseId === caseId}
                        >
                          {loadingCaseId === caseId ? 'Loading...' : 'Review'}
                        </Button>
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button
                              type="button"
                              variant="outline"
                              disabled={actionNotificationId === notification.id}
                            >
                              <Archive className="h-4 w-4" />
                              {actionNotificationId === notification.id ? 'Saving...' : 'Archive'}
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
                        {canDelete ? (
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button
                                type="button"
                                variant="destructive"
                                disabled={actionNotificationId === notification.id}
                              >
                                <Trash2 className="h-4 w-4" />
                                Delete Record
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent className="sm:max-w-md">
                              <AlertDialogHeader>
                                <AlertDialogTitle>Delete this record?</AlertDialogTitle>
                                <AlertDialogDescription>
                                  This removes the notification record. The crash case and evidence files remain saved.
                                </AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>Cancel</AlertDialogCancel>
                                <AlertDialogAction onClick={() => void handleDelete(notification)}>
                                  Delete
                                </AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        ) : null}
                      </div>
                    </div>
                  </Card>
                )
              })}
            </div>
          )}
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
