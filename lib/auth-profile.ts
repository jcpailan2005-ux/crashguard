export interface UserProfile {
  active: boolean
  areaId: string | null
  createdAt: string
  displayName: string
  email: string
  role: 'admin' | 'dispatcher' | 'responder'
  permissions: string[]
  mustChangePassword: boolean
  uid: string
  updatedAt: string
}

export function isDashboardRole(role: UserProfile['role'] | undefined) {
  return role === 'admin' || role === 'dispatcher' || role === 'responder'
}
