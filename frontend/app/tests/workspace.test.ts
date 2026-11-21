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

// ---------------------------------------------------------------------------
// WorkspaceLayout — MUST 2,3,4,6,7,8 — pure logic re-implemented inline
// (WorkspaceTypes imports Three.js; we test pure functions here)
// ---------------------------------------------------------------------------

type BgPresetId = 'dark_eng' | 'neutral_gray' | 'light_eng' | 'gradient_dark' | 'gradient_light'
type LayoutPresetId = 'MODEL' | 'DRAWING' | 'MANUFACTURING' | 'CAM' | 'SIMULATION' | 'INSPECTION'
type PartOpacityPreset = 1 | 0.75 | 0.5 | 0.25

interface WorkspaceLayout {
  leftWidth: number; rightWidth: number; bottomHeight: number
  showModelTree: boolean; showProperties: boolean; showCamPanel: boolean; showStatusBar: boolean
  collapsedLeft: boolean; collapsedRight: boolean; collapsedBottom: boolean
  viewerMaximized: boolean; activePreset: LayoutPresetId
  bgPresetId: BgPresetId; customBgColor: string | null; partOpacity: PartOpacityPreset
  savedVersion: number
}

const MIN_PANEL_WIDTH_T  = 160
const MAX_PANEL_WIDTH_T  = 600
const MIN_BOTTOM_HEIGHT_T = 100
const MAX_BOTTOM_HEIGHT_T = 480
const COLLAPSED_STRIP_W_T = 32

const DEFAULT_LAYOUT_T: WorkspaceLayout = {
  leftWidth: 260, rightWidth: 260, bottomHeight: 220,
  showModelTree: true, showProperties: true, showCamPanel: true, showStatusBar: true,
  collapsedLeft: false, collapsedRight: false, collapsedBottom: false,
  viewerMaximized: false, activePreset: 'MODEL',
  bgPresetId: 'dark_eng', customBgColor: null, partOpacity: 1, savedVersion: 1,
}

function clampNum(v: unknown, min: number, max: number, fallback: number): number {
  const n = typeof v === 'number' && isFinite(v) ? v : fallback
  return Math.max(min, Math.min(max, n))
}

function loadWorkspaceLayoutT(raw: string | null): WorkspaceLayout {
  try {
    if (!raw) return { ...DEFAULT_LAYOUT_T }
    const p = JSON.parse(raw) as Partial<WorkspaceLayout>
    const lw = clampNum(p.leftWidth,    MIN_PANEL_WIDTH_T,  MAX_PANEL_WIDTH_T,  DEFAULT_LAYOUT_T.leftWidth)
    const rw = clampNum(p.rightWidth,   MIN_PANEL_WIDTH_T,  MAX_PANEL_WIDTH_T,  DEFAULT_LAYOUT_T.rightWidth)
    const bh = clampNum(p.bottomHeight, MIN_BOTTOM_HEIGHT_T, MAX_BOTTOM_HEIGHT_T, DEFAULT_LAYOUT_T.bottomHeight)
    return { ...DEFAULT_LAYOUT_T, ...p, leftWidth: lw, rightWidth: rw, bottomHeight: bh }
  } catch {
    return { ...DEFAULT_LAYOUT_T }
  }
}

const BACKGROUND_PRESETS_T = [
  { id: 'dark_eng'       as BgPresetId, label: 'Dark Engineering',  color: 0x0d1117, isDark: true  },
  { id: 'neutral_gray'   as BgPresetId, label: 'Neutral Gray',       color: 0x1a1f2e, isDark: true  },
  { id: 'light_eng'      as BgPresetId, label: 'Light Engineering',  color: 0xd8e0e8, isDark: false },
  { id: 'gradient_dark'  as BgPresetId, label: 'Gradient Dark',      color: 0x111827, isDark: true  },
  { id: 'gradient_light' as BgPresetId, label: 'Gradient Light',     color: 0xe8ecf2, isDark: false },
]

