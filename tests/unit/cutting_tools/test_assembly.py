"""Tests for ToolAssemblyRecord, assembly compatibility and machining readiness.

Covers:
- Assembly model construction (geometry, components, provenance)
- Assembly geometry consistency checks
- Tool-holder-insert compatibility via validate_assembly
- Machining readiness: operation, material, dimensions, machine interface,
  coolant, runout
- UNKNOWN propagation (missing data never yields PASS)
- FAIL precedence over UNKNOWN
- Invalid dimension detection
- Contradictory specifications
- All 9 operation families (drilling, milling, turning, boring, threading,
  reaming, grooving, grinding, EDM)
- Missing machine information integration point
- Missing material information integration point
"""
import pytest

from backend.cutting_tools import (
    CompatibilityStatus,
    HolderCapacity,
    HolderInterface,
    HolderSourceMetadata,
    InsertGeometry,
    InsertGrade,
    InsertRecord,
    InsertSourceMetadata,
    MachiningReadinessRequest,
    ToolAssemblyCompatibility,
    ToolAssemblyGeometry,
    ToolAssemblyRecord,
    ToolAssemblySourceMetadata,
    ToolHolderRecord,
    assess_machining_readiness,
    check_assembly_geometry,
    validate_assembly,
)
from backend.cutting_tools.catalog_models import CuttingToolCatalogRecord
from backend.cutting_tools.iso1832_parser import parse_iso1832

PASS = CompatibilityStatus.PASS
FAIL = CompatibilityStatus.FAIL
UNKNOWN = CompatibilityStatus.UNKNOWN


# ── Fixture helpers ───────────────────────────────────────────────────────────

def _prov_holder() -> HolderSourceMetadata:
    return HolderSourceMetadata(
        source_title="Test", source_authority="Test",
        evidence_status="MANUFACTURER_CATALOG", catalog_code="TEST",
    )


def _prov_insert() -> InsertSourceMetadata:
    return InsertSourceMetadata(
        source_title="Test", source_authority="Test",
        evidence_status="MANUFACTURER_CATALOG", catalog_code="TEST",
    )


def _prov_assembly() -> ToolAssemblySourceMetadata:
    return ToolAssemblySourceMetadata(
        source_title="Test", source_authority="Test",
        evidence_status="MANUFACTURER_CATALOG",
    )


def _drill(
    shank_mm: float | None = 10.0,
    cutting_len: float | None = 60.0,
    coolant: bool | None = None,
    operations: list[str] | None = None,
    cutting_diameter: float | None = 10.0,
    iso_groups: list[str] | None = None,
) -> CuttingToolCatalogRecord:
    return CuttingToolCatalogRecord(
        stable_id="test-drill-10mm",
        manufacturer="TestMfr",
        product_name="Test Drill 10mm",
        tool_category="Drill",
        tool_category_code="DRILL",
        supported_operations=operations or ["drilling"],
        iso_material_groups=iso_groups or ["P", "M"],
        shank_diameter_mm=shank_mm,
        cutting_length_mm=cutting_len,
        cutting_diameter_mm=cutting_diameter,
        through_coolant=coolant,
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
    spindle: str | None = "BT40",
    runout: float | None = 0.005,
) -> ToolHolderRecord:
    return ToolHolderRecord(
        stable_id="test-er32",
        manufacturer="TestMfr",
        product_name="Test ER32",
        holder_type=holder_type,
        spindle_interface=spindle,
        capacity=HolderCapacity(
            min_shank_mm=min_shank,
            max_shank_mm=max_shank,
            max_tool_reach_mm=reach,
            max_runout_mm=runout,
        ),
        supports_coolant=coolant,
        provenance=_prov_holder(),
    )


