'use client'

import { useEffect, useState } from 'react'
import { Loader, Plus, Save, Search } from 'lucide-react'

import { useAuth } from '@/components/auth-provider'
import { DashboardHeader, Sidebar } from '@/components/dashboard-sidebar'
import { PermissionMessage } from '@/components/permission-message'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useToast } from '@/hooks/use-toast'
import {
  assignCctvCamera,
  disableCctvCamera,
  enableCctvCamera,
  getCctvCameras,
  saveCctvCamera,
} from '@/lib/api-client'
import { CctvCamera } from '@/lib/types'

const EMPTY_FORM = {
  cameraId: '',
  label: '',
  areaId: 'talomo',
  barangay: 'Talomo',
  roadName: '',
  locationDescription: '',
  cameraIp: '',
  streamUrl: '',
  latitude: '',
  longitude: '',
  detectionEnabled: true,
  isActive: true,
}

export default function CameraManagementPage() {
  const { profile } = useAuth()
  const { toast } = useToast()
  const [cameras, setCameras] = useState<CctvCamera[]>([])
  const [form, setForm] = useState(EMPTY_FORM)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [assigning, setAssigning] = useState(false)
  const [error, setError] = useState('')
  const [assignmentResponderId, setAssignmentResponderId] = useState('')
  const [assignmentCameraId, setAssignmentCameraId] = useState('')
  const [assignmentAreaId, setAssignmentAreaId] = useState('talomo')

  const loadCameras = async () => {
    try {
      setLoading(true)
      setCameras(await getCctvCameras())
      setError('')
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load cameras.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadCameras()
  }, [])

  const filtered = cameras.filter((camera) => {
    const term = search.toLowerCase().trim()
    if (!term) return true
    return [camera.label, camera.areaId, camera.barangay, camera.roadName, camera.locationDescription]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
      .includes(term)
  })

  const update = (key: keyof typeof EMPTY_FORM, value: string | boolean) => {
    setForm((current) => ({ ...current, [key]: value }))
  }

  const editCamera = (camera: CctvCamera) => {
    setForm({
      cameraId: camera.cameraId,
      label: camera.label,
      areaId: camera.areaId ?? 'talomo',
      barangay: camera.barangay ?? camera.areaId ?? '',
      roadName: camera.roadName ?? '',
      locationDescription: camera.locationDescription ?? camera.location ?? '',
      cameraIp: camera.cameraIp ?? '',
      streamUrl: camera.streamUrl ?? '',
      latitude: camera.latitude == null ? '' : String(camera.latitude),
      longitude: camera.longitude == null ? '' : String(camera.longitude),
      detectionEnabled: camera.detectionEnabled,
      isActive: camera.isActive,
    })
  }

  const save = async () => {
    if (!form.label.trim()) {
      setError('Camera name is required.')
      return
    }
    if (!form.areaId.trim()) {
      setError('Area or barangay is required.')
      return
    }
    if (!form.cameraIp.trim() && !form.streamUrl.trim()) {
      setError('Either IP address or stream URL is required.')
      return
    }
    setSaving(true)
    try {
      const latitude = form.latitude.trim() ? Number(form.latitude) : undefined
      const longitude = form.longitude.trim() ? Number(form.longitude) : undefined
      await saveCctvCamera({
        cameraId: form.cameraId || undefined,
        label: form.label.trim(),
        areaId: form.areaId.trim(),
        barangay: form.barangay.trim() || form.areaId.trim(),
        roadName: form.roadName.trim() || undefined,
        locationDescription: form.locationDescription.trim() || undefined,
        location: form.locationDescription.trim() || form.roadName.trim() || undefined,
        cameraIp: form.cameraIp.trim() || undefined,
        streamUrl: form.streamUrl.trim() || undefined,
        latitude,
        longitude,
        detectionEnabled: form.detectionEnabled,
        isActive: form.isActive,
      })
      setForm(EMPTY_FORM)
      await loadCameras()
      toast({ title: 'Camera saved', description: 'CCTV camera record was updated.' })
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Camera could not be saved.')
    } finally {
      setSaving(false)
    }
  }

  const toggleActive = async (camera: CctvCamera) => {
    try {
      if (camera.isActive) {
        await disableCctvCamera(camera.cameraId)
      } else {
        await enableCctvCamera(camera.cameraId)
      }
      await loadCameras()
    } catch (toggleError) {
      setError(toggleError instanceof Error ? toggleError.message : 'Could not update camera.')
    }
  }

  const assignResponder = async () => {
    if (!assignmentResponderId.trim()) {
      setError('Responder ID is required for assignment.')
      return
    }
    if (!assignmentCameraId && !assignmentAreaId) {
      setError('Choose a camera or area assignment.')
      return
    }
    setAssigning(true)
    try {
      await assignCctvCamera({
        responderId: assignmentResponderId.trim(),
        cameraId: assignmentCameraId || undefined,
        areaId: assignmentAreaId || undefined,
        role: 'viewer',
        status: 'active',
      })
      setAssignmentResponderId('')
      setAssignmentCameraId('')
      toast({ title: 'Assignment saved', description: 'Responder camera access was updated.' })
    } catch (assignError) {
      setError(assignError instanceof Error ? assignError.message : 'Assignment could not be saved.')
    } finally {
      setAssigning(false)
    }
  }

  if (profile?.role !== 'admin') {
    return <PermissionMessage />
  }

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <div className="flex-1 md:ml-0">
        <DashboardHeader />
        <main className="space-y-6 p-6">
          <div>
            <h1 className="text-3xl font-bold">Camera Management</h1>
            <p className="text-muted-foreground">
              Add, edit, disable, and monitor CCTV camera records for local testing.
            </p>
          </div>

          {error ? (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}

          <Card className="border border-border bg-card p-5">
            <div className="mb-4 flex items-center gap-2">
              <Plus className="h-5 w-5" />
              <h2 className="font-semibold">{form.cameraId ? 'Edit Camera' : 'Add Camera'}</h2>
            </div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              <Input value={form.label} onChange={(event) => update('label', event.target.value)} placeholder="Camera name" />
              <Select value={form.areaId} onValueChange={(value) => update('areaId', value)}>
                <SelectTrigger><SelectValue placeholder="Area" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="talomo">Talomo</SelectItem>
                  <SelectItem value="matina">Matina</SelectItem>
                  <SelectItem value="toril">Toril</SelectItem>
                  <SelectItem value="demo">Demo Area</SelectItem>
                </SelectContent>
              </Select>
              <Input value={form.barangay} onChange={(event) => update('barangay', event.target.value)} placeholder="Barangay" />
              <Input value={form.roadName} onChange={(event) => update('roadName', event.target.value)} placeholder="Road name" />
              <Input value={form.locationDescription} onChange={(event) => update('locationDescription', event.target.value)} placeholder="Location description" />
              <Input value={form.cameraIp} onChange={(event) => update('cameraIp', event.target.value)} placeholder="Camera IP address" />
              <Input value={form.streamUrl} onChange={(event) => update('streamUrl', event.target.value)} placeholder="Stream URL or demo://..." />
              <Input value={form.latitude} onChange={(event) => update('latitude', event.target.value)} placeholder="Latitude" />
              <Input value={form.longitude} onChange={(event) => update('longitude', event.target.value)} placeholder="Longitude" />
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-4">
              <label className="flex items-center gap-2 text-sm">
                <Checkbox checked={form.detectionEnabled} onCheckedChange={(value) => update('detectionEnabled', Boolean(value))} />
                Detection enabled
              </label>
              <label className="flex items-center gap-2 text-sm">
                <Checkbox checked={form.isActive} onCheckedChange={(value) => update('isActive', Boolean(value))} />
                Active
              </label>
              <Button type="button" onClick={save} disabled={saving}>
                {saving ? <Loader className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                Save Camera
              </Button>
              {form.cameraId ? (
                <Button type="button" variant="outline" onClick={() => setForm(EMPTY_FORM)}>
                  Clear
                </Button>
              ) : null}
            </div>
          </Card>

          <Card className="border border-border bg-card p-5">
            <div className="mb-4">
              <h2 className="font-semibold">Responder Assignment</h2>
              <p className="text-sm text-muted-foreground">
                Assign a responder UID to one camera or an area for local QA.
              </p>
            </div>
            <div className="grid gap-3 md:grid-cols-[1fr_14rem_14rem_auto]">
              <Input
                value={assignmentResponderId}
                onChange={(event) => setAssignmentResponderId(event.target.value)}
                placeholder="Responder Firebase UID"
              />
              <Select value={assignmentCameraId || 'area-only'} onValueChange={(value) => setAssignmentCameraId(value === 'area-only' ? '' : value)}>
                <SelectTrigger><SelectValue placeholder="Camera" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="area-only">Area assignment only</SelectItem>
                  {cameras.map((camera) => (
                    <SelectItem key={camera.cameraId} value={camera.cameraId}>{camera.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={assignmentAreaId} onValueChange={setAssignmentAreaId}>
                <SelectTrigger><SelectValue placeholder="Area" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="talomo">Talomo</SelectItem>
                  <SelectItem value="matina">Matina</SelectItem>
                  <SelectItem value="toril">Toril</SelectItem>
                  <SelectItem value="demo">Demo Area</SelectItem>
                </SelectContent>
              </Select>
              <Button type="button" onClick={assignResponder} disabled={assigning}>
                {assigning ? <Loader className="h-4 w-4 animate-spin" /> : null}
                Assign
              </Button>
            </div>
          </Card>

          <Card className="border border-border bg-card p-4">
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                className="pl-9"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search cameras..."
              />
            </div>
          </Card>

          <div className="grid gap-3">
            {loading ? (
              <Card className="border border-border bg-card p-8 text-center text-muted-foreground">
                <Loader className="mx-auto mb-2 h-5 w-5 animate-spin" />
                Loading cameras...
              </Card>
            ) : filtered.length === 0 ? (
              <Card className="border border-border bg-card p-8 text-center text-muted-foreground">
                No cameras found.
              </Card>
            ) : (
              filtered.map((camera) => (
                <Card key={camera.cameraId} className="border border-border bg-card p-4">
                  <div className="grid gap-3 lg:grid-cols-[1fr_auto]">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-semibold">{camera.label}</h3>
                        <Badge variant="outline">{camera.areaId || 'unassigned'}</Badge>
                        <Badge variant="outline">{camera.status || 'offline'}</Badge>
                        <Badge variant="outline">{camera.detectionEnabled ? 'Detection Active' : 'Detection Disabled'}</Badge>
                        <Badge variant="outline">{camera.isActive ? 'Active' : 'Inactive'}</Badge>
                      </div>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {camera.roadName || 'Road not set'} · {camera.locationDescription || camera.location || 'Location not set'}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2 lg:justify-end">
                      <Button type="button" variant="outline" onClick={() => editCamera(camera)}>
                        Edit
                      </Button>
                      <Button type="button" variant="outline" onClick={() => toggleActive(camera)}>
                        {camera.isActive ? 'Disable' : 'Enable'}
                      </Button>
                    </div>
                  </div>
                </Card>
              ))
            )}
          </div>
        </main>
      </div>
    </div>
  )
}
