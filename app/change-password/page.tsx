'use client'

import { FormEvent, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/components/auth-provider'
import { changePostgresPassword } from '@/lib/api-client'
import { homeForRole } from '@/lib/role-routing'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export default function ChangePasswordPage() {
  const router = useRouter()
  const { profile, loading, setSessionUser } = useAuth()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!loading && !profile) router.replace('/login')
  }, [loading, profile, router])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (newPassword !== confirmation) return setError('New passwords do not match.')
    setSaving(true)
    setError('')
    try {
      const user = await changePostgresPassword(currentPassword, newPassword)
      setSessionUser(user)
      router.replace(homeForRole(user.role))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Password change failed.')
    } finally {
      setSaving(false)
    }
  }

  if (loading || !profile) return null
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4">
      <Card className="w-full max-w-md p-6">
        <h1 className="text-2xl font-bold">{profile.mustChangePassword ? 'Set your permanent password' : 'Change password'}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{profile.mustChangePassword ? 'Your one-time password must be replaced before operational access is enabled.' : 'Confirm your current password, then choose a new secure password.'}</p>
        <form className="mt-6 space-y-4" onSubmit={submit}>
          <div className="space-y-2"><Label htmlFor="current">{profile.mustChangePassword ? 'Temporary password' : 'Current password'}</Label><Input id="current" type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} required /></div>
          <div className="space-y-2"><Label htmlFor="new">New password</Label><Input id="new" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} minLength={12} required /></div>
          <div className="space-y-2"><Label htmlFor="confirm">Confirm new password</Label><Input id="confirm" type="password" value={confirmation} onChange={(e) => setConfirmation(e.target.value)} minLength={12} required /></div>
          {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
          <Button className="w-full" disabled={saving}>{saving ? 'Saving…' : 'Change password'}</Button>
          {!profile.mustChangePassword ? <Button asChild type="button" variant="outline" className="w-full"><Link href={homeForRole(profile.role)}>Cancel</Link></Button> : null}
        </form>
      </Card>
    </main>
  )
}
