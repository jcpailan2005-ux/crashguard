// Backend API response types and case types for Car Crash Detection System.
import { CaseActionType, CaseStatus } from '@/lib/incident-status'

export type CrashCaseTriggerStatus =
  | 'camera_detection'
  | 'upload_detection'
  | 'sample_detection'
  | 'manual_report'
  | 'unknown'

export interface BoundingBox {
  label: string
  score: number
  box: [number, number, number, number] // [x1, y1, x2, y2]
}

export interface DetectionBox {
  label: string
  classId?: number
  trackId?: number
  cameraId?: string
  sessionId?: string
  sequence?: number
  capturedMonotonic?: number
  lastDetectedSequence?: number
  observationKind?: 'DETECTED' | 'PREDICTED'
  detected?: boolean
  collisionObservation?: boolean
  trackLifecycle?: 'NEW' | 'ACTIVE' | 'TEMPORARILY_MISSED' | 'RETIRED'
  confidence: number
  x: number
  y: number
  width: number
  height: number
}

export interface TrackedVehicle {
  trackId: number
  classId: number
  className: string
  confidence: number
  bbox: [number, number, number, number]
  center: [number, number]
  centerNormalized: [number, number]
  historyLength: number
}

export interface TemporalCrashEvidence {
  classifier_score?: number
  interaction_candidate?: boolean
  approach_detected?: boolean
  closing_score?: number
  convergence_score?: number
  contact_candidate?: boolean
  velocity_change_score?: number
  heading_change_score?: number
  post_contact_observations?: number
  post_contact_disruption?: boolean
  post_contact_score?: number
  min_normalized_center_distance?: number
  max_iou?: number
  temporal_score?: number
  state?: string
}

export interface AiPerformanceTimings {
  vehicle_detection_ms: number
  tracking_ms: number
  interaction_analysis_ms: number
  temporal_verification_ms: number
  total_ai_ms: number
}

/** Live provenance: capturedAt is host decode-completion UTC seconds, not sensor time.
 * Monotonic seconds are meaningful only within this backend process/session.
 */
export interface LiveBoxPacket {
  sourceFrame: LiveFrameIdentity
  inferenceStartedAt: number
  inferenceFinishedAt: number
  boxes: DetectionBox[]
  predictedTracks?: DetectionBox[]
  retiredTrackIds?: number[]
  trackingMs?: number
  imageDataUrl: string
  resultAgeMs: number
  sourceAgeMs: number | null
  validForMs: number
  retentionForMs?: number // Exact image+boxes delivery window; freshness remains 500 ms.
}

export interface LiveBoxView {
  packet: LiveBoxPacket
  expiresAt: number // Browser performance.now(), freshness deadline (500 ms window).
  receivedAt?: number // Browser performance.now() when packet was received at the client.
  retentionExpiresAt?: number // Browser performance.now(), visual retention deadline (up to 5s).
}

export interface LiveFrameIdentity {
  cameraId: string | null
  sessionId: string
  sequence: number
  capturedAt: number | null
  capturedMonotonic: number | null
  width: number | null
  height: number | null
}

