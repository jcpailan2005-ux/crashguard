import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'
import ts from 'typescript'

import { pixelCoordinatePercent } from '../lib/camera-analysis-view.ts'

test('small source-pixel coordinates are not mistaken for normalized percentages', () => {
  assert.equal(pixelCoordinatePercent(1, 1000), 0.1)
  assert.equal(pixelCoordinatePercent(0.5, 1000), 0.05)
  assert.equal(pixelCoordinatePercent(100, 1000), 10)
  assert.equal(pixelCoordinatePercent(0, 1000), 0)
  assert.equal(pixelCoordinatePercent(NaN, 1000), 0)
})

test('case evidence chooses an annotated still once and retains raw-frame fallback', () => {
  // Execute the actual mapper with only URL resolution stubbed; no network,
  // browser account or application module is imported by this geometry test.
  const source = readFileSync('lib/crash-case-mapper.ts', 'utf8')
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText
  const exports: Record<string, any> = {}
  vm.runInNewContext(compiled, { exports, require: (path: string) => {
    assert.equal(path, '@/lib/api-client')
    return { resolveBackendMediaUrl: (value: string | null) => value ?
      value.startsWith('http') ? value : `http://test/${value.replace(/^\/+/, '')}` : null }
  } })
  const input = { caseId: 'CASE-TEST', status: 'pending_review', confidence: .95,
    detectedAt: '2026-10-14T00:00:00Z', updatedAt: '2026-10-14T00:00:00Z',
    keyFramePath: '/raw.jpg', annotatedPath: '/annotated.jpg' }
  const annotated = exports.caseMedia(exports.localCaseToCrashCase(input))
  assert.equal(annotated.previewUrl, 'http://test/annotated.jpg')
  assert.equal(annotated.previewIsAnnotated, true)
  const raw = exports.caseMedia(exports.localCaseToCrashCase({ ...input, annotatedPath: null }))
  assert.equal(raw.previewUrl, 'http://test/raw.jpg')
  assert.equal(raw.previewIsAnnotated, false)
  assert.equal(exports.caseMedia(null).previewIsAnnotated, false)
})

test('raw evidence waits for its source image and baked annotation is not drawn twice', () => {
  for (const file of ['components/media-preview-dialog.tsx', 'components/incident-review-dialog.tsx', 'app/dashboard/map/page.tsx']) {
    const source = readFileSync(file, 'utf8')
    assert.match(source, /pixelCoordinatePercent/)
    assert.match(source, /loadedSource ===/)
    assert.doesNotMatch(source, /if \(value <= 1\)/)
  }
  const dialog = readFileSync('components/media-preview-dialog.tsx', 'utf8')
  assert.match(dialog, /!imageIsAnnotated && loadedSource === mediaUrl/)
  const review = readFileSync('components/incident-review-dialog.tsx', 'utf8')
  assert.match(review, /boxes=\{media\.previewIsAnnotated \? \[\] : caseItem\.boxes\}/)
})