def _geometry(
    shank_mm: float | None = 10.0,
    clamping: float | None = 25.0,
    gauge: float | None = 100.0,
    stick_out: float | None = 70.0,
    overall: float | None = 150.0,
    reach: float | None = 65.0,
    holder_dia: float | None = 40.0,
    spindle: str | None = "BT40",
    coolant: bool | None = True,
) -> ToolAssemblyGeometry:
    return ToolAssemblyGeometry(
        shank_diameter_mm=shank_mm,
        clamping_length_mm=clamping,
        gauge_length_mm=gauge,
        tool_stick_out_mm=stick_out,
        overall_assembly_length_mm=overall,
        effective_reach_mm=reach,
        holder_diameter_mm=holder_dia,
        spindle_interface=spindle,
        coolant_enabled=coolant,
    )


def _assembly(
    tool: CuttingToolCatalogRecord | None = None,
    holder: ToolHolderRecord | None = None,
    geometry: ToolAssemblyGeometry | None = None,
    insert: InsertRecord | None = None,
) -> ToolAssemblyRecord:
    return ToolAssemblyRecord(
        stable_id="test-assembly-01",
        tool=tool or _drill(),
        holder=holder or _er_holder(),
        insert=insert,
        geometry=geometry or _geometry(),
        provenance=_prov_assembly(),
    )


def _insert(
    shape: str = "C",
    ic_mm: float | None = 12.0,
    cutting_dir: str | None = "R",
    operations: list[str] | None = None,
) -> InsertRecord:
    d = parse_iso1832("CNMG120408")
    return InsertRecord(
        stable_id="test-insert",
        manufacturer="TestMfr",
        product_name="Test Insert",
        designation=d,
        geometry=InsertGeometry(shape_code=shape, ic_mm=ic_mm, cutting_direction=cutting_dir),
        grade=InsertGrade(substrate_material_code="CARBIDE"),
        provenance=_prov_insert(),
        iso_material_groups=["P", "M"],
        supported_operations=operations or ["turning"],
    )


def _request(**kwargs) -> MachiningReadinessRequest:
    defaults = dict(operation="drilling")
    defaults.update(kwargs)
    return MachiningReadinessRequest(**defaults)


# ── ToolAssemblyRecord model ──────────────────────────────────────────────────


class TestToolAssemblyRecord:
    def test_basic_construction(self):
        a = _assembly()
        assert a.stable_id == "test-assembly-01"
        assert a.tool.stable_id == "test-drill-10mm"
        assert a.holder.stable_id == "test-er32"
        assert a.insert is None

    def test_components_without_insert(self):
        a = _assembly()
        types = {c.component_type for c in a.components}
        assert "TOOL" in types
        assert "HOLDER" in types
        assert "INSERT" not in types

    def test_components_with_insert(self):
        a = _assembly(insert=_insert())
        types = {c.component_type for c in a.components}
        assert "INSERT" in types

    def test_geometry_all_fields(self):
        g = _geometry()
        assert g.shank_diameter_mm == 10.0
        assert g.gauge_length_mm == 100.0
        assert g.spindle_interface == "BT40"

    def test_validation_none_before_validate(self):
        a = _assembly()
        assert a.validation is None

    def test_provenance_stored(self):
        a = _assembly()
        assert a.provenance.evidence_status == "MANUFACTURER_CATALOG"


# ── Assembly geometry checks ──────────────────────────────────────────────────


