import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'
import * as jsx from 'react/jsx-runtime'
import * as audio from '../lib/accident-alert.ts'
import { DispatcherIncidentAlarmTracker } from '../lib/incident-alarm-contract.ts'
import { enqueueFreshDispatcherAlarms } from '../lib/dispatcher-alarm-delivery.ts'

// Execute the actual monitor and its production tracker/playback code. Only
// React scheduling, the browser surfaces, and API transport are substituted.
function mountMonitor() {
  audio.disarmAccidentAlertAudio()
  let incidents: any[] = []
  let poll: () => void = () => {}
  let index = 0
  const slots: any[] = []
  const effects: Array<() => void> = []
  const cleanups: Array<() => void> = []
  const elements: FakeAudio[] = []
  class FakeAudio {
    volume = 1; currentTime = 0; muted = false; paused = true; preload = ''; loop = false
    plays = 0; blocked = false
    constructor(_src: string) { elements.push(this) }
    pause() { this.paused = true }
    async play() {
      this.plays += 1
      if (this.blocked) throw Object.assign(new Error('blocked'), { name: 'NotAllowedError' })
    }
  }
  const hooks = {
    useState(initial: any) {
      const slot = index++
      if (!(slot in slots)) slots[slot] = initial
      return [slots[slot], (value: any) => { slots[slot] = typeof value === 'function' ? value(slots[slot]) : value }]
    },
    useRef(initial: any) {
      const slot = index++
      return slots[slot] ??= { current: initial }
    },
    useEffect(effect: () => any) {
      const slot = index++
      if (!(slot in slots)) {
        slots[slot] = true
        effects.push(() => { const cleanup = effect(); if (cleanup) cleanups.push(cleanup) })
      }
    },
  }
  const exports: Record<string, any> = {}
  const compiled = ts.transpileModule(readFileSync('components/dispatcher-alarm-monitor.tsx', 'utf8'), {
    compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText
  vm.runInNewContext(compiled, { exports, Audio: FakeAudio,
    window: { setInterval: (fn: () => void) => { poll = fn; return 1 }, clearInterval() {} },
    document: { addEventListener() {}, removeEventListener() {} },
    require: (name: string) => {
      if (name === 'react') return hooks
      if (name === 'react/jsx-runtime') return jsx
      if (name === 'lucide-react') return { Volume2: 'i', VolumeX: 'i' }
      if (name === 'next/link') return { default: 'a' }
      if (name === '@/components/ui/button') return { Button: 'button' }
      if (name === '@/lib/accident-alert') return audio
      if (name === '@/lib/dispatcher-alarm-delivery') return { enqueueFreshDispatcherAlarms }
      if (name === '@/lib/incident-alarm-contract') return { DispatcherIncidentAlarmTracker }
      if (name === '@/lib/phase3-api') return { phase3: {
        incidents: async () => ({ incidents }),
        // Notification failure must not silence a committed incident.
        notifications: async () => { throw new Error('unavailable') },
      } }
      throw new Error(`Unexpected import ${name}`)
    },
  })
  const render = () => { index = 0; const tree = exports.DispatcherAlarmMonitor(); effects.splice(0).forEach(fn => fn()); return tree }
  render()
  return { render, elements, poll: () => poll(), setIncidents: (value: any[]) => { incidents = value },
    cleanup: () => { cleanups.forEach(fn => fn()); audio.disarmAccidentAlertAudio() } }
}
function nodes(node: any): any[] {
  if (!node || typeof node !== 'object') return []
  const children = node.props?.children
  return [node, ...(Array.isArray(children) ? children : [children]).flatMap(nodes)]
}
function contents(node: any): string {
  if (typeof node === 'string') return node
  if (!node || typeof node !== 'object') return ''
  const children = node.props?.children
  return (Array.isArray(children) ? children : [children]).map(contents).join(' ')
}
const flush = async () => { for (let i = 0; i < 30; i++) await Promise.resolve() }

test('actual dispatcher monitor: shared arming, candidate/history silence, exactly one fresh attempt and duplicate silence', async () => {
  const monitor = mountMonitor()
  try {
    await flush()
    // This is the same exported arming operation used by Live Monitor's button.
    await audio.armAccidentAlertAudio(monitor.elements[0] as unknown as HTMLAudioElement)
    assert.match(contents(monitor.render()), /Siren armed/)
    const primingPlays = monitor.elements[0].plays
    const fresh = { id: 'CONFIRMED', detectionMode: 'temporal_collision', createdAt: new Date(Date.now() + 1000).toISOString(),
      evidenceSummary: { finalDecision: 'confirmed_crash' } }
    monitor.setIncidents([{ ...fresh, id: 'CANDIDATE', evidenceSummary: { finalDecision: 'candidate' } },
      { ...fresh, id: 'HISTORY', createdAt: '2000-01-01T00:00:00Z' }])
    monitor.poll(); await flush()
    assert.equal(monitor.elements[0].plays, primingPlays)
    monitor.setIncidents([fresh]); monitor.poll(); await flush()
    assert.equal(monitor.elements[0].plays, primingPlays + 1)
    monitor.poll(); await flush()
    assert.equal(monitor.elements[0].plays, primingPlays + 1)
  } finally { monitor.cleanup() }
})

test('actual dispatcher monitor: Arm Siren unlocks its element and playback rejection renders warning without modifying incident', async () => {
  const monitor = mountMonitor()
  try {
    await flush()
    const button = nodes(monitor.render()).find(node => node.props?.['aria-label'] === 'Arm dispatcher collision alarm')
    button.props.onClick(); await flush()
    assert.equal(monitor.elements[0].plays, 1)
    assert.match(contents(monitor.render()), /Siren armed/)
    monitor.elements[0].blocked = true
    const incident = Object.freeze({ id: 'SAVED', detectionMode: 'temporal_collision',
      createdAt: new Date(Date.now() + 1000).toISOString(), evidenceSummary: Object.freeze({ finalDecision: 'confirmed_crash' }) })
    monitor.setIncidents([incident]); monitor.poll(); await flush()
    const warning = nodes(monitor.render()).find(node => node.props?.role === 'alert' && contents(node).includes('Alarm playback failed'))
    assert.ok(warning)
    assert.match(contents(warning), /SAVED.*NotAllowedError/)
    assert.equal(incident.id, 'SAVED')
    assert.equal(monitor.elements[0].plays, 2)
    monitor.poll(); await flush()
    assert.equal(monitor.elements[0].plays, 2)
  } finally { monitor.cleanup() }
})