export interface DetectionResponse {
  predictedTracks?: DetectionBox[]
  retiredTrackIds?: number[]
  trackingMs?: number
  sourceFrame?: LiveFrameIdentity
  inferenceStartedAt?: number
  inferenceFinishedAt?: number
  /** Serial primary/scene/vehicle model stage, separate from whole analysis time. */
  modelProcessingMs?: number
  inferenceSourceAgeAtCompletionMs?: number | null
  success: boolean
  accident_detected: boolean
  caseId?: string | null
  event_state?: 'IDLE' | 'CANDIDATE' | 'VERIFYING' | 'CONFIRMED' | 'ACTIVE' | 'CLEARED' | 'COOLDOWN' | string
  eventState?: string | null
  detector_event_id?: string | null
  detectorEventId?: string | null
  incident_created?: boolean
  incidentCreated?: boolean
  incident_id?: string | null
  incidentId?: string | null
  duplicate_event?: boolean
  duplicateEvent?: boolean
  detection_mode?: 'temporal_collision' | 'aftermath_review' | 'none' | string
  detectionMode?: 'temporal_collision' | 'aftermath_review' | 'none' | string
  decisionReason?: string | null
  aftermathCandidate?: boolean
  aftermathSuspected?: boolean
  aftermathState?: 'NONE' | 'SUSPECTED' | 'PERSISTENT' | 'REVIEW_CANDIDATE' | 'CLEARED' | string
  aftermathScore?: number
  aftermathReason?: string | null
  rejectionReasons?: string[]
  reviewRequired?: boolean
  aftermathAccepted?: boolean
  aftermathClassifierScore?: number
  aftermathAbnormalityScore?: number
  aftermathVehicleCount?: number
  aftermathPositiveObservations?: number
  aftermathPersistenceSeconds?: number
  aftermathEvidence?: Record<string, unknown>
  aftermathAnalysisMs?: number
  notificationId?: string | null
  status?: string | null
  confidence: number
  lastConfidence?: number | null
  requiredThreshold?: number | null
  threshold?: number | null
  passedThreshold?: boolean
  crashClass?: 'accident' | 'non_accident' | string | null
  crashConfidence?: number | null
  /** Accident-class probability as a 0-1 fraction. This drives crash decisions. */
  accidentProbability?: number | null
  /** Non-accident class probability as a 0-1 fraction, exposed for debugging/calibration. */
  nonAccidentProbability?: number | null
  /** Class with the highest classifier probability, separate from accidentProbability. */
  predictedClass?: 'accident' | 'non_accident' | string | null
  /** Confidence of predictedClass, separate from accidentProbability. */
  predictedClassConfidence?: number | null
  /** Crash classifier score as a 0-1 fraction. Prefer this over crashConfidence. */
  crashScore?: number | null
  /** Same value as crashScore, pre-formatted as a 0-100 percent number. */
  crashScorePercent?: number | null
  uiThreshold?: number | null
  caseThreshold?: number | null
  decisionThreshold?: number | null
  crashSuspected?: boolean | null
  crashClassifierAvailable?: boolean | null
  crashClassifierError?: string | null
  persistenceStatus?: string | null
  persistenceReason?: string | null
  persistenceSkippedReason?: string | null
  rejectionReason?: string | null
  finalDecision?: string | null
  /** True only when a temporally confirmed event was persisted. */
  caseCreated?: boolean | null
  /** True only when a notification was actually persisted alongside the case. */
  notificationCreated?: boolean | null
  /** The object detector's own label for the highest-confidence box ("car", "bus", "truck", ...), or "none".
   * Kept separate from crash-decision fields on purpose — never overwritten by crashScore/finalDecision. */
  detectedObjectLabel?: string | null
  vehicleCount?: number | null
  personCount?: number | null
  sceneValid?: boolean | null
  motionValid?: boolean | null
  interactionCandidate?: boolean | null
  tracker?: 'ByteTrack' | string | null
  trackedVehicles?: TrackedVehicle[]
  activeTracks?: number
  retainedTracks?: number
  activePairs?: number
  involvedTrackIds?: number[]
  temporalCrashCandidate?: boolean
  temporalCrashVerified?: boolean
  temporalCrashScore?: number
  temporalDecisionReason?: string | null
  contactTimestamp?: number | null
  crashEvidence?: TemporalCrashEvidence
  performance?: AiPerformanceTimings
  consecutiveCrashHits?: number | null
  requiredConsecutiveCrashHits?: number | null
  blurScore?: number | null
  brightnessScore?: number | null
  contrastScore?: number | null
  frameQualityStatus?: 'good' | 'bad' | string | null
  qualityRejectionReason?: string | null
  triggerStatus?: string | null
  cameraId?: string | null
  cameraName?: string | null
  sourceCamera?: string | null
  areaId?: string | null
  accidentDetected?: boolean
  media_type: 'image' | 'video'
  timestamp: string
  createdAt?: string
  location: string
  detections: BoundingBox[]
  boxes?: DetectionBox[]
  vehicleBoxCount?: number
  vehicleLabels?: string[]
  annotated_media_url?: string | null
  latestFrameUrl?: string | null
  frameUrl?: string | null
  imageUrl?: string | null
  previewUrl?: string | null
  annotatedFrameUrl?: string | null
  annotatedImageUrl?: string | null
  frameWidth?: number | null
  frameHeight?: number | null
  annotated_media_available?: boolean
  annotated_media_previewable?: boolean
  annotated_media_download_url?: string | null
  /** For video detections: a single annotated frame showing where the accident was flagged. */
  annotated_key_frame_url?: string | null
  /** For video detections: approximate timestamp (seconds) of the key frame. */
  annotated_key_frame_time_s?: number | null
  annotated_media_format?: string | null
  annotated_media_warning?: string | null
  processing_notes?: string | null
  existingCase?: boolean
  casePersistenceStatus?: 'created' | 'blocked_existing_case' | string | null
  alertBlockedReason?: string | null
  activeBlockingCaseId?: string | null
  activeBlockingStatus?: string | null
  lastCreatedCaseId?: string | null
  lastCreatedNotificationId?: string | null
  lastDetectionLabel?: string | null
  thresholdHit?: boolean
  rawCrashConfidence?: number | null
  keyFramePath?: string | null
  annotatedPath?: string | null
}

