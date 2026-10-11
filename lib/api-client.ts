// API client for car crash detection backend
// The environment remains authoritative; the fallback matches the local development stack.

import {
  DetectionResponse,
  LiveFrameIdentity,
  LiveBoxPacket,
  LiveBoxView,
  Incident,
  Notification,
  HealthResponse,
  LocalCrashCase,
  AnalyticsSummary,
  MonthlyAnalyticsPoint,
  AreaAnalyticsPoint,
  CctvCamera,
  MOCK_INCIDENTS,
  MOCK_NOTIFICATIONS,
} from './types'
import { APP_CONFIG } from '@/lib/app-config'
import { fetchWithBackendTimeout } from '@/lib/backend-fetch'
import { acceptLiveBoxPacket, createLiveBoxCursor } from '@/lib/camera-analysis-view'

export const BACKEND_URL = APP_CONFIG.backendUrl
const USE_MOCK_DATA = APP_CONFIG.useMockData
export const NORMALIZED_BACKEND_URL = BACKEND_URL.replace(/\/+$/, '')
export const IS_DEFAULT_BACKEND_URL = !process.env.NEXT_PUBLIC_BACKEND_URL
export const BACKEND_URL_SOURCE = IS_DEFAULT_BACKEND_URL
  ? 'Fallback default'
  : 'NEXT_PUBLIC_BACKEND_URL'
const IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']
const VIDEO_EXTENSIONS = ['mp4', 'mov', 'webm', 'avi', 'm4v', 'mkv']
export type DetectionMediaType = 'image' | 'video'

export class CrashGuardApiError extends Error {
  constructor(
    public readonly status: number,
    message: string
  ) {
    super(message)
    this.name = 'CrashGuardApiError'
  }
}

type ProjectLabel = 'accident' | 'vehicle'

