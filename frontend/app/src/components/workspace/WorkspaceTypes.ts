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

// ---------------------------------------------------------------------------
// Tool pose for animation (real toolpath coordinates only)
// ---------------------------------------------------------------------------

export interface ToolPose {
  x: number
  y: number
  z: number
}

// ---------------------------------------------------------------------------
// Stock bounding box (real dimensions only)
// ---------------------------------------------------------------------------

export interface StockBbox {
  minX: number
  minY: number
  minZ: number
  maxX: number
  maxY: number
  maxZ: number
  confirmed: boolean  // USER_CONFIRMED vs SUGGESTED
}

// ---------------------------------------------------------------------------
// Simulation state (driven by /api/verification/simulate results only)
// ---------------------------------------------------------------------------

export type SimulationRunStatus = 'NOT_PERFORMED' | 'RUNNING' | 'COMPLETED' | 'FAILED'

export interface SimCheckResult {
  status: string         // PASS | FAIL | NOT_PERFORMED | INSUFFICIENT_DATA
  severity: string       // NONE | INFO | WARNING | ERROR | CRITICAL
  warnings: string[]
}

export interface SimulationState {
  runStatus: SimulationRunStatus
  toolpathId: string | null
  verificationState: string
  checks: Record<string, SimCheckResult>
  initialStockVolumeMm3: number | null
  remainingStockVolumeMm3: number | null
  removedVolumeMm3: number | null
  stockRemovalFidelity: string
  collisionPoints: Array<[number, number, number]>
  gougePoints: Array<[number, number, number]>
  errorMessage: string | null
}

export const DEFAULT_SIMULATION_STATE: SimulationState = {
  runStatus: 'NOT_PERFORMED',
  toolpathId: null,
  verificationState: 'NOT_PERFORMED',
  checks: {},
  initialStockVolumeMm3: null,
  remainingStockVolumeMm3: null,
  removedVolumeMm3: null,
  stockRemovalFidelity: 'UNKNOWN',
  collisionPoints: [],
  gougePoints: [],
  errorMessage: null,
}

// ---------------------------------------------------------------------------
// Animation state (toolpath playback — real frames only)
// ---------------------------------------------------------------------------

export type AnimSpeed = 0.25 | 0.5 | 1 | 2 | 5 | 10
export const ANIM_SPEEDS: AnimSpeed[] = [0.25, 0.5, 1, 2, 5, 10]

export interface AnimationState {
  frames: Array<[number, number, number]>
  currentFrame: number
  playing: boolean
  speed: AnimSpeed
}

// ---------------------------------------------------------------------------
// Background presets (viewer appearance — NEVER stored in engineering data)
// HARD RULE 7: layout/appearance must remain separated from manufacturing records
// ---------------------------------------------------------------------------

export type BgPresetId =
  | 'dark_eng'
  | 'neutral_gray'
  | 'light_eng'
  | 'gradient_dark'
  | 'gradient_light'

export interface BackgroundPreset {
  id:            BgPresetId
  label:         string
  color:         number    // Three.js hex integer (scene.background)
  isDark:        boolean   // used to pick overlay contrast colours — MUST 18
  gridColor1:    number
  gridColor2:    number
  axisCanvasBg:  string    // CSS rgba for axis triad overlay
  axisTextColor: string    // CSS colour for axis triad labels
}

export const BACKGROUND_PRESETS: BackgroundPreset[] = [
  { id: 'dark_eng',       label: 'Dark Engineering',  color: 0x0d1117, isDark: true,  gridColor1: 0x1e2a38, gridColor2: 0x2a3a4a, axisCanvasBg: 'rgba(13,17,23,0.72)',   axisTextColor: '#e0e8f0' },
  { id: 'neutral_gray',   label: 'Neutral Gray',       color: 0x1a1f2e, isDark: true,  gridColor1: 0x252d3a, gridColor2: 0x303b4a, axisCanvasBg: 'rgba(26,31,46,0.72)',   axisTextColor: '#d0d8e8' },
  { id: 'light_eng',      label: 'Light Engineering',  color: 0xd8e0e8, isDark: false, gridColor1: 0xa8b4c0, gridColor2: 0xb8c4d0, axisCanvasBg: 'rgba(216,224,232,0.72)', axisTextColor: '#1a2030' },
  { id: 'gradient_dark',  label: 'Gradient Dark',      color: 0x111827, isDark: true,  gridColor1: 0x1f2b3a, gridColor2: 0x2a3848, axisCanvasBg: 'rgba(17,24,39,0.72)',   axisTextColor: '#dce8f4' },
  { id: 'gradient_light', label: 'Gradient Light',     color: 0xe8ecf2, isDark: false, gridColor1: 0xbcc4d0, gridColor2: 0xc8d0dc, axisCanvasBg: 'rgba(232,236,242,0.72)', axisTextColor: '#141e2e' },
]

export const DEFAULT_BG_PRESET: BackgroundPreset = BACKGROUND_PRESETS[0]!

// ---------------------------------------------------------------------------
// Part opacity (viewer — not engineering data)
// ---------------------------------------------------------------------------

export type PartOpacityPreset = 1 | 0.75 | 0.5 | 0.25
export const PART_OPACITY_PRESETS: PartOpacityPreset[] = [1, 0.75, 0.5, 0.25]

// ---------------------------------------------------------------------------
// Workspace layout
//
// UI preferences only — NEVER stored in manufacturing engineering records.
// HARD RULE 7: WorkspaceLayout must remain separated from engineering state.
// HARD RULE 8: use deterministic flex system, not arbitrary CSS positions.
// ---------------------------------------------------------------------------

