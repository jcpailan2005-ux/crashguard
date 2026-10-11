export type AccidentAlertOptions = {
  /**
   * How many buzzer “bursts” (groups of rapid buzz pulses) to play when the MP3
   * is missing or blocked. 1–3. Default 2.
   */
  beepRepeats?: number
}

export type AccidentAlertPlayback = { method: 'mp3' | 'buzzer'; mp3Rejection: string | null }

/** Only fixed browser error categories reach the UI; never display arbitrary exception text. */
export function classifyAlarmPlaybackError(error: unknown): string {
  if (error && typeof error === 'object' && 'mp3Rejection' in error) {
    const rejection = (error as { mp3Rejection: unknown }).mp3Rejection
    return `${typeof rejection === 'string' ? rejection : 'MP3 unavailable'}; fallback audio unavailable`
  }
  const name = error && typeof error === 'object' && 'name' in error
    ? String((error as { name: unknown }).name) : ''
  if (name === 'NotAllowedError') return 'NotAllowedError: browser audio permission'
  if (name === 'NotSupportedError') return 'NotSupportedError: audio format or asset'
  if (name === 'AbortError') return 'AbortError: playback interrupted'
  return 'Other playback error'
}

/**
 * Tries MP3 first; otherwise plays a harsh **buzzer-style** alarm (low square tone,
 * rapid on/off like an electronic buzzer / door alarm).
 */
export async function playAccidentAlert(
  audio: HTMLAudioElement | null,
  volume: number,
  options?: AccidentAlertOptions
): Promise<void> {
  await playAccidentAlertWithResult(audio, volume, options)
}

export async function playAccidentAlertWithResult(
  audio: HTMLAudioElement | null,
  volume: number,
  options?: AccidentAlertOptions
): Promise<AccidentAlertPlayback> {
  const v = Math.min(1, Math.max(0, volume))
  const rounds = Math.min(3, Math.max(1, options?.beepRepeats ?? 2))
  let mp3Rejection: string | null = null

  if (audio) {
    audio.volume = v
    audio.muted = false
    try {
      audio.currentTime = 0
      await audio.play()
      return { method: 'mp3', mp3Rejection: null }
    } catch (error) {
      mp3Rejection = classifyAlarmPlaybackError(error)
    }
  }

  try {
    await playBuzzerSynthAlarm(v, rounds)
  } catch {
    throw Object.assign(new Error('Alarm playback failed'), { mp3Rejection })
  }
  return { method: 'buzzer', mp3Rejection }
}

let armedAudioContext: AudioContext | null = null

/** Call directly from the dispatcher's Arm button to satisfy browser gesture rules. */
export async function armAccidentAlertAudio(): Promise<boolean> {
  if (armedAudioContext?.state === 'running') return true
  let ctx: AudioContext | null = null
  try {
    ctx = getAudioContext()
    if (!ctx) return false
    await ctx.resume()
    if (ctx.state !== 'running') return false
    armedAudioContext = ctx
    return true
  } catch {
    if (ctx) void ctx.close()
    return false
  }
}

function getAudioContext(): AudioContext | null {
  if (typeof window === 'undefined') {
    return null
  }
  const Ctx =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
  return Ctx ? new Ctx() : null
}

/**
 * Electronic buzzer: square wave ~ buzzer frequency, tight pulses (bzz-bzz-bzz).
 */
async function playBuzzerSynthAlarm(volume: number, rounds: number): Promise<void> {
  const ctx = armedAudioContext ?? getAudioContext()
  if (!ctx) throw new Error('Browser audio is unavailable')
  await ctx.resume()
  if (ctx.state !== 'running') throw new Error('Browser audio is blocked until armed')

  const master = ctx.createGain()
  const peak = Math.min(0.52, Math.max(0.12, volume * 0.5))
  master.gain.setValueAtTime(peak, ctx.currentTime)
  master.connect(ctx.destination)

    /** ~Classic piezo / panel buzzer range */
  const buzzHz = 368
  const pulseOn = 0.062
  const pulseOff = 0.048
  const pulsesPerRound = 26
  let t = ctx.currentTime + 0.02

  for (let r = 0; r < rounds; r += 1) {
    for (let p = 0; p < pulsesPerRound; p += 1) {
      const osc = ctx.createOscillator()
      osc.type = 'square'
      osc.frequency.setValueAtTime(buzzHz, t)

      const g = ctx.createGain()
      g.gain.setValueAtTime(0.0001, t)
      g.gain.exponentialRampToValueAtTime(1, t + 0.008)
      g.gain.exponentialRampToValueAtTime(0.0001, t + pulseOn - 0.012)

      osc.connect(g)
      g.connect(master)
      osc.start(t)
      osc.stop(t + pulseOn + 0.003)
      t += pulseOn + pulseOff
    }
    t += 0.22
  }

  const totalMs = Math.ceil((t - ctx.currentTime + 0.1) * 1000)
  await new Promise<void>((resolve) => globalThis.setTimeout(resolve, Math.max(450, totalMs)))
  if (ctx !== armedAudioContext) await ctx.close()
}
