"""Tests for backend.machine_library.material_context.

Covers:
- ISO material group enum completeness (P/M/K/N/S/H/UNKNOWN)
- MaterialMachiningContext construction and validation
- evaluate_material_context PASS / FAIL / UNKNOWN verdicts
- Operation capability flags (turning, milling, drilling, grinding, edm)
- Derived operations (tapping, boring, reaming, threading)
- Spindle speed, power, torque constraint checks
- Missing spindle data yields UNKNOWN (not PASS)
- ISO group recorded in result but does not gate verdict
- Advisory warnings for ISO S and H groups
- PASS result carries certification disclaimer semantics
- Contradictory source: declared capable but spindle data absent
"""

from __future__ import annotations

import pytest

from backend.machine_library.enums import MachineClass
from backend.machine_library.material_context import (
    MachiningOperation,
    MaterialCompatibilityVerdict,
    MaterialCondition,
    MaterialISOGroup,
    MaterialMachiningContext,
    evaluate_material_context,
)
from backend.machine_library.models import (
    MachineCapability,
    MachineCatalogRecord,
    MachineEnvelope,
    MachineSourceMetadata,
    MachineSpindleSpecification,
)

# ---------------------------------------------------------------------------
# Minimal record builders
# ---------------------------------------------------------------------------


def _src() -> MachineSourceMetadata:
    return MachineSourceMetadata(source_title="Test Source")


def _vmc_record(
    *,
    max_rpm: int | None = 10_000,
    power_kw: float | None = 15.0,
    torque_nm: float | None = None,
    milling_capable: bool = True,
    drilling_capable: bool = True,
    turning_capable: bool = False,
    grinding_capable: bool = False,
    edm_capable: bool = False,
    capable_tapping: bool | None = True,
    capable_boring: bool | None = True,
    capable_reaming: bool | None = True,
    capable_threading: bool | None = None,
) -> MachineCatalogRecord:
    return MachineCatalogRecord(
        stable_id="test-vmc",
        manufacturer="TestCo",
        model="VMC-100",
        capability=MachineCapability(
            machine_class=MachineClass.THREE_AXIS_VMC,
            controlled_axes=3,
            milling_capable=milling_capable,
            drilling_capable=drilling_capable,
            turning_capable=turning_capable,
            grinding_capable=grinding_capable,
            edm_capable=edm_capable,
            capable_tapping=capable_tapping,
            capable_boring=capable_boring,
            capable_reaming=capable_reaming,
            capable_threading=capable_threading,
        ),
        spindle=MachineSpindleSpecification(
            max_rpm=max_rpm,
            power_kw=power_kw,
            torque_nm=torque_nm,
        ),
        envelope=MachineEnvelope(),
        source=_src(),
    )


def _lathe_record(
    *,
    max_rpm: int | None = 5_000,
    power_kw: float | None = 11.0,
    torque_nm: float | None = None,
    turning_capable: bool = True,
    milling_capable: bool = False,
    capable_threading: bool | None = True,
) -> MachineCatalogRecord:
    return MachineCatalogRecord(
        stable_id="test-lathe",
        manufacturer="TestCo",
        model="Lathe-100",
        capability=MachineCapability(
            machine_class=MachineClass.CNC_LATHE,
            controlled_axes=2,
            turning_capable=turning_capable,
            milling_capable=milling_capable,
            drilling_capable=False,
            capable_threading=capable_threading,
        ),
        spindle=MachineSpindleSpecification(
            max_rpm=max_rpm,
            power_kw=power_kw,
            torque_nm=torque_nm,
        ),
        envelope=MachineEnvelope(),
        source=_src(),
    )


def _grinder_record() -> MachineCatalogRecord:
    return MachineCatalogRecord(
        stable_id="test-grinder",
        manufacturer="TestCo",
        model="Grinder-100",
        capability=MachineCapability(
            machine_class=MachineClass.SURFACE_GRINDER,
            controlled_axes=3,
            grinding_capable=True,
            milling_capable=False,
            turning_capable=False,
            drilling_capable=False,
        ),
        spindle=MachineSpindleSpecification(max_rpm=3_600),
        envelope=MachineEnvelope(),
        source=_src(),
    )


