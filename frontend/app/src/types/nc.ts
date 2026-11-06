/**
 * Level-12 NC Postprocessor and Safe G-code — TypeScript types.
 *
 * is_dispatchable is always false — this is an OFFLINE CANDIDATE only.
 * DO NOT add READY_TO_RUN or MACHINE_APPROVED to NCProgramStatus.
 */

export type NCProgramStatus =
  | "NOT_GENERATED"
  | "BLOCKED"
  | "CANDIDATE"
  | "VALIDATED_OFFLINE"
  | "REVIEW_REQUIRED"
  | "REJECTED"
  | "STALE";
// NOT_PRESENT: READY_TO_RUN | MACHINE_APPROVED

export type NCMotionType =
  | "RAPID_LINEAR"
  | "FEED_LINEAR"
  | "ARC_CW"
  | "ARC_CCW"
  | "HELIX"
  | "SIMPLE_DRILL_CYCLE"
  | "PECK_DRILL_CYCLE"
  | "DWELL";

export type NCUnitMode = "MM" | "INCH" | "UNKNOWN";
export type NCCoordinateMode = "ABSOLUTE" | "INCREMENTAL" | "UNKNOWN";
export type NCPlane = "XY" | "XZ" | "YZ" | "UNKNOWN";
export type NCFeedMode = "FEED_PER_MINUTE" | "FEED_PER_REV" | "UNKNOWN";
export type NCSpindleDirection = "CW" | "CCW" | "OFF";
export type NCCoolantMode = "OFF" | "FLOOD" | "MIST" | "THROUGH_TOOL" | "UNKNOWN";
export type NCCutterCompMode = "OFF" | "LEFT" | "RIGHT" | "COMPUTER_COMPENSATED";
export type ArcMode = "CENTER_OFFSET" | "RADIUS";
export type WorkOffsetRef =
  | "WORK_OFFSET_1"
  | "WORK_OFFSET_2"
  | "WORK_OFFSET_3"
  | "WORK_OFFSET_4"
  | "WORK_OFFSET_5"
  | "WORK_OFFSET_6"
  | "CUSTOM"
  | "UNKNOWN";

export type PostCertificationStatus =
  | "TEST_ONLY"
  | "UNVERIFIED_MACHINE_PROFILE"
  | "VERIFIED_PROFILE"
  | "CERTIFIED_PROFILE";

export type NCGenerationBlockReason =
  | "UNVERIFIED_TOOLPATH"
  | "PARTIAL_VERIFICATION"
  | "FAILED_VERIFICATION"
  | "BLOCKED_VERIFICATION"
  | "MISSING_POST_PROFILE"
  | "MISSING_TOOL_NUMBER"
  | "MISSING_FEED"
  | "MISSING_SPINDLE_SPEED"
  | "UNSUPPORTED_MOTION"
  | "INVALID_ARC"
  | "UNKNOWN_UNITS"
  | "UNKNOWN_WORK_OFFSET";

export type NCStaleReason =
  | "TOOLPATH_CHANGED"
  | "PROFILE_CHANGED"
  | "MACHINE_CHANGED"
  | "VERIFICATION_CHANGED";

// -------------------------------------------------------------------------
// NC IR types
// -------------------------------------------------------------------------

export interface NCSourceTrace {
  toolpath_id: string | null;
  segment_id: string | null;
  operation_id: string | null;
  setup_id: string | null;
  tool_id: string | null;
  feature_id: string | null;
}

export interface NCBlockElement {
  kind: string;
  data: Record<string, unknown>;
}

export interface NCBlock {
  block_id: string;
  elements: NCBlockElement[];
  sequence_number: number | null;
  comment: string | null;
  source: NCSourceTrace;
}

export interface NCProgram {
  program_id: string;
  program_number: string;
  unit_mode: NCUnitMode;
  coordinate_mode: NCCoordinateMode;
  blocks: NCBlock[];
  toolpath_id: string | null;
  verification_session_id: string | null;
  post_profile_id: string;
  source_toolpath_hash: string;
  source_verification_hash: string;
  /** Always false at Level 12 — never dispatchable. */
  is_dispatchable: false;
  is_offline_candidate: true;
  safety_warnings: string[];
  generation_warnings: string[];
  block_count: number;
}

// -------------------------------------------------------------------------
// Postprocessor types
// -------------------------------------------------------------------------

export interface PostProcessorProfileSummary {
  profile_id: string;
  profile_name: string;
  dialect: string;
  certification_status: PostCertificationStatus;
  not_machine_certified: boolean;
  not_dispatchable: boolean;
}

// -------------------------------------------------------------------------
// Manifest
// -------------------------------------------------------------------------

export interface NCGenerationManifest {
  manifest_id: string;
  source_cad_ref: string | null;
  cam_plan_ref: string | null;
  toolpath_id: string | null;
  verification_session_id: string | null;
  verification_state: string;
  verification_profile: string;
  post_profile_id: string;
  post_profile_name: string;
  post_profile_certification: string;
  program_id: string;
  program_number: string;
  program_status: NCProgramStatus;
  /** SHA-256 hash of program block content — detects modification, not machine safety. */
  program_hash: string;
  generated_at: string;
  generation_warnings: string[];
  validation_warnings: string[];
  is_offline_candidate: true;
  is_dispatchable: false;
  safety_statement: string;
  is_stale: boolean;
  stale_reasons: string[];
}

// -------------------------------------------------------------------------
// API request / response types
// -------------------------------------------------------------------------

export interface NCSegmentInput {
  segment_id: string;
  motion_type: string;
  start_x?: number;
  start_y?: number;
  start_z?: number;
  end_x?: number;
  end_y?: number;
  end_z?: number;
  arc_center?: [number, number, number];
  arc_radius?: number;
  is_cutting: boolean;
  operation_id?: string;
  tool_id?: string;
  setup_id?: string;
  feature_id?: string;
}

export interface NCBuildRequest {
  toolpath_id: string;
  verification_state: string;
  verification_session_id?: string;
  profile_id?: string;
  segments: NCSegmentInput[];
  tool_id?: string;
  tool_number?: number;
  tool_diameter_mm?: number;
  spindle_speed_rpm?: number;
  spindle_direction?: NCSpindleDirection;
  feed_mmpm?: number;
  work_offset?: WorkOffsetRef;
  unit_mode?: NCUnitMode;
  plane?: NCPlane;
  coordinate_mode?: NCCoordinateMode;
  coolant_mode?: NCCoolantMode;
  cutter_comp?: NCCutterCompMode;
  program_number?: string;
  source_toolpath_hash?: string;
  source_verification_hash?: string;
}

export interface NCBuildResponse {
  status: NCProgramStatus;
  block_reasons: NCGenerationBlockReason[];
  warnings: string[];
  errors: string[];
  program_id: string | null;
  program_number: string | null;
  block_count: number;
  /** Always false. */
  is_dispatchable: false;
  is_offline_candidate: true;
  safety_warnings: string[];
  manifest: NCGenerationManifest | null;
}

export interface NCValidateResponse {
  status: NCProgramStatus;
  is_valid: boolean;
  error_count: number;
  warning_count: number;
  errors: string[];
  warnings_list: string[];
}
