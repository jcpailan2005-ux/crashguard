'use client'

import {
  addDoc,
  collection,
  doc,
  getDoc,
  onSnapshot,
  orderBy,
  query,
  serverTimestamp,
  setDoc,
  Timestamp,
  updateDoc,
  where,
  type Firestore,
  type Unsubscribe,
} from 'firebase/firestore'

import {
  CASE_ACTION_NEXT_STATUS,
  CaseActionType,
  CaseStatus,
} from '@/lib/incident-status'
import { getAreaCoordinates } from '@/lib/locations'
import {
  CrashCase,
  CrashCaseAction,
  CrashCaseLocation,
  CrashCaseMedia,
  CrashCaseTriggerStatus,
  DetectionResponse,
} from '@/lib/types'

function toIsoTimestamp(value: unknown): string {
  if (value instanceof Timestamp) {
    return value.toDate().toISOString()
  }

  if (typeof value === 'string') {
    return value
  }

  return new Date().toISOString()
}

function actionFromFirestore(raw: any): CrashCaseAction {
  return {
    action: raw?.action ?? 'review_alert',
    actorId: String(raw?.actorId ?? 'system'),
    timestamp: toIsoTimestamp(raw?.timestamp),
    notes: String(raw?.notes ?? ''),
    previousStatus: raw?.previousStatus ?? 'pending_review',
    nextStatus: raw?.nextStatus ?? 'pending_review',
  }
}

function nullableIsoTimestamp(value: unknown): string | null {
  if (value === undefined || value === null) return null
  return toIsoTimestamp(value)
}

function triggerStatusFromSource(source: CrashCaseMedia['source']): CrashCaseTriggerStatus {
  switch (source) {
    case 'camera-capture':
    case 'live-camera':
    case 'stream':
      return 'camera_detection'
    case 'upload':
      return 'upload_detection'
    case 'sample':
      return 'sample_detection'
    default:
      return 'unknown'
  }
}

function normalizeTriggerStatus(value: unknown): CrashCaseTriggerStatus {
  return value === 'camera_detection' ||
    value === 'upload_detection' ||
    value === 'sample_detection' ||
    value === 'manual_report' ||
    value === 'unknown'
    ? value
    : 'unknown'
}

export function crashCaseFromFirestore(id: string, data: any): CrashCase {
  const fallback = getAreaCoordinates(data?.areaId)
  const createdAt = toIsoTimestamp(data?.createdAt ?? data?.timestamp)
  return {
    caseId: String(data?.caseId ?? id),
    detectionId: String(data?.detectionId ?? id),
    status: data?.status ?? 'pending_review',
    reviewerId: data?.reviewerId ? String(data.reviewerId) : null,
    user: data?.user ?? null,
    vehicle: data?.vehicle ?? null,
    location: {
      label: String(data?.location?.label ?? data?.locationLabel ?? 'Fallback Demo Location'),
      latitude: Number(data?.location?.latitude ?? fallback.latitude),
      longitude: Number(data?.location?.longitude ?? fallback.longitude),
      areaId: data?.location?.areaId ?? data?.areaId ?? null,
      isFallback: Boolean(data?.location?.isFallback ?? fallback.isFallback),
    },
    media: {
      mediaType: data?.media?.mediaType ?? data?.media_type ?? 'image',
      source: data?.media?.source ?? data?.source ?? 'upload',
      sourceFile: data?.media?.sourceFile ?? data?.source_file ?? null,
      annotatedMediaUrl: data?.media?.annotatedMediaUrl ?? null,
      annotatedMediaDownloadUrl: data?.media?.annotatedMediaDownloadUrl ?? null,
      annotatedKeyFrameUrl: data?.media?.annotatedKeyFrameUrl ?? null,
    },
    confidence: Number(data?.confidence ?? 0),
    notes: String(data?.notes ?? ''),
    actions: Array.isArray(data?.actions)
      ? data.actions.map(actionFromFirestore)
      : [],
    acknowledgedAt: nullableIsoTimestamp(data?.acknowledgedAt),
    confirmedAt: nullableIsoTimestamp(data?.confirmedAt),
    createdAt,
    detectedAt: toIsoTimestamp(data?.detectedAt ?? data?.createdAt ?? data?.timestamp),
    dispatchedAt: nullableIsoTimestamp(data?.dispatchedAt),
    falseAlarmAt: nullableIsoTimestamp(data?.falseAlarmAt),
    resolvedAt: nullableIsoTimestamp(data?.resolvedAt),
    triggerStatus: normalizeTriggerStatus(data?.triggerStatus),
    updatedAt: toIsoTimestamp(data?.updatedAt ?? data?.timestamp),
    accidentDetected: Boolean(data?.accidentDetected ?? data?.accident_detected ?? true),
    detections: Array.isArray(data?.detections) ? data.detections : [],
  }
}

