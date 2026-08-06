'use client'

import { type ReactNode, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ClipboardList,
  ExternalLink,
  Eye,
  FileText,
  MapPin,
  Send,
  ShieldQuestion,
  Truck,
} from 'lucide-react'

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { useAuth } from '@/components/auth-provider'
import { useToast } from '@/hooks/use-toast'
import { caseMedia, localCaseToCrashCase } from '@/lib/crash-case-mapper'
import { applyLocalCrashCaseAction } from '@/lib/api-client'
import { applyCrashCaseAction } from '@/lib/crash-case-store'
import { useDisplayMode } from '@/lib/display-mode'
import { getFirebaseConfigError, getFirestoreOrNull } from '@/lib/firebase-guards'
import {
  CASE_ACTION_LABELS,
  CaseActionType,
  CaseStatus,
  getCaseStatusLabel,
  getIncidentTitle,
} from '@/lib/incident-status'
import { getAreaLabel } from '@/lib/locations'
import { getCaseStatusClass } from '@/lib/theme-status'
import { CrashCase, DetectionBox } from '@/lib/types'

interface IncidentReviewDialogProps {
  actorId: string
  caseItem: CrashCase | null
  onCaseUpdated?: (caseItem: CrashCase) => void
  onOpenChange: (open: boolean) => void
  open: boolean
}

type DisplayAction =
  | { kind: 'state'; action: CaseActionType; icon: ReactNode; label?: string; className?: string }
  | { kind: 'media'; icon: ReactNode }
  | { kind: 'map'; icon: ReactNode }
  | { kind: 'history'; icon: ReactNode }
  | { kind: 'details'; icon: ReactNode }

const STATE_ACTION_CLASSES: Partial<Record<CaseActionType, string>> = {
  review_alert:
    'border-[var(--status-under-review)] bg-[color:var(--status-under-review-bg)] text-[var(--status-under-review)] hover:bg-[color:var(--status-under-review-bg)]',
  confirm_crash:
    'border-[var(--status-confirmed)] bg-[color:var(--status-confirmed-bg)] text-[var(--status-confirmed)] hover:bg-[color:var(--status-confirmed-bg)]',
  mark_false_alarm:
    'border-[var(--status-false-alarm)] bg-[color:var(--status-false-alarm-bg)] text-[var(--status-false-alarm)] hover:bg-[color:var(--status-false-alarm-bg)]',
  resolve_case:
    'border-[var(--status-resolved)] bg-[color:var(--status-resolved-bg)] text-[var(--status-resolved)] hover:bg-[color:var(--status-resolved-bg)]',
}

function getReviewActions(status: CaseStatus): DisplayAction[] {
  switch (status) {
    case 'pending_review':
    case 'under_review':
    case 'confirmed_crash':
      return [
        { kind: 'state', action: 'dispatch_help', icon: <Truck className="h-4 w-4" />, label: 'Approve & Dispatch', className: 'bg-destructive text-destructive-foreground hover:bg-destructive/90' },
        { kind: 'state', action: 'mark_false_alarm', icon: <AlertTriangle className="h-4 w-4" />, label: 'False Alarm' },
        { kind: 'media', icon: <ExternalLink className="h-4 w-4" /> },
        { kind: 'map', icon: <MapPin className="h-4 w-4" /> },
      ]
    case 'dispatched':
      return [
        { kind: 'state', action: 'accept_dispatch', icon: <CheckCircle2 className="h-4 w-4" />, label: 'Accept Dispatch' },
        { kind: 'state', action: 'resolve_case', icon: <ClipboardList className="h-4 w-4" /> },
        { kind: 'map', icon: <MapPin className="h-4 w-4" /> },
      ]
    case 'responding':
      return [
        { kind: 'state', action: 'arrive_scene', icon: <MapPin className="h-4 w-4" />, label: 'Mark Arrived' },
        { kind: 'state', action: 'resolve_case', icon: <ClipboardList className="h-4 w-4" /> },
        { kind: 'map', icon: <MapPin className="h-4 w-4" /> },
      ]
    case 'arrived':
      return [
        { kind: 'state', action: 'resolve_case', icon: <ClipboardList className="h-4 w-4" /> },
        { kind: 'map', icon: <MapPin className="h-4 w-4" /> },
      ]
    case 'false_alarm':
      return [
        { kind: 'history', icon: <ClipboardList className="h-4 w-4" /> },
        { kind: 'map', icon: <MapPin className="h-4 w-4" /> },
      ]
    case 'resolved':
      return [
        { kind: 'details', icon: <Eye className="h-4 w-4" /> },
        { kind: 'history', icon: <ClipboardList className="h-4 w-4" /> },
        { kind: 'map', icon: <MapPin className="h-4 w-4" /> },
      ]
  }
}

