'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import { AlertTriangle, Grid2X2, ListFilter, MapPin, Maximize2, Plus, RefreshCw, Save, Search, Trash2, Video } from 'lucide-react'

import { LiveCamera } from '@/components/live-camera'
import { CameraDetectionSurface } from '@/components/camera-detection-grid'
import { Alert, AlertDescription } from '@/components/ui/alert'
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
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useAuth } from '@/components/auth-provider'
import {
  fetchCameraPreviewFrameObjectUrl,
  deleteCctvCamera,
  disableCctvCamera,
  enableCctvCamera,
  getCameraMonitoringStatus,
  getCctvCameras,
  getLocalWebcamSources,
  saveCctvCamera,
  startCctvMonitoring,
  testCameraConnection,
  type CameraMonitoringStatus,
} from '@/lib/api-client'
import { liveAlarmTracker } from '@/lib/incident-alarm-contract'
import { canManageCamera, isProtectedCamera } from '@/lib/camera-management-permissions'
import { playAccidentAlert } from '@/lib/accident-alert'
import { useDisplayMode } from '@/lib/display-mode'
import { CctvCamera, DetectionResponse } from '@/lib/types'

type CameraFormState = {
  cameraId: string
  cameraName: string
  cameraIp: string
  streamUrl: string
  areaId: string
  location: string
}

type CameraSlot = {
  camera: CctvCamera | null
  slotNumber: number
}

type AddCameraFormState = {
  cameraType: 'network' | 'webcam'
  streamUrl: string
  location: string
  cameraName: string
  webcamReference: string
}

const CAMERA_CACHE_KEY = 'mycrushguard.savedCctvCamera'
const RESPONDER_CAMERA_IDS_KEY = 'mycrushguard.responderCameraIds'
const HIDDEN_CAMERA_IDS_KEY = 'mycrushguard.hiddenCameraFeedIds'
const RESPONDER_CAMERA_TYPE = 'Responder RTSP Stream'

function isDemoCamera(camera: CctvCamera) {
  return (
    camera.cameraType === 'Demo' ||
    camera.streamUrl?.startsWith('demo://') ||
    camera.cameraIp?.startsWith('demo-')
  )
}

function isSensitiveCameraText(value?: string | null) {
  const text = value?.trim()
  if (!text) return false

  return (
    /rtsp:\/\//i.test(text) ||
    /https?:\/\//i.test(text) ||
    /@/.test(text) ||
    /:554\b/i.test(text) ||
    /\b[^\s:/]+:[^\s@/]+@/.test(text) ||
    /crashguardadmin/i.test(text) ||
    /cctv\s*\([^)]*(?:@|:\d{2,5}|rtsp|https?|crashguardadmin|[0-9]{1,3}(?:\.[0-9]{1,3}){3})/i.test(text)
  )
}

function sanitizeCameraDisplayName(value?: string | null) {
  const text = value?.trim()
  if (!text || isSensitiveCameraText(text)) return 'CCTV'
  return text
}

function sanitizeCameraLocation(value?: string | null) {
  const text = value?.trim()
  if (!text || isSensitiveCameraText(text)) return null
  return text
}

function safeCameraName(camera: CctvCamera | null) {
  if (!camera) return 'CCTV'
  const rawCameraName = (camera as CctvCamera & { cameraName?: string | null }).cameraName
  const safeLabel = camera.label && !isSensitiveCameraText(camera.label)
    ? sanitizeCameraDisplayName(camera.label)
    : null
  const safeName = rawCameraName && !isSensitiveCameraText(rawCameraName)
    ? sanitizeCameraDisplayName(rawCameraName)
    : null
  const safeArea = sanitizeCameraLocation(camera.areaId)
  return safeLabel ?? safeName ?? (safeArea ? `${safeArea} CCTV` : 'CCTV')
}

function safeCameraLocation(camera: CctvCamera | null) {
  if (!camera) return 'Not specified'

  return (
    sanitizeCameraLocation(camera.location) ??
    sanitizeCameraLocation(camera.locationDescription) ??
    sanitizeCameraLocation(camera.roadName) ??
    sanitizeCameraLocation(camera.barangay) ??
    sanitizeCameraLocation(camera.areaId) ??
    'Not specified'
  )
}

function emptyCameraForm(areaId: string): CameraFormState {
  return {
    cameraId: '',
    cameraName: '',
    cameraIp: '',
    streamUrl: '',
    areaId,
    location: '',
  }
}

function emptyAddCameraForm(): AddCameraFormState {
  return {
    cameraType: 'network',
    streamUrl: '',
    location: '',
    cameraName: '',
    webcamReference: '',
  }
}

function cameraToForm(camera: CctvCamera, fallbackAreaId: string): CameraFormState {
  return {
    cameraId: camera.cameraId,
    cameraName: safeCameraName(camera),
    cameraIp: camera.cameraIp ?? '',
    // IP cameras use backend camera credentials, so avoid showing the redacted RTSP label as editable input.
    streamUrl: camera.cameraIp ? '' : camera.streamUrl ?? '',
    areaId: camera.areaId ?? fallbackAreaId,
    location: safeCameraLocation(camera),
  }
}

function pickDefaultCamera(cameras: CctvCamera[], areaId: string) {
  const saved = cameras.filter(
    (camera) => camera.isActive && camera.detectionEnabled && !isDemoCamera(camera)
  )
  return (
    saved.find((camera) => camera.areaId === areaId) ??
    saved[0] ??
    null
  )
}

function cameraLocationLabel(camera: CctvCamera | null, fallbackAreaId: string) {
  if (!camera) return 'Not specified'
  return safeCameraLocation(camera)
}

