// Regression guard: services using apiClient must NOT pass /api/ prefix.
// apiClient prepends API_BASE='/api', so api('/api/foo') produces '/api/api/foo'.
//
// These tests scan the actual source files for all api<T>( call sites and assert
// that none of the path strings start with '/api/', which would cause a double prefix.

import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const SRC = path.join(__dirname, '..', 'src', 'services')

function readService(name: string): string {
  return readFileSync(path.join(SRC, name), 'utf8')
}

// Extract all string/template literal arguments passed as the first arg to api<...>(
// or bare api( calls. Covers these patterns:
//   api<T>('/some/path', ...)
//   api<T>(`/some/${expr}/path`, ...)
function extractApiPaths(src: string): string[] {
  const paths: string[] = []
  // Match: api<anything>( followed by '/...' or backtick '/...'
  // Also match: api( directly
  const pattern = /api(?:<[^>]*>)?\(\s*[`']([^`']+)/g
  let m: RegExpExecArray | null
  while ((m = pattern.exec(src)) !== null) {
    paths.push(m[1])
  }
  return paths
}

describe('API double-prefix regression — drawingParser.ts', () => {
  const src = readService('drawingParser.ts')
  const paths = extractApiPaths(src)

  test('at least one api() call is present', () => {
    assert.ok(paths.length > 0, 'No api() calls found in drawingParser.ts')
  })

  test('no api() path argument starts with /api/', () => {
    const bad = paths.filter(p => p.startsWith('/api/'))
    assert.deepEqual(bad, [],
      `drawingParser.ts has api() calls with /api/ prefix (double prefix): ${bad.join(', ')}`)
  })

  test('drawing-parser analyze path is /drawing-parser/analyze', () => {
    assert.ok(
      paths.some(p => p === '/drawing-parser/analyze'),
      `Expected to find '/drawing-parser/analyze' among api() paths: ${paths.join(', ')}`,
    )
  })

  test('drawing-parser detections path starts with /drawing-parser/', () => {
    const detectionPaths = paths.filter(p => p.startsWith('/drawing-parser/'))
    assert.ok(
      detectionPaths.length >= 2,
      `Expected at least 2 paths starting with /drawing-parser/, got: ${detectionPaths.join(', ')}`,
    )
  })

  test('all 7 drawing-parser paths are present (after prefix removal)', () => {
    // After the fix, drawingParser.ts should have exactly these base paths:
    // /drawing-parser/analyze
    // /drawing-parser/${...}/detections
    // /drawing-parser/${...}/requirements
    // /drawing-parser/${...}/detections/${...}/confirm
    // /drawing-parser/${...}/detections/${...}/edit
    // /drawing-parser/${...}/detections/${...}/reject
    // /drawing-parser/${...}/detections/${...}/associate
    assert.equal(paths.length, 7,
      `Expected 7 api() calls in drawingParser.ts, found ${paths.length}: ${paths.join(', ')}`)
  })
})

describe('API double-prefix regression — gdt.ts', () => {
  const src = readService('gdt.ts')
  const paths = extractApiPaths(src)

  test('at least one api() call is present', () => {
    assert.ok(paths.length > 0, 'No api() calls found in gdt.ts')
  })

  test('no api() path argument starts with /api/', () => {
    const bad = paths.filter(p => p.startsWith('/api/'))
    assert.deepEqual(bad, [],
      `gdt.ts has api() calls with /api/ prefix (double prefix): ${bad.join(', ')}`)
  })

  test('gdt schema path is /gdt/schema', () => {
    assert.ok(
      paths.some(p => p === '/gdt/schema'),
      `Expected to find '/gdt/schema' among api() paths: ${paths.join(', ')}`,
    )
  })

  test('gdt validate path is /gdt/validate', () => {
    assert.ok(
      paths.some(p => p === '/gdt/validate'),
      `Expected '/gdt/validate' among api() paths: ${paths.join(', ')}`,
    )
  })

  test('gdt interpret path is /gdt/interpret', () => {
    assert.ok(
      paths.some(p => p === '/gdt/interpret'),
      `Expected '/gdt/interpret' among api() paths: ${paths.join(', ')}`,
    )
  })

  test('gdt bonus-tolerance path is /gdt/bonus-tolerance', () => {
    assert.ok(
      paths.some(p => p === '/gdt/bonus-tolerance'),
      `Expected '/gdt/bonus-tolerance' among api() paths: ${paths.join(', ')}`,
    )
  })

  test('gdt virtual-condition path is /gdt/virtual-condition', () => {
    assert.ok(
      paths.some(p => p === '/gdt/virtual-condition'),
      `Expected '/gdt/virtual-condition' among api() paths: ${paths.join(', ')}`,
    )
  })

  test('all 5 gdt paths are present', () => {
    assert.equal(paths.length, 5,
      `Expected 5 api() calls in gdt.ts, found ${paths.length}: ${paths.join(', ')}`)
  })
})

describe('API_BASE construction contract', () => {
  test('apiClient API_BASE is /api', () => {
    const src = readFileSync(path.join(SRC, 'apiClient.ts'), 'utf8')
    assert.ok(
      src.includes("const API_BASE = '/api'"),
      'apiClient.ts must define API_BASE as /api',
    )
  })

  test('apiClient fetch call uses template literal ${API_BASE}${path}', () => {
    const src = readFileSync(path.join(SRC, 'apiClient.ts'), 'utf8')
    assert.ok(
      src.includes('`${API_BASE}${path}`'),
      'apiClient.ts fetch must use `${API_BASE}${path}` — the final URL is /api + path',
    )
  })

  test('a /drawing-parser/analyze path produces /api/drawing-parser/analyze', () => {
    const API_BASE = '/api'
    const path = '/drawing-parser/analyze'
    assert.equal(`${API_BASE}${path}`, '/api/drawing-parser/analyze')
  })

  test('a /gdt/schema path produces /api/gdt/schema', () => {
    const API_BASE = '/api'
    const p = '/gdt/schema'
    assert.equal(`${API_BASE}${p}`, '/api/gdt/schema')
  })

  test('documenting the bug: /api/drawing-parser/analyze path produces double prefix', () => {
    const API_BASE = '/api'
    const buggyPath = '/api/drawing-parser/analyze'
    // This is what the BUG produced before the fix:
    assert.equal(`${API_BASE}${buggyPath}`, '/api/api/drawing-parser/analyze')
  })
})
