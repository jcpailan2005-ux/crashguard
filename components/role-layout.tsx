'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { Bell, Monitor, Moon, Sun, UserRound, Wifi, WifiOff } from 'lucide-react'
import { useTheme } from 'next-themes'
import { useAuth } from '@/components/auth-provider'
import { type OperationalRole, homeForRole } from '@/lib/role-routing'
import { phase3, type PersonalTheme } from '@/lib/phase3-api'
import { useToast } from '@/hooks/use-toast'
import { Button } from '@/components/ui/button'
import { DispatcherAlarmMonitor } from '@/components/dispatcher-alarm-monitor'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'

const NAV: Record<OperationalRole, Array<[string, string]>> = {
  admin: [['Dashboard', '/admin'], ['User Management', '/admin/users'], ['Cameras', '/admin/cameras'], ['Areas', '/admin/areas'], ['Incidents', '/admin/incidents'], ['Analytics', '/admin/analytics'], ['AI Configuration', '/admin/ai'], ['System Settings', '/admin/settings/system'], ['Audit Logs', '/admin/audit-logs'], ['Notifications', '/admin/notifications'], ['Personal Settings', '/admin/settings'], ['Profile', '/admin/profile']],
  dispatcher: [['Operations Dashboard', '/dispatcher'], ['Live Monitor', '/dispatcher/live'], ['Detections', '/dispatcher/detections'], ['New Alerts', '/dispatcher/alerts'], ['Pending Review', '/dispatcher/review'], ['Active Incidents', '/dispatcher/incidents'], ['Responders', '/dispatcher/responders'], ['Incident Map', '/dispatcher/map'], ['Incident History', '/dispatcher/history'], ['Notifications', '/dispatcher/notifications'], ['Settings', '/dispatcher/settings'], ['Profile', '/dispatcher/profile']],
  responder: [['Home', '/responder'], ['My Assignment', '/responder/assignment'], ['Map', '/responder/map'], ['Response History', '/responder/history'], ['Notifications', '/responder/notifications'], ['Settings', '/responder/settings'], ['Profile', '/responder/profile']],
}

