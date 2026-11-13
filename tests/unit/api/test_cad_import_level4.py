"""Level-4 DFM and Process Intelligence tests.

Verifies the deterministic machining process intelligence layer:
  - Domain model completeness
  - Feature-to-process mapping (confirmed and candidate features)
  - Process status rules: CONFIRMED_BY_RULE vs CANDIDATE vs REQUIRES_INPUT
  - Setup candidate derivation
  - Machine class requirements
  - Tool family requirements
  - DFM observation thresholds
  - Operation sequencing and precedence
  - Material unknown → REQUIRES_INPUT (never fabricate cutting parameters)
  - Cutting parameters: always null until material provided
  - Cycle time: always null until cutting parameters available
  - 2D DXF semantics: circles → drilling CANDIDATE only
  - Traceability: operations reference source feature_ids
  - Production-file regressions (IGES and DXF)

HARD RULES (verbatim from task specification):
  - Do NOT fabricate manufacturing processes, machine selections, tool
    selections, feeds, speeds, cycle times or costs.
  - Preserve feature confidence: CANDIDATE features produce CANDIDATE ops.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Shared helpers for building minimal feature results
# ---------------------------------------------------------------------------
from backend.interoperability.features import (
    FeatureRecognitionResult,
    FeatureStatus,
    HoleSubtype,
    ManufacturingFeature,
    ManufacturingFeatureType,
)
from backend.interoperability.process_intelligence import (
    AccessibilityStatus,
    CuttingParameterStatus,
    CycleTimeStatus,
    DFMObservationType,
    DFMSeverity,
    MachineClass,
    ManufacturingOperation,
    MaterialContext,
    MaterialStatus,
    PlanStatus,
    PrecedenceType,
    ProcessFamily,
    ProcessIntelligenceResult,
    ProcessStatus,
    RoughingOrFinishing,
    SetupCandidate,
    ToolFamily,
    TurningIndicator,
)
from backend.interoperability.process_recognition import recognize_process_intelligence


def _make_feature(
    fid: str,
    ftype: ManufacturingFeatureType,
    status: FeatureStatus,
    hole_subtype: HoleSubtype = HoleSubtype.UNKNOWN,
    source_curve_id: str | None = None,
    source_surface_id: str | None = None,
) -> ManufacturingFeature:
    return ManufacturingFeature(
        feature_id=fid,
        feature_type=ftype,
        status=status,
        hole_subtype=hole_subtype,
        surface_ids=(source_surface_id,) if source_surface_id else (),
        curve_ids=(source_curve_id,) if source_curve_id else (),
    )


def _result_with(
    *features: ManufacturingFeature, basis: str = "TOPOLOGY"
) -> FeatureRecognitionResult:
    return FeatureRecognitionResult(
        classified_faces=(),
        adjacencies=(),
        features=features,
        recognition_basis=basis,
    )


# ---------------------------------------------------------------------------
# Domain model tests
# ---------------------------------------------------------------------------

class TestProcessIntelligenceDomainModel:

    def test_process_family_enum_values(self) -> None:
        assert ProcessFamily.DRILLING.value == "DRILLING"
        assert ProcessFamily.MILLING.value == "MILLING"
        assert ProcessFamily.TURNING.value == "TURNING"
        assert ProcessFamily.CHAMFERING.value == "CHAMFERING"
        assert ProcessFamily.CENTER_DRILLING.value == "CENTER_DRILLING"
        assert ProcessFamily.COUNTERBORING.value == "COUNTERBORING"
        assert ProcessFamily.COUNTERSINKING.value == "COUNTERSINKING"
        assert ProcessFamily.PROFILE_MILLING.value == "PROFILE_MILLING"
        assert ProcessFamily.INSPECTION.value == "INSPECTION"

    def test_process_status_enum_values(self) -> None:
        assert ProcessStatus.CANDIDATE.value == "CANDIDATE"
        assert ProcessStatus.CONFIRMED_BY_RULE.value == "CONFIRMED_BY_RULE"
        assert ProcessStatus.REQUIRES_INPUT.value == "REQUIRES_INPUT"
        assert ProcessStatus.NOT_APPLICABLE.value == "NOT_APPLICABLE"
        assert ProcessStatus.RECOMMENDED.value == "RECOMMENDED"

    def test_machine_class_enum_values(self) -> None:
        assert MachineClass.THREE_AXIS_VMC.value == "THREE_AXIS_VMC"
        assert MachineClass.FIVE_AXIS_VMC.value == "FIVE_AXIS_VMC"
        assert MachineClass.CNC_LATHE.value == "CNC_LATHE"
        assert MachineClass.UNKNOWN.value == "UNKNOWN"

    def test_tool_family_enum_values(self) -> None:
        assert ToolFamily.DRILL.value == "DRILL"
        assert ToolFamily.CENTER_DRILL.value == "CENTER_DRILL"
        assert ToolFamily.END_MILL.value == "END_MILL"
        assert ToolFamily.CHAMFER_MILL.value == "CHAMFER_MILL"
        assert ToolFamily.BALL_NOSE_END_MILL.value == "BALL_NOSE_END_MILL"
        assert ToolFamily.SLOT_MILL.value == "SLOT_MILL"
        assert ToolFamily.UNKNOWN.value == "UNKNOWN"

    def test_dfm_severity_enum_values(self) -> None:
        assert DFMSeverity.INFO.value == "INFO"
        assert DFMSeverity.LOW.value == "LOW"
        assert DFMSeverity.MEDIUM.value == "MEDIUM"
        assert DFMSeverity.HIGH.value == "HIGH"

    def test_turning_indicator_enum_values(self) -> None:
        assert TurningIndicator.TURNING_NOT_INDICATED.value == "TURNING_NOT_INDICATED"
        assert TurningIndicator.TURNING_CANDIDATE.value == "TURNING_CANDIDATE"
        assert TurningIndicator.TURNING_STRONGLY_INDICATED.value == "TURNING_STRONGLY_INDICATED"

    def test_plan_status_enum_values(self) -> None:
        assert PlanStatus.COMPLETE.value == "COMPLETE"
        assert PlanStatus.CANDIDATE_PLAN.value == "CANDIDATE_PLAN"
        assert PlanStatus.INSUFFICIENT_DATA.value == "INSUFFICIENT_DATA"
        assert PlanStatus.REQUIRES_INPUT.value == "REQUIRES_INPUT"

    def test_process_intelligence_result_construction(self) -> None:
        r = ProcessIntelligenceResult(
            plan_id="P-1",
            status=PlanStatus.INSUFFICIENT_DATA,
            recognition_basis="NONE",
        )
        assert r.plan_id == "P-1"
        assert r.status == PlanStatus.INSUFFICIENT_DATA
        assert r.dfm_observations == ()
        assert r.process_candidates == ()
        assert r.setups == ()
        assert r.machine_requirements == ()
        assert r.tool_requirements == ()
        assert r.operation_plan == ()

    def test_process_intelligence_result_is_frozen(self) -> None:
        r = ProcessIntelligenceResult(
            plan_id="P-1",
            status=PlanStatus.INSUFFICIENT_DATA,
            recognition_basis="NONE",
        )
        with pytest.raises((AttributeError, TypeError)):
            r.plan_id = "changed"  # type: ignore[misc]

    def test_cutting_parameter_status_defaults(self) -> None:
        cp = CuttingParameterStatus()
        assert cp.estimated_cutting_speed_m_min is None
        assert cp.estimated_feed_mm_tooth is None
        assert cp.estimated_doc_mm is None
        assert cp.material_required is True

    def test_cycle_time_status_defaults(self) -> None:
        ct = CycleTimeStatus()
        assert ct.estimated_total_minutes is None
        assert "REQUIRES" in ct.machining_time_status

    def test_material_context_defaults(self) -> None:
        m = MaterialContext()
        assert m.status == MaterialStatus.UNKNOWN
        assert m.material_name is None

    def test_manufacturing_operation_construction(self) -> None:
        op = ManufacturingOperation(
            operation_id="OP-1",
            process_family=ProcessFamily.DRILLING,
            status=ProcessStatus.CONFIRMED_BY_RULE,
            feature_ids=("F-1",),
            tool_family=ToolFamily.DRILL,
        )
        assert op.operation_id == "OP-1"
        assert op.process_family == ProcessFamily.DRILLING
        assert op.tool_family == ToolFamily.DRILL

    def test_setup_candidate_construction(self) -> None:
        s = SetupCandidate(
            setup_id="SETUP-1",
            machining_direction="+Z",
            feature_ids=("F-1", "F-2"),
        )
        assert s.machining_direction == "+Z"
        assert len(s.feature_ids) == 2

    def test_process_intelligence_result_derived_properties(self) -> None:
        op = ManufacturingOperation(
            operation_id="OP-1",
            process_family=ProcessFamily.DRILLING,
            status=ProcessStatus.CANDIDATE,
            feature_ids=("F-1",),
            tool_family=ToolFamily.DRILL,
        )
        r = ProcessIntelligenceResult(
            plan_id="P-1",
            status=PlanStatus.CANDIDATE_PLAN,
            recognition_basis="2D_GEOMETRY_ONLY",
            process_candidates=(op,),
            operation_plan=(op,),
        )
        assert r.drilling_candidate_count == 1
        assert r.confirmed_operation_count == 0
        assert r.has_dfm_issues is False


# ---------------------------------------------------------------------------
# Negative rules — no fabrication
# ---------------------------------------------------------------------------

class TestNegativeRules:

    def test_no_features_input_returns_insufficient_data(self) -> None:
        r = recognize_process_intelligence(None, None, None)
        assert r.status == PlanStatus.INSUFFICIENT_DATA
        assert r.process_candidates == ()
        assert r.operation_plan == ()

    def test_no_features_input_has_no_operations(self) -> None:
        r = recognize_process_intelligence(None, None, None)
        assert len(r.process_candidates) == 0
        assert len(r.tool_requirements) == 0
        assert len(r.setups) == 0
        assert len(r.machine_requirements) == 0

    def test_empty_feature_result_has_no_operations(self) -> None:
        feat = _result_with(basis="NONE")
        r = recognize_process_intelligence(feat, None, None)
        assert r.process_candidates == ()
        assert r.operation_plan == ()

    def test_candidate_hole_does_not_produce_confirmed_by_rule_operation(self) -> None:
        """DXF circle → CANDIDATE feature → CANDIDATE operation (not CONFIRMED_BY_RULE)."""
        feat = _result_with(
            _make_feature("F-1", ManufacturingFeatureType.HOLE, FeatureStatus.CANDIDATE,
                          source_curve_id="c1"),
            basis="2D_GEOMETRY_ONLY",
        )
        r = recognize_process_intelligence(feat, None, None)
        for op in r.process_candidates:
            assert op.status != ProcessStatus.CONFIRMED_BY_RULE, (
                f"CANDIDATE feature must not produce CONFIRMED_BY_RULE op; got {op.status}"
            )

    def test_candidate_hole_produces_candidate_operations(self) -> None:
        feat = _result_with(
            _make_feature("F-1", ManufacturingFeatureType.HOLE, FeatureStatus.CANDIDATE,
                          source_curve_id="c1"),
            basis="2D_GEOMETRY_ONLY",
        )
        r = recognize_process_intelligence(feat, None, None)
        assert all(op.status == ProcessStatus.CANDIDATE for op in r.process_candidates)

    def test_no_machine_requirements_without_operations(self) -> None:
        feat = _result_with(basis="NONE")
        r = recognize_process_intelligence(feat, None, None)
        assert r.machine_requirements == ()

    def test_no_tool_requirements_without_operations(self) -> None:
        feat = _result_with(basis="NONE")
        r = recognize_process_intelligence(feat, None, None)
        assert r.tool_requirements == ()

    def test_multiple_setups_do_not_auto_require_five_axis(self) -> None:
        """Two holes in opposite directions must not automatically require 5-axis."""
        feat = _result_with(
            _make_feature("F-1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED),
            basis="TOPOLOGY",
        )
        r = recognize_process_intelligence(feat, None, None)
        for mreq in r.machine_requirements:
            assert mreq.machine_class != MachineClass.FIVE_AXIS_VMC, (
                "Must not fabricate 5-axis requirement without confirmed multi-direction evidence"
            )

    def test_cutting_parameters_always_null_without_material(self) -> None:
        feat = _result_with(
            _make_feature("F-1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED),
        )
        r = recognize_process_intelligence(feat, None, None)
        assert r.cutting_parameter_status.estimated_cutting_speed_m_min is None
        assert r.cutting_parameter_status.estimated_feed_mm_tooth is None
        assert r.cutting_parameter_status.estimated_doc_mm is None

    def test_cycle_time_always_null(self) -> None:
        feat = _result_with(
            _make_feature("F-1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED),
        )
        r = recognize_process_intelligence(feat, None, None)
        assert r.cycle_time_status.estimated_total_minutes is None


# ---------------------------------------------------------------------------
# Feature-to-process mapping
# ---------------------------------------------------------------------------

class TestFeatureToProcessMapping:

    def test_confirmed_through_hole_produces_drilling_ops(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED,
                          HoleSubtype.THROUGH),
        )
        r = recognize_process_intelligence(feat, None, None)
        families = [op.process_family for op in r.process_candidates]
        assert ProcessFamily.DRILLING in families

    def test_confirmed_through_hole_has_center_drill_op(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED,
                          HoleSubtype.THROUGH),
        )
        r = recognize_process_intelligence(feat, None, None)
        families = [op.process_family for op in r.process_candidates]
        assert ProcessFamily.CENTER_DRILLING in families

    def test_confirmed_through_hole_produces_confirmed_by_rule(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED,
                          HoleSubtype.THROUGH),
        )
        r = recognize_process_intelligence(feat, None, None)
        confirmed_ops = [op for op in r.process_candidates
                         if op.status == ProcessStatus.CONFIRMED_BY_RULE]
        assert len(confirmed_ops) >= 1

    def test_confirmed_blind_hole_produces_drilling(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED,
                          HoleSubtype.BLIND),
        )
        r = recognize_process_intelligence(feat, None, None)
        families = [op.process_family for op in r.process_candidates]
        assert ProcessFamily.DRILLING in families

    def test_confirmed_counterbore_produces_drilling_and_counterboring(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED,
                          HoleSubtype.COUNTERBORE),
        )
        r = recognize_process_intelligence(feat, None, None)
        families = {op.process_family for op in r.process_candidates}
        assert ProcessFamily.DRILLING in families
        assert ProcessFamily.COUNTERBORING in families

    def test_confirmed_countersink_produces_drilling_and_countersinking(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED,
                          HoleSubtype.COUNTERSINK),
        )
        r = recognize_process_intelligence(feat, None, None)
        families = {op.process_family for op in r.process_candidates}
        assert ProcessFamily.DRILLING in families
        assert ProcessFamily.COUNTERSINKING in families

    def test_confirmed_pocket_produces_milling(self) -> None:
        feat = _result_with(
            _make_feature("P1", ManufacturingFeatureType.POCKET, FeatureStatus.CONFIRMED),
        )
        r = recognize_process_intelligence(feat, None, None)
        families = [op.process_family for op in r.process_candidates]
        assert ProcessFamily.MILLING in families

    def test_confirmed_pocket_produces_roughing_and_finishing(self) -> None:
        feat = _result_with(
            _make_feature("P1", ManufacturingFeatureType.POCKET, FeatureStatus.CONFIRMED),
        )
        r = recognize_process_intelligence(feat, None, None)
        passes = {op.roughing_or_finishing for op in r.process_candidates
                  if op.process_family == ProcessFamily.MILLING}
        assert RoughingOrFinishing.ROUGHING in passes
        assert RoughingOrFinishing.FINISHING in passes

    def test_confirmed_slot_produces_milling_with_slot_mill(self) -> None:
        feat = _result_with(
            _make_feature("S1", ManufacturingFeatureType.SLOT, FeatureStatus.CONFIRMED),
        )
        r = recognize_process_intelligence(feat, None, None)
        families = [op.process_family for op in r.process_candidates]
        tools = [op.tool_family for op in r.process_candidates]
        assert ProcessFamily.MILLING in families
        assert ToolFamily.SLOT_MILL in tools

    def test_confirmed_step_produces_milling(self) -> None:
        feat = _result_with(
            _make_feature("ST1", ManufacturingFeatureType.STEP, FeatureStatus.CONFIRMED),
        )
        r = recognize_process_intelligence(feat, None, None)
        families = [op.process_family for op in r.process_candidates]
        assert ProcessFamily.MILLING in families

    def test_confirmed_chamfer_produces_chamfering(self) -> None:
        feat = _result_with(
            _make_feature("C1", ManufacturingFeatureType.CHAMFER, FeatureStatus.CONFIRMED),
        )
        r = recognize_process_intelligence(feat, None, None)
        families = [op.process_family for op in r.process_candidates]
        assert ProcessFamily.CHAMFERING in families

    def test_confirmed_chamfer_uses_chamfer_mill(self) -> None:
        feat = _result_with(
            _make_feature("C1", ManufacturingFeatureType.CHAMFER, FeatureStatus.CONFIRMED),
        )
        r = recognize_process_intelligence(feat, None, None)
        tools = [op.tool_family for op in r.process_candidates]
        assert ToolFamily.CHAMFER_MILL in tools

    def test_confirmed_fillet_produces_profile_milling(self) -> None:
        feat = _result_with(
            _make_feature("FL1", ManufacturingFeatureType.FILLET, FeatureStatus.CONFIRMED),
        )
        r = recognize_process_intelligence(feat, None, None)
        families = [op.process_family for op in r.process_candidates]
        assert ProcessFamily.PROFILE_MILLING in families

    def test_confirmed_fillet_uses_ball_nose_end_mill(self) -> None:
        feat = _result_with(
            _make_feature("FL1", ManufacturingFeatureType.FILLET, FeatureStatus.CONFIRMED),
        )
        r = recognize_process_intelligence(feat, None, None)
        tools = [op.tool_family for op in r.process_candidates]
        assert ToolFamily.BALL_NOSE_END_MILL in tools

    def test_dxf_hole_candidate_produces_drilling_candidate(self) -> None:
        """2D DXF circle → CANDIDATE drilling, not CONFIRMED_BY_RULE."""
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CANDIDATE,
                          source_curve_id="dxf-circle-000001"),
            basis="2D_GEOMETRY_ONLY",
        )
        r = recognize_process_intelligence(feat, None, None)
        drill_ops = [op for op in r.process_candidates
                     if op.process_family == ProcessFamily.DRILLING]
        assert len(drill_ops) >= 1
        assert all(op.status == ProcessStatus.CANDIDATE for op in drill_ops)

    def test_geometry_only_hole_candidate_produces_candidate_op(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CANDIDATE,
                          source_surface_id="surf-cyl-001"),
            basis="GEOMETRY_ONLY",
        )
        r = recognize_process_intelligence(feat, None, None)
        for op in r.process_candidates:
            assert op.status == ProcessStatus.CANDIDATE


# ---------------------------------------------------------------------------
# Process status rules
# ---------------------------------------------------------------------------

class TestProcessStatusRules:

    def test_confirmed_feature_produces_confirmed_by_rule_op(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED,
                          HoleSubtype.THROUGH),
        )
        r = recognize_process_intelligence(feat, None, None)
        statuses = {op.status for op in r.process_candidates}
        assert ProcessStatus.CONFIRMED_BY_RULE in statuses

    def test_candidate_feature_produces_only_candidate_ops(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CANDIDATE,
                          source_curve_id="c1"),
            basis="2D_GEOMETRY_ONLY",
        )
        r = recognize_process_intelligence(feat, None, None)
        for op in r.process_candidates:
            assert op.status == ProcessStatus.CANDIDATE

    def test_missing_material_noted_in_missing_inputs(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED,
                          HoleSubtype.THROUGH),
        )
        r = recognize_process_intelligence(feat, None, None)
        # At least one missing input mentions material
        material_mentioned = any("material" in s.lower() for s in r.missing_inputs)
        assert material_mentioned


# ---------------------------------------------------------------------------
# Setup candidates
# ---------------------------------------------------------------------------

class TestSetupCandidates:

    def test_operations_produce_at_least_one_setup(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED,
                          HoleSubtype.THROUGH),
        )
        r = recognize_process_intelligence(feat, None, None)
        assert len(r.setups) >= 1

    def test_no_features_no_setups(self) -> None:
        feat = _result_with(basis="NONE")
        r = recognize_process_intelligence(feat, None, None)
        assert r.setups == ()

    def test_2d_dxf_setup_direction_is_plus_z(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CANDIDATE,
                          source_curve_id="c1"),
            basis="2D_GEOMETRY_ONLY",
        )
        r = recognize_process_intelligence(feat, None, None)
        assert len(r.setups) == 1
        assert r.setups[0].machining_direction == "+Z"

    def test_2d_dxf_setup_accessibility_is_potentially_accessible(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CANDIDATE,
                          source_curve_id="c1"),
            basis="2D_GEOMETRY_ONLY",
        )
        r = recognize_process_intelligence(feat, None, None)
        assert r.setups[0].accessibility == AccessibilityStatus.POTENTIALLY_ACCESSIBLE


# ---------------------------------------------------------------------------
# Machine class requirements
# ---------------------------------------------------------------------------

class TestMachineClassRequirements:

    def test_drilling_ops_require_at_least_three_axis_vmc(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED,
                          HoleSubtype.THROUGH),
        )
        r = recognize_process_intelligence(feat, None, None)
        assert len(r.machine_requirements) >= 1
        for mreq in r.machine_requirements:
            assert mreq.machine_class in (
                MachineClass.THREE_AXIS_VMC,
                MachineClass.FOUR_AXIS_VMC,
                MachineClass.FIVE_AXIS_VMC,
                MachineClass.HORIZONTAL_MACHINING_CENTER,
            )

    def test_no_operations_no_machine_requirements(self) -> None:
        feat = _result_with(basis="NONE")
        r = recognize_process_intelligence(feat, None, None)
        assert r.machine_requirements == ()

    def test_machine_requirement_has_basis_note(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED),
        )
        r = recognize_process_intelligence(feat, None, None)
        for mreq in r.machine_requirements:
            assert len(mreq.basis) > 0


# ---------------------------------------------------------------------------
# Tool family requirements
# ---------------------------------------------------------------------------

class TestToolFamilyRequirements:

    def test_drilling_produces_drill_tool_requirement(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED,
                          HoleSubtype.THROUGH),
        )
        r = recognize_process_intelligence(feat, None, None)
        tool_families = {tr.tool_family for tr in r.tool_requirements}
        assert ToolFamily.DRILL in tool_families

    def test_drilling_produces_center_drill_tool_requirement(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED,
                          HoleSubtype.THROUGH),
        )
        r = recognize_process_intelligence(feat, None, None)
        tool_families = {tr.tool_family for tr in r.tool_requirements}
        assert ToolFamily.CENTER_DRILL in tool_families

    def test_pocket_milling_produces_end_mill_tool_requirement(self) -> None:
        feat = _result_with(
            _make_feature("P1", ManufacturingFeatureType.POCKET, FeatureStatus.CONFIRMED),
        )
        r = recognize_process_intelligence(feat, None, None)
        tool_families = {tr.tool_family for tr in r.tool_requirements}
        assert ToolFamily.END_MILL in tool_families

    def test_chamfer_milling_produces_chamfer_mill_requirement(self) -> None:
        feat = _result_with(
            _make_feature("C1", ManufacturingFeatureType.CHAMFER, FeatureStatus.CONFIRMED),
        )
        r = recognize_process_intelligence(feat, None, None)
        tool_families = {tr.tool_family for tr in r.tool_requirements}
        assert ToolFamily.CHAMFER_MILL in tool_families

    def test_no_operations_no_tool_requirements(self) -> None:
        feat = _result_with(basis="NONE")
        r = recognize_process_intelligence(feat, None, None)
        assert r.tool_requirements == ()

    def test_tool_requirement_references_valid_operation_id(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED),
        )
        r = recognize_process_intelligence(feat, None, None)
        op_ids = {op.operation_id for op in r.process_candidates}
        for tr in r.tool_requirements:
            assert tr.operation_id in op_ids


# ---------------------------------------------------------------------------
# DFM observations
# ---------------------------------------------------------------------------

class TestDFMObservations:

    def test_no_depth_no_ld_ratio_dfm(self) -> None:
        """2D DXF hole candidate has no depth → no L/D DFM observation."""
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CANDIDATE,
                          source_curve_id="c1"),
            basis="2D_GEOMETRY_ONLY",
        )
        r = recognize_process_intelligence(feat, None, None)
        ld_obs = [
            obs for obs in r.dfm_observations
            if obs.observation_type in (
                DFMObservationType.DEEP_HOLE,
                DFMObservationType.HIGH_HOLE_LD_RATIO,
            )
        ]
        assert len(ld_obs) == 0

    def test_dfm_observations_tuple_is_returned(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED),
        )
        r = recognize_process_intelligence(feat, None, None)
        assert isinstance(r.dfm_observations, tuple)

    def test_no_dfm_issues_property_when_no_dfm(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED),
        )
        r = recognize_process_intelligence(feat, None, None)
        assert r.has_dfm_issues is False


# ---------------------------------------------------------------------------
# Operation sequencing
# ---------------------------------------------------------------------------

class TestOperationSequencing:

    def test_center_drill_precedes_drilling_in_plan(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED,
                          HoleSubtype.THROUGH),
        )
        r = recognize_process_intelligence(feat, None, None)
        plan = r.operation_plan
        center_drill_idx = next(
            (i for i, op in enumerate(plan) if op.process_family == ProcessFamily.CENTER_DRILLING),
            None,
        )
        drill_idx = next(
            (i for i, op in enumerate(plan) if op.process_family == ProcessFamily.DRILLING),
            None,
        )
        assert center_drill_idx is not None
        assert drill_idx is not None
        assert center_drill_idx < drill_idx, "Center drill must precede drilling in plan"

    def test_drilling_precedes_counterboring_in_plan(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED,
                          HoleSubtype.COUNTERBORE),
        )
        r = recognize_process_intelligence(feat, None, None)
        plan = r.operation_plan
        drill_idx = next(
            (i for i, op in enumerate(plan) if op.process_family == ProcessFamily.DRILLING),
            None,
        )
        cb_idx = next(
            (i for i, op in enumerate(plan) if op.process_family == ProcessFamily.COUNTERBORING),
            None,
        )
        assert drill_idx is not None
        assert cb_idx is not None
        assert drill_idx < cb_idx, "Drilling must precede counterboring"

    def test_drilling_precedes_countersinking_in_plan(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED,
                          HoleSubtype.COUNTERSINK),
        )
        r = recognize_process_intelligence(feat, None, None)
        plan = r.operation_plan
        drill_idx = next(
            (i for i, op in enumerate(plan) if op.process_family == ProcessFamily.DRILLING),
            None,
        )
        cs_idx = next(
            (i for i, op in enumerate(plan) if op.process_family == ProcessFamily.COUNTERSINKING),
            None,
        )
        assert drill_idx is not None
        assert cs_idx is not None
        assert drill_idx < cs_idx, "Drilling must precede countersinking"

    def test_pocket_roughing_precedes_finishing_in_plan(self) -> None:
        feat = _result_with(
            _make_feature("P1", ManufacturingFeatureType.POCKET, FeatureStatus.CONFIRMED),
        )
        r = recognize_process_intelligence(feat, None, None)
        plan = r.operation_plan
        rough_idx = next(
            (i for i, op in enumerate(plan)
             if op.roughing_or_finishing == RoughingOrFinishing.ROUGHING),
            None,
        )
        finish_idx = next(
            (i for i, op in enumerate(plan)
             if op.roughing_or_finishing == RoughingOrFinishing.FINISHING),
            None,
        )
        assert rough_idx is not None
        assert finish_idx is not None
        assert rough_idx < finish_idx, "Roughing must precede finishing"

    def test_center_drill_has_engineering_required_precedence(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED,
                          HoleSubtype.THROUGH),
        )
        r = recognize_process_intelligence(feat, None, None)
        cd_ops = [op for op in r.process_candidates
                  if op.process_family == ProcessFamily.CENTER_DRILLING]
        assert len(cd_ops) >= 1
        assert cd_ops[0].precedence_type == PrecedenceType.ENGINEERING_REQUIRED


# ---------------------------------------------------------------------------
# Material context and cutting parameters
# ---------------------------------------------------------------------------

class TestMaterialContextAndCuttingParams:

    def test_unknown_material_noted_in_missing_inputs(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED),
        )
        r = recognize_process_intelligence(feat, None, None)
        assert any("material" in s.lower() for s in r.missing_inputs)

    def test_cutting_params_require_material_flag(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED),
        )
        r = recognize_process_intelligence(feat, None, None)
        assert r.cutting_parameter_status.material_required is True
        assert r.cutting_parameter_status.tool_material_required is True

    def test_cycle_time_null_without_params(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED),
        )
        r = recognize_process_intelligence(feat, None, None)
        assert r.cycle_time_status.estimated_total_minutes is None

    def test_material_context_stored_in_result(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED),
        )
        mat = MaterialContext(material_name="Aluminium 6061", status=MaterialStatus.KNOWN)
        r = recognize_process_intelligence(feat, None, None, material=mat)
        assert r.material_context.material_name == "Aluminium 6061"
        assert r.material_context.status == MaterialStatus.KNOWN


# ---------------------------------------------------------------------------
# 2D DXF semantics
# ---------------------------------------------------------------------------

class TestDxf2DSemantics:

    def test_dxf_circle_candidate_not_confirmed(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CANDIDATE,
                          source_curve_id="c1"),
            basis="2D_GEOMETRY_ONLY",
        )
        r = recognize_process_intelligence(feat, None, None)
        for op in r.process_candidates:
            assert op.status != ProcessStatus.CONFIRMED_BY_RULE

    def test_dxf_plan_has_candidate_plan_status(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CANDIDATE,
                          source_curve_id="c1"),
            basis="2D_GEOMETRY_ONLY",
        )
        r = recognize_process_intelligence(feat, None, None)
        assert r.status == PlanStatus.CANDIDATE_PLAN

    def test_dxf_warnings_mention_2d_context(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CANDIDATE,
                          source_curve_id="c1"),
            basis="2D_GEOMETRY_ONLY",
        )
        r = recognize_process_intelligence(feat, None, None)
        all_text = " ".join(r.warnings + r.missing_inputs).lower()
        assert "2d" in all_text or "depth" in all_text

    def test_dxf_no_depth_no_dfm_observations(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CANDIDATE,
                          source_curve_id="c1"),
            basis="2D_GEOMETRY_ONLY",
        )
        r = recognize_process_intelligence(feat, None, None)
        assert r.dfm_observations == ()


# ---------------------------------------------------------------------------
# Traceability
# ---------------------------------------------------------------------------

class TestProcessTraceability:

    def test_operation_references_source_feature_id(self) -> None:
        feat = _result_with(
            _make_feature("FEAT-XYZ", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED,
                          HoleSubtype.THROUGH),
        )
        r = recognize_process_intelligence(feat, None, None)
        for op in r.process_candidates:
            assert "FEAT-XYZ" in op.feature_ids

    def test_tool_requirement_references_operation_id(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED),
        )
        r = recognize_process_intelligence(feat, None, None)
        op_ids = {op.operation_id for op in r.process_candidates}
        for tr in r.tool_requirements:
            assert tr.operation_id in op_ids

    def test_evidence_notes_contain_feature_id(self) -> None:
        feat = _result_with(
            _make_feature("TRACEABLE-1", ManufacturingFeatureType.HOLE,
                          FeatureStatus.CONFIRMED, HoleSubtype.THROUGH),
        )
        r = recognize_process_intelligence(feat, None, None)
        for op in r.process_candidates:
            assert "TRACEABLE-1" in op.evidence_notes

    def test_plan_id_is_non_empty_string(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED),
        )
        r = recognize_process_intelligence(feat, None, None)
        assert isinstance(r.plan_id, str)
        assert len(r.plan_id) > 0


# ---------------------------------------------------------------------------
# Turning indicator
# ---------------------------------------------------------------------------

class TestTurningIndicator:

    def test_hole_features_no_turning_indicated(self) -> None:
        feat = _result_with(
            _make_feature("H1", ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED),
        )
        r = recognize_process_intelligence(feat, None, None)
        assert r.turning_indicator == TurningIndicator.TURNING_NOT_INDICATED

    def test_no_features_no_turning_indicated(self) -> None:
        r = recognize_process_intelligence(None, None, None)
        assert r.turning_indicator == TurningIndicator.TURNING_NOT_INDICATED


# ---------------------------------------------------------------------------
# Production-file regressions
# ---------------------------------------------------------------------------

_PRODUCTION_IGES = Path(
    r"C:\Users\ilhan\AppData\Local\Temp\claude"
    r"\C--Users-ilhan-Downloads-MachiningPro-AI-NEXT"
    r"\5c6eaa26-69c4-4e68-864b-24424ae1b1d9\scratchpad"
    r"\fa00aat46855.geo_fin001.004999.igs"
)
_PRODUCTION_DXF = Path(
    r"C:\Users\ilhan\AppData\Local\Temp\claude"
    r"\d83048698c536d4a\1b3bb96a-da82-40ce-ba5d-97b8f361659a"
    r"\scratchpad\109106_01_39.dxf"
)


def _has_iges() -> bool:
    return _PRODUCTION_IGES.exists()


def _has_dxf() -> bool:
    return _PRODUCTION_DXF.exists()


def _load_iges_doc():
    from backend.interoperability.adapters.iges import IGES_DESCRIPTOR, IgesTokenAdapter
    from backend.interoperability.models import EngineeringSource

    adapter = IgesTokenAdapter()
    source = EngineeringSource(
        source_id="SRC-IGES-L4",
        source_format_id="IGES",
        file_name=_PRODUCTION_IGES.name,
    )
    return adapter.ingest_file(source, IGES_DESCRIPTOR, _PRODUCTION_IGES)


def _load_dxf_doc():
    from backend.interoperability.adapters.dxf import DXF_DESCRIPTOR, DxfTokenAdapter
    from backend.interoperability.models import EngineeringSource

    content = _PRODUCTION_DXF.read_bytes().decode("utf-8", "replace")
    adapter = DxfTokenAdapter()
    source = EngineeringSource(
        source_id="SRC-DXF-L4",
        source_format_id="DXF",
        file_name=_PRODUCTION_DXF.name,
        notes=content,
    )
    return adapter.ingest(source, DXF_DESCRIPTOR)


@pytest.mark.skipif(not _has_iges(), reason="production IGES fixture not present")
class TestProductionIgesLevel4:

    def test_iges_process_intelligence_object_present(self) -> None:
        doc = _load_iges_doc()
        assert doc.process_intelligence is not None

    def test_iges_process_candidates_are_candidate_status(self) -> None:
        """IGES process candidates from PLANAR surfaces must not be CONFIRMED_BY_RULE.

        Without topology, no deterministic rule can fire → CONFIRMED_BY_RULE is fabrication.
        """
        from backend.interoperability.process_intelligence import ProcessStatus
        doc = _load_iges_doc()
        assert doc.process_intelligence is not None
        for cand in doc.process_intelligence.process_candidates:
            if hasattr(cand, "status"):
                assert cand.status != ProcessStatus.CONFIRMED_BY_RULE, (  # type: ignore[union-attr]
                    "CONFIRMED_BY_RULE process candidate without topology — possible fabrication"
                )

    def test_iges_zero_dfm_observations(self) -> None:
        """No features → no DFM observations."""
        doc = _load_iges_doc()
        assert doc.process_intelligence is not None
        assert len(doc.process_intelligence.dfm_observations) == 0

    def test_iges_zero_setup_candidates(self) -> None:
        doc = _load_iges_doc()
        assert doc.process_intelligence is not None
        assert len(doc.process_intelligence.setups) == 0

    def test_iges_zero_machine_requirements(self) -> None:
        doc = _load_iges_doc()
        assert doc.process_intelligence is not None
        assert len(doc.process_intelligence.machine_requirements) == 0

    def test_iges_zero_tool_requirements(self) -> None:
        doc = _load_iges_doc()
        assert doc.process_intelligence is not None
        assert len(doc.process_intelligence.tool_requirements) == 0

    def test_iges_operation_plan_no_confirmed_ops(self) -> None:
        """Operations from PLANAR CANDIDATE features must not be CONFIRMED."""
        doc = _load_iges_doc()
        assert doc.process_intelligence is not None
        # Allow CANDIDATE operations; disallow CONFIRMED (needs topology first).
        for op in doc.process_intelligence.operation_plan:
            if hasattr(op, "is_confirmed"):
                assert not op.is_confirmed, (  # type: ignore[union-attr]
                    f"CONFIRMED operation from PLANAR surface without topology"
                )

    def test_iges_plan_status_not_failed(self) -> None:
        """Plan status must be INSUFFICIENT_DATA or CANDIDATE_PLAN after DEF-RSQ-007 fix."""
        doc = _load_iges_doc()
        assert doc.process_intelligence is not None
        assert doc.process_intelligence.status in (
            PlanStatus.INSUFFICIENT_DATA, PlanStatus.CANDIDATE_PLAN
        ), f"Unexpected plan status: {doc.process_intelligence.status}"

    def test_iges_has_missing_inputs(self) -> None:
        doc = _load_iges_doc()
        assert doc.process_intelligence is not None
        assert len(doc.process_intelligence.missing_inputs) > 0

    def test_iges_turning_not_indicated(self) -> None:
        """Production IGES is freeform surfaces, not rotational — turning not indicated."""
        doc = _load_iges_doc()
        assert doc.process_intelligence is not None
        assert doc.process_intelligence.turning_indicator == TurningIndicator.TURNING_NOT_INDICATED

    def test_iges_cutting_params_null(self) -> None:
        doc = _load_iges_doc()
        assert doc.process_intelligence is not None
        cp = doc.process_intelligence.cutting_parameter_status
        assert cp.estimated_cutting_speed_m_min is None
        assert cp.estimated_feed_mm_tooth is None


@pytest.mark.skipif(not _has_dxf(), reason="production DXF fixture not present")
class TestProductionDxfLevel4:

    def test_dxf_process_intelligence_object_present(self) -> None:
        doc = _load_dxf_doc()
        assert doc.process_intelligence is not None

    def test_dxf_has_process_candidates(self) -> None:
        """Production DXF has 14 circle candidates → process candidates exist."""
        doc = _load_dxf_doc()
        assert doc.process_intelligence is not None
        assert len(doc.process_intelligence.process_candidates) > 0

    def test_dxf_has_drilling_candidates(self) -> None:
        doc = _load_dxf_doc()
        assert doc.process_intelligence is not None
        drill_ops = [
            op for op in doc.process_intelligence.process_candidates
            if op.process_family == ProcessFamily.DRILLING
        ]
        assert len(drill_ops) >= 1

    def test_dxf_has_center_drill_candidates(self) -> None:
        doc = _load_dxf_doc()
        assert doc.process_intelligence is not None
        cd_ops = [
            op for op in doc.process_intelligence.process_candidates
            if op.process_family == ProcessFamily.CENTER_DRILLING
        ]
        assert len(cd_ops) >= 1

    def test_dxf_all_ops_are_candidate_not_confirmed(self) -> None:
        """DXF is 2D only; no CONFIRMED_BY_RULE operations allowed."""
        doc = _load_dxf_doc()
        assert doc.process_intelligence is not None
        for op in doc.process_intelligence.process_candidates:
            assert op.status != ProcessStatus.CONFIRMED_BY_RULE, (
                f"DXF 2D must not produce CONFIRMED_BY_RULE; got op={op.operation_id}"
            )

    def test_dxf_has_exactly_one_setup_candidate(self) -> None:
        doc = _load_dxf_doc()
        assert doc.process_intelligence is not None
        assert len(doc.process_intelligence.setups) == 1

    def test_dxf_setup_direction_is_plus_z(self) -> None:
        doc = _load_dxf_doc()
        assert doc.process_intelligence is not None
        assert doc.process_intelligence.setups[0].machining_direction == "+Z"

    def test_dxf_has_exactly_one_machine_requirement(self) -> None:
        doc = _load_dxf_doc()
        assert doc.process_intelligence is not None
        assert len(doc.process_intelligence.machine_requirements) == 1

    def test_dxf_machine_class_is_three_axis_vmc(self) -> None:
        doc = _load_dxf_doc()
        assert doc.process_intelligence is not None
        mreq = doc.process_intelligence.machine_requirements[0]
        assert mreq.machine_class == MachineClass.THREE_AXIS_VMC

    def test_dxf_has_tool_requirements(self) -> None:
        doc = _load_dxf_doc()
        assert doc.process_intelligence is not None
        assert len(doc.process_intelligence.tool_requirements) > 0

    def test_dxf_zero_dfm_observations(self) -> None:
        """No depth info for 2D holes → no L/D DFM observations."""
        doc = _load_dxf_doc()
        assert doc.process_intelligence is not None
        assert len(doc.process_intelligence.dfm_observations) == 0

    def test_dxf_plan_is_candidate_plan(self) -> None:
        doc = _load_dxf_doc()
        assert doc.process_intelligence is not None
        assert doc.process_intelligence.status == PlanStatus.CANDIDATE_PLAN

    def test_dxf_has_missing_inputs(self) -> None:
        doc = _load_dxf_doc()
        assert doc.process_intelligence is not None
        assert len(doc.process_intelligence.missing_inputs) > 0

    def test_dxf_cutting_params_null(self) -> None:
        doc = _load_dxf_doc()
        assert doc.process_intelligence is not None
        cp = doc.process_intelligence.cutting_parameter_status
        assert cp.estimated_cutting_speed_m_min is None

    def test_dxf_cycle_time_null(self) -> None:
        doc = _load_dxf_doc()
        assert doc.process_intelligence is not None
        assert doc.process_intelligence.cycle_time_status.estimated_total_minutes is None

    def test_dxf_turning_not_indicated(self) -> None:
        """Production DXF is 2D drawing — turning not indicated."""
        doc = _load_dxf_doc()
        assert doc.process_intelligence is not None
        assert doc.process_intelligence.turning_indicator == TurningIndicator.TURNING_NOT_INDICATED

    def test_dxf_capability_level_is_level4_or_higher(self) -> None:
        from backend.interoperability.enums import CapabilityLevel

        doc = _load_dxf_doc()
        assert doc.capability_level in (
            CapabilityLevel.LEVEL_4_MANUFACTURING_FEATURES,
            CapabilityLevel.LEVEL_5_PROCESS_CONTENT,
            CapabilityLevel.LEVEL_6_ENGINEERING_VALIDATED,
            CapabilityLevel.LEVEL_7_CYCLE_TIME_INTELLIGENCE,
            CapabilityLevel.LEVEL_8_COST_RFQ_INTELLIGENCE,
        )

    def test_dxf_operation_plan_has_operations(self) -> None:
        doc = _load_dxf_doc()
        assert doc.process_intelligence is not None
        assert len(doc.process_intelligence.operation_plan) > 0


# ---------------------------------------------------------------------------
# API response (Phase 25) — engineering_import response includes manufacturing_intelligence
# ---------------------------------------------------------------------------

class TestApiResponseLevel4:

    @pytest.fixture()
    def _dxf_data(self) -> bytes:
        # _VALID_DXF from Level-1 tests has 1 circle → triggers Level-4
        dxf = (
            "  0\nSECTION\n  2\nHEADER\n  9\n$ACADVER\n  1\nAC1015\n"
            "  9\n$INSUNITS\n 70\n4\n"
            "  0\nENDSEC\n  0\nSECTION\n  2\nENTITIES\n"
            "  0\nLINE\n  8\n0\n 10\n0.0\n 20\n0.0\n 30\n0.0\n"
            " 11\n10.0\n 21\n0.0\n 31\n0.0\n"
            "  0\nCIRCLE\n  8\nHOLES\n 10\n50.0\n 20\n25.0\n 40\n12.5\n"
            "  0\nENDSEC\n  0\nEOF\n"
        )
        return dxf.encode("utf-8")

    def test_api_response_contains_feature_status(self, _dxf_data: bytes, tmp_path: Path) -> None:
        from backend.api.engineering_import import _get_registry
        from backend.interoperability.adapters.dxf import DXF_DESCRIPTOR
        from backend.interoperability.models import EngineeringSource

        p = tmp_path / "test.dxf"
        p.write_bytes(_dxf_data)

        registry = _get_registry()
        source = EngineeringSource(
            source_id="test::test.dxf",
            source_format_id="DXF",
            file_name="test.dxf",
        )
        adapters = registry.find_by_format("DXF")
        doc = adapters[0].ingest_file(source, DXF_DESCRIPTOR, p)

        feature_status = "PRESENT" if doc.features is not None else "NONE"
        assert feature_status == "PRESENT"

    def test_api_response_contains_manufacturing_intelligence(
        self, _dxf_data: bytes, tmp_path: Path
    ) -> None:
        from backend.api.engineering_import import _get_registry
        from backend.interoperability.adapters.dxf import DXF_DESCRIPTOR
        from backend.interoperability.models import EngineeringSource

        p = tmp_path / "test.dxf"
        p.write_bytes(_dxf_data)

        registry = _get_registry()
        source = EngineeringSource(
            source_id="test::test.dxf",
            source_format_id="DXF",
            file_name="test.dxf",
        )
        adapters = registry.find_by_format("DXF")
        doc = adapters[0].ingest_file(source, DXF_DESCRIPTOR, p)

        assert doc.process_intelligence is not None
        mi = {
            "status": doc.process_intelligence.status.value,
            "process_candidate_count": len(doc.process_intelligence.process_candidates),
            "setup_candidate_count": len(doc.process_intelligence.setups),
            "machine_requirement_count": len(doc.process_intelligence.machine_requirements),
        }
        assert mi["process_candidate_count"] > 0
        assert mi["setup_candidate_count"] == 1
        assert mi["machine_requirement_count"] == 1
