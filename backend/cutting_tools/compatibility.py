"""Tool-to-holder and insert-to-holder compatibility engine.

Result status semantics
-----------------------
PASS    — every checked dimension and constraint explicitly passes.
FAIL    — at least one constraint explicitly fails.
UNKNOWN — no constraint explicitly fails but at least one required value is
          absent; the caller must not treat this as PASS.

Design rules:
- Missing data never converts to PASS.
- Geometric fit does not imply machining suitability.
- Each reason string identifies the specific constraint and actual values.
"""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from .catalog_models import CuttingToolCatalogRecord
from .holder_models import HolderInterface, ToolHolderRecord
from .insert_models import InsertRecord


class CompatibilityStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class CompatibilityResult(BaseModel):
    status: CompatibilityStatus
    reasons: list[str]


# ── Holder operation support ──────────────────────────────────────────────────

_HOLDER_OPERATIONS: dict[HolderInterface, frozenset[str]] = {
    HolderInterface.ER_COLLET: frozenset({
        "drilling", "milling", "reaming", "threading", "engraving", "tapping",
    }),
    HolderInterface.HYDRAULIC_CHUCK: frozenset({
        "drilling", "milling", "reaming",
    }),
    HolderInterface.SHRINK_FIT: frozenset({
        "drilling", "milling", "reaming",
    }),
    HolderInterface.MILLING_CHUCK: frozenset({
        "milling", "drilling",
    }),
    HolderInterface.SIDE_LOCK: frozenset({
        "drilling", "milling",
    }),
    HolderInterface.FACE_MILL_HOLDER: frozenset({
        "milling",
    }),
    HolderInterface.BORING_HOLDER: frozenset({
        "boring",
    }),
    HolderInterface.TAPPING_CHUCK: frozenset({
        "tapping", "threading",
    }),
    HolderInterface.TURNING_TOOLHOLDER: frozenset({
        "turning", "grooving", "threading", "boring",
    }),
}

