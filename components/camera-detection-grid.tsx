'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Camera, Eye, EyeOff, Maximize2, RefreshCw } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  cameraDetectionGridClass,
  clipAnalysisBoxes,
  formatCompactFrameAge,
} from '@/lib/camera-analysis-view'
import {
  type CameraMonitoringStatus,
  getCameraMonitoringStatus,
  getCctvCameras,
  subscribeCameraBoxes,
} from '@/lib/api-client'
import type { CctvCamera, LiveBoxView } from '@/lib/types'

type CameraFilter = 'all' | 'cctv' | 'usb'

function cameraName(camera: CctvCamera) {
  return camera.label?.trim() || camera.name?.trim() || 'Camera'
}

function cameraSourceType(camera: CctvCamera): 'CCTV' | 'USB' {
  const value = `${camera.cameraType ?? ''} ${camera.streamSourceLabel ?? ''}`.toLowerCase()
  return value.includes('webcam') || value.includes('usb') ? 'USB' : 'CCTV'
}

function cameraHealth(camera: CctvCamera, status?: CameraMonitoringStatus) {
  if (!camera.isActive || status?.cameraHealth === 'DISABLED') return 'OFFLINE'
  if (status?.reconnecting || status?.status === 'reconnecting') return 'RECONNECTING'
  if (status?.cameraHealth === 'STALE') return 'RECONNECTING'
  if (status?.cameraHealth === 'LIVE' || status?.cameraHealth === 'ONLINE' || status?.monitoringLive) return 'LIVE'
  if (status?.lastError || status?.status === 'connection-lost' || status?.status === 'disconnected') return 'OFFLINE'
  return 'OFFLINE'
}

function collisionStatus(status?: CameraMonitoringStatus) {
  const result = status?.latestResult
  if (result?.finalDecision === 'confirmed_crash' && (result.incidentCreated || result.incident_created)) {
    return 'INCIDENT SENT'
  }
  if (result?.finalDecision === 'confirmed_crash') return 'CONFIRMED CRASH'
  if (
    result?.finalDecision === 'candidate' ||
    result?.aftermathSuspected ||
    (result?.consecutiveCrashHits ?? 0) > 0
  ) {
    return 'ANALYZING POTENTIAL COLLISION'
  }
  return 'MONITORING'
}

function healthVariant(health: string): 'default' | 'secondary' | 'outline' | 'destructive' {
  if (health === 'LIVE') return 'default'
  if (health === 'RECONNECTING') return 'secondary'
  if (health === 'OFFLINE') return 'destructive'
  return 'outline'
}

function useCameraAnalysis(cameraId: string) {
  const [view, setView] = useState<LiveBoxView | null>(null)
  const [, setClock] = useState(false)

  useEffect(() => {
    setView(null)
    return subscribeCameraBoxes(cameraId, null, (incoming) => {
      if (incoming?.packet.sourceFrame.cameraId === cameraId) setView(incoming)
    })
  }, [cameraId])

  useEffect(() => {
    if (!view) return
    const expiresAt = view.retentionExpiresAt ?? performance.now()
    const timeout = window.setTimeout(() => setView(null), Math.max(0, expiresAt - performance.now()))
    const clock = window.setInterval(() => setClock((value) => !value), 250)
    return () => {
      window.clearTimeout(timeout)
      window.clearInterval(clock)
    }
  }, [view])

  return view
}

