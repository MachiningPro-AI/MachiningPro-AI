/**
 * Shared types for the CAD/CAM Workspace.
 *
 * Safety contract (enforced at component layer):
 *   is_dispatchable=false       — never set true
 *   production_released=false   — never set true
 *   verificationState=NOT_PERFORMED  — collision/gouge/fixture all NOT_PERFORMED
 *   simulationState=NOT_PERFORMED    — no fabricated sim results
 *   NO_MACHINE_WRITE=YES        — workspace has no machine write controls
 *   NO_DISPATCH=YES             — no CNC dispatch from this workspace
 */

import type { PreviewMesh } from '../../services/engineeringImport'

// ---------------------------------------------------------------------------
// Display & rendering
// ---------------------------------------------------------------------------

export type DisplayMode = 'shaded' | 'wireframe' | 'shaded_edges' | 'hidden_line' | 'points'

export type ViewPreset = 'iso' | 'top' | 'front' | 'right' | 'left' | 'back' | 'bottom'

export type MotionTypeColor =
  | 'RAPID'    // amber
  | 'FEED'     // cyan
  | 'PLUNGE'   // red-orange
  | 'RETRACT'  // orange
  | 'LINK'     // gray

// ---------------------------------------------------------------------------
// File
// ---------------------------------------------------------------------------

export type FileFormat =
  | 'STL' | 'OBJ' | '3MF'
  | 'STEP' | 'IGES'
  | 'DXF' | 'PDF'
  | 'IMAGE' | 'UNKNOWN'

export interface WorkspaceFile {
  file: File
  name: string
  format: FileFormat
  sizeBytes: number
  loadedAt: Date
}

export function detectFormat(filename: string): FileFormat {
  const ext = filename.split('.').pop()?.toLowerCase() ?? ''
  const map: Record<string, FileFormat> = {
    stl: 'STL', obj: 'OBJ', '3mf': '3MF',
    step: 'STEP', stp: 'STEP', iges: 'IGES', igs: 'IGES',
    dxf: 'DXF', pdf: 'PDF',
    png: 'IMAGE', jpg: 'IMAGE', jpeg: 'IMAGE', bmp: 'IMAGE',
  }
  return map[ext] ?? 'UNKNOWN'
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

// Local-rendered formats (no backend round-trip needed)
export const CLIENT_RENDER_FORMATS: FileFormat[] = ['STL', 'OBJ', '3MF']

// Formats needing backend tessellation
export const SERVER_RENDER_FORMATS: FileFormat[] = ['STEP', 'IGES']

// ---------------------------------------------------------------------------
// Model tree
// ---------------------------------------------------------------------------

export type TreeNodeType =
  | 'root' | 'body' | 'face' | 'edge'
  | 'feature' | 'hole' | 'pocket' | 'slot' | 'step' | 'shoulder'
  | 'setup' | 'operation' | 'toolpath'
  | 'wcs' | 'stock' | 'fixture'
  | 'constraint'

export interface TreeNode {
  id: string
  label: string
  type: TreeNodeType
  children: TreeNode[]
  data?: Record<string, unknown>
  visible: boolean
  expanded: boolean
  badge?: string
}

// ---------------------------------------------------------------------------
// Toolpath visualization (real data only — HARD RULE: no fabricated points)
// ---------------------------------------------------------------------------

export interface ToolpathLineGroup {
  motionType: MotionTypeColor
  points: number[]  // flat [x0,y0,z0, x1,y1,z1, ...] from API VisualizationData
  operationRef: string
}

// ---------------------------------------------------------------------------
// Safety invariants (typed constants — never reassigned)
// ---------------------------------------------------------------------------

export const SAFETY = {
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
// Mesh state from backend
// ---------------------------------------------------------------------------

export interface MeshState {
  mesh: PreviewMesh
  loadedAt: Date
}

// ---------------------------------------------------------------------------
// Operation summary (from manufacturing plan — real data only)
// ---------------------------------------------------------------------------

export interface OperationSummary {
  operationId: string
  name: string
  type: string
  setupRef: string | null
  toolRef: string | null
  sequenceNumber: number
  status: string
}

// ---------------------------------------------------------------------------
// Workflow connection state
// ---------------------------------------------------------------------------

export type WorkflowConnState = 'idle' | 'loading' | 'connected' | 'error'

export interface ConnectedWorkflow {
  workflowId: string
  partName: string | null
  drawingNumber: string | null
  operations: OperationSummary[]
  toolpathGroups: ToolpathLineGroup[]
  planStatus: string | null
}
