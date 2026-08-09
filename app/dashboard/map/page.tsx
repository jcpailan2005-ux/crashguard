'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import dynamic from 'next/dynamic'
import { useRouter, useSearchParams } from 'next/navigation'
import {
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  MapPin,
  Video,
  XCircle,
} from 'lucide-react'

import { useAuth } from '@/components/auth-provider'
import { DashboardHeader, Sidebar } from '@/components/dashboard-sidebar'
import { IncidentReviewDialog } from '@/components/incident-review-dialog'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { useToast } from '@/hooks/use-toast'
import {
  applyLocalCrashCaseAction,
  getLocalCrashCase,
  getLocalCrashCases,
  resolveBackendMediaUrl,
} from '@/lib/api-client'
import { caseMedia as getCaseMedia, localCaseToCrashCase as mapLocalCaseToCrashCase } from '@/lib/crash-case-mapper'
import {
  applyMapReviewDecision,
  subscribeCrashCases,
} from '@/lib/crash-case-store'
import { getFirebaseConfigError, getFirestoreOrNull } from '@/lib/firebase-guards'
import { ACTIVE_CASE_STATUSES, getCaseStatusLabel, getIncidentTitle } from '@/lib/incident-status'
import { getCaseStatusClass } from '@/lib/theme-status'
import { CrashCase, DetectionBox, LocalCrashCase } from '@/lib/types'

const MapComponent = dynamic(() => import('@/components/live-map'), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center bg-card text-muted-foreground">
      Loading map...
    </div>
  ),
})

function formatTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Time unavailable'
  return date.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function shortCaseId(caseId: string) {
  return caseId.length > 10 ? `${caseId.slice(0, 4)}...${caseId.slice(-4)}` : caseId
}

function caseMedia(caseItem: CrashCase | null) {
  if (!caseItem) {
    return { previewUrl: null, fullUrl: null, mediaType: 'image' as const }
  }

  return {
    previewUrl: resolveBackendMediaUrl(
      caseItem.media.annotatedKeyFrameUrl ||
        caseItem.media.keyFrameUrl ||
        caseItem.keyFramePath ||
        caseItem.media.annotatedMediaDownloadUrl ||
        caseItem.media.annotatedMediaUrl ||
        null
    ),
    fullUrl: resolveBackendMediaUrl(
      caseItem.media.keyFrameUrl ||
        caseItem.keyFramePath ||
        caseItem.media.annotatedMediaUrl ||
        caseItem.media.annotatedMediaDownloadUrl ||
        caseItem.media.annotatedKeyFrameUrl ||
        null
    ),
    mediaType: caseItem.media.mediaType === 'video' ? 'video' as const : 'image' as const,
  }
}

function localCaseToCrashCase(caseItem: LocalCrashCase): CrashCase {
  return {
    caseId: caseItem.caseId,
    detectionId: caseItem.caseId,
    status: caseItem.status,
    reviewerId: caseItem.responderId ?? null,
    user: null,
    vehicle: null,
    location: {
      label:
        caseItem.roadName && caseItem.barangay
          ? `${caseItem.barangay} · ${caseItem.roadName}`
          : caseItem.location ?? 'Local crash case',
      latitude: caseItem.latitude ?? 7.1907,
      longitude: caseItem.longitude ?? 125.4553,
      areaId: caseItem.areaId ?? null,
      isFallback: caseItem.latitude == null || caseItem.longitude == null,
    },
    media: {
      mediaType: caseItem.videoPath ? 'video' : 'image',
      source: 'upload',
      sourceFile: caseItem.cameraName ?? caseItem.sourceCamera ?? null,
      annotatedMediaUrl: caseItem.annotatedPath ? `/${caseItem.annotatedPath}` : null,
      annotatedMediaDownloadUrl: caseItem.videoPath ? `/${caseItem.videoPath}` : null,
      annotatedKeyFrameUrl: caseItem.keyFramePath ? `/${caseItem.keyFramePath}` : null,
      keyFrameUrl: caseItem.keyFramePath ? `/${caseItem.keyFramePath}` : null,
    },
    confidence: caseItem.confidence,
    notes: caseItem.notes ?? '',
    actions: [],
    acknowledgedAt: caseItem.reviewedAt ?? null,
    confirmedAt: caseItem.confirmedAt ?? null,
    createdAt: caseItem.detectedAt,
    detectedAt: caseItem.detectedAt,
    dispatchedAt: caseItem.dispatchedAt ?? null,
    falseAlarmAt: caseItem.falseAlarmAt ?? null,
    resolvedAt: caseItem.resolvedAt ?? null,
    triggerStatus: caseItem.triggerStatus === 'camera_detection' ||
      caseItem.triggerStatus === 'upload_detection' ||
      caseItem.triggerStatus === 'sample_detection' ||
      caseItem.triggerStatus === 'manual_report' ||
      caseItem.triggerStatus === 'unknown'
      ? caseItem.triggerStatus
      : 'unknown',
    updatedAt: caseItem.updatedAt,
    accidentDetected: caseItem.accidentDetected,
    detections: caseItem.detections ?? [],
    boxes: caseItem.boxes ?? [],
  }
}

