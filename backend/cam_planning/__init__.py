"""CAM Planning — Level-9 Automatic CAM Planning package.

Provides neutral, candidate-based CAM job models, feature-to-CAM mapping,
deterministic operation ordering, and CAM readiness evaluation.

Safety contract
---------------
NO_GCODE=YES             — this package never produces G-code.
NO_NC_CODE=YES           — this package never produces NC programs.
NO_FABRICATED_DATA=YES   — no synthetic coordinates, no assumed stock,
                           no assumed WCS, no assumed fixtures.
CANDIDATE_NOT_VERIFIED   — all outputs are candidates until human review.
SIMULATION_REQUIRED=YES  — every CAMJob declares simulation is required.
"""

from backend.cam_planning.cam_engine import (
    CamPlanningInput,
    FeatureInput,
    create_cam_job,
    create_cam_job_from_dxf,
    create_cam_job_from_iges,
)
from backend.cam_planning.enums import (
    CAMJobStatus,
    CAMOperationType,
    CAMPlanStatus,
    CAMStrategyType,
    ClearanceType,
    EntryStrategy,
    ExitStrategy,
    FixtureType,
    OperationPhase,
    SetupOrientation,
    SimulationCheck,
    StockSource,
    StockType,
    ToolFamilyRequirement,
    TurningSequenceStep,
    WCSCandidateType,
)
from backend.cam_planning.feature_to_cam import (
    FEATURE_TO_CAM_MAP,
    FeatureMappingResult,
    get_cam_strategy_for_operation,
    map_feature_to_cam_candidates,
)
from backend.cam_planning.models import (
    CAMJob,
    CAMOperationCandidate,
    CAMStrategyCandidate,
    ClearanceRequirement,
    EntryExitRequirement,
    FixtureRequirement,
    HolderRequirement,
    SetupCandidate,
    SimulationRequirement,
    StepParameter,
    StockRequirement,
    ToolpathRequirement,
    ToolRequirement,
    WCSCandidateModel,
)
from backend.cam_planning.operation_ordering import (
    PRECEDENCE_RULES,
    OperationOrderResult,
    PrecedenceRule,
    compute_phase_order,
    sort_operations_by_precedence,
)
from backend.cam_planning.readiness import (
    ReadinessResult,
    check_cam_readiness,
)

__all__ = [
    "CAMJobStatus",
    "CAMOperationType",
    "CAMPlanStatus",
    "CAMStrategyType",
    "ClearanceType",
    "EntryStrategy",
    "ExitStrategy",
    "FixtureType",
    "OperationPhase",
    "SetupOrientation",
    "SimulationCheck",
    "StockSource",
    "StockType",
    "ToolFamilyRequirement",
    "TurningSequenceStep",
    "WCSCandidateType",
    "CAMJob",
    "CAMOperationCandidate",
    "CAMStrategyCandidate",
    "ClearanceRequirement",
    "EntryExitRequirement",
    "FixtureRequirement",
    "HolderRequirement",
    "SetupCandidate",
    "SimulationRequirement",
    "StepParameter",
    "StockRequirement",
    "ToolpathRequirement",
    "ToolRequirement",
    "WCSCandidateModel",
    "FeatureMappingResult",
    "FEATURE_TO_CAM_MAP",
    "get_cam_strategy_for_operation",
    "map_feature_to_cam_candidates",
    "PRECEDENCE_RULES",
    "OperationOrderResult",
    "PrecedenceRule",
    "compute_phase_order",
    "sort_operations_by_precedence",
    "ReadinessResult",
    "check_cam_readiness",
    "CamPlanningInput",
    "FeatureInput",
    "create_cam_job",
    "create_cam_job_from_dxf",
    "create_cam_job_from_iges",
]
