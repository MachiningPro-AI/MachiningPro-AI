"""Level-10 Toolpath Generation Foundation.

Provides vendor-neutral toolpath geometry generation from verified CAM
planning candidate inputs (Level 9).

Safety contract
---------------
NO_GCODE=YES             — this package never produces G-code.
NO_NC_CODE=YES           — no NC programs generated.
NO_FABRICATED_DATA=YES   — no synthetic coordinates, no assumed clearance,
                           no assumed stepdown/stepover, no assumed WCS.
COLLISION_CHECK=NOT_PERFORMED   — declared on every generated toolpath.
GOUGE_CHECK=NOT_PERFORMED       — declared on every generated toolpath.
FIXTURE_CHECK=NOT_PERFORMED     — declared on every generated toolpath.
MACHINE_COLLISION_CHECK=NOT_PERFORMED  — declared on every generated toolpath.
GENERATED_NOT_EQUALS_VERIFIED   — ToolpathStatus.GENERATED != collision-free.
"""

from backend.toolpath.constraints import (
    MachineEnvelopeResult,
    ToolReachResult,
    check_machine_envelope,
    check_tool_reach,
    validate_tool_radius_offset,
)
from backend.toolpath.enums import (
    ClearanceSource,
    CompensationSide,
    CoordinateFrame,
    CornerType,
    DepthStrategy,
    EntryType,
    ExitType,
    LinkStatus,
    MachineEnvelopeStatus,
    MotionType,
    PocketStrategy,
    ProfileSide,
    SegmentGeometryType,
    ToolpathFidelity,
    ToolpathStatus,
    ToolReachStatus,
    TurningMotionType,
    VerificationStatus,
)
from backend.toolpath.generators import (
    ChamferInput,
    DrillInput,
    FaceMillInput,
    PeckDrillInput,
    PocketInput,
    ProfileInput,
    SlotInput,
    TurningInput,
    generate_chamfer_toolpath,
    generate_drill_toolpath,
    generate_face_mill_toolpath,
    generate_peck_drill_toolpath,
    generate_pocket_toolpath,
    generate_profile_toolpath,
    generate_slot_toolpath,
    generate_turning_toolpath,
)
from backend.toolpath.geometry import (
    ArcSegment,
    HelixSegment,
    LineSegment,
    Point3D,
    PolylineSegment,
    Vector3D,
    compute_z_levels,
    offset_polyline_2d,
    ramp_path,
)
from backend.toolpath.models import (
    ClearancePlane,
    PathMetrics,
    RemainingStock,
    StepParameters,
    Toolpath,
    ToolpathCollection,
    ToolpathSegment,
    VerificationContract,
    VisualizationData,
)

__all__ = [
    "ClearanceSource",
    "CoordinateFrame",
    "CompensationSide",
    "CornerType",
    "DepthStrategy",
    "EntryType",
    "ExitType",
    "LinkStatus",
    "MachineEnvelopeStatus",
    "MotionType",
    "PocketStrategy",
    "ProfileSide",
    "SegmentGeometryType",
    "ToolpathFidelity",
    "ToolpathStatus",
    "ToolReachStatus",
    "TurningMotionType",
    "VerificationStatus",
    "ArcSegment",
    "HelixSegment",
    "LineSegment",
    "Point3D",
    "PolylineSegment",
    "Vector3D",
    "compute_z_levels",
    "offset_polyline_2d",
    "ramp_path",
    "ClearancePlane",
    "PathMetrics",
    "RemainingStock",
    "StepParameters",
    "Toolpath",
    "ToolpathCollection",
    "ToolpathSegment",
    "VerificationContract",
    "VisualizationData",
    "ChamferInput",
    "DrillInput",
    "FaceMillInput",
    "PeckDrillInput",
    "PocketInput",
    "ProfileInput",
    "SlotInput",
    "TurningInput",
    "generate_chamfer_toolpath",
    "generate_drill_toolpath",
    "generate_face_mill_toolpath",
    "generate_peck_drill_toolpath",
    "generate_pocket_toolpath",
    "generate_profile_toolpath",
    "generate_slot_toolpath",
    "generate_turning_toolpath",
    "MachineEnvelopeResult",
    "ToolReachResult",
    "check_machine_envelope",
    "check_tool_reach",
    "validate_tool_radius_offset",
]