function EvidenceImageWithBoxes({
  boxes,
  onError,
  src,
}: {
  boxes?: DetectionBox[]
  onError?: () => void
  src: string
}) {
  const [naturalSize, setNaturalSize] = useState({ width: 1, height: 1 })
  const visibleBoxes = boxes?.filter((box) => box.width > 0 && box.height > 0) ?? []
  const toPercent = (value: number, axis: 'x' | 'y') => {
    if (value <= 1) return value * 100
    return (value / (axis === 'x' ? naturalSize.width : naturalSize.height)) * 100
  }

  return (
    <div className="flex justify-center">
      <div className="relative inline-block max-w-full">
        <img
          src={src}
          alt="Detected crash evidence"
          className="block max-h-64 max-w-full object-contain"
          onError={onError}
          onLoad={(event) => {
            setNaturalSize({
              width: event.currentTarget.naturalWidth || 1,
              height: event.currentTarget.naturalHeight || 1,
            })
          }}
        />
        {visibleBoxes.length > 0 ? (
          <div className="pointer-events-none absolute inset-0">
            {visibleBoxes.map((box, index) => (
              <div
                key={`${box.label}-${index}`}
                className="absolute border-2 border-[var(--status-warning)] bg-[color:var(--status-warning-bg)]/20"
                style={{
                  left: `${toPercent(box.x, 'x')}%`,
                  top: `${toPercent(box.y, 'y')}%`,
                  width: `${toPercent(box.width, 'x')}%`,
                  height: `${toPercent(box.height, 'y')}%`,
                }}
              >
                <span className="absolute left-0 top-0 max-w-full -translate-y-full truncate rounded-sm bg-[var(--status-warning)] px-1.5 py-0.5 text-[10px] font-semibold text-background">
                  {box.label} {(box.confidence * 100).toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  )
}

export default function LiveMapPage() {
  const searchParams = useSearchParams()
  const requestedCaseId = searchParams.get('caseId')
  const [cases, setCases] = useState<CrashCase[]>([])
  const [localCases, setLocalCases] = useState<CrashCase[]>([])
  const [selectedCase, setSelectedCase] = useState<CrashCase | null>(null)
  const [reviewDialogOpen, setReviewDialogOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [storeError, setStoreError] = useState<string | null>(null)
  const [loadingUrlCaseId, setLoadingUrlCaseId] = useState<string | null>(null)
  const [urlCaseError, setUrlCaseError] = useState<string | null>(null)
  const [mediaLoadError, setMediaLoadError] = useState(false)
  const [deciding, setDeciding] = useState<'legit_crash' | 'false_alarm' | null>(null)
  const handledUrlCaseIdRef = useRef<string | null>(null)
  const { firebaseUser, profile } = useAuth()
  const { toast } = useToast()

  useEffect(() => {
    const db = getFirestoreOrNull()
    const configError = getFirebaseConfigError()

    if (!db || configError) {
      setStoreError(configError ?? 'Firestore is not ready.')
      setLoading(false)
      return
    }

    if (profile?.role === 'responder' && !profile.areaId) {
      setStoreError('Responder account has no assigned area. Ask an admin to update users/{uid}.')
      setLoading(false)
      return
    }

    return subscribeCrashCases(
      db,
      (nextCases) => {
        setCases(nextCases)
        setStoreError(null)
        setLoading(false)
      },
      (error) => {
        setStoreError(error.message)
        setLoading(false)
      },
      profile?.role === 'responder' ? profile.areaId : null
    )
  }, [profile])

  const refreshLocalCases = () => {
    getLocalCrashCases({ limit: 200 })
      .then((items) => setLocalCases(items.map(mapLocalCaseToCrashCase)))
      .catch(() => setLocalCases([]))
  }

  useEffect(() => {
    refreshLocalCases()
  }, [])

  const combinedCases = useMemo(() => {
    const seen = new Set<string>()
    return [...localCases, ...cases].filter((caseItem) => {
      if (seen.has(caseItem.caseId)) return false
      seen.add(caseItem.caseId)
      if (profile?.role === 'responder') {
        return ['dispatched', 'responding', 'arrived', 'resolved'].includes(caseItem.status)
      }
      return true
    })
  }, [cases, localCases, profile?.role])

  const openReviewCase = (caseItem: CrashCase) => {
    setSelectedCase(caseItem)
    setReviewDialogOpen(true)
  }

  useEffect(() => {
    const caseId = requestedCaseId
    if (!caseId || handledUrlCaseIdRef.current === caseId) return

    setUrlCaseError(null)
    if (caseId.startsWith('CASE-') && loadingUrlCaseId !== caseId) {
      handledUrlCaseIdRef.current = caseId
      setLoadingUrlCaseId(caseId)
      getLocalCrashCase(caseId)
        .then((localCase) => {
          const mappedCase = mapLocalCaseToCrashCase(localCase)
          setLocalCases((previous) =>
            previous.some((caseItem) => caseItem.caseId === mappedCase.caseId)
              ? previous.map((caseItem) =>
                  caseItem.caseId === mappedCase.caseId ? mappedCase : caseItem
                )
              : [mappedCase, ...previous]
          )
          openReviewCase(mappedCase)
        })
        .catch(() => {
          setUrlCaseError('Case not found or no longer available.')
        })
        .finally(() => {
          setLoadingUrlCaseId(null)
        })
      return
    }

    const matchingCase = combinedCases.find((caseItem) => caseItem.caseId === caseId)
    if (matchingCase) {
      handledUrlCaseIdRef.current = caseId
      openReviewCase(matchingCase)
      return
    }

    if (!caseId.startsWith('CASE-') && !loading) {
      handledUrlCaseIdRef.current = caseId
      setUrlCaseError('Case not found or no longer available.')
    }
  }, [combinedCases, loading, loadingUrlCaseId, requestedCaseId])

  useEffect(() => {
    if (!selectedCase) return
    const latest = combinedCases.find((caseItem) => caseItem.caseId === selectedCase.caseId)
    if (latest && latest !== selectedCase) {
      setSelectedCase(latest)
    }
  }, [combinedCases, selectedCase])

  const activeCases = combinedCases.filter((caseItem) =>
    ACTIVE_CASE_STATUSES.has(caseItem.status)
  )
  const visibleCases = useMemo(() => {
    if (!selectedCase || activeCases.some((caseItem) => caseItem.caseId === selectedCase.caseId)) {
      return activeCases
    }

    return [selectedCase, ...activeCases]
  }, [activeCases, selectedCase])
  const media = getCaseMedia(selectedCase)
  const actorId = firebaseUser?.uid ?? 'map-responder'
  const canDecide =
    selectedCase?.status === 'pending_review' || selectedCase?.status === 'under_review'

  useEffect(() => {
    setMediaLoadError(false)
  }, [media.previewUrl])

  const handleDecision = async (decision: 'legit_crash' | 'false_alarm') => {
    if (!selectedCase) return

    setDeciding(decision)
    try {
      if (selectedCase.caseId.startsWith('CASE-')) {
        if (selectedCase.status === 'pending_review') {
          await applyLocalCrashCaseAction(selectedCase.caseId, {
            action: 'review_alert',
            actorId,
          })
        }
        await applyLocalCrashCaseAction(selectedCase.caseId, {
          action: decision === 'legit_crash' ? 'confirm_crash' : 'mark_false_alarm',
          actorId,
        })
        refreshLocalCases()
      } else {
        const db = getFirestoreOrNull()
        if (!db) return
        await applyMapReviewDecision(db, {
          actorId,
          caseItem: selectedCase,
          decision,
        })
      }
      toast({
        title: decision === 'legit_crash' ? 'Crash confirmed' : 'Marked false alarm',
        description: `Case ${shortCaseId(selectedCase.caseId)} was updated from map review.`,
      })
    } catch (error) {
      toast({
        title: 'Decision failed',
        description:
          error instanceof Error ? error.message : 'Could not update the crash case.',
        variant: 'destructive',
      })
    } finally {
      setDeciding(null)
    }
  }

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <div className="flex-1 md:ml-0">
        <DashboardHeader />

        <main className="grid min-h-[calc(100vh-96px)] gap-4 overflow-x-hidden p-4 lg:grid-cols-[minmax(0,1fr)_24rem] lg:p-6">
          <section className="relative z-0 min-h-[22rem] overflow-hidden rounded-md border border-border lg:h-full lg:min-h-0">
            <MapComponent cases={visibleCases} selectedCase={selectedCase} />
          </section>

          <aside className="relative z-20 flex min-w-0 flex-col gap-4 lg:max-h-[calc(100vh-144px)] lg:overflow-hidden">
            <div className="shrink-0">
              <h1 className="text-xl font-bold">Map Evidence Review</h1>
              <p className="text-sm text-muted-foreground">
                Review location, camera context, and detection media before confirming.
              </p>
            </div>

            {storeError ? (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>{storeError}</AlertDescription>
              </Alert>
            ) : null}

            {urlCaseError ? (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>{urlCaseError}</AlertDescription>
              </Alert>
            ) : null}

            {loading ? (
              <Card className="relative z-30 p-4 text-center text-muted-foreground">Loading cases...</Card>
            ) : !selectedCase ? (
              <Card className="relative z-30 min-h-0 overflow-y-auto p-5 lg:flex-1">
                <div className="mb-4 flex items-center gap-2">
                  <MapPin className="h-5 w-5 text-muted-foreground" />
                  <p className="font-semibold">Select a possible crash</p>
                </div>
                <div className="space-y-2">
                  {activeCases.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No active cases on the map.</p>
                  ) : (
                    activeCases.map((caseItem) => (
                      <button
                        key={caseItem.caseId}
                        type="button"
                        onClick={() => openReviewCase(caseItem)}
                        className="w-full rounded-md border border-border p-3 text-left transition-colors hover:bg-muted/50"
                      >
                        <p className="font-medium">{caseItem.location.label}</p>
                        <p className="text-sm text-muted-foreground">
                          {(caseItem.confidence * 100).toFixed(0)}% confidence
                        </p>
                      </button>
                    ))
                  )}
                </div>
              </Card>
            ) : (
              <>
                <Card className="relative z-30 min-h-0 space-y-4 overflow-y-auto border border-border p-4 lg:flex-1">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm text-muted-foreground">
                        {getIncidentTitle(selectedCase.status)} · Case {shortCaseId(selectedCase.caseId)}
                      </p>
                      <h2 className="break-words text-lg font-semibold [overflow-wrap:anywhere]">
                        {selectedCase.location.label}
                      </h2>
                    </div>
                    <Badge className={getCaseStatusClass(selectedCase.status)} variant="outline">
                      {getCaseStatusLabel(selectedCase.status)}
                    </Badge>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
                    <div className="rounded-md border border-border bg-muted/20 p-3">
                      <p className="text-sm text-muted-foreground">Confidence</p>
                      <p className="text-2xl font-semibold">
                        {(selectedCase.confidence * 100).toFixed(0)}%
                      </p>
                    </div>
                    <div className="rounded-md border border-border bg-muted/20 p-3">
                      <p className="text-sm text-muted-foreground">Time Detected</p>
                      <p className="font-medium">{formatTime(selectedCase.detectedAt)}</p>
                    </div>
                  </div>

                  {selectedCase.location.isFallback ? (
                    <Alert>
                      <MapPin className="h-4 w-4" />
                      <AlertDescription>
                        Using fallback demo coordinates until real source coordinates are available.
                      </AlertDescription>
                    </Alert>
                  ) : null}

                  <div className="overflow-hidden rounded-md border border-border bg-[var(--media-background)]">
                    {media.previewUrl && !mediaLoadError ? (
                      media.mediaType === 'video' && !selectedCase.media.annotatedKeyFrameUrl ? (
                        <video
                          src={media.previewUrl}
                          controls
                          preload="metadata"
                          onError={() => setMediaLoadError(true)}
                          className="max-h-64 w-full object-contain"
                        >
                          Your browser does not support video playback.
                        </video>
                      ) : (
                        <EvidenceImageWithBoxes
                          src={media.previewUrl}
                          boxes={selectedCase.boxes}
                          onError={() => setMediaLoadError(true)}
                        />
                      )
                    ) : (
                      <div className="flex min-h-44 items-center justify-center p-5 text-center text-sm text-muted-foreground">
                        {media.previewUrl
                          ? 'Evidence media path exists, but the file could not be loaded.'
                          : 'No evidence media available for this case.'}
                      </div>
                    )}
                  </div>

                  <div className="rounded-md border border-border bg-muted/20 p-3">
                    <div className="flex items-center gap-2">
                      <Video className="h-4 w-4 text-muted-foreground" />
                      <p className="font-medium">Camera / Source Context</p>
                    </div>
                    <p className="mt-1 break-words text-sm text-muted-foreground [overflow-wrap:anywhere]">
                      {selectedCase.media.source.replace('-', ' ')}
                      {selectedCase.media.sourceFile ? `: ${selectedCase.media.sourceFile}` : ''}
                    </p>
                    <p className="mt-2 text-sm text-muted-foreground">
                      Nearby/live camera feeds are represented by the selected source in this
                      school-demo build.
                    </p>
                  </div>

                  <div className="grid min-w-0 gap-2 sm:grid-cols-2">
                    <Button
                      type="button"
                      disabled={!canDecide || deciding != null}
                      onClick={() => handleDecision('legit_crash')}
                      className="bg-[var(--status-confirmed)] text-primary-foreground hover:bg-[var(--status-confirmed)]/90"
                    >
                      <CheckCircle2 className="h-4 w-4" />
                      Legit Crash
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      disabled={!canDecide || deciding != null}
                      onClick={() => handleDecision('false_alarm')}
                      className="border-[var(--status-false-alarm)] bg-[color:var(--status-false-alarm-bg)] text-[var(--status-false-alarm)] hover:bg-[color:var(--status-false-alarm-bg)]"
                    >
                      <XCircle className="h-4 w-4" />
                      False Alarm
                    </Button>
                  </div>

                  <div className="grid min-w-0 gap-2 sm:grid-cols-2">
                    {media.fullUrl ? (
                      <Button asChild variant="outline">
                        <a href={media.fullUrl} target="_blank" rel="noreferrer">
                          <ExternalLink className="h-4 w-4" />
                          View Full Video
                        </a>
                      </Button>
                    ) : null}
                    <Button asChild variant="outline">
                      <a href="/dashboard">Back to Dashboard</a>
                    </Button>
                  </div>

                  {!canDecide ? (
                    <p className="text-sm text-muted-foreground">
                      This case is no longer awaiting a map review decision.
                    </p>
                  ) : null}
                </Card>

                <Card className="relative z-30 max-h-56 shrink-0 overflow-y-auto border border-border p-3">
                  <p className="mb-2 font-semibold">Active Map Queue</p>
                  <div className="space-y-2">
                    {activeCases.map((caseItem) => (
                      <button
                        key={caseItem.caseId}
                        type="button"
                        onClick={() => openReviewCase(caseItem)}
                        className={`w-full rounded-md border p-2 text-left text-sm transition-colors ${
                          selectedCase.caseId === caseItem.caseId
                            ? 'border-primary bg-primary/10'
                            : 'border-border hover:bg-muted/50'
                        }`}
                      >
                        <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
                          <span className="min-w-0 flex-1 truncate">{caseItem.location.label}</span>
                          <Badge className={getCaseStatusClass(caseItem.status)} variant="outline">
                            {getCaseStatusLabel(caseItem.status)}
                          </Badge>
                        </div>
                      </button>
                    ))}
                  </div>
                </Card>
              </>
            )}
          </aside>
        </main>
      </div>

      <IncidentReviewDialog
        actorId={actorId}
        caseItem={selectedCase}
        onCaseUpdated={(caseItem) => {
          setSelectedCase(caseItem)
          if (caseItem.caseId.startsWith('CASE-')) {
            setLocalCases((previous) =>
              previous.map((item) =>
                item.caseId === caseItem.caseId ? caseItem : item
              )
            )
          }
        }}
        onOpenChange={(open) => {
          setReviewDialogOpen(open)
        }}
        open={reviewDialogOpen && selectedCase != null}
      />
    </div>
  )
}
