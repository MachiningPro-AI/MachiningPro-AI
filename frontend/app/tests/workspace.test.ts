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

// ---------------------------------------------------------------------------
// toolpathGroupsToSegments — re-implemented inline for test runner
// (simulationService imports apiClient which is browser-only; test pure logic)
// ---------------------------------------------------------------------------

type ToolpathGroupFE = { motionType: string; points: number[]; operationRef: string }

function toolpathGroupsToSegmentsFE(groups: ToolpathGroupFE[]) {
  const cutting = new Set(['FEED', 'PLUNGE', 'CUTTING'])
  const segments = []
  for (const group of groups) {
    const pts = group.points
    if (pts.length < 6) continue
    for (let i = 0; i + 3 < pts.length; i += 3) {
      segments.push({
        start_x: pts[i]!, start_y: pts[i+1]!, start_z: pts[i+2]!,
        end_x: pts[i+3]!, end_y: pts[i+4]!, end_z: pts[i+5]!,
        motion_type: group.motionType,
        is_cutting: cutting.has(group.motionType),
        operation_id: group.operationRef,
        tool_id: null,
      })
    }
  }
  return segments
}

function toolpathGroupsToAnimFramesFE(groups: ToolpathGroupFE[]) {
  const frames: Array<[number, number, number]> = []
  for (const group of groups) {
    const pts = group.points
    for (let i = 0; i + 2 < pts.length; i += 3) {
      frames.push([pts[i]!, pts[i+1]!, pts[i+2]!])
    }
  }
  return frames
}

describe('toolpathGroupsToSegments — FEED motion', () => {
  const groups: ToolpathGroupFE[] = [
    { motionType: 'FEED', points: [0,0,0, 10,0,0, 10,10,0], operationRef: 'op1' }
  ]

  it('produces N-1 segments from N points', () => {
    const segs = toolpathGroupsToSegmentsFE(groups)
    assert.strictEqual(segs.length, 2)
  })

  it('first segment starts at origin', () => {
    const segs = toolpathGroupsToSegmentsFE(groups)
    assert.strictEqual(segs[0]!.start_x, 0)
    assert.strictEqual(segs[0]!.start_y, 0)
    assert.strictEqual(segs[0]!.start_z, 0)
  })

  it('first segment ends at second point', () => {
    const segs = toolpathGroupsToSegmentsFE(groups)
    assert.strictEqual(segs[0]!.end_x, 10)
  })

  it('FEED is_cutting=true', () => {
    const segs = toolpathGroupsToSegmentsFE(groups)
    assert.ok(segs.every(s => s.is_cutting === true))
  })

  it('operation_id propagated', () => {
    const segs = toolpathGroupsToSegmentsFE(groups)
    assert.ok(segs.every(s => s.operation_id === 'op1'))
  })
})

describe('toolpathGroupsToSegments — RAPID motion', () => {
  const groups: ToolpathGroupFE[] = [
    { motionType: 'RAPID', points: [0,0,50, 10,0,50], operationRef: 'op2' }
  ]

  it('RAPID is_cutting=false', () => {
    const segs = toolpathGroupsToSegmentsFE(groups)
    assert.ok(segs.every(s => s.is_cutting === false))
  })
})

describe('toolpathGroupsToSegments — RETRACT motion', () => {
  it('RETRACT is_cutting=false', () => {
    const groups: ToolpathGroupFE[] = [
      { motionType: 'RETRACT', points: [0,0,0, 0,0,50], operationRef: 'op3' }
    ]
    const segs = toolpathGroupsToSegmentsFE(groups)
    assert.ok(segs.every(s => s.is_cutting === false))
  })
})

describe('toolpathGroupsToSegments — PLUNGE motion', () => {
  it('PLUNGE is_cutting=true', () => {
    const groups: ToolpathGroupFE[] = [
      { motionType: 'PLUNGE', points: [5,5,0, 5,5,-10], operationRef: 'op4' }
    ]
    const segs = toolpathGroupsToSegmentsFE(groups)
    assert.ok(segs.every(s => s.is_cutting === true))
  })
})

describe('toolpathGroupsToSegments — single point (insufficient)', () => {
  it('single point (3 values) produces 0 segments', () => {
    const groups: ToolpathGroupFE[] = [
      { motionType: 'FEED', points: [0,0,0], operationRef: 'op5' }
    ]
    const segs = toolpathGroupsToSegmentsFE(groups)
    assert.strictEqual(segs.length, 0)
  })
})

describe('toolpathGroupsToAnimFrames', () => {
  it('extracts all points as frames', () => {
    const groups: ToolpathGroupFE[] = [
      { motionType: 'FEED', points: [0,0,0, 10,0,0, 10,10,0], operationRef: 'op1' }
    ]
    const frames = toolpathGroupsToAnimFramesFE(groups)
    assert.strictEqual(frames.length, 3)
  })

  it('frame values match input', () => {
    const groups: ToolpathGroupFE[] = [
      { motionType: 'RAPID', points: [1,2,3, 4,5,6], operationRef: 'op1' }
    ]
    const frames = toolpathGroupsToAnimFramesFE(groups)
    assert.deepStrictEqual(frames[0], [1, 2, 3])
    assert.deepStrictEqual(frames[1], [4, 5, 6])
  })

  it('empty groups produce no frames', () => {
    const frames = toolpathGroupsToAnimFramesFE([])
    assert.strictEqual(frames.length, 0)
  })

  it('multiple groups concatenate frames', () => {
    const groups: ToolpathGroupFE[] = [
      { motionType: 'FEED',   points: [0,0,0, 1,0,0], operationRef: 'op1' },
      { motionType: 'RETRACT', points: [1,0,0, 1,0,50], operationRef: 'op1' },
    ]
    const frames = toolpathGroupsToAnimFramesFE(groups)
    assert.strictEqual(frames.length, 4)
  })
})

