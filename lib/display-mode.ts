'use client'

import { useEffect, useMemo, useState } from 'react'
import { UserProfile } from '@/lib/auth-profile'

export type DisplayMode = 'simple' | 'advanced'

const DISPLAY_MODE_STORAGE_KEY = 'mycrushguard.displayMode'

export function canUseAdvancedMode(profile: UserProfile | null) {
  return profile?.role === 'admin'
}

export function useDisplayMode(profile: UserProfile | null) {
  const canUseAdvanced = canUseAdvancedMode(profile)
  const [mode, setModeState] = useState<DisplayMode>('simple')

  useEffect(() => {
    if (!canUseAdvanced) {
      setModeState('simple')
      return
    }

    const stored = window.localStorage.getItem(DISPLAY_MODE_STORAGE_KEY)
    setModeState(stored === 'advanced' ? 'advanced' : 'simple')
  }, [canUseAdvanced, profile?.uid])

  const setMode = (nextMode: DisplayMode) => {
    const allowedMode = canUseAdvanced ? nextMode : 'simple'
    setModeState(allowedMode)
    window.localStorage.setItem(DISPLAY_MODE_STORAGE_KEY, allowedMode)
  }

  return useMemo(
    () => ({
      canUseAdvanced,
      isAdvancedMode: canUseAdvanced && mode === 'advanced',
      mode: canUseAdvanced ? mode : 'simple',
      setMode,
    }),
    [canUseAdvanced, mode]
  )
}
