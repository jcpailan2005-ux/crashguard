import type { PersonalTheme } from '@/lib/phase3-api'

export const PERSONAL_THEME_OPTIONS = ['light', 'dark', 'system'] as const satisfies readonly PersonalTheme[]

export function isPersonalTheme(value: unknown): value is PersonalTheme {
  return PERSONAL_THEME_OPTIONS.includes(value as PersonalTheme)
}
