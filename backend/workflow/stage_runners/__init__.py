"""Stage runner registry."""
from __future__ import annotations

from ..enums import WorkflowStage
from .adaptive_runner import AdaptiveIntelligenceRunner
from .base import StageRunner
from .cad_runner import CadImportRunner
from .cam_runner import CamPlanningRunner
from .cost_runner import CostRfqRunner
from .cutting_data_runner import CuttingDataRunner
from .cycle_time_runner import CycleTimeRunner
from .dfm_runner import DfmRunner
from .digital_twin_runner import DigitalTwinRunner
from .feature_runner import FeatureRecognitionRunner
from .job_runner import JobAssignmentRunner
from .machine_runner import MachineSelectionRunner
from .nc_runner import NcCandidateRunner
from .plan_runner import FinalPlanRunner
from .process_runner import ProcessPlanningRunner
from .scheduling_runner import SchedulingRunner
from .tool_runner import ToolSelectionRunner
from .toolpath_runner import ToolpathRunner
from .verification_runner import VerificationRunner

RUNNERS: dict[WorkflowStage, type[StageRunner]] = {
    WorkflowStage.CAD_IMPORT:              CadImportRunner,
    WorkflowStage.GEOMETRY:               CadImportRunner,  # geometry is extracted in same pass
    WorkflowStage.FEATURE_RECOGNITION:    FeatureRecognitionRunner,
    WorkflowStage.DFM:                    DfmRunner,
    WorkflowStage.PROCESS_PLANNING:       ProcessPlanningRunner,
    WorkflowStage.MACHINE_SELECTION:      MachineSelectionRunner,
    WorkflowStage.TOOL_SELECTION:         ToolSelectionRunner,
    WorkflowStage.CUTTING_DATA:           CuttingDataRunner,
    WorkflowStage.CYCLE_TIME:             CycleTimeRunner,
    WorkflowStage.COST_RFQ:              CostRfqRunner,
    WorkflowStage.CAM_PLANNING:           CamPlanningRunner,
    WorkflowStage.TOOLPATH:              ToolpathRunner,
    WorkflowStage.VERIFICATION:          VerificationRunner,
    WorkflowStage.NC_CANDIDATE:          NcCandidateRunner,
    WorkflowStage.SCHEDULING:            SchedulingRunner,
    WorkflowStage.JOB_ASSIGNMENT:        JobAssignmentRunner,
    WorkflowStage.ADAPTIVE_INTELLIGENCE: AdaptiveIntelligenceRunner,
    WorkflowStage.DIGITAL_TWIN:          DigitalTwinRunner,
    WorkflowStage.FINAL_MANUFACTURING_PLAN: FinalPlanRunner,
}

__all__ = [
    "StageRunner",
    "RUNNERS",
    "CadImportRunner",
    "FeatureRecognitionRunner",
    "DfmRunner",
    "ProcessPlanningRunner",
    "MachineSelectionRunner",
    "ToolSelectionRunner",
    "CuttingDataRunner",
    "CycleTimeRunner",
    "CostRfqRunner",
    "CamPlanningRunner",
    "ToolpathRunner",
    "VerificationRunner",
    "NcCandidateRunner",
    "SchedulingRunner",
    "JobAssignmentRunner",
    "AdaptiveIntelligenceRunner",
    "DigitalTwinRunner",
    "FinalPlanRunner",
]