export type LayoutPresetId =
  | 'MODEL' | 'DRAWING' | 'MANUFACTURING'
  | 'CAM'   | 'SIMULATION' | 'INSPECTION'

export interface WorkspaceLayout {
  leftWidth:        number          // px — Model Tree width
  rightWidth:       number          // px — Properties width
  bottomHeight:     number          // px — CAM panel height
  showModelTree:    boolean
  showProperties:   boolean
  showCamPanel:     boolean
  showStatusBar:    boolean
  collapsedLeft:    boolean
  collapsedRight:   boolean
  collapsedBottom:  boolean
  viewerMaximized:  boolean
  activePreset:     LayoutPresetId
  bgPresetId:       BgPresetId
  customBgColor:    string | null   // null = use bgPresetId
  partOpacity:      PartOpacityPreset
  savedVersion:     number
}

export const MIN_PANEL_WIDTH    = 160
export const MAX_PANEL_WIDTH    = 600
export const MIN_BOTTOM_HEIGHT  = 100
export const MAX_BOTTOM_HEIGHT  = 480
export const COLLAPSED_STRIP_W  = 32   // collapsed left/right strip width  (px)
export const COLLAPSED_STRIP_H  = 32   // collapsed bottom strip height (px)

export const DEFAULT_LAYOUT: WorkspaceLayout = {
  leftWidth:       260,
  rightWidth:      260,
  bottomHeight:    220,
  showModelTree:   true,
  showProperties:  true,
  showCamPanel:    true,
  showStatusBar:   true,
  collapsedLeft:   false,
  collapsedRight:  false,
  collapsedBottom: false,
  viewerMaximized: false,
  activePreset:    'MODEL',
  bgPresetId:      'dark_eng',
  customBgColor:   null,
  partOpacity:     1,
  savedVersion:    1,
}

// Layout presets — only affect panel visibility/size, never engineering data
export const LAYOUT_PRESETS: Record<LayoutPresetId, Partial<WorkspaceLayout>> = {
  MODEL: {
    showModelTree: true,  showProperties: true,  showCamPanel: false, showStatusBar: true,
    collapsedLeft: false, collapsedRight: false, collapsedBottom: false,
    leftWidth: 280, rightWidth: 260, bottomHeight: 220,
  },
  DRAWING: {
    showModelTree: true,  showProperties: true,  showCamPanel: false, showStatusBar: true,
    collapsedLeft: false, collapsedRight: false, collapsedBottom: false,
    leftWidth: 240, rightWidth: 240,
  },
  MANUFACTURING: {
    showModelTree: true,  showProperties: true,  showCamPanel: true,  showStatusBar: true,
    collapsedLeft: false, collapsedRight: false, collapsedBottom: false,
    leftWidth: 260, rightWidth: 260, bottomHeight: 280,
  },
  CAM: {
    showModelTree: true,  showProperties: false, showCamPanel: true,  showStatusBar: true,
    collapsedLeft: false, collapsedRight: true,  collapsedBottom: false,
    leftWidth: 260, bottomHeight: 320,
  },
  SIMULATION: {
    showModelTree: false, showProperties: true,  showCamPanel: true,  showStatusBar: true,
    collapsedLeft: true,  collapsedRight: false, collapsedBottom: false,
    rightWidth: 300, bottomHeight: 320,
  },
  INSPECTION: {
    showModelTree: true,  showProperties: true,  showCamPanel: true,  showStatusBar: true,
    collapsedLeft: false, collapsedRight: false, collapsedBottom: false,
    leftWidth: 240, rightWidth: 320, bottomHeight: 260,
  },
}

const _LAYOUT_STORAGE_KEY = 'machiningpro-workspace-layout'

export function saveWorkspaceLayout(layout: WorkspaceLayout): void {
  try { localStorage.setItem(_LAYOUT_STORAGE_KEY, JSON.stringify(layout)) } catch { /* storage unavailable */ }
}

export function loadWorkspaceLayout(): WorkspaceLayout {
  try {
    const raw = localStorage.getItem(_LAYOUT_STORAGE_KEY)
    if (!raw) return { ...DEFAULT_LAYOUT }
    const p = JSON.parse(raw) as Partial<WorkspaceLayout>
    // Validate numeric fields — MUST 8: reject off-screen / invalid values
    const lw = typeof p.leftWidth    === 'number' && p.leftWidth    >= MIN_PANEL_WIDTH   && p.leftWidth    <= MAX_PANEL_WIDTH   ? p.leftWidth    : DEFAULT_LAYOUT.leftWidth
    const rw = typeof p.rightWidth   === 'number' && p.rightWidth   >= MIN_PANEL_WIDTH   && p.rightWidth   <= MAX_PANEL_WIDTH   ? p.rightWidth   : DEFAULT_LAYOUT.rightWidth
    const bh = typeof p.bottomHeight === 'number' && p.bottomHeight >= MIN_BOTTOM_HEIGHT && p.bottomHeight <= MAX_BOTTOM_HEIGHT ? p.bottomHeight : DEFAULT_LAYOUT.bottomHeight
    return { ...DEFAULT_LAYOUT, ...p, leftWidth: lw, rightWidth: rw, bottomHeight: bh }
  } catch {
    return { ...DEFAULT_LAYOUT }  // MUST 8: safe recovery from corrupt/incompatible storage
  }
}