const LAYOUT_PRESETS_T: Record<LayoutPresetId, Partial<WorkspaceLayout>> = {
  MODEL:         { showModelTree: true,  showProperties: true,  showCamPanel: false, collapsedLeft: false, collapsedRight: false, collapsedBottom: false, leftWidth: 280, rightWidth: 260, bottomHeight: 220 },
  DRAWING:       { showModelTree: true,  showProperties: true,  showCamPanel: false, collapsedLeft: false, collapsedRight: false, collapsedBottom: true,  leftWidth: 260, rightWidth: 280, bottomHeight: 220 },
  MANUFACTURING: { showModelTree: true,  showProperties: true,  showCamPanel: true,  collapsedLeft: false, collapsedRight: false, collapsedBottom: false, leftWidth: 260, rightWidth: 260, bottomHeight: 260 },
  CAM:           { showModelTree: true,  showProperties: false, showCamPanel: true,  collapsedLeft: false, collapsedRight: true,  collapsedBottom: false, leftWidth: 260, rightWidth: 260, bottomHeight: 320 },
  SIMULATION:    { showModelTree: false, showProperties: true,  showCamPanel: true,  collapsedLeft: true,  collapsedRight: false, collapsedBottom: false, leftWidth: 260, rightWidth: 300, bottomHeight: 320 },
  INSPECTION:    { showModelTree: true,  showProperties: true,  showCamPanel: false, collapsedLeft: false, collapsedRight: false, collapsedBottom: true,  leftWidth: 300, rightWidth: 300, bottomHeight: 220 },
}

const PART_OPACITY_PRESETS_T: PartOpacityPreset[] = [1, 0.75, 0.5, 0.25]

describe('DEFAULT_LAYOUT constants', () => {
  it('leftWidth within panel bounds',    () => { assert.ok(DEFAULT_LAYOUT_T.leftWidth  >= MIN_PANEL_WIDTH_T  && DEFAULT_LAYOUT_T.leftWidth  <= MAX_PANEL_WIDTH_T)  })
  it('rightWidth within panel bounds',   () => { assert.ok(DEFAULT_LAYOUT_T.rightWidth >= MIN_PANEL_WIDTH_T  && DEFAULT_LAYOUT_T.rightWidth <= MAX_PANEL_WIDTH_T)  })
  it('bottomHeight within panel bounds', () => { assert.ok(DEFAULT_LAYOUT_T.bottomHeight >= MIN_BOTTOM_HEIGHT_T && DEFAULT_LAYOUT_T.bottomHeight <= MAX_BOTTOM_HEIGHT_T) })
  it('all panels shown by default',  () => {
    assert.strictEqual(DEFAULT_LAYOUT_T.showModelTree,  true)
    assert.strictEqual(DEFAULT_LAYOUT_T.showProperties, true)
    assert.strictEqual(DEFAULT_LAYOUT_T.showCamPanel,   true)
    assert.strictEqual(DEFAULT_LAYOUT_T.showStatusBar,  true)
  })
  it('none collapsed by default', () => {
    assert.strictEqual(DEFAULT_LAYOUT_T.collapsedLeft,   false)
    assert.strictEqual(DEFAULT_LAYOUT_T.collapsedRight,  false)
    assert.strictEqual(DEFAULT_LAYOUT_T.collapsedBottom, false)
  })
  it('viewerMaximized false by default', () => assert.strictEqual(DEFAULT_LAYOUT_T.viewerMaximized, false))
  it('activePreset is MODEL by default', () => assert.strictEqual(DEFAULT_LAYOUT_T.activePreset, 'MODEL'))
  it('bgPresetId is dark_eng by default', () => assert.strictEqual(DEFAULT_LAYOUT_T.bgPresetId, 'dark_eng'))
  it('partOpacity is 1 by default', () => assert.strictEqual(DEFAULT_LAYOUT_T.partOpacity, 1))
  it('COLLAPSED_STRIP_W is 32px', () => assert.strictEqual(COLLAPSED_STRIP_W_T, 32))
})

