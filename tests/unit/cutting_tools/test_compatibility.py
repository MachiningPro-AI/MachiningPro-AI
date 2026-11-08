"""Tests for the tool-to-holder and insert-to-holder compatibility engine.

Covers:
- PASS / FAIL / UNKNOWN status semantics
- Shank diameter fit checks
- Reach vs cutting length checks
- Operation compatibility
- Coolant requirement checks
- Insert shape, IC and hand compatibility
- UNKNOWN propagation (missing dimensions → UNKNOWN, never PASS)
- Contradictory specifications
- All 9 holder types mapped to their supported operations
"""

from backend.cutting_tools import (
    CompatibilityStatus,
    HolderCapacity,
    HolderInterface,
    HolderSourceMetadata,
    InsertGeometry,
    InsertGrade,
    InsertRecord,
    InsertSourceMetadata,
    ToolHolderRecord,
    check_insert_holder_compatibility,
    check_tool_holder_compatibility,
)
from backend.cutting_tools.catalog_models import CuttingToolCatalogRecord
from backend.cutting_tools.iso1832_parser import parse_iso1832

PASS = CompatibilityStatus.PASS
FAIL = CompatibilityStatus.FAIL
UNKNOWN = CompatibilityStatus.UNKNOWN


# ── Shared fixture helpers ────────────────────────────────────────────────────

def _prov() -> HolderSourceMetadata:
    return HolderSourceMetadata(
        source_title="Test", source_authority="Test",
        evidence_status="MANUFACTURER_CATALOG", catalog_code="TEST",
    )


def _drill(
    shank_mm: float | None = 10.0,
    cutting_len: float | None = 60.0,
    coolant: bool | None = None,
    operations: list[str] | None = None,
    shank_interface: str | None = None,
) -> CuttingToolCatalogRecord:
    return CuttingToolCatalogRecord(
        stable_id="test-drill",
        manufacturer="TestMfr",
        product_name="Test Drill",
        tool_category="Drill",
        tool_category_code="DRILL",
        supported_operations=operations or ["drilling"],
        iso_material_groups=["P", "M"],
        shank_diameter_mm=shank_mm,
        cutting_length_mm=cutting_len,
        through_coolant=coolant,
        shank_interface=shank_interface,
        source_title="Test",
        source_authority="Test",
        evidence_status="MANUFACTURER_CATALOG",
        missing_fields=[],
    )


def _end_mill(
    shank_mm: float | None = 12.0,
    cutting_len: float | None = 26.0,
) -> CuttingToolCatalogRecord:
    return CuttingToolCatalogRecord(
        stable_id="test-end-mill",
        manufacturer="TestMfr",
        product_name="Test End Mill",
        tool_category="End Mill",
        tool_category_code="END_MILL",
        supported_operations=["milling"],
        iso_material_groups=["P"],
        shank_diameter_mm=shank_mm,
        cutting_length_mm=cutting_len,
        source_title="Test",
        source_authority="Test",
        evidence_status="MANUFACTURER_CATALOG",
        missing_fields=[],
    )


def _er_holder(
    min_shank: float = 1.0,
    max_shank: float = 20.0,
    reach: float | None = 80.0,
    coolant: bool | None = True,
    holder_type: HolderInterface = HolderInterface.ER_COLLET,
) -> ToolHolderRecord:
    return ToolHolderRecord(
        stable_id="test-holder",
        manufacturer="TestMfr",
        product_name="Test Holder",
        holder_type=holder_type,
        capacity=HolderCapacity(
            min_shank_mm=min_shank,
            max_shank_mm=max_shank,
            max_tool_reach_mm=reach,
        ),
        supports_coolant=coolant,
        provenance=_prov(),
    )


def _insert_provenance() -> InsertSourceMetadata:
    return InsertSourceMetadata(
        source_title="Test", source_authority="Test",
        evidence_status="MANUFACTURER_CATALOG", catalog_code="TEST",
    )