class TestCheckAssemblyGeometry:
    def test_valid_geometry_passes(self):
        r = check_assembly_geometry(_assembly())
        assert r.status == PASS

    def test_zero_stick_out_fails(self):
        a = _assembly(geometry=_geometry(stick_out=0.0))
        r = check_assembly_geometry(a)
        assert r.status == FAIL
        assert any("stick_out" in reason.lower() for reason in r.reasons)

    def test_negative_stick_out_fails(self):
        a = _assembly(geometry=_geometry(stick_out=-5.0))
        r = check_assembly_geometry(a)
        assert r.status == FAIL

    def test_reach_less_than_cutting_length_fails(self):
        # cutting_length=60mm, effective_reach=30mm
        a = _assembly(
            tool=_drill(cutting_len=60.0),
            geometry=_geometry(reach=30.0),
        )
        r = check_assembly_geometry(a)
        assert r.status == FAIL
        assert any("reach" in reason.lower() for reason in r.reasons)

    def test_reach_none_with_cutting_length_gives_unknown(self):
        a = _assembly(
            tool=_drill(cutting_len=60.0),
            geometry=_geometry(reach=None),
        )
        r = check_assembly_geometry(a)
        assert r.status == UNKNOWN

    def test_stick_out_exceeds_gauge_length_fails(self):
        a = _assembly(geometry=_geometry(gauge=50.0, stick_out=70.0))
        r = check_assembly_geometry(a)
        assert r.status == FAIL
        assert any("gauge" in reason.lower() or "stick" in reason.lower() for reason in r.reasons)

    def test_zero_overall_length_fails(self):
        a = _assembly(geometry=_geometry(overall=0.0))
        r = check_assembly_geometry(a)
        assert r.status == FAIL

    def test_contradictory_shank_diameter_fails(self):
        # Assembly says 12mm, tool says 10mm
        a = _assembly(
            tool=_drill(shank_mm=10.0),
            geometry=_geometry(shank_mm=12.0),
        )
        r = check_assembly_geometry(a)
        assert r.status == FAIL
        assert any("contradictory" in reason.lower() for reason in r.reasons)

    def test_consistent_shank_diameter_passes(self):
        a = _assembly(
            tool=_drill(shank_mm=10.0),
            geometry=_geometry(shank_mm=10.0),
        )
        r = check_assembly_geometry(a)
        assert r.status == PASS

    def test_contradictory_spindle_interface_fails(self):
        a = _assembly(
            holder=_er_holder(spindle="BT40"),
            geometry=_geometry(spindle="HSK-A63"),
        )
        r = check_assembly_geometry(a)
        assert r.status == FAIL
        assert any("BT40" in reason or "HSK" in reason for reason in r.reasons)

    def test_coolant_enabled_but_holder_no_coolant_fails(self):
        a = _assembly(
            holder=_er_holder(coolant=False),
            geometry=_geometry(coolant=True),
        )
        r = check_assembly_geometry(a)
        assert r.status == FAIL

    def test_coolant_enabled_holder_unknown_gives_unknown(self):
        a = _assembly(
            holder=_er_holder(coolant=None),
            geometry=_geometry(coolant=True),
        )
        r = check_assembly_geometry(a)
        assert r.status == UNKNOWN

    def test_no_geometry_dimensions_gives_pass(self):
        # Drill with no cutting_length declared → reach check is skipped
        a = ToolAssemblyRecord(
            stable_id="bare",
            tool=_drill(cutting_len=None),
            holder=_er_holder(),
            geometry=ToolAssemblyGeometry(),
            provenance=_prov_assembly(),
        )
        r = check_assembly_geometry(a)
        assert r.status == PASS


# ── validate_assembly ─────────────────────────────────────────────────────────


