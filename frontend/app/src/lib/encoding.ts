/**
 * Encode a Uint8Array to a base-64 string.
 *
 * `btoa(String.fromCharCode(...bytes))` spreads the entire array onto the
 * call stack, which overflows for files larger than ~64 KiB.  This helper
 * processes the bytes in 8 KiB chunks so the stack depth stays bounded.
 */
export function bytesToBase64(bytes: Uint8Array): string {
  let binary = ''
  const chunkSize = 8192
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize))
  }
  return btoa(binary)
}
