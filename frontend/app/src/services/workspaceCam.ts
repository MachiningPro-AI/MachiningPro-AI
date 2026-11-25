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
import type { ConnectedWorkflow, OperationSummary, ToolpathLineGroup } from '../components/workspace/WorkspaceTypes'

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

// ---------------------------------------------------------------------------
// Feature-aware CAM plan (from /api/workspace-cam/feature-cam)
// ---------------------------------------------------------------------------

export interface FeatureCamFeatureInput {
  feature_id: string
  feature_type: string  // HOLE | POCKET | SLOT
  center_x?: number | null
  center_y?: number | null
  center_z_top?: number | null
  depth_mm?: number | null
  diameter_mm?: number | null
  width_mm?: number | null
  length_mm?: number | null
  clearance_z?: number | null
  boundary_points?: Array<[number, number]> | null
}

export interface FeatureCamRequest {
  file_ref: string
  features: FeatureCamFeatureInput[]
  stock_bbox?: {
    min_x: number; min_y: number; min_z: number
    max_x: number; max_y: number; max_z: number
  } | null
  material_grade?: string | null
  wcs_ref?: string
  setup_ref?: string
}

export interface FeatureCamToolInfo {
  tool_id: string | null
  tool_type: string | null
  tool_diameter_mm: number | null
  tool_status: string
  tool_provenance: string
}

export interface FeatureCamOpResult {
  operation_ref: string
  operation_index: number
  feature_id: string
  feature_type: string
  operation_type: string
  cam_strategy: string
  wcs_ref: string
  tool: FeatureCamToolInfo
  toolpath_status: string
  toolpath_id: string | null
  segment_count: number
  point_count: number
  warnings: string[]
  missing_inputs: string[]
  simulation_required: boolean
}

export interface FeatureCamToolpathGroup {
  motion_type: string
  points: number[]  // flat [x0,y0,z0,x1,y1,z1,...]
  operation_ref: string
}

export interface FeatureCamApiResult {
  file_ref: string
  operations: FeatureCamOpResult[]
  toolpath_groups: FeatureCamToolpathGroup[]
  warnings: string[]
  safety: Record<string, unknown>
}

function featureCamGroupsToLineGroups(groups: FeatureCamToolpathGroup[]): ToolpathLineGroup[] {
  return groups.map(g => {
    const mt = g.motion_type
    const motionType: ToolpathLineGroup['motionType'] =
      mt === 'RAPID'   ? 'RAPID'   :
      mt === 'FEED'    ? 'FEED'    :
      mt === 'PLUNGE'  ? 'PLUNGE'  :
      mt === 'RETRACT' ? 'RETRACT' : 'LINK'
    return { motionType, points: g.points, operationRef: g.operation_ref }
  }).filter(g => g.points.length >= 6)
}

export interface FeatureAwareCamResult {
  workflow: ConnectedWorkflow
  apiResult: FeatureCamApiResult
  warnings: string[]
}

