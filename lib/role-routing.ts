export type OperationalRole = 'admin' | 'dispatcher' | 'responder'

export const ROLE_HOME: Record<OperationalRole, string> = {
  admin: '/admin',
  dispatcher: '/dispatcher',
  responder: '/responder',
}

export function homeForRole(role: string | null | undefined): string {
  const normalized = String(role ?? '').toLowerCase() as OperationalRole
  return ROLE_HOME[normalized] ?? '/login'
}

export function routeBelongsToRole(pathname: string, role: OperationalRole): boolean {
  return pathname === ROLE_HOME[role] || pathname.startsWith(`${ROLE_HOME[role]}/`)
}

const LEGACY_SUFFIX_ROUTES: Record<string, Record<OperationalRole, string>> = {
  '/settings': { admin: '/admin/settings', dispatcher: '/dispatcher/settings', responder: '/responder/settings' },
  '/ip-camera': { admin: '/admin/cameras', dispatcher: '/dispatcher/live', responder: '/responder' },
  '/live-camera': { admin: '/admin/cameras', dispatcher: '/dispatcher/live', responder: '/responder' },
  '/notifications': { admin: '/admin/notifications', dispatcher: '/dispatcher/notifications', responder: '/responder/notifications' },
  '/notifications/all': { admin: '/admin/notifications', dispatcher: '/dispatcher/notifications', responder: '/responder/notifications' },
  '/history': { admin: '/admin/incidents', dispatcher: '/dispatcher/history', responder: '/responder/history' },
  '/map': { admin: '/admin/incidents', dispatcher: '/dispatcher/map', responder: '/responder/map' },
  '/analytics': { admin: '/admin/analytics', dispatcher: '/dispatcher', responder: '/responder' },
  '/responder-queue': { admin: '/admin/incidents', dispatcher: '/dispatcher/review', responder: '/responder/assignment' },
  '/upload': { admin: '/admin/cameras', dispatcher: '/dispatcher/live', responder: '/responder' },
}

export function legacyDashboardRedirect(pathname: string, role: OperationalRole): string | null {
  if (pathname === '/dashboard') return homeForRole(role)
  if (!pathname.startsWith('/dashboard/')) return null
  const suffix = pathname.slice('/dashboard'.length)
  return LEGACY_SUFFIX_ROUTES[suffix]?.[role] ?? homeForRole(role)
}
