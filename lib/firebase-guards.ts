'use client'

import { db } from '@/lib/firebase'

export function getFirestoreOrNull() {
  return db
}

export function getFirebaseConfigError() {
  if (db) return null

  return 'Firebase is not configured. Set NEXT_PUBLIC_FIREBASE_* variables in .env.local and restart the frontend.'
}