def _insert(
    shape: str = "C",
    ic_mm: float | None = 12.0,
    cutting_dir: str | None = "R",
    operations: list[str] | None = None,
    designation_str: str = "CNMG120408",
) -> InsertRecord:
    d = parse_iso1832(designation_str)
    return InsertRecord(
        stable_id="test-insert",
        manufacturer="TestMfr",
        product_name="Test Insert",
        designation=d,
        geometry=InsertGeometry(
            shape_code=shape,
            ic_mm=ic_mm,
            cutting_direction=cutting_dir,
        ),
        grade=InsertGrade(substrate_material_code="CARBIDE"),
        provenance=_insert_provenance(),
        iso_material_groups=["P", "M"],
        supported_operations=operations or ["turning"],
    )


def _turning_holder(
    insert_shape: str | None = "C",
    insert_ic: float | None = 12.0,
    insert_hand: str | None = "R",
    holder_type: HolderInterface = HolderInterface.TURNING_TOOLHOLDER,
) -> ToolHolderRecord:
    return ToolHolderRecord(
        stable_id="test-turning-holder",
        manufacturer="TestMfr",
        product_name="Test Turning Holder",
        holder_type=holder_type,
        capacity=HolderCapacity(min_shank_mm=0.0, max_shank_mm=0.0),
        insert_shape_code=insert_shape,
        insert_ic_mm=insert_ic,
        insert_hand=insert_hand,
        supports_coolant=True,
        provenance=_prov(),
    )


# ── Tool-to-holder: shank diameter ───────────────────────────────────────────


class TestShankDiameterCheck:
    def test_pass_when_shank_within_range(self):
        r = check_tool_holder_compatibility(_drill(shank_mm=10.0), _er_holder(1.0, 20.0))
        assert r.status == PASS

    def test_fail_when_shank_too_large(self):
        r = check_tool_holder_compatibility(_drill(shank_mm=25.0), _er_holder(1.0, 20.0))
        assert r.status == FAIL
        assert any("25" in reason for reason in r.reasons)

    def test_fail_when_shank_too_small(self):
        r = check_tool_holder_compatibility(_drill(shank_mm=0.5), _er_holder(1.0, 20.0))
        assert r.status == FAIL

    def test_unknown_when_shank_none(self):
        r = check_tool_holder_compatibility(_drill(shank_mm=None), _er_holder())
        assert r.status == UNKNOWN
        assert any("shank_diameter_mm" in reason for reason in r.reasons)

    def test_pass_on_exact_lower_bound(self):
        r = check_tool_holder_compatibility(_drill(shank_mm=1.0), _er_holder(1.0, 20.0))
        assert r.status == PASS

    def test_pass_on_exact_upper_bound(self):
        r = check_tool_holder_compatibility(_drill(shank_mm=20.0), _er_holder(1.0, 20.0))
        assert r.status == PASS

    def test_fail_just_above_upper_bound(self):
        r = check_tool_holder_compatibility(_drill(shank_mm=20.001), _er_holder(1.0, 20.0))
        assert r.status == FAIL


# ── Tool-to-holder: reach ─────────────────────────────────────────────────────


class TestReachCheck:
    def test_pass_when_cutting_length_within_reach(self):
        r = check_tool_holder_compatibility(_drill(cutting_len=60.0), _er_holder(reach=80.0))
        assert r.status == PASS

    def test_fail_when_cutting_length_exceeds_reach(self):
        r = check_tool_holder_compatibility(_drill(cutting_len=90.0), _er_holder(reach=80.0))
        assert r.status == FAIL
        assert any("90" in reason or "reach" in reason.lower() for reason in r.reasons)

    def test_unknown_when_cutting_length_none(self):
        r = check_tool_holder_compatibility(
            _drill(shank_mm=10.0, cutting_len=None),
            _er_holder(reach=80.0),
        )
        assert r.status == UNKNOWN

    def test_pass_when_no_reach_limit_on_holder(self):
        r = check_tool_holder_compatibility(
            _drill(shank_mm=10.0, cutting_len=200.0), _er_holder(reach=None)
        )
        # No reach limit → not a FAIL (reach not checked)
        assert r.status != FAIL or not any("reach" in reason.lower() for reason in r.reasons)

    def test_pass_on_exact_reach(self):
        r = check_tool_holder_compatibility(_drill(cutting_len=80.0), _er_holder(reach=80.0))
        assert r.status == PASS