export function subscribeCrashCases(
  db: Firestore,
  onCases: (cases: CrashCase[]) => void,
  onError: (error: Error) => void,
  areaId?: string | null
): Unsubscribe {
  const casesQuery = areaId
    ? query(collection(db, 'incidents'), where('areaId', '==', areaId))
    : query(collection(db, 'incidents'), orderBy('updatedAt', 'desc'))
  return onSnapshot(
    casesQuery,
    (snapshot) => {
      const cases = snapshot.docs
        .map((caseDoc) => crashCaseFromFirestore(caseDoc.id, caseDoc.data()))
        .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
      onCases(cases)
    },
    onError
  )
}

export async function createCrashCaseFromDetection(
  db: Firestore,
  params: {
    result: DetectionResponse
    actorId: string
    areaId?: string | null
    source: CrashCaseMedia['source']
    sourceFile?: string | null
    locationLabel?: string | null
  }
): Promise<string | null> {
  if (!params.result.accident_detected) {
    return null
  }

  const detectionId = `DET-${crypto.randomUUID()}`
  const location = getAreaCoordinates(params.areaId)
  const locationPayload: CrashCaseLocation = {
    label:
      params.locationLabel ||
      params.result.location ||
      (location.isFallback ? 'Fallback Demo Location' : 'Detected Location'),
    latitude: location.latitude,
    longitude: location.longitude,
    areaId: params.areaId ?? null,
    isFallback: location.isFallback,
  }
  const nowIso = new Date().toISOString()
  const initialAction: CrashCaseAction = {
    action: 'review_alert',
    actorId: 'system',
    timestamp: nowIso,
    notes: 'Possible crash detected by YOLO. Awaiting responder review.',
    previousStatus: 'pending_review',
    nextStatus: 'pending_review',
  }

  const caseRef = await addDoc(collection(db, 'incidents'), {
    detectionId,
    status: 'pending_review',
    reviewerId: null,
    user: null,
    vehicle: null,
    location: locationPayload,
    areaId: params.areaId ?? null,
    triggerStatus: triggerStatusFromSource(params.source),
    media: {
      mediaType: params.result.media_type,
      source: params.source,
      sourceFile: params.sourceFile ?? null,
      annotatedMediaUrl: params.result.annotated_media_url ?? null,
      annotatedMediaDownloadUrl: params.result.annotated_media_download_url ?? null,
      annotatedKeyFrameUrl: params.result.annotated_key_frame_url ?? null,
    },
    confidence: params.result.confidence,
    notes: '',
    actions: [initialAction],
    createdAt: serverTimestamp(),
    detectedAt: nowIso,
    updatedAt: serverTimestamp(),
    acknowledgedAt: null,
    confirmedAt: null,
    falseAlarmAt: null,
    dispatchedAt: null,
    resolvedAt: null,
    accidentDetected: true,
    detections: params.result.detections,
  })

  await setDoc(caseRef, { caseId: caseRef.id }, { merge: true })
  await addDoc(collection(db, 'notifications'), {
    areaId: params.areaId ?? null,
    incident_id: caseRef.id,
    message: `Possible crash detected at ${locationPayload.label}. Responder review required.`,
    read: false,
    responderUid: params.actorId,
    alertLevel: 'review',
    timestamp: serverTimestamp(),
    title: 'Possible Crash Pending Review',
  })

  return caseRef.id
}

export async function getCrashCase(db: Firestore, caseId: string) {
  const snapshot = await getDoc(doc(db, 'incidents', caseId))
  if (!snapshot.exists()) return null
  return crashCaseFromFirestore(snapshot.id, snapshot.data())
}