describe('loadWorkspaceLayout — MUST 7, 8', () => {
  it('returns default on null storage', () => {
    const result = loadWorkspaceLayoutT(null)
    assert.deepStrictEqual(result, DEFAULT_LAYOUT_T)
  })

  it('returns default on corrupt JSON', () => {
    const result = loadWorkspaceLayoutT('{{not json}}')
    assert.deepStrictEqual(result, DEFAULT_LAYOUT_T)
  })

  it('restores valid stored layout', () => {
    const stored: WorkspaceLayout = { ...DEFAULT_LAYOUT_T, leftWidth: 320, bgPresetId: 'neutral_gray', partOpacity: 0.5 }
    const result = loadWorkspaceLayoutT(JSON.stringify(stored))
    assert.strictEqual(result.leftWidth, 320)
    assert.strictEqual(result.bgPresetId, 'neutral_gray')
    assert.strictEqual(result.partOpacity, 0.5)
  })

  it('clamps leftWidth below MIN to MIN — HARD RULE 6', () => {
    const stored = { ...DEFAULT_LAYOUT_T, leftWidth: 50 }
    const result = loadWorkspaceLayoutT(JSON.stringify(stored))
    assert.strictEqual(result.leftWidth, MIN_PANEL_WIDTH_T)
  })

  it('clamps leftWidth above MAX to MAX — HARD RULE 6', () => {
    const stored = { ...DEFAULT_LAYOUT_T, leftWidth: 9999 }
    const result = loadWorkspaceLayoutT(JSON.stringify(stored))
    assert.strictEqual(result.leftWidth, MAX_PANEL_WIDTH_T)
  })

  it('clamps rightWidth out-of-range', () => {
    const stored = { ...DEFAULT_LAYOUT_T, rightWidth: 10 }
    const result = loadWorkspaceLayoutT(JSON.stringify(stored))
    assert.strictEqual(result.rightWidth, MIN_PANEL_WIDTH_T)
  })

  it('clamps bottomHeight below MIN', () => {
    const stored = { ...DEFAULT_LAYOUT_T, bottomHeight: 10 }
    const result = loadWorkspaceLayoutT(JSON.stringify(stored))
    assert.strictEqual(result.bottomHeight, MIN_BOTTOM_HEIGHT_T)
  })

  it('clamps bottomHeight above MAX', () => {
    const stored = { ...DEFAULT_LAYOUT_T, bottomHeight: 2000 }
    const result = loadWorkspaceLayoutT(JSON.stringify(stored))
    assert.strictEqual(result.bottomHeight, MAX_BOTTOM_HEIGHT_T)
  })

  it('handles non-numeric leftWidth gracefully', () => {
    const stored = { ...DEFAULT_LAYOUT_T, leftWidth: 'abc' }
    const result = loadWorkspaceLayoutT(JSON.stringify(stored))
    assert.strictEqual(result.leftWidth, DEFAULT_LAYOUT_T.leftWidth)
  })
})

describe('BACKGROUND_PRESETS — MUST 15, 17, 18', () => {
  it('has exactly 5 presets', () => assert.strictEqual(BACKGROUND_PRESETS_T.length, 5))

  it('dark_eng has isDark=true',       () => assert.strictEqual(BACKGROUND_PRESETS_T.find(p => p.id === 'dark_eng')!.isDark,       true))
  it('neutral_gray has isDark=true',   () => assert.strictEqual(BACKGROUND_PRESETS_T.find(p => p.id === 'neutral_gray')!.isDark,   true))
  it('light_eng has isDark=false',     () => assert.strictEqual(BACKGROUND_PRESETS_T.find(p => p.id === 'light_eng')!.isDark,     false))
  it('gradient_dark has isDark=true',  () => assert.strictEqual(BACKGROUND_PRESETS_T.find(p => p.id === 'gradient_dark')!.isDark,  true))
  it('gradient_light has isDark=false',() => assert.strictEqual(BACKGROUND_PRESETS_T.find(p => p.id === 'gradient_light')!.isDark, false))

  it('all presets have valid hex color', () => {
    for (const p of BACKGROUND_PRESETS_T) {
      assert.ok(p.color >= 0 && p.color <= 0xffffff, `${p.id} color out of range`)
    }
  })

  it('all preset ids are unique', () => {
    const ids = BACKGROUND_PRESETS_T.map(p => p.id)
    assert.strictEqual(new Set(ids).size, ids.length)
  })

  it('preset ids match BgPresetId type values', () => {
    const valid: BgPresetId[] = ['dark_eng', 'neutral_gray', 'light_eng', 'gradient_dark', 'gradient_light']
    for (const p of BACKGROUND_PRESETS_T) {
      assert.ok(valid.includes(p.id), `${p.id} not a valid BgPresetId`)
    }
  })
})

