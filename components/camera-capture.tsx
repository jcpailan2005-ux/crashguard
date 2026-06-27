'use client'

import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, Camera, Loader, Play, Radio, Square } from 'lucide-react'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

export interface CameraCapturedMedia {
  file: File
  label: 'captured image' | 'recorded video'
  mediaType: 'image' | 'video'
  previewUrl: string
}

interface CameraCaptureProps {
  disabled?: boolean
  onError?: (error: string) => void
  onMediaReady?: (media: CameraCapturedMedia) => void
}

function getCameraErrorMessage(error: unknown): string {
  if (!(error instanceof DOMException)) {
    return error instanceof Error ? error.message : 'Failed to access the camera.'
  }

  switch (error.name) {
    case 'NotAllowedError':
      return 'Camera permission was denied. Please allow camera access in your browser settings.'
    case 'NotFoundError':
      return 'No camera was found on this device.'
    case 'NotReadableError':
      return 'The camera is busy or unavailable because another app is using it.'
    case 'OverconstrainedError':
      return 'The requested camera settings are not supported on this device.'
    default:
      return error.message || 'Failed to access the camera.'
  }
}

function getSupportedRecordingMimeType(): string | undefined {
  if (typeof MediaRecorder === 'undefined') {
    return undefined
  }

  const supportedTypes = [
    'video/webm;codecs=vp9',
    'video/webm;codecs=vp8',
    'video/webm',
    'video/mp4',
  ]

  return supportedTypes.find((type) => MediaRecorder.isTypeSupported(type))
}

