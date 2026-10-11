'use client'
import { FormEvent, useEffect, useState } from 'react'
import { phase3 } from '@/lib/phase3-api'
import type { AuthUser } from '@/lib/api-client'
import { PageHeading } from '@/components/page-heading'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'

export default function UsersPage() {
  const [users, setUsers] = useState<AuthUser[]>([])
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [role, setRole] = useState('RESPONDER')
  const [areaId, setAreaId] = useState('')
  const [areas, setAreas] = useState<Array<Record<string, unknown>>>([])
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [temporary, setTemporary] = useState<string | null>(null)
  const [error, setError] = useState('')
  const refresh = () => phase3.users({ search, role: roleFilter, status: statusFilter }).then((r) => setUsers(r.users)).catch((e) => setError(e.message))
  useEffect(() => { void refresh(); void phase3.areas().then((result) => setAreas(result.areas)) }, [])
  const create = async (event: FormEvent) => {
    event.preventDefault(); setError('')
    try { const result = await phase3.createUser({ email, fullName, role, areaId: areaId || null }); setTemporary(result.user.temporaryPassword); setEmail(''); setFullName(''); setAreaId(''); await refresh() } catch (e) { setError(e instanceof Error ? e.message : 'Create failed') }
  }
  const reset = async (id: string) => { const result = await phase3.resetPassword(id); setTemporary(result.temporaryPassword); await refresh() }
  return <><PageHeading title="User management" description="Create accounts, enforce fresh credentials, and revoke access." />
    {temporary && <Card className="mb-5 border-amber-500 p-4"><p className="font-semibold">Copy this one-time password now</p><code className="mt-2 block break-all text-lg">{temporary}</code><p className="mt-1 text-xs text-muted-foreground">It is not stored or shown again.</p><Button className="mt-3" variant="outline" onClick={() => setTemporary(null)}>I saved it</Button></Card>}
    <Card className="mb-6 p-4"><form onSubmit={create} className="grid gap-3 md:grid-cols-5"><Input placeholder="Full name" value={fullName} onChange={(e) => setFullName(e.target.value)} required /><Input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required /><select aria-label="New user role" className="rounded-md border bg-background px-3" value={role} onChange={(e) => setRole(e.target.value)}><option>ADMIN</option><option>DISPATCHER</option><option>RESPONDER</option></select><select aria-label="Assigned area" className="rounded-md border bg-background px-3" value={areaId} onChange={(e) => setAreaId(e.target.value)}><option value="">No area</option>{areas.map((area) => <option key={String(area.id)} value={String(area.id)}>{String(area.name)}</option>)}</select><Button>Create user</Button></form>{error && <p className="mt-3 text-sm text-destructive">{error}</p>}</Card>
    <Card className="mb-4 grid gap-3 p-4 md:grid-cols-4"><Input aria-label="Search users" placeholder="Search name or email" value={search} onChange={(e) => setSearch(e.target.value)} /><select aria-label="Filter by role" className="rounded-md border bg-background px-3" value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}><option value="">All roles</option><option>ADMIN</option><option>DISPATCHER</option><option>RESPONDER</option></select><select aria-label="Filter by status" className="rounded-md border bg-background px-3" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}><option value="">All statuses</option><option>ACTIVE</option><option>DISABLED</option><option>LOCKED</option></select><Button variant="outline" onClick={() => void refresh()}>Apply filters</Button></Card>
    <div className="space-y-3">{users.map((user) => <Card className="flex flex-col gap-3 p-4 md:flex-row md:items-center" key={user.uid}><div className="min-w-0 flex-1"><p className="font-semibold">{user.displayName}</p><p className="truncate text-sm text-muted-foreground">{user.email} · {user.status} · last login {user.lastLoginAt ?? 'Never'}</p></div><select aria-label={`Area for ${user.displayName}`} className="rounded-md border bg-background px-3 py-2 text-sm" value={user.areaId ?? ''} onChange={(e) => void phase3.updateUser(user.uid, { areaId: e.target.value || null }).then(refresh)}><option value="">No area</option>{areas.map((area) => <option key={String(area.id)} value={String(area.id)}>{String(area.name)}</option>)}</select><select aria-label={`Role for ${user.displayName}`} className="rounded-md border bg-background px-3 py-2 text-sm" value={user.role.toUpperCase()} onChange={(e) => void phase3.setUserRole(user.uid, e.target.value).then(refresh)}><option>ADMIN</option><option>DISPATCHER</option><option>RESPONDER</option></select><Button variant="outline" onClick={() => void reset(user.uid)}>Reset password</Button><Button variant={user.active ? 'destructive' : 'default'} onClick={() => { if (!user.active || window.confirm(`Disable ${user.displayName} and revoke active sessions?`)) void phase3.setUserStatus(user.uid, user.active ? 'DISABLED' : 'ACTIVE').then(refresh) }}>{user.active ? 'Disable' : 'Reactivate'}</Button></Card>)}</div>
  </>
}
