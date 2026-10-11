'use client'

import { NORMALIZED_BACKEND_URL, type AuthUser } from '@/lib/api-client'

export interface OperationalIncident {
  id: string
  state: string
  priority: string | null
  incidentType: string | null
  detectionMode: 'temporal_collision' | 'aftermath_review'
  aiScore: number
  location: string | null
  latitude: number | null
  longitude: number | null
  detectedAt: string
  reviewStatus: string
  reviewedBy: string | null
  reviewStartedAt?: string | null
  reviewedAt?: string | null
  falseAlarmReason?: string | null
  dispatcherNotes?: string | null
  reviewCaseId?: string | null
  detectorEventId?: string | null
  assignmentId: string | null
  assignmentStatus: string | null
  assignedAt?: string | null
  acceptedAt?: string | null
  enRouteAt?: string | null
  arrivedAt?: string | null
  respondingAt?: string | null
  resolvedAt?: string | null
  responderId: string | null
  responderName?: string | null
  evidenceSummary?: Record<string, unknown>
  media?: Record<string, unknown>
  timeline?: Array<Record<string, unknown>>
  createdAt?: string
  updatedAt?: string
}

export interface OperationalAssignment {
  id: string
  incidentId: string
  responderId: string
  assignedBy?: string | null
  status: string
  priority: string | null
  incidentType?: string | null
  location: string | null
  dispatcherName?: string | null
  detectedAt: string
  assignedAt: string
  acceptedAt?: string | null
  enRouteAt?: string | null
  arrivedAt?: string | null
  respondingAt?: string | null
  resolvedAt?: string | null
  declinedAt?: string | null
  cancelledAt?: string | null
  declineReason?: string | null
  responseNotes?: string | null
  outcome?: string | null
  latitude?: number | null
  longitude?: number | null
  previousAssignmentId?: string | null
  updatedAt?: string
}

export type PersonalTheme = 'light' | 'dark' | 'system'

export interface PersonalPreferences {
  theme: PersonalTheme
  notificationPreferences: {
    alertNotifications?: boolean
    browserNotifications?: boolean
    emailNotifications?: boolean
    alarmAudio?: boolean
  }
  updatedAt?: string
}

export interface ResponderPresence {
  uid: string
  id: string
  email: string
  displayName: string
  areaId: string | null
  availabilityStatus: string | null
  presenceStatus: 'ONLINE' | 'OFFLINE'
  lastSeenAt: string | null
  lastLoginAt: string | null
  activeAssignmentId: string | null
  activeAssignmentStatus: string | null
  activeIncidentId: string | null
}

export interface HeartbeatResponse {
  presenceStatus: 'ONLINE'
  lastSeenAt: string
  availabilityStatus: string
  onlineTimeoutSeconds: number
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  const response = await fetch(`${NORMALIZED_BACKEND_URL}/api/v3${path}`, {
    ...init,
    headers,
    credentials: 'include',
  })
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    try {
      const body = (await response.json()) as { detail?: string }
      message = body.detail ?? message
    } catch {}
    throw new Error(message)
  }
  return camelize(await response.json()) as T
}

function camelize(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(camelize)
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value as Record<string, unknown>).map(([key, item]) => [
      key.replace(/_([a-z])/g, (_, letter: string) => letter.toUpperCase()), camelize(item),
    ]))
  }
  return value
}

export interface OperationalNotification {
  id: string
  userId: string
  incidentId?: string | null
  type: string
  title: string
  message: string
  readAt?: string | null
  createdAt: string
}

