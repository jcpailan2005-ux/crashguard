import { homeForRole } from './role-routing.ts'

export interface AuthenticatedLoginUser {
  active: boolean
  mustChangePassword: boolean
  role: string
}

interface LoginDependencies<TUser extends AuthenticatedLoginUser> {
  login: (email: string, password: string) => Promise<unknown>
  currentUser: () => Promise<TUser>
}

export async function authenticateAndResolveSession<TUser extends AuthenticatedLoginUser>(
  email: string,
  password: string,
  dependencies: LoginDependencies<TUser>
): Promise<{ user: TUser; destination: string }> {
  await dependencies.login(email, password)
  // A successful POST is not enough. This request proves the browser accepted
  // the HttpOnly cookie and the backend can resolve its PostgreSQL session.
  const user = await dependencies.currentUser()
  if (!user.active) throw new Error('This account is inactive.')
  if (user.mustChangePassword) return { user, destination: '/change-password' }

  const destination = homeForRole(user.role)
  if (destination === '/login') {
    throw new Error('This account role is not supported. Ask an admin to update this account.')
  }
  return { user, destination }
}

export function formatLoginError(loginError: unknown): string {
  const message = loginError instanceof Error ? loginError.message : ''
  const status = Number((loginError as { status?: unknown } | null)?.status)

  if (status === 401 || message.includes('Invalid email or password')) {
    return 'Invalid email or password. Please check the account and try again.'
  }
  if (
    message.includes('Cannot connect') ||
    message.includes('Could not reach') ||
    message.includes('Failed to fetch')
  ) {
    return 'Cannot connect to the CrashGuard server.'
  }
  if (status === 503) {
    return 'Authentication service is temporarily unavailable.'
  }
  return message || 'Login failed. Please try again.'
}
