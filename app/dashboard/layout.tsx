'use client'

import { useEffect } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { useAuth } from '@/components/auth-provider'
import { isDashboardRole } from '@/lib/auth-profile'
import { PermissionMessage } from '@/components/permission-message'
import { legacyDashboardRedirect } from '@/lib/role-routing'

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { sessionUser, loading, profile, signOutUser } = useAuth()
  const router = useRouter()
  const pathname = usePathname()
  const legacyRedirect = profile ? legacyDashboardRedirect(pathname, profile.role) : null

  useEffect(() => {
    if (loading) return

    if (!sessionUser) {
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

    const target = legacyDashboardRedirect(pathname, profile.role)
    if (target) router.replace(target)

  }, [sessionUser, loading, pathname, profile, router, signOutUser])

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-muted-foreground">
        Loading account...
      </div>
    )
  }

  if (!sessionUser || !profile || !profile.active) {
    return null
  }

  if (!isDashboardRole(profile.role)) {
    return <PermissionMessage onSignOut={() => void signOutUser().then(() => router.replace('/login'))} />
  }

  if (legacyRedirect) return null

  return <>{children}</>
}
