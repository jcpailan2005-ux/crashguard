'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/components/auth-provider'
import { isDashboardRole } from '@/lib/auth-profile'
import { PermissionMessage } from '@/components/permission-message'

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { firebaseUser, loading, profile, signOutUser } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (loading) return

    if (!firebaseUser) {
      router.replace('/login')
      return
    }

    if (!profile) {
      router.replace('/login')
      return
    }

    if (!profile.active) {
      signOutUser().finally(() => router.replace('/login'))
      return
    }

  }, [firebaseUser, loading, profile, router, signOutUser])

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-muted-foreground">
        Loading account...
      </div>
    )
  }

  if (!firebaseUser || !profile || !profile.active) {
    return null
  }

  if (!isDashboardRole(profile.role)) {
    return <PermissionMessage onSignOut={() => void signOutUser().then(() => router.replace('/login'))} />
  }

  return <>{children}</>
}
