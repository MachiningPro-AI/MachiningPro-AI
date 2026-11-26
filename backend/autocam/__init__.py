"""Auto CAM End-to-End Orchestration Module.

MACHININGPRO_AI_AUTO_CAM_END_TO_END_01

Safety contract
---------------
AUTO_CAM_CAN_DISPATCH_CNC=NO
AUTO_CAM_CAN_RELEASE_PRODUCTION=NO
AUTO_CAM_CAN_AUTO_APPROVE=NO
REAL_MACHINE_WRITE_FOUND=NO
DUPLICATE_ENGINE_CREATED=NO
"""

from .models import AutoCamBlocker, AutoCamPlan, AutoCamRequest, AutoCamStageResult
from .orchestrator import run_auto_cam

__all__ = [
    "AutoCamRequest",
    "AutoCamPlan",
    "AutoCamStageResult",
    "AutoCamBlocker",
    "run_auto_cam",
]
