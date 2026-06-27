'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertTriangle,
  Camera,
  EyeOff,
  Link2,
  Loader,
  Play,
  ShieldQuestion,
  Square,
  X,
} from 'lucide-react'
import { CctvVideoOverlay } from '@/components/cctv-video-overlay'
import { DetectedMediaViewer } from '@/components/detected-media-viewer'
import {
  DetectionHistoryEntry,
  RecentDetectionHistory,
} from '@/components/recent-detection-history'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useAuth } from '@/components/auth-provider'
import { playAccidentAlert } from '@/lib/accident-alert'
import { APP_CONFIG } from '@/lib/app-config'
import {
  detectFromFile,
  detectFromStreamUrl,
  fetchCameraPreviewFrameObjectUrl,
  getCameraMonitoringStatus,
  resolveBackendMediaUrl,
  stopCctvMonitoring,
  testCameraConnection,
} from '@/lib/api-client'
import { useDisplayMode } from '@/lib/display-mode'
import { DetectionBox, DetectionResponse } from '@/lib/types'

interface LiveCameraProps {
  detectionIntervalMs?: number
  /** 0–1; MP3 and fallback beep both respect this. Default 1. */
  alertVolume?: number
  /**
   * When true (e.g. barangay responder camera), only accidents update the latest panel,
   * history, overlays, and onDetectionResult. Vehicle-only frames are still analyzed on the
   * server but are not shown as a “detection”. onFrameResult may receive result=null on
   * those frames so parents can still push livePreviewDataUrl only.
   */
  accidentOnlyMode?: boolean
  areaId?: string | null
  cameraId?: string | null
  cameraName?: string | null
  sourceCamera?: string | null
  initialCctvIp?: string | null
  initialStreamUrl?: string | null
  initialSourceTab?: 'device' | 'cctv'
  autoStartCctv?: boolean
  autoStartCctvKey?: string | null
  managedCctvMode?: boolean
  onDetectionResult?: (result: DetectionResponse) => void
  onFrameResult?: (result: DetectionResponse | null, rawFrameDataUrl: string | null) => void
  onError?: (error: string) => void
  onStreamStateChange?: (isStreaming: boolean) => void
}

const MEANINGFUL_CONFIDENCE_THRESHOLD =
  APP_CONFIG.detection.meaningfulConfidenceThreshold
const ALERT_DEBOUNCE_MS = APP_CONFIG.detection.alertDebounceMs
const CRASH_ALERT_VISIBLE_MS = 60_000
const DEVICE_DETECTION_INTERVAL_MS = 1800
const CCTV_DETECTION_INTERVAL_MS = 2500
const STABLE_CRASH_WINDOW_SIZE = 3
const STABLE_CRASH_REQUIRED_HITS = 2
const STABLE_CRASH_MIN_DURATION_MS = 2000
const STABLE_CLEAR_REQUIRED_MISSES = 3
const BOX_HOLD_MS = 4000
const CCTV_FIRST_FRAME_TIMEOUT_MS = 15_000
const DUPLICATE_HISTORY_WINDOW_MS =
  APP_CONFIG.detection.duplicateHistoryWindowMs
/** Labels shown/used by the live camera UI logic. */
const PROJECT_LABELS = new Set(['accident', 'vehicle'])

type CrashAlertKind = 'created' | 'blocked' | 'skipped'

interface CrashAlertState {
  id: string
  kind: CrashAlertKind
  result: DetectionResponse
  visibleUntil: number
}

interface LiveDetectionSample {
  accidentDetected: boolean
  boxes: DetectionBox[]
  caseId?: string | null
  confidence: number
  notificationId?: string | null
  persistenceStatus?: string | null
  result: DetectionResponse
  timestamp: number
}

function normalizeProjectLabel(raw: string): 'accident' | 'vehicle' | null {
  const label = raw.trim().toLowerCase()
  if (!label) return null

  // Crash/accident synonyms (covers common custom training variations).
  if (label === 'accident' || label === 'crash' || label === 'collision') return 'accident'

  // Vehicle synonyms (covers COCO-style labels and common variants).
  if (
    label === 'vehicle' ||
    label === 'car' ||
    label === 'truck' ||
    label === 'bus' ||
    label === 'motorcycle' ||
    label === 'motorbike' ||
    label === 'bicycle' ||
    label === 'bike'
  ) {
    return 'vehicle'
  }

  return null
}

function getUnexpectedLabels(detections: DetectionResponse['detections']): string[] {
  const unique = [...new Set(detections.map((d) => d.label.toLowerCase().trim()))].filter(
    Boolean
  )
  return unique.filter((label) => normalizeProjectLabel(label) === null)
}

function getCameraErrorMessage(error: unknown): string {
  if (!(error instanceof DOMException)) {
    return error instanceof Error ? error.message : 'Failed to access the camera.'
  }

  switch (error.name) {
    case 'NotAllowedError':
      return 'Camera permission was denied. Please allow camera access in your browser settings.'
    case 'NotFoundError':
      return 'No camera was found on this device.'
    case 'NotReadableError':
      return 'The camera is busy or unavailable because another app is using it.'
    case 'OverconstrainedError':
      return 'The requested camera settings are not supported on this device.'
    default:
      return error.message || 'Failed to access the camera.'
  }
}

function getDetectionSignature(result: DetectionResponse): string {
  const labels = result.detections
    .map((detection) => detection.label.toLowerCase())
    .sort()
    .join('|')

  return `${result.accident_detected ? 'accident' : 'normal'}:${labels}`
}

function getHighestDetectionConfidence(result: DetectionResponse): number {
  if (result.detections.length === 0) {
    return result.confidence
  }

  return Math.max(
    result.confidence,
    ...result.detections.map((detection) => detection.score)
  )
}

function hasMeaningfulDetection(result: DetectionResponse): boolean {
  if (result.accident_detected) {
    return true
  }

  const projectRaw = result.detections
    .map((d) => ({ ...d, label: normalizeProjectLabel(d.label) ?? d.label }))
    .filter((d) => PROJECT_LABELS.has(d.label.toLowerCase()))

  if (projectRaw.length === 0) {
    return false
  }

  return (
    getHighestDetectionConfidence({
      ...result,
      detections: projectRaw,
    }) >= MEANINGFUL_CONFIDENCE_THRESHOLD
  )
}

function buildDisplayResult(result: DetectionResponse): DetectionResponse {
  const projectDetections = result.detections
    .map((d) => {
      const normalized = normalizeProjectLabel(d.label)
      return normalized ? { ...d, label: normalized } : null
    })
    .filter((d): d is NonNullable<typeof d> => Boolean(d))

  const derivedAccidentDetected =
    result.accident_detected ||
    projectDetections.some((d) => d.label.toLowerCase() === 'accident')

  if (derivedAccidentDetected && projectDetections.length === 0) {
    return {
      ...result,
      accident_detected: true,
      detections: [
        {
          label: 'accident',
          score: Math.max(result.confidence, 0.01),
          box: [0, 0, 0, 0],
        },
      ],
    }
  }

  if (projectDetections.length === 0) {
    return {
      ...result,
      accident_detected: false,
      detections: [],
      confidence: result.confidence,
    }
  }

  return {
    ...result,
    accident_detected: derivedAccidentDetected,
    confidence: Math.max(
      result.confidence,
      ...projectDetections.map((d) => d.score)
    ),
    detections: projectDetections,
  }
}

