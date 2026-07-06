'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useTheme } from 'next-themes'

import { Sidebar, DashboardHeader } from '@/components/dashboard-sidebar'
import { PermissionMessage } from '@/components/permission-message'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  LogOut,
  RotateCcw,
  Save,
  Settings2,
} from 'lucide-react'
import {
  BACKEND_URL,
  BACKEND_URL_SOURCE,
  CameraSettings,
  IS_DEFAULT_BACKEND_URL,
  checkBackendHealth,
  getCameraSettings,
  saveCameraSettings,
} from '@/lib/api-client'
import { useAuth } from '@/components/auth-provider'
import { useDisplayMode } from '@/lib/display-mode'

export default function SettingsPage() {
  const router = useRouter()
  const { profile, signOutUser } = useAuth()
  const { canUseAdvanced, isAdvancedMode, mode, setMode } = useDisplayMode(profile)
  const { setTheme, theme, resolvedTheme } = useTheme()
  const normalizedRole = String(profile?.role ?? '').toLowerCase()
  const activeTheme = theme === 'system' ? resolvedTheme : theme
  const [isSigningOut, setIsSigningOut] = useState(false)
  const [backendStatus, setBackendStatus] = useState<
    'checking' | 'reachable' | 'unreachable'
  >('checking')
  const [healthTimestamp, setHealthTimestamp] = useState<string | null>(null)
  const [cameraSettings, setCameraSettings] = useState<CameraSettings>({
    cameraLabel: 'Tapo Camera',
    streamType: 'stream1',
    rtspPort: 554,
  })
  const [cameraPassword, setCameraPassword] = useState('')
  const [cameraSettingsMessage, setCameraSettingsMessage] = useState('')
  const [cameraSettingsSaving, setCameraSettingsSaving] = useState(false)

  useEffect(() => {
    if (normalizedRole !== 'admin') {
      return
    }

    let cancelled = false

    async function loadBackendHealth() {
      const health = await checkBackendHealth()

      if (cancelled) {
        return
      }

      if (health.status === 'ok') {
        setBackendStatus('reachable')
        setHealthTimestamp(health.timestamp)
        return
      }

      setBackendStatus('unreachable')
      setHealthTimestamp(null)
    }

    void loadBackendHealth()

    async function loadCameraSettings() {
      try {
        const settings = await getCameraSettings()
        if (!cancelled) {
          setCameraSettings(settings)
        }
      } catch {
        if (!cancelled) {
          setCameraSettingsMessage('Camera settings are unavailable until the backend is running.')
        }
      }
    }

    void loadCameraSettings()

    return () => {
      cancelled = true
    }
  }, [normalizedRole])

  const updateCameraSetting = (key: keyof CameraSettings, value: string | number) => {
    setCameraSettings((current) => ({ ...current, [key]: value }))
  }

  const handleSaveCameraSettings = async () => {
    setCameraSettingsSaving(true)
    setCameraSettingsMessage('')
    try {
      const saved = await saveCameraSettings({
        ...cameraSettings,
        cameraPassword: cameraPassword || undefined,
        rtspPort: Number(cameraSettings.rtspPort || 554),
      })
      setCameraSettings(saved)
      setCameraPassword('')
      setCameraSettingsMessage('Admin Camera Settings saved for this local demo.')
    } catch (error) {
      setCameraSettingsMessage(
        error instanceof Error ? error.message : 'Could not save Admin Camera Settings.'
      )
    } finally {
      setCameraSettingsSaving(false)
    }
  }

  const handleSignOut = async () => {
    setIsSigningOut(true)
    try {
      await signOutUser()
      router.replace('/login')
    } finally {
      setIsSigningOut(false)
    }
  }

  const backendStatusIndicatorClass =
    backendStatus === 'reachable'
      ? 'bg-[var(--status-online)]'
      : backendStatus === 'unreachable'
        ? 'bg-destructive'
        : 'bg-[var(--status-warning)]'
  const backendStatusLabel =
    backendStatus === 'reachable'
      ? 'Health check passed'
      : backendStatus === 'unreachable'
        ? 'Health check failed'
        : 'Checking backend health'
  const backendStatusBadge =
    backendStatus === 'reachable'
      ? 'Reachable'
      : backendStatus === 'unreachable'
        ? 'Not reachable'
        : 'Checking'

  if (normalizedRole === 'responder') {
    return (
      <div className="flex min-h-screen bg-background">
        <Sidebar />
        <div className="flex-1 md:ml-0">
          <DashboardHeader />

          <main className="space-y-6 p-6">
            <div>
              <h1 className="text-3xl font-bold">Settings</h1>
              <p className="text-muted-foreground">
                Manage your responder display and account options.
              </p>
            </div>

            <div className="max-w-2xl space-y-6">
              <Card className="border border-border bg-card/70 p-6">
                <div className="border-b border-border pb-4">
                  <h2 className="text-xl font-semibold">Appearance</h2>
                </div>

                <div className="mt-4 space-y-3">
                  <Label className="text-sm font-semibold">Theme</Label>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Button
                      type="button"
                      variant={activeTheme === 'light' ? 'default' : 'outline'}
                      className="justify-start"
                      onClick={() => setTheme('light')}
                    >
                      Light Mode
                    </Button>
                    <Button
                      type="button"
                      variant={activeTheme === 'dark' ? 'default' : 'outline'}
                      className="justify-start"
                      onClick={() => setTheme('dark')}
                    >
                      Dark Mode
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Theme changes apply across responder dashboard pages.
                  </p>
                </div>
              </Card>

              <Card className="border border-border bg-card/70 p-6">
                <div className="border-b border-border pb-4">
                  <h2 className="text-xl font-semibold">Account</h2>
                </div>

                <div className="mt-4 space-y-3">
                  <p className="text-sm text-muted-foreground">
                    Sign out of this responder session.
                  </p>
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button type="button" variant="outline" className="gap-2" disabled={isSigningOut}>
                        <LogOut className="h-4 w-4" />
                        Sign Out
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent className="sm:max-w-md">
                      <AlertDialogHeader className="items-center gap-3 text-center">
                        <AlertDialogTitle>Are you sure you want to logout?</AlertDialogTitle>
                        <AlertDialogDescription className="max-w-sm text-center">
                          You will need to sign in again to access the dashboard.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter className="mt-2 gap-5 sm:justify-center">
                        <AlertDialogCancel>No</AlertDialogCancel>
                        <AlertDialogAction onClick={handleSignOut} disabled={isSigningOut}>
                          Yes
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              </Card>
            </div>
          </main>
        </div>
      </div>
    )
  }

  if (normalizedRole !== 'admin') {
    return <PermissionMessage />
  }

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <div className="flex-1 md:ml-0">
        <DashboardHeader />

        <main className="p-6 space-y-6 max-w-2xl">
          <div>
            <h1 className="text-3xl font-bold mb-2">Settings</h1>
            <p className="text-muted-foreground">
              Configure camera, alert, and system preferences.
            </p>
          </div>

          <Card className="border border-border bg-card/70 p-6 space-y-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-xl font-semibold">Configuration Mode</h2>
                <p className="text-sm text-muted-foreground">
                  Simple Mode keeps everyday settings clear. Advanced Mode shows technical diagnostics.
                </p>
              </div>
              {canUseAdvanced ? (
                <div className="flex rounded-md border border-border p-1">
                  <Button
                    type="button"
                    size="sm"
                    variant={mode === 'simple' ? 'default' : 'ghost'}
                    onClick={() => setMode('simple')}
                  >
                    Simple Mode
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant={mode === 'advanced' ? 'default' : 'ghost'}
                    onClick={() => setMode('advanced')}
                  >
                    Advanced Mode
                  </Button>
                </div>
              ) : (
                <Badge variant="outline">Simple Mode</Badge>
              )}
            </div>
          </Card>

          {/* API Configuration */}
          {isAdvancedMode ? (
          <Card className="border border-border bg-card/70 p-6 space-y-4">
            <div className="flex items-center gap-3 pb-4 border-b border-border">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                <Settings2 className="w-5 h-5 text-primary" />
              </div>
              <h2 className="text-xl font-semibold">Backend Configuration</h2>
            </div>

            <div className="space-y-4">
              <div>
                <Label className="text-sm font-semibold mb-2 block">Backend URL</Label>
                <Input
                  defaultValue={BACKEND_URL}
                  readOnly
                  className="bg-muted border-border"
                />
                <p className="text-xs text-muted-foreground mt-2">
                  Active source: {BACKEND_URL_SOURCE}. Set `NEXT_PUBLIC_BACKEND_URL`
                  in `.env.local` to point the frontend at the intended FastAPI server.
                </p>
                {IS_DEFAULT_BACKEND_URL ? (
                  <p className="mt-2 text-xs text-[var(--status-warning)]">
                    No `NEXT_PUBLIC_BACKEND_URL` is set right now, so the app is using the
                    fallback `http://localhost:8000`. That only works if this browser can
                    reach the FastAPI server on the same machine.
                  </p>
                ) : null}
              </div>

              <div>
                <Label className="text-sm font-semibold mb-2 block">Backend Status</Label>
                <div className="flex items-center gap-3">
                  <div className={`w-2 h-2 rounded-full ${backendStatusIndicatorClass}`} />
                  <span className="text-sm font-medium">
                    {backendStatusLabel}
                  </span>
                  <Badge variant="outline" className="ml-auto">
                    {backendStatusBadge}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  {backendStatus === 'reachable'
                    ? `Confirmed with GET /api/health at ${new Date(
                        healthTimestamp ?? ''
                      ).toLocaleString()}.`
                    : 'This check only confirms API reachability. It does not prove the browser upload flow end-to-end.'}
                </p>
              </div>

              <div className="rounded-lg border border-border bg-card/50 p-4 space-y-3">
                <div className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 text-[var(--status-online)]" />
                  <div>
                    <p className="text-sm font-semibold">Backend image detection</p>
                    <p className="text-xs text-muted-foreground">
                      Fresh local validation on April 21, 2026 confirmed that
                      `backend/main.py` starts, `POST /api/detect/image` returns a
                      successful JSON response, and the annotated image URL serves a file.
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3">
                  {backendStatus === 'checking' ? (
                    <Loader2 className="mt-0.5 h-4 w-4 animate-spin text-[var(--status-warning)]" />
                  ) : (
                    <AlertTriangle className="mt-0.5 h-4 w-4 text-[var(--status-warning)]" />
                  )}
                  <div>
                    <p className="text-sm font-semibold">Browser upload validation</p>
                    <p className="text-xs text-muted-foreground">
                      Manual browser confirmation is still required for the full Upload
                      page flow. A health check is not the same as selecting an image in
                      the UI, running detection, and visually confirming the returned
                      annotated image preview in the browser.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </Card>
          ) : null}

          <Card id="admin-camera-settings" className="border border-border bg-card/70 p-6 space-y-4">
            <div className="flex items-center gap-3 border-b border-border pb-4">
              <h2 className="text-xl font-semibold">Admin Camera Settings</h2>
            </div>

            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Tapo cameras need RTSP enabled and a camera account. These values are
                stored in a local backend config file for the school demo and are not
                committed to git.
              </p>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <Label className="text-sm font-semibold mb-2 block">Camera label</Label>
                  <Input
                    value={cameraSettings.cameraLabel ?? ''}
                    onChange={(event) => updateCameraSetting('cameraLabel', event.target.value)}
                    placeholder="Tapo Front Gate"
                  />
                </div>
                <div>
                  <Label className="text-sm font-semibold mb-2 block">IP address</Label>
                  <Input
                    value={cameraSettings.cameraIp ?? ''}
                    onChange={(event) => updateCameraSetting('cameraIp', event.target.value)}
                    placeholder="192.168.1.34"
                    inputMode="decimal"
                  />
                </div>
                <div>
                  <Label className="text-sm font-semibold mb-2 block">Area/location</Label>
                  <Input
                    value={cameraSettings.location ?? ''}
                    onChange={(event) => updateCameraSetting('location', event.target.value)}
                    placeholder="Gate 1 / Talomo"
                  />
                </div>
                <div>
                  <Label className="text-sm font-semibold mb-2 block">Area ID</Label>
                  <Input
                    value={cameraSettings.areaId ?? ''}
                    onChange={(event) => updateCameraSetting('areaId', event.target.value)}
                    placeholder="talomo"
                  />
                </div>
                {isAdvancedMode ? (
                <div>
                  <Label className="text-sm font-semibold mb-2 block">Username</Label>
                  <Input
                    value={cameraSettings.cameraUsername ?? ''}
                    onChange={(event) => updateCameraSetting('cameraUsername', event.target.value)}
                    placeholder="Camera account username"
                  />
                </div>
                ) : null}
                {isAdvancedMode ? (
                <div>
                  <Label className="text-sm font-semibold mb-2 block">Password</Label>
                  <Input
                    value={cameraPassword}
                    onChange={(event) => setCameraPassword(event.target.value)}
                    placeholder={
                      cameraSettings.cameraPasswordConfigured
                        ? 'Password saved locally'
                        : 'Camera account password'
                    }
                    type="password"
                  />
                </div>
                ) : null}
                {isAdvancedMode ? (
                <div>
                  <Label className="text-sm font-semibold mb-2 block">Stream type</Label>
                  <Select
                    value={cameraSettings.streamType ?? 'stream1'}
                    onValueChange={(value) => updateCameraSetting('streamType', value)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="stream1">stream1</SelectItem>
                      <SelectItem value="stream2">stream2</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                ) : null}
                {isAdvancedMode ? (
                <div>
                  <Label className="text-sm font-semibold mb-2 block">Port</Label>
                  <Input
                    value={String(cameraSettings.rtspPort ?? 554)}
                    onChange={(event) => updateCameraSetting('rtspPort', event.target.value)}
                    placeholder="554"
                    inputMode="numeric"
                  />
                </div>
                ) : null}
              </div>

              {cameraSettingsMessage ? (
                <p className="text-sm text-muted-foreground">{cameraSettingsMessage}</p>
              ) : null}

              <Button
                type="button"
                className="flex gap-2"
                onClick={() => void handleSaveCameraSettings()}
                disabled={cameraSettingsSaving}
              >
                {cameraSettingsSaving ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Save className="h-4 w-4" />
                )}
                Save Admin Camera Settings
              </Button>
            </div>
          </Card>

          <Card className="border border-border bg-card/70 p-6 space-y-4">
            <div className="flex items-center gap-3 border-b border-border pb-4">
              <h2 className="text-xl font-semibold">Appearance</h2>
            </div>

            <div className="space-y-2">
              <Label htmlFor="theme-mode" className="text-sm font-semibold">
                Theme
              </Label>
              <Select value={theme ?? 'dark'} onValueChange={setTheme}>
                <SelectTrigger id="theme-mode" className="w-full">
                  <SelectValue placeholder="Choose theme" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="dark">Dark</SelectItem>
                  <SelectItem value="light">Light</SelectItem>
                  <SelectItem value="system">System</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Layout, spacing, controls, and workflow stay the same. Only theme colors change.
              </p>
            </div>
          </Card>

          {/* Detection Settings */}
          <Card className="border border-border bg-card/70 p-6 space-y-4">
            <div className="flex items-center gap-3 pb-4 border-b border-border">
              <h2 className="text-xl font-semibold">Detection Settings</h2>
            </div>

            <div className="space-y-4">
              {isAdvancedMode ? (
              <div>
                <Label className="text-sm font-semibold mb-2 block">Confidence Threshold</Label>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min="0"
                    max="100"
                    defaultValue="60"
                    className="flex-1"
                  />
                  <span className="text-sm font-semibold w-12 text-right">60%</span>
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  Minimum confidence level to create a possible crash review case.
                </p>
              </div>
              ) : null}

              <div className="flex items-center justify-between p-3 bg-card/50 rounded border border-border/50">
                <div>
                  <p className="text-sm font-semibold">Alert Sound</p>
                  <p className="text-xs text-muted-foreground">Enable audio notifications</p>
                </div>
                <input type="checkbox" defaultChecked className="w-5 h-5" />
              </div>

              <div className="flex items-center justify-between p-3 bg-card/50 rounded border border-border/50">
                <div>
                  <p className="text-sm font-semibold">Push Notifications</p>
                  <p className="text-xs text-muted-foreground">Browser notifications</p>
                </div>
                <input type="checkbox" defaultChecked className="w-5 h-5" />
              </div>
            </div>
          </Card>

          {/* Model Information */}
          {isAdvancedMode ? (
          <Card className="border border-border bg-card/70 p-6 space-y-4">
            <div className="flex items-center gap-3 pb-4 border-b border-border">
              <h2 className="text-xl font-semibold">AI Model Info</h2>
            </div>

            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Model Type</span>
                <Badge variant="outline">YOLOv8 / YOLO11</Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Supported Input</span>
                <span className="text-sm font-medium">Images, Videos</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Output Classes</span>
                <span className="text-sm font-medium">Accident, Vehicle</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Backend Framework</span>
                <Badge variant="outline">FastAPI</Badge>
              </div>
            </div>
          </Card>
          ) : null}

          {/* System Info */}
          {isAdvancedMode ? (
          <Card className="border border-border bg-card/70 p-6 space-y-4">
            <h2 className="text-xl font-semibold pb-4 border-b border-border">System Info</h2>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Frontend Version</span>
                <span className="font-medium">1.0.0</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Framework</span>
                <span className="font-medium">Next.js 16 + TypeScript</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">UI Library</span>
                <span className="font-medium">shadcn/ui + Tailwind CSS</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Maps</span>
                <span className="font-medium">Leaflet.js</span>
              </div>
            </div>
          </Card>
          ) : null}

          {/* Integration Instructions */}
          {isAdvancedMode ? (
          <Card className="border border-accent/50 bg-accent/10 p-6 space-y-4">
            <h2 className="text-lg font-semibold">FastAPI Backend Integration</h2>
            <div className="text-sm space-y-3 text-muted-foreground">
              <p>
                This frontend connects to a FastAPI backend for YOLO-based accident detection.
              </p>
              <p className="font-semibold text-foreground">Required Endpoints:</p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li>POST /api/detect/image - Detect accidents in images</li>
                <li>POST /api/detect/video - Detect accidents in videos</li>
                <li>GET /api/incidents - List all detected incidents</li>
                <li>GET /api/notifications - Get notifications</li>
                <li>GET /api/health - Backend health check</li>
              </ul>
              <p className="pt-2">
                Set NEXT_PUBLIC_BACKEND_URL to your FastAPI server URL in environment variables.
              </p>
            </div>
          </Card>
          ) : null}

          {/* Action Buttons */}
          <div className="flex gap-3 pt-4">
            <Button className="flex gap-2">
              <Save className="w-4 h-4" />
              Save Settings
            </Button>
            <Button variant="outline" className="flex gap-2">
              <RotateCcw className="w-4 h-4" />
              Reset to Defaults
            </Button>
          </div>
        </main>
      </div>
    </div>
  )
}
