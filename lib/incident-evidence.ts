import type { OperationalIncident } from './phase3-api'
import type { DetectionBox, LiveFrameIdentity } from './types'
import { clipAnalysisBoxes } from './camera-analysis-view.ts'

/** Read saved evidence only. Never fetch a camera frame or run inference. */
export function incidentEvidence(incident: Pick<OperationalIncident, 'media' | 'evidenceSummary'>) {
  const media = incident.media ?? {}
  const evidence = incident.evidenceSummary ?? {}
  const sourceFrame = evidence.sourceFrame as LiveFrameIdentity | undefined
  const width = sourceFrame?.width ?? 0
  const height = sourceFrame?.height ?? 0
  const rawUrl = typeof media.keyFramePath === 'string' ? media.keyFramePath : null
  const annotatedUrl = typeof media.annotatedPath === 'string' ? media.annotatedPath : null
  const boxes = Array.isArray(evidence.boxes) && width > 0 && height > 0
    ? clipAnalysisBoxes((evidence.boxes as DetectionBox[]).filter((box) =>
      (!box.sessionId || box.sessionId === sourceFrame?.sessionId) &&
      (!box.cameraId || box.cameraId === sourceFrame?.cameraId) &&
      (box.sequence == null || box.sequence === sourceFrame?.sequence) &&
      box.observationKind !== 'PREDICTED'), width, height)
    : []
  return { rawUrl, annotatedUrl, sourceFrame, width, height, boxes }
}