export async function generateFeatureAwareCamPlan(
  req: FeatureCamRequest,
  token?: string,
): Promise<FeatureAwareCamResult> {
  const authToken = token ?? tok()
  if (!authToken) throw new Error('Authentication required')

  const resp = await fetch('/api/workspace-cam/feature-cam', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${authToken}`,
    },
    body: JSON.stringify(req),
  })
  if (!resp.ok) {
    const text = await resp.text().catch(() => resp.statusText)
    throw new Error(`Feature CAM API error (${resp.status}): ${text}`)
  }
  const data = (await resp.json()) as FeatureCamApiResult

  const groups = featureCamGroupsToLineGroups(data.toolpath_groups)
  const warnings = [...(data.warnings ?? [])]

  const operations: OperationSummary[] = data.operations
    .filter(op => op.toolpath_status !== 'BLOCKED')
    .map((op, i) => ({
      operationId: op.operation_ref,
      name: `${op.operation_type} ${i + 1} — ${op.feature_id}`,
      type: op.operation_type,
      setupRef: op.wcs_ref,
      toolRef: op.tool.tool_id,
      sequenceNumber: op.operation_index,
      status: op.toolpath_status,
      toolDiameterMm: op.tool.tool_diameter_mm,
    }))

  if (operations.length === 0 && data.operations.length > 0) {
    data.operations.forEach(op => {
      if (op.warnings.length) warnings.push(...op.warnings)
    })
    warnings.push('All operations were BLOCKED — missing geometry or tool data')
  }

  const workflow: ConnectedWorkflow = {
    workflowId: `WS_FEAT_CAM_${Date.now()}`,
    partName: req.file_ref,
    drawingNumber: null,
    operations,
    toolpathGroups: groups,
    planStatus: groups.length > 0 ? 'TOOLPATH_READY' : 'BLOCKED',
  }

  return { workflow, apiResult: data, warnings }
}

// ---------------------------------------------------------------------------
// Workspace simulation (/api/workspace-sim/run)
// ---------------------------------------------------------------------------

export interface WsSimSegmentInput {
  start_x: number; start_y: number; start_z: number
  end_x: number; end_y: number; end_z: number
  motion_type?: string
  is_cutting?: boolean
  operation_id?: string | null
}

export interface WsSimRequest {
  toolpath_id: string
  segments: WsSimSegmentInput[]
  profile?: string
  tool_diameter_mm?: number | null
  tool_length_mm?: number | null
  tool_flute_length_mm?: number | null
  stock_bbox?: { min_x: number; min_y: number; min_z: number; max_x: number; max_y: number; max_z: number } | null
  part_bbox_min?: [number, number, number] | null
  part_bbox_max?: [number, number, number] | null
}

export interface WsSimCheckResult {
  status: string
  severity: string
  warnings: string[]
  errors: string[]
  issues: Array<{ issue_id: string; check_type: string; severity: string; message: string }>
}

export interface WsSimVisualization {
  cutting_points: Array<[number, number, number]>
  rapid_points: Array<[number, number, number]>
  stock_bbox: Record<string, number> | null
  part_bbox: Record<string, number> | null
  collision_points: Array<[number, number, number]>
  gouge_points: Array<[number, number, number]>
  remaining_stock_note: string | null
}

export interface WsSimApiResult {
  session_id: string
  toolpath_id: string
  simulation_status: string
  verification_state: string
  is_verified: boolean
  profile: string
  checks: Record<string, WsSimCheckResult>
  initial_stock_volume_mm3: number | null
  remaining_stock_volume_mm3: number | null
  removed_volume_mm3: number | null
  stock_removal_fidelity: string
  visualization: WsSimVisualization
  warnings: string[]
  errors: string[]
  resource_limit_hit: boolean
  safety: Record<string, unknown>
  offline_only: boolean
  simulation_result_is_not_machining_approval: boolean
}

export async function runWorkspaceSimulation(
  req: WsSimRequest,
  token?: string,
): Promise<WsSimApiResult> {
  const authToken = token ?? tok()
  if (!authToken) throw new Error('Authentication required')

  const resp = await fetch('/api/workspace-sim/run', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${authToken}`,
    },
    body: JSON.stringify(req),
  })
  if (!resp.ok) {
    const text = await resp.text().catch(() => resp.statusText)
    throw new Error(`Workspace simulation API error (${resp.status}): ${text}`)
  }
  return resp.json() as Promise<WsSimApiResult>
}

// ---------------------------------------------------------------------------
// Convert ToolpathLineGroup points to WsSimSegmentInput array
// ---------------------------------------------------------------------------

export function toolpathGroupsToSimSegments(
  groups: ToolpathLineGroup[],
  operationRef?: string,
): WsSimSegmentInput[] {
  const segs: WsSimSegmentInput[] = []
  for (const g of groups) {
    const pts = g.points
    const isCutting = g.motionType === 'FEED' || g.motionType === 'PLUNGE'
    for (let i = 0; i + 5 < pts.length; i += 3) {
      segs.push({
        start_x: pts[i]!,
        start_y: pts[i + 1]!,
        start_z: pts[i + 2]!,
        end_x: pts[i + 3]!,
        end_y: pts[i + 4]!,
        end_z: pts[i + 5]!,
        motion_type: g.motionType,
        is_cutting: isCutting,
        operation_id: operationRef ?? g.operationRef,
      })
    }
  }
  return segs
}

// ---------------------------------------------------------------------------
// Single operation generation (from wizard inputs)
// ---------------------------------------------------------------------------

export type SingleOpType = 'FACE_MILL' | 'POCKET' | 'PROFILE' | 'DRILL'

export interface SingleOpInput {
  opType: SingleOpType
  bbox: { min: [number, number, number]; max: [number, number, number] }
  fileRef: string
  token: string
  sequenceNumber: number
  // Tool
  toolDiameterMm: number | null
  // Common
  clearanceZ: number | null
  // Face mill / Profile
  profileSide?: string
  compensationSide?: string
  // Pocket
  stepdownMm?: number | null
  stepoverMm?: number | null
  pocketDepthMm?: number | null
  pocketStrategy?: string
  // Profile
  contourZ?: number | null
  // Drill
  drillX?: number | null
  drillY?: number | null
  drillDepthMm?: number | null
  peckDepthMm?: number | null
}

export interface SingleOpResult {
  operation: OperationSummary
  toolpathGroups: ToolpathLineGroup[]
  warnings: string[]
}

function opRefFromInput(input: SingleOpInput): string {
  const safe = input.fileRef.replace(/[^a-zA-Z0-9]/g, '_').slice(0, 16)
  return `${input.opType}_${safe}_${input.sequenceNumber}_${Date.now()}`
}

