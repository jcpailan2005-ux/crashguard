'use client'

import {
  ChangeEvent,
  DragEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import {
  AlertTriangle,
  Camera,
  CheckCircle2,
  ClipboardCheck,
  ExternalLink,
  ImageIcon,
  Loader,
  Upload,
  Video,
} from 'lucide-react'
import { useRouter } from 'next/navigation'

import {
  CameraCapture,
  CameraCapturedMedia,
} from '@/components/camera-capture'
import { useAuth } from '@/components/auth-provider'
import { DashboardHeader, Sidebar } from '@/components/dashboard-sidebar'
import { DetectedMediaViewer } from '@/components/detected-media-viewer'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useToast } from '@/hooks/use-toast'
import { playAccidentAlert } from '@/lib/accident-alert'
import { createCrashCaseFromDetection } from '@/lib/crash-case-store'
import { getFirestoreOrNull } from '@/lib/firebase-guards'
import {
  detectFromFile,
  detectMediaTypeFromFile,
  resolveBackendMediaUrl,
} from '@/lib/api-client'
import { DetectionResponse } from '@/lib/types'

type UploadMode = 'upload' | 'camera'

interface SelectedMedia {
  file: File
  label: string
  mediaType: 'image' | 'video'
  previewUrl: string
}

export default function UploadPage() {
  const [mode, setMode] = useState<UploadMode>('upload')
  const [uploadedMedia, setUploadedMedia] = useState<SelectedMedia | null>(null)
  const [cameraMedia, setCameraMedia] = useState<SelectedMedia | null>(null)
  const [dragActive, setDragActive] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<DetectionResponse | null>(null)
  const [createdCaseId, setCreatedCaseId] = useState<string | null>(null)
  const [caseActionLoading, setCaseActionLoading] = useState<string | null>(null)
  const [error, setError] = useState('')

  const fileInputRef = useRef<HTMLInputElement>(null)
  const uploadPreviewUrlRef = useRef<string | null>(null)
  const cameraPreviewUrlRef = useRef<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const { toast } = useToast()
  const { firebaseUser, profile } = useAuth()
  const router = useRouter()

  useEffect(() => {
    const el = new Audio('/alert-sound.mp3')
    el.preload = 'auto'
    el.volume = 1
    audioRef.current = el
  }, [])

  useEffect(() => {
    if (profile?.role === 'responder') {
      router.replace('/dashboard/ip-camera')
    }
  }, [profile, router])

  useEffect(() => {
    return () => {
      if (uploadPreviewUrlRef.current) {
        URL.revokeObjectURL(uploadPreviewUrlRef.current)
      }

      if (cameraPreviewUrlRef.current) {
        URL.revokeObjectURL(cameraPreviewUrlRef.current)
      }
    }
  }, [])

  const activeMedia = useMemo(
    () => (mode === 'upload' ? uploadedMedia : cameraMedia),
    [cameraMedia, mode, uploadedMedia]
  )
  const resultHasPreview = Boolean(result?.annotated_media_url)
  const resultHasDownloadOnly = Boolean(
    result?.annotated_media_download_url && !result?.annotated_media_url
  )
  const imageResultHasFallbackPreviewMessage =
    result?.media_type === 'image' && !resultHasPreview

  const clearResult = () => {
    setResult(null)
    setCreatedCaseId(null)
    setError('')
  }

  const showError = (message: string) => {
    setError(message)
    toast({
      title: 'Error',
      description: message,
      variant: 'destructive',
    })
  }

  const replacePreviewUrl = (
    previewRef: React.MutableRefObject<string | null>,
    newUrl: string
  ) => {
    if (previewRef.current) {
      URL.revokeObjectURL(previewRef.current)
    }

    previewRef.current = newUrl
  }

  const handleUploadSelection = (file: File) => {
    const mediaType = detectMediaTypeFromFile(file)

    if (!mediaType) {
      console.warn('[upload] Unsupported file selected', {
        filename: file.name,
        type: file.type || 'unknown',
      })
      showError('Please select an image or video file.')
      return
    }

    const previewUrl = URL.createObjectURL(file)
    replacePreviewUrl(uploadPreviewUrlRef, previewUrl)

    setUploadedMedia({
      file,
      label: mediaType === 'image' ? 'uploaded image' : 'uploaded video',
      mediaType,
      previewUrl,
    })

    clearResult()
  }

  const handleFileInput = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]

    if (file) {
      handleUploadSelection(file)
    }
  }

  const handleDrag = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    event.stopPropagation()

    if (event.type === 'dragenter' || event.type === 'dragover') {
      setDragActive(true)
    } else if (event.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    event.stopPropagation()
    setDragActive(false)

    const file = event.dataTransfer.files?.[0]

    if (file) {
      handleUploadSelection(file)
    }
  }

  const handleCameraMediaReady = (media: CameraCapturedMedia) => {
    console.info('[upload] Camera media ready', {
      label: media.label,
      mediaType: media.mediaType,
      filename: media.file.name,
      size: media.file.size,
      type: media.file.type || 'unknown',
    })
    replacePreviewUrl(cameraPreviewUrlRef, media.previewUrl)

    setCameraMedia({
      file: media.file,
      label: media.label,
      mediaType: media.mediaType,
      previewUrl: media.previewUrl,
    })

    clearResult()

    toast({
      title:
        media.mediaType === 'image'
          ? 'Image Captured'
          : 'Video Recorded',
      description:
        media.mediaType === 'image'
          ? 'Your captured image is ready for detection.'
          : 'Your recorded video is ready for detection.',
    })
  }

  const handleRunDetection = async () => {
    if (!activeMedia) {
      showError(
        mode === 'upload'
          ? 'Please select an image or video before running detection.'
          : 'Please capture an image or record a video before running detection.'
      )
      return
    }

    setLoading(true)
    setError('')
    setResult(null)
    setCreatedCaseId(null)

    try {
      const resolvedMediaType = detectMediaTypeFromFile(activeMedia.file)

      if (!resolvedMediaType) {
        throw new Error('Please select an image or video file.')
      }

      console.info('[upload] Running detection', {
        source: mode === 'upload' ? 'local-upload' : 'camera-capture',
        mediaType: resolvedMediaType,
        filename: activeMedia.file.name,
        size: activeMedia.file.size,
      })

      const detectionResult = await detectFromFile(activeMedia.file, resolvedMediaType)
      setResult(detectionResult)

      console.info('[upload] Detection result received', {
        mediaType: detectionResult.media_type,
        accidentDetected: detectionResult.accident_detected,
        annotatedMediaUrl: detectionResult.annotated_media_url,
        annotatedMediaAvailable: detectionResult.annotated_media_available,
      })

      if (detectionResult.accident_detected) {
        const db = getFirestoreOrNull()
        if (db) {
          const nextCaseId = await createCrashCaseFromDetection(db, {
            actorId: firebaseUser?.uid ?? 'upload-user',
            areaId: profile?.areaId ?? null,
            result: detectionResult,
            source: mode === 'upload' ? 'upload' : 'camera-capture',
            sourceFile: activeMedia.file.name,
            locationLabel: detectionResult.location,
          })
          setCreatedCaseId(nextCaseId)
        }

        void playAccidentAlert(audioRef.current, 1, { beepRepeats: 3 }).catch(
          (playbackError) => {
            console.warn('Could not play alert sound:', playbackError)
          }
        )

        toast({
          title: 'Possible Crash Detected',
          description: `A pending review case was created with ${(
            detectionResult.confidence * 100
          ).toFixed(0)}% confidence.`,
        })
      } else {
        toast({
          title: detectionResult.annotated_media_url
            ? 'Detection Complete'
            : 'Detection Complete Without Preview',
          description: detectionResult.annotated_media_url
            ? 'The backend returned a detection result and an annotated preview.'
            : detectionResult.processing_notes ??
              'The backend returned a detection result, but no annotated preview image was available.',
        })
      }
    } catch (detectionError) {
      console.warn('[upload] Detection failed', detectionError)
      showError(
        detectionError instanceof Error
          ? detectionError.message
          : 'Detection failed. Please try again.'
      )
    } finally {
      setLoading(false)
    }
  }

  const clearUploadedMedia = () => {
    setUploadedMedia(null)
    clearResult()

    if (uploadPreviewUrlRef.current) {
      URL.revokeObjectURL(uploadPreviewUrlRef.current)
      uploadPreviewUrlRef.current = null
    }

    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const clearCameraMedia = () => {
    setCameraMedia(null)
    clearResult()

    if (cameraPreviewUrlRef.current) {
      URL.revokeObjectURL(cameraPreviewUrlRef.current)
      cameraPreviewUrlRef.current = null
    }
  }

  const previewTitle = result?.media_type === 'video' ? 'Detected Footage' : 'Detected Image'
  const previewDescription =
    result?.media_type === 'video'
      ? 'This is the annotated footage generated by the detector.'
      : 'This is the annotated image generated by the detector.'
  const previewButtonLabel =
    result?.media_type === 'video' ? 'View Footage' : 'View Image'
  const hasAnnotatedMediaResult =
    result?.media_type === 'image'
      ? Boolean(result.annotated_media_url)
      : Boolean(
          result?.annotated_media_url ||
            result?.annotated_media_download_url
        )
  const resolvedOutputFileUrl = resolveBackendMediaUrl(
    result?.annotated_media_download_url ?? null
  )
  const detectionPopupMediaUrl =
    result?.annotated_key_frame_url ?? result?.annotated_media_url ?? null
  const detectionPopupMediaType =
    result?.annotated_key_frame_url ? 'image' : result?.media_type ?? 'image'
  const ensurePendingReviewCase = async () => {
    if (!result?.accident_detected) {
      return null
    }

    if (createdCaseId) {
      return createdCaseId
    }

    const db = getFirestoreOrNull()
    if (!db) {
      toast({
        title: 'Incident store unavailable',
        description: 'Could not create a review case because Firestore is not ready.',
        variant: 'destructive',
      })
      return null
    }

    if (!activeMedia) {
      toast({
        title: 'Media unavailable',
        description: 'Could not create a review case because the uploaded media was cleared.',
        variant: 'destructive',
      })
      return null
    }

    const nextCaseId = await createCrashCaseFromDetection(db, {
      actorId: firebaseUser?.uid ?? 'upload-user',
      areaId: profile?.areaId ?? null,
      result,
      source: mode === 'upload' ? 'upload' : 'camera-capture',
      sourceFile: activeMedia.file.name,
      locationLabel: result.location,
    })

    setCreatedCaseId(nextCaseId)
    return nextCaseId
  }

  const reviewCase = async () => {
    setCaseActionLoading('review')

    try {
      const caseId = await ensurePendingReviewCase()
      const params = new URLSearchParams()

      if (caseId) {
        params.set('caseId', caseId)
      }

      const query = params.toString()
      router.push(query ? `/dashboard/map?${query}` : '/dashboard/map')
    } catch (error) {
      toast({
        title: 'Case action failed',
        description:
          error instanceof Error ? error.message : 'Could not prepare the review case.',
        variant: 'destructive',
      })
    } finally {
      setCaseActionLoading(null)
    }
  }

  const keyFrameActions = result?.accident_detected ? (() => (
    <div className="space-y-3">
      <div className="grid gap-2 rounded-md border border-border bg-muted/20 p-3 text-sm sm:grid-cols-2">
        <div>
          <p className="text-xs text-muted-foreground">Confidence</p>
          <p className="font-medium">{(result.confidence * 100).toFixed(0)}%</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Time</p>
          <p className="font-medium">
            {Number.isNaN(new Date(result.timestamp).getTime())
              ? 'Available'
              : new Date(result.timestamp).toLocaleTimeString([], {
                  hour: 'numeric',
                  minute: '2-digit',
            })}
          </p>
        </div>
      </div>

      <div className="grid gap-2">
        <Button
          type="button"
          className="w-full"
          disabled={caseActionLoading != null}
          onClick={reviewCase}
        >
          <ClipboardCheck className="h-4 w-4" />
          Review
        </Button>
      </div>
    </div>
  )) : null

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <div className="flex-1 md:ml-0">
        <DashboardHeader />

        <main className="max-w-5xl space-y-6 p-6">
          <div>
            <h1 className="mb-2 text-3xl font-bold">Upload Media</h1>
            <p className="text-muted-foreground">
              Upload an image or video from your device, or use the browser camera to
              capture a photo or record a video for detection.
            </p>
          </div>

          {error && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {!error && loading ? (
            <Alert>
              <Loader className="h-4 w-4 animate-spin" />
              <AlertDescription>
                Sending the {activeMedia?.mediaType ?? 'selected'} file to the backend and
                waiting for detection to finish.
              </AlertDescription>
            </Alert>
          ) : null}

          {!error && !loading && result ? (
            <Alert>
              <CheckCircle2 className="h-4 w-4" />
              <AlertDescription>
                {resultHasPreview
                  ? `Detection succeeded and the backend returned an annotated ${result.media_type} preview.`
                  : resultHasDownloadOnly
                    ? 'Detection succeeded, but only a non-inline output file is available.'
                    : imageResultHasFallbackPreviewMessage
                      ? result.processing_notes ??
                        'Detection succeeded, but no annotated image preview was available.'
                      : 'Detection succeeded, but no annotated preview was returned.'}
              </AlertDescription>
            </Alert>
          ) : null}

          <Tabs
            value={mode}
            onValueChange={(value) => {
              setMode(value as UploadMode)
              setError('')
            }}
            className="space-y-6"
          >
            <TabsList className="grid w-full max-w-md grid-cols-2 border border-border bg-card">
              <TabsTrigger value="upload">
                <Upload className="mr-2 h-4 w-4" />
                Upload Media
              </TabsTrigger>
              <TabsTrigger value="camera">
                <Camera className="mr-2 h-4 w-4" />
                Use Camera
              </TabsTrigger>
            </TabsList>

            <TabsContent value="upload" className="space-y-4">
              <Card
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                className={`border-2 border-dashed p-10 text-center transition-all ${
                  dragActive
                    ? 'border-primary bg-primary/10'
                    : 'border-border/60 hover:border-border'
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*,video/*"
                  onChange={handleFileInput}
                  className="hidden"
                />

                {uploadedMedia ? (
                  <div className="space-y-3">
                    <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
                      <CheckCircle2 className="h-8 w-8 text-primary" />
                    </div>
                    <div>
                      <p className="font-semibold">{uploadedMedia.file.name}</p>
                      <p className="text-sm text-muted-foreground">
                        {(uploadedMedia.file.size / 1024 / 1024).toFixed(2)} MB
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={loading}
                    >
                      Choose Another File
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-card">
                      <Upload className="h-8 w-8 text-muted-foreground" />
                    </div>
                    <div>
                      <p className="font-semibold">Upload an image or video</p>
                      <p className="text-sm text-muted-foreground">
                        Drag and drop a file here, or browse your files.
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={loading}
                    >
                      <Upload className="mr-2 h-4 w-4" />
                      Select Image or Video
                    </Button>
                  </div>
                )}
              </Card>

              {uploadedMedia && (
                <>
                  <Card className="overflow-hidden border border-border">
                    <div className="border-b border-border p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-semibold">Selected Media Preview</p>
                        <Badge variant="outline" className="capitalize">
                          {uploadedMedia.label}
                        </Badge>
                      </div>
                    </div>
                    <div className="flex items-center justify-center bg-[var(--media-background)] p-4">
                      {uploadedMedia.mediaType === 'image' ? (
                        <img
                          src={uploadedMedia.previewUrl}
                          alt="Selected upload preview"
                          className="max-h-96 max-w-full rounded object-contain"
                        />
                      ) : (
                        <video
                          src={uploadedMedia.previewUrl}
                          controls
                          className="max-h-96 max-w-full rounded object-contain"
                        />
                      )}
                    </div>
                    <div className="border-t border-border p-4 text-sm text-muted-foreground">
                      {uploadedMedia.mediaType === 'image'
                        ? 'This local image will be sent to POST /api/detect/image.'
                        : 'This local video will be sent to POST /api/detect/video.'}
                    </div>
                  </Card>

                  <div className="flex flex-col gap-3 sm:flex-row">
                    <Button
                      type="button"
                      onClick={handleRunDetection}
                      disabled={loading}
                      className="flex-1"
                      size="lg"
                    >
                      {loading ? (
                        <>
                          <Loader className="mr-2 h-4 w-4 animate-spin" />
                          Processing...
                        </>
                      ) : (
                        'Run Detection'
                      )}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={clearUploadedMedia}
                      disabled={loading}
                      size="lg"
                    >
                      Clear
                    </Button>
                  </div>
                </>
              )}
            </TabsContent>

            <TabsContent value="camera" className="space-y-4">
              <CameraCapture
                disabled={loading}
                onError={showError}
                onMediaReady={handleCameraMediaReady}
              />

              {cameraMedia && (
                <>
                  <Card className="overflow-hidden border border-border">
                    <div className="border-b border-border p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-semibold">Current Camera Input</p>
                        <Badge variant="outline" className="capitalize">
                          {cameraMedia.label}
                        </Badge>
                      </div>
                    </div>
                    <div className="flex h-[20rem] items-center justify-center bg-[var(--media-background)] p-4 sm:h-[24rem]">
                      {cameraMedia.mediaType === 'image' ? (
                        <img
                          src={cameraMedia.previewUrl}
                          alt="Captured image preview"
                          className="h-full max-w-full rounded object-contain"
                        />
                      ) : (
                        <video
                          src={cameraMedia.previewUrl}
                          controls
                          className="h-full max-w-full rounded object-contain"
                        />
                      )}
                    </div>
                    <div className="border-t border-border p-4 text-sm text-muted-foreground">
                      {cameraMedia.mediaType === 'image'
                        ? 'This captured image will be sent to POST /api/detect/image.'
                        : 'This recorded video will be sent to POST /api/detect/video.'}
                    </div>
                  </Card>

                  <div className="flex flex-col gap-3 sm:flex-row">
                    <Button
                      type="button"
                      onClick={handleRunDetection}
                      disabled={loading}
                      className="flex-1"
                      size="lg"
                    >
                      {loading ? (
                        <>
                          <Loader className="mr-2 h-4 w-4 animate-spin" />
                          Processing...
                        </>
                      ) : (
                        'Run Detection'
                      )}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={clearCameraMedia}
                      disabled={loading}
                      size="lg"
                    >
                      Clear
                    </Button>
                  </div>
                </>
              )}
            </TabsContent>
          </Tabs>

          {result && (
            <Card className="border border-border">
              <div className="border-b border-border p-6">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <h2 className="text-2xl font-bold">Detection Result</h2>
                  <Badge
                    className={
                      result.accident_detected
                        ? 'min-w-[10.5rem] justify-center border-destructive/50 bg-destructive/20 text-destructive'
                        : 'min-w-[10.5rem] justify-center border-[var(--status-resolved)] bg-[color:var(--status-resolved-bg)] text-[var(--status-resolved)]'
                    }
                    variant="outline"
                  >
                    {result.accident_detected ? 'Possible Crash' : 'No crash flagged'}
                  </Badge>
                </div>
              </div>

              <div className="space-y-6 p-6">
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="min-h-24 rounded-lg border border-border/50 bg-card/50 p-4">
                    <p className="text-sm text-muted-foreground">Confidence</p>
                    <p className="w-[7ch] font-mono text-3xl font-bold tabular-nums">
                      {(result.confidence * 100).toFixed(1)}%
                    </p>
                  </div>
                  <div className="min-h-24 rounded-lg border border-border/50 bg-card/50 p-4">
                    <p className="text-sm text-muted-foreground">Media Type</p>
                    <div className="flex items-center gap-2">
                      {result.media_type === 'video' ? (
                        <Video className="h-5 w-5 text-primary" />
                      ) : (
                        <ImageIcon className="h-5 w-5 text-primary" />
                      )}
                      <p className="min-w-[5.5rem] text-2xl font-semibold capitalize">
                        {result.media_type}
                      </p>
                    </div>
                  </div>
                  <div className="min-h-24 rounded-lg border border-border/50 bg-card/50 p-4">
                    <p className="text-sm text-muted-foreground">Location</p>
                    <p className="min-h-[1.75rem] text-lg font-semibold leading-7">
                      {result.location}
                    </p>
                  </div>
                  <div className="min-h-24 rounded-lg border border-border/50 bg-card/50 p-4">
                    <p className="text-sm text-muted-foreground">Timestamp</p>
                    <p className="min-w-[15ch] whitespace-nowrap font-mono text-lg font-semibold tabular-nums">
                      {new Date(result.timestamp).toLocaleString()}
                    </p>
                  </div>
                </div>

                <div>
                  <p className="mb-3 text-sm font-semibold">Detections</p>
                  {result.detections.length > 0 ? (
                    <div className="space-y-2">
                      {result.detections.map((detection, index) => (
                        <div
                          key={`${detection.label}-${index}`}
                          className="grid grid-cols-[minmax(0,1fr)_8.5rem] items-center gap-3 rounded border border-border/50 bg-card/50 p-3"
                        >
                          <span className="min-w-0 truncate capitalize">
                            {detection.label}
                          </span>
                          <Badge variant="outline" className="justify-center">
                            {(detection.score * 100).toFixed(0)}% confidence
                          </Badge>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      No vehicle/accident detections were returned for this media.
                    </p>
                  )}
                </div>

                <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                  {!hasAnnotatedMediaResult ? (
                    <div className="flex-1 space-y-2">
                      <p className="text-sm text-muted-foreground">
                        {result.media_type === 'video'
                          ? result.annotated_media_warning ??
                            'No annotated footage preview available.'
                          : result.annotated_media_warning ??
                            'No annotated image preview available.'}
                      </p>
                      {result.processing_notes ? (
                        <p className="text-sm text-muted-foreground/80">
                          {result.processing_notes}
                        </p>
                      ) : null}
                      {resolvedOutputFileUrl ? (
                        <Button asChild variant="outline">
                          <a href={resolvedOutputFileUrl} target="_blank" rel="noreferrer">
                            <ExternalLink className="h-4 w-4" />
                            Open Output File
                          </a>
                        </Button>
                      ) : null}
                    </div>
                  ) : (
                    <div className="flex flex-1 flex-col gap-3 sm:flex-row sm:items-center">
                      {result.accident_detected && detectionPopupMediaUrl ? (
                        <div className="flex flex-col gap-2">
                          <DetectedMediaViewer
                            compact
                            initialOpen={result.accident_detected}
                            mediaType={detectionPopupMediaType}
                            mediaUrl={detectionPopupMediaUrl}
                            title="Possible Crash Detected"
                            description="A possible crash was detected. Review the location and camera evidence."
                            buttonLabel="View Detection Popup"
                            actions={keyFrameActions}
                            boxes={result.boxes}
                          />
                          <p className="text-xs text-muted-foreground">
                            This preview shows where the possible crash was detected.
                          </p>
                        </div>
                      ) : null}

                      <DetectedMediaViewer
                        initialOpen={false}
                        mediaType={result.media_type}
                        mediaUrl={result.annotated_media_url ?? null}
                        fallbackUrl={result.annotated_media_download_url ?? null}
                        title={previewTitle}
                        description={previewDescription}
                        buttonLabel={previewButtonLabel}
                        warning={result.annotated_media_warning}
                        boxes={result.boxes}
                      />
                    </div>
                  )}

                  <Button type="button" variant="ghost" onClick={() => setResult(null)}>
                    Clear Result
                  </Button>
                </div>
              </div>
            </Card>
          )}
        </main>
      </div>
    </div>
  )
}

