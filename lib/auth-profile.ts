'use client'

import { doc, getDoc } from 'firebase/firestore'
import { db } from '@/lib/firebase'

export interface UserProfile {
  active: boolean
  areaId: 'talomo' | 'bago' | 'toril' | null
  createdAt: string
  displayName: string
  email: string
  role: 'user' | 'responder' | 'admin'
  uid: string
  updatedAt: string
}

export function isDashboardRole(role: UserProfile['role'] | undefined) {
  return role === 'admin' || role === 'responder'
}

export async function getUserProfileByUid(uid: string): Promise<UserProfile | null> {
  if (!db) {
    throw new Error(
      'Firestore is not configured. Set NEXT_PUBLIC_FIREBASE_* variables in .env.local and restart the frontend.'
    )
  }

  const snapshot = await getDoc(doc(db, 'users', uid))

  if (!snapshot.exists()) {
    return null
  }

  const data = snapshot.data()
  const role =
    data.role === 'admin' || data.role === 'responder' || data.role === 'user'
      ? data.role
      : 'user'

  return {
    active: Boolean(data.active),
    areaId: (data.areaId ?? null) as UserProfile['areaId'],
    createdAt: String(data.createdAt ?? ''),
    displayName: String(data.displayName ?? ''),
    email: String(data.email ?? ''),
    role,
    uid: String(data.uid ?? snapshot.id),
    updatedAt: String(data.updatedAt ?? ''),
  }
}