export async function applyCrashCaseAction(
  db: Firestore,
  params: {
    caseItem: CrashCase
    action: CaseActionType
    actorId: string
    notes?: string
  }
) {
  const nextStatus = CASE_ACTION_NEXT_STATUS[params.action] ?? params.caseItem.status

  const allowedByAction: Record<CaseActionType, CaseStatus[]> = {
    review_alert: ['pending_review'],
    confirm_crash: ['under_review'],
    mark_false_alarm: ['under_review'],
    dispatch_help: ['confirmed_crash'],
    contact_user: ['pending_review', 'under_review', 'confirmed_crash', 'dispatched'],
    add_notes: ['pending_review', 'under_review', 'confirmed_crash', 'dispatched', 'false_alarm'],
    resolve_case: ['dispatched', 'false_alarm'],
  }

  if (!allowedByAction[params.action].includes(params.caseItem.status)) {
    throw new Error(
      `Cannot ${params.action.replaceAll('_', ' ')} while case is ${params.caseItem.status.replaceAll('_', ' ')}.`
    )
  }

  if (params.action === 'resolve_case' && !params.notes?.trim()) {
    throw new Error('Resolving a case requires notes.')
  }

  const actionTimestamp = new Date().toISOString()
  const timelineAction: CrashCaseAction = {
    action: params.action,
    actorId: params.actorId,
    timestamp: actionTimestamp,
    notes: params.notes?.trim() ?? '',
    previousStatus: params.caseItem.status,
    nextStatus,
  }

  const updatedNotes =
    params.action === 'add_notes' || params.action === 'resolve_case'
      ? [params.caseItem.notes, params.notes?.trim()].filter(Boolean).join('\n')
      : params.caseItem.notes

  const timestampUpdate: Partial<Record<
    'acknowledgedAt' | 'confirmedAt' | 'falseAlarmAt' | 'dispatchedAt' | 'resolvedAt',
    string
  >> = {}

  if (params.action === 'review_alert') timestampUpdate.acknowledgedAt = actionTimestamp
  if (params.action === 'confirm_crash') timestampUpdate.confirmedAt = actionTimestamp
  if (params.action === 'mark_false_alarm') timestampUpdate.falseAlarmAt = actionTimestamp
  if (params.action === 'dispatch_help') timestampUpdate.dispatchedAt = actionTimestamp
  if (params.action === 'resolve_case') timestampUpdate.resolvedAt = actionTimestamp

  await updateDoc(doc(db, 'incidents', params.caseItem.caseId), {
    status: nextStatus,
    reviewerId: params.actorId,
    notes: updatedNotes,
    actions: [...params.caseItem.actions, timelineAction],
    ...timestampUpdate,
    updatedAt: serverTimestamp(),
  })
}

export async function applyMapReviewDecision(
  db: Firestore,
  params: {
    caseItem: CrashCase
    decision: 'legit_crash' | 'false_alarm'
    actorId: string
    notes?: string
  }
) {
  if (
    params.caseItem.status !== 'pending_review' &&
    params.caseItem.status !== 'under_review'
  ) {
    throw new Error(
      `Cannot decide while case is ${params.caseItem.status.replaceAll('_', ' ')}.`
    )
  }

  const actionTimestamp = new Date().toISOString()
  const actions: CrashCaseAction[] = []

  if (params.caseItem.status === 'pending_review') {
    actions.push({
      action: 'review_alert',
      actorId: params.actorId,
      timestamp: actionTimestamp,
      notes: 'Responder opened the map evidence review.',
      previousStatus: 'pending_review',
      nextStatus: 'under_review',
    })
  }

  const finalAction: CaseActionType =
    params.decision === 'legit_crash' ? 'confirm_crash' : 'mark_false_alarm'
  const nextStatus: CaseStatus =
    params.decision === 'legit_crash' ? 'confirmed_crash' : 'false_alarm'

  actions.push({
    action: finalAction,
    actorId: params.actorId,
    timestamp: actionTimestamp,
    notes: params.notes?.trim() ?? 'Map evidence review decision.',
    previousStatus: params.caseItem.status === 'pending_review' ? 'under_review' : 'under_review',
    nextStatus,
  })

  await updateDoc(doc(db, 'incidents', params.caseItem.caseId), {
    status: nextStatus,
    reviewerId: params.actorId,
    actions: [...params.caseItem.actions, ...actions],
    acknowledgedAt:
      params.caseItem.acknowledgedAt ??
      (params.caseItem.status === 'pending_review' ? actionTimestamp : null),
    confirmedAt:
      params.decision === 'legit_crash' ? actionTimestamp : params.caseItem.confirmedAt,
    falseAlarmAt:
      params.decision === 'false_alarm' ? actionTimestamp : params.caseItem.falseAlarmAt,
    updatedAt: serverTimestamp(),
  })
}

export function summarizeCaseCounts(cases: CrashCase[]) {
  const today = new Date().toDateString()
  return {
    pendingReview: cases.filter(
      (c) => c.status === 'pending_review'
    ).length,
    underReview: cases.filter((c) => c.status === 'under_review').length,
    confirmedCrashes: cases.filter((c) => c.status === 'confirmed_crash').length,
    dispatchedCases: cases.filter((c) => c.status === 'dispatched').length,
    falseAlarms: cases.filter((c) => c.status === 'false_alarm').length,
    resolvedToday: cases.filter(
      (c) => c.status === 'resolved' && new Date(c.updatedAt).toDateString() === today
    ).length,
  }
}
