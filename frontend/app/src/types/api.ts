// MachiningPro AI API Types — derived from backend/app.py contracts

export interface LoginRequest { username: string; password: string }
export interface LoginResponse { token: string; display_name: string; role: string; expires_in: number }
export interface HealthResponse { status: string; version: string; database_ok: boolean; server_time: string }




export interface SystemInfo {
  status: string; version: string; database_ok: boolean; database_size_kb: number
  total_users: number; active_users: number; calculation_count: number
  audit_count: number; schema_version: number; server_time: string
}

export type UserRole = 'admin' | 'engineer' | 'viewer'
export interface AuthUser { id: number; username: string; display_name: string; role: UserRole; is_active: number }
export type FeatureStatus = 'ready' | 'beta' | 'planned'
export type EngineeringStatus = 'validated' | 'calculated' | 'warning' | 'error' | 'draft' | 'review' | 'ai_assisted'

// ---------------------------------------------------------------------------
// Level-9 CAM Planning Types (candidate-only; NO G-code)
// ---------------------------------------------------------------------------

export type CAMJobStatus =
  | 'DRAFT' | 'INCOMPLETE' | 'READY_FOR_CAM_PLANNING'
  | 'CAM_PLAN_CREATED' | 'SIMULATION_REQUIRED' | 'BLOCKED'

export type CAMPlanStatus =
  | 'INCOMPLETE' | 'CANDIDATE' | 'ENGINEERING_REVIEW_REQUIRED'
  | 'READY_FOR_TOOLPATH_GENERATION' | 'BLOCKED'

export type StockType =
  | 'BAR' | 'BLOCK' | 'PLATE' | 'CASTING' | 'FORGING'
  | 'NEAR_NET_SHAPE' | 'USER_DEFINED' | 'UNKNOWN'

export type StockSource = 'USER_DEFINED' | 'CAD_STOCK_MODEL' | 'VERIFIED_EXTERNAL_DATA' | 'UNKNOWN'

export type CAMOperationType =
  | 'FACE_MILL' | 'ADAPTIVE_ROUGH' | 'POCKET_ROUGH' | 'POCKET_FINISH'
  | 'CONTOUR_ROUGH' | 'CONTOUR_FINISH' | 'SLOT_MILL' | 'DRILL' | 'PECK_DRILL'
  | 'REAM' | 'BORE' | 'TAP' | 'THREAD_MILL' | 'COUNTERBORE' | 'COUNTERSINK'
  | 'CHAMFER' | 'BALL_END_FINISH' | 'REST_MACHINING'
  | 'TURN_ROUGH' | 'TURN_FINISH' | 'FACE_TURN' | 'GROOVE' | 'PART_OFF'

export type OperationPhase = 'ROUGHING' | 'SEMI_FINISH' | 'FINISH'

export type ToolFamilyRequirement =
  | 'FACE_MILL_CUTTER' | 'SOLID_CARBIDE_END_MILL' | 'INDEXABLE_END_MILL'
  | 'DRILL_BIT' | 'REAMER' | 'BORING_BAR' | 'THREADING_TAP' | 'THREAD_MILL_CUTTER'
  | 'TURNING_INSERT' | 'GROOVING_INSERT' | 'PARTING_INSERT' | 'UNKNOWN'

export type SimulationCheck =
  | 'TOOL_COLLISION' | 'HOLDER_COLLISION' | 'FIXTURE_COLLISION'
  | 'MACHINE_COLLISION' | 'TRAVEL_LIMITS' | 'GOUGING' | 'REMAINING_STOCK'

export interface CamFeatureInput {
  feature_id: string
  feature_type: string
  is_confirmed?: boolean
  has_tolerance_evidence?: boolean
  depth_diameter_ratio?: number | null
}

export interface CamPlanRequest {
  part_id?: string | null
  cad_reference?: string | null
  material?: string | null
  machine_type?: string | null
  machine_requirement_refs?: string[]
  features?: CamFeatureInput[]
  cutting_data_refs?: string[]
  is_2d_only?: boolean
  stock_type?: StockType
  stock_source?: StockSource
  access_directions?: string[]
}

export interface CamReadinessSummary {
  is_ready: boolean
  cam_plan_status: CAMPlanStatus
  job_status: CAMJobStatus
  blockers: string[]
  warnings: string[]
  missing_inputs: string[]
}

export interface CamPlanResponse {
  job_id: string
  status: CAMJobStatus
  cam_plan_status: CAMPlanStatus
  operation_count: number
  setup_count: number
  simulation_required: true  // always true — Level-9 invariant
  warnings: string[]
  missing_inputs: string[]
  readiness: CamReadinessSummary
  cam_job: Record<string, unknown>
}
