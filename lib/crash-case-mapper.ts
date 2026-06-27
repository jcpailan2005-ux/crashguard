'use client'

import { resolveBackendMediaUrl } from '@/lib/api-client'
import { CrashCase, CrashCaseMedia, CrashCaseTriggerStatus, LocalCrashCase } from '@/lib/types'

function normalizeTriggerStatus(value: LocalCrashCase['triggerStatus']): CrashCaseTriggerStatus {
  return value === 'camera_detection' ||
    value === 'upload_detection' ||
    value === 'sample_detection' ||
    value === 'manual_report' ||
    value === 'unknown'
    ? value
    : 'unknown'
}

function sourceFromLocalCase(caseItem: LocalCrashCase): CrashCaseMedia['source'] {
  if (caseItem.triggerStatus === 'camera_detection') return 'live-camera'
  if (caseItem.triggerStatus === 'sample_detection') return 'sample'
  return 'upload'
}

function resolved(path?: string | null) {
  return resolveBackendMediaUrl(path)
}

export function localCaseToCrashCase(caseItem: LocalCrashCase): CrashCase {
  const annotatedUrl = resolved(caseItem.annotatedPath)
  const keyFrameUrl = resolved(caseItem.keyFramePath)
  const thumbnailUrl = resolved(caseItem.thumbnailPath)
  const videoUrl = resolved(caseItem.videoPath)

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
          ? `${caseItem.barangay} - ${caseItem.roadName}`
          : caseItem.location ?? caseItem.cameraName ?? caseItem.sourceCamera ?? 'Local crash case',
      latitude: caseItem.latitude ?? 7.1907,
      longitude: caseItem.longitude ?? 125.4553,
      areaId: caseItem.areaId ?? null,
      isFallback: caseItem.latitude == null || caseItem.longitude == null,
    },
    media: {
      mediaType: caseItem.videoPath ? 'video' : 'image',
      source: sourceFromLocalCase(caseItem),
      sourceFile: caseItem.cameraName ?? caseItem.sourceCamera ?? null,
      annotatedKeyFrameUrl: annotatedUrl ?? keyFrameUrl ?? thumbnailUrl,
      keyFrameUrl,
      thumbnailUrl,
      videoUrl,
      annotatedMediaUrl: annotatedUrl ?? videoUrl,
      annotatedMediaDownloadUrl: videoUrl ?? annotatedUrl,
    },
    confidence: caseItem.confidence,
    notes: caseItem.notes ?? '',
    actions: caseItem.actions ?? [],
    acknowledgedAt: caseItem.reviewedAt ?? null,
    confirmedAt: caseItem.confirmedAt ?? null,
    createdAt: caseItem.createdAt ?? caseItem.detectedAt,
    detectedAt: caseItem.detectedAt,
    dispatchedAt: caseItem.dispatchedAt ?? null,
    falseAlarmAt: caseItem.falseAlarmAt ?? null,
    resolvedAt: caseItem.resolvedAt ?? null,
    triggerStatus: normalizeTriggerStatus(caseItem.triggerStatus),
    updatedAt: caseItem.updatedAt,
    accidentDetected: caseItem.accidentDetected,
    detections: caseItem.detections ?? [],
    boxes: caseItem.boxes ?? [],
    notificationId: caseItem.notificationId ?? null,
    videoPath: caseItem.videoPath ?? null,
    keyFramePath: caseItem.keyFramePath ?? null,
    thumbnailPath: caseItem.thumbnailPath ?? null,
    annotatedPath: caseItem.annotatedPath ?? null,
    sourceCamera: caseItem.sourceCamera ?? null,
    cameraName: caseItem.cameraName ?? null,
    cameraId: caseItem.cameraId ?? null,
    cameraIp: caseItem.cameraIp ?? null,
  }
}

export function caseMedia(caseItem: CrashCase | null) {
  if (!caseItem) {
    return {
      previewUrl: null,
      fullUrl: null,
      mediaType: 'image' as const,
      rawPreviewPath: null,
      hasMediaPath: false,
    }
  }

  const previewPath =
    caseItem.media.annotatedKeyFrameUrl ||
    caseItem.annotatedPath ||
    caseItem.media.keyFrameUrl ||
    caseItem.keyFramePath ||
    caseItem.thumbnailPath ||
    caseItem.videoPath ||
    caseItem.media.annotatedMediaUrl ||
    null
  const fullPath =
    caseItem.media.videoUrl ||
    caseItem.videoPath ||
    caseItem.media.annotatedMediaUrl ||
    caseItem.annotatedPath ||
    caseItem.media.annotatedMediaDownloadUrl ||
    caseItem.media.annotatedKeyFrameUrl ||
    caseItem.media.keyFrameUrl ||
    caseItem.keyFramePath ||
    null

  return {
    previewUrl: resolveBackendMediaUrl(previewPath),
    fullUrl: resolveBackendMediaUrl(fullPath),
    mediaType:
      caseItem.media.mediaType === 'video' && previewPath === (caseItem.media.videoUrl || caseItem.videoPath)
        ? 'video' as const
        : 'image' as const,
    rawPreviewPath: previewPath,
    hasMediaPath: Boolean(previewPath),
  }
}
