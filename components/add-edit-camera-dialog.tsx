'use client'

import { useState, useEffect } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Camera,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Loader2,
  Video,
  Shield,
  KeyRound,
  Eye,
  EyeOff,
} from 'lucide-react'
import { CctvCamera } from '@/lib/types'
import { saveCctvCamera, testCameraConnection, CameraConnectionResult } from '@/lib/api-client'

interface AddEditCameraDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  camera?: CctvCamera | null
  onSaved: (savedCamera: CctvCamera) => void
}

const DEFAULT_AREAS = [
  { id: 'toril', name: 'Toril' },
  { id: 'talomo', name: 'Talomo' },
  { id: 'matina', name: 'Matina' },
  { id: 'buhangin', name: 'Buhangin' },
  { id: 'poblacion', name: 'Poblacion' },
  { id: 'agdao', name: 'Agdao' },
]

export function AddEditCameraDialog({
  open,
  onOpenChange,
  camera,
  onSaved,
}: AddEditCameraDialogProps) {
  const isEditing = Boolean(camera?.cameraId)

  const [label, setLabel] = useState('')
  const [areaId, setAreaId] = useState('toril')
  const [location, setLocation] = useState('')
  const [sourceType, setSourceType] = useState<'rtsp' | 'ip'>('rtsp')

  // RTSP Stream URL fields
  const [streamUrl, setStreamUrl] = useState('')
  const [isReplacingStreamUrl, setIsReplacingStreamUrl] = useState(false)

  // IP Camera fields
  const [cameraIp, setCameraIp] = useState('')
  const [rtspPort, setRtspPort] = useState('554')
  const [streamType, setStreamType] = useState('stream2')
  const [username, setUsername] = useState('crashguard')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isReplacingPassword, setIsReplacingPassword] = useState(false)

  const [detectionEnabled, setDetectionEnabled] = useState(true)
  const [isActive, setIsActive] = useState(true)

  // Testing state
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<CameraConnectionResult | null>(null)
  const [testError, setTestError] = useState<string | null>(null)

  // Saving state
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      setTestResult(null)
      setTestError(null)
      setSaveError(null)
      setIsReplacingStreamUrl(false)
      setIsReplacingPassword(false)

      if (camera) {
        setLabel(camera.label || camera.name || '')
        setAreaId(camera.areaId || 'toril')
        setLocation(camera.location || camera.locationDescription || '')
        setDetectionEnabled(camera.detectionEnabled ?? true)
        setIsActive(camera.isActive ?? true)

        if (camera.cameraIp) {
          setSourceType('ip')
          setCameraIp(camera.cameraIp)
          setStreamUrl('')
        } else {
          setSourceType('rtsp')
          setStreamUrl(camera.streamUrl || '')
          setCameraIp('')
        }
      } else {
        setLabel('')
        setAreaId('toril')
        setLocation('')
        setSourceType('rtsp')
        setStreamUrl('')
        setCameraIp('')
        setRtspPort('554')
        setStreamType('stream2')
        setUsername('crashguard')
        setPassword('')
        setDetectionEnabled(true)
        setIsActive(true)
      }
    }
  }, [open, camera])

  const resolveRtspInputUrl = (rawUrl: string, user: string, pass: string): string => {
    let url = rawUrl.trim()
    if (!url) return ''
    if (user.trim() || pass) {
      if (!url.includes('@') && (url.startsWith('rtsp://') || url.startsWith('rtsps://'))) {
        const parts = url.split('://')
        const encUser = encodeURIComponent(user.trim())
        const encPass = encodeURIComponent(pass)
        url = `${parts[0]}://${encUser}:${encPass}@${parts[1]}`
      }
    }
    return url
  }

  const handleTestConnection = async () => {
    setTesting(true)
    setTestResult(null)
    setTestError(null)

    try {
      if (sourceType === 'rtsp') {
        const resolvedUrl = resolveRtspInputUrl(streamUrl, username, password)
        const urlToTest = isEditing && !isReplacingStreamUrl && !streamUrl && camera?.cameraId
          ? ''
          : resolvedUrl

        if (!urlToTest && isEditing && camera?.cameraId) {
          // Test with existing camera ID
          const res = await testCameraConnection('', {
            cameraId: camera.cameraId,
            label: label.trim() || camera.label,
          })
          setTestResult(res)
        } else {
          if (!urlToTest) {
            setTestError('Please provide an RTSP stream URL to test.')
            setTesting(false)
            return
          }
          const res = await testCameraConnection(urlToTest, {
            label: label.trim() || 'New Camera',
            areaId,
            location: location.trim(),
          })
          setTestResult(res)
        }
      } else {
        // IP Camera mode
        const ip = cameraIp.trim()
        if (!ip) {
          setTestError('Please enter the camera IP address.')
          setTesting(false)
          return
        }

        const res = await testCameraConnection(ip, {
          cameraId: isEditing ? camera?.cameraId : undefined,
          label: label.trim() || `Camera ${ip}`,
          areaId,
          location: location.trim(),
          cameraUsername: username.trim() || undefined,
          cameraPassword: password || undefined,
          streamType,
          rtspPort: parseInt(rtspPort, 10) || 554,
        })
        setTestResult(res)
      }
    } catch (err: any) {
      setTestError(err.message || 'Connection test failed. Check network reachability.')
    } finally {
      setTesting(false)
    }
  }

  const handleSave = async () => {
    if (!label.trim()) {
      setSaveError('Camera name is required.')
      return
    }

    if (sourceType === 'rtsp' && !isEditing && !streamUrl.trim()) {
      setSaveError('RTSP Stream URL is required.')
      return
    }

    if (sourceType === 'ip' && !cameraIp.trim()) {
      setSaveError('Camera IP address is required.')
      return
    }

    setSaving(true)
    setSaveError(null)

    try {
      const payload: Partial<CctvCamera> & { label: string; areaId: string } = {
        cameraId: camera?.cameraId,
        label: label.trim(),
        areaId,
        location: location.trim(),
        detectionEnabled,
        isActive,
      }

      if (sourceType === 'rtsp') {
        if (isReplacingStreamUrl || !isEditing) {
          payload.streamUrl = resolveRtspInputUrl(streamUrl, username, password)
        }
        payload.cameraIp = null
        payload.cameraType = 'RTSP Stream'
      } else {
        payload.cameraIp = cameraIp.trim()
        payload.cameraType = 'Tapo RTSP'
        if (password && (isReplacingPassword || !isEditing)) {
          const safeUser = encodeURIComponent(username.trim())
          const safePass = encodeURIComponent(password)
          const port = parseInt(rtspPort, 10) || 554
          payload.streamUrl = `rtsp://${safeUser}:${safePass}@${cameraIp.trim()}:${port}/${streamType}`
        }
      }

      const saved = await saveCctvCamera(payload)
      onSaved(saved)
      onOpenChange(false)
    } catch (err: any) {
      setSaveError(err.message || 'Failed to save camera.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[620px] max-h-[90vh] overflow-y-auto bg-card text-card-foreground border-border shadow-2xl">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-primary/10 text-primary">
              <Camera className="w-5 h-5" />
            </div>
            <div>
              <DialogTitle className="text-xl font-bold">
                {isEditing ? `Edit Camera: ${camera?.label || camera?.name}` : 'Add New CCTV Camera'}
              </DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground mt-0.5">
                Configure network video streaming parameters and test connectivity to live camera infrastructure.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-4 py-2 text-sm">
          {/* Basic Info */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="camera-name" className="text-xs font-semibold">
                Camera Name <span className="text-destructive">*</span>
              </Label>
              <Input
                id="camera-name"
                placeholder="e.g. Toril Intersection CCTV"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                className="h-9"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="camera-area" className="text-xs font-semibold">
                Area / District <span className="text-destructive">*</span>
              </Label>
              <Select value={areaId} onValueChange={setAreaId}>
                <SelectTrigger id="camera-area" className="h-9">
                  <SelectValue placeholder="Select Area" />
                </SelectTrigger>
                <SelectContent>
                  {DEFAULT_AREAS.map((a) => (
                    <SelectItem key={a.id} value={a.id}>
                      {a.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="camera-location" className="text-xs font-semibold">
              Physical Location / Road Description
            </Label>
            <Input
              id="camera-location"
              placeholder="e.g. Crossing Toril, MacArthur Highway"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              className="h-9"
            />
          </div>

          {/* Source Type Selection */}
          <div className="space-y-2 pt-2 border-t border-border">
            <div className="flex items-center justify-between">
              <Label className="text-xs font-semibold">Source Connection Type</Label>
              <div className="flex gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant={sourceType === 'rtsp' ? 'default' : 'outline'}
                  onClick={() => setSourceType('rtsp')}
                  className="h-7 text-xs px-3"
                >
                  <Video className="w-3.5 h-3.5 mr-1.5" />
                  RTSP Stream URL
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant={sourceType === 'ip' ? 'default' : 'outline'}
                  onClick={() => setSourceType('ip')}
                  className="h-7 text-xs px-3"
                >
                  <Shield className="w-3.5 h-3.5 mr-1.5" />
                  Network IP Camera
                </Button>
              </div>
            </div>

            {sourceType === 'rtsp' ? (
              <div className="space-y-2 bg-muted/40 p-3 rounded-lg border border-border">
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="stream-url" className="text-xs font-semibold">
                      RTSP Stream URL
                    </Label>
                    {isEditing && camera?.streamConfigured && !isReplacingStreamUrl && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-6 text-[11px] text-primary"
                        onClick={() => setIsReplacingStreamUrl(true)}
                      >
                        Replace protected URL
                      </Button>
                    )}
                  </div>
                  {isEditing && camera?.streamConfigured && !isReplacingStreamUrl ? (
                    <div className="flex items-center gap-2 p-2 rounded bg-background border text-xs text-muted-foreground">
                      <KeyRound className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                      <span className="font-mono">
                        {camera.streamSourceLabel || 'rtsp://••••:••••@192.168.1.17:554/stream2'}
                      </span>
                      <Badge variant="outline" className="ml-auto text-[10px] text-emerald-600 border-emerald-300">
                        Configured & Protected
                      </Badge>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <Input
                        id="stream-url"
                        placeholder="rtsp://192.168.1.100:554/stream"
                        value={streamUrl}
                        onChange={(e) => setStreamUrl(e.target.value)}
                        className="h-9 font-mono text-xs"
                      />
                      <div className="grid grid-cols-2 gap-2 pt-1">
                        <div className="space-y-1">
                          <Label htmlFor="rtsp-user" className="text-[11px] text-muted-foreground">
                            Username (optional)
                          </Label>
                          <Input
                            id="rtsp-user"
                            placeholder="Optional username"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            className="h-8 text-xs font-mono"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label htmlFor="rtsp-pwd" className="text-[11px] text-muted-foreground">
                            Password (optional)
                          </Label>
                          <Input
                            id="rtsp-pwd"
                            type="password"
                            placeholder="Optional password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            className="h-8 text-xs font-mono"
                          />
                        </div>
                      </div>
                    </div>
                  )}
                  <p className="text-[11px] text-muted-foreground">
                    Accepts rtsp://host:port/path. Credentials entered are protected server-side and never leaked in logs or client-side storage.
                  </p>
                </div>
              </div>
            ) : (
              <div className="space-y-3 bg-muted/40 p-3 rounded-lg border border-border">
                <div className="grid grid-cols-3 gap-2">
                  <div className="col-span-2 space-y-1">
                    <Label htmlFor="ip-addr" className="text-xs font-semibold">
                      Camera IP Address
                    </Label>
                    <Input
                      id="ip-addr"
                      placeholder="192.168.1.17"
                      value={cameraIp}
                      onChange={(e) => setCameraIp(e.target.value)}
                      className="h-8 font-mono text-xs"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="rtsp-port" className="text-xs font-semibold">
                      RTSP Port
                    </Label>
                    <Input
                      id="rtsp-port"
                      placeholder="554"
                      value={rtspPort}
                      onChange={(e) => setRtspPort(e.target.value)}
                      className="h-8 font-mono text-xs"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-2">
                  <div className="space-y-1">
                    <Label htmlFor="ip-user" className="text-xs font-semibold">
                      Username
                    </Label>
                    <Input
                      id="ip-user"
                      placeholder="crashguard"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      className="h-8 text-xs"
                    />
                  </div>
                  <div className="col-span-2 space-y-1">
                    <div className="flex items-center justify-between">
                      <Label htmlFor="ip-pass" className="text-xs font-semibold">
                        Password
                      </Label>
                      {isEditing && !isReplacingPassword && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-5 text-[10px] text-primary p-0"
                          onClick={() => setIsReplacingPassword(true)}
                        >
                          Change password
                        </Button>
                      )}
                    </div>
                    {isEditing && !isReplacingPassword ? (
                      <div className="flex items-center gap-2 px-3 py-1.5 rounded bg-background border text-xs text-muted-foreground font-mono">
                        <span>••••••••</span>
                        <Badge variant="outline" className="ml-auto text-[10px] text-emerald-600 border-emerald-300">
                          Saved
                        </Badge>
                      </div>
                    ) : (
                      <div className="relative">
                        <Input
                          id="ip-pass"
                          type={showPassword ? 'text' : 'password'}
                          placeholder="Camera password"
                          value={password}
                          onChange={(e) => setPassword(e.target.value)}
                          className="h-8 text-xs pr-8"
                        />
                        <button
                          type="button"
                          onClick={() => setShowPassword(!showPassword)}
                          className="absolute right-2 top-2 text-muted-foreground hover:text-foreground"
                        >
                          {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Operational Toggles */}
          <div className="flex items-center justify-between p-3 rounded-lg bg-muted/20 border border-border">
            <div className="flex items-center gap-2">
              <Switch
                id="active-toggle"
                checked={isActive}
                onCheckedChange={setIsActive}
              />
              <Label htmlFor="active-toggle" className="text-xs cursor-pointer font-medium">
                Camera Enabled (Acquire frames & monitor)
              </Label>
            </div>

            <div className="flex items-center gap-2">
              <Switch
                id="detect-toggle"
                checked={detectionEnabled}
                onCheckedChange={setDetectionEnabled}
              />
              <Label htmlFor="detect-toggle" className="text-xs cursor-pointer font-medium">
                AI Detection Enabled
              </Label>
            </div>
          </div>

          {/* Test Connection Button & Result Box */}
          <div className="space-y-2 pt-2 border-t border-border">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">
                Verify decodable video stream before saving:
              </span>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleTestConnection}
                disabled={testing}
                className="h-8 text-xs font-semibold"
              >
                {testing ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                    Connecting to Stream...
                  </>
                ) : (
                  <>
                    <Video className="w-3.5 h-3.5 mr-1.5 text-primary" />
                    Test Connection
                  </>
                )}
              </Button>
            </div>

            {testResult && (
              <div
                className={`p-3 rounded-lg border text-xs flex items-start gap-2.5 ${
                  testResult.connected
                    ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-700 dark:text-emerald-300'
                    : 'bg-destructive/10 border-destructive/30 text-destructive dark:text-rose-400'
                }`}
              >
                {testResult.connected ? (
                  <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0 text-emerald-600 dark:text-emerald-400" />
                ) : (
                  <XCircle className="w-4 h-4 mt-0.5 shrink-0 text-destructive dark:text-rose-400" />
                )}
                <div className="space-y-0.5">
                  <div className="font-semibold flex items-center gap-2">
                    <span>{testResult.message}</span>
                    {testResult.width && testResult.height && (
                      <Badge variant="outline" className="text-[10px] bg-background/50 font-mono">
                        {testResult.width}x{testResult.height}
                      </Badge>
                    )}
                  </div>
                  {testResult.status && (
                    <div className="text-[11px] opacity-90">
                      Status Code: <span className="font-mono font-semibold">{testResult.status}</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {testError && (
              <div className="p-3 rounded-lg border border-destructive/30 bg-destructive/10 text-destructive dark:text-rose-400 text-xs flex items-start gap-2.5">
                <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                <div className="space-y-0.5">
                  <div className="font-semibold">Connection Failed</div>
                  <div>{testError}</div>
                </div>
              </div>
            )}

            {saveError && (
              <div className="p-2.5 rounded border border-destructive/30 bg-destructive/10 text-destructive text-xs flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{saveError}</span>
              </div>
            )}
          </div>
        </div>

        <DialogFooter className="gap-2 sm:gap-0 pt-2 border-t border-border">
          <Button
            type="button"
            variant="ghost"
            onClick={() => onOpenChange(false)}
            disabled={saving}
            className="h-9 text-xs"
          >
            Cancel
          </Button>
          <Button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="h-9 text-xs font-semibold px-4"
          >
            {saving ? (
              <>
                <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                Saving to PostgreSQL...
              </>
            ) : isEditing ? (
              'Save Changes'
            ) : (
              'Add & Enable Camera'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