function getDetectionOverlayBoxes(result: DetectionResponse): DetectionBox[] {
  const responseBoxes =
    result.boxes
      ?.map((box) => ({
        label: box.label || 'detection',
        confidence: Number(box.confidence) || 0,
        x: Number(box.x),
        y: Number(box.y),
        width: Number(box.width),
        height: Number(box.height),
      }))
      .filter(
        (box) =>
          Number.isFinite(box.x) &&
          Number.isFinite(box.y) &&
          Number.isFinite(box.width) &&
          Number.isFinite(box.height) &&
          box.width > 0 &&
          box.height > 0
      ) ?? []

  if (responseBoxes.length > 0) {
    return responseBoxes
  }

  return result.detections
    .map((detection) => {
      const [x1, y1, x2, y2] = detection.box ?? []
      const x = Number(x1)
      const y = Number(y1)
      const width = Number(x2) - x
      const height = Number(y2) - y

      return {
        label: detection.label || 'detection',
        confidence: Number(detection.score) || 0,
        x,
        y,
        width,
        height,
      }
    })
    .filter(
      (box) =>
        Number.isFinite(box.x) &&
        Number.isFinite(box.y) &&
        Number.isFinite(box.width) &&
        Number.isFinite(box.height) &&
        box.width > 0 &&
        box.height > 0
    )
}

function getPrimaryConfidenceDisplay(result: DetectionResponse): {
  value: number | null
  caption: string
} {
  if (result.accident_detected) {
    const fromBoxes = result.detections
      .filter((d) => d.label.toLowerCase() === 'accident')
      .map((d) => d.score)
    const v =
      fromBoxes.length > 0 ? Math.max(...fromBoxes) : Math.max(result.confidence, 0)
    return {
      value: v > 0 ? v : null,
      caption: 'Crash-class confidence',
    }
  }

  const vehicleScores = result.detections
    .filter((d) => d.label.toLowerCase() === 'vehicle')
    .map((d) => d.score)

  if (vehicleScores.length > 0) {
    return {
      value: Math.max(...vehicleScores),
      caption: 'Vehicle class (no crash flagged)',
    }
  }

  return {
    value: null,
    caption: 'No crash or vehicle class in this frame',
  }
}

function getPersistenceStatus(result: DetectionResponse): string | null {
  return result.persistenceStatus ?? result.casePersistenceStatus ?? null
}

function getCrashAlertKind(result: DetectionResponse): CrashAlertKind {
  const persistenceStatus = getPersistenceStatus(result)

  if (persistenceStatus === 'created' && result.caseId && result.notificationId) {
    return 'created'
  }

  if (persistenceStatus === 'blocked_existing_case') {
    return 'blocked'
  }

  return 'skipped'
}

function getCrashAlertReviewCaseId(alert: CrashAlertState): string | null {
  if (alert.kind === 'created') {
    return alert.result.caseId && alert.result.notificationId
      ? alert.result.caseId
      : null
  }

  if (alert.kind === 'blocked') {
    return alert.result.activeBlockingCaseId ?? null
  }

  return null
}

function getCrashAlertStatusText(alert: CrashAlertState): string {
  if (alert.kind === 'created') {
    return 'Notification created'
  }

  if (alert.kind === 'blocked') {
    return (
      alert.result.alertBlockedReason ??
      alert.result.persistenceSkippedReason ??
      'An active crash case already exists for this camera.'
    )
  }

  return (
    alert.result.persistenceSkippedReason ??
    alert.result.alertBlockedReason ??
    `Persistence status: ${getPersistenceStatus(alert.result) ?? 'not saved'}`
  )
}

function getCrashAlertTitle(alert: CrashAlertState): string {
  if (alert.kind === 'blocked') return 'Active Crash Case Exists'
  if (alert.kind === 'skipped') return 'Crash Detection Not Saved'
  return 'Crash Detected'
}