def _edm_wire_record() -> MachineCatalogRecord:
    return MachineCatalogRecord(
        stable_id="test-wire-edm",
        manufacturer="TestCo",
        model="WireEDM-100",
        capability=MachineCapability(
            machine_class=MachineClass.WIRE_EDM,
            controlled_axes=4,
            edm_capable=True,
            milling_capable=False,
            turning_capable=False,
            drilling_capable=False,
        ),
        spindle=MachineSpindleSpecification(),
        envelope=MachineEnvelope(),
        source=_src(),
    )


def _ctx(
    operation: MachiningOperation,
    iso_group: MaterialISOGroup = MaterialISOGroup.P,
    **kw,
) -> MaterialMachiningContext:
    return MaterialMachiningContext(
        iso_group=iso_group,
        operation=operation,
        **kw,
    )


# ===========================================================================
# TestMaterialISOGroupEnum
# ===========================================================================


class TestMaterialISOGroupEnum:
    def test_all_six_iso_groups_present(self):
        values = {g.value for g in MaterialISOGroup}
        assert {"P", "M", "K", "N", "S", "H"}.issubset(values)

    def test_unknown_group_present(self):
        assert MaterialISOGroup.UNKNOWN.value == "UNKNOWN"

    @pytest.mark.parametrize("group", list(MaterialISOGroup))
    def test_all_groups_are_string(self, group):
        assert isinstance(group.value, str)


# ===========================================================================
# TestMachiningOperationEnum
# ===========================================================================


class TestMachiningOperationEnum:
    def test_primary_operations_present(self):
        ops = {op.value for op in MachiningOperation}
        for expected in ("TURNING", "MILLING", "DRILLING", "GRINDING", "WIRE_EDM", "SINKER_EDM"):
            assert expected in ops

    def test_derived_operations_present(self):
        ops = {op.value for op in MachiningOperation}
        for expected in ("TAPPING", "BORING", "REAMING", "THREADING"):
            assert expected in ops

    def test_unknown_present(self):
        assert MachiningOperation.UNKNOWN.value == "UNKNOWN"


# ===========================================================================
# TestMaterialMachiningContextModel
# ===========================================================================


class TestMaterialMachiningContextModel:
    def test_minimal_context(self):
        ctx = MaterialMachiningContext(
            iso_group=MaterialISOGroup.P,
            operation=MachiningOperation.MILLING,
        )
        assert ctx.iso_group is MaterialISOGroup.P
        assert ctx.operation is MachiningOperation.MILLING
        assert ctx.min_spindle_speed_rpm is None
        assert ctx.min_spindle_power_kw is None
        assert ctx.min_spindle_torque_nm is None

    def test_context_with_spindle_requirements(self):
        ctx = MaterialMachiningContext(
            iso_group=MaterialISOGroup.S,
            operation=MachiningOperation.MILLING,
            min_spindle_speed_rpm=8_000,
            min_spindle_power_kw=18.5,
            min_spindle_torque_nm=120.0,
        )
        assert ctx.min_spindle_speed_rpm == 8_000
        assert ctx.min_spindle_power_kw == 18.5
        assert ctx.min_spindle_torque_nm == 120.0

    def test_context_with_grade_ref(self):
        ctx = MaterialMachiningContext(
            iso_group=MaterialISOGroup.M,
            operation=MachiningOperation.TURNING,
            material_grade_ref="1.4301",
        )
        assert ctx.material_grade_ref == "1.4301"

    def test_context_with_condition(self):
        ctx = MaterialMachiningContext(
            iso_group=MaterialISOGroup.H,
            operation=MachiningOperation.GRINDING,
            material_condition=MaterialCondition.HARDENED,
        )
        assert ctx.material_condition is MaterialCondition.HARDENED


# ===========================================================================
# TestEvaluateMaterialContextPass
# ===========================================================================