export const phase3 = {
  ownProfile: () => request<{ user: AuthUser }>('/me/profile'),
  updateOwnProfile: (fullName: string) =>
    request<{ user: AuthUser }>('/me/profile', {
      method: 'PATCH', body: JSON.stringify({ fullName }),
    }),
  ownPreferences: () =>
    request<{ preferences: PersonalPreferences }>('/me/preferences'),
  updateOwnPreferences: (body: Partial<Pick<PersonalPreferences, 'theme' | 'notificationPreferences'>>) =>
    request<{ preferences: PersonalPreferences }>('/me/preferences', {
      method: 'PATCH', body: JSON.stringify(body),
    }),
  users: (filters: { search?: string; role?: string; status?: string } = {}) => {
    const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => Boolean(value)) as string[][])
    return request<{ users: AuthUser[] }>(`/admin/users${query.size ? `?${query}` : ''}`)
  },
  createUser: (body: { email: string; fullName: string; role: string; areaId?: string | null }) =>
    request<{ user: AuthUser & { temporaryPassword: string } }>('/admin/users', {
      method: 'POST', body: JSON.stringify(body),
    }),
  setUserStatus: (id: string, status: string) =>
    request<{ user: AuthUser }>(`/admin/users/${id}/status`, {
      method: 'PATCH', body: JSON.stringify({ status }),
    }),
  setUserRole: (id: string, role: string) =>
    request<{ user: AuthUser }>(`/admin/users/${id}/role`, {
      method: 'PATCH', body: JSON.stringify({ role }),
    }),
  updateUser: (id: string, body: { email?: string; fullName?: string; areaId?: string | null }) =>
    request<{ user: AuthUser }>(`/admin/users/${id}`, {
      method: 'PATCH', body: JSON.stringify(body),
    }),
  resetPassword: (id: string) =>
    request<{ userId: string; temporaryPassword: string; mustChangePassword: boolean }>(`/admin/users/${id}/reset-password`, { method: 'POST' }),
  areas: () => request<{ areas: Array<Record<string, unknown>> }>('/areas'),
  createArea: (body: { name: string; description?: string }) => request('/areas', { method: 'POST', body: JSON.stringify(body) }),
  cameras: () => request<{ cameras: Array<Record<string, unknown>> }>('/cameras'),
  createCamera: (body: Record<string, unknown>) => request('/cameras', { method: 'POST', body: JSON.stringify(body) }),
  updateCamera: (id: string, body: Record<string, unknown>) => request(`/cameras/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  incidents: (reviewStatus?: string) =>
    request<{ incidents: OperationalIncident[] }>(`/incidents${reviewStatus ? `?reviewStatus=${encodeURIComponent(reviewStatus)}` : ''}`),
  claim: (id: string) => request(`/dispatcher/incidents/${id}/claim`, { method: 'POST' }),
  review: (id: string, body: Record<string, unknown>) =>
    request(`/dispatcher/incidents/${id}/review`, { method: 'POST', body: JSON.stringify(body) }),
  responders: () => request<{ responders: ResponderPresence[] }>('/responders/presence'),
  heartbeat: () => request<HeartbeatResponse>('/responder/presence/heartbeat', { method: 'POST' }),
  assign: (incidentId: string, responderId: string) =>
    request(`/dispatcher/incidents/${incidentId}/assign`, { method: 'POST', body: JSON.stringify({ responderId }) }),
  reassign: (incidentId: string, responderId: string) =>
    request(`/dispatcher/incidents/${incidentId}/reassign`, { method: 'POST', body: JSON.stringify({ responderId }) }),
  cancel: (assignmentId: string) => request(`/dispatcher/assignments/${assignmentId}/cancel`, { method: 'POST' }),
  assignments: (history = false) =>
    request<{ assignments: OperationalAssignment[] }>(`/responder/assignments?history=${history}`),
  transition: (id: string, status: string, extra: Record<string, unknown> = {}) =>
    request<{ assignment: OperationalAssignment }>(`/responder/assignments/${id}/transition`, {
      method: 'POST', body: JSON.stringify({ status, ...extra }),
    }),
  availability: (status: string) => request('/responder/availability', { method: 'POST', body: JSON.stringify({ status }) }),
  notifications: (unreadOnly = false) =>
    request<{ notifications: OperationalNotification[] }>(`/notifications${unreadOnly ? '?unreadOnly=true' : ''}`),
  readNotification: (id: string) => request(`/notifications/${id}/read`, { method: 'POST' }),
  analytics: () => request<Record<string, unknown>>('/admin/analytics'),
  auditLogs: () => request<{ auditLogs: Array<Record<string, unknown>> }>('/admin/audit-logs'),
  settings: () => request<{ settings: Array<Record<string, unknown>> }>('/admin/ai-settings'),
  setSetting: (key: string, value: unknown) => request(`/admin/ai-settings/${encodeURIComponent(key)}`, { method: 'PUT', body: JSON.stringify({ value }) }),
}
