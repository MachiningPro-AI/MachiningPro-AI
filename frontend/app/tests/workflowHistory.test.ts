/**
 * Tests for workflowHistory service — Level 20 MUST 17.
 *
 * Tests: history types, export format registry, NC safety labels,
 * URL builder, status helpers, reload recovery helpers.
 *
 * Run with: npm test
 */

import assert from 'node:assert/strict'
import { describe, test } from 'node:test'

import {
  EXPORT_FORMATS,
  NC_MANIFEST_SAFETY_LABELS,
  buildExportUrl,
  formatHistoryDate,
  getExportMeta,
  isNcSafetyFormat,
  statusBadgeClass,
} from '../src/services/workflowHistory.ts'

// ---------------------------------------------------------------------------
// Export format registry
// ---------------------------------------------------------------------------

describe('EXPORT_FORMATS', () => {
  test('contains 5 formats', () => {
    assert.equal(EXPORT_FORMATS.length, 5)
  })

  test('all required format IDs present', () => {
    const ids = EXPORT_FORMATS.map(f => f.id)
    assert.ok(ids.includes('plan.json'))
    assert.ok(ids.includes('plan.html'))
    assert.ok(ids.includes('stages.csv'))
    assert.ok(ids.includes('dfm.json'))
    assert.ok(ids.includes('nc-manifest.json'))
  })

  test('every format has a non-empty label', () => {
    for (const f of EXPORT_FORMATS) {
      assert.ok(f.label.length > 0, `Empty label for ${f.id}`)
    }
  })

  test('every format has a valid mimeType', () => {
    for (const f of EXPORT_FORMATS) {
      assert.ok(f.mimeType.includes('/'), `Invalid mimeType for ${f.id}`)
    }
  })

  test('nc-manifest.json has ncSafetyWarning=true', () => {
    const nc = EXPORT_FORMATS.find(f => f.id === 'nc-manifest.json')
    assert.ok(nc)
    assert.equal(nc!.ncSafetyWarning, true)
  })

  test('non-NC formats have ncSafetyWarning=false', () => {
    for (const f of EXPORT_FORMATS.filter(f => f.id !== 'nc-manifest.json')) {
      assert.equal(f.ncSafetyWarning, false, `${f.id} should not have NC warning`)
    }
  })
})

// ---------------------------------------------------------------------------
// NC safety labels
// ---------------------------------------------------------------------------

describe('NC_MANIFEST_SAFETY_LABELS', () => {
  test('OFFLINE_CANDIDATE is true', () => {
    assert.equal(NC_MANIFEST_SAFETY_LABELS.OFFLINE_CANDIDATE, true)
  })

  test('NOT_MACHINE_APPROVED is true', () => {
    assert.equal(NC_MANIFEST_SAFETY_LABELS.NOT_MACHINE_APPROVED, true)
  })

  test('NOT_DISPATCHED is true', () => {
    assert.equal(NC_MANIFEST_SAFETY_LABELS.NOT_DISPATCHED, true)
  })

  test('NO_CNC_TRANSFER is true', () => {
    assert.equal(NC_MANIFEST_SAFETY_LABELS.NO_CNC_TRANSFER, true)
  })

  test('no SEND_TO_CNC field', () => {
    assert.ok(!('SEND_TO_CNC' in NC_MANIFEST_SAFETY_LABELS))
  })

  test('no DISPATCH_APPROVED field', () => {
    assert.ok(!('DISPATCH_APPROVED' in NC_MANIFEST_SAFETY_LABELS))
  })
})

// ---------------------------------------------------------------------------
// isNcSafetyFormat
// ---------------------------------------------------------------------------

describe('isNcSafetyFormat', () => {
  test('true for nc-manifest.json', () => {
    assert.equal(isNcSafetyFormat('nc-manifest.json'), true)
  })

  test('false for plan.json', () => {
    assert.equal(isNcSafetyFormat('plan.json'), false)
  })

  test('false for plan.html', () => {
    assert.equal(isNcSafetyFormat('plan.html'), false)
  })

  test('false for stages.csv', () => {
    assert.equal(isNcSafetyFormat('stages.csv'), false)
  })

  test('false for dfm.json', () => {
    assert.equal(isNcSafetyFormat('dfm.json'), false)
  })
})

