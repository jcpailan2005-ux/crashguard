'use client'

import { useEffect, useRef, useState } from 'react'
import { Volume2, VolumeX } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { armAccidentAlertAudio, classifyAlarmPlaybackError, playAccidentAlert, playAccidentAlertWithResult } from '@/lib/accident-alert'
import { enqueueFreshDispatcherAlarms } from '@/lib/dispatcher-alarm-delivery'
import { DispatcherIncidentAlarmTracker } from '@/lib/incident-alarm-contract'
import { phase3 } from '@/lib/phase3-api'

/** Lives in the dispatcher layout, so route changes cannot stop incident polling or disarm audio. */
export function DispatcherAlarmMonitor() {
  const [armed, setArmed] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState('')
  const [playbackStatus, setPlaybackStatus] = useState('')
  const trackerRef = useRef(new DispatcherIncidentAlarmTracker())
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const armedRef = useRef(false)
  const pollingRef = useRef(false)
  const queueRef = useRef<Promise<void>>(Promise.resolve())

  useEffect(() => {
    const audio = new Audio('/alert-sound.mp3')
    audio.preload = 'auto'
    audio.loop = false
    audioRef.current = audio
    let stopped = false

    const poll = async () => {
      if (pollingRef.current || stopped) return
      pollingRef.current = true
      try {
        const [notificationResponse, incidentResponse] = await Promise.all([
          phase3.notifications(),
          phase3.incidents(),
        ])
        if (stopped) return
        const delivery = enqueueFreshDispatcherAlarms(
          trackerRef.current,
          notificationResponse.notifications ?? [],
          incidentResponse.incidents ?? [],
          armedRef.current,
          queueRef.current,
          async (incidentId) => {
            if (stopped || !armedRef.current || !audioRef.current) return
            setPlaying(true)
            setPlaybackStatus('ALARM_ELIGIBLE · ALARM_ATTEMPTED · PLAY_CALLED')
            try {
              const result = await playAccidentAlertWithResult(audioRef.current, 1, { beepRepeats: 3 })
              setPlaybackStatus(`PLAY_RESOLVED · ${result.method}${result.mp3Rejection ? ` · MP3 ${result.mp3Rejection}` : ''}`)
              if (!audio.paused) {
                const mediaError = await new Promise<boolean>((resolve) => {
                  const timer = window.setTimeout(() => done(false), 30_000)
                  function done(failed: boolean) {
                    window.clearTimeout(timer)
                    audio.removeEventListener('ended', onEnded)
                    audio.removeEventListener('error', onError)
                    resolve(failed)
                  }
                  const onEnded = () => done(false)
                  const onError = () => done(true)
                  audio.addEventListener('ended', onEnded)
                  audio.addEventListener('error', onError)
                })
                if (mediaError) {
                  await playAccidentAlert(null, 1, { beepRepeats: 3 })
                  setPlaybackStatus('PLAY_RESOLVED · buzzer after MP3 media error')
                }
              }
              setError('')
            } catch (playbackError) {
              const category = classifyAlarmPlaybackError(playbackError)
              setPlaybackStatus(`PLAY_REJECTED · ${category}`)
              setError(`Alarm playback failed for incident ${incidentId}. ${category}. Check browser sound permission and arm the siren again.`)
            } finally {
              setPlaying(false)
            }
          }
        )
        queueRef.current = delivery.pending
        if (!armedRef.current && delivery.eligible.length > 0) {
          setError('A new confirmed incident arrived while the siren was unarmed. Arm the siren for future incidents.')
        }
      } catch {
        if (!stopped) setError('Dispatcher alarm feed is unavailable. Retrying automatically.')
      } finally {
        pollingRef.current = false
      }
    }

    void poll()
    const interval = window.setInterval(() => void poll(), 5_000)
    const onVisibility = () => { if (document.visibilityState === 'visible') void poll() }
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      stopped = true
      window.clearInterval(interval)
      document.removeEventListener('visibilitychange', onVisibility)
      audio.pause()
      audioRef.current = null
    }
  }, [])

  const toggle = async () => {
    if (armedRef.current) {
      armedRef.current = false
      audioRef.current?.pause()
      setPlaying(false)
      setArmed(false)
      return
    }
    const ready = await armAccidentAlertAudio()
    if (!ready) {
      setError('Browser audio could not be armed. Check sound permissions and try again.')
      return
    }
    armedRef.current = true
    setArmed(true)
    setError('')
  }

  return (
    <div className="flex items-center gap-2">
      <Button type="button" size="sm" variant={armed ? 'default' : 'outline'} onClick={() => void toggle()}
        aria-label={armed ? 'Mute dispatcher collision alarm' : 'Arm dispatcher collision alarm'}>
        {armed ? <Volume2 className="mr-1 h-4 w-4" /> : <VolumeX className="mr-1 h-4 w-4" />}
        {playing ? 'Alarm sounding' : armed ? 'Siren armed' : 'Arm siren'}
      </Button>
      {error ? <span role="alert" className="max-w-64 text-xs text-destructive">{error}</span> : null}
      {playbackStatus ? <span role="status" className="max-w-64 text-xs text-muted-foreground">{playbackStatus}</span> : null}
    </div>
  )
}
