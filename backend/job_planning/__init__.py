"""
Level-17 CNC Job Planning & Machine Assignment.

ASSIGNMENT_IS_PROPOSED_ONLY: All assignment outputs are proposed recommendations only.
Human approval is mandatory before any machine is selected or any job is dispatched.
Missing capability data fails closed — UNKNOWN is never treated as eligible.
No CNC machine is ever commanded from this module.

Safety constants (all True):
  NO_AUTOMATIC_MACHINE_ASSIGNMENT
  NO_AUTOMATIC_JOB_DISPATCH
  NO_FABRICATED_CAPABILITY_DATA
  MISSING_DATA_FAILS_CLOSED
  ASSIGNMENT_IS_PROPOSED_ONLY
  HUMAN_APPROVAL_MANDATORY
  UNKNOWN_CAPABILITY_IS_NOT_ELIGIBLE
"""

from __future__ import annotations

from .assignment import plan_job_assignment
from .capability import (
    build_capability_profile_from_catalog,
    build_capability_profile_from_resource,
)
from .enums import (
    AssignmentStatus,
    CapabilityMatchLevel,
    MaterialCompatibilityResult,
    PlanningBlockReason,
    RankingObjective,
    SpindleMatchResult,
    WorkloadStatus,
)
from .explainability import explain_candidate, explain_recommendation
from .matching import (
    check_material_compatibility,
    check_process_capabilities,
    check_spindle_requirements,
)
from .models import (
    AssignmentCandidate,
    AssignmentRecommendation,
    CamOperationRequirements,
    CapabilityCheckResult,
    MachineCapabilityProfile,
    MaterialCompatibilityCheck,
    SpindleMatchCheck,
    WorkloadEstimate,
)
from .ranking import (
    compute_capability_score,
    compute_overall_score,
    material_compat_score,
    rank_candidates,
    spindle_match_score,
)
from .workload import estimate_workload, workload_score

# ---------------------------------------------------------------------------
# Safety constants — ALL True
# MUST NOT be set to False — these are architecture invariants
# ---------------------------------------------------------------------------

NO_AUTOMATIC_MACHINE_ASSIGNMENT: bool = True
NO_AUTOMATIC_JOB_DISPATCH: bool = True
NO_FABRICATED_CAPABILITY_DATA: bool = True
MISSING_DATA_FAILS_CLOSED: bool = True
ASSIGNMENT_IS_PROPOSED_ONLY: bool = True
HUMAN_APPROVAL_MANDATORY: bool = True
UNKNOWN_CAPABILITY_IS_NOT_ELIGIBLE: bool = True

__all__ = [
    # Main entry point
    "plan_job_assignment",
    # Capability builders
    "build_capability_profile_from_catalog",
    "build_capability_profile_from_resource",
    # Matching
    "check_material_compatibility",
    "check_process_capabilities",
    "check_spindle_requirements",
    # Ranking
    "compute_capability_score",
    "compute_overall_score",
    "material_compat_score",
    "spindle_match_score",
    "rank_candidates",
    # Workload
    "estimate_workload",
    "workload_score",
    # Explainability
    "explain_candidate",
    "explain_recommendation",
    # Enums
    "AssignmentStatus",
    "CapabilityMatchLevel",
    "MaterialCompatibilityResult",
    "PlanningBlockReason",
    "RankingObjective",
    "SpindleMatchResult",
    "WorkloadStatus",
    # Models
    "AssignmentCandidate",
    "AssignmentRecommendation",
    "CamOperationRequirements",
    "CapabilityCheckResult",
    "MachineCapabilityProfile",
    "MaterialCompatibilityCheck",
    "SpindleMatchCheck",
    "WorkloadEstimate",
    # Safety constants
    "NO_AUTOMATIC_MACHINE_ASSIGNMENT",
    "NO_AUTOMATIC_JOB_DISPATCH",
    "NO_FABRICATED_CAPABILITY_DATA",
    "MISSING_DATA_FAILS_CLOSED",
    "ASSIGNMENT_IS_PROPOSED_ONLY",
    "HUMAN_APPROVAL_MANDATORY",
    "UNKNOWN_CAPABILITY_IS_NOT_ELIGIBLE",
]