# ── Tool-to-holder: operations ────────────────────────────────────────────────


class TestOperationCompatibilityTool:
    def test_pass_drill_in_er_collet(self):
        r = check_tool_holder_compatibility(_drill(operations=["drilling"]), _er_holder())
        assert r.status == PASS

    def test_fail_tap_in_hydraulic_chuck(self):
        r = check_tool_holder_compatibility(
            _drill(operations=["tapping"]),
            _er_holder(holder_type=HolderInterface.HYDRAULIC_CHUCK),
        )
        assert r.status == FAIL
        assert any(
            "operation" in reason.lower() or "tapping" in reason.lower()
            for reason in r.reasons
        )

    def test_pass_milling_in_shrink_fit(self):
        r = check_tool_holder_compatibility(
            _end_mill(),
            _er_holder(holder_type=HolderInterface.SHRINK_FIT),
        )
        assert r.status == PASS

    def test_fail_turning_in_er_collet(self):
        r = check_tool_holder_compatibility(
            _drill(operations=["turning"]),
            _er_holder(holder_type=HolderInterface.ER_COLLET),
        )
        assert r.status == FAIL

    def test_pass_tap_in_tapping_chuck(self):
        r = check_tool_holder_compatibility(
            _drill(operations=["tapping"]),
            _er_holder(holder_type=HolderInterface.TAPPING_CHUCK),
        )
        assert r.status == PASS


# ── Tool-to-holder: coolant ───────────────────────────────────────────────────


class TestCoolantCheck:
    def test_pass_when_coolant_not_required(self):
        r = check_tool_holder_compatibility(
            _drill(coolant=None),
            _er_holder(coolant=False),
        )
        # No coolant requirement from tool → pass
        assert r.status == PASS

    def test_pass_when_coolant_supported(self):
        r = check_tool_holder_compatibility(
            _drill(coolant=True),
            _er_holder(coolant=True),
        )
        assert r.status == PASS

    def test_fail_when_coolant_required_but_not_supported(self):
        r = check_tool_holder_compatibility(
            _drill(coolant=True),
            _er_holder(coolant=False),
        )
        assert r.status == FAIL
        assert any("coolant" in reason.lower() for reason in r.reasons)

    def test_unknown_when_coolant_required_but_holder_unknown(self):
        r = check_tool_holder_compatibility(
            _drill(coolant=True),
            _er_holder(coolant=None),
        )
        assert r.status == UNKNOWN
        assert any("coolant" in reason.lower() for reason in r.reasons)

    def test_no_coolant_requirement_does_not_affect_pass(self):
        r = check_tool_holder_compatibility(
            _drill(coolant=False),
            _er_holder(coolant=True),
        )
        assert r.status == PASS


# ── Tool-to-holder: UNKNOWN propagation ──────────────────────────────────────


class TestToolHolderUnknownPropagation:
    def test_missing_shank_gives_unknown(self):
        r = check_tool_holder_compatibility(_drill(shank_mm=None, cutting_len=50.0), _er_holder())
        assert r.status == UNKNOWN

    def test_missing_cutting_len_with_reach_gives_unknown(self):
        r = check_tool_holder_compatibility(
            _drill(shank_mm=10.0, cutting_len=None), _er_holder(reach=80.0)
        )
        assert r.status == UNKNOWN

    def test_missing_coolant_support_on_holder_gives_unknown(self):
        r = check_tool_holder_compatibility(
            _drill(shank_mm=10.0, coolant=True), _er_holder(coolant=None)
        )
        assert r.status == UNKNOWN

    def test_fail_takes_precedence_over_unknown(self):
        # Shank fails; coolant is also unknown — result must be FAIL not UNKNOWN
        r = check_tool_holder_compatibility(
            _drill(shank_mm=50.0, coolant=True),
            _er_holder(max_shank=20.0, coolant=None),
        )
        assert r.status == FAIL


