"""
Phase R — Machine Kinematic Model
Phase S — Axis Solution
Phase T — Machine Limit Verification

Supported canonical architectures:
  3_AXIS_VMC
  3_AXIS_HMC
  4_AXIS_TABLE
  5_AXIS_TABLE_TABLE
  5_AXIS_HEAD_TABLE

TEST_ONLY machine definitions are allowed for deterministic validation.
Production machine architecture is NOT inferred from model/marketing name alone.

Fail-closed contract:
  Missing architecture → NOT_VERIFIABLE (never PASS)
  Missing axis limits → NOT_PERFORMED (never safe)
  Axis violation → FAIL (never clamped)
  Singularity not implemented → SINGULARITY_CHECK=NOT_IMPLEMENTED

FABRICATED_MACHINE_DATA=NO
AUTO_APPROVAL=NO
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class MachineArchitecture(StrEnum):
    THREE_AXIS_VMC = "3_AXIS_VMC"
    THREE_AXIS_HMC = "3_AXIS_HMC"
    FOUR_AXIS_TABLE = "4_AXIS_TABLE"
    FIVE_AXIS_TABLE_TABLE = "5_AXIS_TABLE_TABLE"
    FIVE_AXIS_HEAD_TABLE = "5_AXIS_HEAD_TABLE"
    UNKNOWN = "UNKNOWN"


@dataclass
class AxisLimit:
    """Legitimate catalog axis limit — never fabricated."""
    axis: str                      # X, Y, Z, A, B, C
    min_mm_or_deg: float
    max_mm_or_deg: float
    source: str = "CATALOG"
    test_only: bool = False


@dataclass
class MachineKinematicModel:
    machine_id: str = ""
    architecture: str = "UNKNOWN"
    axis_count: int = 3
    axis_limits: list[AxisLimit] = field(default_factory=list)
    home_position: dict[str, float] = field(default_factory=dict)
    test_only: bool = False          # True = isolated test fixture; never production
    source: str = "CATALOG"
    provenance: str = "CATALOG_PARAMETRIC"

    @property
    def is_known_architecture(self) -> bool:
        return self.architecture not in ("UNKNOWN", "NOT_AVAILABLE")

    def axis_limit_map(self) -> dict[str, tuple[float, float]]:
        return {al.axis: (al.min_mm_or_deg, al.max_mm_or_deg) for al in self.axis_limits}


@dataclass
class AxisSolutionResult:
    """Phase S — derived machine axis state for one toolpath pose."""
    pose_id: str = ""
    x_mm: float | None = None
    y_mm: float | None = None
    z_mm: float | None = None
    a_deg: float | None = None
    b_deg: float | None = None
    c_deg: float | None = None
    status: str = "NOT_VERIFIABLE"
    kinematic_method: str = "DIRECT_XYZ"
    solution_provenance: str = "CATALOG_PARAMETRIC"
    warnings: list[str] = field(default_factory=list)


@dataclass
class AxisViolation:
    axis: str
    command_value: float
    limit_min: float
    limit_max: float
    excess: float
    operation_id: str = ""
    toolpath_segment: str = ""


@dataclass
class MachineLimitVerificationResult:
    """Phase T — machine limit verification for a full toolpath."""
    machine_id: str = ""
    architecture: str = "UNKNOWN"
    status: str = "NOT_PERFORMED"
    method: str = "NOT_PERFORMED"
    violations: list[AxisViolation] = field(default_factory=list)
    singularity_check: str = "NOT_IMPLEMENTED"
    axes_checked: list[str] = field(default_factory=list)
    segments_checked: int = 0
    provenance: str = "CATALOG_PARAMETRIC"
    warnings: list[str] = field(default_factory=list)


def build_kinematic_model_from_catalog(
    machine_id: str,
    machine_class_value: str,
    envelope,
    source: str = "CATALOG",
) -> MachineKinematicModel:
    """Build a kinematic model from a MachineCatalogRecord.

    Architecture is taken directly from the catalog MachineClass.
    Axis limits are populated from envelope.rotary_axes and linear travels.
    """
    model = MachineKinematicModel(
        machine_id=machine_id,
        architecture=_map_machine_class(machine_class_value),
        source=source,
        provenance="CATALOG_PARAMETRIC",
    )

    if envelope is None:
        model.warnings = ["No envelope data; axis limits unavailable"]
        return model

    # Linear axes from travel
    linear_axes = []
    if envelope.travel_x_mm is not None:
        linear_axes.append(AxisLimit("X", 0.0, envelope.travel_x_mm, source))
    if envelope.travel_y_mm is not None:
        linear_axes.append(AxisLimit("Y", 0.0, envelope.travel_y_mm, source))
    if envelope.travel_z_mm is not None:
        linear_axes.append(AxisLimit("Z", 0.0, envelope.travel_z_mm, source))

    # Rotary axes from catalog — only if explicit angle limits exist
    rotary_axes = []
    min_ang = getattr(envelope, "min_angle_deg", None)
    max_ang = getattr(envelope, "max_angle_deg", None)
    if min_ang is not None and max_ang is not None:
        # Determine axis label (default A for primary rotary)
        axis_label = getattr(envelope, "rotary_axis_label", "A")
        rotary_axes.append(AxisLimit(axis_label, min_ang, max_ang, source))

    model.axis_limits = linear_axes + rotary_axes
    model.axis_count = 3 + len(rotary_axes) if rotary_axes else 3

    return model


def _map_machine_class(value: str) -> str:
    mapping = {
        "3_AXIS_VMC": "3_AXIS_VMC",
        "4_AXIS_VMC": "4_AXIS_TABLE",
        "5_AXIS_VMC": "5_AXIS_TABLE_TABLE",
        "HMC": "3_AXIS_HMC",
    }
    return mapping.get(value, "UNKNOWN")


def build_test_only_kinematic_model(
    machine_id: str,
    architecture: str,
    x_range: tuple[float, float],
    y_range: tuple[float, float],
    z_range: tuple[float, float],
    a_range: tuple[float, float] | None = None,
    b_range: tuple[float, float] | None = None,
    c_range: tuple[float, float] | None = None,
) -> MachineKinematicModel:
    """Build a TEST_ONLY kinematic model for deterministic validation cases.

    Never used in production path. test_only=True is mandatory.
    """
    limits = [
        AxisLimit("X", *x_range, "TEST_ONLY", test_only=True),
        AxisLimit("Y", *y_range, "TEST_ONLY", test_only=True),
        AxisLimit("Z", *z_range, "TEST_ONLY", test_only=True),
    ]
    if a_range:
        limits.append(AxisLimit("A", *a_range, "TEST_ONLY", test_only=True))
    if b_range:
        limits.append(AxisLimit("B", *b_range, "TEST_ONLY", test_only=True))
    if c_range:
        limits.append(AxisLimit("C", *c_range, "TEST_ONLY", test_only=True))

    return MachineKinematicModel(
        machine_id=machine_id,
        architecture=architecture,
        axis_count=3 + sum(1 for r in [a_range, b_range, c_range] if r is not None),
        axis_limits=limits,
        test_only=True,
        source="TEST_ONLY",
        provenance="TEST_ONLY",
    )


def solve_axis_positions_3axis(
    x_mm: float,
    y_mm: float,
    z_mm: float,
    pose_id: str = "",
) -> AxisSolutionResult:
    """Phase S — 3-axis direct axis solution.

    For a 3-axis VMC or HMC the tool tip maps directly to X, Y, Z.
    No rotation decomposition needed.
    """
    return AxisSolutionResult(
        pose_id=pose_id,
        x_mm=x_mm,
        y_mm=y_mm,
        z_mm=z_mm,
        status="PASS",
        kinematic_method="DIRECT_XYZ",
        solution_provenance="CATALOG_PARAMETRIC",
    )


def verify_machine_limits(
    model: MachineKinematicModel,
    segments: list,          # list of dicts with start/end XYZ
    operation_id: str = "",
) -> MachineLimitVerificationResult:
    """Phase T — verify every toolpath segment against machine axis limits.

    segments: list of {'x': float, 'y': float, 'z': float, 'seg_id': str}
    For 3-axis: checks X, Y, Z only.
    Rotary axes checked when rotary limits are present in the model.

    Violations are reported — never clamped.
    Missing limits → NOT_PERFORMED (not safe).
    """
    r = MachineLimitVerificationResult(
        machine_id=model.machine_id,
        architecture=model.architecture,
        provenance=model.provenance,
    )

    if not model.is_known_architecture:
        r.status = "NOT_VERIFIABLE"
        r.method = "NOT_VERIFIABLE"
        r.warnings.append("machine architecture unknown; axis limit check not possible")
        return r

    limit_map = model.axis_limit_map()
    if not limit_map:
        r.status = "NOT_PERFORMED"
        r.method = "NOT_PERFORMED"
        r.warnings.append("no axis limits in kinematic model; NOT_PERFORMED")
        return r

    linear_axes = [a for a in limit_map if a in ("X", "Y", "Z")]
    rotary_axes = [a for a in limit_map if a in ("A", "B", "C")]
    r.axes_checked = list(limit_map.keys())
    r.method = "CATALOG_AXIS_LIMIT_CHECK"

    violations: list[AxisViolation] = []
    r.segments_checked = len(segments)

    for seg in segments:
        seg_id = seg.get("seg_id", "")

        for axis in linear_axes:
            val = seg.get(axis.lower())
            if val is None:
                continue
            lo, hi = limit_map[axis]
            if val < lo or val > hi:
                excess = (val - hi) if val > hi else (lo - val)
                violations.append(AxisViolation(
                    axis=axis,
                    command_value=val,
                    limit_min=lo,
                    limit_max=hi,
                    excess=excess,
                    operation_id=operation_id,
                    toolpath_segment=seg_id,
                ))

        for axis in rotary_axes:
            val = seg.get(axis.lower())
            if val is None:
                continue
            lo, hi = limit_map[axis]
            if val < lo or val > hi:
                excess = (val - hi) if val > hi else (lo - val)
                violations.append(AxisViolation(
                    axis=axis,
                    command_value=val,
                    limit_min=lo,
                    limit_max=hi,
                    excess=excess,
                    operation_id=operation_id,
                    toolpath_segment=seg_id,
                ))

    r.violations = violations
    r.singularity_check = "NOT_IMPLEMENTED"

    if violations:
        r.status = "FAIL"
    elif limit_map:
        r.status = "PASS"
    else:
        r.status = "NOT_PERFORMED"

    return r