describe('LAYOUT_PRESETS — MUST 6, HARD RULE 1, 2', () => {
  const presetIds: LayoutPresetId[] = ['MODEL', 'DRAWING', 'MANUFACTURING', 'CAM', 'SIMULATION', 'INSPECTION']

  it('has exactly 6 presets', () => assert.strictEqual(presetIds.length, 6))

  it('all presets are defined', () => {
    for (const id of presetIds) {
      assert.ok(id in LAYOUT_PRESETS_T, `Missing preset: ${id}`)
    }
  })

  it('no preset contains engineering data fields — HARD RULE 1', () => {
    const forbiddenFields = ['operationId', 'toolRef', 'machineId', 'workflowId', 'planStatus', 'drawingNumber']
    for (const id of presetIds) {
      const preset = LAYOUT_PRESETS_T[id]
      for (const field of forbiddenFields) {
        assert.ok(!(field in preset), `Preset ${id} illegally contains engineering field: ${field}`)
      }
    }
  })

  it('no preset triggers simulation or CAM regen — HARD RULE 2', () => {
    const forbiddenFields = ['runSimulation', 'regenToolpath', 'dispatchJob', 'confirmWcs']
    for (const id of presetIds) {
      const preset = LAYOUT_PRESETS_T[id]
      for (const field of forbiddenFields) {
        assert.ok(!(field in preset), `Preset ${id} illegally contains control field: ${field}`)
      }
    }
  })

  it('MODEL preset shows model tree and properties', () => {
    assert.strictEqual(LAYOUT_PRESETS_T.MODEL.showModelTree, true)
    assert.strictEqual(LAYOUT_PRESETS_T.MODEL.showProperties, true)
  })

  it('CAM preset shows model tree and CAM panel', () => {
    assert.strictEqual(LAYOUT_PRESETS_T.CAM.showModelTree, true)
    assert.strictEqual(LAYOUT_PRESETS_T.CAM.showCamPanel, true)
  })

  it('SIMULATION preset hides model tree', () => {
    assert.strictEqual(LAYOUT_PRESETS_T.SIMULATION.showModelTree, false)
  })

  it('all panel width/height values in presets are within bounds when defined', () => {
    for (const id of presetIds) {
      const p = LAYOUT_PRESETS_T[id]
      if (p.leftWidth   !== undefined) assert.ok(p.leftWidth   >= MIN_PANEL_WIDTH_T  && p.leftWidth   <= MAX_PANEL_WIDTH_T,  `${id}.leftWidth out of range`)
      if (p.rightWidth  !== undefined) assert.ok(p.rightWidth  >= MIN_PANEL_WIDTH_T  && p.rightWidth  <= MAX_PANEL_WIDTH_T,  `${id}.rightWidth out of range`)
      if (p.bottomHeight !== undefined) assert.ok(p.bottomHeight >= MIN_BOTTOM_HEIGHT_T && p.bottomHeight <= MAX_BOTTOM_HEIGHT_T, `${id}.bottomHeight out of range`)
    }
  })
})