export function LiveCamera({
  detectionIntervalMs = 1000,
  alertVolume = 1,
  accidentOnlyMode = false,
  areaId,
  cameraId,
  cameraName,
  sourceCamera,
  initialCctvIp,
  initialStreamUrl,
  initialSourceTab = 'device',
  autoStartCctv = false,
  autoStartCctvKey,
  managedCctvMode = false,
  onDetectionResult,
  onFrameResult,
  onError,
  onStreamStateChange,
}: LiveCameraProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const detectionIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const cctvStatusIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const cctvFrameIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const requestInFlightRef = useRef(false)
  const detectionEnabledRef = useRef(false)
  const autoStartDetectionRef = useRef(false)
  const lastAlertTimestampRef = useRef(0)
  const lastAlertSignatureRef = useRef('')
  const lastHistorySignatureRef = useRef('')
  const lastHistoryTimestampRef = useRef(0)
  const sourceTabRef = useRef<'device' | 'cctv'>(initialSourceTab)
  const streamUrlRef = useRef(initialStreamUrl ?? '')
  const cctvIpRef = useRef(initialCctvIp ?? '')
  const cctvMonitorIdRef = useRef('')
  const cctvPreviewUrlRef = useRef<string | null>(null)
  const cctvAutoStartAttemptedKeyRef = useRef('')
  const cctvAutoStartSuppressedRef = useRef(false)
  const cctvStartedAtRef = useRef<number | null>(null)
  const cctvLastFrameAtRef = useRef<number | null>(null)
  const detectionSamplesRef = useRef<LiveDetectionSample[]>([])
  const crashRunStartedAtRef = useRef<number | null>(null)
  const boxHoldUntilRef = useRef(0)
  const dismissedCrashAlertIdsRef = useRef<Set<string>>(new Set())

  const [stream, setStream] = useState<MediaStream | null>(null)
  const [isStartingCamera, setIsStartingCamera] = useState(false)
  const [isDetecting, setIsDetecting] = useState(false)
  const [isProcessingFrame, setIsProcessingFrame] = useState(false)
  const [error, setError] = useState('')
  const [latestResult, setLatestResult] = useState<DetectionResponse | null>(null)
  const [history, setHistory] = useState<DetectionHistoryEntry[]>([])
  const [liveOverlayLabels, setLiveOverlayLabels] = useState<string[]>([])
  const [liveOverlayBoxes, setLiveOverlayBoxes] = useState<DetectionBox[]>([])
  const [overlayTimestamp, setOverlayTimestamp] = useState('')
  const [sourceTab, setSourceTab] = useState<'device' | 'cctv'>(initialSourceTab)
  const [streamUrl, setStreamUrl] = useState(initialStreamUrl ?? '')
  const [cctvIp, setCctvIp] = useState(initialCctvIp ?? '')
  const [cctvConnectionStatus, setCctvConnectionStatus] = useState('')
  const [cctvFrameError, setCctvFrameError] = useState('')
  const [cctvPreviewUrl, setCctvPreviewUrl] = useState<string | null>(null)
  const [isCctvLive, setIsCctvLive] = useState(false)
  const [overlaySourceSize, setOverlaySourceSize] = useState<{
    width: number
    height: number
  } | null>(null)
  const [modelHint, setModelHint] = useState('')
  const [crashAlert, setCrashAlert] = useState<CrashAlertState | null>(null)

  const audioRef = useRef<HTMLAudioElement | null>(null)
  const { profile } = useAuth()
  const { isAdvancedMode } = useDisplayMode(profile)

  useEffect(() => {
    const el = new Audio('/alert-sound.mp3')
    el.preload = 'auto'
    el.volume = Math.min(1, Math.max(0, alertVolume))
    audioRef.current = el
  }, [alertVolume])

  useEffect(() => {
    sourceTabRef.current = sourceTab
  }, [sourceTab])

  useEffect(() => {
    streamUrlRef.current = streamUrl
  }, [streamUrl])

  useEffect(() => {
    cctvIpRef.current = cctvIp
  }, [cctvIp])

  useEffect(() => {
    if (detectionEnabledRef.current || isCctvLive) {
      return
    }

    cctvIpRef.current = initialCctvIp ?? ''
    streamUrlRef.current = initialStreamUrl ?? ''
    sourceTabRef.current = initialSourceTab
    setCctvIp(initialCctvIp ?? '')
    setStreamUrl(initialStreamUrl ?? '')
    setSourceTab(initialSourceTab)
  }, [initialCctvIp, initialStreamUrl, initialSourceTab, isCctvLive])

  useEffect(() => {
    const updateTimestamp = () => {
      setOverlayTimestamp(
        new Date().toLocaleString([], {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
        })
      )
    }

    updateTimestamp()

    const interval = setInterval(updateTimestamp, 1000)

    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (!stream || !videoRef.current) {
      return
    }

    const videoElement = videoRef.current
    videoElement.srcObject = stream

    const playStream = async () => {
      try {
        await videoElement.play()
      } catch (playError) {
        const message =
          playError instanceof Error
            ? playError.message
            : 'The live camera preview could not start.'

        setError(message)
        onError?.(message)
      }
    }

    void playStream()
  }, [onError, stream])

  useEffect(() => {
    const sessionLive = Boolean(stream) || isCctvLive
    onStreamStateChange?.(sessionLive)
  }, [onStreamStateChange, stream, isCctvLive])

  useEffect(() => {
    return () => {
      onStreamStateChange?.(false)
    }
  }, [onStreamStateChange])

  useEffect(() => {
    if (!stream || !autoStartDetectionRef.current) {
      return
    }

    autoStartDetectionRef.current = false
    void startDetection(true)
  }, [stream])

  useEffect(() => {
    if (!crashAlert) {
      return
    }

    const timeout = setTimeout(() => {
      setCrashAlert((current) => (current?.id === crashAlert.id ? null : current))
    }, Math.max(0, crashAlert.visibleUntil - Date.now()))

    return () => clearTimeout(timeout)
  }, [crashAlert])

  useEffect(() => {
    return () => {
      detectionEnabledRef.current = false

      if (detectionIntervalRef.current) {
        clearInterval(detectionIntervalRef.current)
      }
      if (cctvStatusIntervalRef.current) {
        clearInterval(cctvStatusIntervalRef.current)
      }
      if (cctvFrameIntervalRef.current) {
        clearInterval(cctvFrameIntervalRef.current)
      }
      if (cctvPreviewUrlRef.current) {
        URL.revokeObjectURL(cctvPreviewUrlRef.current)
      }
      cctvStartedAtRef.current = null
      cctvLastFrameAtRef.current = null

      if (stream) {
        stream.getTracks().forEach((track) => track.stop())
      }
    }
  }, [stream])

  /** Annotated backend frame (may show person/car/etc.) — only when an accident is flagged. */
  const resolvedAnnotatedMediaUrl = useMemo(
    () =>
      latestResult?.accident_detected
        ? resolveBackendMediaUrl(latestResult.annotated_media_url)
        : null,
    [latestResult?.accident_detected, latestResult?.annotated_media_url]
  )

  const showCrashAlert = (result: DetectionResponse) => {
    if (!result.accident_detected) {
      return
    }

    const kind = getCrashAlertKind(result)
    const reviewCaseId =
      kind === 'blocked'
        ? result.activeBlockingCaseId ?? result.caseId
        : result.caseId
    const id = [
      kind,
      reviewCaseId,
      result.notificationId,
      result.persistenceStatus,
      result.alertBlockedReason,
      result.persistenceSkippedReason,
    ].join('|')

    if (dismissedCrashAlertIdsRef.current.has(id)) {
      return
    }

    setCrashAlert((current) => {
      const visibleUntil = Date.now() + CRASH_ALERT_VISIBLE_MS

      if (current?.id === id) {
        return {
          ...current,
          kind,
          result,
          visibleUntil: Math.max(current.visibleUntil, visibleUntil),
        }
      }

      return {
        id,
        kind,
        result,
        visibleUntil,
      }
    })
  }

  const getEffectiveDetectionIntervalMs = () =>
    sourceTabRef.current === 'cctv'
      ? Math.max(detectionIntervalMs, CCTV_DETECTION_INTERVAL_MS)
      : Math.max(detectionIntervalMs, DEVICE_DETECTION_INTERVAL_MS)

  const recordDetectionSample = (
    result: DetectionResponse,
    boxes: DetectionBox[]
  ) => {
    const now = Date.now()
    if (result.accident_detected) {
      crashRunStartedAtRef.current ??= now
    } else {
      crashRunStartedAtRef.current = null
    }

    const sample: LiveDetectionSample = {
      accidentDetected: result.accident_detected,
      boxes,
      caseId: result.caseId,
      confidence: getHighestDetectionConfidence(result),
      notificationId: result.notificationId,
      persistenceStatus: getPersistenceStatus(result),
      result,
      timestamp: now,
    }
    detectionSamplesRef.current = [...detectionSamplesRef.current, sample].slice(-6)

    const recent = detectionSamplesRef.current.slice(-STABLE_CRASH_WINDOW_SIZE)
    const crashHits = recent.filter((item) => item.accidentDetected).length
    const crashDuration =
      crashRunStartedAtRef.current == null ? 0 : now - crashRunStartedAtRef.current
    const stableCrash =
      result.accident_detected &&
      (crashHits >= STABLE_CRASH_REQUIRED_HITS ||
        crashDuration >= STABLE_CRASH_MIN_DURATION_MS)
    const consecutiveClean = detectionSamplesRef.current
      .slice()
      .reverse()
      .findIndex((item) => item.accidentDetected)

    const cleanCount =
      consecutiveClean === -1
        ? detectionSamplesRef.current.length
        : consecutiveClean
    const preferredStableSample =
      stableCrash
        ? recent
            .slice()
            .reverse()
            .find(
              (item) =>
                item.accidentDetected &&
                getPersistenceStatus(item.result) === 'created' &&
                item.result.caseId
            ) ?? sample
        : sample

    return {
      cleanCount,
      sample,
      stableBoxes: preferredStableSample.boxes,
      stableCrash,
      stableResult: preferredStableSample.result,
      timestamp: now,
    }
  }

  const applyDetectionResult = (
    result: DetectionResponse,
    rawFrameDataUrl: string | null,
    options: { emitFrameResult: boolean }
  ) => {
    const displayResult = buildDisplayResult(result)
    const displayBoxes = getDetectionOverlayBoxes(displayResult)
    const stability = recordDetectionSample(displayResult, displayBoxes)
    const surfacedResult = stability.stableCrash
      ? stability.stableResult
      : displayResult
    const surfacedBoxes = stability.stableCrash
      ? stability.stableBoxes
      : displayBoxes

    setLatestResult((current) => {
      if (
        stability.stableCrash ||
        !accidentOnlyMode ||
        stability.cleanCount >= STABLE_CLEAR_REQUIRED_MISSES
      ) {
        return surfacedResult
      }

      return current
    })

    if (displayBoxes.length > 0 && (stability.stableCrash || !accidentOnlyMode)) {
      boxHoldUntilRef.current = stability.timestamp + BOX_HOLD_MS
      setLiveOverlayBoxes(surfacedBoxes)
    } else if (
      stability.timestamp >= boxHoldUntilRef.current &&
      (!accidentOnlyMode || stability.cleanCount >= STABLE_CLEAR_REQUIRED_MISSES)
    ) {
      setLiveOverlayBoxes(surfacedBoxes)
    }

    if (accidentOnlyMode && !stability.stableCrash) {
      if (stability.cleanCount >= STABLE_CLEAR_REQUIRED_MISSES) {
        setLiveOverlayLabels([])
        setModelHint('')
      }
    } else {
      setLiveOverlayLabels(
        [...new Set(surfacedResult.detections.map((detection) => detection.label).filter(Boolean))].slice(
          0,
          6
        )
      )
      const unexpected = getUnexpectedLabels(surfacedResult.detections)
      setModelHint(
        unexpected.length > 0
          ? `The model reported â€œ${unexpected.join(', ')}â€, but this app expects only accident and vehicle (see backend/data.yaml). Replace backend/best.pt with your trained crash weights if you see COCO-style labels.`
          : ''
      )
    }

    if (options.emitFrameResult) {
      if (accidentOnlyMode) {
        onFrameResult?.(stability.stableCrash ? surfacedResult : null, rawFrameDataUrl)
      } else {
        onFrameResult?.(surfacedResult, rawFrameDataUrl)
      }
    }

    const surfaceDetection = accidentOnlyMode
      ? stability.stableCrash
      : hasMeaningfulDetection(surfacedResult)

    if (surfaceDetection) {
      const signature = getDetectionSignature(surfacedResult)
      const now = Date.now()

      onDetectionResult?.(surfacedResult)

      const isDuplicateHistoryItem =
        lastHistorySignatureRef.current === signature &&
        now - lastHistoryTimestampRef.current < DUPLICATE_HISTORY_WINDOW_MS

      if (!isDuplicateHistoryItem) {
        lastHistorySignatureRef.current = signature
        lastHistoryTimestampRef.current = now

        setHistory((previous) => [
          {
            accidentDetected: surfacedResult.accident_detected,
            confidence: getHighestDetectionConfidence(surfacedResult),
            id: `${now}`,
            labels: surfacedResult.detections.map((detection) => detection.label),
            timestamp: surfacedResult.timestamp,
          },
          ...previous,
        ].slice(0, 5))
      }
    }

    if (stability.stableCrash) {
      showCrashAlert(surfacedResult)

      const now = Date.now()
      const signature = getDetectionSignature(surfacedResult)

      if (
        now - lastAlertTimestampRef.current > ALERT_DEBOUNCE_MS ||
        lastAlertSignatureRef.current !== signature
      ) {
        lastAlertTimestampRef.current = now
        lastAlertSignatureRef.current = signature

        void playAccidentAlert(audioRef.current, alertVolume, { beepRepeats: 3 }).catch(
          (playbackError) => {
            console.warn('Could not play alert sound:', playbackError)
          }
        )
      }
    }

    return surfacedResult
  }

  const dismissCrashAlert = () => {
    setCrashAlert((current) => {
      if (current) {
        dismissedCrashAlertIdsRef.current.add(current.id)
      }
      return null
    })
  }

  const stopDetection = () => {
    if (sourceTabRef.current === 'cctv') {
      cctvAutoStartSuppressedRef.current = true
    }

    if (cctvMonitorIdRef.current) {
      void stopCctvMonitoring(cctvMonitorIdRef.current).catch(() => {
        // The UI should still stop locally if the backend worker is already gone.
      })
    }
    detectionEnabledRef.current = false
    autoStartDetectionRef.current = false
    detectionSamplesRef.current = []
    crashRunStartedAtRef.current = null
    boxHoldUntilRef.current = 0

    if (detectionIntervalRef.current) {
      clearInterval(detectionIntervalRef.current)
      detectionIntervalRef.current = null
    }

    requestInFlightRef.current = false
    setIsDetecting(false)
    setIsProcessingFrame(false)
    setIsCctvLive(false)
    setCctvConnectionStatus('')
    setCctvFrameError('')
    setLiveOverlayBoxes([])

    if (cctvStatusIntervalRef.current) {
      clearInterval(cctvStatusIntervalRef.current)
      cctvStatusIntervalRef.current = null
    }
    if (cctvFrameIntervalRef.current) {
      clearInterval(cctvFrameIntervalRef.current)
      cctvFrameIntervalRef.current = null
    }
    if (cctvPreviewUrlRef.current) {
      URL.revokeObjectURL(cctvPreviewUrlRef.current)
      cctvPreviewUrlRef.current = null
    }
    setCctvPreviewUrl(null)
    cctvStartedAtRef.current = null
    cctvLastFrameAtRef.current = null
    cctvMonitorIdRef.current = ''
  }

  const handleSourceTabChange = (value: string) => {
    stopDetection()

    if (stream) {
      stream.getTracks().forEach((track) => track.stop())
    }

    if (videoRef.current) {
      videoRef.current.srcObject = null
    }

    setStream(null)
    setIsStartingCamera(false)
    setIsCctvLive(false)
    setError('')
    setModelHint('')
    setSourceTab(value === 'cctv' ? 'cctv' : 'device')
  }

  const stopCamera = () => {
    stopDetection()

    if (stream) {
      stream.getTracks().forEach((track) => track.stop())
    }

    if (videoRef.current) {
      videoRef.current.srcObject = null
    }

    setStream(null)
    setIsStartingCamera(false)
  }

  const startCamera = async () => {
    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      const message = 'This browser does not support camera access.'
      setError(message)
      onError?.(message)
      return
    }

    setIsStartingCamera(true)
    setError('')
    autoStartDetectionRef.current = true

    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: 'environment' },
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      })

      setStream(mediaStream)
    } catch (cameraError) {
      autoStartDetectionRef.current = false
      const message = getCameraErrorMessage(cameraError)
      setError(message)
      onError?.(message)
    } finally {
      setIsStartingCamera(false)
    }
  }

  const updateOverlaySourceSize = (width: number, height: number) => {
    if (width <= 0 || height <= 0) {
      return
    }

    setOverlaySourceSize((current) => {
      if (current?.width === width && current.height === height) {
        return current
      }

      return { width, height }
    })
  }

  const captureFrameFile = async (): Promise<File | null> => {
    if (!videoRef.current || !canvasRef.current) {
      return null
    }

    const videoElement = videoRef.current

    if (videoElement.videoWidth === 0 || videoElement.videoHeight === 0) {
      return null
    }

    const canvasElement = canvasRef.current
    const context = canvasElement.getContext('2d')

    if (!context) {
      return null
    }

    canvasElement.width = videoElement.videoWidth
    canvasElement.height = videoElement.videoHeight
    updateOverlaySourceSize(canvasElement.width, canvasElement.height)
    context.drawImage(videoElement, 0, 0, canvasElement.width, canvasElement.height)

    const blob = await new Promise<Blob | null>((resolve) => {
      canvasElement.toBlob(resolve, 'image/jpeg', 0.85)
    })

    if (!blob) {
      return null
    }

    return new File([blob], `live-frame-${Date.now()}.jpg`, {
      type: 'image/jpeg',
    })
  }

  const captureFrameDataUrl = (): string | null => {
    if (!videoRef.current || !canvasRef.current) {
      return null
    }

    const videoElement = videoRef.current

    if (videoElement.videoWidth === 0 || videoElement.videoHeight === 0) {
      return null
    }

    const canvasElement = canvasRef.current
    const context = canvasElement.getContext('2d')

    if (!context) {
      return null
    }

    // Keep preview payload small enough for Firestore documents.
    const maxWidth = 360
    const scale = Math.min(1, maxWidth / videoElement.videoWidth)
    const targetWidth = Math.max(1, Math.floor(videoElement.videoWidth * scale))
    const targetHeight = Math.max(1, Math.floor(videoElement.videoHeight * scale))

    canvasElement.width = targetWidth
    canvasElement.height = targetHeight
    context.drawImage(videoElement, 0, 0, canvasElement.width, canvasElement.height)

    return canvasElement.toDataURL('image/jpeg', 0.45)
  }

  const runDetectionFrame = async () => {
    const isCctv = sourceTabRef.current === 'cctv'

    if (!detectionEnabledRef.current || requestInFlightRef.current) {
      return
    }

    if (!isCctv && !stream) {
      return
    }

    if (isCctv && !streamUrlRef.current.trim()) {
      return
    }

    requestInFlightRef.current = true
    setIsProcessingFrame(true)

    try {
      let result: DetectionResponse
      let rawFrameDataUrl: string | null = null

      if (isCctv) {
        const resolvedCameraName = sourceCamera ?? cameraName ?? 'CCTV Camera'
        const resolvedAreaId = areaId ?? 'demo'
        result = await detectFromStreamUrl(streamUrlRef.current, {
          cameraId: cameraId ?? undefined,
          cameraIp: cctvIpRef.current.trim() || undefined,
          label: resolvedCameraName,
          areaId: resolvedAreaId,
          location: resolvedCameraName,
          cameraType: 'CCTV stream',
        })
      } else {
        rawFrameDataUrl = captureFrameDataUrl()
        const frameFile = await captureFrameFile()

        if (!frameFile) {
          return
        }

        result = await detectFromFile(frameFile, 'image', {
          triggerStatus: 'camera_detection',
          sourceCamera: sourceCamera ?? cameraName ?? 'Device Live Camera',
          areaId: areaId ?? 'demo',
          cameraId: cameraId ?? 'DEVICE-LIVE-CAMERA',
          cameraName: cameraName ?? sourceCamera ?? 'Device Live Camera',
          location: sourceCamera ?? cameraName ?? 'Device Live Camera',
        })
      }

      setError('')
      const surfacedResult = applyDetectionResult(result, rawFrameDataUrl, {
        emitFrameResult: true,
      })

      if (process.env.NODE_ENV !== 'production' && surfacedResult.accident_detected) {
        console.info('[live-camera] camera detection persistence', {
          caseId: surfacedResult.caseId,
          notificationId: surfacedResult.notificationId,
          persistenceStatus: surfacedResult.persistenceStatus ?? surfacedResult.casePersistenceStatus,
          persistenceSkippedReason: surfacedResult.persistenceSkippedReason,
          alertBlockedReason: surfacedResult.alertBlockedReason,
          activeBlockingCaseId: surfacedResult.activeBlockingCaseId,
          timestamp: surfacedResult.timestamp,
          createdAt: surfacedResult.createdAt,
        })
      }
    } catch (detectionError) {
      const message =
        detectionError instanceof Error
          ? detectionError.message
          : 'Live detection failed.'

      setError(message)
      onError?.(message)
    } finally {
      requestInFlightRef.current = false
      setIsProcessingFrame(false)
    }
  }

  const handleCctvMonitorResult = (result: DetectionResponse) => {
    applyDetectionResult(result, null, { emitFrameResult: false })
  }

  const getStatusFrameUrl = (status: {
    latestFrameUrl?: string | null
    annotatedFrameUrl?: string | null
    annotatedImageUrl?: string | null
    frameUrl?: string | null
    imageUrl?: string | null
    previewUrl?: string | null
  }) =>
    status.latestFrameUrl ??
    status.annotatedFrameUrl ??
    status.annotatedImageUrl ??
    status.frameUrl ??
    status.imageUrl ??
    status.previewUrl ??
    null

  const pollCctvMonitor = async (monitorId: string) => {
    try {
      const status = await getCameraMonitoringStatus(monitorId)
      setCctvConnectionStatus(
        status.message ||
          (status.detectionRunning ? 'Monitoring live' : status.status || 'Connected')
      )
      if (status.latestFrameAvailable || status.latestFrameReceived || status.previewAvailable) {
        if (status.frameWidth && status.frameHeight) {
          updateOverlaySourceSize(status.frameWidth, status.frameHeight)
        }
        void pollCctvPreview(monitorId, getStatusFrameUrl(status))
      } else if (
        cctvStartedAtRef.current &&
        !cctvLastFrameAtRef.current &&
        Date.now() - cctvStartedAtRef.current > CCTV_FIRST_FRAME_TIMEOUT_MS
      ) {
        setCctvFrameError('Camera connected, but no video frame received.')
        setCctvConnectionStatus('Needs Attention')
        setIsProcessingFrame(false)
      }
      if (status.lastError && !isAdvancedMode) {
        setCctvFrameError('Unable to load CCTV frame. Ask admin to check this camera.')
      }
      if (status.latestResult) {
        handleCctvMonitorResult(status.latestResult)
      }
    } catch (statusError) {
      setCctvConnectionStatus(
        statusError instanceof Error ? statusError.message : 'Camera status unavailable.'
      )
    }
  }

  const pollCctvPreview = async (monitorId: string, frameUrl?: string | null) => {
    try {
      const url = await fetchCameraPreviewFrameObjectUrl(monitorId, frameUrl)
      if (cctvPreviewUrlRef.current) {
        URL.revokeObjectURL(cctvPreviewUrlRef.current)
      }
      cctvPreviewUrlRef.current = url
      cctvLastFrameAtRef.current = Date.now()
      setCctvPreviewUrl(url)
      setCctvFrameError('')
      setIsProcessingFrame(false)
    } catch (previewError) {
      // Keep the last good frame visible while the next frame is loading.
      if (
        cctvStartedAtRef.current &&
        !cctvLastFrameAtRef.current &&
        Date.now() - cctvStartedAtRef.current > CCTV_FIRST_FRAME_TIMEOUT_MS
      ) {
        setCctvFrameError('Camera connected, but no video frame received.')
        setCctvConnectionStatus('Needs Attention')
        setIsProcessingFrame(false)
      } else if (!cctvPreviewUrlRef.current && isAdvancedMode) {
        setCctvFrameError(
          previewError instanceof Error
            ? previewError.message
            : 'Camera preview is not available.'
        )
      }
    }
  }

  const startIpCctvMonitor = async () => {
    const cameraIp = cctvIpRef.current.trim()
    if (!cameraIp) {
      return false
    }

    setCctvConnectionStatus('Connecting')
    const resolvedCameraName = sourceCamera ?? cameraName ?? 'CCTV Camera'
    const resolvedAreaId = areaId ?? 'demo'
    const connection = await testCameraConnection(cameraIp, {
      cameraId: cameraId ?? undefined,
      label: resolvedCameraName,
      areaId: resolvedAreaId,
      location: resolvedCameraName,
    })
    const monitorId = connection.cameraId || connection.cameraIp || cameraIp
    cctvMonitorIdRef.current = monitorId
    cctvStartedAtRef.current = Date.now()
    cctvLastFrameAtRef.current = null
    detectionEnabledRef.current = true
    setIsCctvLive(true)
    setIsDetecting(true)
    setError('')
    setCctvFrameError('')
    setCctvConnectionStatus(connection.status || connection.message || 'Monitoring live')

    await pollCctvMonitor(monitorId)
    await pollCctvPreview(monitorId)

    cctvStatusIntervalRef.current = setInterval(() => {
      void pollCctvMonitor(monitorId)
    }, getEffectiveDetectionIntervalMs())
    cctvFrameIntervalRef.current = setInterval(() => {
      void pollCctvPreview(monitorId)
    }, 1200)
    return true
  }

  const startDetection = async (skipCameraBoot = false) => {
    if (sourceTabRef.current === 'cctv') {
      if (!cctvIpRef.current.trim() && !streamUrlRef.current.trim()) {
        const message = 'Enter a CCTV IP address or stream URL.'
        setError(message)
        onError?.(message)
        return
      }

      if (detectionEnabledRef.current) {
        return
      }

      if (cctvIpRef.current.trim()) {
        try {
          await startIpCctvMonitor()
        } catch (monitorError) {
          const detail = monitorError instanceof Error ? monitorError.message : ''
          const message = detail
            ? `Unable to connect to CCTV stream. Check camera IP/stream URL. ${detail}`
            : 'Unable to connect to CCTV stream. Check camera IP/stream URL.'
          setCctvConnectionStatus('Connection failed')
          setError(message)
          onError?.(message)
        }
        return
      }

      detectionEnabledRef.current = true
      setIsCctvLive(true)
      setIsDetecting(true)
      cctvStartedAtRef.current = Date.now()
      cctvLastFrameAtRef.current = null
      setCctvConnectionStatus('Monitoring stream URL')
      setCctvFrameError('')
      setError('')
      await runDetectionFrame()

      detectionIntervalRef.current = setInterval(() => {
        void runDetectionFrame()
      }, getEffectiveDetectionIntervalMs())
      return
    }

    if (!stream) {
      if (skipCameraBoot) {
        return
      }

      autoStartDetectionRef.current = true
      await startCamera()
      return
    }

    if (detectionEnabledRef.current) {
      return
    }

    detectionEnabledRef.current = true
    setIsDetecting(true)
    setError('')

    await runDetectionFrame()

    detectionIntervalRef.current = setInterval(() => {
      void runDetectionFrame()
    }, getEffectiveDetectionIntervalMs())
  }

  const resolvedAutoStartCctvKey =
    autoStartCctvKey ??
    [cameraId ?? '', initialCctvIp ?? '', initialStreamUrl ?? ''].join('|')

  useEffect(() => {
    cctvAutoStartAttemptedKeyRef.current = ''
    cctvAutoStartSuppressedRef.current = false
  }, [resolvedAutoStartCctvKey])

  useEffect(() => {
    const hasSavedSource = Boolean(
      (initialCctvIp ?? '').trim() || (initialStreamUrl ?? '').trim()
    )

    if (
      !autoStartCctv ||
      initialSourceTab !== 'cctv' ||
      !hasSavedSource ||
      detectionEnabledRef.current ||
      isCctvLive ||
      cctvAutoStartSuppressedRef.current ||
      cctvAutoStartAttemptedKeyRef.current === resolvedAutoStartCctvKey
    ) {
      return
    }

    cctvAutoStartAttemptedKeyRef.current = resolvedAutoStartCctvKey
    sourceTabRef.current = 'cctv'
    cctvIpRef.current = initialCctvIp ?? ''
    streamUrlRef.current = initialStreamUrl ?? ''
    setSourceTab('cctv')
    setCctvIp(initialCctvIp ?? '')
    setStreamUrl(initialStreamUrl ?? '')
    setCctvConnectionStatus('Starting saved CCTV stream')
    void startDetection()
  }, [
    autoStartCctv,
    initialCctvIp,
    initialSourceTab,
    initialStreamUrl,
    isCctvLive,
    resolvedAutoStartCctvKey,
  ])

  const isStreaming = !!stream || isCctvLive
  const hasCctvFrameSurface = Boolean(cctvPreviewUrl || resolvedAnnotatedMediaUrl)
  const effectiveDetectionIntervalMs =
    sourceTab === 'cctv'
      ? Math.max(detectionIntervalMs, CCTV_DETECTION_INTERVAL_MS)
      : Math.max(detectionIntervalMs, DEVICE_DETECTION_INTERVAL_MS)
  const overlayLabels = sourceTab === 'cctv' && !hasCctvFrameSurface ? [] : liveOverlayLabels
  const overlayBoxes = sourceTab === 'cctv' && !hasCctvFrameSurface ? [] : liveOverlayBoxes
  const confidenceDisplay = latestResult
    ? getPrimaryConfidenceDisplay(latestResult)
    : { value: null as number | null, caption: '' }
  const blockingCaseId =
    latestResult?.activeBlockingCaseId ??
    (latestResult?.existingCase ? latestResult.caseId ?? null : null)
  const lastCreatedCaseId = latestResult?.lastCreatedCaseId ?? latestResult?.caseId ?? null
  const lastCreatedNotificationId =
    latestResult?.lastCreatedNotificationId ?? latestResult?.notificationId ?? null

  const idleHint =
    sourceTab === 'cctv'
      ? managedCctvMode
        ? 'Choose an available CCTV and start monitoring.'
        : 'Enter a stream URL below. The backend pulls frames (same model as uploads).'
      : 'Start the device camera; live detection runs automatically.'
  const crashAlertReviewCaseId = crashAlert ? getCrashAlertReviewCaseId(crashAlert) : null
  const crashAlertReviewHref = crashAlertReviewCaseId
    ? `/dashboard/map?caseId=${encodeURIComponent(crashAlertReviewCaseId)}`
    : null
  const crashAlertCameraLabel = crashAlert
    ? crashAlert.result.sourceCamera ??
      crashAlert.result.cameraName ??
      sourceCamera ??
      cameraName ??
      (sourceTab === 'cctv' ? 'CCTV Camera' : 'Device Live Camera')
    : ''
  const crashAlertArea = crashAlert
    ? crashAlert.result.areaId ?? areaId ?? 'demo'
    : ''
  const crashAlertConfidence = crashAlert
    ? getHighestDetectionConfidence(crashAlert.result)
    : null
  const crashAlertTime = crashAlert
    ? new Date(crashAlert.result.createdAt ?? crashAlert.result.timestamp)
    : null
  const crashAlertCaseId = crashAlert
    ? crashAlert.kind === 'blocked'
      ? crashAlert.result.activeBlockingCaseId ?? crashAlert.result.caseId
      : crashAlert.result.caseId
    : null
  const simpleCrashStatus = crashAlert
    ? crashAlert.kind === 'created'
      ? 'Notification created'
      : crashAlert.kind === 'blocked'
        ? 'Active case already exists'
        : getCrashAlertStatusText(crashAlert)
    : ''

  return (
    <div className="space-y-6">
      <Card className="overflow-hidden border border-border">
        <Tabs
          value={sourceTab}
          onValueChange={handleSourceTabChange}
          className="gap-0 rounded-none border-0 bg-transparent shadow-none"
        >
          <div className="border-b border-border px-4 pt-4">
            <TabsList className="h-auto w-full flex-wrap justify-start gap-1 sm:w-auto">
              <TabsTrigger value="device" className="gap-1.5">
                <Camera className="size-4" />
                Device camera
              </TabsTrigger>
              <TabsTrigger value="cctv" className="gap-1.5">
                <Link2 className="size-4" />
                CCTV / stream URL
              </TabsTrigger>
            </TabsList>
          </div>

          <CctvVideoOverlay
            annotatedPreviewUrl={resolvedAnnotatedMediaUrl}
            boxes={overlayBoxes}
            boxFit={stream ? 'cover' : 'contain'}
            isDetecting={isDetecting}
            isLive={isStreaming}
            labels={
              latestResult && !latestResult.accident_detected ? [] : overlayLabels
            }
            sourceHeight={overlaySourceSize?.height ?? null}
            sourceWidth={overlaySourceSize?.width ?? null}
            timestamp={overlayTimestamp}
          >
            {stream ? (
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="h-full w-full object-cover"
                onLoadedMetadata={(event) => {
                  updateOverlaySourceSize(
                    event.currentTarget.videoWidth,
                    event.currentTarget.videoHeight
                  )
                }}
              />
            ) : isCctvLive ? (
              <div className="flex h-full w-full items-center justify-center bg-[var(--media-background)]">
                {cctvPreviewUrl ? (
                  <img
                    src={cctvPreviewUrl}
                    alt="Live CCTV preview"
                    className="h-full w-full object-contain"
                    onLoad={(event) => {
                      updateOverlaySourceSize(
                        event.currentTarget.naturalWidth,
                        event.currentTarget.naturalHeight
                      )
                    }}
                  />
                ) : resolvedAnnotatedMediaUrl ? (
                  <img
                    src={resolvedAnnotatedMediaUrl}
                    alt="Latest annotated CCTV frame"
                    className="max-h-full max-w-full object-contain"
                    onLoad={(event) => {
                      updateOverlaySourceSize(
                        event.currentTarget.naturalWidth,
                        event.currentTarget.naturalHeight
                      )
                    }}
                  />
                ) : (
                  <div className="px-6 text-center text-sm text-[var(--media-muted-foreground)]">
                    <p className="font-medium text-[var(--media-foreground)]">
                      {cctvFrameError
                        ? managedCctvMode && !isAdvancedMode
                          ? 'Unable to load CCTV frame'
                          : cctvFrameError
                        : 'Loading camera feed'}
                    </p>
                    <p className="mt-1">
                      {cctvFrameError
                        ? managedCctvMode && !isAdvancedMode
                          ? 'Ask admin to check this camera.'
                          : 'Check camera connection and frame preview status.'
                        : 'Waiting for the first video frame.'}
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex h-full items-center justify-center p-6">
                <div className="space-y-3 text-center">
                  {sourceTab === 'device' && isStartingCamera ? (
                    <Loader className="mx-auto h-8 w-8 animate-spin text-primary" />
                  ) : sourceTab === 'device' ? (
                    <Camera className="mx-auto h-12 w-12 text-primary/60" />
                  ) : (
                    <Link2 className="mx-auto h-12 w-12 text-primary/60" />
                  )}
                  <div>
                    <p className="font-medium text-[var(--media-foreground)]">
                      {sourceTab === 'device'
                        ? isStartingCamera
                          ? 'Starting camera...'
                          : 'Live preview is off'
                        : 'CCTV stream is idle'}
                    </p>
                    <p className="text-sm text-[var(--media-muted-foreground)]">{idleHint}</p>
                  </div>
                </div>
              </div>
            )}

            {isProcessingFrame && (!cctvFrameError || hasCctvFrameSurface) && (
              <div className="pointer-events-none absolute inset-x-0 bottom-0 flex items-center justify-center gap-2 bg-[color:var(--media-overlay)] px-4 py-3 text-sm text-[var(--media-foreground)]">
                <Loader className="h-4 w-4 animate-spin" />
                {sourceTab === 'cctv' && !hasCctvFrameSurface ? 'Loading camera feed' : 'Processing live frame'}
              </div>
            )}

            {crashAlert && (
              <div className="absolute left-3 right-3 top-16 z-20 sm:left-4 sm:right-auto sm:w-[min(30rem,calc(100%-2rem))]">
                <div
                  className={`rounded-lg border p-4 shadow-2xl backdrop-blur-md ${
                    crashAlert.kind === 'created'
                      ? 'border-destructive/70 bg-destructive/95 text-destructive-foreground'
                      : crashAlert.kind === 'blocked'
                        ? 'border-orange-300 bg-orange-50/95 text-orange-950 dark:border-orange-900/70 dark:bg-orange-950/95 dark:text-orange-50'
                        : 'border-yellow-300 bg-yellow-50/95 text-yellow-950 dark:border-yellow-900/70 dark:bg-yellow-950/95 dark:text-yellow-50'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div
                      className={`mt-0.5 flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-md ${
                        crashAlert.kind === 'created'
                          ? 'bg-white/15'
                          : 'bg-black/5 dark:bg-white/10'
                      }`}
                    >
                      {crashAlert.kind === 'blocked' ? (
                        <ShieldQuestion className="h-5 w-5" />
                      ) : (
                        <AlertTriangle className="h-5 w-5" />
                      )}
                    </div>

                    <div className="min-w-0 flex-1 space-y-3">
                      <div className="flex min-w-0 items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="text-xs font-semibold uppercase opacity-80">
                            Emergency Alert
                          </p>
                          <h3 className="truncate text-lg font-bold">
                            {getCrashAlertTitle(crashAlert)}
                          </h3>
                        </div>
                        <Button
                          type="button"
                          size="icon"
                          variant="ghost"
                          className={`h-8 w-8 flex-shrink-0 ${
                            crashAlert.kind === 'created'
                              ? 'text-destructive-foreground hover:bg-white/15 hover:text-destructive-foreground'
                              : ''
                          }`}
                          onClick={dismissCrashAlert}
                          aria-label="Dismiss crash alert"
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>

                      <div className="grid gap-2 text-sm sm:grid-cols-2">
                        <p className="min-w-0">
                          <span className="block text-xs font-semibold opacity-70">Camera</span>
                          <span className="block truncate">{crashAlertCameraLabel}</span>
                        </p>
                        <p className="min-w-0">
                          <span className="block text-xs font-semibold opacity-70">Area</span>
                          <span className="block truncate">{crashAlertArea}</span>
                        </p>
                        <p>
                          <span className="block text-xs font-semibold opacity-70">Confidence</span>
                          <span className="font-mono tabular-nums">
                            {crashAlertConfidence != null
                              ? `${(crashAlertConfidence * 100).toFixed(1)}%`
                              : 'Unknown'}
                          </span>
                        </p>
                        <p>
                          <span className="block text-xs font-semibold opacity-70">Detected</span>
                          <span className="font-mono text-xs tabular-nums">
                            {crashAlertTime && !Number.isNaN(crashAlertTime.getTime())
                              ? crashAlertTime.toLocaleString()
                              : 'Unknown'}
                          </span>
                        </p>
                      </div>

                      <div className="space-y-1 rounded-md bg-black/10 p-3 text-sm dark:bg-black/20">
                        {isAdvancedMode && crashAlertCaseId ? (
                          <p className="break-all">
                            <span className="font-semibold">Case ID:</span> {crashAlertCaseId}
                          </p>
                        ) : null}
                        {isAdvancedMode && crashAlert?.result.notificationId ? (
                          <p className="break-all">
                            <span className="font-semibold">Notification ID:</span>{' '}
                            {crashAlert.result.notificationId}
                          </p>
                        ) : null}
                        <p>
                          <span className="font-semibold">Status:</span>{' '}
                          {isAdvancedMode ? getCrashAlertStatusText(crashAlert) : simpleCrashStatus}
                        </p>
                        {isAdvancedMode ? (
                          <>
                            <p className="break-all">
                              <span className="font-semibold">Persistence:</span>{' '}
                              {getPersistenceStatus(crashAlert.result) ?? 'none'}
                            </p>
                            <p className="break-all">
                              <span className="font-semibold">Trigger:</span>{' '}
                              {crashAlert.result.triggerStatus ?? 'camera_detection'}
                            </p>
                            <p className="break-all">
                              <span className="font-semibold">Camera ID:</span>{' '}
                              {crashAlert.result.cameraId ?? 'none'}
                            </p>
                          </>
                        ) : null}
                      </div>

                      <div className="flex flex-wrap gap-2">
                        {crashAlertReviewHref ? (
                          <Button
                            asChild
                            size="sm"
                            variant={crashAlert.kind === 'created' ? 'secondary' : 'default'}
                            className="font-semibold"
                          >
                            <a href={crashAlertReviewHref} onClick={dismissCrashAlert}>
                              {crashAlert.kind === 'blocked' ? 'Review Existing Case' : 'Review Case'}
                            </a>
                          </Button>
                        ) : null}
                        {crashAlert.kind === 'skipped' ? (
                          <Badge variant="outline" className="border-current bg-transparent">
                            No review case created
                          </Badge>
                        ) : null}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </CctvVideoOverlay>

          <div className="space-y-4 p-4">
            {error && (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {isAdvancedMode && modelHint && (
              <Alert>
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>{modelHint}</AlertDescription>
              </Alert>
            )}

            <TabsContent value="device" className="mt-0 space-y-4 outline-none">
              <div className="grid gap-3 sm:grid-cols-2">
                <Button
                  type="button"
                  onClick={startCamera}
                  disabled={isStartingCamera || !!stream}
                >
                  {isStartingCamera ? (
                    <>
                      <Loader className="mr-2 h-4 w-4 animate-spin" />
                      Starting...
                    </>
                  ) : (
                    <>
                      <Play className="mr-2 h-4 w-4" />
                      Start Camera
                    </>
                  )}
                </Button>

                <Button
                  type="button"
                  variant="outline"
                  onClick={stopCamera}
                  disabled={!stream}
                >
                  <Square className="mr-2 h-4 w-4" />
                  Stop Camera
                </Button>
              </div>

              {isAdvancedMode ? (
              <p className="text-sm text-muted-foreground">
                Detection starts automatically when the camera opens. Frames are sent every{' '}
                {effectiveDetectionIntervalMs} ms; the next request waits until the previous one finishes.
                {accidentOnlyMode
                  ? ' Only possible crash frames are shown in the live summary, history, and alerts; other frames are still analyzed but not surfaced.'
                  : null}
              </p>
              ) : null}
            </TabsContent>

            <TabsContent value="cctv" className="mt-0 space-y-4 outline-none">
              {!managedCctvMode || isAdvancedMode ? (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="cctv-camera-ip">CCTV IP address</Label>
                    <Input
                      id="cctv-camera-ip"
                      placeholder="192.168.1.34"
                      value={cctvIp}
                      onChange={(event) => setCctvIp(event.target.value)}
                      disabled={isCctvLive || (managedCctvMode && !isAdvancedMode)}
                      autoComplete="off"
                      spellCheck={false}
                    />
                    {isAdvancedMode ? (
                      <p className="text-xs text-muted-foreground">
                        Admin configuration only. The backend uses the saved camera account to open the stream.
                      </p>
                    ) : null}
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="cctv-stream-url">Stream URL</Label>
                    <Input
                      id="cctv-stream-url"
                      placeholder="Optional: rtsp://user:pass@192.168.1.100:554/stream"
                      value={streamUrl}
                      onChange={(event) => setStreamUrl(event.target.value)}
                      disabled={isCctvLive || (managedCctvMode && !isAdvancedMode)}
                      autoComplete="off"
                      spellCheck={false}
                    />
                    {isAdvancedMode ? (
                      <p className="text-xs text-muted-foreground">
                        Optional fallback. If both fields are filled, the IP address is used first.
                      </p>
                    ) : null}
                  </div>
                </>
              ) : (
                <Alert>
                  <ShieldQuestion className="h-4 w-4" />
                  <AlertDescription>
                    Camera settings are managed by admin. Select a saved CCTV above to monitor it.
                  </AlertDescription>
                </Alert>
              )}

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-lg border border-border bg-background p-3 text-sm">
                  <p className="text-muted-foreground">Connection status</p>
                  <p className="font-medium">
                    {cctvConnectionStatus
                      ? managedCctvMode && !isAdvancedMode && cctvConnectionStatus.toLowerCase().includes('failed')
                        ? 'Unable to connect'
                        : cctvConnectionStatus
                      : isCctvLive
                        ? 'Monitoring Live'
                        : 'Offline'}
                  </p>
                </div>
                <div className="rounded-lg border border-border bg-background p-3 text-sm">
                  <p className="text-muted-foreground">Detection status</p>
                  <p className="font-medium">{isDetecting ? 'Monitoring Live' : 'Offline'}</p>
                </div>
              </div>

              {isAdvancedMode && latestResult ? (
                <div className="grid gap-3 rounded-lg border border-dashed border-border bg-background/60 p-3 text-xs text-muted-foreground sm:grid-cols-2">
                  <p className="break-all">Last confidence: {latestResult.confidence != null ? `${(latestResult.confidence * 100).toFixed(1)}%` : 'none'}</p>
                  <p className="break-all">Last result: {latestResult.lastDetectionLabel ?? (latestResult.accident_detected ? 'Possible crash' : 'No crash')}</p>
                  <p className="break-all">Last detection: {latestResult.timestamp ?? 'none'}</p>
                  <p className="break-all">Camera IP: {cctvIp || 'none'}</p>
                  <p className="break-all">Last case: {lastCreatedCaseId ?? 'none'}</p>
                  <p className="break-all">Last notification: {lastCreatedNotificationId ?? 'none'}</p>
                  <p className="break-all">Response caseId: {latestResult.caseId ?? 'none'}</p>
                  <p className="break-all">Response notificationId: {latestResult.notificationId ?? 'none'}</p>
                  <p className="break-all">Persistence: {latestResult.persistenceStatus ?? latestResult.casePersistenceStatus ?? 'none'}</p>
                  <p className="break-all">Skipped reason: {latestResult.persistenceSkippedReason ?? 'none'}</p>
                  <p className="break-all">Threshold: {latestResult.requiredThreshold != null ? `${(latestResult.requiredThreshold * 100).toFixed(1)}%` : 'none'}</p>
                  <p className="break-all">Passed threshold: {latestResult.passedThreshold == null ? 'none' : String(latestResult.passedThreshold)}</p>
                  <p className="break-all">Blocked case: {blockingCaseId ?? 'none'}</p>
                  <p className="break-all">Blocked status: {latestResult.activeBlockingStatus ?? 'none'}</p>
                  <p className="break-all">Blocked reason: {latestResult.alertBlockedReason ?? 'none'}</p>
                </div>
              ) : null}

              <div className="grid gap-3 sm:grid-cols-2">
                {!isCctvLive ? (
                  <Button
                    type="button"
                    onClick={() => void startDetection()}
                    disabled={!cctvIp.trim() && !streamUrl.trim()}
                  >
                    <Play className="mr-2 h-4 w-4" />
                    Start Monitoring
                  </Button>
                ) : null}

                {isCctvLive ? (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={stopCamera}
                  >
                    <Square className="mr-2 h-4 w-4" />
                    Stop Monitoring
                  </Button>
                ) : null}
              </div>

              <p className="text-sm text-muted-foreground">
                {managedCctvMode && !isAdvancedMode
                  ? 'Needs Review alerts appear when a possible crash is detected.'
                  : 'The backend reads the CCTV feed and runs crash detection in the background. Possible crashes remain pending review until a responder confirms them.'}
              </p>
            </TabsContent>

            {(!managedCctvMode || isAdvancedMode || sourceTab !== 'cctv') ? (
              <Button
                type="button"
                variant="secondary"
                onClick={stopDetection}
                disabled={!isDetecting}
                className="w-full sm:w-auto"
              >
                <EyeOff className="mr-2 h-4 w-4" />
                Stop Detection
              </Button>
            ) : null}
          </div>
        </Tabs>

        <canvas ref={canvasRef} className="hidden" />
      </Card>

      {latestResult?.accident_detected && (
        <Card className="border border-border">
          <div className="border-b border-border p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="text-lg font-semibold">Latest possible crash frame</h3>
                <p className="text-sm text-muted-foreground">
                  Shown only when the model reports a possible crash. Normal traffic is not listed here.
                </p>
              </div>
              <Badge
                className="min-w-[10.5rem] justify-center border-destructive/50 bg-destructive/20 text-destructive"
                variant="outline"
              >
                Possible crash
              </Badge>
            </div>
          </div>

          <div className="space-y-6 p-4">
            <div className="grid gap-4 md:grid-cols-3">
              <div className="min-h-24 rounded-lg border border-border/50 bg-card/50 p-4">
                <p className="text-sm text-muted-foreground">Confidence</p>
                <p className="w-[7ch] font-mono text-2xl font-bold tabular-nums">
                  {confidenceDisplay.value != null
                    ? `${(confidenceDisplay.value * 100).toFixed(1)}%`
                    : '—'}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {confidenceDisplay.caption}
                </p>
              </div>
              <div className="min-h-24 rounded-lg border border-border/50 bg-card/50 p-4">
                <p className="text-sm text-muted-foreground">Location</p>
                <p className="min-h-[1.75rem] text-lg font-semibold leading-7">
                  {latestResult.location}
                </p>
              </div>
              <div className="min-h-24 rounded-lg border border-border/50 bg-card/50 p-4">
                <p className="text-sm text-muted-foreground">Timestamp</p>
                <p className="min-w-[10ch] whitespace-nowrap font-mono text-lg font-semibold tabular-nums">
                  {new Date(latestResult.timestamp).toLocaleTimeString()}
                </p>
              </div>
            </div>

            <div>
              <p className="mb-3 text-sm font-semibold">Live Labels</p>
              {latestResult.detections.length > 0 ? (
                <div className="space-y-2">
                  {latestResult.detections.map((detection, index) => (
                    <div
                      key={`${detection.label}-${index}`}
                      className="grid grid-cols-[minmax(0,1fr)_8.5rem] items-center gap-3 rounded border border-border/50 bg-card/50 p-3"
                    >
                      <span className="min-w-0 truncate capitalize">
                        {detection.label}
                      </span>
                      <Badge variant="outline" className="justify-center">
                        {(detection.score * 100).toFixed(0)}% confidence
                      </Badge>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No crash or vehicle boxes passed the filter. If the backend is
                  returning other class names (e.g. bicycle), check the model hint
                  above and verify backend/best.pt is your two-class trained weights.
                </p>
              )}
            </div>

            <DetectedMediaViewer
              initialOpen={!!resolvedAnnotatedMediaUrl}
              mediaType="image"
              mediaUrl={latestResult.annotated_media_url ?? null}
              title="Possible crash annotated frame"
              description="Annotated frame from the server for this possible crash detection only."
              buttonLabel="View crash frame"
            />
          </div>
        </Card>
      )}

      <RecentDetectionHistory entries={history} />
    </div>
  )
}