class TestValidateAssembly:
    def test_valid_assembly_passes(self):
        v = validate_assembly(_assembly())
        assert v.overall_status == PASS

    def test_validation_result_has_all_checks(self):
        v = validate_assembly(_assembly())
        assert v.tool_holder_check is not None
        assert v.geometry_check is not None
        assert v.insert_holder_check is None  # no insert

    def test_validation_with_insert_has_insert_check(self):
        turning_holder = ToolHolderRecord(
            stable_id="test-turning",
            manufacturer="TestMfr",
            product_name="Turning Holder",
            holder_type=HolderInterface.TURNING_TOOLHOLDER,
            capacity=HolderCapacity(min_shank_mm=0.0, max_shank_mm=0.0),
            insert_shape_code="C",
            insert_ic_mm=12.0,
            insert_hand="R",
            supports_coolant=True,
            provenance=_prov_holder(),
        )
        turning_tool = CuttingToolCatalogRecord(
            stable_id="test-turning-tool",
            manufacturer="TestMfr",
            product_name="Test Turning Tool",
            tool_category="Turning Insert",
            tool_category_code="TURNING_INSERT",
            supported_operations=["turning"],
            iso_material_groups=["P"],
            source_title="Test",
            source_authority="Test",
            evidence_status="MANUFACTURER_CATALOG",
            missing_fields=[],
        )
        a = _assembly(
            tool=turning_tool,
            holder=turning_holder,
            geometry=ToolAssemblyGeometry(),
            insert=_insert(),
        )
        v = validate_assembly(a)
        assert v.insert_holder_check is not None

    def test_shank_fail_propagates_to_overall_fail(self):
        a = _assembly(
            tool=_drill(shank_mm=50.0),
            holder=_er_holder(max_shank=20.0),
        )
        v = validate_assembly(a)
        assert v.overall_status == FAIL

    def test_geometry_fail_propagates_to_overall_fail(self):
        a = _assembly(geometry=_geometry(stick_out=-1.0))
        v = validate_assembly(a)
        assert v.overall_status == FAIL

    def test_all_reasons_non_empty(self):
        v = validate_assembly(_assembly())
        assert len(v.all_reasons) >= 1

    def test_fail_takes_precedence_over_unknown(self):
        # Shank fails; cutting_len is None → geometry would be UNKNOWN
        a = _assembly(
            tool=_drill(shank_mm=50.0, cutting_len=None),
            holder=_er_holder(max_shank=20.0),
            geometry=_geometry(reach=None),
        )
        v = validate_assembly(a)
        assert v.overall_status == FAIL


# ── Machining readiness — operation checks ────────────────────────────────────


class TestReadinessOperation:
    def test_pass_drill_for_drilling(self):
        r = assess_machining_readiness(
            _assembly(tool=_drill(operations=["drilling"])),
            _request(operation="drilling"),
        )
        assert r.operation_check.result.status == PASS

    def test_fail_drill_for_milling(self):
        r = assess_machining_readiness(
            _assembly(tool=_drill(operations=["drilling"])),
            _request(operation="milling"),
        )
        assert r.operation_check.result.status == FAIL

    def test_case_insensitive_operation(self):
        r = assess_machining_readiness(
            _assembly(tool=_drill(operations=["drilling"])),
            _request(operation="DRILLING"),
        )
        assert r.operation_check.result.status == PASS

    def test_all_nine_operation_families(self):
        ops = [
            "drilling", "milling", "turning", "boring", "threading",
            "reaming", "grooving", "grinding", "edm",
        ]
        for op in ops:
            tool = _drill(operations=[op])
            r = assess_machining_readiness(_assembly(tool=tool), _request(operation=op))
            assert r.operation_check.result.status == PASS, (
                f"Expected PASS for operation {op!r}"
            )


# ── Machining readiness — material group ─────────────────────────────────────


class TestReadinessMaterial:
    def test_pass_known_supported_group(self):
        r = assess_machining_readiness(
            _assembly(tool=_drill(iso_groups=["P", "M"])),
            _request(workpiece_material_group="P"),
        )
        assert r.material_check.status == PASS

    def test_fail_unsupported_group(self):
        r = assess_machining_readiness(
            _assembly(tool=_drill(iso_groups=["P"])),
            _request(workpiece_material_group="H"),
        )
        assert r.material_check.status == FAIL

    def test_unknown_when_group_not_specified(self):
        r = assess_machining_readiness(
            _assembly(),
            _request(workpiece_material_group=None),
        )
        assert r.material_check.status == UNKNOWN

    def test_unknown_propagates_through_overall(self):
        r = assess_machining_readiness(
            _assembly(),
            _request(workpiece_material_group=None, spindle_interface_required=None),
        )
        # At least UNKNOWN overall because of missing material and machine info
        assert r.overall.status in (UNKNOWN, FAIL)

    def test_fail_invalid_iso_code(self):
        r = assess_machining_readiness(
            _assembly(),
            _request(workpiece_material_group="X"),
        )
        assert r.material_check.status == FAIL

    def test_material_library_integration_point(self):
        """workpiece_material_group=None signals unlinked Material Library."""
        r = assess_machining_readiness(
            _assembly(),
            _request(workpiece_material_group=None),
        )
        assert any(
            "material" in reason.lower() for reason in r.material_check.reasons
        )

    def test_all_six_iso_groups_accepted(self):
        for group in ("P", "M", "K", "N", "S", "H"):
            tool = _drill(iso_groups=[group])
            r = assess_machining_readiness(
                _assembly(tool=tool),
                _request(workpiece_material_group=group),
            )
            assert r.material_check.status == PASS, f"Failed for group {group!r}"


