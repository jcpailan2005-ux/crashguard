'use client'

import { useState } from 'react'
import { resolveBackendMediaUrl } from '@/lib/api-client'
import { incidentEvidence } from '@/lib/incident-evidence'
import type { OperationalIncident } from '@/lib/phase3-api'

export function OperationalIncidentEvidence({ incident }: { incident: OperationalIncident }) {
  const evidence = incidentEvidence(incident)
  const [loaded, setLoaded] = useState<string | null>(null)
  const [failedRaw, setFailedRaw] = useState<string | null>(null)
  const raw = resolveBackendMediaUrl(evidence.rawUrl)
  const annotated = resolveBackendMediaUrl(evidence.annotatedUrl)
  const src = raw && failedRaw !== raw && evidence.width > 0 && evidence.height > 0 ? raw : annotated ?? raw
  if (!src) return <p className="text-xs text-muted-foreground">No saved incident evidence available.</p>
  const boxes = src === raw && src !== annotated && loaded === src ? evidence.boxes : []
  return (
    <figure className="space-y-2" aria-label="Saved incident evidence">
      <div className="relative w-full overflow-hidden rounded-md bg-black"
        style={{ aspectRatio: evidence.width && evidence.height ? `${evidence.width}/${evidence.height}` : '16/9' }}>
        <img key={src} src={src} alt="Exact analyzed incident evidence frame"
          className="absolute inset-0 h-full w-full object-contain"
          onLoad={(event) => setLoaded(event.currentTarget.naturalWidth === evidence.width &&
            event.currentTarget.naturalHeight === evidence.height ? src : null)}
          onError={() => { setLoaded(null); if (src === raw) setFailedRaw(raw) }} />
        {boxes.length ? <svg className="pointer-events-none absolute inset-0 h-full w-full"
          viewBox={`0 0 ${evidence.width} ${evidence.height}`} preserveAspectRatio="xMidYMid meet"
          aria-label="Saved vehicle bounding boxes">
          {boxes.map((box, index) => <g key={`${box.trackId ?? index}-${index}`}>
            <rect x={box.x} y={box.y} width={box.width} height={box.height}
              stroke="#22c55e" strokeWidth="2" vectorEffect="non-scaling-stroke" fill="none" />
            <text x={box.x} y={Math.max(16, box.y - 5)} fill="#22c55e" fontSize="16"
              stroke="black" strokeWidth="0.5" paintOrder="stroke">
              {box.label} {Math.round(box.confidence * 100)}%{box.trackId != null ? ` #${box.trackId}` : ''}
            </text>
          </g>)}
        </svg> : null}
      </div>
      <figcaption className="text-xs text-muted-foreground">Saved analyzed evidence{evidence.sourceFrame ? ` · Frame ${evidence.sourceFrame.sequence}` : ''}</figcaption>
    </figure>
  )
}
