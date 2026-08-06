'use client'

import { Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Circle,
  Image as ImageIcon,
  Loader,
  Video,
} from 'lucide-react'
import {
  doc,
  onSnapshot,
  serverTimestamp,
  setDoc,
} from 'firebase/firestore'

import { DashboardHeader, Sidebar } from '@/components/dashboard-sidebar'
import { DetectedMediaViewer } from '@/components/detected-media-viewer'
import { LiveCamera } from '@/components/live-camera'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { useToast } from '@/hooks/use-toast'
import { useAuth } from '@/components/auth-provider'
import { detectFromFile } from '@/lib/api-client'
import { APP_CONFIG } from '@/lib/app-config'
import { isDashboardRole } from '@/lib/auth-profile'
import { createCrashCaseFromDetection } from '@/lib/crash-case-store'
import { db } from '@/lib/firebase'
import { getFirebaseConfigError } from '@/lib/firebase-guards'
import { AreaId, getAreaLabel } from '@/lib/locations'
import { LOCATION_TABS, SAMPLES, Sample } from '@/lib/sample-data'
import { DetectionResponse } from '@/lib/types'

interface LiveCameraSession {
  active?: boolean
  areaId?: AreaId
  livePreviewDataUrl?: string | null
  latestDetection?: DetectionResponse | null
  responderUid?: string
  updatedAt?: unknown
}

/** Firestore rejects `undefined` anywhere in document data; optional API fields must be stripped. */
function detectionPayloadForFirestore(result: DetectionResponse): Record<string, unknown> {
  return JSON.parse(JSON.stringify(result)) as Record<string, unknown>
}

function SamplesPageContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { authError, firebaseUser, loading, profile, signOutUser } = useAuth()
  const [mounted, setMounted] = useState(false)
  const [selectedSample, setSelectedSample] = useState<Sample | null>(null)
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [sampleResult, setSampleResult] = useState<DetectionResponse | null>(null)
  const [sampleError, setSampleError] = useState('')
  const [liveSession, setLiveSession] = useState<LiveCameraSession | null>(null)
  const [liveSessionSubscribeError, setLiveSessionSubscribeError] = useState<string | null>(null)
  const lastResponderAlertAtRef = useRef(0)
  const lastLiveSessionPublishAtRef = useRef(0)

  const { toast } = useToast()
  const isResponder = profile?.role === 'responder'
  const responderArea = profile?.role === 'responder' ? profile.areaId : null
  const canReviewIncidents = isDashboardRole(profile?.role)
  const canReadLiveSessions = profile?.role === 'admin' || Boolean(responderArea)
  const requestedArea = searchParams.get('area')
  const selectedLocation: AreaId =
    responderArea ??
    (requestedArea === 'talomo' || requestedArea === 'bago' || requestedArea === 'toril'
      ? requestedArea
      : 'talomo')

  useEffect(() => {
    if (isResponder) {
      router.replace('/dashboard')
      return
    }
  }, [isResponder, router])

  const visibleLocationTabs = useMemo(() => {
    if (!responderArea) return LOCATION_TABS
    return LOCATION_TABS.filter((tab) => tab.value === responderArea)
  }, [responderArea])

  const visibleSamples = SAMPLES.filter((sample) => sample.location === selectedLocation)
  const responderAreaLabel = responderArea ? getAreaLabel(responderArea) : ''

  useEffect(() => {
    setMounted(true)
  }, [])

  useEffect(() => {
    if (!mounted || loading) return

    if (!firebaseUser || !profile) {
      router.replace('/login')
      return
    }

    if (!profile.active) {
      signOutUser().finally(() => router.replace('/login'))
    }
  }, [firebaseUser, loading, mounted, profile, router, signOutUser])

  useEffect(() => {
    if (responderArea || !canReadLiveSessions) return

    setLiveSession(null)
    setLiveSessionSubscribeError(null)

    if (!db) {
      setLiveSessionSubscribeError(getFirebaseConfigError())
      return
    }

    const unsubscribe = onSnapshot(
      doc(db, 'live_camera_sessions', selectedLocation),
      (snapshot) => {
        setLiveSessionSubscribeError(null)
        if (!snapshot.exists()) {
          setLiveSession(null)
          return
        }

        setLiveSession(snapshot.data() as LiveCameraSession)
      },
      (error) => {
        console.error('Failed to subscribe to live camera session:', error)
        setLiveSessionSubscribeError(
          error instanceof Error ? error.message : 'Could not subscribe to live status.'
        )
        setLiveSession(null)
      }
    )

    return () => unsubscribe()
  }, [canReadLiveSessions, responderArea, selectedLocation])

  const updateResponderLiveSession = async (
    payload: Partial<Pick<LiveCameraSession, 'active' | 'latestDetection' | 'livePreviewDataUrl'>>
  ) => {
    if (!responderArea || !firebaseUser) return
    if (!db) {
      toast({
        title: 'Firebase is not configured',
        description: getFirebaseConfigError() ?? 'Firestore is not ready.',
        variant: 'destructive',
      })
      return
    }

    const docData: Record<string, unknown> = {
      areaId: responderArea,
      responderUid: firebaseUser.uid,
      updatedAt: serverTimestamp(),
    }

    if (payload.active !== undefined) {
      docData.active = payload.active
    }

    if ('latestDetection' in payload) {
      const ld = payload.latestDetection
      docData.latestDetection =
        ld == null ? null : detectionPayloadForFirestore(ld)
    }

    if ('livePreviewDataUrl' in payload) {
      docData.livePreviewDataUrl = payload.livePreviewDataUrl ?? null
    }

    try {
      await setDoc(doc(db, 'live_camera_sessions', responderArea), docData, {
        merge: true,
      })
    } catch (error) {
      console.error('Failed to publish responder live camera status:', error)
      toast({
        title: 'Firebase: could not publish camera status',
        description:
          error instanceof Error
            ? error.message
            : 'Check Firestore rules for live_camera_sessions and your network.',
        variant: 'destructive',
      })
    }
  }

  const publishResponderLivePreview = (
    result: DetectionResponse | null,
    rawFrameDataUrl: string | null
  ) => {
    const now = Date.now()
    if (now - lastLiveSessionPublishAtRef.current < APP_CONFIG.detection.liveSessionPublishIntervalMs) {
      return
    }

    lastLiveSessionPublishAtRef.current = now
    const payload: Partial<Pick<LiveCameraSession, 'active' | 'latestDetection' | 'livePreviewDataUrl'>> = {
      active: true,
    }

    if (result) {
      payload.latestDetection = {
        ...result,
        detections: result.detections.slice(0, 5),
      }
    }

    // Avoid clearing a good preview when a frame snapshot briefly fails.
    if (rawFrameDataUrl) {
      payload.livePreviewDataUrl = rawFrameDataUrl
    }

    void updateResponderLiveSession(payload)
  }

  const pushResponderIncidentToFirestore = async (result: DetectionResponse) => {
    if (!responderArea || !firebaseUser || !result.accident_detected) return
    if (!db) return

    try {
      const now = Date.now()
      if (now - lastResponderAlertAtRef.current < APP_CONFIG.detection.responderAlertDebounceMs) {
        return
      }
      lastResponderAlertAtRef.current = now

      await createCrashCaseFromDetection(db, {
        actorId: firebaseUser.uid,
        areaId: responderArea,
        result,
        source: 'live-camera',
        sourceFile: `${responderArea}-live-camera`,
        locationLabel: `${responderAreaLabel} CCTV`,
      })
    } catch (error) {
      console.error('Failed to publish responder alert:', error)
    }
  }

  if (!mounted || loading) {
    return null
  }

  if (!firebaseUser || !profile || !profile.active) {
    return null
  }

  if (isResponder) {
    return null
  }

  const responderMissingArea =
    profile?.role === 'responder' && profile.areaId == null
  const isLiveSessionOnline =
    Boolean(liveSession?.active) &&
    liveSession?.areaId === selectedLocation
  const livePreviewUrl = isLiveSessionOnline
    ? (liveSession?.livePreviewDataUrl ?? null)
    : null

  const openSample = (sample: Sample) => {
    setSelectedSample(sample)
    setSampleResult(null)
    setSampleError('')
    setIsDialogOpen(true)
  }

  const handleAnalyzeSample = async (sample: Sample) => {
    setIsAnalyzing(true)
    setSampleError('')
    setSampleResult(null)

    try {
      const response = await fetch(sample.url)

      if (!response.ok) {
        throw new Error(`Could not load ${sample.url} for analysis.`)
      }

      const blob = await response.blob()
      const file = new File([blob], `${sample.id}.jpg`, {
        type: blob.type || 'image/jpeg',
      })
      const result = await detectFromFile(file, sample.type)

      setSampleResult(result)
      if (result.accident_detected && db && canReviewIncidents) {
        await createCrashCaseFromDetection(db, {
          actorId: firebaseUser?.uid ?? 'sample-user',
          areaId: sample.location,
          result,
          source: 'sample',
          sourceFile: sample.url,
          locationLabel: `${getAreaLabel(sample.location)} sample`,
        })
      }
      toast({
        title: result.accident_detected ? 'Possible Crash Pending Review' : 'Detection Complete',
        description: `${sample.title} returned ${(result.confidence * 100).toFixed(
          0
        )}% possible crash confidence.`,
        variant: result.accident_detected ? 'destructive' : 'default',
      })
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : 'Sample analysis failed. Please try again.'

      setSampleError(message)
      toast({
        title: 'Sample Analysis Failed',
        description: message,
        variant: 'destructive',
      })
    } finally {
      setIsAnalyzing(false)
    }
  }

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <div className="flex-1 md:ml-0">
        <DashboardHeader />

        {responderMissingArea && (
          <div className="px-6 pt-4">
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                This account is a responder but has no <code className="text-xs">areaId</code> in
                Firestore <code className="text-xs">users/{'{uid}'}</code>. Add{' '}
                <code className="text-xs">areaId: &quot;talomo&quot;</code> (or bago/toril) so the
                live camera can publish to the correct document. Until then you will see the admin
                gallery instead of the camera panel.
              </AlertDescription>
            </Alert>
          </div>
        )}

        {responderArea ? (
          <main className="space-y-6 p-6">
            <div>
              <h1 className="mb-2 text-3xl font-bold">{responderAreaLabel} CCTV Monitor</h1>
              <p className="text-muted-foreground">
                Live CCTV feed for your assigned area only. Possible crash detections trigger alarm and
                are sent to admin notifications.
              </p>
            </div>

            {authError && (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>{authError}</AlertDescription>
              </Alert>
            )}

            <LiveCamera
              accidentOnlyMode
              areaId={responderArea}
              cameraId={`DEVICE-LIVE-CAMERA-${responderArea.toUpperCase()}`}
              cameraName="Device Live Camera"
              sourceCamera="Device Live Camera"
              detectionIntervalMs={1000}
              onStreamStateChange={(isStreaming) => {
                if (isStreaming) {
                  void updateResponderLiveSession({ active: true })
                } else {
                  void updateResponderLiveSession({
                    active: false,
                    livePreviewDataUrl: null,
                    latestDetection: null,
                  })
                }
              }}
              onFrameResult={(result, rawFrameDataUrl) => {
                publishResponderLivePreview(result, rawFrameDataUrl)
              }}
              onDetectionResult={(result) => {
                void updateResponderLiveSession({
                  active: true,
                  latestDetection: {
                    ...result,
                    detections: result.detections.slice(0, 5),
                  } as DetectionResponse,
                })
                void pushResponderIncidentToFirestore(result)
              }}
            />
          </main>
        ) : (
        <main className="space-y-8 p-6">
          <div>
            <h1 className="mb-2 text-3xl font-bold">CCTV Sample Gallery</h1>
            <p className="text-muted-foreground">
              Preview demo samples and run continuous live detection from your laptop
              or phone camera in the browser.
            </p>
          </div>

          {!responderArea && (
            <section className="space-y-4">
              <p className="rounded-lg border border-border bg-card/50 p-4 text-sm text-muted-foreground">
                Admin view includes broader CCTV controls. Responder accounts only show assigned
                footage cards.
              </p>
            </section>
          )}

          {authError && !responderArea && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>{authError}</AlertDescription>
            </Alert>
          )}

          <section className="space-y-4">
            <Card className="border border-border bg-card/70 p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-lg font-semibold">Live {selectedLocation.toUpperCase()} Camera</h2>
                  <p className="text-sm text-muted-foreground">
                    Realtime responder camera status mirrored to admin (Firebase), not a direct video
                    feed.
                  </p>
                </div>
                <Badge
                  variant="outline"
                  className={
                    isLiveSessionOnline
                      ? 'border-[var(--status-online)] bg-[color:var(--status-online-bg)] text-[var(--status-online)]'
                      : 'border-border bg-background text-muted-foreground'
                  }
                >
                  <Circle className="mr-2 h-3 w-3" />
                  {isLiveSessionOnline ? 'Camera Online' : 'Camera Offline'}
                </Badge>
              </div>

              {isLiveSessionOnline && livePreviewUrl ? (
                <div className="mt-4 space-y-3 rounded-lg border border-border/50 bg-card/50 p-3">
                  <div className="text-sm text-muted-foreground">Latest Live Frame</div>
                  <DetectedMediaViewer
                    buttonLabel={`View Live ${selectedLocation.toUpperCase()} Frame`}
                    description="Latest raw frame mirrored from responder live camera."
                    initialOpen={false}
                    mediaType="image"
                    mediaUrl={livePreviewUrl}
                    title={`${selectedLocation.toUpperCase()} Live Frame`}
                  />
                </div>
              ) : (
                <p className="mt-4 text-sm text-muted-foreground">
                  Waiting for responder to start camera and send live detections.
                </p>
              )}

              {liveSessionSubscribeError && (
                <Alert variant="destructive" className="mt-4">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>
                    Could not read live status from Firebase: {liveSessionSubscribeError}. Check
                    Firestore rules and that this app uses the same Firebase project as the
                    responder session.
                  </AlertDescription>
                </Alert>
              )}
            </Card>

            <div>
              <h2 className="text-xl font-semibold">Live Camera Feed</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Pick a CCTV area below to view realtime responder camera status.
              </p>
            </div>

            {!responderArea && (
              <div className="flex flex-wrap gap-2">
                {visibleLocationTabs.map((location) => (
                  <Button
                    key={location.value}
                    type="button"
                    variant={selectedLocation === location.value ? 'default' : 'outline'}
                    onClick={() => router.push(`/samples?area=${location.value}`)}
                  >
                    {location.label}
                  </Button>
                ))}
              </div>
            )}

            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {!responderArea && isLiveSessionOnline && (
                <Card className="overflow-hidden border border-[var(--status-online)] bg-card shadow-lg">
                  <div className="relative aspect-video overflow-hidden bg-[var(--media-background)]">
                    {livePreviewUrl ? (
                      <img
                        src={livePreviewUrl}
                        alt={`Live ${selectedLocation} camera preview`}
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center text-sm text-muted-foreground">
                        Live camera is online. Waiting for latest frame preview.
                      </div>
                    )}
                    <div className="absolute left-3 top-3">
                      <Badge className="border-[var(--status-online)] bg-[color:var(--status-online-bg)] text-[var(--status-online)]" variant="outline">
                        LIVE {selectedLocation.toUpperCase()}
                      </Badge>
                    </div>
                  </div>

                  <div className="space-y-3 p-4">
                    <div>
                      <h3 className="text-sm font-semibold">Live {selectedLocation.toUpperCase()} Camera</h3>
                      <p className="text-xs text-muted-foreground">
                        Realtime responder status mirrored from Firebase.
                      </p>
                    </div>

                    <DetectedMediaViewer
                      buttonLabel={`View Live ${selectedLocation.toUpperCase()} Frame`}
                      description="Latest annotated frame pushed from responder live camera."
                      initialOpen={false}
                      mediaType="image"
                      mediaUrl={livePreviewUrl}
                      title={`${selectedLocation.toUpperCase()} Live Frame`}
                      warning={liveSession?.latestDetection?.annotated_media_warning}
                    />
                  </div>
                </Card>
              )}
            </div>
          </section>
        </main>
        )}
      </div>

      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="max-w-2xl border border-border bg-card">
          <DialogHeader>
            <DialogTitle>{selectedSample?.title}</DialogTitle>
          </DialogHeader>

          {selectedSample && (
            <div className="space-y-4">
              <div className="overflow-hidden rounded-lg border border-border bg-[var(--media-background)]">
                {selectedSample.type === 'video' ? (
                  <video
                    src={selectedSample.url}
                    controls
                    className="max-h-[50vh] w-full bg-[var(--media-background)] object-contain"
                  />
                ) : (
                  <img
                    src={selectedSample.url}
                    alt={selectedSample.title}
                    className="max-h-[50vh] w-full object-contain"
                  />
                )}
              </div>

              <div className="space-y-3">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  Sample metadata (preset for demo)
                </p>
                <p className="text-sm text-muted-foreground">{selectedSample.description}</p>

                <div className="grid gap-3 sm:grid-cols-3">
                  <div>
                    <p className="text-xs text-muted-foreground">Type</p>
                    <div className="mt-1 flex items-center gap-2">
                      {selectedSample.type === 'video' ? (
                        <Video className="h-4 w-4 text-primary" />
                      ) : (
                        <ImageIcon className="h-4 w-4 text-primary" />
                      )}
                      <p className="font-semibold capitalize">{selectedSample.type}</p>
                    </div>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Expected Status</p>
                    <p className="mt-1 font-semibold">
                      {selectedSample.hasAccident ? 'Possible crash' : 'Normal'}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Expected Confidence</p>
                    <p className="mt-1 font-semibold">
                      {(selectedSample.confidence * 100).toFixed(0)}%
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex gap-3">
                <Button
                  type="button"
                  onClick={() => handleAnalyzeSample(selectedSample)}
                  disabled={isAnalyzing}
                  className="flex-1"
                >
                  {isAnalyzing ? (
                    <>
                      <Loader className="mr-2 h-4 w-4 animate-spin" />
                      Analyzing...
                    </>
                  ) : (
                    'Analyze This Sample'
                  )}
                </Button>
                <Button type="button" variant="outline" onClick={() => setIsDialogOpen(false)}>
                  Close
                </Button>
              </div>

              {sampleError ? (
                <Alert variant="destructive">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>{sampleError}</AlertDescription>
                </Alert>
              ) : null}

              {sampleResult ? (
                <Card className="border border-border bg-card/70 p-4">
                  <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-primary" />
                      <p className="font-semibold">Backend Detection Result</p>
                    </div>
                    <Badge
                      className={
                        sampleResult.accident_detected
                          ? 'border-destructive/50 bg-destructive/20 text-destructive'
                          : 'border-[var(--status-resolved)] bg-[color:var(--status-resolved-bg)] text-[var(--status-resolved)]'
                      }
                      variant="outline"
                    >
                      {sampleResult.accident_detected ? 'Possible crash' : 'No crash flagged'}
                    </Badge>
                  </div>

                  {!sampleResult.accident_detected && sampleResult.detections.length > 0 ? (
                    <p className="mb-3 text-xs text-muted-foreground">
                      The model found objects, but none were classified as the <span className="font-semibold">accident</span> label.
                    </p>
                  ) : null}

                  <div className="grid gap-3 sm:grid-cols-3">
                    <div>
                      <p className="text-xs text-muted-foreground">Confidence</p>
                      <p className="font-semibold">
                        {(sampleResult.confidence * 100).toFixed(1)}%
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Detections</p>
                      <p className="font-semibold">{sampleResult.detections.length}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Media Type</p>
                      <p className="font-semibold capitalize">{sampleResult.media_type}</p>
                    </div>
                  </div>

                  {sampleResult.detections.length > 0 ? (
                    <div className="mt-4 space-y-2">
                      {sampleResult.detections.slice(0, 5).map((detection, index) => (
                        <div
                          key={`${detection.label}-${index}`}
                          className="flex items-center justify-between rounded border border-border/50 bg-card/50 p-2 text-sm"
                        >
                          <span className="capitalize">{detection.label}</span>
                          <Badge variant="outline">
                            {(detection.score * 100).toFixed(0)}%
                          </Badge>
                        </div>
                      ))}
                    </div>
                  ) : null}

                  <div className="mt-4">
                    <DetectedMediaViewer
                      buttonLabel="View Annotated Sample"
                      description="This is the annotated output returned by the FastAPI backend."
                      fallbackUrl={sampleResult.annotated_media_download_url ?? null}
                      initialOpen={sampleResult.accident_detected}
                      mediaType={sampleResult.media_type}
                      mediaUrl={sampleResult.annotated_media_url ?? null}
                      title="Detected Sample Output"
                      warning={sampleResult.annotated_media_warning}
                    />
                  </div>
                </Card>
              ) : null}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default function SamplesPage() {
  return (
    <Suspense fallback={null}>
      <SamplesPageContent />
    </Suspense>
  )
}