function normalizeProjectLabel(raw: string): ProjectLabel | null {
  const label = raw.trim().toLowerCase()
  if (!label) return null

  if (label === 'accident' || label === 'crash' || label === 'collision') return 'accident'

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

function normalizeDetectionResponse(result: DetectionResponse): DetectionResponse {
  const frameUrl =
    result.latestFrameUrl ??
    result.annotatedFrameUrl ??
    result.annotatedImageUrl ??
    result.frameUrl ??
    result.imageUrl ??
    result.previewUrl ??
    result.annotated_media_url ??
    result.annotated_key_frame_url ??
    null
  const projectDetections = result.detections
    .map((d) => {
      const normalized = normalizeProjectLabel(d.label)
      return normalized ? { ...d, label: normalized } : null
    })
    .filter((d): d is NonNullable<typeof d> => Boolean(d))

  const backendConfidence = Number.isFinite(Number(result.confidence))
    ? Number(result.confidence)
    : 0
  const crashConfidence =
    result.crashConfidence != null && Number.isFinite(Number(result.crashConfidence))
      ? Number(result.crashConfidence)
      : null
  const rawCrashConfidence =
    result.rawCrashConfidence != null && Number.isFinite(Number(result.rawCrashConfidence))
      ? Number(result.rawCrashConfidence)
      : result.accident_detected
        ? crashConfidence ?? backendConfidence
        : result.rawCrashConfidence

  return {
    ...result,
    accident_detected: Boolean(result.accident_detected),
    confidence: backendConfidence,
    crashConfidence,
    rawCrashConfidence,
    annotated_media_url: result.annotated_media_url ?? frameUrl,
    latestFrameUrl: result.latestFrameUrl ?? frameUrl,
    frameUrl: result.frameUrl ?? frameUrl,
    detections: projectDetections,
  }
}

function normalizeCameraMonitoringStatus(
  status: CameraMonitoringStatus
): CameraMonitoringStatus {
  return {
    ...status,
    latestResult: status.latestResult
      ? normalizeDetectionResponse(status.latestResult)
      : status.latestResult,
  }
}

function buildBackendUnreachableMessage() {
  const guidance = [
    `Could not reach the backend at ${NORMALIZED_BACKEND_URL}.`,
    'Make sure the FastAPI server is running and that `NEXT_PUBLIC_BACKEND_URL` points to the correct address.',
  ]

  if (typeof window === 'undefined') {
    return guidance.join(' ')
  }

  const pageUrl = new URL(window.location.href)
  const backendUrl = new URL(NORMALIZED_BACKEND_URL)

  if (
    pageUrl.protocol === 'https:' &&
    backendUrl.protocol === 'http:'
  ) {
    guidance.push(
      'This page is loaded over HTTPS but the backend uses HTTP, so the browser may be blocking the request as mixed content.'
    )
  }

  if (
    IS_DEFAULT_BACKEND_URL &&
    !['localhost', '127.0.0.1'].includes(pageUrl.hostname)
  ) {
    guidance.push(
      'The app is using the local fallback `http://127.0.0.1:8010`. Set `NEXT_PUBLIC_BACKEND_URL` when the API runs elsewhere.'
    )
  }

  return guidance.join(' ')
}

function createMockDetectionResponse(
  mediaType: DetectionMediaType
): DetectionResponse {
  return {
    success: true,
    accident_detected: Math.random() > 0.5,
    confidence: 0.75 + Math.random() * 0.25,
    media_type: mediaType,
    timestamp: new Date().toISOString(),
    location: 'Demo Location',
    detections: [
      {
        label: 'vehicle',
        score: 0.95,
        box: [100, 120, 220, 260],
      },
      {
        label: 'accident',
        score: 0.85,
        box: [140, 150, 260, 300],
      },
    ],
  }
}

export function detectMediaTypeFromFile(
  file: Pick<File, 'name' | 'type'>
): DetectionMediaType | null {
  if (file.type.startsWith('image/')) {
    return 'image'
  }

  if (file.type.startsWith('video/')) {
    return 'video'
  }

  const extension = file.name.split('.').pop()?.toLowerCase()

  if (extension && IMAGE_EXTENSIONS.includes(extension)) {
    return 'image'
  }

  if (extension && VIDEO_EXTENSIONS.includes(extension)) {
    return 'video'
  }

  return null
}

function validateDetectionFile(
  file: File,
  mediaType: DetectionMediaType
) {
  if (!(file instanceof File)) {
    throw new Error('No file was provided for detection.')
  }

  if (file.size <= 0) {
    throw new Error('The selected file is empty. Please choose a valid image or video.')
  }

  if (mediaType === 'image') {
    if (detectMediaTypeFromFile(file) !== 'image') {
      throw new Error('Please choose a valid image file before running detection.')
    }

    return
  }

  if (detectMediaTypeFromFile(file) !== 'video') {
    throw new Error('Please choose a valid video file before running detection.')
  }
}

/**
 * Resolve backend media URLs so the UI can handle either absolute or relative paths.
 */
export function resolveBackendMediaUrl(
  mediaUrl?: string | null
): string | null {
  if (!mediaUrl) {
    return null
  }

  if (/^https?:\/\//i.test(mediaUrl)) {
    return mediaUrl
  }

  const normalizedPath = mediaUrl.startsWith('/') ? mediaUrl : `/${mediaUrl}`
  return `${NORMALIZED_BACKEND_URL}${normalizedPath}`
}

/**
 * Generic fetch wrapper with error handling
 * @param endpoint API endpoint path
 * @param options Fetch options
 * @returns Parsed JSON response
 */
async function apiCall<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${NORMALIZED_BACKEND_URL}${endpoint}`
  const headers = new Headers(options.headers)
  if (!headers.has('Content-Type') && options.body && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  try {
    const response = await fetch(url, {
      ...options,
      headers,
      credentials: options.credentials ?? 'include',
    })

    if (!response.ok) {
      const message = await readErrorMessage(response, `API Error: ${response.status} ${response.statusText}`)
      throw new CrashGuardApiError(response.status, message)
    }

    return (await response.json()) as T
  } catch (error) {
    if (!(error instanceof CrashGuardApiError)) {
      console.error(`API call failed to ${url}:`, error)
    }
    throw error
  }
}

async function readErrorMessage(
  response: Response,
  fallbackMessage: string
): Promise<string> {
  try {
    const data = (await response.json()) as any
    if (data && typeof data.detail === 'object' && data.detail !== null) {
      return data.detail.message || JSON.stringify(data.detail)
    }
    return data.detail || data.error || data.message || fallbackMessage
  } catch {
    try {
      const text = await response.text()
      return text || fallbackMessage
    } catch {
      return fallbackMessage
    }
  }
}

/**
 * Upload image or video file for detection
 * @param file Image or video file to detect
 * @param mediaType Type of media ('image' or 'video')
 * @returns Detection result with accident status and confidence
 *
 * BACKEND INTEGRATION:
 * - POST /api/detect/image with multipart/form-data
 * - POST /api/detect/video with multipart/form-data
 * - Should run YOLO model and return detection results
 */
/**
 * Capture one frame from a CCTV / network stream on the backend (RTSP, HTTP, HTTPS)
 * and run the same image detection pipeline as file uploads.
 */
export async function detectFromStreamUrl(
  streamUrl: string,
  metadata: {
    cameraId?: string
    label?: string
    areaId?: string
    location?: string
    cameraType?: string
    cameraIp?: string
  } = {}
): Promise<DetectionResponse> {
  const trimmed = streamUrl.trim()
  if (!trimmed) {
    throw new Error('Please enter a stream URL.')
  }

  let response: Response

  try {
    response = await fetch(`${NORMALIZED_BACKEND_URL}/api/detect/stream-frame`, {
      method: 'POST',
      headers: await authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ url: trimmed, ...metadata }),
    })
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error(buildBackendUnreachableMessage())
    }
    throw error
  }

  if (!response.ok) {
    const message = await readErrorMessage(
      response,
      `Stream detection failed with status ${response.status}.`
    )
    throw new Error(message)
  }

  const result = (await response.json()) as DetectionResponse
  return normalizeDetectionResponse(result)
}

type RawNotification = Omit<Partial<Notification>, 'alertLevel' | 'read' | 'timestamp'> & {
  notificationId?: string | number
  notification_id?: string | number
  case_id?: string | number
  alertLevel?: string
  alert_level?: string
  timestamp?: string
  createdAt?: string
  created_at?: string
  isRead?: boolean | number | string
  is_read?: boolean | number | string
  read?: boolean | number | string
  responder_id?: string | null
  area_id?: string | null
  sourceCamera?: string | null
  source_camera?: string | null
  cameraId?: string | null
  camera_id?: string | null
  cameraName?: string | null
  camera_name?: string | null
  triggerStatus?: string | null
  trigger_status?: string | null
  evidenceImageUrl?: string | null
  evidence_image_url?: string | null
  annotatedImageUrl?: string | null
  annotated_image_url?: string | null
  mediaUrl?: string | null
  media_url?: string | null
  thumbnailUrl?: string | null
  thumbnail_url?: string | null
  hasEvidence?: boolean | number | string
  has_evidence?: boolean | number | string
}

function normalizeReadFlag(
  value: RawNotification['read'] | RawNotification['isRead'] | RawNotification['is_read']
): boolean {
  if (typeof value === 'boolean') return value
  if (typeof value === 'number') return value !== 0
  if (typeof value === 'string') {
    return value === '1' || value.toLowerCase() === 'true'
  }
  return false
}

function normalizeNotification(raw: RawNotification): Notification {
  const alertLevel = raw.alertLevel ?? raw.alert_level
  const caseId = raw.caseId ?? raw.case_id ?? raw.incident_id ?? null
  const timestamp = String(raw.timestamp ?? raw.createdAt ?? raw.created_at ?? new Date().toISOString())
  const evidenceImageUrl = raw.evidenceImageUrl ?? raw.evidence_image_url ?? null
  const annotatedImageUrl = raw.annotatedImageUrl ?? raw.annotated_image_url ?? null
  const mediaUrl = raw.mediaUrl ?? raw.media_url ?? null
  const thumbnailUrl = raw.thumbnailUrl ?? raw.thumbnail_url ?? null
  return {
    id: String(raw.id ?? raw.notificationId ?? raw.notification_id ?? caseId ?? crypto.randomUUID()),
    incident_id: String(raw.incident_id ?? raw.case_id ?? raw.caseId ?? ''),
    caseId: caseId == null ? null : String(caseId),
    title: String(raw.title ?? 'Crash Alert Needs Review'),
    message: String(raw.message ?? ''),
    timestamp,
    createdAt: String(raw.createdAt ?? raw.created_at ?? timestamp),
    alertLevel:
      alertLevel === 'review' || alertLevel === 'warning'
        ? alertLevel
        : 'info',
    read: normalizeReadFlag(raw.read ?? raw.isRead ?? raw.is_read),
    responderId: raw.responderId ?? raw.responder_id ?? null,
    areaId: raw.areaId ?? raw.area_id ?? null,
    sourceCamera: raw.sourceCamera ?? raw.source_camera ?? null,
    cameraId: raw.cameraId ?? raw.camera_id ?? null,
    cameraName: raw.cameraName ?? raw.camera_name ?? null,
    triggerStatus: raw.triggerStatus ?? raw.trigger_status ?? null,
    evidenceImageUrl,
    annotatedImageUrl,
    mediaUrl,
    thumbnailUrl,
    hasEvidence: normalizeReadFlag(raw.hasEvidence ?? raw.has_evidence) || Boolean(evidenceImageUrl || annotatedImageUrl || mediaUrl || thumbnailUrl),
  }
}

function notificationTime(value: Notification): number {
  const parsed = new Date(value.createdAt ?? value.timestamp).getTime()
  return Number.isNaN(parsed) ? 0 : parsed
}

async function authHeaders(extra?: HeadersInit): Promise<Headers> {
  return new Headers(extra)
}

export interface AuthUser {
  uid: string
  email: string
  displayName: string
  role: 'admin' | 'dispatcher' | 'responder'
  roles?: Array<'ADMIN' | 'DISPATCHER' | 'RESPONDER'>
  permissions?: string[]
  areaId: string | null
  active: boolean
  status?: 'ACTIVE' | 'DISABLED' | 'LOCKED'
  mustChangePassword: boolean
  availabilityStatus?: string | null
  createdAt: string
  updatedAt: string
  lastLoginAt?: string | null
}

export interface AuthResponse {
  user: AuthUser
}

export async function loginWithPostgres(email: string, password: string): Promise<AuthResponse> {
  const response = await fetchWithBackendTimeout(`${NORMALIZED_BACKEND_URL}/api/v3/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
    credentials: 'include',
  })
  if (!response.ok) {
    throw new CrashGuardApiError(
      response.status,
      await readErrorMessage(response, 'Login failed.')
    )
  }
  return (await response.json()) as AuthResponse
}