function shortCaseId(caseId: string) {
  return caseId.length > 10 ? `${caseId.slice(0, 4)}...${caseId.slice(-4)}` : caseId
}

function formatDetectedTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Time unavailable'
  return date.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function normalizeDisplayText(value?: string | null) {
  return value?.trim().replace(/\s+/g, ' ') ?? ''
}

function formatAreaLabel(areaId?: string | null) {
  const normalized = normalizeDisplayText(areaId)
  if (!normalized) return 'Unassigned'

  const knownAreaLabel = getAreaLabel(normalized)
  if (knownAreaLabel !== 'Fallback Demo Location') return knownAreaLabel

  return normalized
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function isSensitiveLocationText(value: string) {
  const normalized = value.toLowerCase()

  return (
    /(?:https?|rtsp):\/\//i.test(value) ||
    /\b(?:\d{1,3}\.){3}\d{1,3}\b/.test(value) ||
    /\/\/[^/\s]*@/.test(value) ||
    /(?:username|password|credential|token|streamurl|cameraip|rtsp)/i.test(value) ||
    normalized.includes('://') ||
    normalized.includes('@')
  )
}

function getIncidentLocationLabel(caseItem: CrashCase) {
  const locationLabel = normalizeDisplayText(caseItem.location.label)
  const fallbackArea = formatAreaLabel(caseItem.location.areaId)
  const cameraValues = [
    caseItem.cameraName,
    caseItem.sourceCamera,
    caseItem.media.sourceFile,
    caseItem.cameraId,
    caseItem.cameraIp,
  ]
    .map(normalizeDisplayText)
    .filter(Boolean)
    .map((value) => value.toLowerCase())

  if (
    locationLabel &&
    !isSensitiveLocationText(locationLabel) &&
    !cameraValues.includes(locationLabel.toLowerCase())
  ) {
    return locationLabel
  }

  return fallbackArea
}

function EvidenceImageWithBoxes({
  boxes,
  onError,
  onLoad,
  src,
}: {
  boxes?: DetectionBox[]
  onError: () => void
  onLoad: () => void
  src: string
}) {
  const [naturalSize, setNaturalSize] = useState({ width: 1, height: 1 })
  const visibleBoxes = boxes?.filter((box) => box.width > 0 && box.height > 0) ?? []
  const toPercent = (value: number, axis: 'x' | 'y') => {
    if (value <= 1) return value * 100
    return (value / (axis === 'x' ? naturalSize.width : naturalSize.height)) * 100
  }

  return (
    <div className="flex min-h-64 items-center justify-center">
      <div className="relative inline-block max-w-full">
        <img
          src={src}
          alt="Possible crash key frame"
          onError={onError}
          onLoad={(event) => {
            setNaturalSize({
              width: event.currentTarget.naturalWidth || 1,
              height: event.currentTarget.naturalHeight || 1,
            })
            onLoad()
          }}
          className="block max-h-[28rem] max-w-full object-contain"
        />
        {visibleBoxes.length > 0 ? (
          <div className="pointer-events-none absolute inset-0">
            {visibleBoxes.map((box, index) => (
              <div
                key={`${box.label}-${box.x}-${box.y}-${index}`}
                className="absolute rounded-sm border-2 border-red-500 bg-red-500/10 shadow-[0_0_0_1px_rgba(0,0,0,0.35)]"
                style={{
                  left: `${toPercent(box.x, 'x')}%`,
                  top: `${toPercent(box.y, 'y')}%`,
                  width: `${toPercent(box.width, 'x')}%`,
                  height: `${toPercent(box.height, 'y')}%`,
                }}
              >
                <span className="absolute left-0 top-0 max-w-full -translate-y-full truncate rounded-sm bg-red-600 px-1.5 py-0.5 text-[10px] font-semibold leading-none text-white">
                  {box.label || 'detection'} {(box.confidence * 100).toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  )
}

export function IncidentReviewDialog({
  actorId,
  caseItem,
  onCaseUpdated,
  onOpenChange,
  open,
}: IncidentReviewDialogProps) {
  const [notes, setNotes] = useState('')
  const [submittingAction, setSubmittingAction] = useState<CaseActionType | null>(null)
  const [openSections, setOpenSections] = useState<string[]>([])
  const [imageLoadError, setImageLoadError] = useState(false)
  const [showConfirmDispatchModal, setShowConfirmDispatchModal] = useState(false)
  const { toast } = useToast()
  const { profile } = useAuth()
  const { isAdvancedMode } = useDisplayMode(profile)

  const media = useMemo(() => caseMedia(caseItem), [caseItem])

  useEffect(() => {
    setImageLoadError(false)
  }, [media.previewUrl])

  const actions = useMemo(
    () => (caseItem ? getReviewActions(caseItem.status) : []),
    [caseItem]
  )

  if (!caseItem) return null

  const mapUrl = `https://www.google.com/maps?q=${caseItem.location.latitude},${caseItem.location.longitude}`

  const openAccordionSection = (section: string) => {
    setOpenSections((current) =>
      current.includes(section) ? current : [...current, section]
    )
  }

  const handleAction = async (action: CaseActionType) => {
    setSubmittingAction(action)
    try {
      if (caseItem.caseId.startsWith('CASE-')) {
        const updatedCase = await applyLocalCrashCaseAction(caseItem.caseId, {
          action,
          actorId,
          notes,
        })
        onCaseUpdated?.(localCaseToCrashCase(updatedCase))
      } else {
        const db = getFirestoreOrNull()
        const configError = getFirebaseConfigError()

        if (!db || configError) {
          throw new Error(configError ?? 'Firestore is not ready.')
        }

        await applyCrashCaseAction(db, {
          action,
          actorId,
          caseItem,
          notes,
        })
      }
      setNotes('')
      toast({
        title: CASE_ACTION_LABELS[action],
        description: `Case ${shortCaseId(caseItem.caseId)} updated.`,
      })
    } catch (error) {
      toast({
        title: 'Action failed',
        description:
          error instanceof Error ? error.message : 'Could not update the case.',
        variant: 'destructive',
      })
    } finally {
      setSubmittingAction(null)
    }
  }

  const saveNotes = () => handleAction('add_notes')
  const canSaveNotes = caseItem.status !== 'resolved' && notes.trim().length > 0

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] w-[calc(100vw-2rem)] max-w-5xl overflow-y-auto overflow-x-hidden border border-border bg-card p-0 sm:!max-w-5xl">
        <div className="w-full min-w-0 space-y-5 p-5 pr-10 sm:p-6 sm:pr-12">
          <DialogHeader className="space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0">
                <DialogTitle className="text-xl">{getIncidentTitle(caseItem.status)}</DialogTitle>
                <DialogDescription className="mt-1">
                  Case {shortCaseId(caseItem.caseId)}
                </DialogDescription>
              </div>
              <Badge className={getCaseStatusClass(caseItem.status)} variant="outline">
                {getCaseStatusLabel(caseItem.status)}
              </Badge>
            </div>
          </DialogHeader>

          <div className="grid w-full min-w-0 grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(280px,360px)]">
            <section className="w-full min-w-0 space-y-4">
              <div className="min-h-[240px] w-full overflow-hidden rounded-lg border border-border bg-[var(--media-background)]">
                {media.previewUrl && !imageLoadError ? (
                  media.mediaType === 'video' ? (
                    <video
                      src={media.previewUrl}
                      controls
                      preload="metadata"
                      onError={() => setImageLoadError(true)}
                      className="max-h-[28rem] w-full object-contain"
                    >
                      Your browser does not support video playback.
                    </video>
                  ) : (
                    <EvidenceImageWithBoxes
                      src={media.previewUrl}
                      onError={() => setImageLoadError(true)}
                      onLoad={() => setImageLoadError(false)}
                      boxes={caseItem.boxes}
                    />
                  )
                ) : (
                  <div className="flex min-h-64 items-center justify-center p-6 text-center text-sm text-muted-foreground">
                    {media.hasMediaPath
                      ? 'Media path exists, but the file could not be loaded.'
                      : 'No evidence media available for this case.'}
                  </div>
                )}
              </div>

              <div className="w-full min-w-0 rounded-lg border border-border bg-background/50 p-4">
                <h3 className="font-semibold">Incident Summary</h3>
                <div className="mt-3 space-y-3">
                  <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
                    <p className="shrink-0 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Confidence
                    </p>
                    <p className="break-words text-left text-sm font-semibold leading-snug text-foreground [overflow-wrap:anywhere] sm:text-right">
                      {(caseItem.confidence * 100).toFixed(0)}%
                    </p>
                  </div>
                  <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
                    <p className="shrink-0 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Time Detected
                    </p>
                    <p className="break-words text-left text-sm font-semibold leading-snug text-foreground [overflow-wrap:anywhere] sm:text-right">
                      {formatDetectedTime(caseItem.detectedAt)}
                    </p>
                  </div>
                  <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
                    <p className="shrink-0 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Location
                    </p>
                    <p className="whitespace-normal break-words text-left text-sm font-semibold leading-snug text-foreground [overflow-wrap:anywhere] sm:text-right">
                      {getIncidentLocationLabel(caseItem)}
                    </p>
                  </div>
                  <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
                    <p className="shrink-0 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Camera
                    </p>
                    <p className="break-words text-left text-sm font-semibold leading-snug text-foreground [overflow-wrap:anywhere] sm:text-right">
                      {caseItem.cameraName ?? caseItem.sourceCamera ?? caseItem.media.sourceFile ?? 'Device Live Camera'}
                    </p>
                  </div>
                  {isAdvancedMode ? (
                  <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
                    <p className="shrink-0 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Camera ID
                    </p>
                    <p className="break-words text-left text-sm font-semibold leading-snug text-foreground [overflow-wrap:anywhere] sm:text-right">
                      {caseItem.cameraId ?? 'Not provided'}
                    </p>
                  </div>
                  ) : null}
                  <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
                    <p className="shrink-0 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Area
                    </p>
                    <p className="break-words text-left text-sm font-semibold leading-snug text-foreground [overflow-wrap:anywhere] sm:text-right">
                      {caseItem.location.areaId ?? 'Unassigned'}
                    </p>
                  </div>
                  {isAdvancedMode ? (
                  <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
                    <p className="shrink-0 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Trigger
                    </p>
                    <p className="break-words text-left text-sm font-semibold leading-snug capitalize text-foreground [overflow-wrap:anywhere] sm:text-right">
                      {caseItem.triggerStatus.replaceAll('_', ' ')}
                    </p>
                  </div>
                  ) : null}
                  {isAdvancedMode ? (
                  <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
                    <p className="shrink-0 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Notification
                    </p>
                    <p className="break-words text-left text-sm font-semibold leading-snug text-foreground [overflow-wrap:anywhere] sm:text-right">
                      {caseItem.notificationId ?? 'Not linked'}
                    </p>
                  </div>
                  ) : null}
                </div>
              </div>
            </section>

            <aside className="w-full min-w-0 space-y-4">
              <section className="w-full min-w-0 rounded-lg border border-border bg-background/50 p-4">
                <h3 className="font-semibold">Responder Actions</h3>
                <div className="mt-3 grid gap-2">
                  {actions.map((item) => {
                    if (item.kind === 'map') {
                      return (
                        <Button key="map" asChild variant="outline" className="justify-start">
                          <a href={mapUrl} target="_blank" rel="noreferrer">
                            {item.icon}
                            Open Map
                          </a>
                        </Button>
                      )
                    }

                    if (item.kind === 'media') {
                      return (
                        <Button
                          key="media"
                          asChild={Boolean(media.fullUrl)}
                          disabled={!media.fullUrl}
                          variant="outline"
                          className="justify-start"
                        >
                          {media.fullUrl ? (
                            <a href={media.fullUrl} target="_blank" rel="noreferrer">
                              {item.icon}
                              View Full Media
                            </a>
                          ) : (
                            <span>{item.icon} View Full Media</span>
                          )}
                        </Button>
                      )
                    }

                    if (item.kind === 'history') {
                      return (
                        <Button
                          key="history"
                          type="button"
                          variant="outline"
                          className="justify-start"
                          onClick={() => openAccordionSection('history')}
                        >
                          {item.icon}
                          View Action History
                        </Button>
                      )
                    }

                    if (item.kind === 'details') {
                      return (
                        <Button
                          key="details"
                          type="button"
                          variant="outline"
                          className="justify-start"
                          onClick={() => openAccordionSection('details')}
                        >
                          {item.icon}
                          View Details
                        </Button>
                      )
                    }

                    return (
                      <Button
                        key={item.action}
                        type="button"
                        variant="outline"
                        onClick={() => handleAction(item.action)}
                        disabled={submittingAction != null}
                        className={`justify-start ${STATE_ACTION_CLASSES[item.action] ?? item.className ?? ''}`}
                      >
                        {item.icon}
                        {submittingAction === item.action
                          ? 'Saving...'
                          : item.label ?? CASE_ACTION_LABELS[item.action]}
                      </Button>
                    )
                  })}
                </div>
              </section>

              {caseItem.status !== 'resolved' ? (
                <section className="w-full min-w-0 rounded-lg border border-border bg-background/50 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="font-semibold">Notes</h3>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={!canSaveNotes || submittingAction != null}
                      onClick={saveNotes}
                    >
                      Save Notes
                    </Button>
                  </div>
                  <Textarea
                    value={notes}
                    onChange={(event) => setNotes(event.target.value)}
                    placeholder="Add review notes, contact result, dispatch details, or resolution reason."
                    className="mt-3 min-h-24 resize-none"
                  />
                  {caseItem.notes ? (
                    <p className="mt-3 line-clamp-3 whitespace-pre-wrap text-sm text-muted-foreground">
                      {caseItem.notes}
                    </p>
                  ) : null}
                </section>
              ) : (
                <section className="w-full min-w-0 rounded-lg border border-border bg-background/50 p-4 text-sm text-muted-foreground">
                  This case is resolved. Details remain available, but state-changing actions are locked.
                </section>
              )}
            </aside>
          </div>

          <Accordion
            type="multiple"
            value={openSections}
            onValueChange={setOpenSections}
            className="rounded-lg border border-border bg-background/40 px-4"
          >
            {isAdvancedMode ? (
            <AccordionItem value="details">
              <AccordionTrigger>
                <span className="inline-flex items-center gap-2">
                  <FileText className="h-4 w-4" />
                  More Details
                </span>
              </AccordionTrigger>
              <AccordionContent>
                <div className="grid gap-3 pb-3 text-sm sm:grid-cols-2">
                  <p><span className="text-muted-foreground">Full case ID:</span> {caseItem.caseId}</p>
                  <p><span className="text-muted-foreground">Notification ID:</span> {caseItem.notificationId ?? 'Not linked'}</p>
                  <p><span className="text-muted-foreground">Detection ID:</span> {caseItem.detectionId}</p>
                  <p><span className="text-muted-foreground">Trigger:</span> {caseItem.triggerStatus.replaceAll('_', ' ')}</p>
                  <p><span className="text-muted-foreground">Source:</span> {caseItem.media.source.replace('-', ' ')}</p>
                  <p><span className="text-muted-foreground">Camera:</span> {caseItem.cameraName ?? caseItem.sourceCamera ?? 'Not provided'}</p>
                  <p><span className="text-muted-foreground">Camera ID:</span> {caseItem.cameraId ?? 'Not provided'}</p>
                  <p><span className="text-muted-foreground">Area:</span> {caseItem.location.areaId ?? 'Unassigned'}</p>
                  <p><span className="text-muted-foreground">Updated:</span> {formatDetectedTime(caseItem.updatedAt)}</p>
                  <p><span className="text-muted-foreground">Coordinates:</span> {caseItem.location.latitude.toFixed(5)}, {caseItem.location.longitude.toFixed(5)}</p>
                  <p><span className="text-muted-foreground">Detection boxes:</span> {caseItem.boxes?.length ?? 0}</p>
                </div>
              </AccordionContent>
            </AccordionItem>
            ) : null}

            {isAdvancedMode ? (
              <AccordionItem value="media-debug">
                <AccordionTrigger>
                  <span className="inline-flex items-center gap-2">
                    <Eye className="h-4 w-4" />
                    Media Debug
                  </span>
                </AccordionTrigger>
                <AccordionContent>
                  <div className="grid gap-2 pb-3 text-xs sm:grid-cols-2">
                    <p className="break-all"><span className="text-muted-foreground">caseId:</span> {caseItem.caseId}</p>
                    <p className="break-all"><span className="text-muted-foreground">annotatedPath:</span> {caseItem.annotatedPath ?? 'null'}</p>
                    <p className="break-all"><span className="text-muted-foreground">keyFramePath:</span> {caseItem.keyFramePath ?? 'null'}</p>
                    <p className="break-all"><span className="text-muted-foreground">thumbnailPath:</span> {caseItem.thumbnailPath ?? 'null'}</p>
                    <p className="break-all"><span className="text-muted-foreground">videoPath:</span> {caseItem.videoPath ?? 'null'}</p>
                    <p className="break-all"><span className="text-muted-foreground">resolvedPreviewUrl:</span> {media.previewUrl ?? 'null'}</p>
                  </div>
                </AccordionContent>
              </AccordionItem>
            ) : null}

            <AccordionItem value="history" className="border-border">
              <AccordionTrigger className="hover:no-underline">
                <span className="flex items-center gap-2 font-semibold">
                  <ChevronDown className="h-4 w-4" />
                  Action History
                </span>
              </AccordionTrigger>
              <AccordionContent>
                <div className="space-y-3 pb-3">
                  {caseItem.actions.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No actions recorded.</p>
                  ) : (
                    caseItem.actions
                      .slice()
                      .reverse()
                      .map((action, index) => (
                        <div key={`${action.timestamp}-${index}`} className="text-sm">
                          <div className="flex flex-wrap items-center gap-2">
                            <Send className="h-3.5 w-3.5 text-muted-foreground" />
                            <span className="font-medium">
                              {CASE_ACTION_LABELS[action.action]}
                            </span>
                            <span className="text-xs text-muted-foreground">
                              {formatDetectedTime(action.timestamp)}
                            </span>
                          </div>
                          {action.notes ? (
                            <p className="ml-5 mt-1 whitespace-pre-wrap text-muted-foreground">
                              {action.notes}
                            </p>
                          ) : null}
                        </div>
                      ))
                  )}
                </div>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </div>
      </DialogContent>

      <Dialog open={showConfirmDispatchModal} onOpenChange={setShowConfirmDispatchModal}>
        <DialogContent className="max-w-md border border-border bg-card p-6">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <AlertTriangle className="h-5 w-5" />
              Confirm Emergency Dispatch
            </DialogTitle>
            <DialogDescription className="mt-2 text-sm text-muted-foreground">
              Dispatch incident to responders? This will verify the accident and create an emergency alert in the Responder Queue.
            </DialogDescription>
          </DialogHeader>
          <div className="mt-6 flex justify-end gap-3">
            <Button
              type="button"
              variant="outline"
              onClick={() => setShowConfirmDispatchModal(false)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={submittingAction != null}
              onClick={async () => {
                setShowConfirmDispatchModal(false)
                await handleAction('dispatch_help')
              }}
            >
              {submittingAction === 'dispatch_help' ? 'Dispatching...' : 'YES, Confirm & Dispatch'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </Dialog>
  )
}
