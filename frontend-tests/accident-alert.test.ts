import assert from 'node:assert/strict'
import test from 'node:test'

import { armAccidentAlertAudio, classifyAlarmPlaybackError, playAccidentAlert, playAccidentAlertWithResult } from '../lib/accident-alert.ts'

test('successful MP3 playback does not also start fallback audio', async () => {
  let plays = 0
  const audio = {
    volume: 0,
    currentTime: 3,
    duration: Number.NaN,
    play: async () => { plays += 1 },
  } as unknown as HTMLAudioElement
  await playAccidentAlert(audio, 1)
  assert.equal(plays, 1)
  assert.equal(audio.currentTime, 0)
})

test('audio arming reports unavailable browser audio', async () => {
  assert.equal(await armAccidentAlertAudio(), false)
})

test('MP3 playback reports a resolved attempt at positive volume and unmuted state', async () => {
  let plays = 0
  const audio = { volume: 0, muted: true, currentTime: 5,
    play: async () => { plays += 1 } } as unknown as HTMLAudioElement
  const result = await playAccidentAlertWithResult(audio, 1)
  assert.deepEqual(result, { method: 'mp3', mp3Rejection: null })
  assert.equal(plays, 1)
  assert.equal(audio.volume, 1)
  assert.equal(audio.muted, false)
  assert.equal(audio.currentTime, 0)
})

test('MP3 rejection remains detectable if fallback audio is unavailable', async () => {
  const audio = { volume: 0, muted: false, currentTime: 0,
    play: async () => { throw Object.assign(new Error('blocked'), { name: 'NotAllowedError' }) },
  } as unknown as HTMLAudioElement
  await assert.rejects(playAccidentAlertWithResult(audio, 1), (error: unknown) =>
    classifyAlarmPlaybackError(error) === 'NotAllowedError: browser audio permission; fallback audio unavailable')
  assert.equal(classifyAlarmPlaybackError({ name: 'NotAllowedError' }), 'NotAllowedError: browser audio permission')
  assert.equal(classifyAlarmPlaybackError({ name: 'NotSupportedError' }), 'NotSupportedError: audio format or asset')
})