export function CameraCapture({
  disabled = false,
  onError,
  onMediaReady,
}: CameraCaptureProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const recordedChunksRef = useRef<Blob[]>([])
  const isUnmountingRef = useRef(false)

  const [stream, setStream] = useState<MediaStream | null>(null)
  const [isStartingCamera, setIsStartingCamera] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!stream || !videoRef.current) {
      return
    }

    const videoElement = videoRef.current
    videoElement.srcObject = stream

    const playStream = async () => {
      try {
        await videoElement.play()
      } catch (playError) {
        const message =
          playError instanceof Error
            ? playError.message
            : 'The live camera preview could not start.'

        setError(message)
        onError?.(message)
      }
    }

    void playStream()
  }, [onError, stream])

  useEffect(() => {
    return () => {
      isUnmountingRef.current = true

      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop()
      }

      if (stream) {
        stream.getTracks().forEach((track) => track.stop())
      }
    }
  }, [stream])

  const stopCameraTracks = (activeStream: MediaStream | null) => {
    if (!activeStream) {
      return
    }

    activeStream.getTracks().forEach((track) => track.stop())
  }

  const startCamera = async () => {
    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      const message = 'This browser does not support camera access.'
      setError(message)
      onError?.(message)
      return
    }

    setIsStartingCamera(true)
    setError('')

    try {
      console.info('[camera] Requesting browser camera access')
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: 'environment' },
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      })

      setStream(mediaStream)
      console.info('[camera] Camera stream started')
    } catch (cameraError) {
      const message = getCameraErrorMessage(cameraError)
      console.warn('[camera] Camera start failed', cameraError)
      setError(message)
      onError?.(message)
    } finally {
      setIsStartingCamera(false)
    }
  }

  const stopRecording = () => {
    if (!mediaRecorderRef.current || mediaRecorderRef.current.state === 'inactive') {
      const message = 'No video recording is currently in progress.'
      setError(message)
      onError?.(message)
      return
    }

    setIsRecording(false)
    mediaRecorderRef.current.stop()
  }

  const stopCamera = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
    }

    stopCameraTracks(stream)

    if (videoRef.current) {
      videoRef.current.srcObject = null
    }

    setStream(null)
    setIsRecording(false)
    setIsStartingCamera(false)
  }

  const captureImage = async () => {
    if (!videoRef.current || !canvasRef.current) {
      const message = 'The camera preview is not ready yet.'
      setError(message)
      onError?.(message)
      return
    }

    const videoElement = videoRef.current

    if (videoElement.videoWidth === 0 || videoElement.videoHeight === 0) {
      const message =
        'No captured frame is available yet. Wait for the preview to load, then try again.'
      setError(message)
      onError?.(message)
      return
    }

    const canvasElement = canvasRef.current
    const context = canvasElement.getContext('2d')

    if (!context) {
      const message = 'Unable to prepare the captured image.'
      setError(message)
      onError?.(message)
      return
    }

    canvasElement.width = videoElement.videoWidth
    canvasElement.height = videoElement.videoHeight
    context.drawImage(videoElement, 0, 0, canvasElement.width, canvasElement.height)

    const blob = await new Promise<Blob | null>((resolve) => {
      canvasElement.toBlob(resolve, 'image/jpeg', 0.95)
    })

    if (!blob) {
      const message = 'No captured frame is available right now. Please try again.'
      setError(message)
      onError?.(message)
      return
    }

    setError('')

    const file = new File([blob], `camera-capture-${Date.now()}.jpg`, {
      type: 'image/jpeg',
    })

    console.info('[camera] Captured image ready', {
      filename: file.name,
      size: file.size,
      type: file.type,
    })

    onMediaReady?.({
      file,
      label: 'captured image',
      mediaType: 'image',
      previewUrl: URL.createObjectURL(blob),
    })
  }

  const startRecording = () => {
    if (!stream) {
      const message = 'Start the camera before recording a video.'
      setError(message)
      onError?.(message)
      return
    }

    if (typeof MediaRecorder === 'undefined') {
      const message = 'This browser does not support video recording.'
      setError(message)
      onError?.(message)
      return
    }

    try {
      const mimeType = getSupportedRecordingMimeType()
      const mediaRecorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream)

      recordedChunksRef.current = []

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          recordedChunksRef.current.push(event.data)
        }
      }

      mediaRecorder.onstop = () => {
        const recorderType = mediaRecorder.mimeType || mimeType || 'video/webm'
        const extension = recorderType.includes('mp4') ? 'mp4' : 'webm'

        if (isUnmountingRef.current) {
          recordedChunksRef.current = []
          mediaRecorderRef.current = null
          return
        }

        if (recordedChunksRef.current.length === 0) {
          recordedChunksRef.current = []
          mediaRecorderRef.current = null
          setIsRecording(false)
          return
        }

        const blob = new Blob(recordedChunksRef.current, { type: recorderType })
        const file = new File(
          [blob],
          `camera-recording-${Date.now()}.${extension}`,
          { type: recorderType }
        )

        recordedChunksRef.current = []
        mediaRecorderRef.current = null
        setIsRecording(false)
        setError('')

        onMediaReady?.({
          file,
          label: 'recorded video',
          mediaType: 'video',
          previewUrl: URL.createObjectURL(blob),
        })
      }

      mediaRecorder.onerror = () => {
        const message = 'Video recording failed. Please try again.'
        setError(message)
        onError?.(message)
        setIsRecording(false)
      }

      mediaRecorder.start()
      mediaRecorderRef.current = mediaRecorder
      setIsRecording(true)
      setError('')
    } catch (recordingError) {
      const message =
        recordingError instanceof Error
          ? recordingError.message
          : 'Failed to start video recording.'

      setError(message)
      onError?.(message)
      setIsRecording(false)
    }
  }

  const isStreaming = !!stream

  return (
    <Card className="overflow-hidden border border-border">
      <div className="relative aspect-video bg-[var(--media-background)]">
        {isStreaming ? (
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full items-center justify-center p-6">
            <div className="space-y-3 text-center">
              {isStartingCamera ? (
                <Loader className="mx-auto h-8 w-8 animate-spin text-primary" />
              ) : (
                <Camera className="mx-auto h-12 w-12 text-primary/60" />
              )}
              <div>
                <p className="font-medium text-[var(--media-foreground)]">
                  {isStartingCamera ? 'Starting camera...' : 'Camera preview is off'}
                </p>
                <p className="text-sm text-[var(--media-muted-foreground)]">
                  Start the browser camera to capture a photo or record a video.
                </p>
              </div>
            </div>
          </div>
        )}

        {isStreaming && (
          <div className="absolute left-4 top-4 rounded-full border border-[var(--status-live)] bg-[color:var(--status-live-bg)] px-3 py-1 text-xs font-semibold text-[var(--status-live)]">
            LIVE
          </div>
        )}

        {isRecording && (
          <div className="absolute right-4 top-4 flex items-center gap-2 rounded-full bg-destructive px-3 py-1 text-xs font-semibold text-destructive-foreground">
            <Radio className="h-3.5 w-3.5" />
            Recording
          </div>
        )}
      </div>

      <div className="space-y-4 p-4">
        {error && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          <Button
            type="button"
            onClick={startCamera}
            disabled={disabled || isStartingCamera || isStreaming}
          >
            {isStartingCamera ? (
              <>
                <Loader className="mr-2 h-4 w-4 animate-spin" />
                Starting...
              </>
            ) : (
              <>
                <Play className="mr-2 h-4 w-4" />
                Start Camera
              </>
            )}
          </Button>

          <Button
            type="button"
            variant="outline"
            onClick={stopCamera}
            disabled={disabled || !isStreaming}
          >
            <Square className="mr-2 h-4 w-4" />
            Stop Camera
          </Button>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <Button
            type="button"
            variant="secondary"
            onClick={captureImage}
            disabled={disabled || !isStreaming || isRecording}
          >
            <Camera className="mr-2 h-4 w-4" />
            Capture Image
          </Button>

          {!isRecording ? (
            <Button
              type="button"
              variant="secondary"
              onClick={startRecording}
              disabled={disabled || !isStreaming}
            >
              <Radio className="mr-2 h-4 w-4" />
              Start Recording
            </Button>
          ) : (
            <Button
              type="button"
              variant="destructive"
              onClick={stopRecording}
              disabled={disabled}
            >
              <Square className="mr-2 h-4 w-4" />
              Stop Recording
            </Button>
          )}
        </div>
      </div>

      <canvas ref={canvasRef} className="hidden" />
    </Card>
  )
}