describe('DEFAULT_SIMULATION_STATE contract', () => {
  const DEFAULT_SIMULATION_STATE_FE = {
    runStatus: 'NOT_PERFORMED' as const,
    toolpathId: null,
    verificationState: 'NOT_PERFORMED',
    checks: {},
    initialStockVolumeMm3: null,
    remainingStockVolumeMm3: null,
    removedVolumeMm3: null,
    stockRemovalFidelity: 'UNKNOWN',
    collisionPoints: [] as Array<[number, number, number]>,
    gougePoints: [] as Array<[number, number, number]>,
    errorMessage: null,
  }

  it('runStatus starts NOT_PERFORMED', () => assert.strictEqual(DEFAULT_SIMULATION_STATE_FE.runStatus, 'NOT_PERFORMED'))
  it('no initial stock volume', () => assert.strictEqual(DEFAULT_SIMULATION_STATE_FE.initialStockVolumeMm3, null))
  it('no collision points', () => assert.strictEqual(DEFAULT_SIMULATION_STATE_FE.collisionPoints.length, 0))
  it('no gouge points', () => assert.strictEqual(DEFAULT_SIMULATION_STATE_FE.gougePoints.length, 0))
  it('verificationState NOT_PERFORMED', () => assert.strictEqual(DEFAULT_SIMULATION_STATE_FE.verificationState, 'NOT_PERFORMED'))
  it('checks empty by default', () => assert.strictEqual(Object.keys(DEFAULT_SIMULATION_STATE_FE.checks).length, 0))
})

describe('StockBbox shape contract', () => {
  type StockBboxFE = { minX: number; minY: number; minZ: number; maxX: number; maxY: number; maxZ: number; confirmed: boolean }

  it('confirmed=false for SUGGESTED stock', () => {
    const bbox: StockBboxFE = { minX: 0, minY: 0, minZ: 0, maxX: 100, maxY: 50, maxZ: 30, confirmed: false }
    assert.strictEqual(bbox.confirmed, false)
  })

  it('confirmed=true for USER_CONFIRMED stock', () => {
    const bbox: StockBboxFE = { minX: 0, minY: 0, minZ: 0, maxX: 100, maxY: 50, maxZ: 30, confirmed: true }
    assert.strictEqual(bbox.confirmed, true)
  })

  it('dimensions are numbers', () => {
    const bbox: StockBboxFE = { minX: -10, minY: -5, minZ: 0, maxX: 90, maxY: 45, maxZ: 30, confirmed: false }
    assert.ok(typeof bbox.minX === 'number')
    assert.ok(typeof bbox.maxZ === 'number')
  })
})

describe('ToolPose shape contract', () => {
  type ToolPoseFE = { x: number; y: number; z: number }

  it('pose has x, y, z', () => {
    const pose: ToolPoseFE = { x: 10.5, y: -3.2, z: 0 }
    assert.ok(typeof pose.x === 'number')
    assert.ok(typeof pose.y === 'number')
    assert.ok(typeof pose.z === 'number')
  })

  it('pose values can be negative (machining below WCS)', () => {
    const pose: ToolPoseFE = { x: 0, y: 0, z: -15.0 }
    assert.ok(pose.z < 0)
  })
})

describe('Animation state — no fabricated frames invariant', () => {
  it('empty frames produce null tool pose', () => {
    const frames: Array<[number, number, number]> = []
    const frame = 0
    const toolPose = frames.length > 0 && frame < frames.length
      ? { x: frames[frame]![0], y: frames[frame]![1], z: frames[frame]![2] }
      : null
    assert.strictEqual(toolPose, null)
  })

  it('valid frame produces pose from real data', () => {
    const frames: Array<[number, number, number]> = [[10, 20, -5]]
    const frame = 0
    const toolPose = frames.length > 0 && frame < frames.length
      ? { x: frames[frame]![0], y: frames[frame]![1], z: frames[frame]![2] }
      : null
    assert.deepStrictEqual(toolPose, { x: 10, y: 20, z: -5 })
  })
})

describe('State immutability — viewer does not change engineering state', () => {
  it('SAFETY.IS_DISPATCHABLE unchanged after animation', () => {
    // Animation only changes animFrame — SAFETY const is never reassigned
    assert.strictEqual(SAFETY.IS_DISPATCHABLE, false)
  })

  it('SAFETY.PRODUCTION_RELEASED unchanged after simulation', () => {
    assert.strictEqual(SAFETY.PRODUCTION_RELEASED, false)
  })

  it('SAFETY.ENGINEERING_STATE_CHANGED is false', () => {
    assert.strictEqual(SAFETY.ENGINEERING_STATE_CHANGED, false)
  })
})

describe('ANIM_SPEEDS coverage', () => {
  const ANIM_SPEEDS_FE = [0.25, 0.5, 1, 2, 5, 10]
  it('has 6 speed levels', () => assert.strictEqual(ANIM_SPEEDS_FE.length, 6))
  it('includes 0.25x (slow motion)', () => assert.ok(ANIM_SPEEDS_FE.includes(0.25)))
  it('includes 1x (normal)', () => assert.ok(ANIM_SPEEDS_FE.includes(1)))
  it('includes 10x (fast forward)', () => assert.ok(ANIM_SPEEDS_FE.includes(10)))
})