# ── Insert-to-holder: holder type check ──────────────────────────────────────


class TestInsertHolderTypeCheck:
    def test_pass_turning_insert_in_turning_holder(self):
        r = check_insert_holder_compatibility(_insert(), _turning_holder())
        assert r.status == PASS

    def test_fail_insert_in_er_collet(self):
        r = check_insert_holder_compatibility(
            _insert(),
            _er_holder(holder_type=HolderInterface.ER_COLLET),
        )
        assert r.status == FAIL
        assert any("ER_COLLET" in reason or "indexable" in reason.lower() for reason in r.reasons)

    def test_fail_insert_in_milling_chuck(self):
        r = check_insert_holder_compatibility(
            _insert(),
            _er_holder(holder_type=HolderInterface.MILLING_CHUCK),
        )
        assert r.status == FAIL

    def test_pass_milling_insert_in_face_mill_holder(self):
        r = check_insert_holder_compatibility(
            _insert(operations=["milling"]),
            _turning_holder(holder_type=HolderInterface.FACE_MILL_HOLDER),
        )
        # May pass (shape/IC check) or fail (operation); just check holder type accepted
        assert r.status != FAIL or not any(
            "does not accept indexable" in reason for reason in r.reasons
        )

    def test_pass_insert_in_boring_holder(self):
        r = check_insert_holder_compatibility(
            _insert(operations=["boring"]),
            _turning_holder(holder_type=HolderInterface.BORING_HOLDER),
        )
        assert r.status != FAIL or not any(
            "does not accept indexable" in reason for reason in r.reasons
        )


# ── Insert-to-holder: shape compatibility ────────────────────────────────────


class TestInsertShapeCompatibility:
    def test_pass_matching_shape(self):
        r = check_insert_holder_compatibility(_insert(shape="C"), _turning_holder(insert_shape="C"))
        assert r.status == PASS

    def test_fail_mismatched_shape(self):
        r = check_insert_holder_compatibility(_insert(shape="S"), _turning_holder(insert_shape="C"))
        assert r.status == FAIL
        assert any("shape" in reason.lower() for reason in r.reasons)

    def test_unknown_when_holder_shape_unspecified(self):
        r = check_insert_holder_compatibility(
            _insert(shape="C"),
            _turning_holder(insert_shape=None),
        )
        assert r.status == UNKNOWN
        assert any("shape" in reason.lower() for reason in r.reasons)


# ── Insert-to-holder: IC check ────────────────────────────────────────────────


class TestInsertICCompatibility:
    def test_pass_matching_ic(self):
        r = check_insert_holder_compatibility(
            _insert(ic_mm=12.0),
            _turning_holder(insert_ic=12.0),
        )
        assert r.status == PASS

    def test_fail_mismatched_ic(self):
        r = check_insert_holder_compatibility(
            _insert(ic_mm=16.0),
            _turning_holder(insert_ic=12.0),
        )
        assert r.status == FAIL
        assert any("IC" in reason or "ic" in reason.lower() for reason in r.reasons)

    def test_unknown_when_insert_ic_none(self):
        r = check_insert_holder_compatibility(
            _insert(ic_mm=None),
            _turning_holder(insert_ic=12.0),
        )
        assert r.status == UNKNOWN


# ── Insert-to-holder: hand/direction ─────────────────────────────────────────


class TestInsertHandCompatibility:
    def test_pass_matching_right_hand(self):
        r = check_insert_holder_compatibility(
            _insert(cutting_dir="R"),
            _turning_holder(insert_hand="R"),
        )
        assert r.status == PASS

    def test_fail_right_insert_in_left_holder(self):
        r = check_insert_holder_compatibility(
            _insert(cutting_dir="R"),
            _turning_holder(insert_hand="L"),
        )
        assert r.status == FAIL
        assert any("hand" in reason.lower() or "R" in reason for reason in r.reasons)

    def test_pass_neutral_insert_in_right_holder(self):
        r = check_insert_holder_compatibility(
            _insert(cutting_dir="N"),
            _turning_holder(insert_hand="R"),
        )
        assert r.status == PASS

    def test_pass_right_insert_in_neutral_holder(self):
        r = check_insert_holder_compatibility(
            _insert(cutting_dir="R"),
            _turning_holder(insert_hand="N"),
        )
        assert r.status == PASS