class TestEvaluateMaterialContextPass:
    def test_milling_on_vmc_passes(self):
        r = evaluate_material_context(_ctx(MachiningOperation.MILLING), _vmc_record())
        assert r.verdict is MaterialCompatibilityVerdict.PASS

    def test_drilling_on_vmc_passes(self):
        r = evaluate_material_context(_ctx(MachiningOperation.DRILLING), _vmc_record())
        assert r.verdict is MaterialCompatibilityVerdict.PASS

    def test_tapping_on_vmc_passes(self):
        r = evaluate_material_context(_ctx(MachiningOperation.TAPPING), _vmc_record())
        assert r.verdict is MaterialCompatibilityVerdict.PASS

    def test_boring_on_vmc_passes(self):
        r = evaluate_material_context(_ctx(MachiningOperation.BORING), _vmc_record())
        assert r.verdict is MaterialCompatibilityVerdict.PASS

    def test_reaming_on_vmc_passes(self):
        r = evaluate_material_context(_ctx(MachiningOperation.REAMING), _vmc_record())
        assert r.verdict is MaterialCompatibilityVerdict.PASS

    def test_turning_on_lathe_passes(self):
        r = evaluate_material_context(_ctx(MachiningOperation.TURNING), _lathe_record())
        assert r.verdict is MaterialCompatibilityVerdict.PASS

    def test_grinding_on_grinder_passes(self):
        r = evaluate_material_context(_ctx(MachiningOperation.GRINDING), _grinder_record())
        assert r.verdict is MaterialCompatibilityVerdict.PASS

    def test_wire_edm_on_edm_passes(self):
        r = evaluate_material_context(_ctx(MachiningOperation.WIRE_EDM), _edm_wire_record())
        assert r.verdict is MaterialCompatibilityVerdict.PASS

    def test_pass_carries_stable_id(self):
        r = evaluate_material_context(_ctx(MachiningOperation.MILLING), _vmc_record())
        assert r.machine_stable_id == "test-vmc"

    def test_pass_carries_operation(self):
        r = evaluate_material_context(_ctx(MachiningOperation.MILLING), _vmc_record())
        assert r.operation is MachiningOperation.MILLING

    def test_pass_carries_iso_group(self):
        ctx = _ctx(MachiningOperation.MILLING, iso_group=MaterialISOGroup.K)
        r = evaluate_material_context(ctx, _vmc_record())
        assert r.iso_group is MaterialISOGroup.K
        assert r.verdict is MaterialCompatibilityVerdict.PASS

    def test_pass_all_iso_groups_on_capable_machine(self):
        for group in (MaterialISOGroup.P, MaterialISOGroup.M, MaterialISOGroup.K,
                      MaterialISOGroup.N, MaterialISOGroup.S, MaterialISOGroup.H):
            ctx = _ctx(MachiningOperation.MILLING, iso_group=group)
            r = evaluate_material_context(ctx, _vmc_record())
            assert r.verdict is MaterialCompatibilityVerdict.PASS, (
                f"Expected PASS for ISO group {group}"
            )

    def test_spindle_speed_within_limit_passes(self):
        ctx = _ctx(MachiningOperation.MILLING, min_spindle_speed_rpm=5_000)
        r = evaluate_material_context(ctx, _vmc_record(max_rpm=10_000))
        assert r.verdict is MaterialCompatibilityVerdict.PASS

    def test_spindle_power_within_limit_passes(self):
        ctx = _ctx(MachiningOperation.MILLING, min_spindle_power_kw=10.0)
        r = evaluate_material_context(ctx, _vmc_record(power_kw=15.0))
        assert r.verdict is MaterialCompatibilityVerdict.PASS

    def test_spindle_torque_within_limit_passes(self):
        ctx = _ctx(MachiningOperation.MILLING, min_spindle_torque_nm=50.0)
        r = evaluate_material_context(ctx, _vmc_record(torque_nm=100.0))
        assert r.verdict is MaterialCompatibilityVerdict.PASS


# ===========================================================================
# TestEvaluateMaterialContextFail
# ===========================================================================


