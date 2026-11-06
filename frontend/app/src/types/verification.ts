/**
 * Level-11 Toolpath Verification and Simulation types.
 *
 * is_verified is ALWAYS derived — never set directly.
 * UNKNOWN / NOT_PERFORMED / INSUFFICIENT_DATA are NEVER treated as PASS.
 * COMPLETED simulation != VERIFIED toolpath.
 */

export type VerificationStatus =
  | 'NOT_PERFORMED'
  | 'INSUFFICIENT_DATA'
  | 'PASS'
  | 'FAIL'
  | 'PARTIAL'
  | 'ERROR';

export type VerificationCheckType =
  | 'TOOL_COLLISION'
  | 'HOLDER_COLLISION'
  | 'FIXTURE_COLLISION'
  | 'PART_GOUGE'
  | 'STOCK_GOUGE'
  | 'MACHINE_ENVELOPE'
  | 'AXIS_LIMIT'
  | 'TOOL_REACH'
  | 'RAPID_CLEARANCE'
  | 'STOCK_REMAINING'
  | 'OVERTRAVEL'
  | 'KINEMATIC_CHECK';

export type VerificationSeverity = 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';

export type VerificationState =
  | 'UNVERIFIED'
  | 'PARTIALLY_VERIFIED'
  | 'VERIFIED'
  | 'FAILED'
  | 'BLOCKED';

export type StockShape = 'BOX' | 'CYLINDER' | 'USER_DEFINED_MESH' | 'NEAR_NET_MESH' | 'UNKNOWN';
export type StockFidelity =
  | 'EXACT_MESH'
  | 'ANALYTIC_PRIMITIVE'
  | 'DISCRETIZED_APPROXIMATION'
  | 'UNKNOWN';
export type StockRemovalFidelity =
  | 'EXACT_BOOLEAN'
  | 'ANALYTIC'
  | 'VOXEL_APPROXIMATE'
  | 'UNKNOWN';

export type SimulationStatus =
  | 'NOT_STARTED'
  | 'RUNNING'
  | 'COMPLETED'
  | 'PARTIAL'
  | 'FAILED'
  | 'BLOCKED';

export type VerificationProfileEnum =
  | 'GEOMETRY_ONLY'
  | 'TOOL_AND_PART'
  | 'TOOL_HOLDER_PART'
  | 'FULL_SETUP'
  | 'FULL_MACHINE';

export type FixtureType =
  | 'VISE_JAWS'
  | 'CHUCK'
  | 'SOFT_JAWS'
  | 'FIXTURE_PLATE'
  | 'CUSTOM_FIXTURE_MESH'
  | 'CLAMPS'
  | 'UNKNOWN';

export type FixtureSource = 'USER_DEFINED' | 'VERIFIED_LIBRARY_RECORD' | 'IMPORTED_GEOMETRY';

export interface VerificationIssue {
  issue_id: string;
  check_type: VerificationCheckType;
  severity: VerificationSeverity;
  message: string;
  toolpath_id?: string;
  operation_id?: string;
  segment_id?: string;
  tool_id?: string;
  setup_id?: string;
  feature_id?: string;
  geometry_refs: string[];
  evidence: Record<string, unknown>;
}

export interface VerificationResult {
  check_type: VerificationCheckType;
  status: VerificationStatus;
  severity: VerificationSeverity;
  toolpath_refs: string[];
  segment_refs: string[];
  geometry_refs: string[];
  evidence: Record<string, unknown>;
  warnings: string[];
  errors: string[];
  issues: VerificationIssue[];
}

export interface VerificationSummary {
  verification_state: VerificationState;
  profile: VerificationProfileEnum;
  checks_performed: number;
  checks_passed: number;
  checks_failed: number;
  checks_not_performed: number;
  checks_insufficient_data: number;
  critical_issues: number;
  error_issues: number;
  warning_issues: number;
  info_issues: number;
  is_verified: boolean;
}

export interface VisualizationData {
  cutting_points: number[][];
  rapid_points: number[][];
  stock_bbox?: Record<string, number>;
  part_bbox?: Record<string, number>;
  fixture_bboxes: Record<string, number>[];
  collision_points: number[][];
  gouge_points: number[][];
  remaining_stock_note?: string;
}

export interface StockModel {
  shape: StockShape;
  fidelity: StockFidelity;
  min_x_mm?: number;
  min_y_mm?: number;
  min_z_mm?: number;
  max_x_mm?: number;
  max_y_mm?: number;
  max_z_mm?: number;
  radius_mm?: number;
  height_mm?: number;
  center_x_mm?: number;
  center_y_mm?: number;
  bottom_z_mm?: number;
}

export interface FixtureGeometry {
  fixture_id: string;
  fixture_type: FixtureType;
  source: FixtureSource;
  min_x_mm: number;
  min_y_mm: number;
  min_z_mm: number;
  max_x_mm: number;
  max_y_mm: number;
  max_z_mm: number;
}

export interface VerificationSegment {
  segment_id?: string;
  start_x: number;
  start_y: number;
  start_z: number;
  end_x: number;
  end_y: number;
  end_z: number;
  motion_type: string;
  is_cutting: boolean;
  operation_id?: string;
  tool_id?: string;
  setup_id?: string;
  feature_id?: string;
}

export interface SimulationRequest {
  toolpath_id: string;
  segments: VerificationSegment[];
  profile: VerificationProfileEnum;
  tool_diameter_mm?: number;
  tool_length_mm?: number;
  tool_flute_length_mm?: number;
  holder_diameter_mm?: number;
  holder_length_mm?: number;
  stock?: StockModel;
  fixtures?: FixtureGeometry[];
  machine_travel_x_mm?: number;
  machine_travel_y_mm?: number;
  machine_travel_z_mm?: number;
  part_bbox_min?: [number, number, number];
  part_bbox_max?: [number, number, number];
}

export interface SimulationResult {
  session_id: string;
  toolpath_id: string;
  simulation_status: SimulationStatus;
  verification_state: VerificationState;
  /** Always derived from verification_state — never set directly. */
  is_verified: boolean;
  profile: VerificationProfileEnum;
  checks: Record<string, VerificationResult>;
  issues: VerificationIssue[];
  summary?: VerificationSummary;
  initial_stock_volume_mm3?: number;
  remaining_stock_volume_mm3?: number;
  removed_volume_mm3?: number;
  stock_removal_fidelity: StockRemovalFidelity;
  visualization: VisualizationData;
  warnings: string[];
  errors: string[];
  resource_limit_hit: boolean;
}

/** Counts of verification checks by status for display. */
export interface VerificationCheckDisplay {
  pass: number;
  fail: number;
  not_performed: number;
  insufficient_data: number;
  partial: number;
}
