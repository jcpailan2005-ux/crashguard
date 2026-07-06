'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AlertTriangle, MapPin, Plus, RefreshCw, Save, Video } from 'lucide-react'

import { Sidebar } from '@/components/dashboard-sidebar'
import { LiveCamera } from '@/components/live-camera'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/components/auth-provider'
import {
  fetchCameraPreviewFrameObjectUrl,
  getCameraMonitoringStatus,
  getCctvCameras,
  saveCctvCamera,
  type CameraMonitoringStatus,
} from '@/lib/api-client'
import { useDisplayMode } from '@/lib/display-mode'
import { CctvCamera } from '@/lib/types'

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
  streamUrl: string
  location: string
}

const CAMERA_CACHE_KEY = 'mycrushguard.savedCctvCamera'

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
    streamUrl: '',
    location: '',
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

function isRtspStreamUrl(value: string) {
  return /^rtsps?:\/\/\S+$/i.test(value.trim())
}

function cameraStatusFrameUrl(status?: CameraMonitoringStatus) {
  return status?.latestFrameUrl ?? status?.frameUrl ?? status?.previewUrl ?? status?.imageUrl ?? null
}

function cameraStatusBadges(status: CameraMonitoringStatus | undefined, camera: CctvCamera | null) {
  if (!camera || !camera.isActive || !camera.detectionEnabled) return ['OFFLINE']
  if (status?.reconnecting || status?.status === 'reconnecting') return ['RECONNECTING']
  if (status?.lastError || status?.status === 'connection-lost') return ['OFFLINE']

  const badges: string[] = []
  if (status?.monitoringLive || status?.cameraConnected || status?.latestFrameAvailable) {
    badges.push('LIVE')
  }
  if (status?.detectionRunning) {
    badges.push('SCANNING')
  }
  return badges.length > 0 ? badges : ['OFFLINE']
}

function statusBadgeVariant(label: string): 'default' | 'secondary' | 'outline' {
  if (label === 'LIVE' || label === 'SCANNING') return 'default'
  if (label === 'RECONNECTING') return 'secondary'
  return 'outline'
}

function formatConfidence(value?: number | null) {
  if (typeof value !== 'number') return 'No confidence yet'
  return `${Math.round(value * 100)}%`
}

function latestAlertId(status?: CameraMonitoringStatus) {
  return (
    status?.lastCreatedCaseId ??
    status?.activeBlockingCaseId ??
    status?.activeCaseId ??
    status?.latestResult?.caseId ??
    null
  )
}

function buildCameraSlots(cameras: CctvCamera[]): CameraSlot[] {
  const slots: CameraSlot[] = cameras.map((camera, index) => ({ camera, slotNumber: index + 1 }))
  if (slots.length < 3) {
    slots.push({ camera: null, slotNumber: slots.length + 1 })
  }
  return slots
}