class TestEvaluateMaterialContextFail:
    def test_milling_on_lathe_fails(self):
        r = evaluate_material_context(_ctx(MachiningOperation.MILLING), _lathe_record())
        assert r.verdict is MaterialCompatibilityVerdict.FAIL

    def test_turning_on_vmc_fails(self):
        r = evaluate_material_context(_ctx(MachiningOperation.TURNING), _vmc_record())
        assert r.verdict is MaterialCompatibilityVerdict.FAIL

    def test_grinding_on_vmc_fails(self):
        r = evaluate_material_context(_ctx(MachiningOperation.GRINDING), _vmc_record())
        assert r.verdict is MaterialCompatibilityVerdict.FAIL

    def test_wire_edm_on_vmc_fails(self):
        r = evaluate_material_context(_ctx(MachiningOperation.WIRE_EDM), _vmc_record())
        assert r.verdict is MaterialCompatibilityVerdict.FAIL

    def test_tapping_explicitly_false_fails(self):
        r = evaluate_material_context(
            _ctx(MachiningOperation.TAPPING),
            _vmc_record(capable_tapping=False),
        )
        assert r.verdict is MaterialCompatibilityVerdict.FAIL

    def test_boring_explicitly_false_fails(self):
        r = evaluate_material_context(
            _ctx(MachiningOperation.BORING),
            _vmc_record(capable_boring=False),
        )
        assert r.verdict is MaterialCompatibilityVerdict.FAIL

    def test_spindle_speed_too_low_fails(self):
        ctx = _ctx(MachiningOperation.MILLING, min_spindle_speed_rpm=15_000)
        r = evaluate_material_context(ctx, _vmc_record(max_rpm=10_000))
        assert r.verdict is MaterialCompatibilityVerdict.FAIL
        assert "SPINDLE_SPEED_INSUFFICIENT" in " ".join(r.reasons)

    def test_spindle_power_too_low_fails(self):
        ctx = _ctx(MachiningOperation.MILLING, min_spindle_power_kw=30.0)
        r = evaluate_material_context(ctx, _vmc_record(power_kw=15.0))
        assert r.verdict is MaterialCompatibilityVerdict.FAIL
        assert "SPINDLE_POWER_INSUFFICIENT" in " ".join(r.reasons)

    def test_spindle_torque_too_low_fails(self):
        ctx = _ctx(MachiningOperation.MILLING, min_spindle_torque_nm=200.0)
        r = evaluate_material_context(ctx, _vmc_record(torque_nm=100.0))
        assert r.verdict is MaterialCompatibilityVerdict.FAIL
        assert "SPINDLE_TORQUE_INSUFFICIENT" in " ".join(r.reasons)

    def test_fail_carries_stable_id(self):
        r = evaluate_material_context(_ctx(MachiningOperation.MILLING), _lathe_record())
        assert r.machine_stable_id == "test-lathe"
        assert r.is_fail

    def test_fail_reason_non_empty(self):
        r = evaluate_material_context(_ctx(MachiningOperation.TURNING), _vmc_record())
        assert len(r.reasons) > 0


# ===========================================================================
# TestEvaluateMaterialContextUnknown
# ===========================================================================


class TestEvaluateMaterialContextUnknown:
    def test_unknown_operation_yields_unknown(self):
        r = evaluate_material_context(
            _ctx(MachiningOperation.UNKNOWN),
            _vmc_record(),
        )
        assert r.verdict is MaterialCompatibilityVerdict.UNKNOWN

    def test_missing_spindle_speed_data_yields_unknown(self):
        ctx = _ctx(MachiningOperation.MILLING, min_spindle_speed_rpm=5_000)
        r = evaluate_material_context(ctx, _vmc_record(max_rpm=None))
        assert r.verdict is MaterialCompatibilityVerdict.UNKNOWN
        assert any("SPINDLE_DATA_ABSENT" in reason for reason in r.reasons)

    def test_missing_spindle_power_data_yields_unknown(self):
        ctx = _ctx(MachiningOperation.MILLING, min_spindle_power_kw=10.0)
        r = evaluate_material_context(ctx, _vmc_record(power_kw=None))
        assert r.verdict is MaterialCompatibilityVerdict.UNKNOWN
        assert any("SPINDLE_DATA_ABSENT" in reason for reason in r.reasons)

    def test_missing_spindle_torque_data_yields_unknown(self):
        ctx = _ctx(MachiningOperation.MILLING, min_spindle_torque_nm=50.0)
        r = evaluate_material_context(ctx, _vmc_record(torque_nm=None))
        assert r.verdict is MaterialCompatibilityVerdict.UNKNOWN
        assert any("SPINDLE_DATA_ABSENT" in reason for reason in r.reasons)

    def test_unknown_carries_iso_group(self):
        ctx = _ctx(MachiningOperation.UNKNOWN, iso_group=MaterialISOGroup.S)
        r = evaluate_material_context(ctx, _vmc_record())
        assert r.iso_group is MaterialISOGroup.S

    def test_unknown_is_not_pass(self):
        ctx = _ctx(MachiningOperation.MILLING, min_spindle_speed_rpm=5_000)
        r = evaluate_material_context(ctx, _vmc_record(max_rpm=None))
        assert not r.is_pass

    def test_tapping_subflagnone_yields_unknown(self):
        # capable_tapping=None means not declared; primary (drilling) True
        r = evaluate_material_context(
            _ctx(MachiningOperation.TAPPING),
            _vmc_record(capable_tapping=None),
        )
        # capable_tapping not declared → UNKNOWN (insufficient data), not PASS
        assert r.verdict is MaterialCompatibilityVerdict.UNKNOWN