export function RoleLayout({ role, children }: { role: OperationalRole; children: React.ReactNode }) {
  const { loading, profile, setPersonalPreferences, signOutUser } = useAuth()
  const router = useRouter()
  const pathname = usePathname()
  const { setTheme } = useTheme()
  const { toast } = useToast()
  const [presence, setPresence] = useState<'connecting' | 'online' | 'offline'>('connecting')
  const [themeSaving, setThemeSaving] = useState(false)
  const [signingOut, setSigningOut] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)
  const notificationHref = `/${role}/notifications`
  const compactCameraPage = role === 'dispatcher' && (
    pathname === '/dispatcher/live' || pathname === '/dispatcher/detections'
  )

  useEffect(() => {
    if (loading || !profile || profile.mustChangePassword) return
    let cancelled = false
    const fetchUnread = async () => {
      try {
        const res = await phase3.notifications(true)
        if (!cancelled) setUnreadCount(res.notifications?.length ?? 0)
      } catch {}
    }
    void fetchUnread()
    const interval = window.setInterval(() => void fetchUnread(), 30_000)
    return () => {
      cancelled = true
      window.clearInterval(interval)
    }
  }, [loading, profile, pathname])
  useEffect(() => {
    if (loading) return
    if (!profile) return router.replace('/login')
    if (profile.mustChangePassword) return router.replace('/change-password')
    if (profile.role !== role) return router.replace(homeForRole(profile.role))
  }, [loading, profile, role, router])

  useEffect(() => {
    if (role !== 'responder' || !profile || profile.mustChangePassword) return
    let cancelled = false
    let requestInFlight = false
    const heartbeat = async () => {
      if (requestInFlight || document.visibilityState === 'hidden') return
      requestInFlight = true
      try {
        await phase3.heartbeat()
        if (!cancelled) setPresence('online')
      } catch {
        if (!cancelled) setPresence('offline')
      } finally {
        requestInFlight = false
      }
    }
    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') void heartbeat()
    }
    void heartbeat()
    const interval = window.setInterval(() => void heartbeat(), 25_000)
    document.addEventListener('visibilitychange', onVisibilityChange)
    return () => {
      cancelled = true
      window.clearInterval(interval)
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [profile, role])

  const changeTheme = useCallback(async (nextTheme: PersonalTheme) => {
    if (themeSaving) return
    setTheme(nextTheme)
    setThemeSaving(true)
    try {
      const { preferences } = await phase3.updateOwnPreferences({ theme: nextTheme })
      setPersonalPreferences(preferences)
    } catch (error) {
      toast({ title: 'Theme could not be saved', description: error instanceof Error ? error.message : 'Try again from Personal settings.', variant: 'destructive' })
    } finally {
      setThemeSaving(false)
    }
  }, [setPersonalPreferences, setTheme, themeSaving, toast])

  const signOut = useCallback(async () => {
    if (signingOut) return
    setSigningOut(true)
    await signOutUser()
    router.replace('/login')
  }, [router, signOutUser, signingOut])
  if (loading || !profile || profile.role !== role || profile.mustChangePassword) return null
  return (
    <div className="min-h-screen bg-background md:flex">
      <aside className="border-b border-border bg-card p-4 md:sticky md:top-0 md:h-screen md:w-64 md:overflow-y-auto md:border-b-0 md:border-r">
        <Link href={homeForRole(role)} className="text-xl font-bold">CrashGuard</Link>
        <p className="mt-1 text-xs uppercase tracking-wider text-muted-foreground">{role} workspace</p>
        <nav className="mt-6 grid grid-cols-2 gap-1 sm:grid-cols-3 md:grid-cols-1">
          {NAV[role].map(([label, href]) => {
            const exactOnly = href === '/admin/settings'
            const active = pathname === href || (!exactOnly && href !== homeForRole(role) && pathname.startsWith(`${href}/`))
            return <Link key={href} href={href} className={`rounded-md px-3 py-2 text-sm ${active ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}`}>{label}</Link>
          })}
        </nav>
        <Button variant="outline" className="mt-6 w-full" disabled={signingOut} onClick={() => void signOut()}>{signingOut ? 'Signing out…' : 'Sign out'}</Button>
      </aside>
      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-40 flex h-16 items-center justify-between border-b border-border bg-background/95 px-5 backdrop-blur md:px-8">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold">{NAV[role].find(([, href]) => pathname === href || (href !== homeForRole(role) && pathname.startsWith(`${href}/`)))?.[0] ?? `${role[0].toUpperCase()}${role.slice(1)} workspace`}</p>
            {!compactCameraPage ? (
              <p className="truncate text-xs text-muted-foreground">Signed in as {profile.displayName}</p>
            ) : null}
          </div>
          <div className="flex items-center gap-1">
            {role === 'dispatcher' ? <DispatcherAlarmMonitor /> : null}
            {role === 'responder' ? <div className={`mr-1 hidden items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium sm:flex ${presence === 'online' ? 'border-[var(--status-online)] bg-[color:var(--status-online-bg)] text-[var(--status-online)]' : 'text-muted-foreground'}`}>{presence === 'online' ? <Wifi className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />}{presence === 'online' ? 'Online' : presence === 'offline' ? 'Reconnecting' : 'Connecting'}</div> : null}
            <Button asChild size="icon" variant="ghost" className="relative">
              <Link href={notificationHref} aria-label={`Open notifications (${unreadCount} unread)`}>
                <Bell className="h-4 w-4" />
                {unreadCount > 0 ? (
                  <span className="absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-bold text-primary-foreground">
                    {unreadCount > 99 ? '99+' : unreadCount}
                  </span>
                ) : null}
              </Link>
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild><Button size="icon" variant="ghost" aria-label="Change theme"><Sun className="h-4 w-4 dark:hidden" /><Moon className="hidden h-4 w-4 dark:block" /></Button></DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>Appearance</DropdownMenuLabel>
                <DropdownMenuItem disabled={themeSaving} onClick={() => void changeTheme('light')}><Sun className="h-4 w-4" />Light</DropdownMenuItem>
                <DropdownMenuItem disabled={themeSaving} onClick={() => void changeTheme('dark')}><Moon className="h-4 w-4" />Dark</DropdownMenuItem>
                <DropdownMenuItem disabled={themeSaving} onClick={() => void changeTheme('system')}><Monitor className="h-4 w-4" />System</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <DropdownMenu>
              <DropdownMenuTrigger asChild><Button size="icon" variant="ghost" aria-label="Open profile menu"><UserRound className="h-4 w-4" /></Button></DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>{profile.displayName}<span className="block text-xs font-normal text-muted-foreground">{profile.email}</span></DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild><Link href={`/${role}/profile`}>Profile</Link></DropdownMenuItem>
                <DropdownMenuItem asChild><Link href={`/${role}/settings`}>Personal settings</Link></DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem disabled={signingOut} onClick={() => void signOut()}>{signingOut ? 'Signing out…' : 'Sign out'}</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>
        <main className="p-5 md:p-8">{children}</main>
      </div>
    </div>
  )
}
