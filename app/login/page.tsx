'use client'

import { FormEvent, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/components/auth-provider'
import { isDashboardRole } from '@/lib/auth-profile'
import { loginWithSQLite } from '@/lib/api-client'
import { storeAuthToken } from '@/lib/session-auth'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export default function LoginPage() {
  const router = useRouter()
  const { authError, firebaseUser, profile, loading, setSessionUser } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const formatLoginError = (loginError: unknown) => {
    const message = loginError instanceof Error ? loginError.message : ''

    if (message.includes('Invalid email or password') || message.includes('401')) {
      return 'Invalid email or password. Please check the account and try again.'
    }

    if (message.includes('Could not reach') || message.includes('Failed to fetch')) {
      return 'Could not reach the backend login service. Make sure FastAPI is running.'
    }

    return message || 'Login failed. Please try again.'
  }

  useEffect(() => {
    if (loading || !firebaseUser || !profile) return

    if (isDashboardRole(profile.role)) {
      router.replace('/dashboard')
      return
    }

    router.replace('/samples')
  }, [firebaseUser, loading, profile, router])

  useEffect(() => {
    if (loading || !firebaseUser || !authError) return
    setError(authError)
  }, [authError, firebaseUser, loading])

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setSubmitting(true)

    try {
      const response = await loginWithSQLite(email, password)
      storeAuthToken(response.token)
      setSessionUser(response.user)

      if (!response.user.active) {
        throw new Error('This account is inactive.')
      }

      if (response.user.role === 'user') {
        router.replace('/samples')
        return
      }

      if (isDashboardRole(response.user.role)) {
        router.replace('/dashboard')
        return
      }

      throw new Error('This account role is not supported. Ask an admin to update this account.')
    } catch (submitError) {
      setError(formatLoginError(submitError))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4">
      <Card className="w-full max-w-md border border-border bg-card/70 p-6">
        <div className="mb-6 space-y-1 text-center">
          <h1 className="text-2xl font-bold">CrashGuard Login</h1>
          <p className="text-sm text-muted-foreground">
            Sign in as admin or assigned barangay responder.
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
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </div>

          {error ? (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}

          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting ? 'Signing in...' : 'Sign in'}
          </Button>

          <Button asChild type="button" variant="outline" className="w-full">
            <Link href="/">Back to Home</Link>
          </Button>

          <p className="text-center text-sm text-muted-foreground">
            Need an account?{' '}
            <Link href="/register" className="font-medium text-primary underline-offset-4 hover:underline">
              Register
            </Link>
          </p>
        </form>
      </Card>
    </main>
  )
}