# ===========================================================================
# TestISOGroupPlanningContext
# ===========================================================================


class TestISOGroupPlanningContext:
    """ISO group must be recorded but must not alter PASS/FAIL on its own."""

    def test_iso_p_milling_passes(self):
        r = evaluate_material_context(
            _ctx(MachiningOperation.MILLING, iso_group=MaterialISOGroup.P),
            _vmc_record(),
        )
        assert r.verdict is MaterialCompatibilityVerdict.PASS

    def test_iso_s_milling_passes_on_capable_machine(self):
        r = evaluate_material_context(
            _ctx(MachiningOperation.MILLING, iso_group=MaterialISOGroup.S),
            _vmc_record(),
        )
        assert r.verdict is MaterialCompatibilityVerdict.PASS

    def test_iso_s_adds_advisory_warning(self):
        r = evaluate_material_context(
            _ctx(MachiningOperation.MILLING, iso_group=MaterialISOGroup.S),
            _vmc_record(),
        )
        assert r.verdict is MaterialCompatibilityVerdict.PASS
        assert any("ISO_S" in w for w in r.warnings)

    def test_iso_h_adds_advisory_warning(self):
        r = evaluate_material_context(
            _ctx(MachiningOperation.GRINDING, iso_group=MaterialISOGroup.H),
            _grinder_record(),
        )
        assert r.verdict is MaterialCompatibilityVerdict.PASS
        assert any("ISO_H" in w for w in r.warnings)

    def test_iso_h_hard_turning_capable_machine_passes(self):
        # H material with TURNING operation on a turning-capable machine MUST pass —
        # hard turning is a valid process; ISO group must not block capable machine.
        r = evaluate_material_context(
            _ctx(MachiningOperation.TURNING, iso_group=MaterialISOGroup.H),
            _lathe_record(),
        )
        assert r.verdict is MaterialCompatibilityVerdict.PASS

    def test_iso_group_does_not_affect_fail_for_wrong_operation(self):
        # Grinding on a VMC fails regardless of ISO group
        for group in (MaterialISOGroup.P, MaterialISOGroup.S, MaterialISOGroup.H):
            r = evaluate_material_context(
                _ctx(MachiningOperation.GRINDING, iso_group=group),
                _vmc_record(),
            )
            assert r.verdict is MaterialCompatibilityVerdict.FAIL, (
                f"Expected FAIL for ISO group {group} with GRINDING on VMC"
            )


# ===========================================================================
# TestContradictorySourceRecord
# ===========================================================================


class TestContradictorySourceRecord:
    """Machine declares capable but spindle spec absent — must yield UNKNOWN."""

    def test_declared_milling_capable_no_spindle_rpm_with_requirement_unknown(self):
        ctx = _ctx(MachiningOperation.MILLING, min_spindle_speed_rpm=4_000)
        r = evaluate_material_context(ctx, _vmc_record(max_rpm=None))
        assert r.verdict is MaterialCompatibilityVerdict.UNKNOWN

    def test_declared_turning_capable_no_power_with_requirement_unknown(self):
        ctx = _ctx(MachiningOperation.TURNING, min_spindle_power_kw=5.0)
        r = evaluate_material_context(ctx, _lathe_record(power_kw=None))
        assert r.verdict is MaterialCompatibilityVerdict.UNKNOWN

    def test_multiple_absent_spindle_fields_accumulate_reasons(self):
        ctx = _ctx(
            MachiningOperation.MILLING,
            min_spindle_speed_rpm=5_000,
            min_spindle_power_kw=10.0,
            min_spindle_torque_nm=50.0,
        )
        r = evaluate_material_context(ctx, _vmc_record(max_rpm=None, power_kw=None, torque_nm=None))
        assert r.verdict is MaterialCompatibilityVerdict.UNKNOWN
        absent_count = sum(1 for reason in r.reasons if "SPINDLE_DATA_ABSENT" in reason)
        assert absent_count == 3


