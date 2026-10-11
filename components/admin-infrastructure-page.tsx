'use client'
import { FormEvent, useEffect, useState } from 'react'
import { phase3 } from '@/lib/phase3-api'
import { PageHeading } from '@/components/page-heading'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'

export function AdminInfrastructurePage({ kind }: { kind: 'areas' | 'cameras' }) {
  const [rows, setRows] = useState<Array<Record<string, unknown>>>([])
  const [name, setName] = useState('')
  const [detail, setDetail] = useState('')
  const [error, setError] = useState('')
  const refresh = () => (kind === 'areas' ? phase3.areas().then((r) => r.areas) : phase3.cameras().then((r) => r.cameras)).then(setRows).catch((e) => setError(e.message))
  useEffect(() => { void refresh() }, [kind])
  const submit = async (event: FormEvent) => { event.preventDefault(); try { if (kind === 'areas') await phase3.createArea({ name, description: detail }); else await phase3.createCamera({ name, location: detail, status: 'OFFLINE', detectionEnabled: true }); setName(''); setDetail(''); await refresh() } catch (e) { setError(e instanceof Error ? e.message : 'Create failed') } }
  const toggleCamera = async (row: Record<string, unknown>) => {
    const disabling = row.status !== 'DISABLED'
    if (disabling && !window.confirm(`Disable camera ${String(row.name)}?`)) return
    await phase3.updateCamera(String(row.id), {
      name: row.name, areaId: row.areaId ?? null, location: row.location ?? null,
      status: disabling ? 'DISABLED' : 'OFFLINE', detectionEnabled: !disabling,
      latitude: row.latitude ?? null, longitude: row.longitude ?? null,
    })
    await refresh()
  }
  return <><PageHeading title={kind === 'areas' ? 'Response areas' : 'Camera registry'} description={kind === 'areas' ? 'Manage the geographic scope used for cameras and responders.' : 'Register and configure monitored camera sources.'} /><Card className="mb-6 p-4"><form className="grid gap-3 md:grid-cols-3" onSubmit={submit}><Input value={name} onChange={(e) => setName(e.target.value)} placeholder={kind === 'areas' ? 'Area name' : 'Camera name'} required /><Input value={detail} onChange={(e) => setDetail(e.target.value)} placeholder={kind === 'areas' ? 'Description' : 'Location'} /><Button>Create {kind === 'areas' ? 'area' : 'camera'}</Button></form>{error && <p className="mt-2 text-sm text-destructive">{error}</p>}</Card><div className="grid gap-3 md:grid-cols-2">{rows.map((row) => <Card className="p-4" key={String(row.id)}><p className="font-semibold">{String(row.name)}</p><p className="text-sm text-muted-foreground">{String(row.description ?? row.location ?? row.status ?? '')}</p>{kind === 'cameras' && <><p className="mt-2 text-xs text-muted-foreground">Detection: {row.detectionEnabled ? 'enabled' : 'disabled'} · stream: {row.streamConfigured ? 'configured' : 'not configured'}</p><Button className="mt-3" variant="outline" onClick={() => void toggleCamera(row)}>{row.status === 'DISABLED' ? 'Enable camera' : 'Disable camera'}</Button></>}</Card>)}</div></>
}
