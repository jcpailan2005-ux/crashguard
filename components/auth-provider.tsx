'use client'

import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { AuthUser, getCurrentSQLiteUser } from '@/lib/api-client'
import { clearStoredAuthToken, getStoredAuthToken } from '@/lib/session-auth'
import { UserProfile } from '@/lib/auth-profile'

interface AuthContextValue {
  authError: string | null
  firebaseUser: AuthUser | null
  loading: boolean
  profile: UserProfile | null
  refreshUser: () => Promise<void>
  setSessionUser: (user: AuthUser) => void
  signOutUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

function toProfile(user: AuthUser): UserProfile {
  return {
    active: user.active,
    areaId:
      user.areaId === 'talomo' || user.areaId === 'bago' || user.areaId === 'toril'
        ? user.areaId
        : null,
    createdAt: user.createdAt,
    displayName: user.displayName,
    email: user.email,
    role: user.role,
    uid: user.uid,
    updatedAt: user.updatedAt,
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [authError, setAuthError] = useState<string | null>(null)
  const [firebaseUser, setFirebaseUser] = useState<AuthUser | null>(null)
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [loading, setLoading] = useState(true)

  const setSessionUser = (user: AuthUser) => {
    setAuthError(null)
    setFirebaseUser(user)
    setProfile(toProfile(user))
  }

  const refreshUser = async () => {
    const token = getStoredAuthToken()
    if (!token) {
      setAuthError(null)
      setFirebaseUser(null)
      setProfile(null)
      setLoading(false)
      return
    }

    try {
      const user = await getCurrentSQLiteUser()
      setSessionUser(user)
    } catch (error) {
      console.error('Failed to restore SQLite session:', error)
      clearStoredAuthToken()
      setFirebaseUser(null)
      setProfile(null)
      setAuthError('Your saved session expired. Please sign in again.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refreshUser()
  }, [])

  const signOutUser = async () => {
    clearStoredAuthToken()
    setAuthError(null)
    setFirebaseUser(null)
    setProfile(null)
  }

  const value = useMemo(
    () => ({
      authError,
      firebaseUser,
      loading,
      profile,
      refreshUser,
      setSessionUser,
      signOutUser,
    }),
    [authError, firebaseUser, loading, profile]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
