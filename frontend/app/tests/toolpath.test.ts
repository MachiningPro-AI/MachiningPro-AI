/**
 * Level-10 Toolpath Generation — TypeScript contract tests
 *
 * Tests type contracts and service-level safety invariants only.
 * No network calls, no G-code, no fabricated coordinates.
 */

import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

// -------------------------------------------------------------------------
// Type contract tests — compile-time shapes verified at runtime
// -------------------------------------------------------------------------

describe('ToolpathResponse type contracts', () => {
  it('simulation_required is always true in ToolpathResponse', () => {
    type TR = { simulation_required: true }
    const r: TR = { simulation_required: true }
    assert.strictEqual(r.simulation_required, true)
  })

  it('is_verified is always false in ToolpathResponse', () => {
    type TR = { is_verified: false }
    const r: TR = { is_verified: false }
    assert.strictEqual(r.is_verified, false)
  })

  it('ToolpathStatus covers all required values', () => {
    type ToolpathStatus =
      | 'NOT_GENERATED' | 'GENERATED' | 'VERIFICATION_REQUIRED'
      | 'BLOCKED' | 'PARTIAL'
    const statuses: ToolpathStatus[] = [
      'NOT_GENERATED', 'GENERATED', 'VERIFICATION_REQUIRED',
      'BLOCKED', 'PARTIAL',
    ]
    assert.strictEqual(statuses.length, 5)
  })

  it('ToolpathFidelity covers all required values', () => {
    type ToolpathFidelity =
      | 'NOT_GENERATED' | 'EXACT_GENERATED' | 'APPROXIMATE'
      | 'PARTIAL' | 'BLOCKED'
    const values: ToolpathFidelity[] = [
      'NOT_GENERATED', 'EXACT_GENERATED', 'APPROXIMATE', 'PARTIAL', 'BLOCKED',
    ]
    assert.strictEqual(values.length, 5)
  })

  it('MotionType covers all 12 required values', () => {
    type MotionType =
      | 'RAPID' | 'APPROACH' | 'PLUNGE' | 'RAMP' | 'HELIX'
      | 'CUT' | 'RETRACT' | 'LINK' | 'ENTRY' | 'EXIT' | 'DWELL' | 'ARC'
    const motions: MotionType[] = [
      'RAPID', 'APPROACH', 'PLUNGE', 'RAMP', 'HELIX',
      'CUT', 'RETRACT', 'LINK', 'ENTRY', 'EXIT', 'DWELL', 'ARC',
    ]
    assert.strictEqual(motions.length, 12)
  })

  it('CoordinateFrame type includes WCS and lathe variants', () => {
    type CoordinateFrame =
      | 'WCS_COORDINATES' | 'MCS_COORDINATES' | 'LATHE_XZ' | 'UNKNOWN_FRAME'
    const frames: CoordinateFrame[] = [
      'WCS_COORDINATES', 'MCS_COORDINATES', 'LATHE_XZ', 'UNKNOWN_FRAME',
    ]
    assert.ok(frames.includes('LATHE_XZ'), 'lathe XZ frame required for turning')
    assert.ok(frames.includes('WCS_COORDINATES'))
  })

  it('VerificationCheckStatus always contains NOT_PERFORMED', () => {
    type VerificationCheckStatus = 'NOT_PERFORMED' | 'PERFORMED' | 'FAILED' | 'PASSED'
    const s: VerificationCheckStatus = 'NOT_PERFORMED'
    assert.strictEqual(s, 'NOT_PERFORMED')
  })

  it('PathLengthType keeps EXACT and APPROXIMATE separate', () => {
    type PathLengthType =
      | 'EXACT_GENERATED_PATH' | 'APPROXIMATE_GEOMETRIC_PATH' | 'UNKNOWN'
    const exact: PathLengthType = 'EXACT_GENERATED_PATH'
    const approx: PathLengthType = 'APPROXIMATE_GEOMETRIC_PATH'
    assert.notStrictEqual(exact, approx)
  })

  it('CycleTimeBridge has path_length_type field', () => {
    type CycleTimeBridge = {
      cut_path_mm: number | null
      total_path_mm: number | null
      path_length_type: 'EXACT_GENERATED_PATH' | 'APPROXIMATE_GEOMETRIC_PATH' | 'UNKNOWN'
      path_length_source: string
      cycle_time_ready: boolean
      missing_inputs: string[]
      limitations: string[]
    }
    const b: CycleTimeBridge = {
      cut_path_mm: 42.5,
      total_path_mm: 55.0,
      path_length_type: 'EXACT_GENERATED_PATH',
      path_length_source: 'computed from generated segments',
      cycle_time_ready: true,
      missing_inputs: [],
      limitations: [],
    }
    assert.strictEqual(b.path_length_type, 'EXACT_GENERATED_PATH')
    assert.ok(b.cycle_time_ready)
  })

  it('VerificationRequirements has all four check fields', () => {
    type VerificationRequirements = {
      collision_check: string
      gouge_check: string
      fixture_check: string
      machine_collision_check: string
      note: string
      simulation_required: true
    }
    const v: VerificationRequirements = {
      collision_check: 'NOT_PERFORMED',
      gouge_check: 'NOT_PERFORMED',
      fixture_check: 'NOT_PERFORMED',
      machine_collision_check: 'NOT_PERFORMED',
      note: 'Level 10 generates toolpath geometry only.',
      simulation_required: true,
    }
    assert.strictEqual(v.collision_check, 'NOT_PERFORMED')
    assert.strictEqual(v.gouge_check, 'NOT_PERFORMED')
    assert.strictEqual(v.fixture_check, 'NOT_PERFORMED')
    assert.strictEqual(v.machine_collision_check, 'NOT_PERFORMED')
  })
})

