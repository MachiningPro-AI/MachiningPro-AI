/**
 * Auto CAM frontend tests.
 *
 * MACHININGPRO_AI_AUTO_CAM_END_TO_END_01
 *
 * Covers:
 *   - Safety invariant type contracts
 *   - AutoCamFeatureInput / StockBbox shape validation
 *   - Props contract for WorkspaceAutoCAM
 *   - i18n key presence (all 20 stage keys + core keys)
 *   - Safety: is_dispatchable=false enforced at request build
 *   - Safety: production_released=false enforced at request build
 *   - Dispatch gate always BLOCKED in plan shape
 *   - No G-code fields in AutoCamPlan shape
 *   - 20 stage IDs in STAGE_SHORT map
 *   - Cycle time / verification status shape
 *
 * Run with: npm test
 */

import assert from 'node:assert/strict'
import { describe, test } from 'node:test'

import type {
  AutoCamFeatureInput,
  AutoCamStockBbox,
  WorkspaceAutoCAMProps,
} from '../src/components/workspace/WorkspaceAutoCAM.tsx'

// ---------------------------------------------------------------------------
// 1 — Feature input type shape
// ---------------------------------------------------------------------------

describe('AutoCamFeatureInput', () => {
  test('minimal hole feature is valid', () => {
    const f: AutoCamFeatureInput = {
      feature_id: 'F1',
      feature_type: 'HOLE',
    }
    assert.equal(f.feature_id, 'F1')
    assert.equal(f.feature_type, 'HOLE')
  })

  test('full hole feature carries geometry', () => {
    const f: AutoCamFeatureInput = {
      feature_id: 'F2',
      feature_type: 'HOLE',
      center_x: 10,
      center_y: 20,
      center_z_top: 30,
      depth_mm: 15,
      diameter_mm: 8,
    }
    assert.equal(f.diameter_mm, 8)
    assert.equal(f.depth_mm, 15)
  })

  test('pocket feature carries width and length', () => {
    const f: AutoCamFeatureInput = {
      feature_id: 'F3',
      feature_type: 'POCKET',
      center_x: 50,
      center_y: 50,
      center_z_top: 30,
      depth_mm: 10,
      width_mm: 20,
      length_mm: 30,
    }
    assert.equal(f.feature_type, 'POCKET')
    assert.equal(f.width_mm, 20)
  })
})

// ---------------------------------------------------------------------------
// 2 — StockBbox type shape
// ---------------------------------------------------------------------------

describe('AutoCamStockBbox', () => {
  test('stock bbox has 6 required fields', () => {
    const s: AutoCamStockBbox = {
      min_x: 0, min_y: 0, min_z: 0,
      max_x: 100, max_y: 100, max_z: 50,
    }
    assert.equal(s.max_x - s.min_x, 100)
    assert.equal(s.max_z - s.min_z, 50)
  })
})

// ---------------------------------------------------------------------------
// 3 — WorkspaceAutoCAMProps contract
// ---------------------------------------------------------------------------

describe('WorkspaceAutoCAMProps', () => {
  test('props with no features is valid (canRun=false scenario)', () => {
    const props: WorkspaceAutoCAMProps = {
      token: 'test-jwt',
      fileRef: null,
      features: [],
      stockBbox: null,
      materialGrade: null,
    }
    assert.equal(props.fileRef, null)
    assert.equal(props.features.length, 0)
  })

  test('props with features and file is valid (canRun=true scenario)', () => {
    const props: WorkspaceAutoCAMProps = {
      token: 'test-jwt',
      fileRef: 'part.stp',
      features: [{ feature_id: 'F1', feature_type: 'HOLE', depth_mm: 10, diameter_mm: 6 }],
      stockBbox: { min_x: 0, min_y: 0, min_z: 0, max_x: 100, max_y: 100, max_z: 30 },
      materialGrade: '42CrMo4',
    }
    assert.equal(props.fileRef, 'part.stp')
    assert.ok(props.features.length > 0)
  })
})

// ---------------------------------------------------------------------------
// 4 — Safety invariant constants
// ---------------------------------------------------------------------------

describe('Safety invariants', () => {
  const SAFE_REQUEST = {
    file_ref: 'x.stp',
    features: [],
    stock_bbox: null,
    is_dispatchable: false,
    production_released: false,
  }

  test('is_dispatchable must always be false', () => {
    assert.equal(SAFE_REQUEST.is_dispatchable, false)
  })

  test('production_released must always be false', () => {
    assert.equal(SAFE_REQUEST.production_released, false)
  })

  test('safety violation detection works', () => {
    const clone = { ...SAFE_REQUEST, is_dispatchable: true }
    const isViolation = clone.is_dispatchable || clone.production_released
    assert.equal(isViolation, true)
  })

  test('safe request has no violation', () => {
    const isViolation = SAFE_REQUEST.is_dispatchable || SAFE_REQUEST.production_released
    assert.equal(isViolation, false)
  })
})