# Holder types that accept indexable inserts in a pocket
_INSERT_HOLDER_TYPES: frozenset[HolderInterface] = frozenset({
    HolderInterface.TURNING_TOOLHOLDER,
    HolderInterface.BORING_HOLDER,
    HolderInterface.FACE_MILL_HOLDER,
})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _result(
    failures: list[str],
    unknowns: list[str],
    passes: list[str],
) -> CompatibilityResult:
    if failures:
        unknown_note = ["UNKNOWN checks present: " + "; ".join(unknowns)] if unknowns else []
        return CompatibilityResult(
            status=CompatibilityStatus.FAIL,
            reasons=failures + unknown_note,
        )
    if unknowns:
        return CompatibilityResult(
            status=CompatibilityStatus.UNKNOWN,
            reasons=unknowns,
        )
    return CompatibilityResult(
        status=CompatibilityStatus.PASS,
        reasons=passes,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def check_tool_holder_compatibility(
    tool: CuttingToolCatalogRecord,
    holder: ToolHolderRecord,
) -> CompatibilityResult:
    """Check whether a solid/rotary tool fits and operates correctly in a holder.

    Checks performed (in order):
    1. Shank diameter within holder capacity.
    2. Cutting length within holder max reach (when both are present).
    3. Operation compatibility between tool and holder type.
    4. Coolant requirement satisfiable by holder.

    Missing required dimensions produce UNKNOWN, not PASS.
    """
    failures: list[str] = []
    unknowns: list[str] = []
    passes: list[str] = []

    # 1. Shank diameter
    if tool.shank_diameter_mm is None:
        unknowns.append(
            "tool.shank_diameter_mm is None — cannot verify dimensional fit"
        )
    else:
        d = tool.shank_diameter_mm
        lo = holder.capacity.min_shank_mm
        hi = holder.capacity.max_shank_mm
        if d < lo or d > hi:
            failures.append(
                f"Shank {d:.3g}mm outside holder range [{lo}–{hi}]mm"
            )
        else:
            passes.append(f"Shank {d:.3g}mm within holder range [{lo}–{hi}]mm")

    # 2. Reach vs cutting length
    if holder.capacity.max_tool_reach_mm is not None:
        if tool.cutting_length_mm is None:
            unknowns.append(
                "tool.cutting_length_mm is None — reach clearance unverified"
            )
        elif tool.cutting_length_mm > holder.capacity.max_tool_reach_mm:
            failures.append(
                f"Cutting length {tool.cutting_length_mm}mm exceeds holder "
                f"max reach {holder.capacity.max_tool_reach_mm}mm"
            )
        else:
            passes.append(
                f"Cutting length {tool.cutting_length_mm}mm within reach "
                f"{holder.capacity.max_tool_reach_mm}mm"
            )

    # 3. Operation compatibility
    tool_ops = {op.lower() for op in tool.supported_operations}
    holder_ops = _HOLDER_OPERATIONS.get(holder.holder_type, frozenset())
    overlap = tool_ops & holder_ops
    if not overlap:
        failures.append(
            f"No operation overlap: tool={sorted(tool_ops)}, "
            f"holder_type={holder.holder_type!r} supports {sorted(holder_ops)}"
        )
    else:
        passes.append(f"Supported operations overlap: {sorted(overlap)}")

    # 4. Coolant
    if tool.through_coolant is True:
        if holder.supports_coolant is False:
            failures.append(
                "Tool requires through-coolant; holder.supports_coolant=False"
            )
        elif holder.supports_coolant is None:
            unknowns.append(
                "tool.through_coolant=True but holder.supports_coolant is None"
            )
        else:
            passes.append("Through-coolant requirement satisfied by holder")

    return _result(failures, unknowns, passes)


def check_insert_holder_compatibility(
    insert: InsertRecord,
    holder: ToolHolderRecord,
) -> CompatibilityResult:
    """Check whether an ISO indexable insert seats correctly in a holder pocket.

    Checks performed (in order):
    1. Holder type must accept indexable inserts.
    2. Insert shape must match holder pocket shape (when holder pocket is specified).
    3. Insert IC must match holder pocket IC (when both are specified).
    4. Cutting direction (hand) must be compatible.
    5. Operation compatibility.

    Missing pocket dimensions produce UNKNOWN, not PASS.
    """
    failures: list[str] = []
    unknowns: list[str] = []
    passes: list[str] = []

    # 1. Holder must accept inserts
    if holder.holder_type not in _INSERT_HOLDER_TYPES:
        return CompatibilityResult(
            status=CompatibilityStatus.FAIL,
            reasons=[
                f"Holder type {holder.holder_type!r} does not accept indexable inserts "
                f"(requires one of: {sorted(str(t) for t in _INSERT_HOLDER_TYPES)})"
            ],
        )

    # 2. Insert shape vs pocket shape
    if holder.insert_shape_code is None:
        unknowns.append(
            "holder.insert_shape_code is None — shape compatibility unverified"
        )
    elif insert.geometry.shape_code != holder.insert_shape_code:
        failures.append(
            f"Insert shape {insert.geometry.shape_code!r} does not match "
            f"holder pocket {holder.insert_shape_code!r}"
        )
    else:
        passes.append(
            f"Insert shape {insert.geometry.shape_code!r} matches holder pocket"
        )

    # 3. Insert IC vs pocket IC
    if holder.insert_ic_mm is not None and insert.geometry.ic_mm is None:
        unknowns.append(
            "insert.geometry.ic_mm is None — IC dimensional fit unverified"
        )
    elif holder.insert_ic_mm is not None and insert.geometry.ic_mm is not None:
        if insert.geometry.ic_mm != holder.insert_ic_mm:
            failures.append(
                f"Insert IC {insert.geometry.ic_mm}mm does not match "
                f"holder pocket IC {holder.insert_ic_mm}mm"
            )
        else:
            passes.append(f"Insert IC {insert.geometry.ic_mm}mm matches holder pocket")

    # 4. Cutting direction / hand
    if holder.insert_hand is not None and insert.geometry.cutting_direction is not None:
        insert_hand = insert.geometry.cutting_direction.upper()
        holder_hand = holder.insert_hand.upper()
        # N (neutral) is compatible with any holder hand
        if holder_hand != "N" and insert_hand != "N" and insert_hand != holder_hand:
            failures.append(
                f"Insert hand {insert_hand!r} incompatible with "
                f"holder hand {holder_hand!r}"
            )
        else:
            passes.append(
                f"Hand compatible: insert={insert_hand!r}, holder={holder_hand!r}"
            )

    # 5. Operation compatibility
    insert_ops = {op.lower() for op in insert.supported_operations}
    holder_ops = _HOLDER_OPERATIONS.get(holder.holder_type, frozenset())
    overlap = insert_ops & holder_ops
    if not overlap:
        failures.append(
            f"No operation overlap: insert={sorted(insert_ops)}, "
            f"holder_type={holder.holder_type!r} supports {sorted(holder_ops)}"
        )
    else:
        passes.append(f"Supported operations overlap: {sorted(overlap)}")

    return _result(failures, unknowns, passes)
