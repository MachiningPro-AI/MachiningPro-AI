// MUST 2 regression: CadFeaturesPage must use bytesToBase64, not btoa spread.
//
// btoa(String.fromCharCode(...new Uint8Array(ab))) spreads the entire array
// onto the call stack, overflowing for files > ~64 KiB.
//
// STACK_OVERFLOW_ROOT_CAUSE=btoa_spread_on_full_array
// SAFE_BASE64_HELPER_USED=bytesToBase64_from_encoding.ts
// LARGE_FILE_BASE64_TEST=YES

import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { bytesToBase64 } from '../src/lib/encoding.ts'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const SRC = path.join(__dirname, '..', 'src')

describe('CadFeaturesPage base64 regression', () => {
  test('CadFeaturesPage does NOT use the unsafe btoa spread pattern', () => {
    const src = readFileSync(
      path.join(SRC, 'pages', 'CadFeaturesPage.tsx'), 'utf8',
    )
    assert.ok(
      !src.includes('String.fromCharCode(...new Uint8Array'),
      'Unsafe btoa spread still present in CadFeaturesPage.tsx — will overflow for large files',
    )
  })

  test('CadFeaturesPage uses bytesToBase64', () => {
    const src = readFileSync(
      path.join(SRC, 'pages', 'CadFeaturesPage.tsx'), 'utf8',
    )
    assert.ok(
      src.includes('bytesToBase64'),
      'CadFeaturesPage.tsx must use bytesToBase64 from encoding.ts',
    )
  })

  test('bytesToBase64 handles 200 KB without call-stack overflow (DXF-sized file)', () => {
    const bytes = new Uint8Array(200_000)
    bytes.fill(0x41)  // 'A'
    let result: string | undefined
    assert.doesNotThrow(() => { result = bytesToBase64(bytes) })
    assert.ok(typeof result === 'string' && result.length > 0)
  })

  test('bytesToBase64 produces correct output for known payload', () => {
    const bytes = new Uint8Array([72, 101, 108, 108, 111])  // "Hello"
    assert.equal(bytesToBase64(bytes), btoa('Hello'))
  })

  test('bytesToBase64 handles empty array', () => {
    assert.equal(bytesToBase64(new Uint8Array(0)), '')
  })

  test('DOCUMENTATION: btoa spread overflows for large arrays', () => {
    // This test documents the bug pattern — large array spreads blow the stack.
    // We do NOT demonstrate the overflow (it would crash the test runner).
    // Instead, we verify that the new code path avoids the spread.
    const src = readFileSync(
      path.join(SRC, 'pages', 'CadFeaturesPage.tsx'), 'utf8',
    )
    assert.ok(src.includes('bytesToBase64'), 'The chunked implementation must be in use')
    assert.ok(!src.includes('fromCharCode(...new'), 'The spread must not be in use')
  })
})