# ── Machining readiness — dimensions ─────────────────────────────────────────


class TestReadinessDimensions:
    def test_pass_exact_cutting_diameter(self):
        r = assess_machining_readiness(
            _assembly(tool=_drill(cutting_diameter=10.0)),
            _request(required_cutting_diameter_mm=10.0),
        )
        assert r.dimension_check.status == PASS

    def test_fail_wrong_cutting_diameter(self):
        r = assess_machining_readiness(
            _assembly(tool=_drill(cutting_diameter=10.0)),
            _request(required_cutting_diameter_mm=12.0),
        )
        assert r.dimension_check.status == FAIL

    def test_unknown_cutting_diameter_when_none(self):
        r = assess_machining_readiness(
            _assembly(tool=_drill(cutting_diameter=None)),
            _request(required_cutting_diameter_mm=10.0),
        )
        assert r.dimension_check.status == UNKNOWN

    def test_pass_sufficient_reach(self):
        r = assess_machining_readiness(
            _assembly(geometry=_geometry(reach=70.0)),
            _request(required_reach_mm=50.0),
        )
        assert r.dimension_check.status == PASS

    def test_fail_insufficient_reach(self):
        r = assess_machining_readiness(
            _assembly(geometry=_geometry(reach=30.0)),
            _request(required_reach_mm=60.0),
        )
        assert r.dimension_check.status == FAIL

    def test_unknown_reach_when_not_declared(self):
        r = assess_machining_readiness(
            _assembly(geometry=_geometry(reach=None)),
            _request(required_reach_mm=50.0),
        )
        assert r.dimension_check.status == UNKNOWN

    def test_pass_sufficient_cutting_length(self):
        r = assess_machining_readiness(
            _assembly(tool=_drill(cutting_len=60.0)),
            _request(required_cutting_length_mm=50.0),
        )
        assert r.dimension_check.status == PASS

    def test_fail_insufficient_cutting_length(self):
        r = assess_machining_readiness(
            _assembly(tool=_drill(cutting_len=30.0)),
            _request(required_cutting_length_mm=50.0),
        )
        assert r.dimension_check.status == FAIL

    def test_no_dimension_requirement_passes(self):
        r = assess_machining_readiness(_assembly(), _request())
        assert r.dimension_check.status == PASS


# ── Machining readiness — machine interface ───────────────────────────────────


