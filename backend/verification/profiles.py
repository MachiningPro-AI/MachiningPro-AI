"""
Verification profiles and their mandatory check sets.

A profile defines which checks are MANDATORY for a toolpath to reach VERIFIED state.
Never call GEOMETRY_ONLY verification "machine verified".
"""

from .enums import VerificationCheckType, VerificationProfileEnum

PROFILE_MANDATORY_CHECKS: dict[VerificationProfileEnum, frozenset[VerificationCheckType]] = {
    VerificationProfileEnum.GEOMETRY_ONLY: frozenset(
        {
            VerificationCheckType.PART_GOUGE,
            VerificationCheckType.STOCK_GOUGE,
        }
    ),
    VerificationProfileEnum.TOOL_AND_PART: frozenset(
        {
            VerificationCheckType.PART_GOUGE,
            VerificationCheckType.STOCK_GOUGE,
            VerificationCheckType.TOOL_COLLISION,
            VerificationCheckType.TOOL_REACH,
        }
    ),
    VerificationProfileEnum.TOOL_HOLDER_PART: frozenset(
        {
            VerificationCheckType.PART_GOUGE,
            VerificationCheckType.STOCK_GOUGE,
            VerificationCheckType.TOOL_COLLISION,
            VerificationCheckType.TOOL_REACH,
            VerificationCheckType.HOLDER_COLLISION,
        }
    ),
    VerificationProfileEnum.FULL_SETUP: frozenset(
        {
            VerificationCheckType.PART_GOUGE,
            VerificationCheckType.STOCK_GOUGE,
            VerificationCheckType.TOOL_COLLISION,
            VerificationCheckType.TOOL_REACH,
            VerificationCheckType.HOLDER_COLLISION,
            VerificationCheckType.FIXTURE_COLLISION,
            VerificationCheckType.RAPID_CLEARANCE,
        }
    ),
    VerificationProfileEnum.FULL_MACHINE: frozenset(
        {
            VerificationCheckType.PART_GOUGE,
            VerificationCheckType.STOCK_GOUGE,
            VerificationCheckType.TOOL_COLLISION,
            VerificationCheckType.TOOL_REACH,
            VerificationCheckType.HOLDER_COLLISION,
            VerificationCheckType.FIXTURE_COLLISION,
            VerificationCheckType.RAPID_CLEARANCE,
            VerificationCheckType.MACHINE_ENVELOPE,
            VerificationCheckType.AXIS_LIMIT,
            VerificationCheckType.OVERTRAVEL,
            VerificationCheckType.KINEMATIC_CHECK,
        }
    ),
}

PROFILE_DESCRIPTIONS: dict[VerificationProfileEnum, str] = {
    VerificationProfileEnum.GEOMETRY_ONLY: "Part gouge and stock gouge only",
    VerificationProfileEnum.TOOL_AND_PART: "Tool body checks against part and stock",
    VerificationProfileEnum.TOOL_HOLDER_PART: "Tool and holder body checks",
    VerificationProfileEnum.FULL_SETUP: "Full setup including fixture (requires fixture geometry)",
    VerificationProfileEnum.FULL_MACHINE: (
        "Complete machine-level verification (requires machine data)"
    ),
}


def get_mandatory_checks(
    profile: VerificationProfileEnum,
) -> frozenset[VerificationCheckType]:
    return PROFILE_MANDATORY_CHECKS.get(profile, frozenset())