export interface Incident {
  id: string
  timestamp: string
  location: string
  confidence: number
  media_type: 'image' | 'video' | 'cctv'
  status: CaseStatus | 'warning' | 'processed' | 'review'
  accident_detected: boolean
  source_file?: string
  latitude?: number
  longitude?: number
}

export interface LocalCrashCase {
  caseId: string
  status: CaseStatus
  detectionMode?: 'temporal_collision' | 'aftermath_review' | string | null
  confidence: number
  createdAt?: string
  detectedAt: string
  reviewedAt?: string | null
  confirmedAt?: string | null
  falseAlarmAt?: string | null
  dispatchedAt?: string | null
  resolvedAt?: string | null
  updatedAt: string
  location?: string | null
  latitude?: number | null
  longitude?: number | null
  areaId?: string | null
  videoPath?: string | null
  keyFramePath?: string | null
  thumbnailPath?: string | null
  annotatedPath?: string | null
  sourceCamera?: string | null
  cameraId?: string | null
  cameraName?: string | null
  cameraIp?: string | null
  barangay?: string | null
  roadName?: string | null
  assignedResponderId?: string | null
  triggerStatus?: CrashCaseTriggerStatus | string | null
  responderId?: string | null
  notificationId?: string | null
  accidentDetected: boolean
  notes?: string | null
  actions?: CrashCaseAction[]
  boxes?: DetectionBox[]
  detections?: BoundingBox[]
}

export interface CctvCamera {
  cameraId: string
  label: string
  name?: string
  cameraIp?: string | null
  areaId?: string | null
  barangay?: string | null
  roadName?: string | null
  locationDescription?: string | null
  location?: string | null
  latitude?: number | null
  longitude?: number | null
  streamUrl?: string | null
  streamConfigured?: boolean
  streamSourceLabel?: string | null
  cameraType?: string | null
  status?: string | null
  cameraHealth?: string | null
  lastFrameAgeMs?: number | null
  isActive: boolean
  detectionEnabled: boolean
  lastEventAt?: string | null
  lastSeenAt?: string | null
  createdAt?: string
  updatedAt?: string
}

export interface AnalyticsSummary {
  detectionsThisMonth: number
  detectionsThisYear: number
  confirmedCrashes: number
  falseAlarms: number
  totalCases: number
  averageReviewTimeSeconds: number | null
  averageResolveTimeSeconds: number | null
}

export interface MonthlyAnalyticsPoint {
  month: string
  detections: number
  confirmedCrashes: number
  falseAlarms: number
}

export interface AreaAnalyticsPoint {
  area: string
  cases: number
}

export interface Notification {
  id: string
  incident_id: string
  title: string
  message: string
  timestamp: string
  createdAt?: string
  alertLevel: 'review' | 'warning' | 'info'
  read: boolean
  caseId?: string | null
  responderId?: string | null
  areaId?: string | null
  sourceCamera?: string | null
  cameraId?: string | null
  cameraName?: string | null
  triggerStatus?: string | null
  evidenceImageUrl?: string | null
  annotatedImageUrl?: string | null
  mediaUrl?: string | null
  thumbnailUrl?: string | null
  hasEvidence?: boolean
}

export interface CrashCaseAction {
  action: CaseActionType
  actorId: string
  timestamp: string
  notes: string
  previousStatus: CaseStatus
  nextStatus: CaseStatus
}

