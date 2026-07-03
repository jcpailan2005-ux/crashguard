'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, Grid2X2, MapPin, RefreshCw, Save, Video } from 'lucide-react'

import { DashboardHeader, Sidebar } from '@/components/dashboard-sidebar'
import { LiveCamera } from '@/components/live-camera'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/components/auth-provider'
import { getCctvCameras, saveCctvCamera } from '@/lib/api-client'
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

const CAMERA_CACHE_KEY = 'mycrushguard.savedCctvCamera'

function isDemoCamera(camera: CctvCamera) {
  return (
    camera.cameraType === 'Demo' ||
    camera.streamUrl?.startsWith('demo://') ||
    camera.cameraIp?.startsWith('demo-')
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

function cameraToForm(camera: CctvCamera, fallbackAreaId: string): CameraFormState {
  return {
    cameraId: camera.cameraId,
    cameraName: camera.label,
    cameraIp: camera.cameraIp ?? '',
    // IP cameras use backend camera credentials, so avoid showing the redacted RTSP label as editable input.
    streamUrl: camera.cameraIp ? '' : camera.streamUrl ?? '',
    areaId: camera.areaId ?? fallbackAreaId,
    location: camera.location ?? camera.locationDescription ?? camera.roadName ?? '',
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
  if (!camera) return fallbackAreaId
  return camera.location ?? camera.locationDescription ?? camera.roadName ?? camera.areaId ?? fallbackAreaId
}

function cameraStatusLabel(camera: CctvCamera | null) {
  if (!camera) return 'Offline'
  if (!camera.isActive || !camera.detectionEnabled) return 'Offline'
  return 'Monitoring Live'
}

function buildCameraSlots(cameras: CctvCamera[]): CameraSlot[] {
  const slots: CameraSlot[] = cameras.map((camera, index) => ({ camera, slotNumber: index + 1 }))
  while (slots.length < 3) {
    slots.push({ camera: null, slotNumber: slots.length + 1 })
  }
  return slots
}

export default function IpCameraPage() {
  const { profile } = useAuth()
  const { isAdvancedMode } = useDisplayMode(profile)
  const areaId = profile?.areaId ?? 'talomo'
  const normalizedRole = String(profile?.role ?? '').toLowerCase()
  const canEditCameraSettings = normalizedRole === 'admin' && isAdvancedMode
  const showAdvancedCameraControls = canEditCameraSettings
  const [cameras, setCameras] = useState<CctvCamera[]>([])
  const [activeCamera, setActiveCamera] = useState<CctvCamera | null>(null)
  const [form, setForm] = useState<CameraFormState>(() => emptyCameraForm(areaId))
  const [showAllCameras, setShowAllCameras] = useState(false)
  const [loadingCameras, setLoadingCameras] = useState(true)
  const [savingCamera, setSavingCamera] = useState(false)
  const [cameraMessage, setCameraMessage] = useState('')
  const [cameraError, setCameraError] = useState('')

  const activeAreaId = form.areaId.trim() || activeCamera?.areaId || areaId
  const activeCameraName =
    form.cameraName.trim() || activeCamera?.label || 'Manual CCTV Camera'
  const activeCameraSource = activeCameraName
  const activeStatusLabel = cameraError
    ? 'Needs Attention'
    : activeCamera
      ? cameraStatusLabel(activeCamera)
      : 'Offline'
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
  const savedCameras = useMemo(
    () => cameras.filter((camera) => !isDemoCamera(camera)),
    [cameras]
  )
  const cameraSlots = useMemo(() => buildCameraSlots(savedCameras), [savedCameras])

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
        setCameraMessage(`Monitoring ${defaultCamera.label}`)
        window.localStorage.setItem(CAMERA_CACHE_KEY, JSON.stringify(defaultCamera))
      } else {
        applyCamera(null)
        setCameraMessage('No saved CCTV cameras yet. Ask admin to add cameras.')
      }
    } catch (error) {
      const cached = window.localStorage.getItem(CAMERA_CACHE_KEY)
      if (cached) {
        try {
          const cachedCamera = JSON.parse(cached) as CctvCamera
          applyCamera(cachedCamera)
          setCameraMessage('Using locally cached camera values until the backend is reachable.')
        } catch {
          setCameraMessage('')
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
      setCameraError('Enter a camera IP address or stream URL before saving in Advanced Mode.')
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
      setCameraMessage(`Saved camera: ${saved.label}`)
    } catch (error) {
      setCameraError(error instanceof Error ? error.message : 'Could not save camera.')
    } finally {
      setSavingCamera(false)
    }
  }

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <div className="flex-1 md:ml-0">
        <DashboardHeader />

        <main className="space-y-6 p-6">
          <div>
            <h1 className="mb-2 text-3xl font-bold">CCTV Monitoring</h1>
            <p className="text-muted-foreground">
              Monitoring active traffic camera.
            </p>
          </div>

          <Card className="space-y-4 border border-border p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-lg font-semibold">Active Camera</h2>
                  <Badge variant="outline">
                    {activeStatusLabel}
                  </Badge>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">
                  {activeCamera
                    ? `${activeCamera.label} - ${cameraLocationLabel(activeCamera, activeAreaId)}`
                    : 'No saved CCTV cameras yet. Ask admin to add cameras.'}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {showAdvancedCameraControls ? (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setShowAllCameras((current) => !current)}
                  >
                    <Grid2X2 className="mr-2 h-4 w-4" />
                    {showAllCameras ? 'Hide All Cameras' : 'View All Cameras'}
                  </Button>
                ) : null}
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void loadSavedCameras()}
                  disabled={loadingCameras}
                >
                  <RefreshCw className={`mr-2 h-4 w-4 ${loadingCameras ? 'animate-spin' : ''}`} />
                  Refresh
                </Button>
              </div>
            </div>

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

            {cameraMessage && (showAdvancedCameraControls || !activeCamera) ? (
              <Alert>
                <CheckCircle2 className="h-4 w-4" />
                <AlertDescription>{cameraMessage}</AlertDescription>
              </Alert>
            ) : null}

            {showAdvancedCameraControls ? (
            <div className="grid gap-3 md:grid-cols-3">
              {cameraSlots.slice(0, showAllCameras ? undefined : 3).map(({ camera, slotNumber }) => {
                if (!camera) {
                  return (
                    <div
                      key={`empty-slot-${slotNumber}`}
                      className="rounded-lg border border-dashed border-border bg-background p-4 text-left"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate font-semibold">Camera Slot {slotNumber}</p>
                          <p className="mt-1 text-sm text-muted-foreground">
                            Ask admin to add camera
                          </p>
                        </div>
                        <Badge variant="outline">Empty</Badge>
                      </div>
                      <div className="mt-4 flex h-24 items-center justify-center rounded-md bg-muted text-sm text-muted-foreground">
                        Camera unavailable
                      </div>
                    </div>
                  )
                }

                const selected = activeCamera?.cameraId === camera.cameraId
                const available = Boolean((camera.cameraIp || camera.streamUrl) && camera.isActive && camera.detectionEnabled)
                return (
                  <button
                    key={camera.cameraId}
                    type="button"
                    className={`rounded-lg border p-4 text-left transition-colors ${
                      selected
                        ? 'border-primary bg-primary/10'
                        : 'border-border bg-background hover:border-primary/50'
                    }`}
                    onClick={() => {
                      if (savedCameras.some((item) => item.cameraId === camera.cameraId)) {
                        applyCamera(camera)
                      }
                    }}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate font-semibold">{camera.label}</p>
                        <p className="mt-1 flex items-center gap-1 text-sm text-muted-foreground">
                          <MapPin className="h-3.5 w-3.5" />
                          <span className="truncate">{cameraLocationLabel(camera, areaId)}</span>
                        </p>
                      </div>
                      <Badge variant={available ? 'default' : 'outline'}>
                        {available ? 'Monitoring' : 'Offline'}
                      </Badge>
                    </div>
                    <div className="mt-4 flex h-24 items-center justify-center rounded-md bg-muted text-sm text-muted-foreground">
                      {available ? 'Live feed' : 'Camera unavailable'}
                    </div>
                  </button>
                )
              })}
            </div>
            ) : null}

            <div className="rounded-lg border border-border bg-background p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 font-medium">
                    <Video className="h-4 w-4" />
                    Active camera: {activeCameraName}
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Area/location: {cameraLocationLabel(activeCamera, activeAreaId)}
                  </p>
                </div>
                <Badge variant="outline">{activeStatusLabel}</Badge>
              </div>
            </div>

            {showAdvancedCameraControls ? (
              <div className="space-y-4 rounded-lg border border-dashed border-border bg-background/60 p-4">
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
                  placeholder="192.168.1.34"
                  autoComplete="off"
                  spellCheck={false}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="saved-camera-stream">Stream URL</Label>
                <Input
                  id="saved-camera-stream"
                  type="password"
                  value={form.streamUrl}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, streamUrl: event.target.value }))
                  }
                  placeholder="rtsp://user:pass@192.168.1.34:554/stream1"
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
                    ? `${activeCamera.label} - ${activeCamera.areaId ?? activeAreaId}`
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
              </div>
            ) : null}
          </Card>

          <LiveCamera
            accidentOnlyMode
            areaId={activeAreaId}
            cameraId={activeCamera?.cameraId ?? null}
            cameraName={activeCameraName}
            sourceCamera={activeCameraSource}
            initialCctvIp={form.cameraIp}
            initialStreamUrl={form.streamUrl}
            initialSourceTab="cctv"
            autoStartCctv={shouldAutoStartCctv}
            autoStartCctvKey={autoStartCctvKey}
            detectionIntervalMs={1000}
            managedCctvMode
          />
        </main>
      </div>
    </div>
  )
}
