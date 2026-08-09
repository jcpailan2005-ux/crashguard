'use client'

import Link from 'next/link'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import {
  LayoutDashboard,
  Camera,
  MapPin,
  Bell,
  ImageIcon,
  ListChecks,
  History as HistoryIcon,
  BarChart3,
  ChevronRight,
  ChevronDown,
  Menu,
  Settings,
  Video,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { useAuth } from '@/components/auth-provider'
import { Button } from '@/components/ui/button'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'

interface NavItem {
  name: string
  href: string
  icon: React.ReactNode
  children?: Array<{
    name: string
    href: string
  }>
}

const responderNavItems: NavItem[] = [
  { name: 'Dashboard', href: '/dashboard', icon: <LayoutDashboard className="w-5 h-5" /> },
  { name: 'Responder Queue', href: '/dashboard/responder-queue', icon: <ListChecks className="w-5 h-5" /> },
  { name: 'History', href: '/dashboard/history', icon: <HistoryIcon className="w-5 h-5" /> },
  { name: 'Notifications', href: '/dashboard/notifications', icon: <Bell className="w-5 h-5" /> },
  { name: 'Settings', href: '/dashboard/settings', icon: <Settings className="w-5 h-5" /> },
]

const adminNavItems: NavItem[] = [
  { name: 'Dashboard', href: '/dashboard', icon: <LayoutDashboard className="w-5 h-5" /> },
  { name: 'Live Camera', href: '/dashboard/ip-camera', icon: <Camera className="w-5 h-5" /> },
  { name: 'Map Review', href: '/dashboard/map', icon: <MapPin className="w-5 h-5" /> },
  { name: 'Notifications', href: '/dashboard/notifications', icon: <Bell className="w-5 h-5" /> },
  { name: 'Analytics', href: '/dashboard/analytics', icon: <BarChart3 className="w-5 h-5" /> },
  { name: 'Settings', href: '/dashboard/settings', icon: <Settings className="w-5 h-5" /> },
  { name: 'CCTV', href: '/samples', icon: <Video className="w-5 h-5" /> },
]

const defaultNavItems: NavItem[] = [
  { name: 'Dashboard', href: '/dashboard', icon: <LayoutDashboard className="w-5 h-5" /> },
  { name: 'Notifications', href: '/dashboard/notifications', icon: <Bell className="w-5 h-5" /> },
  { name: 'Settings', href: '/dashboard/settings', icon: <Settings className="w-5 h-5" /> },
]

export function Sidebar() {
  const pathname = usePathname()
  const router = useRouter()
  const searchParams = useSearchParams()
  const { profile, signOutUser } = useAuth()
  const [isOpen, setIsOpen] = useState(false)
  const [isCctvExpanded, setIsCctvExpanded] = useState(pathname.startsWith('/samples'))
  const [isSigningOut, setIsSigningOut] = useState(false)

  useEffect(() => {
    if (pathname.startsWith('/samples')) {
      setIsCctvExpanded(true)
    }
  }, [pathname])

  const isActive = (href: string) => pathname === href || pathname.startsWith(href + '/')
  const selectedArea = searchParams.get('area') ?? 'talomo'
  const normalizedRole = String(profile?.role ?? '').toLowerCase()
  const isAdmin = normalizedRole === 'admin'
  const isNormalUser = normalizedRole === 'user'
  const isResponder = normalizedRole === 'responder'
  const responderArea = normalizedRole === 'responder' ? profile?.areaId ?? null : null
  const roleLabel =
    isAdmin
      ? 'Admin'
      : normalizedRole === 'responder'
        ? 'Responder'
        : 'User'

  const effectiveNavItems = isResponder
    ? responderNavItems
    : isAdmin
      ? adminNavItems
      : defaultNavItems

  const getItemHref = (href: string) => {
    if (!responderArea) return href
    if (href === '/samples') return `/samples?area=${responderArea}`
    if (!href.startsWith('/dashboard')) return href
    return `${href}?area=${responderArea}`
  }

  const isChildActive = (href: string) => {
    if (!pathname.startsWith('/samples')) return false
    const area = new URLSearchParams(href.split('?')[1] ?? '').get('area')
    return selectedArea === area
  }

  const handleSignOut = async () => {
    setIsSigningOut(true)
    try {
      await signOutUser()
      router.replace('/login')
    } finally {
      setIsSigningOut(false)
    }
  }

  return (
    <>
      {/* Mobile menu button */}
      <div className="md:hidden fixed top-4 left-4 z-40">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setIsOpen(!isOpen)}
          className="bg-card border border-border"
        >
          <Menu className="w-5 h-5" />
        </Button>
      </div>

      {/* Overlay for mobile */}
      {isOpen && (
        <div
          className="fixed inset-0 z-30 bg-[var(--scrim)] md:hidden"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed left-0 top-0 z-30 flex h-screen w-64 flex-col border-r border-sidebar-border bg-sidebar transition-transform duration-300 ${
          isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        }`}
      >
        {/* Logo */}
        <div className="flex-shrink-0 p-6 border-b border-sidebar-border">
          <Link href="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
            <div className="w-10 h-10 rounded-lg bg-sidebar-primary flex items-center justify-center">
              <span className="text-sidebar-primary-foreground font-bold text-lg">CD</span>
            </div>
            <div className="flex-1">
              <h1 className="font-bold text-sidebar-primary">Crash Detect</h1>
              <p className="text-xs text-sidebar-accent-foreground">AI Monitor</p>
            </div>
          </Link>
        </div>

        {/* Navigation */}
        <nav className="min-h-0 flex-1 space-y-2 overflow-y-auto p-4 pb-6">
          {effectiveNavItems.map((item) => {
            if (!item.children) {
              return (
                <Link
                  key={item.href}
                  href={getItemHref(item.href)}
                  onClick={() => setIsOpen(false)}
                  className={`flex items-center gap-3 px-4 py-2.5 rounded-lg transition-all ${
                    isActive(item.href)
                      ? 'bg-sidebar-primary text-sidebar-primary-foreground'
                      : 'text-sidebar-foreground hover:bg-sidebar-accent'
                  }`}
                >
                  {item.icon}
                  <span className="font-medium">{item.name}</span>
                  {isActive(item.href) && (
                    <ChevronRight className="w-4 h-4 ml-auto" />
                  )}
                </Link>
              )
            }

            const parentActive = pathname.startsWith(item.href)
            const expanded = isCctvExpanded
            const visibleChildren = responderArea
              ? item.children.filter((child) => child.href.endsWith(`area=${responderArea}`))
              : item.children

            return (
              <div key={item.href} className="space-y-1">
                <button
                  type="button"
                  onClick={() => setIsCctvExpanded((prev) => !prev)}
                  className={`flex w-full items-center gap-3 px-4 py-2.5 rounded-lg text-left transition-all ${
                    parentActive
                      ? 'bg-sidebar-primary text-sidebar-primary-foreground'
                      : 'text-sidebar-foreground hover:bg-sidebar-accent'
                  }`}
                >
                  {item.icon}
                  <span className="font-medium">{item.name}</span>
                  {expanded ? (
                    <ChevronDown className="ml-auto h-4 w-4" />
                  ) : (
                    <ChevronRight className="ml-auto h-4 w-4" />
                  )}
                </button>

                {expanded && (
                  <div className="ml-4 space-y-1 border-l border-sidebar-border pl-3">
                    {visibleChildren.map((child) => (
                      <Link
                        key={child.href}
                        href={child.href}
                        onClick={() => setIsOpen(false)}
                        className={`block rounded-md px-3 py-2 text-sm transition-all ${
                          isChildActive(child.href)
                            ? 'bg-sidebar-primary text-sidebar-primary-foreground'
                            : 'text-sidebar-foreground/90 hover:bg-sidebar-accent'
                        }`}
                      >
                        {child.name}
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </nav>

        {/* Footer status */}
        <div className="flex-shrink-0 space-y-2 border-t border-sidebar-border bg-sidebar p-4">
          {!isResponder ? (
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button type="button" variant="outline" className="w-full" disabled={isSigningOut}>
                  Sign Out
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent className="sm:max-w-md">
                <AlertDialogHeader className="items-center gap-3 text-center">
                  <AlertDialogTitle>Are you sure you want to logout?</AlertDialogTitle>
                  <AlertDialogDescription className="max-w-sm text-center">
                    You will need to sign in again to access the dashboard.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter className="mt-2 gap-5 sm:justify-center">
                  <AlertDialogCancel>No</AlertDialogCancel>
                  <AlertDialogAction onClick={handleSignOut} disabled={isSigningOut}>
                    Yes
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          ) : null}
          <div className="bg-card/50 rounded-lg p-3 border border-border">
            <div className="space-y-2 text-xs">
              <div className="flex items-center justify-between gap-2">
                <span className="text-muted-foreground">Role</span>
                <span className="font-semibold text-sidebar-foreground">{roleLabel}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 animate-pulse rounded-full bg-[var(--status-online)]" />
                <span className="text-muted-foreground">Backend Ready</span>
              </div>
            </div>
          </div>
        </div>
      </aside>
      <div className="hidden w-64 flex-shrink-0 md:block" aria-hidden="true" />
    </>
  )
}

export function DashboardHeader() {
  return (
    <header className="border-b border-border bg-card/50 backdrop-blur">
      <div className="flex items-center justify-between px-6 py-4">
        <h1 className="text-2xl font-bold text-balance">Car Crash Detection</h1>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span>Live</span>
          <div className="h-2 w-2 animate-pulse rounded-full bg-[var(--status-live)]" />
        </div>
      </div>
    </header>
  )
}