/** @deprecated Compatibility name for older components; uses PostgreSQL v3 auth. */
export const loginWithSQLite = loginWithPostgres

export async function logoutFromPostgres(): Promise<void> {
  await apiCall<{ success: boolean }>('/api/v3/auth/logout', { method: 'POST' })
}

export async function getCurrentPostgresUser(): Promise<AuthUser> {
  return apiCall<{ user: AuthUser }>('/api/v3/auth/me').then((result) => result.user)
}

/** @deprecated Compatibility name for older components; uses PostgreSQL v3 auth. */
export const getCurrentSQLiteUser = getCurrentPostgresUser

export async function changePostgresPassword(
  currentPassword: string,
  newPassword: string
): Promise<AuthUser> {
  return apiCall<{ user: AuthUser }>('/api/v3/auth/change-password', {
    method: 'POST',
    body: JSON.stringify({ currentPassword, newPassword }),
  }).then((result) => result.user)
}

export interface CameraConnectionResult {
  connected: boolean
  status?: string
  cameraHealth?: string
  message: string
  cameraId?: string
  cameraIp?: string
  label?: string
  width?: number
  height?: number
}

export async function testCameraConnection(
  cameraIpOrUrl: string,
  metadata: {
    cameraId?: string
    label?: string
    areaId?: string
    location?: string
    cameraUsername?: string
    cameraPassword?: string
    streamType?: string
    rtspPort?: number
  } = {}
): Promise<CameraConnectionResult> {
  let response: Response
  const source = cameraIpOrUrl.trim()
  const isStreamUrl = /^[a-z][a-z0-9+.-]*:\/\//i.test(source)

  try {
    response = await fetch(`${NORMALIZED_BACKEND_URL}/api/cameras/test-connection`, {
      method: 'POST',
      headers: await authHeaders({ 'Content-Type': 'application/json' }),
      credentials: 'include',
      body: JSON.stringify({ [isStreamUrl ? 'url' : 'cameraIp']: source, ...metadata }),
    })
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error(buildBackendUnreachableMessage())
    }
    throw error
  }

  if (!response.ok) {
    try {
      const data = await response.json()
      let detail = data?.detail || data
      if (typeof detail === 'object' && detail !== null) {
        return {
          connected: false,
          status: detail.status || 'OFFLINE',
          cameraHealth: 'OFFLINE',
          message: detail.message || 'Camera connection could not be verified directly.',
        }
      }
      const rawMessage = String(detail || '')
      const message = rawMessage.toLowerCase().includes('authentication')
        ? 'RTSP stream link is ready to save.'
        : rawMessage || `Camera connection failed with status ${response.status}.`

      return {
        connected: false,
        status: 'OFFLINE',
        cameraHealth: 'OFFLINE',
        message,
      }
    } catch {
      return {
        connected: false,
        status: 'OFFLINE',
        cameraHealth: 'OFFLINE',
        message: `Camera connection failed with status ${response.status}.`,
      }
    }
  }

  return (await response.json()) as CameraConnectionResult
}

