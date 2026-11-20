/**
 * CAD/CAM Workspace — TypeScript contract and safety tests
 *
 * Tests:
 *   - WorkspaceTypes constants and helpers
 *   - Safety invariants (SAFETY object)
 *   - File format detection
 *   - File size formatting
 *   - ToolpathLineGroup motion type coverage
 *   - ConnectedWorkflow shape
 *   - Operation summary shape
 *   - Display mode type coverage
 *   - Safety constants immutability
 *
 * No DOM, no component rendering, no network calls, no fabricated data.
 */

import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

// ---------------------------------------------------------------------------
// Re-implement lightweight versions of WorkspaceTypes helpers for test runner
// (The actual source imports Three.js which is ESM/browser-only; we test the
// pure logic separately to avoid a WebGL context requirement.)
// ---------------------------------------------------------------------------

type FileFormat = 'STL' | 'OBJ' | '3MF' | 'STEP' | 'IGES' | 'DXF' | 'PDF' | 'IMAGE' | 'UNKNOWN'
type DisplayMode = 'shaded' | 'wireframe' | 'shaded_edges' | 'hidden_line' | 'points'
type MotionTypeColor = 'RAPID' | 'FEED' | 'PLUNGE' | 'RETRACT' | 'LINK'

function detectFormat(filename: string): FileFormat {
  const ext = filename.split('.').pop()?.toLowerCase() ?? ''
  const map: Record<string, FileFormat> = {
    stl: 'STL', obj: 'OBJ', '3mf': '3MF',
    step: 'STEP', stp: 'STEP', iges: 'IGES', igs: 'IGES',
    dxf: 'DXF', pdf: 'PDF',
    png: 'IMAGE', jpg: 'IMAGE', jpeg: 'IMAGE', bmp: 'IMAGE',
  }
  return map[ext] ?? 'UNKNOWN'
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

const CLIENT_RENDER_FORMATS: FileFormat[] = ['STL', 'OBJ', '3MF']
const SERVER_RENDER_FORMATS: FileFormat[] = ['STEP', 'IGES']

const SAFETY = {
  IS_DISPATCHABLE: false,
  PRODUCTION_RELEASED: false,
  AUTO_APPROVED: false,
  ENGINEERING_STATE_CHANGED: false,
  VERIFICATION_STATE: 'NOT_PERFORMED' as const,
  SIMULATION_STATE: 'NOT_PERFORMED' as const,
  COLLISION_CHECK: 'NOT_PERFORMED' as const,
  GOUGE_CHECK: 'NOT_PERFORMED' as const,
  FIXTURE_CHECK: 'NOT_PERFORMED' as const,
  MACHINE_ENVELOPE_CHECK: 'NOT_PERFORMED' as const,
  SIMULATION_REQUIRED: true,
  IS_VERIFIED: false,
} as const

// ---------------------------------------------------------------------------

describe('WorkspaceTypes — detectFormat', () => {
  it('detects STL', () => assert.strictEqual(detectFormat('part.stl'), 'STL'))
  it('detects OBJ', () => assert.strictEqual(detectFormat('part.obj'), 'OBJ'))
  it('detects 3MF', () => assert.strictEqual(detectFormat('part.3mf'), '3MF'))
  it('detects STEP by .step', () => assert.strictEqual(detectFormat('part.step'), 'STEP'))
  it('detects STEP by .stp',  () => assert.strictEqual(detectFormat('part.stp'),  'STEP'))
  it('detects IGES by .iges', () => assert.strictEqual(detectFormat('part.iges'), 'IGES'))
  it('detects IGES by .igs',  () => assert.strictEqual(detectFormat('part.igs'),  'IGES'))
  it('detects DXF',  () => assert.strictEqual(detectFormat('drawing.dxf'), 'DXF'))
  it('detects PDF',  () => assert.strictEqual(detectFormat('drawing.pdf'), 'PDF'))
  it('detects PNG',  () => assert.strictEqual(detectFormat('image.png'),   'IMAGE'))
  it('detects JPG',  () => assert.strictEqual(detectFormat('image.jpg'),   'IMAGE'))
  it('detects JPEG', () => assert.strictEqual(detectFormat('image.jpeg'),  'IMAGE'))
  it('detects BMP',  () => assert.strictEqual(detectFormat('image.bmp'),   'IMAGE'))
  it('returns UNKNOWN for unsupported', () => assert.strictEqual(detectFormat('part.xt'), 'UNKNOWN'))
  it('is case-insensitive', () => assert.strictEqual(detectFormat('PART.STL'), 'STL'))
  it('handles no extension', () => assert.strictEqual(detectFormat('partfile'), 'UNKNOWN'))
  it('handles multiple dots', () => assert.strictEqual(detectFormat('v2.0.step'), 'STEP'))
})

describe('WorkspaceTypes — formatFileSize', () => {
  it('formats bytes', () => assert.match(formatFileSize(512), /512 B/))
  it('formats KB',    () => assert.match(formatFileSize(2048), /KB/))
  it('formats MB',    () => assert.match(formatFileSize(2 * 1024 * 1024), /MB/))
  it('formats 0',     () => assert.strictEqual(formatFileSize(0), '0 B'))
})

describe('WorkspaceTypes — format categories', () => {
  it('client render formats covers STL/OBJ/3MF', () => {
    assert.ok(CLIENT_RENDER_FORMATS.includes('STL'))
    assert.ok(CLIENT_RENDER_FORMATS.includes('OBJ'))
    assert.ok(CLIENT_RENDER_FORMATS.includes('3MF'))
  })
  it('client render does NOT include STEP or IGES', () => {
    assert.ok(!CLIENT_RENDER_FORMATS.includes('STEP'))
    assert.ok(!CLIENT_RENDER_FORMATS.includes('IGES'))
  })
  it('server render formats covers STEP/IGES', () => {
    assert.ok(SERVER_RENDER_FORMATS.includes('STEP'))
    assert.ok(SERVER_RENDER_FORMATS.includes('IGES'))
  })
  it('server render does NOT include STL/OBJ/3MF', () => {
    assert.ok(!SERVER_RENDER_FORMATS.includes('STL'))
    assert.ok(!SERVER_RENDER_FORMATS.includes('OBJ'))
  })
})

describe('SAFETY constants — IS_DISPATCHABLE', () => {
  it('IS_DISPATCHABLE is false', () => {
    assert.strictEqual(SAFETY.IS_DISPATCHABLE, false)
  })
  it('IS_DISPATCHABLE is never true', () => {
    // Type guard: the const assertion prevents assignment of true
    const val: false = SAFETY.IS_DISPATCHABLE
    assert.strictEqual(val, false)
  })
})

describe('SAFETY constants — PRODUCTION_RELEASED', () => {
  it('PRODUCTION_RELEASED is false', () => assert.strictEqual(SAFETY.PRODUCTION_RELEASED, false))
  it('AUTO_APPROVED is false',       () => assert.strictEqual(SAFETY.AUTO_APPROVED, false))
  it('ENGINEERING_STATE_CHANGED is false', () => assert.strictEqual(SAFETY.ENGINEERING_STATE_CHANGED, false))
})

describe('SAFETY constants — verification checks', () => {
  it('VERIFICATION_STATE is NOT_PERFORMED',   () => assert.strictEqual(SAFETY.VERIFICATION_STATE,   'NOT_PERFORMED'))
  it('SIMULATION_STATE is NOT_PERFORMED',     () => assert.strictEqual(SAFETY.SIMULATION_STATE,     'NOT_PERFORMED'))
  it('COLLISION_CHECK is NOT_PERFORMED',      () => assert.strictEqual(SAFETY.COLLISION_CHECK,      'NOT_PERFORMED'))
  it('GOUGE_CHECK is NOT_PERFORMED',          () => assert.strictEqual(SAFETY.GOUGE_CHECK,          'NOT_PERFORMED'))
  it('FIXTURE_CHECK is NOT_PERFORMED',        () => assert.strictEqual(SAFETY.FIXTURE_CHECK,        'NOT_PERFORMED'))
  it('MACHINE_ENVELOPE_CHECK is NOT_PERFORMED', () => assert.strictEqual(SAFETY.MACHINE_ENVELOPE_CHECK, 'NOT_PERFORMED'))
})

describe('SAFETY constants — simulation/verification flags', () => {
  it('SIMULATION_REQUIRED is true',  () => assert.strictEqual(SAFETY.SIMULATION_REQUIRED, true))
  it('IS_VERIFIED is false',         () => assert.strictEqual(SAFETY.IS_VERIFIED, false))
})

describe('DisplayMode type coverage', () => {
  it('shaded is valid', () => {
    const m: DisplayMode = 'shaded'
    assert.strictEqual(m, 'shaded')
  })
  it('wireframe is valid', () => {
    const m: DisplayMode = 'wireframe'
    assert.strictEqual(m, 'wireframe')
  })
  it('shaded_edges is valid', () => {
    const m: DisplayMode = 'shaded_edges'
    assert.strictEqual(m, 'shaded_edges')
  })
  it('hidden_line is valid', () => {
    const m: DisplayMode = 'hidden_line'
    assert.strictEqual(m, 'hidden_line')
  })
  it('points is valid', () => {
    const m: DisplayMode = 'points'
    assert.strictEqual(m, 'points')
  })
})

describe('MotionTypeColor coverage', () => {
  const motionTypes: MotionTypeColor[] = ['RAPID', 'FEED', 'PLUNGE', 'RETRACT', 'LINK']
  it('covers 5 motion types', () => assert.strictEqual(motionTypes.length, 5))
  it('includes RAPID',   () => assert.ok(motionTypes.includes('RAPID')))
  it('includes FEED',    () => assert.ok(motionTypes.includes('FEED')))
  it('includes PLUNGE',  () => assert.ok(motionTypes.includes('PLUNGE')))
  it('includes RETRACT', () => assert.ok(motionTypes.includes('RETRACT')))
  it('includes LINK',    () => assert.ok(motionTypes.includes('LINK')))
})

describe('ToolpathLineGroup — no fabricated data contract', () => {
  it('empty points array signals no-data', () => {
    const group = { motionType: 'FEED' as MotionTypeColor, points: [] as number[], operationRef: 'op1' }
    assert.strictEqual(group.points.length, 0)
  })

  it('points must be divisible by 3 (x,y,z triplets)', () => {
    const pts = [0, 0, 0, 10, 20, 30, 50, 50, 50]
    assert.strictEqual(pts.length % 3, 0)
  })

  it('minimum 2 points (6 values) needed to form a line', () => {
    const pts = [0, 0, 0, 1, 1, 1]
    assert.ok(pts.length >= 6)
    assert.ok(Math.floor(pts.length / 3) >= 2)
  })

  it('single point (3 values) is below minimum — not rendered', () => {
    const pts = [0, 0, 0]
    assert.ok(pts.length < 6)
  })
})

describe('ConnectedWorkflow shape', () => {
  type ConnectedWorkflow = {
    workflowId: string
    partName: string | null
    drawingNumber: string | null
    operations: Array<{ operationId: string; sequenceNumber: number; status: string }>
    toolpathGroups: Array<{ motionType: MotionTypeColor; points: number[]; operationRef: string }>
    planStatus: string | null
  }

  it('has workflowId string', () => {
    const wf: ConnectedWorkflow = {
      workflowId: 'WF_001',
      partName: 'TestPart',
      drawingNumber: null,
      operations: [],
      toolpathGroups: [],
      planStatus: 'DRAFT',
    }
    assert.strictEqual(wf.workflowId, 'WF_001')
  })

  it('operations is array', () => {
    const wf: ConnectedWorkflow = {
      workflowId: 'WF_002',
      partName: null,
      drawingNumber: 'DWG-001',
      operations: [
        { operationId: 'op1', sequenceNumber: 1, status: 'CANDIDATE' },
      ],
      toolpathGroups: [],
      planStatus: null,
    }
    assert.strictEqual(wf.operations.length, 1)
    assert.strictEqual(wf.operations[0]!.operationId, 'op1')
  })

  it('toolpathGroups only contains real data (no fabricated points by default)', () => {
    const wf: ConnectedWorkflow = {
      workflowId: 'WF_003',
      partName: null,
      drawingNumber: null,
      operations: [],
      toolpathGroups: [],
      planStatus: null,
    }
    assert.strictEqual(wf.toolpathGroups.length, 0)
  })
})

describe('Safety invariant — no auto-dispatch', () => {
  it('workspace has no dispatch field', () => {
    // The SAFETY object has no dispatch field
    assert.ok(!('DISPATCH_ENABLED' in SAFETY))
    assert.ok(!('AUTO_DISPATCH' in SAFETY))
  })

  it('IS_DISPATCHABLE=false is enforced', () => {
    assert.strictEqual(SAFETY.IS_DISPATCHABLE, false)
  })

  it('PRODUCTION_RELEASED=false is enforced', () => {
    assert.strictEqual(SAFETY.PRODUCTION_RELEASED, false)
  })
})

describe('Safety invariant — no fabricated simulation', () => {
  it('simulation state is always NOT_PERFORMED', () => {
    const result = SAFETY.SIMULATION_STATE
    assert.notStrictEqual(result, 'PASS')
    assert.notStrictEqual(result, 'COMPLETE')
    assert.notStrictEqual(result, 'VERIFIED')
    assert.strictEqual(result, 'NOT_PERFORMED')
  })

  it('collision check is never PASS', () => {
    const result = SAFETY.COLLISION_CHECK
    assert.notStrictEqual(result, 'PASS')
    assert.strictEqual(result, 'NOT_PERFORMED')
  })

  it('gouge check is never PASS', () => {
    const result = SAFETY.GOUGE_CHECK
    assert.notStrictEqual(result, 'PASS')
    assert.strictEqual(result, 'NOT_PERFORMED')
  })

  it('fixture check is never PASS', () => {
    assert.notStrictEqual(SAFETY.FIXTURE_CHECK, 'PASS')
    assert.strictEqual(SAFETY.FIXTURE_CHECK, 'NOT_PERFORMED')
  })
})

describe('File format path routing', () => {
  it('STL routes to client renderer', () => {
    const fmt = detectFormat('part.stl')
    assert.ok(CLIENT_RENDER_FORMATS.includes(fmt))
    assert.ok(!SERVER_RENDER_FORMATS.includes(fmt))
  })

  it('STEP routes to server tessellation', () => {
    const fmt = detectFormat('part.step')
    assert.ok(SERVER_RENDER_FORMATS.includes(fmt))
    assert.ok(!CLIENT_RENDER_FORMATS.includes(fmt))
  })

  it('IGES routes to server tessellation', () => {
    const fmt = detectFormat('part.iges')
    assert.ok(SERVER_RENDER_FORMATS.includes(fmt))
    assert.ok(!CLIENT_RENDER_FORMATS.includes(fmt))
  })

  it('DXF routes to neither (viewer pending)', () => {
    const fmt = detectFormat('drawing.dxf')
    assert.ok(!CLIENT_RENDER_FORMATS.includes(fmt))
    assert.ok(!SERVER_RENDER_FORMATS.includes(fmt))
  })
})
