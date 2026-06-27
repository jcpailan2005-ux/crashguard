'use client'

import { getApp, getApps, initializeApp } from 'firebase/app'
import { connectAuthEmulator, getAuth, type Auth } from 'firebase/auth'
import {
  connectFirestoreEmulator,
  getFirestore,
  type Firestore,
} from 'firebase/firestore'

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
  measurementId: process.env.NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID,
}

function hasFirebaseConfig() {
  return Boolean(
    firebaseConfig.apiKey &&
      firebaseConfig.authDomain &&
      firebaseConfig.projectId &&
      firebaseConfig.appId
  )
}

const app = hasFirebaseConfig() ? (getApps().length > 0 ? getApp() : initializeApp(firebaseConfig)) : null

function parseHostPort(value: string | undefined, fallbackPort: number) {
  const normalized = (value ?? '').replace(/^https?:\/\//, '')
  const [host, rawPort] = normalized.split(':')
  return {
    host: host || 'localhost',
    port: rawPort ? Number(rawPort) : fallbackPort,
  }
}

export const auth: Auth | null = app ? getAuth(app) : null
export const db: Firestore | null = app ? getFirestore(app) : null

if (
  typeof window !== 'undefined' &&
  app &&
  auth &&
  db &&
  process.env.NEXT_PUBLIC_USE_FIREBASE_EMULATOR === 'true'
) {
  const emulatorState = window as typeof window & {
    __CRASHGUARD_FIREBASE_EMULATOR_CONNECTED__?: boolean
  }

  if (!emulatorState.__CRASHGUARD_FIREBASE_EMULATOR_CONNECTED__) {
    const authHost =
      process.env.NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST ?? 'localhost:9099'
    const firestore = parseHostPort(
      process.env.NEXT_PUBLIC_FIRESTORE_EMULATOR_HOST,
      8080
    )

    connectAuthEmulator(auth, `http://${authHost.replace(/^https?:\/\//, '')}`, {
      disableWarnings: true,
    })
    connectFirestoreEmulator(db, firestore.host, firestore.port)
    emulatorState.__CRASHGUARD_FIREBASE_EMULATOR_CONNECTED__ = true
  }
}