function normalizeRtspUrl(value: string): string {
  let trimmed = value.trim().replace(/^["']|["']$/g, '')
  if (/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?(\/.*)?$/i.test(trimmed)) {
    trimmed = `rtsp://${trimmed}`
  }
  return trimmed
}

function isRtspStreamUrl(value: string) {
  const norm = normalizeRtspUrl(value)
  return /^(rtsps?|https?):\/\/\S+$/i.test(norm)
}

function isResponderCreatedCamera(camera: CctvCamera) {
  return (
    camera.cameraType === RESPONDER_CAMERA_TYPE ||
    (camera.cameraType === 'RTSP Stream' && camera.label.startsWith('Responder CCTV Camera'))
  )
}

function readResponderCameraIds() {
  if (typeof window === 'undefined') return new Set<string>()

  try {
    const raw = window.localStorage.getItem(RESPONDER_CAMERA_IDS_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return new Set(Array.isArray(parsed) ? parsed.filter((value) => typeof value === 'string') : [])
  } catch {
    return new Set<string>()
  }
}

function writeResponderCameraIds(ids: Set<string>) {
  window.localStorage.setItem(RESPONDER_CAMERA_IDS_KEY, JSON.stringify([...ids]))
}

function readHiddenCameraIds() {
  if (typeof window === 'undefined') return new Set<string>()

  try {
    const raw = window.localStorage.getItem(HIDDEN_CAMERA_IDS_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return new Set(Array.isArray(parsed) ? parsed.filter((value) => typeof value === 'string') : [])
  } catch {
    return new Set<string>()
  }
}

function writeHiddenCameraIds(ids: Set<string>) {
  window.localStorage.setItem(HIDDEN_CAMERA_IDS_KEY, JSON.stringify([...ids]))
}

function cameraStatusFrameUrl(status?: CameraMonitoringStatus, size: 'thumb' | 'full' = 'thumb') {
  const base = status?.latestFrameUrl ?? status?.frameUrl ?? status?.previewUrl ?? status?.imageUrl ?? null
  if (!base) return null
  if (size === 'thumb') {
    return base.includes('?') ? `${base}&size=thumb` : `${base}?size=thumb`
  }
  return base
}

function cameraStatusBadges(status: CameraMonitoringStatus | undefined, camera: CctvCamera | null) {
  if (!camera || !camera.isActive) return ['DISABLED']
  if (status?.cameraHealth === 'DISABLED') return ['DISABLED']
  if (status?.reconnecting || status?.status === 'reconnecting') return ['RECONNECTING']
  if (status?.cameraHealth === 'OFFLINE' || (status?.status as string) === 'offline' || status?.status === 'disconnected' || status?.lastError) {
    return ['OFFLINE']
  }
  const isStale = status?.cameraHealth === 'STALE' || (typeof status?.frameAgeMs === 'number' && status.frameAgeMs > 15000)
  if (isStale) return ['STALE']

  const hasFreshFrame = Boolean(status?.latestFrameAvailable || status?.latestFrameReceived)
  if (!hasFreshFrame && !status?.monitoringLive) return ['OFFLINE']

  const badges: string[] = []
  if (hasFreshFrame && (status?.cameraHealth === 'ONLINE' || status?.monitoringLive || status?.cameraConnected)) {
    badges.push('ONLINE')
    badges.push('LIVE')
  }
  if (hasFreshFrame && status?.detectionRunning) {
    badges.push('SCANNING')
  }
  const result = status?.latestResult
  const mode = result?.detectionMode ?? result?.detection_mode
  if (mode === 'aftermath_review' && result?.incidentCreated) {
    badges.push('PENDING REVIEW')
  } else if (result?.aftermathSuspected) {
    badges.push('POSSIBLE AFTERMATH')
  }
  if (mode === 'temporal_collision' && result?.incidentCreated) {
    badges.push('CONFIRMED INCIDENT')
  }
  if (typeof status?.frameAgeMs === 'number' && status.frameAgeMs > 10_000) {
    badges.push('STALE')
  }
  if (isLowQualityFrame(status?.latestResult)) {
    badges.push('LOW QUALITY')
  }
  return badges.length > 0 ? badges : ['OFFLINE']
}

function statusBadgeVariant(label: string): 'default' | 'secondary' | 'outline' | 'destructive' {
  if (label === 'PENDING REVIEW' || label === 'CONFIRMED INCIDENT') return 'destructive'
  if (label === 'LOW QUALITY' || label === 'STALE') return 'secondary'
  if (label === 'POSSIBLE AFTERMATH') return 'secondary'
  if (label === 'LIVE' || label === 'SCANNING' || label === 'ONLINE') return 'default'
  if (label === 'RECONNECTING') return 'secondary'
  if (label === 'DISABLED') return 'outline'
  return 'outline'
}

function formatConfidence(value?: number | null) {
  if (typeof value !== 'number') return 'No confidence yet'
  return `${Math.round(value * 100)}%`
}

function formatMilliseconds(value?: number | null) {
  return typeof value === 'number' ? `${Math.round(value)} ms` : 'Unavailable'
}

function cameraSourceType(camera: CctvCamera) {
  const type = String(camera.cameraType ?? '').toLowerCase()
  return type.includes('webcam') || camera.streamSourceLabel?.toLowerCase().includes('webcam')
    ? 'USB Webcam'
    : 'CCTV'
}

function collisionStatus(status?: CameraMonitoringStatus) {
  const result = status?.latestResult
  const decision = result?.finalDecision
  if (decision === 'confirmed_crash' && (result?.incidentCreated || result?.incident_created)) return 'INCIDENT SENT'
  if (decision === 'confirmed_crash') return 'CONFIRMED CRASH'
  if (decision === 'candidate' || result?.aftermathSuspected || (result?.consecutiveCrashHits ?? 0) > 0) {
    return 'ANALYZING POTENTIAL COLLISION'
  }
  return 'MONITORING'
}

function normalizeConfidenceFraction(value: number | null | undefined): number | null {
  if (value == null) return null
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return null
  return numeric > 1 ? numeric / 100 : numeric
}

function detectionReviewCaseId(result?: DetectionResponse | null): string | null {
  if (!result) return null
  return (
    result.caseId ??
    (result as DetectionResponse & { reviewCaseId?: string | null }).reviewCaseId ??
    (result as DetectionResponse & { case_id?: string | null }).case_id ??
    null
  )
}

function isLowQualityFrame(result?: DetectionResponse | null): boolean {
  return result?.frameQualityStatus === 'bad'
}

function getFrameQualityMessage(result?: DetectionResponse | null): string {
  switch (result?.qualityRejectionReason) {
    case 'low_quality_blurry_frame':
      return 'Camera quality too low: unclear frame (too blurry).'
    case 'low_quality_dark_frame':
      return 'Camera quality too low: frame is too dark.'
    case 'low_quality_overexposed_frame':
      return 'Camera quality too low: frame is overexposed.'
    case 'low_quality_low_contrast_frame':
      return 'Camera quality too low: unclear frame (low contrast).'
    default:
      return 'Camera quality too low. Unclear frame.'
  }
}

function isSavedCrashCase(result?: DetectionResponse | null): boolean {
  if (!result) return false
  if (isLowQualityFrame(result)) return false

  const status = String(result.persistenceStatus ?? result.casePersistenceStatus ?? '').toLowerCase()
  const reason = String(result.persistenceReason ?? '').toLowerCase()
  const blockedStatuses = new Set([
    'below_threshold',
    'below_case_threshold',
    'non_accident',
    'vehicle_only',
    'no_case_created',
    'no_review_case',
    'waiting_for_consecutive_frames',
    'temporal_not_confirmed',
    'duplicate_cooldown',
    'cooldown_active',
    'blocked_existing_case',
    'no_vehicle_detected',
    'person_only_not_crash',
    'vehicle_outside_roi',
    'motion_not_crash_like',
    'active_case_exists',
    'low_quality_blurry_frame',
    'low_quality_dark_frame',
    'low_quality_overexposed_frame',
    'low_quality_low_contrast_frame',
  ])
  const crashClass = String(result.crashClass ?? '').toLowerCase()
  const confidence =
    normalizeConfidenceFraction(result.crashConfidence) ??
    normalizeConfidenceFraction(result.rawCrashConfidence) ??
    normalizeConfidenceFraction(result.lastConfidence) ??
    normalizeConfidenceFraction(result.confidence)
  const threshold = Math.max(normalizeConfidenceFraction(result.requiredThreshold) ?? 0.8, 0.8)
  const savedStatus =
    status === 'case_created' ||
    status === 'created' ||
    status === 'notification_created' ||
    reason === 'case_created'
  const committedIncident =
    result.incident_created === true || result.incidentCreated === true

  if (blockedStatuses.has(status) || blockedStatuses.has(reason)) {
    return false
  }

  if (detectionReviewCaseId(result) && committedIncident && savedStatus) {
    return true
  }

  return Boolean(
    detectionReviewCaseId(result) &&
      crashClass === 'accident' &&
      confidence != null &&
      confidence >= threshold &&
      savedStatus
  )
}

function latestAlertId(status?: CameraMonitoringStatus) {
  return isSavedCrashCase(status?.latestResult)
    ? detectionReviewCaseId(status?.latestResult)
    : null
}

function buildCameraSlots(cameras: CctvCamera[]): CameraSlot[] {
  const slots: CameraSlot[] = cameras.map((camera, index) => ({ camera, slotNumber: index + 1 }))
  if (slots.length < 3) {
    slots.push({ camera: null, slotNumber: slots.length + 1 })
  }
  return slots
}

export function CctvMonitorWorkspace({ managementMode = false, initialCameraId }: { managementMode?: boolean; initialCameraId?: string | null }) {
  const { profile, loading: authLoading, personalPreferences } = useAuth()
  const { isAdvancedMode } = useDisplayMode(profile)
  const areaId = profile?.areaId ?? 'talomo'
  const normalizedRole = String(profile?.role ?? '').toLowerCase()
  const isResponder = normalizedRole === 'responder'
  const isDispatcher = normalizedRole === 'dispatcher'
  const isAdmin = normalizedRole === 'admin'
  const workspaceAudioRef = useRef<HTMLAudioElement | null>(null)
  const alarmAudioEnabled = personalPreferences?.notificationPreferences.alarmAudio ?? true

  useEffect(() => {
    const el = new Audio('/alert-sound.mp3')
    el.preload = 'auto'
    workspaceAudioRef.current = el
  }, [])
  const canCreateCamera = canManageCamera(profile, 'create')
  const canDeleteCamera = canManageCamera(profile, 'disable')
  const canEditCameraSettings = canManageCamera(profile, 'update')
  const showAdvancedCameraControls = canEditCameraSettings && managementMode
  const [cameras, setCameras] = useState<CctvCamera[]>([])
  const [activeCamera, setActiveCamera] = useState<CctvCamera | null>(null)
  const [form, setForm] = useState<CameraFormState>(() => emptyCameraForm(areaId))
  const [addCameraForm, setAddCameraForm] = useState<AddCameraFormState>(() => emptyAddCameraForm())
  const [isAddCameraOpen, setIsAddCameraOpen] = useState(false)
  const [addCameraError, setAddCameraError] = useState('')
  const [webcamSources, setWebcamSources] = useState<Array<{ reference: string; name: string }>>([])
  const [loadingCameras, setLoadingCameras] = useState(true)
  const [savingCamera, setSavingCamera] = useState(false)
  const [testingCamera, setTestingCamera] = useState(false)
  const [connectionMessage, setConnectionMessage] = useState('')
  const [testedCameraId, setTestedCameraId] = useState<string | null>(null)
  const [removingCameraId, setRemovingCameraId] = useState<string | null>(null)
  const [responderCameraIds, setResponderCameraIds] = useState<Set<string>>(() => new Set())
  const [hiddenCameraIds, setHiddenCameraIds] = useState<Set<string>>(() => readHiddenCameraIds())
  const [cameraError, setCameraError] = useState('')
  const [cameraStatuses, setCameraStatuses] = useState<Record<string, CameraMonitoringStatus>>({})
  const [cameraPreviewUrls, setCameraPreviewUrls] = useState<Record<string, string>>({})
  const [searchQuery, setSearchQuery] = useState('')
  const [areaFilter, setAreaFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [viewMode, setViewMode] = useState<'single' | 'grid'>('grid')
  const previewUrlsRef = useRef<Record<string, string>>({})
  const workspaceRef = useRef<HTMLElement | null>(null)

  const activeAreaId = form.areaId.trim() || activeCamera?.areaId || areaId
  const activeCameraStatus = activeCamera ? cameraStatuses[activeCamera.cameraId] : undefined
  const activeCameraName =
    form.cameraName.trim()
      ? sanitizeCameraDisplayName(form.cameraName)
      : activeCamera
        ? safeCameraName(activeCamera)
        : 'Manual CCTV Camera'
  const activeCameraSource = activeCameraName
  const activeCameraLocation = activeCamera
    ? cameraLocationLabel(activeCamera, activeAreaId)
    : form.location.trim() || activeAreaId
  const shouldAutoStartCctv = Boolean(
    activeCamera?.isActive &&
      activeCamera.detectionEnabled &&
      (activeCamera.cameraId || form.cameraIp.trim() || form.streamUrl.trim())
  )
  const autoStartCctvKey = activeCamera
    ? [
        activeCamera.cameraId,
        activeCamera.updatedAt ?? '',
        activeCamera.cameraIp ?? '',
        activeCamera.streamUrl ?? '',
      ].join('|')
    : null

  const savedCameraCount = useMemo(
    () => cameras.filter((camera) => !isDemoCamera(camera) && !hiddenCameraIds.has(camera.cameraId)).length,
    [cameras, hiddenCameraIds]
  )
  const savedCameras = useMemo(() => {
    const unique = new Map<string, CctvCamera>()
    for (const camera of cameras) {
      if (isDemoCamera(camera)) continue
      if (hiddenCameraIds.has(camera.cameraId)) continue
      const uniqueKey = camera.cameraIp?.trim() || camera.streamUrl?.trim() || camera.cameraId
      if (!unique.has(uniqueKey)) {
        unique.set(uniqueKey, camera)
      }
    }
    return [...unique.values()]
  }, [cameras, hiddenCameraIds])
  const areaOptions = useMemo(
    () => [...new Set(savedCameras.map((camera) => camera.areaId).filter((value): value is string => Boolean(value)))].sort(),
    [savedCameras]
  )
  const filteredCameras = useMemo(() => {
    const query = searchQuery.trim().toLowerCase()
    return savedCameras.filter((camera) => {
      const badges = cameraStatusBadges(cameraStatuses[camera.cameraId], camera)
      const matchesQuery = !query || `${safeCameraName(camera)} ${safeCameraLocation(camera)}`.toLowerCase().includes(query)
      const matchesArea = areaFilter === 'all' || camera.areaId === areaFilter
      const matchesStatus = statusFilter === 'all' || badges.includes(statusFilter)
      return matchesQuery && matchesArea && matchesStatus
    })
  }, [areaFilter, cameraStatuses, savedCameras, searchQuery, statusFilter])
  const cameraSlots = useMemo(() => buildCameraSlots(filteredCameras), [filteredCameras])
  const displayedCameraSlots = useMemo(
    () => viewMode === 'grid' && !managementMode
      ? cameraSlots.filter((slot) => slot.camera != null)
      : cameraSlots,
    [cameraSlots, managementMode, viewMode]
  )
  const activeStatusBadges = useMemo(
    () => cameraStatusBadges(activeCameraStatus, activeCamera),
    [activeCamera, activeCameraStatus]
  )
  const canRemoveCamera = useCallback(
    (camera: CctvCamera) => canDeleteCamera && !isProtectedCamera(camera),
    [canDeleteCamera]
  )

  const applyCamera = useCallback((camera: CctvCamera | null) => {
    setActiveCamera(camera)
    setForm(camera ? cameraToForm(camera, areaId) : emptyCameraForm(areaId))
  }, [areaId])

  const loadSavedCameras = useCallback(async () => {
    setLoadingCameras(true)
    setCameraError('')

    try {
      const items = await getCctvCameras()
      setCameras(items)
      const visibleItems = items.filter((camera) => !hiddenCameraIds.has(camera.cameraId))
      const targetCamera = initialCameraId ? visibleItems.find((c) => c.cameraId === initialCameraId) : null
      const defaultCamera = targetCamera || pickDefaultCamera(visibleItems, areaId)

      if (defaultCamera) {
        applyCamera(defaultCamera)
        window.localStorage.setItem(CAMERA_CACHE_KEY, JSON.stringify(defaultCamera))
      } else {
        applyCamera(null)
      }
    } catch (error) {
      const cached = window.localStorage.getItem(CAMERA_CACHE_KEY)
      if (cached) {
        try {
          const cachedCamera = JSON.parse(cached) as CctvCamera
          if (cachedCamera.cameraId && !hiddenCameraIds.has(cachedCamera.cameraId)) {
            applyCamera(cachedCamera)
          } else {
            window.localStorage.removeItem(CAMERA_CACHE_KEY)
            applyCamera(null)
          }
        } catch {
        }
      }
      setCameraError(error instanceof Error ? error.message : 'Could not load saved cameras.')
    } finally {
      setLoadingCameras(false)
    }
  }, [applyCamera, areaId, hiddenCameraIds])

  useEffect(() => {
    setForm((current) => ({
      ...current,
      areaId: current.areaId || areaId,
    }))
  }, [areaId])

  useEffect(() => {
    if (authLoading || !profile) return
    void loadSavedCameras()
  }, [authLoading, loadSavedCameras, profile])

  useEffect(() => {
    setResponderCameraIds(readResponderCameraIds())
    setHiddenCameraIds(readHiddenCameraIds())
  }, [])

  const setPreviewUrl = useCallback((cameraId: string, objectUrl: string) => {
    setCameraPreviewUrls((previous) => {
      const previousUrl = previous[cameraId]
      if (previousUrl && previousUrl !== objectUrl) {
        URL.revokeObjectURL(previousUrl)
      }
      const next = { ...previous, [cameraId]: objectUrl }
      previewUrlsRef.current = next
      return next
    })
  }, [])

  const clearPreviewUrl = useCallback((cameraId: string) => {
    setCameraPreviewUrls((previous) => {
      const previousUrl = previous[cameraId]
      if (previousUrl) {
        URL.revokeObjectURL(previousUrl)
      }
      const next = { ...previous }
      delete next[cameraId]
      previewUrlsRef.current = next
      return next
    })
  }, [])

  const loadCameraStatuses = useCallback(async () => {
    if (savedCameras.length === 0) {
      setCameraStatuses({})
      Object.keys(previewUrlsRef.current).forEach(clearPreviewUrl)
      return
    }

    // TODO: Replace this per-camera polling with GET /api/cameras/status/all when available.
    const pairs = await Promise.all(
      savedCameras.map(async (camera) => {
        try {
          return [camera.cameraId, await getCameraMonitoringStatus(camera.cameraId)] as const
        } catch {
          return [
            camera.cameraId,
            {
              cameraId: camera.cameraId,
              status: 'disconnected',
              message: 'Camera status unavailable.',
              monitoringLive: false,
              detectionRunning: false,
              latestFrameAvailable: false,
              previewAvailable: false,
            } satisfies CameraMonitoringStatus,
          ] as const
        }
      })
    )

    const nextStatuses = Object.fromEntries(pairs)
    setCameraStatuses(nextStatuses)

    pairs.forEach(([cameraId, status]) => {
      if (cameraId !== activeCamera?.cameraId && status.latestResult &&
          liveAlarmTracker.consume(status.latestResult) && alarmAudioEnabled && normalizedRole !== 'dispatcher') {
        void playAccidentAlert(workspaceAudioRef.current, 1, { beepRepeats: 3 }).catch(() => {
          setCameraError('Browser alarm audio was blocked. Arm sound in Live Monitor or dispatcher alerts.')
        })
      }
    })

    await Promise.all(
      pairs.map(async ([cameraId, status]) => {
        if (!status.latestFrameAvailable && !status.latestFrameReceived && !status.previewAvailable) {
          clearPreviewUrl(cameraId)
          return
        }

        try {
          const objectUrl = await fetchCameraPreviewFrameObjectUrl(cameraId, cameraStatusFrameUrl(status))
          setPreviewUrl(cameraId, objectUrl)
        } catch {
          clearPreviewUrl(cameraId)
        }
      })
    )
  }, [clearPreviewUrl, savedCameras, setPreviewUrl])

  useEffect(() => {
    if (loadingCameras || authLoading || !profile) return
    void loadCameraStatuses()
  }, [authLoading, loadCameraStatuses, loadingCameras, profile])

  useEffect(() => {
    if (savedCameras.length === 0 || authLoading || !profile) return
    const interval = window.setInterval(() => {
      void loadCameraStatuses()
    }, 4000)
    return () => window.clearInterval(interval)
  }, [authLoading, loadCameraStatuses, profile, savedCameras.length])

  useEffect(() => {
    if (viewMode !== 'grid' || managementMode || authLoading || !profile) return
    const active = savedCameras.filter((camera) => camera.isActive && camera.detectionEnabled)
    if (active.length === 0) return
    let cancelled = false
    void Promise.allSettled(active.map((camera) => startCctvMonitoring(camera.cameraId))).then((results) => {
      if (cancelled) return
      setCameraStatuses((previous) => {
        const next = { ...previous }
        results.forEach((result, index) => {
          if (result.status === 'fulfilled') next[active[index].cameraId] = result.value
        })
        return next
      })
    })
    return () => { cancelled = true }
  }, [authLoading, managementMode, profile, savedCameras, viewMode])

  useEffect(() => {
    return () => {
      Object.values(previewUrlsRef.current).forEach((objectUrl) => {
        URL.revokeObjectURL(objectUrl)
      })
      previewUrlsRef.current = {}
    }
  }, [])

  const saveCamera = async () => {
    const cameraName = form.cameraName.trim()
    const cameraIp = form.cameraIp.trim()
    const streamUrl = form.streamUrl.trim()
    const formAreaId = activeAreaId.trim()

    if (!cameraName) {
      setCameraError('Camera name is required.')
      return
    }

    if (!cameraIp && !streamUrl) {
      setCameraError('Enter a camera IP address or secure source before saving in Advanced Mode.')
      return
    }

    setSavingCamera(true)
    setCameraError('')

    try {
      const saved = await saveCctvCamera({
        cameraId: form.cameraId || activeCamera?.cameraId || undefined,
        label: cameraName,
        cameraIp: cameraIp || undefined,
        streamUrl: streamUrl || undefined,
        areaId: formAreaId,
        location: form.location.trim() || cameraName,
        locationDescription: form.location.trim() || undefined,
        cameraType: cameraIp ? 'Tapo RTSP' : 'Stream',
        status: 'offline',
        isActive: true,
        detectionEnabled: true,
      })

      setActiveCamera(saved)
      setForm(cameraToForm(saved, formAreaId))
      setCameras((previous) => {
        const withoutSaved = previous.filter((camera) => camera.cameraId !== saved.cameraId)
        return [saved, ...withoutSaved]
      })
      window.localStorage.setItem(CAMERA_CACHE_KEY, JSON.stringify(saved))
    } catch (error) {
      setCameraError(error instanceof Error ? error.message : 'Could not save camera.')
    } finally {
      setSavingCamera(false)
    }
  }

  const openAddCameraDialog = () => {
    setAddCameraForm(emptyAddCameraForm())
    setAddCameraError('')
    setConnectionMessage('')
    setTestedCameraId(null)
    setIsAddCameraOpen(true)
    void getLocalWebcamSources().then(setWebcamSources).catch(() => setWebcamSources([]))
  }

  const saveWebcamCamera = async () => {
    const source = webcamSources.find((item) => item.reference === addCameraForm.webcamReference)
    const name = addCameraForm.cameraName.trim()
    if (!source || !name) {
      setAddCameraError('Choose a configured USB webcam and enter a camera name.')
      return
    }
    if (isSensitiveCameraText(name)) {
      setAddCameraError('Camera name cannot contain a network address or credentials.')
      return
    }
    setSavingCamera(true)
    setAddCameraError('')
    try {
      const saved = await saveCctvCamera({
        label: name,
        streamUrl: source.reference,
        areaId: areaId || 'default',
        location: name,
        cameraType: 'Local Webcam',
        status: 'offline',
        isActive: true,
        detectionEnabled: true,
      })
      setCameras((previous) => [saved, ...previous.filter((camera) => camera.cameraId !== saved.cameraId)])
      setActiveCamera(saved)
      setForm(cameraToForm(saved, areaId || 'default'))
      window.localStorage.setItem(CAMERA_CACHE_KEY, JSON.stringify(saved))
      setIsAddCameraOpen(false)
    } catch (error) {
      setAddCameraError(error instanceof Error ? error.message : 'Could not save webcam.')
    } finally {
      setSavingCamera(false)
    }
  }

  const testNewCameraConnection = async () => {
    const streamUrl = normalizeRtspUrl(addCameraForm.streamUrl)
    if (!streamUrl) {
      setAddCameraError('Enter an RTSP stream link before testing connectivity.')
      return
    }
    if (!isRtspStreamUrl(streamUrl)) {
      setAddCameraError('Enter a valid RTSP stream link, for example rtsp://username:password@camera-ip:554/stream.')
      return
    }
    setTestingCamera(true)
    setAddCameraError('')
    setConnectionMessage('')
    try {
      const result = await testCameraConnection(streamUrl, {
        label: addCameraForm.location.trim() || `Camera ${cameras.length + 1}`,
        areaId: areaId || 'default',
        location: addCameraForm.location.trim() || areaId || 'Default Area',
      })
      setTestedCameraId(result.cameraId ?? null)
      if (result.connected) {
        setConnectionMessage(result.message || 'Camera connection verified.')
      } else {
        setConnectionMessage('Camera connection check finished. You can save and monitor this stream.')
      }
    } catch {
      setConnectionMessage('Camera check finished. You can proceed to save this camera.')
    } finally {
      setTestingCamera(false)
    }
  }

  const toggleCameraActive = async (camera: CctvCamera) => {
    setCameraError('')
    try {
      const updated = camera.isActive
        ? await disableCctvCamera(camera.cameraId)
        : await enableCctvCamera(camera.cameraId)
      setCameras((previous) => previous.map((item) => item.cameraId === updated.cameraId ? updated : item))
      if (activeCamera?.cameraId === updated.cameraId) applyCamera(updated)
    } catch (error) {
      setCameraError(error instanceof Error ? error.message : 'Could not change camera status.')
    }
  }

  const saveAdminCamera = async () => {
    const streamUrl = normalizeRtspUrl(addCameraForm.streamUrl)
    const rawLocation = addCameraForm.location.trim()

    if (!streamUrl) {
      setAddCameraError('RTSP stream link is required.')
      return
    }

    if (!isRtspStreamUrl(streamUrl)) {
      setAddCameraError('Enter a valid RTSP stream link, for example rtsp://username:password@camera-ip:554/stream.')
      return
    }

    if (rawLocation && isSensitiveCameraText(rawLocation)) {
      setAddCameraError('Camera location must describe the physical placement, not an RTSP link, IP address, or credentials.')
      return
    }

    const cameraNumber = cameras.length + 1
    const location = rawLocation || `Camera ${cameraNumber}`
    const label = rawLocation ? `${rawLocation} CCTV` : `Camera ${cameraNumber}`

    setSavingCamera(true)
    setAddCameraError('')
    setCameraError('')

    try {
      const saved = await saveCctvCamera({
        cameraId: testedCameraId ?? undefined,
        label,
        streamUrl,
        areaId: areaId || 'default',
        barangay: areaId || 'default',
        location,
        locationDescription: location,
        cameraType: 'RTSP Stream',
        status: 'offline',
        isActive: true,
        detectionEnabled: true,
      })

      setActiveCamera(saved)
      setForm(cameraToForm(saved, areaId || 'default'))
      setCameras((previous) => {
        const withoutSaved = previous.filter((camera) => camera.cameraId !== saved.cameraId)
        return [saved, ...withoutSaved]
      })
      window.localStorage.setItem(CAMERA_CACHE_KEY, JSON.stringify(saved))
      setAddCameraForm(emptyAddCameraForm())
      setIsAddCameraOpen(false)
    } catch (error) {
      setAddCameraError(error instanceof Error ? error.message : 'Could not save camera.')
    } finally {
      setSavingCamera(false)
    }
  }

  const removeCamera = async (camera: CctvCamera) => {
    if (!canRemoveCamera(camera)) return
    setRemovingCameraId(camera.cameraId)
    setCameraError('')
    try {
      await deleteCctvCamera(camera.cameraId)
      const nextCameras = cameras.filter((item) => item.cameraId !== camera.cameraId)
      setCameras(nextCameras)
      clearPreviewUrl(camera.cameraId)
      if (activeCamera?.cameraId === camera.cameraId) {
        const replacement = pickDefaultCamera(nextCameras, areaId)
        applyCamera(replacement)
        if (replacement) {
          window.localStorage.setItem(CAMERA_CACHE_KEY, JSON.stringify(replacement))
        } else {
          window.localStorage.removeItem(CAMERA_CACHE_KEY)
        }
      }
    } catch (error) {
      setCameraError(error instanceof Error ? error.message : 'Could not delete camera.')
    } finally {
      setRemovingCameraId(null)
    }
  }

  if (authLoading || !profile) {
    return (
      <section className="flex min-h-[calc(100vh-4rem)] items-center justify-center p-6">
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          <RefreshCw className="h-4 w-4 animate-spin text-primary" />
          <span>Authenticating camera session...</span>
        </div>
      </section>
    )
  }

  return (
    <>
        <section ref={workspaceRef} className="space-y-4 bg-background">
          {cameraError ? (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                {canEditCameraSettings
                  ? cameraError
                  : 'Unable to connect to this CCTV. Please ask the admin to check the camera settings.'}
              </AlertDescription>
            </Alert>
          ) : null}

          <Card className="p-3">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
              <div className="relative min-w-0 flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input aria-label="Search cameras" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="Search camera or location" className="pl-9" />
              </div>
              <div className="grid gap-2 sm:grid-cols-2 lg:flex">
                <Select value={areaFilter} onValueChange={setAreaFilter}>
                  <SelectTrigger className="min-w-40" aria-label="Filter cameras by area"><SelectValue placeholder="All areas" /></SelectTrigger>
                  <SelectContent><SelectItem value="all">All areas</SelectItem>{areaOptions.map((area) => <SelectItem key={area} value={area}>{area}</SelectItem>)}</SelectContent>
                </Select>
                <Select value={statusFilter} onValueChange={setStatusFilter}>
                  <SelectTrigger className="min-w-40" aria-label="Filter cameras by status"><ListFilter className="h-4 w-4" /><SelectValue placeholder="All statuses" /></SelectTrigger>
                  <SelectContent><SelectItem value="all">All statuses</SelectItem><SelectItem value="LIVE">Live</SelectItem><SelectItem value="SCANNING">Scanning</SelectItem><SelectItem value="OFFLINE">Offline</SelectItem><SelectItem value="RECONNECTING">Reconnecting</SelectItem><SelectItem value="STALE">Stale frame</SelectItem></SelectContent>
                </Select>
              </div>
              {!managementMode ? <div className="flex gap-2">
                <Button type="button" variant={viewMode === 'single' ? 'default' : 'outline'} size="sm" onClick={() => setViewMode('single')}><Video className="h-4 w-4" />Focused</Button>
                <Button type="button" variant={viewMode === 'grid' ? 'default' : 'outline'} size="sm" onClick={() => setViewMode('grid')}><Grid2X2 className="h-4 w-4" />Show all cameras</Button>
                <Button type="button" variant="outline" size="icon-sm" aria-label="Open camera workspace fullscreen" onClick={() => void workspaceRef.current?.requestFullscreen?.()}><Maximize2 className="h-4 w-4" /></Button>
              </div> : null}
            </div>
          </Card>

          <div className={managementMode || viewMode === 'grid' ? 'grid gap-4' : 'grid gap-4 xl:grid-cols-[minmax(0,1fr)_21rem]'}>
            {!managementMode && viewMode === 'single' ? <section className="min-w-0 space-y-3">
              <div className="flex flex-col gap-2 px-1 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                    <Video className="h-4 w-4 shrink-0" />
                    <span className="break-words text-foreground [overflow-wrap:anywhere]">
                      {activeCamera ? safeCameraName(activeCamera) : 'No CCTV available'}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {activeCamera
                      ? cameraLocationLabel(activeCamera, activeAreaId)
                      : 'Please connect or assign a CCTV camera.'}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {activeCamera ? (
                    activeStatusBadges.map((badge) => (
                      <Badge key={badge} variant={statusBadgeVariant(badge)}>
                        {badge}
                      </Badge>
                    ))
                  ) : (
                    <Badge variant="outline">OFFLINE</Badge>
                  )}
                </div>
              </div>

              {activeCamera ? (
                <LiveCamera
                  key={activeCamera.cameraId}
                  accidentOnlyMode
                  areaId={activeAreaId}
                  cameraId={activeCamera.cameraId}
                  cameraLocation={activeCameraLocation}
                  cameraName={activeCameraName}
                  sourceCamera={activeCameraSource}
                  initialCctvIp={form.cameraIp}
                  initialStreamUrl={form.streamUrl}
                  initialSourceTab="cctv"
                  autoStartCctv={shouldAutoStartCctv}
                  autoStartCctvKey={autoStartCctvKey}
                  controlRoomMode
                  detectionIntervalMs={1000}
                  managedCctvMode
                />
              ) : (
                <div className="flex min-h-[420px] items-center justify-center rounded-lg border border-border bg-zinc-950 p-6 text-center text-zinc-300">
                  <div>
                    <p className="text-lg font-semibold text-white">No CCTV available</p>
                    <p className="mt-2 text-sm">Please connect or assign a CCTV camera.</p>
                  </div>
                </div>
              )}
            </section> : null}

            <aside className="min-w-0 rounded-lg border border-border bg-card">
              <div className="flex items-start justify-between gap-3 border-b border-border p-3">
                <div className="min-w-0">
                  <h2 className="font-semibold">Camera feeds</h2>
                  <p className="text-sm text-muted-foreground">
                    Select a feed to open it.
                  </p>
                </div>
                <div className="flex shrink-0 gap-2">
                  {canCreateCamera ? (
                    <Button type="button" size="sm" onClick={openAddCameraDialog}>
                      <Plus className="h-4 w-4" />
                      Add Camera
                    </Button>
                  ) : null}
                  <Button
                    type="button"
                    size="icon"
                    variant="outline"
                    onClick={() => void loadSavedCameras()}
                    disabled={loadingCameras}
                    aria-label="Refresh camera feeds"
                  >
                    <RefreshCw className={`h-4 w-4 ${loadingCameras ? 'animate-spin' : ''}`} />
                  </Button>
                </div>
              </div>
              <div className={managementMode || viewMode === 'grid' ? 'grid gap-3 p-3 sm:grid-cols-2 xl:grid-cols-3' : 'grid gap-3 p-3 sm:grid-cols-2 xl:max-h-[calc(100vh-220px)] xl:grid-cols-1 xl:overflow-y-auto'}>
                {displayedCameraSlots.map(({ camera, slotNumber }) => {
                  if (!camera) {
                    const emptyTitle = savedCameras.length === 0
                      ? 'Waiting for assigned camera'
                      : 'No other CCTV available'
                    return (
                      <div
                        key={`empty-thumbnail-${slotNumber}`}
                        className="overflow-hidden rounded-lg border border-dashed border-border bg-background"
                      >
                        <div className="flex aspect-video items-center justify-center bg-zinc-950 text-xs font-medium uppercase tracking-wide text-zinc-500">
                          {savedCameras.length === 0 ? 'No feed' : 'Standby'}
                        </div>
                        <div className="p-3">
                          <p className="font-medium">{emptyTitle}</p>
                          <p className="text-sm text-muted-foreground">
                            {savedCameras.length === 0
                              ? 'Please connect or assign a CCTV camera.'
                              : 'Waiting for assigned camera'}
                          </p>
                        </div>
                      </div>
                    )
                  }

                  const status = cameraStatuses[camera.cameraId]
                  const badges = cameraStatusBadges(status, camera)
                  const selected = activeCamera?.cameraId === camera.cameraId
                  const previewUrl = cameraPreviewUrls[camera.cameraId]
                  const alertId = latestAlertId(status)
                  const removable = canRemoveCamera(camera)

                  return (
                    <div
                      key={camera.cameraId}
                      role="button"
                      tabIndex={0}
                      className={`overflow-hidden rounded-lg border text-left transition-colors ${
                        selected
                          ? 'border-primary bg-primary/10'
                          : 'border-border bg-background hover:border-primary/50'
                      }`}
                      onClick={() => applyCamera(camera)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault()
                          applyCamera(camera)
                        }
                      }}
                      aria-label={`Select ${safeCameraName(camera)}`}
                    >
                      <div className="relative aspect-video overflow-hidden bg-zinc-950">
                        <CameraDetectionSurface cameraId={camera.cameraId}>
                        {previewUrl ? (
                          <img
                            src={previewUrl}
                            alt={`${safeCameraName(camera)} live preview`}
                            className="h-full w-full object-cover"
                          />
                        ) : (
                          <div className="flex h-full w-full items-center justify-center px-4 text-center text-xs text-zinc-500">
                            Camera preview unavailable
                          </div>
                        )}
                        </CameraDetectionSurface>
                        <div className="absolute left-2 top-2 max-w-[70%] rounded bg-black/70 px-2 py-1 text-xs font-medium text-white">
                          <span className="block truncate">{safeCameraName(camera)}</span>
                        </div>
                        <div className="absolute right-2 top-2 flex max-w-[45%] flex-wrap justify-end gap-1">
                          {badges.map((badge) => (
                            <Badge key={badge} variant={statusBadgeVariant(badge)}>
                              {badge}
                            </Badge>
                          ))}
                        </div>
                        {status?.latestResult?.finalDecision === 'confirmed_crash' ? (
                          <div role="alert" className="absolute inset-x-0 bottom-8 bg-red-950/95 px-3 py-2 text-center font-semibold text-white">
                            Collision Detected
                          </div>
                        ) : null}
                        {alertId ? <Link
                          href={isAdmin ? `/admin/incidents?incident=${encodeURIComponent(alertId)}` : `/dispatcher/review?incident=${encodeURIComponent(alertId)}`}
                          className="absolute bottom-2 left-2"
                          onClick={(event) => event.stopPropagation()}
                          aria-label={`Open incident ${alertId}`}
                        ><Badge variant="destructive">ALERT</Badge></Link> : null}
                        {viewMode === 'grid' && !managementMode ? (
                          <Button
                            type="button"
                            size="icon-sm"
                            variant="outline"
                            className="absolute bottom-2 right-2 bg-background/95"
                            aria-label={`Expand ${safeCameraName(camera)}`}
                            onClick={(event) => {
                              event.stopPropagation()
                              applyCamera(camera)
                              setViewMode('single')
                            }}
                          >
                            <Maximize2 className="h-4 w-4" />
                          </Button>
                        ) : null}
                        {removable ? (
                          <div className="absolute bottom-2 right-2">
                            <AlertDialog>
                              <AlertDialogTrigger asChild>
                                <Button
                                  type="button"
                                  size="icon-sm"
                                  variant="outline"
                                  className="border-destructive/40 bg-background/95 text-destructive hover:border-destructive/60 hover:bg-destructive/10 hover:text-destructive"
                                  disabled={removingCameraId === camera.cameraId}
                                  aria-label={`Delete ${safeCameraName(camera)}`}
                                  onClick={(event) => event.stopPropagation()}
                                  onKeyDown={(event) => event.stopPropagation()}
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </AlertDialogTrigger>
                              <AlertDialogContent className="sm:max-w-md">
                                <AlertDialogHeader>
                                  <AlertDialogTitle>Delete camera?</AlertDialogTitle>
                                  <AlertDialogDescription>
                                    {`Delete "${safeCameraName(camera)}" and stop monitoring this camera?`}
                                  </AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                  <AlertDialogCancel disabled={removingCameraId === camera.cameraId}>
                                    Cancel
                                  </AlertDialogCancel>
                                  <AlertDialogAction
                                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                    disabled={removingCameraId === camera.cameraId}
                                    onClick={(event) => {
                                      event.stopPropagation()
                                      void removeCamera(camera)
                                    }}
                                  >
                                    {removingCameraId === camera.cameraId
                                      ? 'Deleting...'
                                      : 'Delete Camera'}
                                  </AlertDialogAction>
                                </AlertDialogFooter>
                              </AlertDialogContent>
                            </AlertDialog>
                          </div>
                        ) : null}
                      </div>
                      <div className="space-y-2 p-3">
                        <div className="min-w-0">
                          <p className="break-words font-medium [overflow-wrap:anywhere]">
                            {safeCameraName(camera)}
                          </p>
                          <p className="mt-1 flex min-w-0 items-center gap-1 text-sm text-muted-foreground">
                            <MapPin className="h-3.5 w-3.5 shrink-0" />
                            <span className="min-w-0 break-words [overflow-wrap:anywhere]">
                              {cameraLocationLabel(camera, areaId)}
                            </span>
                          </p>
                          <p className="mt-1 text-xs font-medium text-muted-foreground">Type: {cameraSourceType(camera)}</p>
                        </div>
                        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                          <span>Vehicles: {status?.vehicleBoxCount ?? 0}</span>
                          <span>Analysis: {formatMilliseconds(status?.inferenceCompletionAgeMs ?? status?.frameAgeMs)}</span>
                          <span>Collision: {collisionStatus(status)}</span>
                          {alertId ? <span>Case: {alertId}</span> : null}
                        </div>
                        {status ? <div className="grid grid-cols-2 gap-x-3 gap-y-1 rounded-md bg-muted/60 p-2 text-xs text-muted-foreground">
                          <span>Health: {status.cameraHealth ?? 'OFFLINE'}</span>
                          <span>Frame age: {formatMilliseconds(status.frameAgeMs)}</span>
                          <span>Latency: {formatMilliseconds(status.processingLatencyMs)}</span>
                          <span>Reconnects: {status.reconnectCount ?? 0}</span>
                          {isAdmin && typeof status.captureFps === 'number' ? (
                            <span>Capture: {status.captureFps} FPS</span>
                          ) : null}
                          {isAdmin && typeof status.previewFps === 'number' ? (
                            <span>Preview: {status.previewFps} FPS</span>
                          ) : null}
                          {isAdmin && typeof status.aiFps === 'number' ? (
                            <span>AI: {status.aiFps} FPS</span>
                          ) : null}
                          {isAdmin && status.sourceResolution ? (
                            <span>Res: {status.sourceResolution}</span>
                          ) : null}
                        </div> : null}
                        {managementMode && isAdmin ? <div className="flex gap-2 pt-1">
                          <Button type="button" size="sm" variant="outline" onClick={(event) => { event.stopPropagation(); applyCamera(camera) }}>Edit</Button>
                          <Button type="button" size="sm" variant={camera.isActive ? 'destructive' : 'secondary'} onClick={(event) => { event.stopPropagation(); void toggleCameraActive(camera) }}>{camera.isActive ? 'Disable' : 'Enable'}</Button>
                        </div> : null}
                        {managementMode && isAdmin && status?.latestResult ? <div className="rounded-md bg-muted p-2 text-xs text-muted-foreground">
                          <p>Temporal score: {formatConfidence(status.latestResult.temporalCrashScore)}</p>
                          <p>Aftermath score: {formatConfidence(status.latestResult.aftermathScore)}</p>
                          <p>Aftermath state: {status.latestResult.aftermathState ?? 'NONE'}</p>
                          {status.latestResult.rejectionReasons?.length ? <p>Gate: {status.latestResult.rejectionReasons.join(', ')}</p> : null}
                        </div> : null}
                      </div>
                    </div>
                  )
                })}
              </div>
            </aside>
          </div>

          {showAdvancedCameraControls ? (
            <Card className="space-y-4 border border-dashed border-border bg-background/60 p-4">
              <div>
                <h3 className="font-semibold">Advanced Camera Settings</h3>
                <p className="text-sm text-muted-foreground">
                  Admin-only stream configuration. Do not share screenshots with camera credentials.
                </p>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="saved-camera-name">Camera Name</Label>
                  <Input
                    id="saved-camera-name"
                    value={form.cameraName}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, cameraName: event.target.value }))
                    }
                    placeholder="Main Gate CCTV"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="saved-camera-area">Area</Label>
                  <Input
                    id="saved-camera-area"
                    value={form.areaId}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, areaId: event.target.value }))
                    }
                    placeholder={areaId}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="saved-camera-ip">Camera IP</Label>
                  <Input
                    id="saved-camera-ip"
                    value={form.cameraIp}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, cameraIp: event.target.value }))
                    }
                    placeholder="Camera IP address"
                    autoComplete="off"
                    spellCheck={false}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="saved-camera-stream">Secure Source</Label>
                  <Input
                    id="saved-camera-stream"
                    type="password"
                    value={form.streamUrl}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, streamUrl: event.target.value }))
                    }
                    placeholder="Optional secure source"
                    autoComplete="off"
                    spellCheck={false}
                  />
                </div>
                <div className="space-y-2 md:col-span-2">
                  <Label htmlFor="saved-camera-location">Location / Description</Label>
                  <Input
                    id="saved-camera-location"
                    value={form.location}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, location: event.target.value }))
                    }
                    placeholder="Talomo crossing northbound"
                  />
                </div>
              </div>

              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="rounded-md border border-border bg-background px-3 py-2 text-sm">
                  <div className="flex items-center gap-2 font-medium">
                    <Video className="h-4 w-4" />
                    Active camera: {activeCameraName}
                  </div>
                  <p className="mt-1 text-muted-foreground">
                    {activeCamera
                      ? `${safeCameraName(activeCamera)} - ${cameraLocationLabel(activeCamera, activeAreaId)}`
                      : savedCameraCount > 0
                        ? 'Edit or save these values to make them the default.'
                        : 'No saved camera yet. Manual CCTV input still works below.'}
                  </p>
                </div>
                <Button type="button" onClick={() => void saveCamera()} disabled={savingCamera}>
                  <Save className="mr-2 h-4 w-4" />
                  {savingCamera ? 'Saving...' : 'Save Camera'}
                </Button>
              </div>
            </Card>
          ) : null}
        </section>

        <Dialog open={isAddCameraOpen} onOpenChange={setIsAddCameraOpen}>
          <DialogContent className="border border-border bg-card sm:max-w-lg">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Video className="h-5 w-5 text-primary" />
                Add New Camera
              </DialogTitle>
              <DialogDescription>
                Choose a camera type and enter its setup details.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="new-camera-type">Camera type</Label>
                <Select value={addCameraForm.cameraType} onValueChange={(value: 'network' | 'webcam') => {
                  setAddCameraForm((current) => ({ ...current, cameraType: value }))
                  setAddCameraError('')
                }}>
                  <SelectTrigger id="new-camera-type"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="network">CCTV / Network Camera</SelectItem>
                    <SelectItem value="webcam">USB Webcam</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {addCameraError ? (
                <Alert variant="destructive">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>{addCameraError}</AlertDescription>
                </Alert>
              ) : null}
              {connectionMessage ? (
                <Alert className="border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300">
                  <AlertDescription>{connectionMessage}</AlertDescription>
                </Alert>
              ) : null}

              {addCameraForm.cameraType === 'network' ? <div className="space-y-2">
                <Label htmlFor="new-camera-stream" className="font-semibold text-sm">
                  RTSP Stream Link <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="new-camera-stream"
                  type="text"
                  value={addCameraForm.streamUrl}
                  onChange={(event) =>
                    setAddCameraForm((current) => ({
                      ...current,
                      streamUrl: event.target.value,
                    }))
                  }
                  placeholder="rtsp://username:password@camera-ip:554/stream"
                  autoComplete="off"
                  spellCheck={false}
                  className="font-mono text-xs"
                />
                <p className="text-xs text-muted-foreground">
                  Paste your camera RTSP stream URL here. This is the only link required.
                </p>
              </div> : (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="new-webcam-name">Camera name</Label>
                    <Input id="new-webcam-name" value={addCameraForm.cameraName} onChange={(event) =>
                      setAddCameraForm((current) => ({ ...current, cameraName: event.target.value }))} placeholder="FOBOS MODEL GW600" />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="new-webcam-device">Device</Label>
                    <Select value={addCameraForm.webcamReference} onValueChange={(value) =>
                      setAddCameraForm((current) => ({ ...current, webcamReference: value,
                        cameraName: current.cameraName || webcamSources.find((item) => item.reference === value)?.name || '' }))}>
                      <SelectTrigger id="new-webcam-device"><SelectValue placeholder="Select a configured webcam" /></SelectTrigger>
                      <SelectContent>{webcamSources.map((source) =>
                        <SelectItem key={source.reference} value={source.reference}>{source.name}</SelectItem>)}</SelectContent>
                    </Select>
                    {webcamSources.length === 0 ? <p className="text-xs text-muted-foreground">No USB webcams are configured on this server.</p> : null}
                  </div>
                </>
              )}

              {addCameraForm.cameraType === 'network' ? <div className="space-y-2">
                <Label htmlFor="new-camera-location" className="text-xs text-muted-foreground font-normal">
                  Camera Location or Name <span className="text-muted-foreground font-normal">(Optional)</span>
                </Label>
                <Input
                  id="new-camera-location"
                  value={addCameraForm.location}
                  onChange={(event) =>
                    setAddCameraForm((current) => ({
                      ...current,
                      location: event.target.value,
                    }))
                  }
                  placeholder="e.g. Bago CCTV, Gate 1, or leave empty"
                  className="text-xs"
                />
              </div> : null}

              <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end pt-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsAddCameraOpen(false)}
                  disabled={savingCamera}
                >
                  Cancel
                </Button>
                {addCameraForm.cameraType === 'network' ? <Button
                  type="button"
                  variant="secondary"
                  onClick={() => void testNewCameraConnection()}
                  disabled={savingCamera || testingCamera}
                >
                  <RefreshCw className={`h-4 w-4 ${testingCamera ? 'animate-spin' : ''}`} />
                  {testingCamera ? 'Testing...' : 'Test Connection'}
                </Button> : null}
                <Button
                  type="button"
                  onClick={() => void (addCameraForm.cameraType === 'network' ? saveAdminCamera() : saveWebcamCamera())}
                  disabled={savingCamera}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white gap-1.5"
                >
                  <Save className="h-4 w-4" />
                  {savingCamera ? 'Saving...' : 'Save Camera'}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
    </>
  )
}
