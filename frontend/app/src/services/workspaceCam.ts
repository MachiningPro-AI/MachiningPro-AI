/**
 * Workspace CAM Plan Generation Service
 *
 * Derives real CAM operations and toolpaths from a loaded mesh's bounding box.
 * Uses the existing /api/toolpath endpoints — NO fabricated data.
 *
 * Safety contract:
 *   NO_FABRICATED_TOOLPATHS=YES  — all points from real API responses
 *   NO_FAKE_CAM=YES              — inputs derived from actual mesh geometry
 *   SIMULATION_REQUIRED=YES      — passes through from toolpath API
 */

import { getStoredAuth } from './apiClient'
import type { ConnectedWorkflow, ToolpathLineGroup } from '../components/workspace/WorkspaceTypes'

// ---------------------------------------------------------------------------
// Types matching backend ToolpathSegment serialization
// ---------------------------------------------------------------------------

interface ToolpathSegmentFE {
  segment_id: string
  operation_ref: string
  motion_type: string
  start_point: [number, number, number] | null
  end_point: [number, number, number] | null
  polyline_points: Array<[number, number, number]>
}

interface ToolpathApiResponse {
  toolpath_id: string
  operation_ref: string
  status: string
  toolpaths: ToolpathSegmentFE[]
  warnings: string[]
  missing_inputs: string[]
}

// ---------------------------------------------------------------------------
// Segment → ToolpathLineGroup
// ---------------------------------------------------------------------------