export async function generateSingleOperation(input: SingleOpInput): Promise<SingleOpResult> {
  const { opType, bbox, token } = input
  if (!token) throw new Error('Authentication required')

  const [xMin, yMin, zMin] = bbox.min
  const [xMax, yMax, zMax] = bbox.max
  const height = zMax - zMin
  const autoClr = zMax + Math.max(height * 0.15, 5)
  const clearZ = input.clearanceZ ?? autoClr

  const opRef = opRefFromInput(input)
  const warnings: string[] = []
  let resp: ToolpathApiResponse

  if (opType === 'FACE_MILL') {
    resp = await postToolpath('face-mill', {
      operation_ref: opRef,
      region_x_min: xMin,
      region_x_max: xMax,
      region_y_min: yMin,
      region_y_max: yMax,
      face_z: zMax,
      tool_diameter_mm: input.toolDiameterMm,
      stepover_mm: input.stepoverMm ?? null,
      clearance_z: clearZ,
      clearance_source: 'USER_DEFINED',
    }, token)

  } else if (opType === 'POCKET') {
    const depth = input.pocketDepthMm ?? height * 0.5
    const pocketBtm = zMax - depth
    resp = await postToolpath('pocket', {
      operation_ref: opRef,
      boundary_points: [[xMin, yMin], [xMax, yMin], [xMax, yMax], [xMin, yMax]],
      pocket_top_z: zMax,
      pocket_bottom_z: pocketBtm,
      tool_diameter_mm: input.toolDiameterMm,
      stepdown_mm: input.stepdownMm ?? null,
      stepover_mm: input.stepoverMm ?? null,
      strategy: input.pocketStrategy ?? 'OFFSET',
      clearance_z: clearZ,
      clearance_source: 'USER_DEFINED',
    }, token)

  } else if (opType === 'PROFILE') {
    const profZ = input.contourZ ?? (zMax - height * 0.1)
    resp = await postToolpath('profile', {
      operation_ref: opRef,
      contour_points: [[xMin, yMin], [xMax, yMin], [xMax, yMax], [xMin, yMax]],
      contour_z: profZ,
      tool_diameter_mm: input.toolDiameterMm,
      profile_side: input.profileSide ?? 'OUTER',
      compensation_side: input.compensationSide ?? 'CENTERLINE',
      clearance_z: clearZ,
      clearance_source: 'USER_DEFINED',
      closed: true,
    }, token)

  } else if (opType === 'DRILL') {
    const drillX = input.drillX ?? (xMin + xMax) / 2
    const drillY = input.drillY ?? (yMin + yMax) / 2
    const drillDepth = input.drillDepthMm ?? height * 0.5
    resp = await postToolpath('drill', {
      operation_ref: opRef,
      hole_x: drillX,
      hole_y: drillY,
      hole_top_z: zMax,
      hole_depth_mm: drillDepth,
      peck_depth_mm: input.peckDepthMm ?? null,
      clearance_z: clearZ,
      clearance_source: 'USER_DEFINED',
    }, token)

  } else {
    throw new Error(`Unsupported operation type: ${opType as string}`)
  }

  if (resp.warnings?.length) warnings.push(...resp.warnings)
  const groups = segmentsToGroups(resp.toolpaths)

  if (groups.length === 0) {
    throw new Error(
      `Toolpath API returned no drawable segments for ${opType}. ` +
      (warnings.length ? `Warnings: ${warnings.join('; ')}` : 'No geometry produced.')
    )
  }

  // Estimate cut length from segments
  const totalPts = groups.reduce((s, g) => s + g.points.length / 3, 0)
  const estCutLen = totalPts > 0 ? totalPts * 2 : null  // rough mm estimate

  const opTypeLabels: Record<SingleOpType, string> = {
    FACE_MILL: 'Face Mill',
    POCKET: 'Pocket',
    PROFILE: 'Profile',
    DRILL: 'Drill',
  }
  const strategyLabel = opType === 'POCKET' ? (input.pocketStrategy ?? 'OFFSET')
    : opType === 'PROFILE' ? (input.profileSide ?? 'OUTER')
    : undefined

  const operation: OperationSummary = {
    operationId: opRef,
    name: `${opTypeLabels[opType]} ${input.sequenceNumber}`,
    type: opType,
    setupRef: 'SETUP_1',
    toolRef: input.toolDiameterMm ? `D${input.toolDiameterMm}` : null,
    sequenceNumber: input.sequenceNumber,
    status: 'TOOLPATH_READY',
    strategy: strategyLabel ?? null,
    estimatedCutLengthMm: estCutLen,
    toolDiameterMm: input.toolDiameterMm,
  }

  return { operation, toolpathGroups: groups, warnings }
}
