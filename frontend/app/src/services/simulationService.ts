/**
 * Simulation service — calls POST /api/verification/simulate.
 *
 * Safety contract:
 *   IS_DISPATCHABLE=false          — no machine dispatch, offline simulation only
 *   NO_FABRICATED_SEGMENTS=YES     — segments derived from real toolpath points only
 *   NO_FAKE_COLLISION_PASS=YES     — missing geometry reports NOT_VERIFIABLE
 *   SIMULATION_REQUIRED=true       — results do not constitute verified NC approval
 */

import { getStoredAuth } from './apiClient'
import type { ToolpathLineGroup } from '../components/workspace/WorkspaceTypes'

// ---------------------------------------------------------------------------
// Request / Response types (mirrors backend verification/models.py)
// ---------------------------------------------------------------------------

export interface VerificationSegmentFE {
  start_x: number
  start_y: number
  start_z: number
  end_x: number
  end_y: number
  end_z: number
  motion_type: string
  is_cutting: boolean
  operation_id: string | null
  tool_id: string | null
}

export interface StockModelFE {
  shape: 'BOX' | 'CYLINDER' | 'UNKNOWN'
  fidelity?: 'USER_CONFIRMED' | 'SUGGESTED' | 'UNKNOWN'
  min_x_mm?: number | null
  min_y_mm?: number | null
  min_z_mm?: number | null
  max_x_mm?: number | null
  max_y_mm?: number | null
  max_z_mm?: number | null
}

export interface SimulationRequestFE {
  toolpath_id: string
  segments: VerificationSegmentFE[]
  tool_diameter_mm?: number | null
  tool_length_mm?: number | null
  tool_flute_length_mm?: number | null
  holder_diameter_mm?: number | null
  holder_length_mm?: number | null
  stock?: StockModelFE | null
  part_bbox_min?: [number, number, number] | null
  part_bbox_max?: [number, number, number] | null
}

export interface VerificationCheckResultFE {
  check_type: string
  status: string
  severity: string
  warnings: string[]
  errors: string[]
  issues: Array<{ message: string; severity: string; segment_id?: string }>
}

export interface SimulationVisualizationFE {
  stock_bbox: Record<string, number> | null
  collision_points: Array<[number, number, number]>
  gouge_points: Array<[number, number, number]>
  remaining_stock_note: string | null
}

export interface SimulationResultFE {
  session_id: string
  toolpath_id: string
  simulation_status: 'COMPLETED' | 'FAILED' | 'PARTIAL' | string
  verification_state: string
  checks: Record<string, VerificationCheckResultFE>
  initial_stock_volume_mm3: number | null
  remaining_stock_volume_mm3: number | null
  removed_volume_mm3: number | null
  stock_removal_fidelity: string
  visualization: SimulationVisualizationFE | null
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const CUTTING_MOTION_TYPES = new Set(['FEED', 'PLUNGE', 'CUTTING', 'FINISH_PASS'])

/** Convert frontend toolpath groups to VerificationSegments for the simulation API. */
export function toolpathGroupsToSegments(
  groups: ToolpathLineGroup[],
): VerificationSegmentFE[] {
  const segments: VerificationSegmentFE[] = []
  for (const group of groups) {
    const pts = group.points
    if (pts.length < 6) continue
    for (let i = 0; i + 3 < pts.length; i += 3) {
      segments.push({
        start_x:  pts[i]!,
        start_y:  pts[i + 1]!,
        start_z:  pts[i + 2]!,
        end_x:    pts[i + 3]!,
        end_y:    pts[i + 4]!,
        end_z:    pts[i + 5]!,
        motion_type:  group.motionType,
        is_cutting:   CUTTING_MOTION_TYPES.has(group.motionType),
        operation_id: group.operationRef,
        tool_id:      null,
      })
    }
  }
  return segments
}

/** Extract flat list of ordered positions from toolpath groups for animation. */
export function toolpathGroupsToAnimFrames(
  groups: ToolpathLineGroup[],
): Array<[number, number, number]> {
  const frames: Array<[number, number, number]> = []
  for (const group of groups) {
    const pts = group.points
    for (let i = 0; i + 2 < pts.length; i += 3) {
      frames.push([pts[i]!, pts[i + 1]!, pts[i + 2]!])
    }
  }
  return frames
}

// ---------------------------------------------------------------------------
// API call
// ---------------------------------------------------------------------------

export class SimulationApiError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function runSimulation(
  req: SimulationRequestFE,
  token?: string | null,
): Promise<SimulationResultFE> {
  const auth = getStoredAuth()
  const tok = token ?? auth.token
  if (!tok) throw new SimulationApiError(401, 'Authentication required')

  const resp = await fetch('/api/verification/simulate', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${tok}`,
    },
    body: JSON.stringify(req),
  })

  if (!resp.ok) {
    let detail = `Simulation request failed: ${resp.status}`
    try {
      const err = await resp.json() as Record<string, unknown>
      if (typeof err['detail'] === 'string') detail = err['detail']
    } catch { /* non-JSON */ }
    throw new SimulationApiError(resp.status, detail)
  }

  return resp.json() as Promise<SimulationResultFE>
}