export interface CameraMonitoringStatus {
  latestFrameIdentity?: LiveFrameIdentity | null
  sourceReportedFps?: number | null
  modelProcessingMs?: number | null
  inferenceCompletionAgeMs?: number | null
  frameCopyMs?: number | null
  framesSkippedBeforeInference?: number
  cameraId?: string | null
  cameraIp?: string | null
  monitorKey?: string | null
  streamUrlConfigured?: boolean
  label?: string
  status:
    | 'disconnected'
    | 'connecting'
    | 'monitoring-live'
    | 'possible-crash-detected'
    | 'connection-lost'
    | 'reconnecting'
    | 'demo'
  message?: string
  lastCheckedAt?: string | null
  lastFrameTimestamp?: string | null
  lastFrameAt?: string | null
  lastDetectionAt?: string | null
  confidence?: number | null
  lastConfidence?: number | null
  lastDetectionLabel?: string | null
  lastResult?: string | null
  vehicleBoxCount?: number
  vehicleLabels?: string[]
  cameraConnected?: boolean
  monitoringLive?: boolean
  latestFrameReceived?: boolean
  latestFrameAvailable?: boolean
  latestFrameUrl?: string | null
  frameUrl?: string | null
  imageUrl?: string | null
  previewUrl?: string | null
  annotatedFrameUrl?: string | null
  annotatedImageUrl?: string | null
  frameWidth?: number | null
  frameHeight?: number | null
  frameAgeMs?: number | null
  lastConnectionAt?: string | null
  connectionAttemptCount?: number
  reconnectCount?: number
  droppedFrames?: number
  staleFrameEvents?: number
  captureMs?: number | null
  decodeMs?: number | null
  processingLatencyMs?: number | null
  cameraHealth?: 'ONLINE' | 'LIVE' | 'STALE' | 'RECONNECTING' | 'OFFLINE' | 'DISABLED' | string
  detectionWorkerRunning?: boolean
  detectionRunning?: boolean
  activePendingCase?: boolean
  activeCaseId?: string | null
  activeBlockingCaseId?: string | null
  activeBlockingStatus?: string | null
  alertBlockedReason?: string | null
  lastCreatedCaseId?: string | null
  lastCreatedNotificationId?: string | null
  lastError?: string | null
  latestResult?: DetectionResponse | null
  previewAvailable?: boolean
  existingCaseMessage?: string | null
  reconnecting?: boolean
  captureFps?: number | null
  previewFps?: number | null
  aiFps?: number | null
  sourceWidth?: number | null
  sourceHeight?: number | null
  sourceResolution?: string | null
  previewResolution?: string | null
  aiResolution?: string | null
  codec?: string | null
}