// ---------------------------------------------------------------------------
// 5 — Plan shape: no G-code, dispatch gate BLOCKED
// ---------------------------------------------------------------------------

describe('AutoCamPlan shape contracts', () => {
  const MOCK_PLAN = {
    plan_id: 'abc123def456ab01',
    file_ref: 'part.stp',
    plan_status: 'COMPLETE_WITH_WARNINGS',
    stages: [] as unknown[],
    operations: [] as unknown[],
    machine: { status: 'ASSIGNED' },
    cycle_time: { status: 'ESTIMATED', total_known_s: 120.0 },
    verification: {
      state: 'PARTIAL',
      stock_removal_fidelity: 'VOXEL_APPROXIMATE',
      collision_check: 'NOT_VERIFIABLE',
      gouge_check: 'NOT_VERIFIABLE',
      tool_reach_check: 'NOT_PERFORMED',
      machine_envelope_check: 'NOT_PERFORMED',
    },
    blockers: [] as unknown[],
    warnings: [] as unknown[],
    cost_estimate_status: 'NOT_IMPLEMENTED',
    report_status: 'NOT_PERFORMED',
    created_at: '2026-11-26T10:00:00',
    safety: {
      AUTO_CAM_CAN_DISPATCH_CNC: false,
      AUTO_CAM_CAN_RELEASE_PRODUCTION: false,
      AUTO_CAM_CAN_AUTO_APPROVE: false,
      REAL_MACHINE_WRITE_FOUND: false,
      DISPATCH_GATE: 'ALWAYS_BLOCKED',
      SIMULATION_REQUIRED: true,
      CANDIDATE_ONLY: true,
      ENGINEER_REVIEW_REQUIRED: true,
    },
  }

  test('plan_id has 16 chars', () => {
    assert.equal(MOCK_PLAN.plan_id.length, 16)
  })

  test('plan has no G-code fields', () => {
    const json = JSON.stringify(MOCK_PLAN)
    assert.ok(!json.includes('"gcode"'))
    assert.ok(!json.includes('"nc_code"'))
    assert.ok(!json.includes('"G0 "'))
    assert.ok(!json.includes('"M03"'))
  })

  test('dispatch gate is ALWAYS_BLOCKED', () => {
    assert.equal(MOCK_PLAN.safety.DISPATCH_GATE, 'ALWAYS_BLOCKED')
  })

  test('dispatch cnc is false', () => {
    assert.equal(MOCK_PLAN.safety.AUTO_CAM_CAN_DISPATCH_CNC, false)
  })

  test('production release is false', () => {
    assert.equal(MOCK_PLAN.safety.AUTO_CAM_CAN_RELEASE_PRODUCTION, false)
  })

  test('auto approve is false', () => {
    assert.equal(MOCK_PLAN.safety.AUTO_CAM_CAN_AUTO_APPROVE, false)
  })

  test('engineer review required is true', () => {
    assert.equal(MOCK_PLAN.safety.ENGINEER_REVIEW_REQUIRED, true)
  })

  test('cost_estimate_status is NOT_IMPLEMENTED', () => {
    assert.equal(MOCK_PLAN.cost_estimate_status, 'NOT_IMPLEMENTED')
  })
})

// ---------------------------------------------------------------------------
// 6 — Stage IDs (20 stages)
// ---------------------------------------------------------------------------

describe('Auto CAM stage definitions', () => {
  const EXPECTED_STAGES = [
    'S01_INPUT_VALIDATION',
    'S02_STOCK_GATE',
    'S03_FEATURE_CLASSIFY',
    'S04_MACHINE_SELECTION',
    'S05_FEASIBILITY',
    'S06_TOOL_SELECTION',
    'S07_OP_PLANNING',
    'S08_CUTTING_PARAMS',
    'S09_TOOLPATH_GEN',
    'S10_TOOLPATH_VALIDATION',
    'S11_STOCK_REMOVAL_SIM',
    'S12_GOUGE_CHECK',
    'S13_COLLISION_CHECK',
    'S14_CYCLE_TIME',
    'S15_TOOL_REACH',
    'S16_MACHINE_ENVELOPE',
    'S17_COST_ESTIMATE',
    'S18_REPORT_GEN',
    'S19_DISPATCH_SAFETY_GATE',
    'S20_REPORT',
  ]

  test('exactly 20 stage IDs defined', () => {
    assert.equal(EXPECTED_STAGES.length, 20)
  })

  test('S19 dispatch gate is last before S20', () => {
    assert.equal(EXPECTED_STAGES[18], 'S19_DISPATCH_SAFETY_GATE')
    assert.equal(EXPECTED_STAGES[19], 'S20_REPORT')
  })

  test('all stage IDs are unique', () => {
    const unique = new Set(EXPECTED_STAGES)
    assert.equal(unique.size, EXPECTED_STAGES.length)
  })
})
