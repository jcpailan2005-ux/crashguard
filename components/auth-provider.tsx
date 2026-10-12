'use client'

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { useTheme } from 'next-themes'
import { AuthUser, CrashGuardApiError, getCurrentSQLiteUser, logoutFromSQLite } from '@/lib/api-client'
import { UserProfile } from '@/lib/auth-profile'
import { phase3, type PersonalPreferences } from '@/lib/phase3-api'
import { isPersonalTheme } from '@/lib/personal-settings'

interface AuthContextValue {
  authError: string | null
  sessionUser: AuthUser | null
  loading: boolean
  profile: UserProfile | null
  personalPreferences: PersonalPreferences | null
  refreshUser: () => Promise<void>
  setSessionUser: (user: AuthUser) => void
  setPersonalPreferences: (preferences: PersonalPreferences) => void
  signOutUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

function toProfile(user: AuthUser): UserProfile {
  return {
    active: user.active,
    areaId: user.areaId,
    createdAt: user.createdAt,
    displayName: user.displayName,
    email: user.email,
    role: user.role,
    permissions: user.permissions ?? [],
    mustChangePassword: user.mustChangePassword,
    uid: user.uid,
    updatedAt: user.updatedAt,
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { setTheme } = useTheme()
  const [authError, setAuthError] = useState<string | null>(null)
  const [sessionUser, setSessionAccount] = useState<AuthUser | null>(null)
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [personalPreferences, setPersonalPreferences] = useState<PersonalPreferences | null>(null)
  const [loading, setLoading] = useState(true)
  const sessionEpochRef = useRef(0)

  const setSessionUser = useCallback((user: AuthUser) => {
    sessionEpochRef.current += 1
    setAuthError(null)
    setSessionAccount(user)
    setProfile(toProfile(user))
    setLoading(false)
  }, [])

  const refreshUser = useCallback(async () => {
    const requestEpoch = ++sessionEpochRef.current
    setLoading(true)
    try {
      const user = await getCurrentSQLiteUser()
      if (requestEpoch !== sessionEpochRef.current) return
      setAuthError(null)
      setSessionAccount(user)
      setProfile(toProfile(user))
    } catch (error) {
      if (requestEpoch !== sessionEpochRef.current) return
      if (!(error instanceof CrashGuardApiError && error.status === 401)) {
        console.error('Failed to restore SQLite session:', error)
      }
      setSessionAccount(null)
      setProfile(null)
      setAuthError(null)
    } finally {
      if (requestEpoch === sessionEpochRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refreshUser()
  }, [refreshUser])

  useEffect(() => {
    if (!profile?.uid || profile.mustChangePassword) return
    let cancelled = false
    void phase3.ownPreferences()
      .then(({ preferences }) => {
        if (cancelled) return
        setPersonalPreferences(preferences)
        if (isPersonalTheme(preferences.theme)) setTheme(preferences.theme)
      })
      .catch(() => {
        // Local next-themes persistence remains the safe fallback while the backend is unavailable.
      })
    return () => { cancelled = true }
  }, [profile?.mustChangePassword, profile?.uid, setTheme])

  const signOutUser = useCallback(async () => {
    sessionEpochRef.current += 1
    try {
      await logoutFromSQLite()
    } catch {
      // Local cleanup is still required if the backend is unavailable.
    }
    setAuthError(null)
    setSessionAccount(null)
    setProfile(null)
    setPersonalPreferences(null)
    setLoading(false)
  }, [])

  const value = useMemo(
    () => ({
      authError,
      sessionUser,
      loading,
      profile,
      personalPreferences,
      refreshUser,
      setSessionUser,
      setPersonalPreferences,
      signOutUser,
    }),
    [authError, sessionUser, loading, personalPreferences, profile, refreshUser, setSessionUser, signOutUser]
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