export interface CameraStreamAccess {
  token: string
  expiresInSeconds: number
  streamUrl?: string
  previewUrl: string
  eventsUrl: string
}

export async function getCameraMonitoringStatus(
  cameraIdOrIp: string
): Promise<CameraMonitoringStatus> {
  const status = await apiCall<CameraMonitoringStatus>(
    `/api/cameras/${encodeURIComponent(cameraIdOrIp.trim())}/status`
  )
  return normalizeCameraMonitoringStatus(status)
}

export function getCameraPreviewFrameUrl(cameraIp: string): string {
  const encodedIp = encodeURIComponent(cameraIp.trim())
  return `${NORMALIZED_BACKEND_URL}/api/cameras/${encodedIp}/latest-frame.jpg?t=${Date.now()}`
}

export function getCameraMjpegPreviewUrl(cameraIdOrIp: string): string {
  return `${NORMALIZED_BACKEND_URL}/api/cameras/${encodeURIComponent(cameraIdOrIp.trim())}/preview.mjpeg`
}

export async function createCameraStreamAccess(cameraId: string): Promise<CameraStreamAccess> {
  return apiCall<CameraStreamAccess>(
    `/api/cameras/${encodeURIComponent(cameraId.trim())}/stream-token`,
    { method: 'POST' }
  )
}