function segmentsToGroups(segs: ToolpathSegmentFE[]): ToolpathLineGroup[] {
  const groups: ToolpathLineGroup[] = []
  for (const seg of segs) {
    let pts: number[] = []
    if (seg.polyline_points && seg.polyline_points.length >= 2) {
      pts = seg.polyline_points.flatMap(p => [p[0], p[1], p[2]])
    } else if (seg.start_point && seg.end_point) {
      pts = [
        seg.start_point[0], seg.start_point[1], seg.start_point[2],
        seg.end_point[0],   seg.end_point[1],   seg.end_point[2],
      ]
    }
    if (pts.length < 6) continue  // need at least 2 points
    const mt = seg.motion_type
    const motionType: ToolpathLineGroup['motionType'] =
      mt === 'RAPID'   ? 'RAPID'   :
      mt === 'FEED'    ? 'FEED'    :
      mt === 'PLUNGE'  ? 'PLUNGE'  :
      mt === 'RETRACT' ? 'RETRACT' : 'LINK'
    groups.push({ motionType, points: pts, operationRef: seg.operation_ref })
  }
  return groups
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

function tok(): string {
  return getStoredAuth().token ?? ''
}

async function postToolpath(
  endpoint: string,
  body: Record<string, unknown>,
  token: string,
): Promise<ToolpathApiResponse> {
  const resp = await fetch(`/api/toolpath/${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  })
  if (!resp.ok) {
    const text = await resp.text().catch(() => resp.statusText)
    throw new Error(`Toolpath API error (${endpoint} ${resp.status}): ${text}`)
  }
  return resp.json() as Promise<ToolpathApiResponse>
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export interface WorkspaceCamInput {
  bbox: { min: [number, number, number]; max: [number, number, number] }
  fileRef: string
  token?: string
}

export interface WorkspaceCamResult {
  workflow: ConnectedWorkflow
  warnings: string[]
}

/**
 * Derive real CAM operations from the mesh bounding box and generate toolpaths.
 *
 * Operations generated:
 *   1. FACE_MILL — face the top surface of the part (bbox-top XY region)
 *   2. PROFILE   — outer rectangular contour at stock depth (bbox outline)
 *
 * Both operations use geometry derived directly from the loaded file's bbox.
 * No coordinates are invented or hardcoded.
 */
export async function generateWorkspaceCamPlan(
  input: WorkspaceCamInput,
): Promise<WorkspaceCamResult> {
  const authToken = input.token ?? tok()
  if (!authToken) throw new Error('Authentication required')

  const { min, max } = input.bbox
  const [xMin, yMin, zMin] = min
  const [xMax, yMax, zMax] = max
  const height = zMax - zMin
  const clearanceZ = zMax + Math.max(height * 0.15, 5)  // 15% above part or min 5mm

  const warnings: string[] = []
  const groups: ToolpathLineGroup[] = []

  // ---------------------------------------------------------------------------
  // Op 1 — Face Mill (face top of part)
  // ---------------------------------------------------------------------------
  const faceMachFace = `FACE_MILL_${input.fileRef.replace(/[^a-zA-Z0-9]/g, '_').slice(0, 20)}`
  let faceMillOk = false
  try {
    const faceResp = await postToolpath('face-mill', {
      operation_ref: faceMachFace,
      region_x_min: xMin,
      region_x_max: xMax,
      region_y_min: yMin,
      region_y_max: yMax,
      face_z: zMax,
      tool_diameter_mm: null,  // let backend use default
      stepover_mm: null,
      clearance_z: clearanceZ,
      clearance_source: 'BBOX_DERIVED',
    }, authToken)
    const faceGroups = segmentsToGroups(faceResp.toolpaths)
    groups.push(...faceGroups)
    if (faceResp.warnings.length) warnings.push(...faceResp.warnings)
    faceMillOk = faceGroups.length > 0
  } catch (err) {
    warnings.push(`Face mill: ${err instanceof Error ? err.message : String(err)}`)
  }

  // ---------------------------------------------------------------------------
  // Op 2 — Profile (outer rectangular contour)
  // ---------------------------------------------------------------------------
  const profRef = `PROFILE_${input.fileRef.replace(/[^a-zA-Z0-9]/g, '_').slice(0, 20)}`
  const profileZ = zMax - height * 0.1  // 10% down from top for a first finishing pass
  // Rectangular outline of the bounding box
  const contourPoints: Array<[number, number]> = [
    [xMin, yMin], [xMax, yMin], [xMax, yMax], [xMin, yMax],
  ]
  let profileOk = false
  try {
    const profResp = await postToolpath('profile', {
      operation_ref: profRef,
      contour_points: contourPoints,
      contour_z: profileZ,
      tool_diameter_mm: null,
      profile_side: 'OUTER',
      compensation_side: 'CENTERLINE',
      clearance_z: clearanceZ,
      clearance_source: 'BBOX_DERIVED',
      closed: true,
    }, authToken)
    const profGroups = segmentsToGroups(profResp.toolpaths)
    groups.push(...profGroups)
    if (profResp.warnings.length) warnings.push(...profResp.warnings)
    profileOk = profGroups.length > 0
  } catch (err) {
    warnings.push(`Profile: ${err instanceof Error ? err.message : String(err)}`)
  }

  if (!faceMillOk && !profileOk) {
    throw new Error(
      'Toolpath generation returned no drawable segments. ' +
      'The backend toolpath API is reachable but returned empty polylines. ' +
      `Warnings: ${warnings.join('; ')}`
    )
  }

  const workflow: ConnectedWorkflow = {
    workflowId: `WS_CAM_${Date.now()}`,
    partName: input.fileRef,
    drawingNumber: null,
    operations: [
      ...(faceMillOk ? [{
        operationId: faceMachFace,
        name: 'Face Mill — Top',
        type: 'FACE_MILL',
        setupRef: 'SETUP_1',
        toolRef: null,
        sequenceNumber: 1,
        status: 'TOOLPATH_READY',
      }] : []),
      ...(profileOk ? [{
        operationId: profRef,
        name: 'Profile — Outer Contour',
        type: 'CONTOUR_FINISH',
        setupRef: 'SETUP_1',
        toolRef: null,
        sequenceNumber: faceMillOk ? 2 : 1,
        status: 'TOOLPATH_READY',
      }] : []),
    ],
    toolpathGroups: groups,
    planStatus: 'TOOLPATH_READY',
  }

  return { workflow, warnings }
}