# ===========================================================================
# TestResultProperties
# ===========================================================================


class TestResultProperties:
    def test_is_pass_true(self):
        r = evaluate_material_context(_ctx(MachiningOperation.MILLING), _vmc_record())
        assert r.is_pass
        assert not r.is_fail
        assert not r.is_unknown

    def test_is_fail_true(self):
        r = evaluate_material_context(_ctx(MachiningOperation.TURNING), _vmc_record())
        assert r.is_fail
        assert not r.is_pass
        assert not r.is_unknown

    def test_is_unknown_true(self):
        r = evaluate_material_context(_ctx(MachiningOperation.UNKNOWN), _vmc_record())
        assert r.is_unknown
        assert not r.is_pass
        assert not r.is_fail


# ===========================================================================
# TestSeedCatalogRecordsContextEvaluation
# ===========================================================================


class TestSeedCatalogRecordsContextEvaluation:
    """Smoke-test evaluate_material_context against real seed catalog records."""

    def test_haas_vf2ss_milling_p_steel_passes(self):
        from backend.machine_library.seed_catalog import seed_machine_library
        records = {r.stable_id: r for r in seed_machine_library()}
        haas = records["ml-haas-vf-2ss"]
        ctx = MaterialMachiningContext(
            iso_group=MaterialISOGroup.P,
            operation=MachiningOperation.MILLING,
        )
        r = evaluate_material_context(ctx, haas)
        assert r.verdict is MaterialCompatibilityVerdict.PASS

    def test_haas_st20_lathe_turning_passes(self):
        from backend.machine_library.seed_catalog import seed_machine_library
        records = {r.stable_id: r for r in seed_machine_library()}
        lathe = records["ml-haas-st-20"]
        ctx = MaterialMachiningContext(
            iso_group=MaterialISOGroup.P,
            operation=MachiningOperation.TURNING,
        )
        r = evaluate_material_context(ctx, lathe)
        assert r.verdict is MaterialCompatibilityVerdict.PASS

    def test_fanuc_wire_edm_evaluates_correctly(self):
        from backend.machine_library.seed_catalog import seed_machine_library
        records = {r.stable_id: r for r in seed_machine_library()}
        edm = records["ml-fanuc-robocut-c400ia"]
        ctx = MaterialMachiningContext(
            iso_group=MaterialISOGroup.H,
            operation=MachiningOperation.WIRE_EDM,
        )
        r = evaluate_material_context(ctx, edm)
        assert r.verdict is MaterialCompatibilityVerdict.PASS

    def test_haas_vf2ss_turning_fails(self):
        from backend.machine_library.seed_catalog import seed_machine_library
        records = {r.stable_id: r for r in seed_machine_library()}
        haas = records["ml-haas-vf-2ss"]
        ctx = MaterialMachiningContext(
            iso_group=MaterialISOGroup.P,
            operation=MachiningOperation.TURNING,
        )
        r = evaluate_material_context(ctx, haas)
        assert r.verdict is MaterialCompatibilityVerdict.FAIL

    def test_pass_is_not_certification(self):
        from backend.machine_library.seed_catalog import seed_machine_library
        records = {r.stable_id: r for r in seed_machine_library()}
        haas = records["ml-haas-vf-2ss"]
        ctx = MaterialMachiningContext(
            iso_group=MaterialISOGroup.S,
            operation=MachiningOperation.MILLING,
            min_spindle_speed_rpm=6_000,
        )
        r = evaluate_material_context(ctx, haas)
        # PASS means capabilities are consistent — not a machining approval
        assert r.verdict is MaterialCompatibilityVerdict.PASS
        # ISO S warning must be present
        assert any("ISO_S" in w for w in r.warnings)