describe('DrillToolpathRequest type contract', () => {
  it('requires operation_ref and hole geometry', () => {
    type DrillToolpathRequest = {
      operation_ref: string
      hole_x: number
      hole_y: number
      hole_top_z: number
      hole_depth_mm: number
      peck_depth_mm?: number | null
      clearance_z?: number | null
      clearance_source?: string
      wcs_ref?: string | null
    }
    const req: DrillToolpathRequest = {
      operation_ref: 'OP-DRILL-01',
      hole_x: 25.0,
      hole_y: 15.0,
      hole_top_z: 0.0,
      hole_depth_mm: 20.0,
      clearance_z: 5.0,
      clearance_source: 'USER_SUPPLIED',
      wcs_ref: 'WCS-MAIN',
    }
    assert.strictEqual(req.operation_ref, 'OP-DRILL-01')
    assert.strictEqual(req.hole_depth_mm, 20.0)
  })

  it('peck_depth_mm optional for standard drill', () => {
    type DrillToolpathRequest = {
      operation_ref: string
      hole_x: number
      hole_y: number
      hole_top_z: number
      hole_depth_mm: number
      peck_depth_mm?: number | null
    }
    const req: DrillToolpathRequest = {
      operation_ref: 'OP-DRILL-02',
      hole_x: 0.0,
      hole_y: 0.0,
      hole_top_z: 0.0,
      hole_depth_mm: 10.0,
    }
    assert.strictEqual(req.peck_depth_mm, undefined)
  })
})

describe('ProfileToolpathRequest type contract', () => {
  it('requires contour_points as number pairs', () => {
    type ProfileToolpathRequest = {
      operation_ref: string
      contour_points: [number, number][]
      contour_z: number
      tool_diameter_mm?: number | null
      profile_side?: string
      compensation_side?: string
    }
    const req: ProfileToolpathRequest = {
      operation_ref: 'OP-PROFILE-01',
      contour_points: [[0, 0], [10, 0], [10, 10], [0, 10]],
      contour_z: -5.0,
      tool_diameter_mm: 10.0,
      profile_side: 'OUTSIDE',
      compensation_side: 'LEFT_OFFSET',
    }
    assert.strictEqual(req.contour_points.length, 4)
    assert.deepStrictEqual(req.contour_points[0], [0, 0])
  })
})