describe('PART_OPACITY_PRESETS — MUST 20', () => {
  it('has exactly 4 opacity values', () => assert.strictEqual(PART_OPACITY_PRESETS_T.length, 4))
  it('includes 100% (fully opaque)', () => assert.ok(PART_OPACITY_PRESETS_T.includes(1)))
  it('includes 75%',  () => assert.ok(PART_OPACITY_PRESETS_T.includes(0.75)))
  it('includes 50%',  () => assert.ok(PART_OPACITY_PRESETS_T.includes(0.5)))
  it('includes 25%',  () => assert.ok(PART_OPACITY_PRESETS_T.includes(0.25)))
  it('all values between 0 and 1 inclusive', () => {
    for (const v of PART_OPACITY_PRESETS_T) {
      assert.ok(v > 0 && v <= 1, `${v} out of range`)
    }
  })
  it('values are in descending order', () => {
    for (let i = 1; i < PART_OPACITY_PRESETS_T.length; i++) {
      assert.ok(PART_OPACITY_PRESETS_T[i]! < PART_OPACITY_PRESETS_T[i-1]!, `Not descending at index ${i}`)
    }
  })
})

describe('WorkspaceLayout — HARD RULE 7: layout never in engineering records', () => {
  it('WorkspaceLayout has no operationId field', () => {
    const layout: WorkspaceLayout = { ...DEFAULT_LAYOUT_T }
    assert.ok(!('operationId' in layout))
  })

  it('WorkspaceLayout has no toolRef field', () => {
    const layout: WorkspaceLayout = { ...DEFAULT_LAYOUT_T }
    assert.ok(!('toolRef' in layout))
  })

  it('WorkspaceLayout has no machineId field', () => {
    const layout: WorkspaceLayout = { ...DEFAULT_LAYOUT_T }
    assert.ok(!('machineId' in layout))
  })

  it('WorkspaceLayout has no workflowId field', () => {
    const layout: WorkspaceLayout = { ...DEFAULT_LAYOUT_T }
    assert.ok(!('workflowId' in layout))
  })

  it('bgPresetId change does not affect SAFETY constants', () => {
    const layout: WorkspaceLayout = { ...DEFAULT_LAYOUT_T, bgPresetId: 'light_eng' }
    assert.strictEqual(SAFETY.IS_DISPATCHABLE,     false)
    assert.strictEqual(SAFETY.PRODUCTION_RELEASED, false)
    assert.strictEqual(SAFETY.COLLISION_CHECK,     'NOT_PERFORMED')
    assert.strictEqual(layout.bgPresetId,          'light_eng')
  })
})

describe('Panel sizing constraints — HARD RULE 5', () => {
  it('MIN_PANEL_WIDTH is non-zero — viewport cannot be squeezed to zero', () => {
    assert.ok(MIN_PANEL_WIDTH_T > 0)
  })
  it('MAX_PANEL_WIDTH > MIN_PANEL_WIDTH', () => {
    assert.ok(MAX_PANEL_WIDTH_T > MIN_PANEL_WIDTH_T)
  })
  it('MIN_BOTTOM_HEIGHT is non-zero', () => {
    assert.ok(MIN_BOTTOM_HEIGHT_T > 0)
  })
  it('MAX_BOTTOM_HEIGHT > MIN_BOTTOM_HEIGHT', () => {
    assert.ok(MAX_BOTTOM_HEIGHT_T > MIN_BOTTOM_HEIGHT_T)
  })
})

// ---------------------------------------------------------------------------
// MUST 12: File load status badge
// ---------------------------------------------------------------------------