export interface CrashCaseLocation {
  label: string
  latitude: number
  longitude: number
  areaId?: string | null
  isFallback?: boolean
}

export interface CrashCaseMedia {
  mediaType: 'image' | 'video' | 'cctv'
  source: 'upload' | 'camera-capture' | 'live-camera' | 'sample' | 'stream'
  sourceFile?: string | null
  annotatedMediaUrl?: string | null
  annotatedMediaDownloadUrl?: string | null
  annotatedKeyFrameUrl?: string | null
  keyFrameUrl?: string | null
  thumbnailUrl?: string | null
  videoUrl?: string | null
}

export interface CrashCasePerson {
  name?: string
  phone?: string
  email?: string
}

export interface CrashCaseVehicle {
  plateNumber?: string
  type?: string
  color?: string
  description?: string
}

export interface CrashCase {
  caseId: string
  detectionId: string
  detectionMode?: 'temporal_collision' | 'aftermath_review' | string | null
  status: CaseStatus
  reviewerId: string | null
  user: CrashCasePerson | null
  vehicle: CrashCaseVehicle | null
  location: CrashCaseLocation
  media: CrashCaseMedia
  confidence: number
  notes: string
  actions: CrashCaseAction[]
  acknowledgedAt: string | null
  confirmedAt: string | null
  createdAt: string
  detectedAt: string
  dispatchedAt: string | null
  falseAlarmAt: string | null
  resolvedAt: string | null
  triggerStatus: CrashCaseTriggerStatus
  updatedAt: string
  accidentDetected: boolean
  detections: BoundingBox[]
  boxes?: DetectionBox[]
  notificationId?: string | null
  videoPath?: string | null
  keyFramePath?: string | null
  thumbnailPath?: string | null
  annotatedPath?: string | null
  sourceCamera?: string | null
  cameraName?: string | null
  cameraId?: string | null
  cameraIp?: string | null
}

export interface HealthResponse {
  status: 'ok' | 'error'
  timestamp: string
  version: string
}

export interface UploadProgress {
  progress: number
  status: 'idle' | 'uploading' | 'processing' | 'completed' | 'error'
  error?: string
}

// Mock data for demo when backend is unavailable
export const MOCK_INCIDENTS: Incident[] = [
  {
    id: 'INC001',
    timestamp: new Date(Date.now() - 2 * 60000).toISOString(),
    location: 'Talomo - McArthur Highway',
    confidence: 0.91,
    media_type: 'video',
    status: 'review',
    accident_detected: true,
    latitude: 7.0667,
    longitude: 125.5833,
  },
  {
    id: 'INC002',
    timestamp: new Date(Date.now() - 15 * 60000).toISOString(),
    location: 'Bago Aplaya - Diversion Road',
    confidence: 0.87,
    media_type: 'image',
    status: 'review',
    accident_detected: true,
    latitude: 7.0498,
    longitude: 125.6110,
  },
  {
    id: 'INC003',
    timestamp: new Date(Date.now() - 45 * 60000).toISOString(),
    location: 'Toril - Bayabas Area',
    confidence: 0.62,
    media_type: 'video',
    status: 'review',
    accident_detected: true,
    latitude: 7.0172,
    longitude: 125.5046,
  },
]

export const MOCK_NOTIFICATIONS: Notification[] = [
  {
    id: 'NOT001',
    incident_id: 'INC001',
    title: 'Possible Crash Detected',
    message: 'Possible collision detected at Talomo - McArthur Highway',
    timestamp: new Date(Date.now() - 2 * 60000).toISOString(),
    alertLevel: 'review',
    read: false,
  },
  {
    id: 'NOT002',
    incident_id: 'INC002',
    title: 'Crash Alert Needs Review',
    message: 'Possible crash detection on Bago Aplaya - Diversion Road',
    timestamp: new Date(Date.now() - 15 * 60000).toISOString(),
    alertLevel: 'review',
    read: false,
  },
  {
    id: 'NOT003',
    incident_id: 'INC003',
    title: 'Pending Responder Review',
    message: 'Potential collision at Toril - Bayabas Area - requires review',
    timestamp: new Date(Date.now() - 45 * 60000).toISOString(),
    alertLevel: 'warning',
    read: true,
  },
]