// This channel is visual only: it never normalizes or dispatches incident results.
export function subscribeCameraBoxes(
  cameraId: string,
  eventsUrl: string | null,
  receive: (view: LiveBoxView | null) => void
): () => void {
  let stopped = false
  let inFlight = false
  let pending = false
  const cursor = createLiveBoxCursor()
  let fallback = true
  let controller: AbortController | null = null
  const fetchLatest = async () => {
    if (stopped) return
    if (inFlight) { pending = true; return }
    inFlight = true
    controller = new AbortController()
    const requestController = controller
    const timeout = setTimeout(() => requestController.abort(), 2000)
    const started = performance.now()
    try {
      const response = await fetch(`${NORMALIZED_BACKEND_URL}/api/cameras/${encodeURIComponent(cameraId)}/analysis-packet`, {
        headers: await authHeaders(), credentials: 'include', cache: 'no-store', signal: requestController.signal,
      })
      if (!response.ok) throw new Error('Analysis preview unavailable')
      const { packet } = await response.json() as { packet: LiveBoxPacket | null }
      if (stopped) return
      if (!packet) { receive(null); return }
      const transportMs = performance.now() - started
      const now = performance.now()
      const view = acceptLiveBoxPacket(cameraId, packet, cursor, transportMs, now)
      if (view) receive(view)
    } catch {
      if (!stopped) receive(null)
    } finally {
      clearTimeout(timeout)
      inFlight = false
      if (pending && !stopped) { pending = false; void fetchLatest() }
    }
  }
  let events: EventSource | null = null
  if (typeof EventSource !== 'undefined') {
    const url = new URL(eventsUrl || `${NORMALIZED_BACKEND_URL}/api/cameras/${encodeURIComponent(cameraId)}/events`)
    url.searchParams.set('boxes_only', 'true')
    events = new EventSource(url.toString(), { withCredentials: true })
    // An open SSE socket does not prove that a boxes event can reach this
    // browser. Keep the bounded read-only fallback active until the first
    // actual boxes notification arrives, then let SSE drive packet reads.
    events.onopen = () => { void fetchLatest() }
    events.onerror = () => { fallback = true }
    events.addEventListener('boxes', () => { fallback = false; void fetchLatest() })
  }
  const timer = setInterval(() => { if (fallback) void fetchLatest() }, 250)
  void fetchLatest()
  return () => {
    stopped = true
    clearInterval(timer)
    events?.close()
    controller?.abort()
  }
}

export async function fetchCameraPreviewFrameObjectUrl(
  cameraId: string,
  frameUrl?: string | null
): Promise<string> {
  let targetPath = `/api/cameras/${encodeURIComponent(cameraId.trim())}/latest-frame.jpg`
  if (frameUrl?.trim()) {
    try {
      const parsed = new URL(frameUrl)
      targetPath = `${parsed.pathname}${parsed.search}`
    } catch {
      targetPath = frameUrl.startsWith('/') ? frameUrl : `/${frameUrl}`
    }
  }
  const separator = targetPath.includes('?') ? '&' : '?'
  const url = `${NORMALIZED_BACKEND_URL}${targetPath}${separator}t=${Date.now()}`
  const response = await fetch(
    url,
    {
      headers: await authHeaders(),
      credentials: 'include',
    }
  )
  if (!response.ok) {
    const message = await readErrorMessage(response, 'Camera preview is not available.')
    throw new Error(message)
  }
  return URL.createObjectURL(await response.blob())
}

export async function testDetectionOnCurrentFrame(
  cameraIdOrIp: string
): Promise<DetectionResponse> {
  return apiCall<DetectionResponse>(
    `/api/cameras/${encodeURIComponent(cameraIdOrIp.trim())}/test-detection`,
    { method: 'POST' }
  )
}

export async function getCctvCameras(): Promise<CctvCamera[]> {
  return apiCall<CctvCamera[]>('/api/cameras')
}

export async function getLocalWebcamSources(): Promise<Array<{ reference: string; name: string }>> {
  return apiCall<Array<{ reference: string; name: string }>>('/api/cameras/local-webcam-sources')
}

export async function getCctvCamera(cameraId: string): Promise<CctvCamera> {
  return apiCall<CctvCamera>(`/api/cameras/${encodeURIComponent(cameraId)}`)
}

export async function saveCctvCamera(camera: Partial<CctvCamera> & { label: string; areaId: string }): Promise<CctvCamera> {
  const endpoint = camera.cameraId
    ? `/api/cameras/${encodeURIComponent(camera.cameraId)}`
    : '/api/cameras'
  return apiCall<CctvCamera>(endpoint, {
    method: camera.cameraId ? 'PUT' : 'POST',
    body: JSON.stringify(camera),
  })
}

export async function disableCctvCamera(cameraId: string): Promise<CctvCamera> {
  return apiCall<CctvCamera>(`/api/cameras/${encodeURIComponent(cameraId)}/disable`, {
    method: 'POST',
  })
}

export async function enableCctvCamera(cameraId: string): Promise<CctvCamera> {
  return apiCall<CctvCamera>(`/api/cameras/${encodeURIComponent(cameraId)}/enable`, {
    method: 'POST',
  })
}

export async function deleteCctvCamera(cameraId: string): Promise<{ ok: boolean; cameraId: string; status: string }> {
  return apiCall<{ ok: boolean; cameraId: string; status: string }>(`/api/cameras/${encodeURIComponent(cameraId)}`, {
    method: 'DELETE',
  })
}

export async function startCctvMonitoring(cameraId: string): Promise<CameraMonitoringStatus> {
  const status = await apiCall<CameraMonitoringStatus>(
    `/api/cameras/${encodeURIComponent(cameraId)}/monitor/start`,
    { method: 'POST' }
  )
  return normalizeCameraMonitoringStatus(status)
}