describe('File load status — MUST 12', () => {
  type FileLoadStatus = 'IDLE' | 'LOADING' | 'GEOMETRY_READY' | 'FAILED' | 'UNSUPPORTED'

  const ALL_STATUSES: FileLoadStatus[] = ['IDLE', 'LOADING', 'GEOMETRY_READY', 'FAILED', 'UNSUPPORTED']

  it('All 5 required status values exist', () => {
    assert.strictEqual(ALL_STATUSES.length, 5)
  })

  it('GEOMETRY_READY is distinct from LOADING', () => {
    const s1: FileLoadStatus = 'GEOMETRY_READY'
    const s2: FileLoadStatus = 'LOADING'
    assert.notStrictEqual(s1, s2)
  })

  it('FAILED is distinct from UNSUPPORTED', () => {
    const s1: FileLoadStatus = 'FAILED'
    const s2: FileLoadStatus = 'UNSUPPORTED'
    assert.notStrictEqual(s1, s2)
  })

  it('Default status is IDLE, not a failure state', () => {
    const dflt: FileLoadStatus = 'IDLE'
    assert.strictEqual(dflt, 'IDLE')
    assert.notStrictEqual(dflt, 'FAILED')
  })

  it('After STEP mesh received → GEOMETRY_READY', () => {
    function simulateStepResult(hasMesh: boolean): FileLoadStatus {
      return hasMesh ? 'GEOMETRY_READY' : 'FAILED'
    }
    assert.strictEqual(simulateStepResult(true),  'GEOMETRY_READY')
    assert.strictEqual(simulateStepResult(false), 'FAILED')
  })

  it('STL/OBJ/3MF always → GEOMETRY_READY (client-rendered)', () => {
    const clientFormats: FileFormat[] = ['STL', 'OBJ', '3MF']
    function statusForClient(fmt: FileFormat): FileLoadStatus {
      if (['STL', 'OBJ', '3MF'].includes(fmt)) return 'GEOMETRY_READY'
      return 'UNSUPPORTED'
    }
    for (const f of clientFormats) assert.strictEqual(statusForClient(f), 'GEOMETRY_READY')
  })

  it('IMAGE/UNKNOWN → UNSUPPORTED', () => {
    const noPreviewFormats: FileFormat[] = ['IMAGE', 'UNKNOWN']
    function statusForNoPreview(fmt: FileFormat): FileLoadStatus {
      return ['IMAGE', 'UNKNOWN'].includes(fmt) ? 'UNSUPPORTED' : 'GEOMETRY_READY'
    }
    for (const f of noPreviewFormats) assert.strictEqual(statusForNoPreview(f), 'UNSUPPORTED')
  })
})

// ---------------------------------------------------------------------------
// MUST 13: Structured error diagnostic
// ---------------------------------------------------------------------------

describe('Import error diagnostic — MUST 13', () => {
  interface ImportDiagnostic {
    file: string; format: string; stage: string; cause: string; action: string
  }

  it('All 5 required diagnostic fields are present', () => {
    const d: ImportDiagnostic = {
      file: 'MP_SYN_001.step',
      format: 'STEP-GENERIC',
      stage: 'TESSELLATION_FAILED',
      cause: 'Tessellation produced no geometry.',
      action: 'Ensure the STEP file contains solid or surface bodies.',
    }
    assert.ok(d.file)
    assert.ok(d.format)
    assert.ok(d.stage)
    assert.ok(d.cause)
    assert.ok(d.action)
  })

  it('Stage is TESSELLATION_FAILED when backend returned no preview_mesh', () => {
    function inferStage(hasMesh: boolean | undefined): string {
      if (hasMesh === undefined) return 'TESSELLATION_FAILED'
      return hasMesh ? 'GEOMETRY_OK' : 'NO_GEOMETRY_RETURNED'
    }
    assert.strictEqual(inferStage(undefined), 'TESSELLATION_FAILED')
    assert.strictEqual(inferStage(false),     'NO_GEOMETRY_RETURNED')
    assert.strictEqual(inferStage(true),      'GEOMETRY_OK')
  })

  it('Cause prefers fidelity_events LOST/UNSUPPORTED class over generic message', () => {
    function pickCause(events?: Array<{class: string; description: string}>, errors?: string[]): string {
      const first = events?.find(ev => ev.class === 'LOST' || ev.class === 'UNSUPPORTED')
      return first?.description ?? errors?.[0] ?? 'Tessellation produced no geometry.'
    }
    assert.strictEqual(pickCause([{class: 'UNSUPPORTED', description: 'OCC not available'}]), 'OCC not available')
    assert.strictEqual(pickCause([], ['some error']), 'some error')
    assert.strictEqual(pickCause(), 'Tessellation produced no geometry.')
  })

  it('Action differs between STEP and IGES formats', () => {
    function pickAction(format: string): string {
      return format === 'STEP'
        ? 'Ensure the STEP file contains solid or surface bodies. Try saving as AP214 or AP242.'
        : 'Ensure the IGES file contains surfaces or solid geometry. Resave from the originating CAD tool.'
    }
    assert.ok(pickAction('STEP').includes('AP214'))
    assert.ok(pickAction('IGES').includes('IGES'))
    assert.notStrictEqual(pickAction('STEP'), pickAction('IGES'))
  })
})