// ---------------------------------------------------------------------------
// getExportMeta
// ---------------------------------------------------------------------------

describe('getExportMeta', () => {
  test('returns meta for plan.json', () => {
    const m = getExportMeta('plan.json')
    assert.ok(m)
    assert.equal(m!.id, 'plan.json')
  })

  test('returns meta for nc-manifest.json', () => {
    const m = getExportMeta('nc-manifest.json')
    assert.ok(m)
    assert.equal(m!.ncSafetyWarning, true)
  })
})

// ---------------------------------------------------------------------------
// buildExportUrl
// ---------------------------------------------------------------------------

describe('buildExportUrl', () => {
  test('builds correct URL for plan.json', () => {
    const url = buildExportUrl('WF_abc123', 'plan.json')
    assert.equal(url, '/api/workflow/WF_abc123/export/plan.json')
  })

  test('builds correct URL for nc-manifest.json', () => {
    const url = buildExportUrl('WF_xyz', 'nc-manifest.json')
    assert.equal(url, '/api/workflow/WF_xyz/export/nc-manifest.json')
  })

  test('sanitizes path traversal in workflow_id', () => {
    const url = buildExportUrl('../../../etc/passwd', 'plan.json')
    assert.ok(!url.includes('..'))
    assert.ok(!url.includes('/etc/passwd'))
  })

  test('sanitizes special chars in workflow_id', () => {
    const url = buildExportUrl('WF_<script>', 'stages.csv')
    assert.ok(!url.includes('<'))
    assert.ok(!url.includes('>'))
  })

  test('URL starts with /api/workflow/', () => {
    const url = buildExportUrl('WF_abc', 'dfm.json')
    assert.ok(url.startsWith('/api/workflow/'))
  })

  test('no double slashes', () => {
    const url = buildExportUrl('WF_abc', 'plan.json')
    assert.ok(!url.includes('//'))
  })
})

// ---------------------------------------------------------------------------
// statusBadgeClass
// ---------------------------------------------------------------------------

describe('statusBadgeClass', () => {
  test('COMPLETED → green', () => {
    assert.ok(statusBadgeClass('COMPLETED').includes('green'))
  })

  test('PARTIAL → yellow', () => {
    assert.ok(statusBadgeClass('PARTIAL').includes('yellow'))
  })

  test('FAILED → red', () => {
    assert.ok(statusBadgeClass('FAILED').includes('red'))
  })

  test('INTERRUPTED → orange', () => {
    assert.ok(statusBadgeClass('INTERRUPTED').includes('orange'))
  })

  test('RUNNING → blue', () => {
    assert.ok(statusBadgeClass('RUNNING').includes('blue'))
  })

  test('unknown status → gray fallback', () => {
    assert.ok(statusBadgeClass('UNKNOWN_XYZ').includes('gray'))
  })
})

// ---------------------------------------------------------------------------
// formatHistoryDate
// ---------------------------------------------------------------------------

describe('formatHistoryDate', () => {
  test('returns non-empty string for valid ISO date', () => {
    const result = formatHistoryDate('2026-11-10T12:00:00')
    assert.ok(result.length > 0)
  })

  test('does not throw for invalid input', () => {
    assert.doesNotThrow(() => formatHistoryDate('not-a-date'))
  })

  test('returns input as fallback for invalid date', () => {
    const result = formatHistoryDate('not-a-date')
    assert.equal(result, 'not-a-date')
  })
})

// ---------------------------------------------------------------------------
// Reload recovery constants (compile-time checks only — no DOM in node:test)
// ---------------------------------------------------------------------------

describe('reload recovery exports', () => {
  test('saveCurrentWorkflowId is a function', async () => {
    const mod = await import('../src/services/workflowHistory.ts')
    assert.equal(typeof mod.saveCurrentWorkflowId, 'function')
  })

  test('restoreCurrentWorkflowId is a function', async () => {
    const mod = await import('../src/services/workflowHistory.ts')
    assert.equal(typeof mod.restoreCurrentWorkflowId, 'function')
  })

  test('clearCurrentWorkflowId is a function', async () => {
    const mod = await import('../src/services/workflowHistory.ts')
    assert.equal(typeof mod.clearCurrentWorkflowId, 'function')
  })
})