class TestReadinessMachineInterface:
    def test_pass_matching_spindle_interface(self):
        r = assess_machining_readiness(
            _assembly(holder=_er_holder(spindle="BT40"), geometry=_geometry(spindle="BT40")),
            _request(spindle_interface_required="BT40"),
        )
        assert r.machine_interface_check.status == PASS

    def test_fail_mismatched_spindle_interface(self):
        r = assess_machining_readiness(
            _assembly(geometry=_geometry(spindle="BT40")),
            _request(spindle_interface_required="HSK-A63"),
        )
        assert r.machine_interface_check.status == FAIL

    def test_unknown_when_not_required(self):
        r = assess_machining_readiness(
            _assembly(),
            _request(spindle_interface_required=None),
        )
        assert r.machine_interface_check.status == UNKNOWN

    def test_unknown_when_assembly_has_no_interface(self):
        r = assess_machining_readiness(
            _assembly(
                holder=_er_holder(spindle=None),
                geometry=ToolAssemblyGeometry(),
            ),
            _request(spindle_interface_required="BT40"),
        )
        assert r.machine_interface_check.status == UNKNOWN

    def test_machine_library_integration_point(self):
        """spindle_interface_required=None signals unlinked Machine Library."""
        r = assess_machining_readiness(
            _assembly(),
            _request(spindle_interface_required=None),
        )
        assert any(
            "machine" in reason.lower() or "spindle" in reason.lower()
            for reason in r.machine_interface_check.reasons
        )

    def test_case_insensitive_spindle_match(self):
        r = assess_machining_readiness(
            _assembly(geometry=_geometry(spindle="bt40")),
            _request(spindle_interface_required="BT40"),
        )
        assert r.machine_interface_check.status == PASS


# ── Machining readiness — coolant ─────────────────────────────────────────────


class TestReadinessCoolant:
    def test_pass_when_no_coolant_required(self):
        r = assess_machining_readiness(_assembly(), _request(coolant_required=None))
        assert r.coolant_check.status == PASS

    def test_pass_coolant_satisfied_by_geometry(self):
        r = assess_machining_readiness(
            _assembly(geometry=_geometry(coolant=True)),
            _request(coolant_required=True),
        )
        assert r.coolant_check.status == PASS

    def test_fail_coolant_required_geometry_disabled(self):
        r = assess_machining_readiness(
            _assembly(geometry=_geometry(coolant=False)),
            _request(coolant_required=True),
        )
        assert r.coolant_check.status == FAIL

    def test_unknown_coolant_unset_holder_unknown(self):
        r = assess_machining_readiness(
            _assembly(
                holder=_er_holder(coolant=None),
                geometry=_geometry(coolant=None),
            ),
            _request(coolant_required=True),
        )
        assert r.coolant_check.status == UNKNOWN


# ── Machining readiness — runout ──────────────────────────────────────────────


class TestReadinessRunout:
    def test_pass_runout_within_limit(self):
        r = assess_machining_readiness(
            _assembly(holder=_er_holder(runout=0.003)),
            _request(max_runout_mm=0.005),
        )
        assert r.runout_check.status == PASS

    def test_fail_runout_exceeds_limit(self):
        r = assess_machining_readiness(
            _assembly(holder=_er_holder(runout=0.010)),
            _request(max_runout_mm=0.005),
        )
        assert r.runout_check.status == FAIL

    def test_pass_when_no_runout_required(self):
        r = assess_machining_readiness(_assembly(), _request(max_runout_mm=None))
        assert r.runout_check.status == PASS

    def test_unknown_when_holder_runout_not_published(self):
        r = assess_machining_readiness(
            _assembly(holder=_er_holder(runout=None)),
            _request(max_runout_mm=0.005),
        )
        assert r.runout_check.status == UNKNOWN


# ── UNKNOWN propagation and "no false positive" rule ────────────────────────


class TestNoFalsePositiveAssembly:
    def test_missing_material_and_machine_never_passes_overall(self):
        r = assess_machining_readiness(
            _assembly(),
            _request(workpiece_material_group=None, spindle_interface_required=None),
        )
        assert r.overall.status != PASS

    def test_fail_takes_precedence_over_multiple_unknowns(self):
        # Operation fails, material is unknown, machine is unknown
        r = assess_machining_readiness(
            _assembly(tool=_drill(operations=["drilling"])),
            _request(
                operation="turning",
                workpiece_material_group=None,
                spindle_interface_required=None,
            ),
        )
        assert r.overall.status == FAIL

    def test_overall_reasons_always_non_empty(self):
        r = assess_machining_readiness(_assembly(), _request())
        assert len(r.overall.reasons) >= 1

    def test_pass_only_when_all_checks_pass(self):
        r = assess_machining_readiness(
            _assembly(
                tool=_drill(
                    operations=["drilling"],
                    cutting_diameter=10.0,
                    cutting_len=60.0,
                    iso_groups=["P"],
                ),
                holder=_er_holder(spindle="BT40", runout=0.003),
                geometry=_geometry(
                    shank_mm=10.0, reach=65.0, spindle="BT40", coolant=True,
                ),
            ),
            _request(
                operation="drilling",
                workpiece_material_group="P",
                required_cutting_diameter_mm=10.0,
                required_reach_mm=50.0,
                required_cutting_length_mm=50.0,
                spindle_interface_required="BT40",
                coolant_required=True,
                max_runout_mm=0.005,
            ),
        )
        assert r.overall.status == PASS