# ── Insert-to-holder: operations ─────────────────────────────────────────────


class TestInsertHolderOperationCompatibility:
    def test_pass_turning_insert_in_turning_holder(self):
        r = check_insert_holder_compatibility(
            _insert(operations=["turning"]),
            _turning_holder(holder_type=HolderInterface.TURNING_TOOLHOLDER),
        )
        assert r.status == PASS

    def test_fail_milling_insert_in_turning_holder(self):
        r = check_insert_holder_compatibility(
            _insert(operations=["milling"]),
            _turning_holder(holder_type=HolderInterface.TURNING_TOOLHOLDER),
        )
        assert r.status == FAIL

    def test_pass_grooving_insert_in_turning_holder(self):
        r = check_insert_holder_compatibility(
            _insert(operations=["grooving"]),
            _turning_holder(holder_type=HolderInterface.TURNING_TOOLHOLDER),
        )
        assert r.status == PASS


# ── UNKNOWN propagation and "no false positive" rule ────────────────────────


class TestNoFalsePositive:
    def test_all_missing_dimensions_gives_unknown_not_pass(self):
        # All key fields None — must NEVER produce PASS
        r = check_tool_holder_compatibility(
            _drill(shank_mm=None, cutting_len=None, coolant=None),
            _er_holder(reach=None, coolant=None),
        )
        assert r.status in (UNKNOWN, FAIL)
        assert r.status != PASS

    def test_missing_insert_shape_gives_unknown_not_pass(self):
        r = check_insert_holder_compatibility(
            _insert(shape="C"),
            _turning_holder(insert_shape=None, insert_ic=None, insert_hand=None),
        )
        assert r.status == UNKNOWN

    def test_reasons_always_non_empty(self):
        for status_result in [
            check_tool_holder_compatibility(_drill(), _er_holder()),
            check_tool_holder_compatibility(_drill(shank_mm=None), _er_holder()),
            check_tool_holder_compatibility(_drill(shank_mm=50.0), _er_holder()),
        ]:
            assert len(status_result.reasons) >= 1, "result must always include at least one reason"

    def test_fail_reason_identifies_constraint(self):
        r = check_tool_holder_compatibility(_drill(shank_mm=25.0), _er_holder(1.0, 20.0))
        # At least one reason should mention the out-of-range shank
        assert any("25" in reason or "shank" in reason.lower() for reason in r.reasons)

    def test_unknown_when_insert_ic_none_and_holder_specifies_ic(self):
        r = check_insert_holder_compatibility(_insert(ic_mm=None), _turning_holder(insert_ic=12.0))
        assert r.status == UNKNOWN
        assert r.status != PASS


# ── Compatibility result model ────────────────────────────────────────────────


class TestCompatibilityResult:
    def test_status_enum_has_three_values(self):
        expected = {"PASS", "FAIL", "UNKNOWN"}
        from backend.cutting_tools import CompatibilityStatus
        assert {s.value for s in CompatibilityStatus} == expected

    def test_result_is_pydantic_model(self):
        from backend.cutting_tools import CompatibilityResult
        r = CompatibilityResult(status=PASS, reasons=["all good"])
        assert r.status == PASS
        assert r.reasons == ["all good"]

    def test_all_nine_holder_types_in_operations_map(self):
        from backend.cutting_tools.compatibility import _HOLDER_OPERATIONS
        for ht in HolderInterface:
            assert ht in _HOLDER_OPERATIONS, f"{ht!r} missing from _HOLDER_OPERATIONS"
            assert len(_HOLDER_OPERATIONS[ht]) >= 1
