'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useTheme } from 'next-themes'
import {
  AlertCircle,
  AlertTriangle,
  Bell,
  Check,
  CheckCircle2,
  Clock,
  Copy,
  ExternalLink,
  Headset,
  KeyRound,
  Lock,
  MapPin,
  Monitor,
  Moon,
  Navigation,
  Play,
  Radio,
  RefreshCw,
  RotateCcw,
  Save,
  ShieldAlert,
  ShieldCheck,
  Square,
  Sun,
  User,
  UserCheck,
  Volume2,
  VolumeX,
  Wifi,
} from 'lucide-react'

import { useAuth } from '@/components/auth-provider'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useToast } from '@/hooks/use-toast'
import { isPersonalTheme } from '@/lib/personal-settings'
import { phase3, type PersonalTheme } from '@/lib/phase3-api'

interface PersonalSettingsPageProps {
  role?: 'dispatcher' | 'responder' | 'admin'
}

export function PersonalSettingsPage({ role: explicitRole }: PersonalSettingsPageProps) {
  const { profile, setPersonalPreferences, setSessionUser } = useAuth()
  const { setTheme, theme, resolvedTheme } = useTheme()
  const { toast } = useToast()

  const activeRole = (explicitRole || profile?.role?.toLowerCase() || 'dispatcher') as
    | 'dispatcher'
    | 'responder'
    | 'admin'

  // Form states
  const [fullName, setFullName] = useState(profile?.displayName ?? '')
  const [selectedTheme, setSelectedTheme] = useState<PersonalTheme>('system')
  const [alertNotifications, setAlertNotifications] = useState(true)
  const [browserNotifications, setBrowserNotifications] = useState(true)
  const [emailNotifications, setEmailNotifications] = useState(false)
  const [alarmAudio, setAlarmAudio] = useState(true)

  // Initial baseline states for dirty checking
  const [initialFullName, setInitialFullName] = useState(profile?.displayName ?? '')
  const [initialTheme, setInitialTheme] = useState<PersonalTheme>('system')
  const [initialAlertNotifications, setInitialAlertNotifications] = useState(true)
  const [initialBrowserNotifications, setInitialBrowserNotifications] = useState(true)
  const [initialEmailNotifications, setInitialEmailNotifications] = useState(false)
  const [initialAlarmAudio, setInitialAlarmAudio] = useState(true)

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [successMessage, setSuccessMessage] = useState('')

  // Browser notification permissions state
  const [browserPermission, setBrowserPermission] = useState<NotificationPermission>('default')

  // Audio testing player state
  const [isPlayingAudio, setIsPlayingAudio] = useState(false)
  const [audioBlocked, setAudioBlocked] = useState(false)
  const audioInstanceRef = useRef<HTMLAudioElement | null>(null)

  const [themeSaving, setThemeSaving] = useState(false)

  // Load initial preferences
  useEffect(() => {
    setFullName(profile?.displayName ?? '')
    setInitialFullName(profile?.displayName ?? '')
  }, [profile?.displayName, profile?.uid])

  useEffect(() => {
    if (typeof window !== 'undefined' && 'Notification' in window) {
      setBrowserPermission(Notification.permission)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    void phase3
      .ownPreferences()
      .then(({ preferences }) => {
        if (cancelled) return
        const storedTheme = isPersonalTheme(preferences.theme) ? preferences.theme : 'system'
        setSelectedTheme(storedTheme)
        setInitialTheme(storedTheme)
        setTheme(storedTheme)

        const alertNotifs = preferences.notificationPreferences?.alertNotifications ?? true
        const browserNotifs = preferences.notificationPreferences?.browserNotifications ?? true
        const emailNotifs = preferences.notificationPreferences?.emailNotifications ?? false
        const alarmAud = preferences.notificationPreferences?.alarmAudio ?? true

        setAlertNotifications(alertNotifs)
        setInitialAlertNotifications(alertNotifs)

        setBrowserNotifications(browserNotifs)
        setInitialBrowserNotifications(browserNotifs)

        setEmailNotifications(emailNotifs)
        setInitialEmailNotifications(emailNotifs)

        setAlarmAudio(alarmAud)
        setInitialAlarmAudio(alarmAud)
      })
      .catch((caught) => {
        if (cancelled) return
        const localTheme = isPersonalTheme(theme) ? theme : 'system'
        setSelectedTheme(localTheme)
        setInitialTheme(localTheme)
        setErrorMessage(caught instanceof Error ? caught.message : 'Could not load preferences.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [profile?.uid, setTheme])

  // Audio Cleanup
  useEffect(() => {
    return () => {
      if (audioInstanceRef.current) {
        audioInstanceRef.current.pause()
        audioInstanceRef.current = null
      }
    }
  }, [])

  // Check if form is dirty
  const isDirty =
    fullName.trim() !== initialFullName.trim() ||
    selectedTheme !== initialTheme ||
    alertNotifications !== initialAlertNotifications ||
    browserNotifications !== initialBrowserNotifications ||
    emailNotifications !== initialEmailNotifications ||
    alarmAudio !== initialAlarmAudio

  const handleDiscard = () => {
    setFullName(initialFullName)
    setSelectedTheme(initialTheme)
    setTheme(initialTheme)
    setAlertNotifications(initialAlertNotifications)
    setBrowserNotifications(initialBrowserNotifications)
    setEmailNotifications(initialEmailNotifications)
    setAlarmAudio(initialAlarmAudio)
    setErrorMessage('')
    setSuccessMessage('')
    toast({
      title: 'Changes discarded',
      description: 'Preferences reverted to last saved state.',
    })
  }

  const chooseTheme = async (nextTheme: PersonalTheme) => {
    if (themeSaving) return
    setSelectedTheme(nextTheme)
    setTheme(nextTheme)
    setThemeSaving(true)
    try {
      const { preferences } = await phase3.updateOwnPreferences({ theme: nextTheme })
      setPersonalPreferences(preferences)
      setInitialTheme(nextTheme)
      toast({
        title: 'Theme updated',
        description: `Theme set to ${
          nextTheme === 'system' ? 'System Default' : nextTheme === 'dark' ? 'Dark' : 'Light'
        }.`,
      })
    } catch {
      toast({
        title: 'Theme applied locally',
        description: 'Applied in browser; will synchronize to server on full save.',
      })
    } finally {
      setThemeSaving(false)
    }
  }

  const handleCopy = async (text: string, label: string) => {
    try {
      await navigator.clipboard.writeText(text)
      toast({
        title: 'Copied to clipboard',
        description: `${label}: ${text.slice(0, 16)}...`,
      })
    } catch {
      toast({
        title: 'Unable to copy',
        description: 'Clipboard access was denied by browser.',
        variant: 'destructive',
      })
    }
  }

  // Siren Audio Testing
  const toggleAudioTest = () => {
    if (isPlayingAudio && audioInstanceRef.current) {
      audioInstanceRef.current.pause()
      audioInstanceRef.current.currentTime = 0
      setIsPlayingAudio(false)
      return
    }

    try {
      if (!audioInstanceRef.current) {
        audioInstanceRef.current = new Audio('/alert-sound.mp3')
        audioInstanceRef.current.onended = () => setIsPlayingAudio(false)
      }
      audioInstanceRef.current.currentTime = 0
      const playPromise = audioInstanceRef.current.play()
      if (playPromise !== undefined) {
        playPromise
          .then(() => {
            setIsPlayingAudio(true)
            setAudioBlocked(false)
          })
          .catch(() => {
            setAudioBlocked(true)
            setIsPlayingAudio(false)
            toast({
              title: 'Audio playback restricted',
              description: 'Please interact with the document to grant autoplay sound permissions.',
              variant: 'destructive',
            })
          })
      }
    } catch {
      setAudioBlocked(true)
      setIsPlayingAudio(false)
    }
  }

  // Request browser desktop notification permissions
  const requestNotificationPermission = async () => {
    if (typeof window === 'undefined' || !('Notification' in window)) {
      toast({
        title: 'Notifications unsupported',
        description: 'Your browser does not support desktop notifications.',
        variant: 'destructive',
      })
      return
    }

    try {
      const permission = await Notification.requestPermission()
      setBrowserPermission(permission)
      if (permission === 'granted') {
        toast({
          title: 'Notifications authorized',
          description: 'Browser desktop notifications are now enabled for urgent collision alerts.',
        })
      } else {
        toast({
          title: 'Notifications blocked',
          description: 'Permission was not granted. Check your browser site settings.',
          variant: 'destructive',
        })
      }
    } catch {
      toast({
        title: 'Request failed',
        description: 'Unable to prompt for notification permission.',
        variant: 'destructive',
      })
    }
  }

  const sendTestNotification = () => {
    if (typeof window === 'undefined' || !('Notification' in window)) return
    if (Notification.permission !== 'granted') {
      void requestNotificationPermission()
      return
    }

    try {
      new Notification('CrashGuard Emergency Alert [TEST]', {
        body:
          activeRole === 'dispatcher'
            ? 'New collision detected: Shaw Blvd & EDSA. Priority 1 triage required.'
            : 'New emergency dispatch assigned: Unit 104 en route to scene.',
        icon: '/favicon.ico',
      })
      toast({
        title: 'Test alert sent',
        description: 'Check your system desktop notification banner.',
      })
    } catch {
      toast({
        title: 'Test failed',
        description: 'Browser blocked displaying the notification.',
        variant: 'destructive',
      })
    }
  }

  // Save changes
  const saveChanges = async () => {
    if (!fullName.trim()) {
      setErrorMessage('Full name cannot be left blank.')
      return
    }

    setSaving(true)
    setErrorMessage('')
    setSuccessMessage('')

    try {
      const [{ user }, { preferences }] = await Promise.all([
        phase3.updateOwnProfile(fullName.trim()),
        phase3.updateOwnPreferences({
          theme: selectedTheme,
          notificationPreferences: {
            alertNotifications,
            browserNotifications,
            emailNotifications,
            alarmAudio,
          },
        }),
      ])

      setSessionUser(user)
      setPersonalPreferences(preferences)

      setInitialFullName(fullName.trim())
      setInitialTheme(selectedTheme)
      setInitialAlertNotifications(alertNotifications)
      setInitialBrowserNotifications(browserNotifications)
      setInitialEmailNotifications(emailNotifications)
      setInitialAlarmAudio(alarmAudio)

      setSuccessMessage('Operational preferences and profile successfully updated.')
      toast({
        title: 'Settings saved',
        description: 'Your profile and emergency operational preferences have been updated.',
      })
    } catch (caught) {
      const msg = caught instanceof Error ? caught.message : 'Failed to synchronize settings.'
      setErrorMessage(msg)
      toast({
        title: 'Error saving settings',
        description: msg,
        variant: 'destructive',
      })
    } finally {
      setSaving(false)
    }
  }

  const roleTitle =
    activeRole === 'dispatcher'
      ? 'Emergency Dispatch Controller'
      : activeRole === 'responder'
      ? 'Field Emergency Responder'
      : 'System Administrator'

  const roleSubtitle =
    activeRole === 'dispatcher'
      ? 'Manage central triage console preferences, siren thresholds, and workstation notifications.'
      : activeRole === 'responder'
      ? 'Manage mobile field response settings, dispatch siren alarms, and presence telemetry.'
      : 'Manage administrative identity and system monitoring notifications.'

  const initials = (profile?.displayName || 'CrashGuard User')
    .split(' ')
    .filter(Boolean)
    .map((n) => n[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()

  return (
    <div className="space-y-6 max-w-5xl pb-16">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
            {activeRole === 'dispatcher'
              ? 'Dispatcher Settings'
              : activeRole === 'responder'
              ? 'Responder Settings'
              : 'Personal Settings'}
          </h1>
          <p className="text-sm text-muted-foreground">{roleSubtitle}</p>
        </div>

        {isDirty ? (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleDiscard}
              disabled={saving || loading}
              className="h-9 gap-1.5"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              <span>Discard</span>
            </Button>
            <Button
              size="sm"
              onClick={() => void saveChanges()}
              disabled={saving || loading}
              className="h-9 gap-1.5 bg-primary text-primary-foreground"
            >
              <Save className={`h-3.5 w-3.5 ${saving ? 'animate-spin' : ''}`} />
              <span>{saving ? 'Saving...' : 'Save Changes'}</span>
            </Button>
          </div>
        ) : null}
      </div>

      {/* Operator Identity Hero Card */}
      <Card className="border border-border bg-card p-5 shadow-xs">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary font-mono text-xl font-bold border border-primary/20">
              {initials || 'CG'}
            </div>
            <div className="space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-lg font-bold text-foreground">
                  {profile?.displayName || 'Authenticated Operator'}
                </h2>
                <Badge
                  variant="outline"
                  className="border-primary/40 bg-primary/10 text-primary font-semibold text-xs gap-1 py-0.5"
                >
                  {activeRole === 'dispatcher' ? (
                    <Headset className="h-3 w-3" />
                  ) : activeRole === 'responder' ? (
                    <Navigation className="h-3 w-3" />
                  ) : (
                    <ShieldCheck className="h-3 w-3" />
                  )}
                  {roleTitle}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground font-mono">{profile?.email}</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2.5 pt-2 sm:pt-0 border-t sm:border-t-0 border-border">
            {/* Area Jurisdiction Badge */}
            <div className="flex items-center gap-1.5 rounded-md border border-border bg-muted/40 px-2.5 py-1 text-xs text-muted-foreground">
              <MapPin className="h-3.5 w-3.5 text-primary" />
              <span className="font-medium text-foreground">
                {profile?.areaId ? `Sector: ${profile.areaId}` : 'Jurisdiction: All Districts'}
              </span>
            </div>

            {/* Responder Presence Badge */}
            {activeRole === 'responder' ? (
              <div className="flex items-center gap-1.5 rounded-md border border-emerald-300 bg-emerald-50 px-2.5 py-1 text-xs text-emerald-700 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-400 font-medium">
                <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                <span>Live Presence Active</span>
              </div>
            ) : null}

            {/* Account ID Copy */}
            {profile?.uid ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => void handleCopy(profile.uid, 'User ID')}
                className="h-8 gap-1.5 text-xs text-muted-foreground hover:text-foreground font-mono"
                title="Copy Operator Account UUID"
              >
                <Copy className="h-3 w-3" />
                <span>UID: {profile.uid.slice(0, 8)}...</span>
              </Button>
            ) : null}
          </div>
        </div>
      </Card>

      {/* Messages */}
      {errorMessage ? (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Validation Error</AlertTitle>
          <AlertDescription>{errorMessage}</AlertDescription>
        </Alert>
      ) : null}

      {successMessage ? (
        <Alert className="border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-300">
          <CheckCircle2 className="h-4 w-4" />
          <AlertTitle>Preferences Updated</AlertTitle>
          <AlertDescription>{successMessage}</AlertDescription>
        </Alert>
      ) : null}

      {/* Settings Navigation Tabs */}
      <Tabs defaultValue="general" className="w-full space-y-6">
        <TabsList className="bg-muted p-1 border border-border flex flex-wrap h-auto w-full justify-start gap-1">
          <TabsTrigger value="general" className="gap-1.5 text-xs">
            <User className="h-3.5 w-3.5" />
            <span>Profile & Account</span>
          </TabsTrigger>
          <TabsTrigger value="audio" className="gap-1.5 text-xs">
            <Volume2 className="h-3.5 w-3.5" />
            <span>Audio & Siren Alarms</span>
          </TabsTrigger>
          <TabsTrigger value="notifications" className="gap-1.5 text-xs">
            <Bell className="h-3.5 w-3.5" />
            <span>Notification Channels</span>
          </TabsTrigger>
          <TabsTrigger value="appearance" className="gap-1.5 text-xs">
            <Monitor className="h-3.5 w-3.5" />
            <span>Appearance & Theme</span>
          </TabsTrigger>
          <TabsTrigger value="protocol" className="gap-1.5 text-xs">
            <ShieldAlert className="h-3.5 w-3.5" />
            <span>Operational Protocol</span>
          </TabsTrigger>
        </TabsList>

        {/* Tab 1: Profile & Account */}
        <TabsContent value="general" className="space-y-4">
          <Card className="border border-border p-5 shadow-xs space-y-5">
            <div className="border-b border-border pb-3">
              <h3 className="text-base font-semibold text-foreground">Operator Identification</h3>
              <p className="text-xs text-muted-foreground">
                Your name is recorded on official collision triage decisions and emergency response logs.
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="operator-name" className="text-xs font-semibold uppercase tracking-wider">
                  Full Name
                </Label>
                <Input
                  id="operator-name"
                  value={fullName}
                  onChange={(e) => {
                    setFullName(e.target.value)
                    setErrorMessage('')
                  }}
                  placeholder="Enter full name"
                  maxLength={160}
                  className="h-9 text-sm"
                />
                <p className="text-[11px] text-muted-foreground">
                  Appears in review attribution and incident timeline logs.
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="operator-email" className="text-xs font-semibold uppercase tracking-wider">
                  Verified Email
                </Label>
                <div className="relative">
                  <Input
                    id="operator-email"
                    value={profile?.email ?? ''}
                    readOnly
                    className="h-9 text-sm bg-muted text-muted-foreground pr-8"
                  />
                  <Lock className="absolute right-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                </div>
                <p className="text-[11px] text-muted-foreground">
                  Managed by central system administrators.
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="operator-role" className="text-xs font-semibold uppercase tracking-wider">
                  System Role
                </Label>
                <Input
                  id="operator-role"
                  value={profile?.role?.toUpperCase() ?? ''}
                  readOnly
                  className="h-9 text-sm bg-muted text-muted-foreground font-mono"
                />
                <p className="text-[11px] text-muted-foreground">
                  Grants operational permissions across triage and dispatch queues.
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="operator-area" className="text-xs font-semibold uppercase tracking-wider">
                  Assigned Sector / Zone
                </Label>
                <Input
                  id="operator-area"
                  value={profile?.areaId ?? 'All Sectors (Global Scope)'}
                  readOnly
                  className="h-9 text-sm bg-muted text-muted-foreground"
                />
                <p className="text-[11px] text-muted-foreground">
                  Geographic boundary for assigned incident handling.
                </p>
              </div>
            </div>
          </Card>

          {/* Account Security Card */}
          <Card className="border border-border p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
                  <KeyRound className="h-4 w-4 text-primary" />
                  Account Credentials & Password
                </h3>
                <p className="text-xs text-muted-foreground">
                  Secure your emergency response console credentials.
                </p>
              </div>
              <Button asChild variant="outline" size="sm" className="h-9 gap-1.5 text-xs">
                <Link href="/change-password">
                  <span>Change Password</span>
                  <ExternalLink className="h-3 w-3" />
                </Link>
              </Button>
            </div>
          </Card>
        </TabsContent>

        {/* Tab 2: Audio & Siren Alarms */}
        <TabsContent value="audio" className="space-y-4">
          <Card className="border border-border p-5 shadow-xs space-y-5">
            <div className="border-b border-border pb-3">
              <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
                <Volume2 className="h-4 w-4 text-primary" />
                Emergency Collision Siren & Sound Output
              </h3>
              <p className="text-xs text-muted-foreground">
                High-decibel audible alerts notify operators immediately when severe traffic accidents occur.
              </p>
            </div>

            {/* Master Siren Toggle */}
            <div className="flex items-start justify-between gap-4 rounded-lg border border-border p-4 bg-card">
              <div className="space-y-1">
                <Label htmlFor="alarm-audio" className="font-semibold text-sm cursor-pointer">
                  Play Alarm Siren for Newly Committed Incidents
                </Label>
                <p className="text-xs text-muted-foreground">
                  {activeRole === 'dispatcher'
                    ? 'Sounds immediately when YOLO Dual-Path AI detects a confirmed vehicle collision.'
                    : 'Sounds immediately when an incident is dispatched to your emergency response unit.'}
                </p>
              </div>
              <Switch
                id="alarm-audio"
                checked={alarmAudio}
                onCheckedChange={setAlarmAudio}
                aria-label="Toggle siren audio alarm"
              />
            </div>

            {/* Audio Testing Tool */}
            <div className="rounded-lg border border-border p-4 bg-muted/30 space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-foreground">
                    Siren Sound Output Test
                  </h4>
                  <p className="text-xs text-muted-foreground">
                    Verify workstation speaker output and browser audio autoplay permissions.
                  </p>
                </div>
                <Button
                  type="button"
                  variant={isPlayingAudio ? 'destructive' : 'default'}
                  size="sm"
                  onClick={toggleAudioTest}
                  className="h-9 gap-2 text-xs font-semibold"
                >
                  {isPlayingAudio ? (
                    <>
                      <Square className="h-3.5 w-3.5" />
                      <span>Stop Siren</span>
                    </>
                  ) : (
                    <>
                      <Play className="h-3.5 w-3.5" />
                      <span>Test Siren Sound</span>
                    </>
                  )}
                </Button>
              </div>

              {isPlayingAudio ? (
                <div className="flex items-center gap-3 rounded border border-primary/30 bg-primary/5 p-3 text-xs text-primary font-medium">
                  <div className="flex items-center gap-1">
                    <span className="h-3 w-1 bg-primary animate-pulse rounded-full" />
                    <span className="h-4 w-1 bg-primary animate-pulse delay-75 rounded-full" />
                    <span className="h-5 w-1 bg-primary animate-pulse delay-150 rounded-full" />
                    <span className="h-3 w-1 bg-primary animate-pulse delay-100 rounded-full" />
                  </div>
                  <span>Playing siren audio sample (/alert-sound.mp3)... Click &quot;Stop Siren&quot; to halt.</span>
                </div>
              ) : null}

              {audioBlocked ? (
                <div className="rounded border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300">
                  <p className="font-semibold flex items-center gap-1.5">
                    <AlertTriangle className="h-3.5 w-3.5" />
                    Browser Autoplay Was Blocked
                  </p>
                  <p className="mt-1">
                    Modern browsers restrict autoplaying sounds until you interact with the page. Clicking
                    the test button grants persistent audio playback permissions for this session.
                  </p>
                </div>
              ) : null}
            </div>

            <div className="text-xs text-muted-foreground space-y-1">
              <p>
                <strong>Operational Note:</strong> Visual notifications remain active even if audio is
                muted. In high-noise environments or multi-monitor operations, keeping the audio siren
                armed ensures sub-second awareness.
              </p>
            </div>
          </Card>
        </TabsContent>

        {/* Tab 3: Notification Channels */}
        <TabsContent value="notifications" className="space-y-4">
          <Card className="border border-border p-5 shadow-xs space-y-5">
            <div className="border-b border-border pb-3">
              <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
                <Bell className="h-4 w-4 text-primary" />
                Notification Routing & Triage Alerts
              </h3>
              <p className="text-xs text-muted-foreground">
                Control which channels receive collision alerts, status transitions, and emergency updates.
              </p>
            </div>

            {/* Desktop Browser Push Notifications */}
            <div className="rounded-lg border border-border p-4 bg-muted/20 space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Label className="font-semibold text-sm">Browser Desktop Push Alerts</Label>
                    <Badge
                      variant="outline"
                      className={`text-[11px] font-semibold ${
                        browserPermission === 'granted'
                          ? 'border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-400'
                          : browserPermission === 'denied'
                          ? 'border-rose-300 bg-rose-50 text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-400'
                          : 'border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-400'
                      }`}
                    >
                      {browserPermission === 'granted'
                        ? 'Permission Granted'
                        : browserPermission === 'denied'
                        ? 'Blocked in Browser'
                        : 'Permission Required'}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Delivers OS-level banner notifications when this tab is minimized or running in the
                    background.
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  {browserPermission !== 'granted' ? (
                    <Button
                      type="button"
                      variant="default"
                      size="sm"
                      onClick={() => void requestNotificationPermission()}
                      className="h-8 text-xs gap-1.5"
                    >
                      <Bell className="h-3 w-3" />
                      <span>Request Permission</span>
                    </Button>
                  ) : (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={sendTestNotification}
                      className="h-8 text-xs gap-1.5"
                    >
                      <span>Send Test Push</span>
                    </Button>
                  )}
                  <Switch
                    checked={browserNotifications}
                    onCheckedChange={setBrowserNotifications}
                    aria-label="Toggle browser desktop notifications"
                  />
                </div>
              </div>
            </div>

            {/* In-App Incident Alerts */}
            <div className="flex items-start justify-between gap-4 rounded-lg border border-border p-4 bg-card">
              <div className="space-y-1">
                <Label htmlFor="alert-notifs" className="font-semibold text-sm cursor-pointer">
                  Real-Time Collision & Dispatch Alerts
                </Label>
                <p className="text-xs text-muted-foreground">
                  Show banner tickers, active badge counters, and live triage feeds across all operational
                  pages.
                </p>
              </div>
              <Switch
                id="alert-notifs"
                checked={alertNotifications}
                onCheckedChange={setAlertNotifications}
                aria-label="Toggle in-app collision alerts"
              />
            </div>

            {/* Email Notifications */}
            <div className="flex items-start justify-between gap-4 rounded-lg border border-border p-4 bg-card">
              <div className="space-y-1">
                <Label htmlFor="email-notifs" className="font-semibold text-sm cursor-pointer">
                  Email Shift Summaries & High-Priority Digests
                </Label>
                <p className="text-xs text-muted-foreground">
                  Receive email alerts for critical system notices and shift handover summaries.
                </p>
              </div>
              <Switch
                id="email-notifs"
                checked={emailNotifications}
                onCheckedChange={setEmailNotifications}
                aria-label="Toggle email notifications"
              />
            </div>
          </Card>
        </TabsContent>

        {/* Tab 4: Appearance & Theme */}
        <TabsContent value="appearance" className="space-y-4">
          <Card className="border border-border p-5 shadow-xs space-y-5">
            <div className="border-b border-border pb-3">
              <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
                <Monitor className="h-4 w-4 text-primary" />
                Workstation Display & Color Theme
              </h3>
              <p className="text-xs text-muted-foreground">
                High-contrast dark themes reduce eye strain during nighttime emergency operations.
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              {/* Light Theme Tile */}
              <div
                onClick={() => chooseTheme('light')}
                className={`cursor-pointer rounded-lg border p-4 transition-all ${
                  selectedTheme === 'light'
                    ? 'border-primary bg-primary/5 ring-2 ring-primary/20 shadow-xs'
                    : 'border-border bg-card hover:bg-muted/40'
                }`}
              >
                <div className="flex items-center justify-between pb-3">
                  <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
                    <Sun className="h-4 w-4 text-amber-500" />
                    Light Theme
                  </span>
                  {selectedTheme === 'light' ? (
                    <CheckCircle2 className="h-4 w-4 text-primary" />
                  ) : null}
                </div>
                <div className="rounded border border-slate-200 bg-white p-3 space-y-1.5 shadow-2xs">
                  <div className="h-2 w-16 bg-slate-300 rounded" />
                  <div className="h-2 w-full bg-slate-100 rounded" />
                  <div className="h-2 w-3/4 bg-slate-100 rounded" />
                </div>
                <p className="mt-2 text-[11px] text-muted-foreground">
                  Optimized for daytime control rooms and bright ambient lighting.
                </p>
              </div>

              {/* Dark Theme Tile */}
              <div
                onClick={() => chooseTheme('dark')}
                className={`cursor-pointer rounded-lg border p-4 transition-all ${
                  selectedTheme === 'dark'
                    ? 'border-primary bg-primary/5 ring-2 ring-primary/20 shadow-xs'
                    : 'border-border bg-card hover:bg-muted/40'
                }`}
              >
                <div className="flex items-center justify-between pb-3">
                  <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
                    <Moon className="h-4 w-4 text-indigo-400" />
                    Dark Theme
                  </span>
                  {selectedTheme === 'dark' ? (
                    <CheckCircle2 className="h-4 w-4 text-primary" />
                  ) : null}
                </div>
                <div className="rounded border border-slate-700 bg-slate-900 p-3 space-y-1.5 shadow-2xs">
                  <div className="h-2 w-16 bg-slate-600 rounded" />
                  <div className="h-2 w-full bg-slate-800 rounded" />
                  <div className="h-2 w-3/4 bg-slate-800 rounded" />
                </div>
                <p className="mt-2 text-[11px] text-muted-foreground">
                  High-contrast dark surfaces for 24/7 nighttime emergency desks.
                </p>
              </div>

              {/* System Default Tile */}
              <div
                onClick={() => chooseTheme('system')}
                className={`cursor-pointer rounded-lg border p-4 transition-all ${
                  selectedTheme === 'system'
                    ? 'border-primary bg-primary/5 ring-2 ring-primary/20 shadow-xs'
                    : 'border-border bg-card hover:bg-muted/40'
                }`}
              >
                <div className="flex items-center justify-between pb-3">
                  <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
                    <Monitor className="h-4 w-4 text-primary" />
                    System Default
                  </span>
                  {selectedTheme === 'system' ? (
                    <CheckCircle2 className="h-4 w-4 text-primary" />
                  ) : null}
                </div>
                <div className="rounded border border-slate-300 dark:border-slate-700 bg-gradient-to-r from-white to-slate-900 p-3 space-y-1.5 shadow-2xs">
                  <div className="h-2 w-16 bg-slate-400 rounded" />
                  <div className="h-2 w-full bg-slate-300 dark:bg-slate-700 rounded" />
                  <div className="h-2 w-3/4 bg-slate-300 dark:bg-slate-700 rounded" />
                </div>
                <p className="mt-2 text-[11px] text-muted-foreground">
                  Automatically syncs with your operating system display appearance
                  {resolvedTheme ? ` (currently ${resolvedTheme === 'dark' ? 'Dark' : 'Light'})` : ''}.
                </p>
              </div>
            </div>
          </Card>
        </TabsContent>

        {/* Tab 5: Operational Protocols */}
        <TabsContent value="protocol" className="space-y-4">
          <Card className="border border-border p-5 shadow-xs space-y-5">
            <div className="border-b border-border pb-3">
              <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
                <ShieldAlert className="h-4 w-4 text-primary" />
                {activeRole === 'dispatcher'
                  ? 'Central Dispatcher Operational Directives'
                  : 'Field Emergency Response Protocols'}
              </h3>
              <p className="text-xs text-muted-foreground">
                Official procedural guidelines for triage latency, status progression, and emergency
                integrity.
              </p>
            </div>

            {activeRole === 'dispatcher' ? (
              <div className="space-y-4 text-xs">
                <div className="rounded-lg border border-border p-4 bg-muted/30 space-y-2">
                  <h4 className="font-bold text-foreground uppercase tracking-wider text-[11px]">
                    1. Dual-Path Collision Classification
                  </h4>
                  <ul className="list-disc list-inside space-y-1 text-muted-foreground">
                    <li>
                      <strong>Priority 1 (Temporal Collision):</strong> Dynamic impact detected in motion.
                      Immediate siren alarm is triggered. Triage required within 30 seconds.
                    </li>
                    <li>
                      <strong>Priority 2 (Aftermath Scene):</strong> High-confidence stationary obstruction
                      or overturned vehicle. Visual review alert queued for dispatcher validation.
                    </li>
                  </ul>
                </div>

                <div className="rounded-lg border border-border p-4 bg-muted/30 space-y-2">
                  <h4 className="font-bold text-foreground uppercase tracking-wider text-[11px]">
                    2. 15-Minute Review Claim Leases
                  </h4>
                  <p className="text-muted-foreground">
                    When you claim an unreviewed collision, the review case is locked exclusively to your
                    operator ID for 15 minutes. If no confirmation or false-alarm dismissal is completed
                    before expiration, the lock releases back to the general dispatcher queue.
                  </p>
                </div>

                <div className="rounded-lg border border-border p-4 bg-muted/30 space-y-2">
                  <h4 className="font-bold text-foreground uppercase tracking-wider text-[11px]">
                    3. Dispatch Velocity Target
                  </h4>
                  <p className="text-muted-foreground">
                    Assign the closest available unit with verified online presence. If an assigned unit
                    declines or cannot respond, immediately reassign to the next available emergency vehicle.
                  </p>
                </div>
              </div>
            ) : (
              <div className="space-y-4 text-xs">
                <div className="rounded-lg border border-border p-4 bg-muted/30 space-y-2">
                  <h4 className="font-bold text-foreground uppercase tracking-wider text-[11px]">
                    1. Response Lifecycle Progression
                  </h4>
                  <p className="text-muted-foreground">
                    Field responders must sequentially update assignment status to maintain accurate
                    timelines:
                  </p>
                  <div className="flex flex-wrap items-center gap-1.5 pt-1 font-mono font-semibold">
                    <span className="bg-muted px-2 py-0.5 rounded border border-border">ASSIGNED</span>
                    <span>➔</span>
                    <span className="bg-muted px-2 py-0.5 rounded border border-border">ACCEPTED</span>
                    <span>➔</span>
                    <span className="bg-sky-50 text-sky-700 dark:bg-sky-950/40 dark:text-sky-300 px-2 py-0.5 rounded border border-sky-200">
                      EN_ROUTE
                    </span>
                    <span>➔</span>
                    <span className="bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300 px-2 py-0.5 rounded border border-blue-200">
                      ARRIVED
                    </span>
                    <span>➔</span>
                    <span className="bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 px-2 py-0.5 rounded border border-emerald-200">
                      RESOLVED
                    </span>
                  </div>
                </div>

                <div className="rounded-lg border border-border p-4 bg-muted/30 space-y-2">
                  <h4 className="font-bold text-foreground uppercase tracking-wider text-[11px]">
                    2. Automated 25-Second Telemetry Heartbeat
                  </h4>
                  <p className="text-muted-foreground">
                    CrashGuard automatically transmits a telemetry heartbeat every 25 seconds while this
                    window is open to report your live operational readiness to Central Dispatch. If
                    navigating offline, update your availability status in the header menu.
                  </p>
                </div>

                <div className="rounded-lg border border-border p-4 bg-muted/30 space-y-2">
                  <h4 className="font-bold text-foreground uppercase tracking-wider text-[11px]">
                    3. Scene Assessment & Safety Directive
                  </h4>
                  <p className="text-muted-foreground">
                    Prioritize vehicle safety while en route. Upon on-scene arrival, secure hazard perimeters
                    before logging outcome notes and marking the scene cleared.
                  </p>
                </div>
              </div>
            )}
          </Card>
        </TabsContent>
      </Tabs>

      {/* Floating / Sticky Save Bar when dirty */}
      {isDirty ? (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-30 w-[90%] max-w-2xl rounded-xl border border-border bg-card/95 backdrop-blur-md p-4 shadow-xl flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-amber-500 animate-pulse" />
            <span className="text-xs font-semibold text-foreground">
              You have unsaved operational preference changes
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleDiscard}
              disabled={saving}
              className="h-8 text-xs"
            >
              Discard
            </Button>
            <Button
              size="sm"
              onClick={() => void saveChanges()}
              disabled={saving}
              className="h-8 text-xs bg-primary text-primary-foreground gap-1.5"
            >
              <Save className={`h-3 w-3 ${saving ? 'animate-spin' : ''}`} />
              <span>{saving ? 'Saving...' : 'Save Changes'}</span>
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
