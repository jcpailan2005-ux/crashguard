export type AccidentAlertOptions = {
  /**
   * How many buzzer “bursts” (groups of rapid buzz pulses) to play when the MP3
   * is missing or blocked. 1–3. Default 2.
   */
  beepRepeats?: number
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
  const v = Math.min(1, Math.max(0, volume))
  const rounds = Math.min(3, Math.max(1, options?.beepRepeats ?? 2))

  if (audio) {
    audio.volume = v
    try {
      audio.currentTime = 0
      await audio.play()
      const d = audio.duration
      if (Number.isFinite(d) && d >= 0.2) {
        return
      }
    } catch {
      // Autoplay blocked — buzzer below.
    }
  }

  await playBuzzerSynthAlarm(v, rounds)
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
function playBuzzerSynthAlarm(volume: number, rounds: number): Promise<void> {
  return new Promise((resolve) => {
    const ctx = getAudioContext()
    if (!ctx) {
      resolve()
      return
    }

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
    globalThis.setTimeout(() => {
      void ctx.close().then(() => resolve())
    }, Math.max(450, totalMs))
  })
}