export async function stopCctvMonitoring(cameraId: string): Promise<{ ok: boolean; cameraId: string; status: string }> {
  return apiCall<{ ok: boolean; cameraId: string; status: string }>(
    `/api/cameras/${encodeURIComponent(cameraId)}/monitor/stop`,
    { method: 'POST' }
  )
}

export async function assignCctvCamera(params: {
  responderId: string
  cameraId?: string
  areaId?: string
  role?: string
  status?: string
}): Promise<Record<string, unknown>> {
  return apiCall<Record<string, unknown>>('/api/camera-assignments', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

export async function detectFromCameraIp(
  cameraIp: string,
  metadata: {
    cameraId?: string
    label?: string
    areaId?: string
    location?: string
  } = {}
): Promise<DetectionResponse> {
  const trimmed = cameraIp.trim()
  if (!trimmed) {
    throw new Error('Please enter the camera IP address.')
  }

  let response: Response

  try {
    response = await fetch(`${NORMALIZED_BACKEND_URL}/api/detect/stream-frame`, {
      method: 'POST',
      headers: await authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ cameraIp: trimmed, ...metadata }),
    })
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error(buildBackendUnreachableMessage())
    }
    throw error
  }

  if (!response.ok) {
    const message = await readErrorMessage(
      response,
      `Camera detection failed with status ${response.status}.`
    )
    throw new Error(message)
  }

  const result = (await response.json()) as DetectionResponse
  return normalizeDetectionResponse(result)
}

export interface CameraSettings {
  cameraLabel?: string
  cameraIp?: string
  areaId?: string
  location?: string
  cameraUsername?: string
  cameraPassword?: string
  streamType?: 'stream1' | 'stream2'
  rtspPort?: number
  hasCredentials?: boolean
  cameraPasswordConfigured?: boolean
}

export async function getCameraSettings(): Promise<CameraSettings> {
  return apiCall<CameraSettings>('/api/camera-settings')
}

export async function saveCameraSettings(settings: CameraSettings): Promise<CameraSettings> {
  return apiCall<CameraSettings>('/api/camera-settings', {
    method: 'POST',
    body: JSON.stringify(settings),
  })
}

export async function detectFromFile(
  file: File,
  mediaType?: DetectionMediaType,
  metadata: {
    triggerStatus?: 'camera_detection' | 'upload_detection'
    sourceCamera?: string
    areaId?: string
    cameraId?: string
    cameraName?: string
    cameraIp?: string
    location?: string
  } = {}
): Promise<DetectionResponse> {
  try {
    const resolvedMediaType = mediaType ?? detectMediaTypeFromFile(file)

    if (!resolvedMediaType) {
      throw new Error('Please select an image or video file.')
    }

    validateDetectionFile(file, resolvedMediaType)

    const formData = new FormData()
    formData.append('file', file)
    Object.entries(metadata).forEach(([key, value]) => {
      if (value) {
        formData.append(key, value)
      }
    })

    let response: Response

    try {
      console.info(
        `[detect] Sending ${resolvedMediaType} file to backend`,
        {
          endpoint: `${NORMALIZED_BACKEND_URL}/api/detect/${resolvedMediaType}`,
          filename: file.name,
          size: file.size,
          type: file.type || 'unknown',
        }
      )

      response = await fetch(`${NORMALIZED_BACKEND_URL}/api/detect/${resolvedMediaType}`, {
        method: 'POST',
        headers: await authHeaders(),
        body: formData,
      })
    } catch (error) {
      if (error instanceof TypeError) {
        throw new Error(buildBackendUnreachableMessage())
      }

      throw error
    }

    if (!response.ok) {
      const message = await readErrorMessage(
        response,
        `Detection failed with status ${response.status}.`
      )
      console.warn('[detect] Backend returned an error response', {
        mediaType: resolvedMediaType,
        status: response.status,
        message,
      })
      throw new Error(message)
    }

    const result = (await response.json()) as DetectionResponse
    console.info('[detect] Detection completed', {
      mediaType: resolvedMediaType,
      accident_detected: result.accident_detected,
      annotated_media_available: result.annotated_media_available,
      annotated_media_url: result.annotated_media_url,
    })
    return normalizeDetectionResponse(result)
  } catch (error) {
    console.error('Detection request failed:', error)
    if (USE_MOCK_DATA) {
      console.warn('Falling back to mock detection response')
      return createMockDetectionResponse(
        mediaType ?? detectMediaTypeFromFile(file) ?? 'image'
      )
    }

    if (error instanceof Error) {
      throw error
    }

    throw new Error('Detection request failed.')
  }
}

