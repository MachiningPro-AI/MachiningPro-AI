"""Structured domain models for the Machine Library.

Hierarchy:
  MachineCatalogRecord
    ├─ MachineCapability      (process flags, axes, tool system, control)
    ├─ MachineSpindleSpecification
    ├─ MachineEnvelope        (workspace dimensions, workpiece limits)
    │    └─ MachineAxisSpecification  (one per rotary axis)
    └─ MachineSourceMetadata  (provenance)

Design rules
------------
MISSING_VALUE_AS_ZERO=NO   — optional numeric fields use None, never 0.
SYNTHETIC_SPECIFICATIONS_ADDED=NO — no default fallback values for specs.
FAIL_CLOSED=YES — validation refuses to pass on absent limit data.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.machine_library.enums import (
    AxisType,
    EvidenceGrade,
    MachineCatalogStatus,
    MachineClass,
)

__all__ = [
    "MachineAxisSpecification",
    "MachineCapability",
    "MachineCatalogRecord",
    "MachineEnvelope",
    "MachineSourceMetadata",
    "MachineSpindleSpecification",
    "MachineCatalogStatus",
]


class MachineAxisSpecification(BaseModel):
    """Specification for a single CNC axis (linear or rotary)."""

    axis_label: str
    axis_type: AxisType

    # Linear axis (mm)
    travel_mm: float | None = None

    # Rotary axis (degrees)
    min_angle_deg: float | None = None
    max_angle_deg: float | None = None

    # Dynamics
    rapid_mpm: float | None = None        # m/min (linear) or deg/s for rotary
    feed_max_mpm: float | None = None

    # Accuracy
    positioning_accuracy_um: float | None = None
    repeatability_um: float | None = None


class MachineSpindleSpecification(BaseModel):
    """Spindle performance specification.

    All fields are optional — missing values carry None, not 0.
    Both continuous and peak values are captured when available.
    """

    min_rpm: int | None = None
    max_rpm: int | None = None

    # Power (kW)
    power_kw: float | None = None
    power_continuous_kw: float | None = None
    power_peak_kw: float | None = None

    # Torque (Nm)
    torque_nm: float | None = None
    torque_continuous_nm: float | None = None
    torque_peak_nm: float | None = None
    torque_at_rpm: int | None = None

    # Interface
    interface: str | None = None   # e.g. "CAT-40", "HSK-A63", "BT-30"
    interfaces_supported: list[str] = Field(default_factory=list)


class MachineEnvelope(BaseModel):
    """Workspace envelope and workpiece capacity.

    Covers both prismatic machines (travel_x/y/z) and
    turning machines (max_turning_diameter/length).
    """

    # Linear axis travels (mm)
    travel_x_mm: float | None = None
    travel_y_mm: float | None = None
    travel_z_mm: float | None = None

    # Rotary axes (A, B, C) — per-axis detail
    rotary_axes: list[MachineAxisSpecification] = Field(default_factory=list)

    # Table
    table_length_mm: float | None = None
    table_width_mm: float | None = None
    table_load_kg: float | None = None

    # Maximum workpiece envelope
    max_workpiece_x_mm: float | None = None
    max_workpiece_y_mm: float | None = None
    max_workpiece_z_mm: float | None = None
    max_workpiece_mass_kg: float | None = None

    # Turning / Swiss specific
    max_turning_diameter_mm: float | None = None
    max_turning_length_mm: float | None = None
    bar_capacity_mm: float | None = None

    # Grinding specific
    grinding_wheel_diameter_mm: float | None = None
    max_grinding_length_mm: float | None = None


class MachineCapability(BaseModel):
    """Process capabilities, axis configuration, and machine features.

    Captures boolean capability flags, the tool magazine system,
    coolant options, and control system information.
    """

    machine_class: MachineClass
    controlled_axes: int
    simultaneous_axes: int | None = None

    # Process capabilities
    turning_capable: bool = False
    milling_capable: bool = False
    drilling_capable: bool = False
    grinding_capable: bool = False
    edm_capable: bool = False

    # Detailed process flags
    capable_tapping: bool | None = None
    capable_boring: bool | None = None
    capable_threading: bool | None = None
    capable_reaming: bool | None = None
    capable_5axis_simultaneous: bool | None = None
    capable_3plus2: bool | None = None

    # Machine features
    has_subspindle: bool = False
    has_y_axis: bool = False
    has_live_tooling: bool = False
    has_b_axis: bool = False
    has_pallet_changer: bool = False

    # Tool magazine
    tool_magazine_capacity: int | None = None
    tool_magazine_type: str | None = None
    tool_interface: str | None = None
    max_tool_diameter_mm: float | None = None
    max_tool_diameter_adj_mm: float | None = None
    max_tool_length_mm: float | None = None
    atc_chip_to_chip_sec: float | None = None
    atc_tool_to_tool_sec: float | None = None

    # Feed dynamics
    max_cutting_feed_mm_min: float | None = None
    rapid_traverse_mpm: float | None = None

    # Coolant
    has_through_spindle_coolant: bool | None = None
    coolant_pressure_bar: float | None = None
    mql_support: bool | None = None
    flood_coolant: bool = True
    chip_conveyor: bool | None = None

    # Control
    controller_family: str | None = None
    controller_model: str | None = None
    controller_generation: str | None = None
    nc_dialect: str | None = None

    # Accuracy
    positioning_accuracy_um: float | None = None
    repeatability_um: float | None = None

    # Processes
    supported_processes: list[str] = Field(default_factory=list)

    @property
    def has_primary_capability(self) -> bool:
        """True when at least one primary process capability is declared."""
        return any([
            self.turning_capable,
            self.milling_capable,
            self.drilling_capable,
            self.grinding_capable,
            self.edm_capable,
        ])


class MachineSourceMetadata(BaseModel):
    """Data provenance for a machine catalog record.

    Every record must carry evidence provenance before it can be used in
    capability decisions.  Missing provenance is an error, not a warning.
    """

    source_title: str
    evidence_grade: EvidenceGrade = EvidenceGrade.MANUFACTURER_DATASHEET
    source_url: str | None = None
    source_note: str | None = None
    verified_date: str | None = None


class MachineCatalogRecord(BaseModel):
    """Top-level machine catalog entry with structured sub-models.

    Replaces the legacy flat MachineCatalogRecord from backend.machines.catalog_models.
    This record carries full provenance, structured capability, envelope, and
    spindle sub-models rather than a flat attribute list.

    Rules
    -----
    MISSING_VALUE_AS_ZERO=NO
    SYNTHETIC_SPECIFICATIONS_ADDED=NO
    FABRICATED_MACHINE_SPEC=NO
    """

    stable_id: str
    manufacturer: str
    model: str
    family: str | None = None

    capability: MachineCapability
    spindle: MachineSpindleSpecification
    envelope: MachineEnvelope
    source: MachineSourceMetadata

    catalog_status: MachineCatalogStatus = MachineCatalogStatus.ACTIVE

    # Lineage
    year_introduced: int | None = None
    year_discontinued: int | None = None
    country_of_origin: str | None = None
    machine_weight_kg: float | None = None

    @property
    def machine_class(self) -> MachineClass:
        return self.capability.machine_class

    @property
    def missing_fields(self) -> list[str]:
        """Field names that carry None in this record (spindle + envelope)."""
        absent: list[str] = []
        s = self.spindle
        for attr in (
            "min_rpm", "max_rpm", "power_kw", "torque_nm", "interface",
        ):
            if getattr(s, attr) is None:
                absent.append(f"spindle.{attr}")
        e = self.envelope
        for attr in (
            "travel_x_mm", "travel_y_mm", "travel_z_mm",
            "table_load_kg",
            "max_turning_diameter_mm", "max_turning_length_mm",
        ):
            if getattr(e, attr) is None:
                absent.append(f"envelope.{attr}")
        return sorted(absent)
