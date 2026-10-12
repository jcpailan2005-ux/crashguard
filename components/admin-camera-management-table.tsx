'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { Input } from '@/components/ui/input'
import {
  Camera,
  Plus,
  Search,
  RefreshCw,
  Video,
  Play,
  Pencil,
  Trash2,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Loader2,
  Activity,
  ShieldCheck,
} from 'lucide-react'
import { CctvCamera } from '@/lib/types'
import {
  getCctvCameras,
  enableCctvCamera,
  disableCctvCamera,
  deleteCctvCamera,
  testCameraConnection,
  CameraConnectionResult,
  getCameraMonitoringStatus,
} from '@/lib/api-client'
import { useAuth } from '@/components/auth-provider'
import { canManageCamera, isProtectedCamera } from '@/lib/camera-management-permissions'
import { AddEditCameraDialog } from '@/components/add-edit-camera-dialog'

interface AdminCameraManagementTableProps {
  onViewCamera?: (camera: CctvCamera) => void
}

interface CameraWithLiveHealth extends CctvCamera {
  liveHealth?: string
  liveStatus?: string
  lastFrameAgeMs?: number | null
  reconnectCount?: number
  isTesting?: boolean
  testResult?: CameraConnectionResult | null
}

export function AdminCameraManagementTable({ onViewCamera }: AdminCameraManagementTableProps) {
  const { profile } = useAuth()
  const canCreateCamera = canManageCamera(profile, 'create')
  const canUpdateCamera = canManageCamera(profile, 'update')
  const canDeleteCamera = canManageCamera(profile, 'disable')
  const [actionError, setActionError] = useState('')
  const [cameras, setCameras] = useState<CameraWithLiveHealth[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [refreshing, setRefreshing] = useState(false)

  // Dialog states
  const [dialogOpen, setDialogOpen] = useState(false)
  const [selectedCamera, setSelectedCamera] = useState<CctvCamera | null>(null)

  const loadCameras = useCallback(async () => {
    try {
      const data = await getCctvCameras()
      // Augment cameras with live health states
      setCameras((prev) => {
        const prevMap = new Map(prev.map((c) => [c.cameraId, c]))
        return data.map((c) => {
          const existing = prevMap.get(c.cameraId)
          return {
            ...c,
            liveHealth: existing?.liveHealth ?? (c.isActive ? 'CONNECTING' : 'DISABLED'),
            liveStatus: existing?.liveStatus ?? (c.isActive ? 'connecting' : 'disabled'),
            lastFrameAgeMs: existing?.lastFrameAgeMs ?? null,
            reconnectCount: existing?.reconnectCount ?? 0,
          }
        })
      })
    } catch (err) {
      console.error('Failed to load cameras:', err)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    loadCameras()
  }, [loadCameras])

  // Poll camera statuses for active cameras every 4 seconds
  useEffect(() => {
    let mounted = true

    const pollStatuses = async () => {
      if (!cameras.length) return

      for (const cam of cameras) {
        if (!mounted) break
        if (!cam.isActive) continue

        try {
          const status = await getCameraMonitoringStatus(cam.cameraId)
          if (!mounted) break
          setCameras((curr) =>
            curr.map((c) => {
              if (c.cameraId === cam.cameraId) {
                return {
                  ...c,
                  liveHealth: (status as any).cameraHealth || (status.monitoringLive ? 'ONLINE' : 'OFFLINE'),
                  liveStatus: status.status || 'disconnected',
                  lastFrameAgeMs: status.frameAgeMs ?? null,
                  reconnectCount: status.reconnectCount ?? c.reconnectCount,
                }
              }
              return c
            })
          )
        } catch {
          // Keep prior status on transient failure
        }
      }
    }

    const interval = setInterval(pollStatuses, 4000)
    void pollStatuses()

    return () => {
      mounted = false
      clearInterval(interval)
    }
  }, [cameras.length])

  const handleToggleActive = async (cam: CameraWithLiveHealth, checked: boolean) => {
    try {
      if (checked) {
        await enableCctvCamera(cam.cameraId)
      } else {
        await disableCctvCamera(cam.cameraId)
      }
      setCameras((curr) =>
        curr.map((c) =>
          c.cameraId === cam.cameraId
            ? {
                ...c,
                isActive: checked,
                liveHealth: checked ? 'CONNECTING' : 'DISABLED',
                liveStatus: checked ? 'connecting' : 'disabled',
              }
            : c
        )
      )
    } catch (err: any) {
      console.error('Failed to toggle camera active state:', err)
    }
  }

  const handleInlineTest = async (cam: CameraWithLiveHealth) => {
    setCameras((curr) =>
      curr.map((c) => (c.cameraId === cam.cameraId ? { ...c, isTesting: true, testResult: null } : c))
    )

    try {
      const res = await testCameraConnection('', {
        cameraId: cam.cameraId,
        label: cam.label,
      })
      setCameras((curr) =>
        curr.map((c) =>
          c.cameraId === cam.cameraId
            ? {
                ...c,
                isTesting: false,
                testResult: res,
                liveHealth: res.connected ? 'ONLINE' : 'OFFLINE',
              }
            : c
        )
      )
    } catch (err: any) {
      setCameras((curr) =>
        curr.map((c) =>
          c.cameraId === cam.cameraId
            ? {
                ...c,
                isTesting: false,
                testResult: {
                  connected: false,
                  status: 'OFFLINE',
                  message: err.message || 'Connection test failed',
                },
                liveHealth: 'OFFLINE',
              }
            : c
        )
      )
    }
  }

  const handleDelete = async (cam: CameraWithLiveHealth) => {
    if (!canDeleteCamera || isProtectedCamera(cam)) return
    setActionError('')
    if (!confirm(`Are you sure you want to disable and remove "${cam.label}"?`)) return
    try {
      await deleteCctvCamera(cam.cameraId)
      await loadCameras()
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Could not remove camera.')
    }
  }

  const handleOpenAdd = () => {
    setSelectedCamera(null)
    setDialogOpen(true)
  }

  const handleOpenEdit = (cam: CctvCamera) => {
    setSelectedCamera(cam)
    setDialogOpen(true)
  }

  const filteredCameras = cameras.filter((c) => {
    const q = search.toLowerCase().trim()
    if (!q) return true
    return (
      (c.label || '').toLowerCase().includes(q) ||
      (c.location || '').toLowerCase().includes(q) ||
      (c.areaId || '').toLowerCase().includes(q) ||
      (c.cameraIp || '').toLowerCase().includes(q)
    )
  })

  const getHealthBadge = (cam: CameraWithLiveHealth) => {
    if (!cam.isActive) {
      return (
        <Badge variant="outline" className="bg-zinc-500/10 text-zinc-600 dark:text-zinc-400 border-zinc-500/20 text-xs font-semibold">
          DISABLED
        </Badge>
      )
    }

    const health = (cam.liveHealth || 'OFFLINE').toUpperCase()

    if (health === 'ONLINE' || health === 'LIVE') {
      return (
        <Badge variant="outline" className="bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30 text-xs font-semibold animate-pulse">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block mr-1.5" />
          ONLINE
        </Badge>
      )
    }

    if (health === 'CONNECTING' || health === 'RECONNECTING') {
      return (
        <Badge variant="outline" className="bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30 text-xs font-semibold">
          <Loader2 className="w-3 h-3 mr-1 inline animate-spin text-amber-500" />
          RECONNECTING
        </Badge>
      )
    }

    if (health === 'STALE') {
      return (
        <Badge variant="outline" className="bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30 text-xs font-semibold">
          <AlertTriangle className="w-3 h-3 mr-1 inline text-amber-500" />
          STALE
        </Badge>
      )
    }

    return (
      <Badge variant="outline" className="bg-destructive/15 text-destructive dark:text-rose-400 border-destructive/30 text-xs font-semibold">
        <span className="w-1.5 h-1.5 rounded-full bg-destructive inline-block mr-1.5" />
        OFFLINE
      </Badge>
    )
  }

  const formatFrameAge = (cam: CameraWithLiveHealth) => {
    if (!cam.isActive) return 'Disabled'
    if (cam.lastFrameAgeMs != null) {
      const sec = (cam.lastFrameAgeMs / 1000).toFixed(1)
      return `${sec}s ago`
    }
    if (cam.lastSeenAt) {
      return new Date(cam.lastSeenAt).toLocaleTimeString()
    }
    return 'No frame received'
  }

  return (
    <div className="space-y-4">
      {/* Top Banner & Actions */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 rounded-xl border border-border bg-card shadow-sm">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-primary" />
            <h2 className="text-lg font-bold">Camera Infrastructure Management</h2>
            <Badge variant="secondary" className="text-xs">
              {cameras.length} {cameras.length === 1 ? 'Camera' : 'Cameras'} Configured
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground">
            Authoritative CCTV camera repository backed by SQLite. Manage stream credentials, test live feeds, and control camera activation.
          </p>
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          {canCreateCamera && <Button size="sm" onClick={handleOpenAdd}>
            <Plus className="w-3.5 h-3.5 mr-1.5" />Add Camera
          </Button>}
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setRefreshing(true)
              void loadCameras()
            }}
            disabled={refreshing}
            className="h-9 text-xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {actionError && <p role="alert" className="text-sm text-destructive">{actionError}</p>}
      {/* Filter / Search Bar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-2.5 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="Search by name, location, or area..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 h-9 text-xs"
          />
        </div>
      </div>

      {/* Cameras Table */}
      <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/30">
              <TableHead className="text-xs font-bold w-[220px]">Camera Name</TableHead>
              <TableHead className="text-xs font-bold">Area</TableHead>
              <TableHead className="text-xs font-bold">Location</TableHead>
              <TableHead className="text-xs font-bold">Connection Health</TableHead>
              <TableHead className="text-xs font-bold text-center">Enabled</TableHead>
              <TableHead className="text-xs font-bold">Last Frame</TableHead>
              <TableHead className="text-xs font-bold text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} className="h-32 text-center text-xs text-muted-foreground">
                  <div className="flex flex-col items-center justify-center gap-2">
                    <Loader2 className="w-5 h-5 animate-spin text-primary" />
                    <span>Loading camera registry from SQLite...</span>
                  </div>
                </TableCell>
              </TableRow>
            ) : filteredCameras.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="h-32 text-center text-xs text-muted-foreground">
                  <div className="flex flex-col items-center justify-center gap-2">
                    <Camera className="w-8 h-8 text-muted-foreground/40" />
                    <span className="font-medium">No cameras have been configured.</span>
                    <span className="text-[11px]">Click &quot;+ Add Camera&quot; above to connect an RTSP stream or IP camera.</span>
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              filteredCameras.map((cam) => (
                <TableRow key={cam.cameraId} className="hover:bg-muted/20 transition-colors">
                  {/* Camera Name */}
                  <TableCell>
                    <div className="flex items-center gap-2.5">
                      <div className="p-2 rounded-lg bg-primary/10 text-primary shrink-0">
                        <Video className="w-4 h-4" />
                      </div>
                      <div className="space-y-0.5">
                        <div className="font-semibold text-xs text-foreground flex items-center gap-1.5">
                          <span>{cam.label || cam.name || cam.cameraId}</span>
                        </div>
                        <div className="text-[11px] text-muted-foreground flex items-center gap-1.5 font-mono">
                          <span>{cam.cameraType || 'RTSP Stream'}</span>
                          {cam.cameraIp && <span>• {cam.cameraIp}</span>}
                        </div>
                      </div>
                    </div>
                  </TableCell>

                  {/* Area */}
                  <TableCell>
                    <Badge variant="secondary" className="capitalize text-[11px] font-medium">
                      {cam.areaId || cam.barangay || 'Toril'}
                    </Badge>
                  </TableCell>

                  {/* Location */}
                  <TableCell>
                    <span className="text-xs text-muted-foreground line-clamp-1">
                      {cam.location || cam.locationDescription || 'Crossing MacArthur Highway'}
                    </span>
                  </TableCell>

                  {/* Connection Health */}
                  <TableCell>
                    <div className="space-y-1">
                      {getHealthBadge(cam)}
                      {cam.testResult && (
                        <div
                          className={`text-[11px] flex items-center gap-1 mt-1 ${
                            cam.testResult.connected ? 'text-emerald-600' : 'text-destructive'
                          }`}
                        >
                          {cam.testResult.connected ? (
                            <CheckCircle2 className="w-3 h-3 shrink-0" />
                          ) : (
                            <XCircle className="w-3 h-3 shrink-0" />
                          )}
                          <span className="truncate max-w-[180px]">{cam.testResult.message}</span>
                        </div>
                      )}
                    </div>
                  </TableCell>

                  {/* Enabled Toggle */}
                  <TableCell className="text-center">
                    <Switch
                      disabled={!canUpdateCamera || (!canDeleteCamera && cam.isActive)}
                      checked={cam.isActive}
                      onCheckedChange={(checked) => handleToggleActive(cam, checked)}
                      aria-label={`Toggle ${cam.label}`}
                    />
                  </TableCell>

                  {/* Last Frame */}
                  <TableCell>
                    <div className="text-xs font-mono text-muted-foreground flex items-center gap-1">
                      <Activity className="w-3.5 h-3.5 text-muted-foreground/60" />
                      <span>{formatFrameAge(cam)}</span>
                    </div>
                  </TableCell>

                  {/* Actions */}
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      {/* View button (switches to Live Monitor) */}
                      {onViewCamera && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => onViewCamera(cam)}
                          title="View live CCTV feed"
                          className="h-8 px-2 text-xs text-primary hover:text-primary hover:bg-primary/10"
                        >
                          <Play className="w-3.5 h-3.5 mr-1" />
                          View
                        </Button>
                      )}

                      {/* Test Connection */}
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleInlineTest(cam)}
                        disabled={cam.isTesting}
                        title="Test decoded frame connection"
                        className="h-8 px-2 text-xs"
                      >
                        {cam.isTesting ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          'Test'
                        )}
                      </Button>

                      {/* Edit */}
                      {canUpdateCamera && <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleOpenEdit(cam)}
                        title="Edit camera parameters"
                        className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground"
                      >
                        <Pencil className="w-3.5 h-3.5" />
                      </Button>}

                      {/* Delete */}
                      {canDeleteCamera && !isProtectedCamera(cam) && <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(cam)}
                        title="Disable and remove camera"
                        className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>}
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Add / Edit Camera Dialog */}
      <AddEditCameraDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        camera={selectedCamera}
        onSaved={loadCameras}
      />
    </div>
  )
}