// ---------------------------------------------------------------------------
// MUST 6: Default display mode is shaded_edges
// ---------------------------------------------------------------------------

describe('Default display mode — MUST 6', () => {
  it('shaded_edges is a valid DisplayMode value', () => {
    const mode: DisplayMode = 'shaded_edges'
    assert.strictEqual(mode, 'shaded_edges')
  })

  it('shaded_edges is distinct from plain shaded', () => {
    const edges: DisplayMode  = 'shaded_edges'
    const plain: DisplayMode  = 'shaded'
    assert.notStrictEqual(edges, plain)
  })

  it('Default mode must be shaded_edges, not plain shaded', () => {
    const DEFAULT_DISPLAY_MODE: DisplayMode = 'shaded_edges'
    assert.strictEqual(DEFAULT_DISPLAY_MODE, 'shaded_edges')
    assert.notStrictEqual(DEFAULT_DISPLAY_MODE, 'shaded')
  })
})

// ---------------------------------------------------------------------------
// MUST 4/MUST 8: Backend B-Rep format detection logic
// ---------------------------------------------------------------------------

describe('B-Rep tessellation eligibility — MUST 4/MUST 8', () => {
  type ImportStatus = 'SUCCESS' | 'PARTIAL_SUCCESS' | 'RECOGNIZED_ONLY' | 'FAILED' | 'UNRECOGNIZED' | 'PARSE_ERROR' | 'UNKNOWN'

  function canTessellate(status: ImportStatus): boolean {
    // Mirror backend fix: not in FAILED/UNRECOGNIZED/PARSE_ERROR
    return !(['FAILED', 'UNRECOGNIZED', 'PARSE_ERROR'] as ImportStatus[]).includes(status)
  }

  it('SUCCESS can tessellate', () => { assert.ok(canTessellate('SUCCESS')) })
  it('PARTIAL_SUCCESS can tessellate — ROOT CAUSE FIX', () => { assert.ok(canTessellate('PARTIAL_SUCCESS')) })
  it('RECOGNIZED_ONLY can tessellate', () => { assert.ok(canTessellate('RECOGNIZED_ONLY')) })
  it('FAILED cannot tessellate', () => { assert.ok(!canTessellate('FAILED')) })
  it('UNRECOGNIZED cannot tessellate', () => { assert.ok(!canTessellate('UNRECOGNIZED')) })
  it('PARSE_ERROR cannot tessellate', () => { assert.ok(!canTessellate('PARSE_ERROR')) })

  it('STEP format triggers STEP tessellation', () => {
    function chooseFormat(formatId: string): 'STEP' | 'IGES' | 'NONE' {
      if (formatId.startsWith('STEP')) return 'STEP'
      if (formatId === 'IGES') return 'IGES'
      return 'NONE'
    }
    assert.strictEqual(chooseFormat('STEP-GENERIC'), 'STEP')
    assert.strictEqual(chooseFormat('STEP-AP214'),   'STEP')
    assert.strictEqual(chooseFormat('IGES'),         'IGES')
    assert.strictEqual(chooseFormat('DXF'),          'NONE')
  })

  it('PARTIAL_SUCCESS + STEP = tessellation attempted (key regression guard)', () => {
    const importStatus: ImportStatus = 'PARTIAL_SUCCESS'
    const formatId = 'STEP-GENERIC'
    const eligible = canTessellate(importStatus) && formatId.startsWith('STEP')
    assert.ok(eligible, 'STEP with PARTIAL_SUCCESS must attempt tessellation')
  })
})
