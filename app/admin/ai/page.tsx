'use client'
import { useEffect, useState } from 'react'
import { phase3 } from '@/lib/phase3-api'
import { PageHeading } from '@/components/page-heading'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const DEFAULTS: Record<string, string> = {
  crash_detection_enabled: 'true', temporal_threshold: '0.8',
  minimum_track_history: '8', post_contact_verification: 'true',
}
export default function AiSettingsPage() {
  const [values, setValues] = useState(DEFAULTS)
  const [message, setMessage] = useState('')
  useEffect(() => { void phase3.settings().then((r) => setValues((current) => ({ ...current, ...Object.fromEntries(r.settings.map((s) => [String(s.key), String(s.value)])) }))) }, [])
  const save = async (key: string) => {
    if (!window.confirm(`Change critical AI setting ${key}? This action is audited.`)) return
    const raw = values[key]; const value = raw === 'true' ? true : raw === 'false' ? false : Number.isNaN(Number(raw)) ? raw : Number(raw)
    try { await phase3.setSetting(key, value); setMessage(`${key} saved and audited.`) } catch (e) { setMessage(e instanceof Error ? e.message : 'Save failed') }
  }
  return <><PageHeading title="AI configuration" description="Validated operational controls; detector state-machine boundaries remain unchanged." /><div className="grid gap-4 md:grid-cols-2">{Object.entries(values).map(([key, value]) => <Card className="p-5" key={key}><label className="text-sm font-semibold capitalize" htmlFor={key}>{key.replaceAll('_', ' ')}</label><Input className="my-3" id={key} value={value} onChange={(e) => setValues((current) => ({ ...current, [key]: e.target.value }))} /><Button variant="outline" onClick={() => void save(key)}>Save setting</Button></Card>)}</div>{message && <p className="mt-4 text-sm text-muted-foreground">{message}</p>}</>
}
