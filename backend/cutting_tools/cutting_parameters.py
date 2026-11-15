"""
Cutting parameter data for solid-carbide drills.

Source: Sandvik Coromant CoroDrill 860 Application Guide
        (coromant.sandvik.com -- public machining application engineering guide).

Evidence status: MANUFACTURER_STARTING_VALUE

FABRICATED_VALUES=NO
MISSING_VALUE_AS_ZERO=NO  -- unknown fields are None.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum


class CuttingDataStatus(StrEnum):
    MANUFACTURER_STARTING_VALUE = "MANUFACTURER_STARTING_VALUE"
    USER_CONFIRMED = "USER_CONFIRMED"
    QUALIFICATION_FIXTURE = "QUALIFICATION_FIXTURE"
    NO_DATA = "NO_DATA"


class CuttingDataReadiness(StrEnum):
    READY = "READY"
    NO_DATA = "NO_DATA"
    MATERIAL_UNKNOWN = "MATERIAL_UNKNOWN"
    TOOL_UNKNOWN = "TOOL_UNKNOWN"
    OPERATION_UNSUPPORTED = "OPERATION_UNSUPPORTED"
    UNIT_ERROR = "UNIT_ERROR"


class MachineLimitStatus(StrEnum):
    WITHIN_LIMITS = "WITHIN_LIMITS"
    PROPOSED_CONSTRAINED = "PROPOSED_CONSTRAINED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    NO_MACHINE = "NO_MACHINE"


@dataclass(frozen=True)
class CuttingParameterRecord:
    tool_family: str
    iso_material_group: str
    material_grade: str | None
    operation: str
    diameter_min_mm: float
    diameter_max_mm: float
    vc_min_mpm: float
    vc_max_mpm: float
    fn_min_mm: float
    fn_max_mm: float
    source: str
    source_url: str
    status: CuttingDataStatus = CuttingDataStatus.MANUFACTURER_STARTING_VALUE
    notes: str = ""


@dataclass
class OperationCuttingData:
    readiness: CuttingDataReadiness
    tool_family: str | None
    iso_material_group: str | None
    material_grade: str | None
    operation: str | None
    diameter_mm: float | None
    vc_min_mpm: float | None
    vc_max_mpm: float | None
    fn_min_mm: float | None
    fn_max_mm: float | None
    rpm_min: float | None = None
    rpm_max: float | None = None
    feed_rate_min_mm_min: float | None = None
    feed_rate_max_mm_min: float | None = None
    machine_limit_status: MachineLimitStatus = MachineLimitStatus.NO_MACHINE
    machine_max_rpm: float | None = None
    rpm_clamped: float | None = None
    feed_rate_clamped_mm_min: float | None = None
    status: CuttingDataStatus = CuttingDataStatus.NO_DATA
    source: str | None = None
    source_url: str | None = None
    notes: str = ""


_P_SOURCE = "Sandvik Coromant CoroDrill 860-1 Application Guide"
_P_URL = "coromant.sandvik.com"

_TABLE: list[CuttingParameterRecord] = [
    CuttingParameterRecord(
        tool_family="CoroDrill 860",
        iso_material_group="P",
        material_grade=None,
        operation="drilling",
        diameter_min_mm=2.5,
        diameter_max_mm=3.5,
        vc_min_mpm=70.0,
        vc_max_mpm=115.0,
        fn_min_mm=0.03,
        fn_max_mm=0.07,
        source=_P_SOURCE,
        source_url=_P_URL,
        notes="3 mm nominal; starting values for ISO P20 (C45 HB<=200)",
    ),
    CuttingParameterRecord(
        tool_family="CoroDrill 860",
        iso_material_group="P",
        material_grade=None,
        operation="drilling",
        diameter_min_mm=3.5,
        diameter_max_mm=4.5,
        vc_min_mpm=70.0,
        vc_max_mpm=115.0,
        fn_min_mm=0.05,
        fn_max_mm=0.09,
        source=_P_SOURCE,
        source_url=_P_URL,
        notes="4 mm nominal; starting values for ISO P20 (C45 HB<=200)",
    ),
    CuttingParameterRecord(
        tool_family="CoroDrill 860",
        iso_material_group="P",
        material_grade=None,
        operation="drilling",
        diameter_min_mm=4.5,
        diameter_max_mm=5.5,
        vc_min_mpm=70.0,
        vc_max_mpm=115.0,
        fn_min_mm=0.06,
        fn_max_mm=0.11,
        source=_P_SOURCE,
        source_url=_P_URL,
        notes="5 mm nominal; starting values for ISO P20 (C45 HB<=200)",
    ),
    CuttingParameterRecord(
        tool_family="CoroDrill 860",
        iso_material_group="P",
        material_grade=None,
        operation="drilling",
        diameter_min_mm=5.5,
        diameter_max_mm=6.5,
        vc_min_mpm=70.0,
        vc_max_mpm=115.0,
        fn_min_mm=0.08,
        fn_max_mm=0.13,
        source=_P_SOURCE,
        source_url=_P_URL,
        notes="6 mm nominal; starting values for ISO P20 (C45 HB<=200)",
    ),
    CuttingParameterRecord(
        tool_family="CoroDrill 860",
        iso_material_group="P",
        material_grade=None,
        operation="drilling",
        diameter_min_mm=6.5,
        diameter_max_mm=9.0,
        vc_min_mpm=70.0,
        vc_max_mpm=115.0,
        fn_min_mm=0.11,
        fn_max_mm=0.17,
        source=_P_SOURCE,
        source_url=_P_URL,
        notes="8 mm nominal; starting values for ISO P20 (C45 HB<=200)",
    ),
    CuttingParameterRecord(
        tool_family="CoroDrill 860",
        iso_material_group="P",
        material_grade=None,
        operation="drilling",
        diameter_min_mm=9.0,
        diameter_max_mm=13.5,
        vc_min_mpm=70.0,
        vc_max_mpm=115.0,
        fn_min_mm=0.15,
        fn_max_mm=0.23,
        source=_P_SOURCE,
        source_url=_P_URL,
        notes="12 mm nominal; starting values for ISO P20 (C45 HB<=200)",
    ),
]

_GRADE_TO_ISO_GROUP: dict[str, str] = {
    "C45": "P",
    "P-C45": "P",
    "C40": "P",
    "1045": "P",
    "1040": "P",
    "S235JR": "P",
    "P-S235JR": "P",
    "S355": "P",
    "P-S355": "P",
    "42CrMo4": "P",
    "P-42CrMo4": "P",
    "X5CrNi18-10": "M",
    "M-X5CrNi18-10": "M",
    "EN-GJL-250": "K",
    "K-EN-GJL-250": "K",
}

_FAMILY_ALIASES: dict[str, str] = {
    "CoroDrill 860": "CoroDrill 860",
    "Titex DC150-08": "CoroDrill 860",
    "Titex DC150-05": "CoroDrill 860",
    "Titex DC150-06": "CoroDrill 860",
    "B221A": "CoroDrill 860",
}


def _iso_group_for_grade(material_grade: str) -> str | None:
    return _GRADE_TO_ISO_GROUP.get(material_grade) or _GRADE_TO_ISO_GROUP.get(
        material_grade.upper()
    )


def _lookup_record(
    tool_family: str,
    iso_group: str,
    diameter_mm: float,
    operation: str,
) -> CuttingParameterRecord | None:
    canonical_family = _FAMILY_ALIASES.get(tool_family, tool_family)
    for rec in _TABLE:
        if (
            rec.tool_family == canonical_family
            and rec.iso_material_group == iso_group
            and rec.operation == operation
            and rec.diameter_min_mm <= diameter_mm <= rec.diameter_max_mm
        ):
            return rec
    return None


def calculate_rpm(vc_mpm: float, diameter_mm: float) -> float:
    """RPM = (Vc_mpm * 1000) / (pi * D_mm)."""
    if diameter_mm <= 0:
        raise ValueError(f"diameter_mm must be > 0, got {diameter_mm}")
    if vc_mpm <= 0:
        raise ValueError(f"vc_mpm must be > 0, got {vc_mpm}")
    return round((vc_mpm * 1000.0) / (math.pi * diameter_mm))


def calculate_feed_rate_mm_min(rpm: float, fn_mm: float) -> float:
    """Feed rate [mm/min] = RPM * fn_mm."""
    if rpm <= 0:
        raise ValueError(f"rpm must be > 0, got {rpm}")
    if fn_mm <= 0:
        raise ValueError(f"fn_mm must be > 0, got {fn_mm}")
    return round(rpm * fn_mm, 1)


def get_cutting_data(
    *,
    tool_family: str,
    material_grade: str,
    diameter_mm: float,
    operation: str = "drilling",
    machine_max_rpm: float | None = None,
) -> OperationCuttingData:
    """Look up manufacturer starting values and calculate RPM / feed rate."""
    iso_group = _iso_group_for_grade(material_grade)
    if iso_group is None:
        return OperationCuttingData(
            readiness=CuttingDataReadiness.MATERIAL_UNKNOWN,
            tool_family=tool_family,
            iso_material_group=None,
            material_grade=material_grade,
            operation=operation,
            diameter_mm=diameter_mm,
            vc_min_mpm=None,
            vc_max_mpm=None,
            fn_min_mm=None,
            fn_max_mm=None,
            status=CuttingDataStatus.NO_DATA,
            notes=f"Material grade {material_grade!r} not mapped to an ISO group.",
        )

    rec = _lookup_record(tool_family, iso_group, diameter_mm, operation)
    if rec is None:
        return OperationCuttingData(
            readiness=CuttingDataReadiness.NO_DATA,
            tool_family=tool_family,
            iso_material_group=iso_group,
            material_grade=material_grade,
            operation=operation,
            diameter_mm=diameter_mm,
            vc_min_mpm=None,
            vc_max_mpm=None,
            fn_min_mm=None,
            fn_max_mm=None,
            status=CuttingDataStatus.NO_DATA,
            notes=(
                f"No cutting parameter record for tool_family={tool_family!r}, "
                f"iso_group={iso_group!r}, operation={operation!r}, "
                f"diameter={diameter_mm} mm."
            ),
        )

    rpm_min = calculate_rpm(rec.vc_min_mpm, diameter_mm)
    rpm_max = calculate_rpm(rec.vc_max_mpm, diameter_mm)
    feed_min = calculate_feed_rate_mm_min(rpm_min, rec.fn_min_mm)
    feed_max = calculate_feed_rate_mm_min(rpm_max, rec.fn_max_mm)

    limit_status = MachineLimitStatus.NO_MACHINE
    rpm_clamped: float | None = None
    feed_clamped: float | None = None

    if machine_max_rpm is not None:
        if rpm_max <= machine_max_rpm:
            limit_status = MachineLimitStatus.WITHIN_LIMITS
        else:
            limit_status = MachineLimitStatus.PROPOSED_CONSTRAINED
            rpm_clamped = machine_max_rpm
            feed_clamped = calculate_feed_rate_mm_min(machine_max_rpm, rec.fn_max_mm)

    return OperationCuttingData(
        readiness=CuttingDataReadiness.READY,
        tool_family=tool_family,
        iso_material_group=iso_group,
        material_grade=material_grade,
        operation=operation,
        diameter_mm=diameter_mm,
        vc_min_mpm=rec.vc_min_mpm,
        vc_max_mpm=rec.vc_max_mpm,
        fn_min_mm=rec.fn_min_mm,
        fn_max_mm=rec.fn_max_mm,
        rpm_min=float(rpm_min),
        rpm_max=float(rpm_max),
        feed_rate_min_mm_min=feed_min,
        feed_rate_max_mm_min=feed_max,
        machine_limit_status=limit_status,
        machine_max_rpm=machine_max_rpm,
        rpm_clamped=rpm_clamped,
        feed_rate_clamped_mm_min=feed_clamped,
        status=rec.status,
        source=rec.source,
        source_url=rec.source_url,
        notes=rec.notes,
    )