function ExactDetectionFrame({
  cameraId,
  view,
  showDetections,
  expanded = false,
}: {
  cameraId: string
  view: LiveBoxView | null
  showDetections: boolean
  expanded?: boolean
}) {
  const [loadedFrameKey, setLoadedFrameKey] = useState<string | null>(null)
  const now = typeof performance === 'undefined' ? 0 : performance.now()
  const visible = Boolean(view && now < (view.retentionExpiresAt ?? 0))
  const packet = visible ? view!.packet : null
  const frame = packet?.sourceFrame
  const width = frame?.width ?? 0
  const height = frame?.height ?? 0
  const packetKey = packet
    ? `${frame!.cameraId}:${frame!.sessionId}:${frame!.sequence}`
    : null
  const boxes = packet ? clipAnalysisBoxes(packet.boxes, width, height) : []
  return (
    <div
      className={`relative w-full overflow-hidden rounded-md border border-border/60 bg-zinc-950 ${expanded ? 'min-h-[55vh]' : ''}`}
      style={{ aspectRatio: width > 0 && height > 0 ? `${width}/${height}` : '16/9' }}
      aria-label={`Exact analyzed detection frame for ${cameraId}`}
    >
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
          {showDetections && loadedFrameKey === packetKey ? (
            <svg
              className="pointer-events-none absolute inset-0 h-full w-full"
              viewBox={`0 0 ${width} ${height}`}
              preserveAspectRatio="xMidYMid meet"
              aria-label="Synchronized vehicle boxes, labels, and confidence"
            >
              {boxes.map((box, index) => {
                const confidence = Math.max(0, Math.min(1, box.confidence || 0))
                const label = `${(box.label || 'Vehicle').replace(/^\w/, (letter) => letter.toUpperCase())} ${Math.round(confidence * 100)}%`
                const labelWidth = Math.min(width, Math.max(92, label.length * 8 + 14))
                const labelX = Math.max(0, Math.min(box.x, width - labelWidth))
                const labelY = Math.max(0, box.y - 24)
                return (
                  <g key={`${box.label}-${index}`}>
                    <rect
                      x={box.x}
                      y={box.y}
                      width={box.width}
                      height={box.height}
                      fill="none"
                      stroke="#22c55e"
                      strokeWidth={expanded ? 4 : 3}
                      vectorEffect="non-scaling-stroke"
                    />
                    <rect x={labelX} y={labelY} width={labelWidth} height="24" rx="3" fill="#15803d" opacity="0.97" />
                    <text x={labelX + 7} y={labelY + 17} fill="white" fontSize="14" fontFamily="system-ui, sans-serif" fontWeight="700">
                      {label}
                    </text>
                  </g>
                )
              })}
            </svg>
          ) : null}
          <div className="absolute bottom-2 left-2 flex flex-wrap gap-1.5">
            <Badge className="bg-black/85 text-white hover:bg-black/85">
              {boxes.length} {boxes.length === 1 ? 'vehicle' : 'vehicles'}
            </Badge>
            {!showDetections ? <Badge variant="secondary">Boxes hidden</Badge> : null}
          </div>
        </>
      ) : (
        <div className="flex h-full min-h-52 items-center justify-center px-6 text-center text-sm text-zinc-400">
          Waiting for an exact analyzed frame. Live capture and other cameras continue independently.
        </div>
      )}
    </div>
  )
}

function DetectionCameraTile({
  camera,
  status,
  showDetections,
}: {
  camera: CctvCamera
  status?: CameraMonitoringStatus
  showDetections: boolean
}) {
  const view = useCameraAnalysis(camera.cameraId)
  const [expanded, setExpanded] = useState(false)
  const now = typeof performance === 'undefined' ? 0 : performance.now()
  const packet = view && now < (view.retentionExpiresAt ?? 0) ? view.packet : null
  const boxes = packet
    ? clipAnalysisBoxes(packet.boxes, packet.sourceFrame.width ?? 0, packet.sourceFrame.height ?? 0)
    : []
  const health = cameraHealth(camera, status)
  const sourceType = cameraSourceType(camera)
  const collision = collisionStatus(status)
  const fresh = Boolean(view && now < view.expiresAt)
  const receivedAt = view?.receivedAt ?? now
  const ageMs = packet
    ? (packet.sourceAgeMs ?? packet.resultAgeMs) + Math.max(0, now - receivedAt)
    : null
  const freshness = packet ? (fresh ? 'FRESH' : 'STALE') : 'WAITING'
  const capturedAt = packet?.sourceFrame.capturedAt
    ? new Date(packet.sourceFrame.capturedAt * 1000).toLocaleString()
    : 'Unavailable'

  return (
    <article className="overflow-hidden rounded-xl border border-border bg-card shadow-sm" data-camera-tile={camera.cameraId}>
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-4 py-3">
        <div className="min-w-0">
          <h2 className="truncate font-semibold">{cameraName(camera)}</h2>
          <p className="mt-1 flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
            <span className="flex items-center gap-1"><Camera className="h-3.5 w-3.5" />{sourceType}</span>
            <span aria-label={`Analysis freshness ${freshness}`}>
              {freshness} {packet ? `• ${formatCompactFrameAge(ageMs)}` : ''}
            </span>
          </p>
        </div>
        <Badge variant={healthVariant(health)}>{health}</Badge>
      </div>

      <div className="p-3">
        <ExactDetectionFrame cameraId={camera.cameraId} view={view} showDetections={showDetections} />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-4 py-3 text-sm">
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          <p><span className="text-muted-foreground">Vehicles:</span> <strong>{boxes.length}</strong></p>
          <p><span className="text-muted-foreground">Collision:</span> <strong>{collision}</strong></p>
        </div>
        <Button type="button" size="sm" variant="outline" onClick={() => setExpanded(true)}>
          <Maximize2 className="h-4 w-4" />Expand
        </Button>
      </div>

      <Dialog open={expanded} onOpenChange={setExpanded}>
        <DialogContent className="max-h-[95vh] overflow-y-auto sm:max-w-6xl">
          <DialogHeader>
            <DialogTitle>{cameraName(camera)}</DialogTitle>
            <DialogDescription>Large exact analyzed frame with synchronized vehicle annotations.</DialogDescription>
          </DialogHeader>
          <ExactDetectionFrame cameraId={camera.cameraId} view={view} showDetections={showDetections} expanded />
          <div className="grid gap-2 rounded-md bg-muted/60 p-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <p><span className="text-muted-foreground">Type:</span> {sourceType}</p>
            <p><span className="text-muted-foreground">Health:</span> {health}</p>
            <p><span className="text-muted-foreground">Freshness:</span> {packet ? (fresh ? 'FRESH' : 'STALE') : 'WAITING'}</p>
            <p><span className="text-muted-foreground">Vehicles:</span> {boxes.length}</p>
            <p className="sm:col-span-2"><span className="text-muted-foreground">Capture time:</span> {capturedAt}</p>
            <p><span className="text-muted-foreground">Frame sequence:</span> {packet?.sourceFrame.sequence ?? 'Unavailable'}</p>
            <p><span className="text-muted-foreground">Collision:</span> {collision}</p>
          </div>
          <DialogFooter>
            <DialogClose asChild><Button type="button">Back to all cameras</Button></DialogClose>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </article>
  )
}

