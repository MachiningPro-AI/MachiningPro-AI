"""Level-17 machine capability profile builder.

Builds MachineCapabilityProfile from catalog records or scheduling resources.
All None values preserved — never substituted with fabricated data.
"""

from __future__ import annotations

from ..machines.catalog_models import MachineCatalogRecord
from ..scheduling.enums import MachineClass
from ..scheduling.models import MachineResource
from .models import MachineCapabilityProfile

_MACHINE_TYPE_CODE_TO_CLASS: dict[str, MachineClass] = {
    "VMC": MachineClass.VMC_3AXIS,
    "VMC_3AXIS": MachineClass.VMC_3AXIS,
    "VMC_4AXIS": MachineClass.VMC_4AXIS,
    "VMC_5AXIS": MachineClass.VMC_5AXIS,
    "HMC": MachineClass.HMC_3AXIS,
    "HMC_3AXIS": MachineClass.HMC_3AXIS,
    "HMC_4AXIS": MachineClass.HMC_4AXIS,
    "LATHE": MachineClass.LATHE_2AXIS,
    "LATHE_2AXIS": MachineClass.LATHE_2AXIS,
    "LATHE_LIVE_TOOL": MachineClass.LATHE_LIVE_TOOL,
    "MILL_TURN": MachineClass.TURN_MILL,
    "TURN_MILL": MachineClass.TURN_MILL,
    "5AXIS": MachineClass.VMC_5AXIS,
    "GRINDER": MachineClass.GRINDER,
    "WIRE_EDM": MachineClass.WIRE_EDM,
}


def _map_type_code_to_class(code: str | None) -> MachineClass:
    if code is None:
        return MachineClass.UNKNOWN
    return _MACHINE_TYPE_CODE_TO_CLASS.get(code.upper(), MachineClass.UNKNOWN)


def build_capability_profile_from_catalog(
    machine_id: str,
    record: MachineCatalogRecord,
) -> MachineCapabilityProfile:
    """Build a MachineCapabilityProfile from a MachineCatalogRecord.

    All Optional fields in the catalog record are preserved as None.
    is_fabricated_capability is always False.
    """
    machine_class = _map_type_code_to_class(record.machine_type_code)

    # Spindle power — prefer continuous if available, else peak, else generic
    spindle_kw = (
        record.spindle_power_continuous_kw
        or record.spindle_power_kw
        or record.spindle_power_peak_kw
    )

    # Travel dimensions — catalog uses travel_x/y/z_mm
    tx = record.travel_x_mm
    ty = record.travel_y_mm
    tz = record.travel_z_mm

    # For lathes, turning diameter maps to x_travel, length maps to z_travel
    if tx is None and record.max_turning_diameter_mm is not None:
        tx = record.max_turning_diameter_mm
    if tz is None and record.max_turning_length_mm is not None:
        tz = record.max_turning_length_mm

    return MachineCapabilityProfile(
        machine_id=machine_id,
        machine_class=machine_class,
        axis_count=record.axis_count,
        spindle_max_rpm=record.spindle_max_rpm,
        spindle_power_kw=spindle_kw,
        travel_x_mm=tx,
        travel_y_mm=ty,
        travel_z_mm=tz,
        table_load_kg=record.table_load_kg,
        turning_capable=record.turning_capable,
        milling_capable=record.milling_capable,
        drilling_capable=record.drilling_capable,
        through_spindle_coolant=record.through_spindle_coolant,
        has_live_tooling=record.has_live_tooling,
        capable_tapping=record.capable_tapping,
        capable_boring=record.capable_boring,
        tool_magazine_capacity=record.tool_magazine_capacity,
        is_fabricated_capability=False,
    )


def build_capability_profile_from_resource(
    resource: MachineResource,
) -> MachineCapabilityProfile:
    """Build a MachineCapabilityProfile from a Level-13 MachineResource.

    Fields not present in MachineResource remain None — never fabricated.
    is_fabricated_capability is always False.
    """
    return MachineCapabilityProfile(
        machine_id=resource.machine_id,
        machine_class=resource.machine_class,
        axis_count=resource.axis_count,
        spindle_max_rpm=(
            int(resource.spindle_speed_max_rpm)
            if resource.spindle_speed_max_rpm is not None
            else None
        ),
        spindle_power_kw=resource.spindle_power_kw,
        travel_x_mm=resource.x_travel_mm,
        travel_y_mm=resource.y_travel_mm,
        travel_z_mm=resource.z_travel_mm,
        table_load_kg=resource.table_load_capacity_kg,
        turning_capable=resource.supports_turning,
        milling_capable=resource.supports_milling,
        drilling_capable=False,
        through_spindle_coolant=None,
        has_live_tooling=False,
        capable_tapping=None,
        capable_boring=None,
        tool_magazine_capacity=None,
        is_fabricated_capability=False,
    )
