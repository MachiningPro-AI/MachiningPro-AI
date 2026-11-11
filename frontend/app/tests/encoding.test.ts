// Regression tests for bytesToBase64 — guards against the
// "Maximum call stack size exceeded" RangeError that btoa(String.fromCharCode(...bytes))
// produces on large files (spread of >~64 KiB Uint8Array blows the call stack).

import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import { bytesToBase64 } from '../src/lib/encoding.ts'

describe('bytesToBase64', () => {
  test('encodes empty array', () => {
    assert.equal(bytesToBase64(new Uint8Array(0)), '')
  })

  test('encodes small known payload', () => {
    // "Hello" in ASCII bytes
    const bytes = new Uint8Array([72, 101, 108, 108, 111])
    assert.equal(bytesToBase64(bytes), btoa('Hello'))
  })

  test('does not overflow call stack for large DXF-sized payload', () => {
    // 200 000 bytes is well above the typical call-stack limit for spread args.
    // The old btoa(String.fromCharCode(...bytes)) would throw RangeError here.
    const bytes = new Uint8Array(200_000)
    bytes.fill(0x41) // 'A'
    let result: string | undefined
    assert.doesNotThrow(() => { result = bytesToBase64(bytes) })
    assert.ok(typeof result === 'string' && result.length > 0)
  })

  test('round-trips correctly across chunk boundaries', () => {
    // 10 000 bytes with all 256 values cycling — verifies no off-by-one at
    // the 8192-byte chunk boundary.
    const original = new Uint8Array(10_000)
    for (let i = 0; i < original.length; i++) original[i] = i % 256
    const encoded = bytesToBase64(original)
    const decoded = Uint8Array.from(atob(encoded), c => c.charCodeAt(0))
    assert.deepEqual(decoded, original)
  })
})