export function CameraDetectionGrid() {
  const [cameras, setCameras] = useState<CctvCamera[]>([])
  const [statuses, setStatuses] = useState<Record<string, CameraMonitoringStatus>>({})
  const [filter, setFilter] = useState<CameraFilter>('all')
  const [showDetections, setShowDetections] = useState(true)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadCameras = useCallback(async () => {
    setLoading(true)
    try {
      const saved = await getCctvCameras()
      setCameras(saved.filter((camera) => camera.isActive))
      setError('')
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load cameras.')
    } finally {
      setLoading(false)
    }
  }, [])

  const loadStatuses = useCallback(async () => {
    if (cameras.length === 0) return
    const results = await Promise.allSettled(
      cameras.map((camera) => getCameraMonitoringStatus(camera.cameraId))
    )
    setStatuses((current) => {
      const next = { ...current }
      results.forEach((result, index) => {
        if (result.status === 'fulfilled') next[cameras[index].cameraId] = result.value
      })
      return next
    })
  }, [cameras])

  useEffect(() => { void loadCameras() }, [loadCameras])
  useEffect(() => {
    void loadStatuses()
    const interval = window.setInterval(() => void loadStatuses(), 4000)
    return () => window.clearInterval(interval)
  }, [loadStatuses])

  const visibleCameras = useMemo(() => cameras.filter((camera) => {
    const source = cameraSourceType(camera)
    return filter === 'all' || (filter === 'usb' ? source === 'USB' : source === 'CCTV')
  }), [cameras, filter])

  const gridClass = cameraDetectionGridClass(visibleCameras.length)

  return (
    <section className="space-y-5" aria-label="All camera analyzed detections">
      <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap gap-2" aria-label="Camera type filter">
          {(['all', 'cctv', 'usb'] as const).map((value) => (
            <Button key={value} type="button" size="sm" variant={filter === value ? 'default' : 'outline'} aria-pressed={filter === value} onClick={() => setFilter(value)}>
              {value === 'all' ? 'All' : value === 'cctv' ? 'CCTV' : 'USB'}
            </Button>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" variant="outline" aria-pressed={showDetections} onClick={() => setShowDetections((value) => !value)}>
            {showDetections ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
            Detections {showDetections ? 'ON' : 'OFF'}
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={() => { void loadCameras(); void loadStatuses() }} disabled={loading}>
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />Refresh
          </Button>
        </div>
      </div>

      {error ? <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">{error}</div> : null}
      {loading && cameras.length === 0 ? <p className="text-sm text-muted-foreground">Loading camera detection views…</p> : null}
      {!loading && visibleCameras.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border p-10 text-center text-sm text-muted-foreground">
          No active cameras match this filter.
        </div>
      ) : null}

      <div className={gridClass} data-camera-grid-count={visibleCameras.length}>
        {visibleCameras.map((camera) => (
          <DetectionCameraTile
            key={camera.cameraId}
            camera={camera}
            status={statuses[camera.cameraId]}
            showDetections={showDetections}
          />
        ))}
      </div>
    </section>
  )
}
