import assert from 'node:assert/strict'
import test from 'node:test'

import { isPersonalTheme, PERSONAL_THEME_OPTIONS } from '../lib/personal-settings.ts'

test('personal settings expose light, dark, and system themes', () => {
  assert.deepEqual(PERSONAL_THEME_OPTIONS, ['light', 'dark', 'system'])
})

test('only supported account themes are accepted for synchronization', () => {
  for (const theme of PERSONAL_THEME_OPTIONS) assert.equal(isPersonalTheme(theme), true)
  assert.equal(isPersonalTheme('admin'), false)
  assert.equal(isPersonalTheme(undefined), false)
})