# ── ToolAssemblyCompatibility model ──────────────────────────────────────────


class TestToolAssemblyCompatibilityModel:
    def test_all_checks_present(self):
        r: ToolAssemblyCompatibility = assess_machining_readiness(
            _assembly(), _request()
        )
        assert r.assembly_validation is not None
        assert r.operation_check is not None
        assert r.material_check is not None
        assert r.dimension_check is not None
        assert r.machine_interface_check is not None
        assert r.coolant_check is not None
        assert r.runout_check is not None
        assert r.overall is not None

    def test_assembly_stable_id_propagated(self):
        r = assess_machining_readiness(_assembly(), _request())
        assert r.assembly_stable_id == "test-assembly-01"

    def test_request_stored_in_result(self):
        req = _request(operation="drilling", workpiece_material_group="P")
        r = assess_machining_readiness(_assembly(), req)
        assert r.request.operation == "drilling"
        assert r.request.workpiece_material_group == "P"


# ── Contradictory specifications ─────────────────────────────────────────────


class TestContradictorySpecifications:
    def test_contradictory_shank_in_assembly_geometry(self):
        # Tool has 10mm shank, geometry declares 12mm
        a = _assembly(
            tool=_drill(shank_mm=10.0),
            geometry=_geometry(shank_mm=12.0),
        )
        v = validate_assembly(a)
        assert v.overall_status == FAIL
        assert any("contradictory" in r.lower() for r in v.all_reasons)

    def test_contradictory_spindle_interface(self):
        a = _assembly(
            holder=_er_holder(spindle="BT40"),
            geometry=_geometry(spindle="CAT40"),
        )
        v = validate_assembly(a)
        assert v.overall_status == FAIL

    def test_contradictory_coolant_config(self):
        # Geometry says coolant on, holder says no coolant
        a = _assembly(
            holder=_er_holder(coolant=False),
            geometry=_geometry(coolant=True),
        )
        v = validate_assembly(a)
        assert v.geometry_check.status == FAIL


# ── All 9 holder types in readiness ──────────────────────────────────────────


class TestAllHolderTypes:
    @pytest.mark.parametrize("holder_type,operation", [
        (HolderInterface.ER_COLLET, "drilling"),
        (HolderInterface.HYDRAULIC_CHUCK, "drilling"),
        (HolderInterface.SHRINK_FIT, "milling"),
        (HolderInterface.MILLING_CHUCK, "milling"),
        (HolderInterface.SIDE_LOCK, "drilling"),
        (HolderInterface.FACE_MILL_HOLDER, "milling"),
        (HolderInterface.BORING_HOLDER, "boring"),
        (HolderInterface.TAPPING_CHUCK, "tapping"),
        (HolderInterface.TURNING_TOOLHOLDER, "turning"),
    ])
    def test_holder_type_accepts_operation(self, holder_type, operation):
        a = _assembly(
            tool=_drill(operations=[operation]),
            holder=_er_holder(holder_type=holder_type),
        )
        r = assess_machining_readiness(a, _request(operation=operation))
        assert r.operation_check.result.status == PASS
        assert r.assembly_validation.tool_holder_check.status != FAIL or not any(
            "operation" in reason.lower() for reason in
            r.assembly_validation.tool_holder_check.reasons
        )