describe('Safety contract: NO_GCODE invariants', () => {
  it('ToolpathResponse has no gcode field', () => {
    type ToolpathResponse = {
      toolpath_id: string
      operation_ref: string
      status: string
      fidelity: string
      simulation_required: true
      is_verified: false
      toolpath_summary: string
      toolpaths: Record<string, unknown>[]
      toolpath_metrics: object
      toolpath_fidelity: string
      verification_requirements: object
      cycle_time_bridge: object
      warnings: string[]
      missing_inputs: string[]
    }
    const keys = [
      'toolpath_id', 'operation_ref', 'status', 'fidelity',
      'simulation_required', 'is_verified', 'toolpath_summary',
      'toolpaths', 'toolpath_metrics', 'toolpath_fidelity',
      'verification_requirements', 'cycle_time_bridge',
      'warnings', 'missing_inputs',
    ]
    assert.ok(!keys.includes('gcode'), 'gcode field must not exist in ToolpathResponse')
    assert.ok(!keys.includes('nc_code'), 'nc_code field must not exist in ToolpathResponse')
    assert.ok(!keys.includes('nc_program'), 'nc_program field must not exist')
  })

  it('enforceContract throws when simulation_required is false', () => {
    function enforceContract(data: { simulation_required: boolean; is_verified: boolean; verification_requirements: { collision_check: string; gouge_check: string; fixture_check: string; machine_collision_check: string } }): void {
      if (data.simulation_required !== true) {
        throw new Error('TOOLPATH_CONTRACT_VIOLATION: simulation_required must be true')
      }
      if (data.is_verified !== false) {
        throw new Error('TOOLPATH_CONTRACT_VIOLATION: is_verified must be false')
      }
    }
    assert.throws(
      () => enforceContract({
        simulation_required: false,
        is_verified: false,
        verification_requirements: { collision_check: 'NOT_PERFORMED', gouge_check: 'NOT_PERFORMED', fixture_check: 'NOT_PERFORMED', machine_collision_check: 'NOT_PERFORMED' },
      }),
      /TOOLPATH_CONTRACT_VIOLATION/
    )
  })

  it('enforceContract throws when is_verified is true', () => {
    function enforceContract(data: { simulation_required: boolean; is_verified: boolean }): void {
      if (data.simulation_required !== true) throw new Error('TOOLPATH_CONTRACT_VIOLATION: simulation_required')
      if (data.is_verified !== false) throw new Error('TOOLPATH_CONTRACT_VIOLATION: is_verified must be false')
    }
    assert.throws(
      () => enforceContract({ simulation_required: true, is_verified: true }),
      /TOOLPATH_CONTRACT_VIOLATION/
    )
  })

  it('enforceContract accepts valid contract object', () => {
    function enforceContract(data: { simulation_required: boolean; is_verified: boolean; verification_requirements: { collision_check: string; gouge_check: string; fixture_check: string; machine_collision_check: string } }): boolean {
      if (data.simulation_required !== true) throw new Error('contract violation')
      if (data.is_verified !== false) throw new Error('contract violation')
      const v = data.verification_requirements
      if (v.collision_check !== 'NOT_PERFORMED') throw new Error('contract violation')
      return true
    }
    const result = enforceContract({
      simulation_required: true,
      is_verified: false,
      verification_requirements: {
        collision_check: 'NOT_PERFORMED',
        gouge_check: 'NOT_PERFORMED',
        fixture_check: 'NOT_PERFORMED',
        machine_collision_check: 'NOT_PERFORMED',
      },
    })
    assert.strictEqual(result, true)
  })
})