export default function IpCameraPage() {
  const { profile } = useAuth()
  const { isAdvancedMode } = useDisplayMode(profile)
  const areaId = profile?.areaId ?? 'talomo'
  const normalizedRole = String(profile?.role ?? '').toLowerCase()
  const isResponder = normalizedRole === 'responder'
  const canEditCameraSettings = normalizedRole === 'admin' && isAdvancedMode
  const showAdvancedCameraControls = canEditCameraSettings
  const [cameras, setCameras] = useState<CctvCamera[]>([])
  const [activeCamera, setActiveCamera] = useState<CctvCamera | null>(null)
  const [form, setForm] = useState<CameraFormState>(() => emptyCameraForm(areaId))
  const [addCameraForm, setAddCameraForm] = useState<AddCameraFormState>(() => emptyAddCameraForm())
  const [isAddCameraOpen, setIsAddCameraOpen] = useState(false)
  const [addCameraError, setAddCameraError] = useState('')
  const [loadingCameras, setLoadingCameras] = useState(true)
  const [savingCamera, setSavingCamera] = useState(false)
  const [cameraError, setCameraError] = useState('')
  const [cameraStatuses, setCameraStatuses] = useState<Record<string, CameraMonitoringStatus>>({})
  const [cameraPreviewUrls, setCameraPreviewUrls] = useState<Record<string, string>>({})
  const previewUrlsRef = useRef<Record<string, string>>({})

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
      (form.cameraIp.trim() || form.streamUrl.trim())
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
    () => cameras.filter((camera) => !isDemoCamera(camera)).length,
    [cameras]
  )
  const savedCameras = useMemo(() => {
    const unique = new Map<string, CctvCamera>()
    for (const camera of cameras) {
      if (isDemoCamera(camera)) continue
      const uniqueKey = camera.cameraIp?.trim() || camera.streamUrl?.trim() || camera.cameraId
      if (!unique.has(uniqueKey)) {
        unique.set(uniqueKey, camera)
      }
    }
    return [...unique.values()]
  }, [cameras])
  const cameraSlots = useMemo(() => buildCameraSlots(savedCameras), [savedCameras])
  const activeStatusBadges = useMemo(
    () => cameraStatusBadges(activeCameraStatus, activeCamera),
    [activeCamera, activeCameraStatus]
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
      const defaultCamera = pickDefaultCamera(items, areaId)

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
          applyCamera(cachedCamera)
        } catch {
        }
      }
      setCameraError(error instanceof Error ? error.message : 'Could not load saved cameras.')
    } finally {
      setLoadingCameras(false)
    }
  }, [applyCamera, areaId])

  useEffect(() => {
    setForm((current) => ({
      ...current,
      areaId: current.areaId || areaId,
    }))
  }, [areaId])

  useEffect(() => {
    void loadSavedCameras()
  }, [loadSavedCameras])

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
    if (loadingCameras) return
    void loadCameraStatuses()
  }, [loadCameraStatuses, loadingCameras])

  useEffect(() => {
    if (savedCameras.length === 0) return
    const interval = window.setInterval(() => {
      void loadCameraStatuses()
    }, 4000)
    return () => window.clearInterval(interval)
  }, [loadCameraStatuses, savedCameras.length])

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
    setIsAddCameraOpen(true)
  }

  const saveResponderCamera = async () => {
    const streamUrl = addCameraForm.streamUrl.trim()
    const location = addCameraForm.location.trim()

    if (!streamUrl) {
      setAddCameraError('RTSP stream link is required.')
      return
    }

    if (!isRtspStreamUrl(streamUrl)) {
      setAddCameraError('Enter a valid RTSP stream link, for example rtsp://username:password@camera-ip:554/stream.')
      return
    }

    if (!location) {
      setAddCameraError('Camera location is required.')
      return
    }

    if (isSensitiveCameraText(location)) {
      setAddCameraError('Camera location must describe the physical placement, not an RTSP link, IP address, or credentials.')
      return
    }

    setSavingCamera(true)
    setAddCameraError('')
    setCameraError('')

    try {
      const saved = await saveCctvCamera({
        label: `Responder CCTV Camera ${savedCameraCount + 1}`,
        streamUrl,
        areaId,
        barangay: areaId,
        location,
        locationDescription: location,
        cameraType: 'RTSP Stream',
        status: 'offline',
        isActive: true,
        detectionEnabled: true,
      })

      setActiveCamera(saved)
      setForm(cameraToForm(saved, areaId))
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

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <div className="flex-1 md:ml-0">
        <main className="space-y-4 p-4 pt-16 md:p-6 md:pt-6">
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

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_21rem]">
            <section className="min-w-0 space-y-3">
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
            </section>

            <aside className="min-w-0 rounded-lg border border-border bg-card">
              <div className="flex items-start justify-between gap-3 border-b border-border p-3">
                <div className="min-w-0">
                  <h2 className="font-semibold">Camera feeds</h2>
                  <p className="text-sm text-muted-foreground">
                    Select a feed to open it.
                  </p>
                </div>
                <div className="flex shrink-0 gap-2">
                  {isResponder ? (
                    <Button type="button" size="sm" onClick={openAddCameraDialog}>
                      <Plus className="h-4 w-4" />
                      Add New Camera
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
              <div className="grid gap-3 p-3 sm:grid-cols-2 xl:max-h-[calc(100vh-220px)] xl:grid-cols-1 xl:overflow-y-auto">
                {cameraSlots.map(({ camera, slotNumber }) => {
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

                  return (
                    <button
                      key={camera.cameraId}
                      type="button"
                      className={`overflow-hidden rounded-lg border text-left transition-colors ${
                        selected
                          ? 'border-primary bg-primary/10'
                          : 'border-border bg-background hover:border-primary/50'
                      }`}
                      onClick={() => applyCamera(camera)}
                      aria-label={`Select ${safeCameraName(camera)}`}
                    >
                      <div className="relative aspect-video overflow-hidden bg-zinc-950">
                        {previewUrl ? (
                          <img
                            src={previewUrl}
                            alt={`${safeCameraName(camera)} preview`}
                            className="h-full w-full object-cover"
                          />
                        ) : (
                          <div className="flex h-full w-full items-center justify-center px-4 text-center text-xs text-zinc-500">
                            Camera preview unavailable
                          </div>
                        )}
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
                        {alertId ? (
                          <Badge className="absolute bottom-2 left-2" variant="destructive">
                            ALERT
                          </Badge>
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
                        </div>
                        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                          <span>Confidence: {formatConfidence(status?.lastConfidence ?? status?.confidence)}</span>
                          {alertId ? <span>Case: {alertId}</span> : null}
                        </div>
                      </div>
                    </button>
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
        </main>

        <Dialog open={isAddCameraOpen} onOpenChange={setIsAddCameraOpen}>
          <DialogContent className="border border-border bg-card sm:max-w-lg">
            <DialogHeader>
              <DialogTitle>Add New Camera</DialogTitle>
            </DialogHeader>

            <div className="space-y-4">
              {addCameraError ? (
                <Alert variant="destructive">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>{addCameraError}</AlertDescription>
                </Alert>
              ) : null}

              <div className="space-y-2">
                <Label htmlFor="new-camera-stream">RTSP Stream Link</Label>
                <Input
                  id="new-camera-stream"
                  type="password"
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
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="new-camera-location">Camera Location</Label>
                <Input
                  id="new-camera-location"
                  value={addCameraForm.location}
                  onChange={(event) =>
                    setAddCameraForm((current) => ({
                      ...current,
                      location: event.target.value,
                    }))
                  }
                  placeholder="Talomo Road, Main Gate, Parking Area"
                />
                <p className="text-xs text-muted-foreground">
                  Use the physical placement of the camera. Do not enter an IP address or stream link here.
                </p>
              </div>

              <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsAddCameraOpen(false)}
                  disabled={savingCamera}
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  onClick={() => void saveResponderCamera()}
                  disabled={savingCamera}
                >
                  <Save className="h-4 w-4" />
                  {savingCamera ? 'Saving...' : 'Save Camera'}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  )
}