/**
 * Get all recent incidents
 * @returns List of detected incidents
 *
 * BACKEND INTEGRATION:
 * - GET /api/incidents
 * - Should return paginated list of all detected accidents
 */
export async function getIncidents(): Promise<Incident[]> {
  try {
    return await apiCall<Incident[]>('/api/incidents')
  } catch (error) {
    console.warn('Failed to fetch incidents, using mock data')
    return MOCK_INCIDENTS
  }
}

/**
 * Get all notifications
 * @returns List of notifications for detected incidents
 *
 * BACKEND INTEGRATION:
 * - GET /api/notifications
 * - Should return alerts and notifications
 */
export async function getNotifications(): Promise<Notification[]> {
  try {
    const notifications = await apiCall<RawNotification[]>('/api/notifications')
    const normalized = notifications
      .map(normalizeNotification)
      .sort((a, b) => notificationTime(b) - notificationTime(a))
    if (typeof window !== 'undefined') {
      console.info('[notifications] fetched', {
        count: normalized.length,
        newestId: normalized[0]?.id ?? null,
        newestTimestamp: normalized[0]?.timestamp ?? null,
      })
    }
    return normalized
  } catch (error) {
    if (USE_MOCK_DATA) {
      console.warn('Failed to fetch notifications, using mock data')
      return MOCK_NOTIFICATIONS
    }
    throw error
  }
}

export async function archiveNotification(notificationId: string): Promise<{ notificationId: string; archived: boolean }> {
  return apiCall<{ notificationId: string; archived: boolean }>(
    `/api/notifications/${encodeURIComponent(notificationId)}/archive`,
    { method: 'POST' }
  )
}

export async function deleteNotification(notificationId: string): Promise<{ notificationId: string; deleted: boolean }> {
  return apiCall<{ notificationId: string; deleted: boolean }>(
    `/api/notifications/${encodeURIComponent(notificationId)}`,
    { method: 'DELETE' }
  )
}

export async function getLocalCrashCases(params: {
  search?: string
  status?: string
  areaId?: string
  date?: string
  fromDate?: string
  toDate?: string
  sort?: string
  limit?: number
  offset?: number
} = {}): Promise<LocalCrashCase[]> {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value != null && value !== '' && value !== 'all') {
      query.set(key, String(value))
    }
  })
  return apiCall<LocalCrashCase[]>(`/api/crash-cases${query.toString() ? `?${query}` : ''}`)
}

export async function getLocalCrashCase(caseId: string): Promise<LocalCrashCase> {
  return apiCall<LocalCrashCase>(`/api/crash-cases/${encodeURIComponent(caseId)}`)
}

export async function getAnalyticsSummary(): Promise<AnalyticsSummary> {
  return apiCall<AnalyticsSummary>('/api/analytics/summary')
}

export async function getMonthlyAnalytics(): Promise<MonthlyAnalyticsPoint[]> {
  return apiCall<MonthlyAnalyticsPoint[]>('/api/analytics/monthly')
}

export async function getAreaAnalytics(): Promise<AreaAnalyticsPoint[]> {
  return apiCall<AreaAnalyticsPoint[]>('/api/analytics/areas')
}

export async function applyLocalCrashCaseAction(
  caseId: string,
  params: { action: string; actorId?: string; notes?: string }
): Promise<LocalCrashCase> {
  return apiCall<LocalCrashCase>(`/api/crash-cases/${encodeURIComponent(caseId)}/actions`, {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

/**
 * Check backend health/status
 * @returns Health status of backend
 *
 * BACKEND INTEGRATION:
 * - GET /api/health
 * - Should return status and version info
 */
export async function checkBackendHealth(): Promise<HealthResponse> {
  try {
    return await apiCall<HealthResponse>('/api/health')
  } catch (error) {
    console.warn('Backend health check failed')
    return {
      status: 'error',
      timestamp: new Date().toISOString(),
      version: 'unknown',
    }
  }
}

/**
 * Get dashboard statistics
 * @returns Stats about uploads and detections
 */
export async function getDashboardStats() {
  try {
    const incidents = await getIncidents()
    const totalCount = incidents.length
    const accidentCount = incidents.filter(
      (i) => i.accident_detected
    ).length

    return {
      totalUploads: totalCount,
      accidentsDetected: accidentCount,
      lastDetectionTime: incidents[0]?.timestamp || null,
    }
  } catch (error) {
    console.warn('Failed to get dashboard stats')
    return {
      totalUploads: 0,
      accidentsDetected: 0,
      lastDetectionTime: null,
    }
  }
}
