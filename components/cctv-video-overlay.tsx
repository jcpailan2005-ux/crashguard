'use client'

import { ReactNode, useEffect, useMemo, useRef, useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { DetectionBox, LiveBoxView } from '@/lib/types'
import { subscribeCameraBoxes } from '@/lib/api-client'
import {
  clipAnalysisBoxes,
  FRESHNESS_LIMIT_MS,
  fitMediaRect,
  formatFrameAge,
  VISUAL_RETENTION_LIMIT_MS,
} from '@/lib/camera-analysis-view'

export { clipAnalysisBoxes, fitMediaRect, formatFrameAge, FRESHNESS_LIMIT_MS, VISUAL_RETENTION_LIMIT_MS }

function AnalyzedFrame({ view }: { view: LiveBoxView }) {
  const [loaded, setLoaded] = useState(false)
  const [, setTick] = useState(false)
  const [isExpanded, setIsExpanded] = useState(false)

  useEffect(() => {
    const timer = setInterval(() => setTick((prev) => !prev), 100)
    return () => clearInterval(timer)
  }, [])

  const now = performance.now()
  const { packet } = view
  const frame = packet.sourceFrame
  const width = frame.width!, height = frame.height!
  const boxes = clipAnalysisBoxes(packet.boxes, width, height)

  const receivedAt = view.receivedAt ?? (view.expiresAt - FRESHNESS_LIMIT_MS)
  const retentionExpiresAt = view.retentionExpiresAt ?? (receivedAt + VISUAL_RETENTION_LIMIT_MS)
  if (now >= retentionExpiresAt) {
    return (
      <p className="text-xs text-muted-foreground">
        Waiting for a fresh analyzed frame. Live video continues above.
      </p>
    )
  }

  const isFresh = now < view.expiresAt
  const elapsedSinceDelivery = Math.max(0, now - receivedAt)
  const currentAgeMs =
    packet.sourceAgeMs != null
      ? packet.sourceAgeMs + elapsedSinceDelivery
      : packet.resultAgeMs != null
        ? packet.resultAgeMs + elapsedSinceDelivery
        : null
  const ageDisplay = formatFrameAge(currentAgeMs)
  const isRetained = now < retentionExpiresAt

  const statusLabel =
    boxes.length === 0
      ? isFresh
        ? 'FRESH — NO VEHICLES ACCEPTED'
        : 'STALE — NO VEHICLES ACCEPTED'
      : isFresh
        ? 'FRESH'
        : 'STALE'

  const vehicleSummary =
    boxes.length === 0
      ? 'NO VEHICLES ACCEPTED'
      : boxes
          .map((box) => {
            const conf =
              Number.isFinite(box.confidence) && box.confidence > 0
                ? Math.max(0, Math.min(1, box.confidence))
                : null
            return (
              (box.label || 'detection').replace(/^\w/, (c) => c.toUpperCase()) +
              (conf != null ? ` ${(conf * 100).toFixed(0)}%` : '')
            )
          })
          .join(' • ')

  return (
    <div className="space-y-2">
      <div className="flex flex-col gap-1 text-xs">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <Badge
              variant={isFresh ? 'default' : 'outline'}
              className={
                isFresh
                  ? 'bg-emerald-600 hover:bg-emerald-600 text-white font-semibold text-[10px] tracking-wider uppercase'
                  : 'border-amber-500 bg-amber-500/15 text-amber-500 font-semibold text-[10px] tracking-wider uppercase'
              }
            >
              {isFresh ? 'FRESH' : 'STALE'}
            </Badge>
            <span className="font-semibold text-foreground">
              {statusLabel} • {ageDisplay}
            </span>
            {boxes.length > 0 && (
              <span className="font-medium text-foreground/80">
                {vehicleSummary}
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={() => setIsExpanded((prev) => !prev)}
            className="text-[11px] font-medium text-primary hover:underline cursor-pointer"
          >
            {isExpanded ? 'Collapse view' : 'Expand view'}
          </button>
        </div>
        <div className="flex items-center justify-between text-[11px] font-mono text-muted-foreground">
          <span>
            Frame {frame.sequence} · captured {frame.capturedAt ? new Date(frame.capturedAt * 1000).toLocaleTimeString() : 'unknown'}
          </span>
          <span className="text-[10px] text-muted-foreground/80">
            {isExpanded ? 'Expanded inspection (click thumbnail to collapse)' : 'Compact thumbnail (click to expand)'}
          </span>
        </div>
      </div>

      <div
        className={`relative overflow-hidden bg-black rounded border border-border/40 shadow-sm transition-all cursor-pointer ${
          isExpanded ? 'w-full max-w-2xl' : 'w-full max-w-[280px]'
        }`}
        style={{ aspectRatio: `${width}/${height}` }}
        onClick={() => setIsExpanded((prev) => !prev)}
        title={isExpanded ? 'Click to collapse thumbnail' : 'Click to expand thumbnail'}
      >
        <img
          src={packet.imageDataUrl}
          alt={`Analyzed camera frame ${frame.sequence}`}
          className="block h-full w-full object-contain"
          onLoad={(event) =>
            setLoaded(
              event.currentTarget.naturalWidth === width &&
              event.currentTarget.naturalHeight === height &&
              performance.now() < retentionExpiresAt
            )
          }
          onError={() => setLoaded(false)}
        />
        {loaded && isRetained && (
          <svg
            className="pointer-events-none absolute inset-0 h-full w-full"
            viewBox={`0 0 ${width} ${height}`}
            preserveAspectRatio="xMidYMid meet"
            aria-label="Vehicle boxes for analyzed frame"
          >
            {boxes.map((box, index) => {
              const conf =
                Number.isFinite(box.confidence) && box.confidence > 0
                  ? Math.max(0, Math.min(1, box.confidence))
                  : null
              const labelText =
                (box.label || 'detection').replace(/^\w/, (c) => c.toUpperCase()) +
                (conf != null ? ` ${(conf * 100).toFixed(0)}%` : '')
              return (
                <g key={index}>
                  <rect
                    x={box.x}
                    y={box.y}
                    width={box.width}
                    height={box.height}
                    fill="none"
                    stroke="#ef4444"
                    strokeWidth="2"
                    vectorEffect="non-scaling-stroke"
                  />
                  <rect
                    x={box.x}
                    y={box.y - 18}
                    width={labelText.length * 7.5 + 8}
                    height={18}
                    rx="2"
                    fill="#dc2626"
                  />
                  <text
                    x={box.x + 4}
                    y={box.y - 4}
                    fill="#fff"
                    fontSize="12"
                    fontFamily="system-ui, sans-serif"
                    fontWeight="600"
                  >
                    {labelText}
                  </text>
                </g>
              )
            })}
          </svg>
        )}
      </div>
    </div>
  )
}

export function SynchronizedAnalysisPreview({
  cameraId,
  eventsUrl,
  retentionMs = VISUAL_RETENTION_LIMIT_MS,
}: {
  cameraId: string
  eventsUrl: string | null
  retentionMs?: number
}) {
  const [view, setView] = useState<LiveBoxView | null>(null)

  useEffect(() => {
    setView(null)
    return subscribeCameraBoxes(cameraId, eventsUrl, (incoming) => {
      if (!incoming) {
        // The backend exposes exact packets for a short freshness window.
        // Keep the last exact image+boxes until its visual retention deadline
        // instead of flashing back to an empty state between analyses.
        return
      }
      const receivedAt = performance.now()
      const remainingRetention = Math.max(100, retentionMs - (incoming.packet.resultAgeMs || 0))
      const retentionExpiresAt = incoming.retentionExpiresAt ?? (receivedAt + remainingRetention)
      setView({
        ...incoming,
        receivedAt,
        retentionExpiresAt,
      })
    })
  }, [cameraId, eventsUrl, retentionMs])

  useEffect(() => {
    if (!view) return
    const retentionExpiresAt =
      view.retentionExpiresAt ??
      ((view.receivedAt ?? (view.expiresAt - FRESHNESS_LIMIT_MS)) + retentionMs)
    const delay = Math.max(0, retentionExpiresAt - performance.now())
    const timer = setTimeout(() => {
      setView(null)
    }, delay)
    return () => clearTimeout(timer)
  }, [view, retentionMs])

  const isVisible =
    view != null &&
    performance.now() <
      (view.retentionExpiresAt ??
        ((view.receivedAt ?? (view.expiresAt - FRESHNESS_LIMIT_MS)) + retentionMs))

  const now = typeof performance === 'undefined' ? 0 : performance.now()
  const packet = view && isVisible ? view.packet : null
  const boxes = packet
    ? clipAnalysisBoxes(packet.boxes, packet.sourceFrame.width ?? 0, packet.sourceFrame.height ?? 0)
    : []
  const receivedAt = view?.receivedAt ?? now
  const ageMs = packet
    ? (packet.sourceAgeMs ?? packet.resultAgeMs) + Math.max(0, now - receivedAt)
    : null
  const isFresh = Boolean(view && now < view.expiresAt)

  return (
    <div className="flex flex-wrap items-center gap-2 border-t px-3 py-2 text-xs" aria-label="Compact analyzed camera status">
      <span className="font-medium">Latest analysis</span>
      <Badge variant={isFresh ? 'default' : 'outline'}>{packet ? (isFresh ? 'FRESH' : 'STALE') : 'WAITING'}</Badge>
      <span className="text-muted-foreground">
        {packet
          ? `${boxes.length} ${boxes.length === 1 ? 'vehicle' : 'vehicles'} · ${formatFrameAge(ageMs)}`
          : 'Waiting for an analyzed frame'}
      </span>
      <span className="ml-auto text-muted-foreground">Open Detection View for full frames and boxes.</span>
    </div>
  )
}

export function CameraTileDetectionView({
  cameraId,
  fallbackImageUrl,
  enabled = true,
}: {
  cameraId: string
  fallbackImageUrl?: string | null
  enabled?: boolean
}) {
  const [view, setView] = useState<LiveBoxView | null>(null)
  const [loadedFrameKey, setLoadedFrameKey] = useState<string | null>(null)
  const [, setTick] = useState(false)

  useEffect(() => {
    if (!enabled) {
      setView(null)
      return
    }
    return subscribeCameraBoxes(cameraId, null, (incoming) => {
      if (incoming?.packet.sourceFrame.cameraId === cameraId) {
        setView(incoming)
      }
    })
  }, [cameraId, enabled])

  useEffect(() => {
    if (!view) return
    const expiresAt = view.retentionExpiresAt ?? performance.now()
    const timer = window.setTimeout(() => setView(null), Math.max(0, expiresAt - performance.now()))
    return () => window.clearTimeout(timer)
  }, [view])

  useEffect(() => {
    if (!view) return
    const timer = window.setInterval(() => setTick((value) => !value), 250)
    return () => window.clearInterval(timer)
  }, [view])

  const now = typeof performance === 'undefined' ? 0 : performance.now()
  const visible = Boolean(view && now < (view.retentionExpiresAt ?? 0))
  const packet = visible ? view!.packet : null
  const packetKey = packet
    ? `${packet.sourceFrame.cameraId}:${packet.sourceFrame.sessionId}:${packet.sourceFrame.sequence}`
    : null
  const width = packet?.sourceFrame.width ?? 0
  const height = packet?.sourceFrame.height ?? 0
  const boxes = packet ? clipAnalysisBoxes(packet.boxes, width, height) : []
  const receivedAt = view?.receivedAt ?? now
  const ageMs = packet
    ? (packet.sourceAgeMs ?? packet.resultAgeMs) + Math.max(0, now - receivedAt)
    : null

  return (
    <div className="relative aspect-video overflow-hidden bg-zinc-950" aria-label={`Detection view for ${cameraId}`}>
      {packet ? (
        <>
          <img
            key={packetKey}
            src={packet.imageDataUrl}
            alt="Exact analyzed camera frame"
            className="h-full w-full object-contain"
            onLoad={(event) => setLoadedFrameKey(
              event.currentTarget.naturalWidth === width && event.currentTarget.naturalHeight === height
                ? packetKey
                : null
            )}
            onError={() => setLoadedFrameKey(null)}
          />
          {loadedFrameKey === packetKey ? <svg
            className="pointer-events-none absolute inset-0 h-full w-full"
            viewBox={`0 0 ${width} ${height}`}
            preserveAspectRatio="xMidYMid meet"
            aria-label="Synchronized vehicle detection boxes"
          >
            {boxes.map((box, index) => {
              const confidence = Math.max(0, Math.min(1, box.confidence || 0))
              const label = `${(box.label || 'Vehicle').replace(/^\w/, (letter) => letter.toUpperCase())} ${Math.round(confidence * 100)}%`
              const labelY = Math.max(0, box.y - 22)
              return <g key={`${box.label}-${index}`}>
                <rect x={box.x} y={box.y} width={box.width} height={box.height}
                  fill="none" stroke="#22c55e" strokeWidth="3" vectorEffect="non-scaling-stroke" />
                <rect x={box.x} y={labelY} width={Math.max(74, label.length * 8 + 12)} height="22"
                  rx="3" fill="#15803d" opacity="0.96" />
                <text x={box.x + 6} y={labelY + 15} fill="white" fontSize="13"
                  fontFamily="system-ui, sans-serif" fontWeight="700">{label}</text>
              </g>
            })}
          </svg> : null}
          <div className="absolute bottom-2 left-2 flex flex-wrap gap-1.5">
            <Badge className="bg-black/80 text-white hover:bg-black/80">
              {boxes.length} {boxes.length === 1 ? 'vehicle' : 'vehicles'}
            </Badge>
            <Badge className="bg-black/80 text-white hover:bg-black/80">
              Analysis {formatFrameAge(ageMs)}
            </Badge>
          </div>
        </>
      ) : fallbackImageUrl ? (
        <>
          <img src={fallbackImageUrl} alt="Live camera preview" className="h-full w-full object-contain" />
          <div className="absolute bottom-2 left-2 rounded bg-black/80 px-2 py-1 text-xs font-medium text-white">
            {enabled ? 'Waiting for analyzed frame' : 'Detections hidden'}
          </div>
        </>
      ) : (
        <div className="flex h-full items-center justify-center px-4 text-center text-xs text-zinc-400">
          Camera preview unavailable
        </div>
      )}
    </div>
  )
}

interface CctvVideoOverlayProps {
  annotatedPreviewUrl?: string | null
  boxes?: DetectionBox[]
  boxFit?: 'contain' | 'cover'
  children: ReactNode
  emptyDetectionLabel?: string
  isDetecting: boolean
  isLive: boolean
  labels: string[]
  sourceHeight?: number | null
  sourceWidth?: number | null
  timestamp: string
}

type ContainerSize = {
  width: number
  height: number
}

function getBoxBounds(boxes: DetectionBox[]) {
  return boxes.reduce(
    (bounds, box) => ({
      width: Math.max(bounds.width, box.x + box.width),
      height: Math.max(bounds.height, box.y + box.height),
    }),
    { width: 0, height: 0 }
  )
}

export function CctvVideoOverlay({
  annotatedPreviewUrl,
  boxes = [],
  boxFit = 'contain',
  children,
  emptyDetectionLabel = 'No verified collision in current frame',
  isDetecting,
  isLive,
  labels,
  sourceHeight,
  sourceWidth,
  timestamp,
}: CctvVideoOverlayProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [containerSize, setContainerSize] = useState<ContainerSize>({
    width: 0,
    height: 0,
  })

  useEffect(() => {
    const element = containerRef.current
    if (!element) {
      return
    }

    const updateSize = () => {
      setContainerSize({
        width: element.clientWidth,
        height: element.clientHeight,
      })
    }

    updateSize()

    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', updateSize)
      return () => window.removeEventListener('resize', updateSize)
    }

    const observer = new ResizeObserver(updateSize)
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  const visibleBoxes = useMemo(
    () =>
      boxes.filter(
        (box) =>
          Number.isFinite(box.x) &&
          Number.isFinite(box.y) &&
          Number.isFinite(box.width) &&
          Number.isFinite(box.height) &&
          box.width > 0 &&
          box.height > 0
      ),
    [boxes]
  )

  const boxBounds = useMemo(() => getBoxBounds(visibleBoxes), [visibleBoxes])
  const hasNormalizedBoxes =
    visibleBoxes.length > 0 &&
    visibleBoxes.every((box) => box.x + box.width <= 1.01 && box.y + box.height <= 1.01)
  const resolvedSourceWidth =
    sourceWidth && sourceWidth > 0
      ? sourceWidth
      : hasNormalizedBoxes
        ? 1
        : boxBounds.width
  const resolvedSourceHeight =
    sourceHeight && sourceHeight > 0
      ? sourceHeight
      : hasNormalizedBoxes
        ? 1
        : boxBounds.height

  const mediaRect = useMemo(() => fitMediaRect(
    resolvedSourceWidth, resolvedSourceHeight, containerSize.width, containerSize.height, boxFit
  ), [boxFit, containerSize.height, containerSize.width, resolvedSourceHeight, resolvedSourceWidth])

  return (
    <div
      ref={containerRef}
      className="relative aspect-video overflow-hidden bg-[var(--media-background)]"
    >
      {children}

      {mediaRect && visibleBoxes.length > 0 && (
        <div
          className="pointer-events-none absolute"
          style={{
            height: mediaRect.height,
            left: mediaRect.left,
            top: mediaRect.top,
            width: mediaRect.width,
          }}
        >
          {visibleBoxes.map((box, index) => {
            const left = (box.x / resolvedSourceWidth) * 100
            const top = (box.y / resolvedSourceHeight) * 100
            const width = (box.width / resolvedSourceWidth) * 100
            const height = (box.height / resolvedSourceHeight) * 100
            const confidence = Number.isFinite(box.confidence)
              ? Math.max(0, Math.min(1, box.confidence))
              : null

            return (
              <div
                key={`${box.label}-${box.x}-${box.y}-${index}`}
                className="absolute rounded-sm border-2 border-red-500 bg-red-500/10 shadow-[0_0_0_1px_rgba(0,0,0,0.35)]"
                style={{
                  height: `${height}%`,
                  left: `${left}%`,
                  top: `${top}%`,
                  width: `${width}%`,
                }}
              >
                <div className="absolute left-0 top-0 max-w-full -translate-y-full rounded-sm bg-red-600 px-1.5 py-0.5 text-[10px] font-semibold leading-none text-white shadow-sm">
                  <span className="block truncate capitalize">
                    {box.label || 'detection'}
                    {confidence != null ? ` ${(confidence * 100).toFixed(0)}%` : ''}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      )}

      <div className="pointer-events-none absolute left-4 top-4 rounded-md border border-[var(--media-border)] bg-[color:var(--media-overlay)] px-3 py-2 text-xs font-mono text-[var(--media-foreground)] shadow-lg backdrop-blur-sm">
        {timestamp}
      </div>

      <div className="pointer-events-none absolute right-4 top-4 flex items-center gap-2">
        {isLive && (
          <Badge className="border-[var(--status-live)] bg-[color:var(--status-live-bg)] text-[var(--status-live)] hover:bg-[color:var(--status-live-bg)]">
            LIVE
          </Badge>
        )}
        {isDetecting && (
          <Badge className="bg-primary/90 text-primary-foreground hover:bg-primary/90">
            SCANNING
          </Badge>
        )}
      </div>

      {labels.length > 0 && (
        <div className="pointer-events-none absolute bottom-4 left-4 flex max-w-[60%] flex-wrap gap-2">
          {labels.slice(0, 4).map((label, index) => (
            <Badge
              key={`${label}-${index}`}
              variant="outline"
              className="border-[var(--media-border)] bg-[color:var(--media-overlay)] capitalize text-[var(--media-foreground)]"
            >
              {label}
            </Badge>
          ))}
        </div>
      )}

      {isDetecting && labels.length === 0 && (
        <div className="pointer-events-none absolute bottom-4 left-4">
          <Badge
            variant="outline"
            className="border-[var(--media-border)] bg-[color:var(--media-overlay)] text-[var(--media-foreground)]"
          >
            {emptyDetectionLabel}
          </Badge>
        </div>
      )}

      {annotatedPreviewUrl && (
        <div className="pointer-events-none absolute bottom-4 right-4 h-28 w-44 overflow-hidden rounded-lg border border-[var(--media-border)] bg-[color:var(--media-overlay)] shadow-xl backdrop-blur-sm sm:h-32 sm:w-52">
          <img
            src={annotatedPreviewUrl}
            alt="Latest annotated detection preview"
            className="h-full w-full object-cover"
          />
        </div>
      )}
    </div>
  )
}
