'use client'

import { FormEvent, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Eye, EyeOff, ShieldCheck } from 'lucide-react'
import { useAuth } from '@/components/auth-provider'
import { getCurrentSQLiteUser, loginWithSQLite } from '@/lib/api-client'
import { authenticateAndResolveSession, formatLoginError } from '@/lib/login-lifecycle'
import { homeForRole } from '@/lib/role-routing'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export default function LoginPage() {
  const router = useRouter()
  const { authError, sessionUser, profile, loading, setSessionUser } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  useEffect(() => {
    if (loading || !sessionUser || !profile) return

    if (profile.mustChangePassword) {
      router.replace('/change-password')
      return
    }
    router.replace(homeForRole(profile.role))
  }, [sessionUser, loading, profile, router])

  useEffect(() => {
    if (loading || !sessionUser || !authError) return
    setError(authError)
  }, [authError, sessionUser, loading])

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setSubmitting(true)

    try {
      const { user, destination } = await authenticateAndResolveSession(email, password, {
        login: loginWithSQLite,
        currentUser: getCurrentSQLiteUser,
      })
      setSessionUser(user)
      router.replace(destination)
    } catch (submitError) {
      setError(formatLoginError(submitError))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="login-light flex min-h-screen items-center justify-center bg-background px-4 py-10 text-foreground">
      <Card className="w-full max-w-md border border-border bg-card p-6 shadow-xl shadow-slate-200/60 sm:p-8">
        <div className="mb-7 space-y-2 text-center">
          <div className="mx-auto flex size-12 items-center justify-center rounded-xl bg-primary text-primary-foreground"><ShieldCheck className="size-6" /></div>
          <h1 className="text-2xl font-bold tracking-tight">CrashGuard</h1>
          <p className="text-sm text-muted-foreground">
            Secure emergency operations and incident coordination.
          </p>
        </div>

        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="pr-10"
                required
              />
              <Button type="button" variant="ghost" size="icon-sm" className="absolute right-1 top-1/2 -translate-y-1/2" aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword} onClick={() => setShowPassword((visible) => !visible)}>
                {showPassword ? <EyeOff /> : <Eye />}
              </Button>
            </div>
          </div>

          {error ? (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}

          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting ? 'Signing in…' : 'Sign in'}
          </Button>

          <Button asChild type="button" variant="outline" className="w-full">
            <Link href="/">Back to Home</Link>
          </Button>

          <p className="text-center text-sm text-muted-foreground">
            Accounts are issued by a CrashGuard administrator.
          </p>
        </form>
      </Card>
    </main>
  )
}
