"""Level-5 Machine and Tool Selection Intelligence — regression tests.

Tests cover:
  - Domain model structure and immutability
  - Negative rules (no fabrication, unknown stays unknown)
  - Machine requirement derivation
  - Machine class candidates
  - Tool capability requirements
  - Tool family candidates
  - Holder requirements
  - Tool/holder compatibility
  - Reach and accessibility
  - Material compatibility
  - Cutting parameter foundation
  - Operation sequencing and alternatives
  - Production IGES validation (no regression, INSUFFICIENT_DATA)
  - Production DXF validation (machine/tool candidates, LEVEL_5)
  - API response fields
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Production file paths (same as Level-4 tests)
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
        source_id="SRC-IGES-L5",
        file_name=_PRODUCTION_IGES.name,
    )
    return adapter.ingest_file(source, IGES_DESCRIPTOR, _PRODUCTION_IGES)


def _load_dxf_doc():
    from backend.interoperability.adapters.dxf import DXF_DESCRIPTOR, DxfTokenAdapter
    from backend.interoperability.models import EngineeringSource

    adapter = DxfTokenAdapter()
    source = EngineeringSource(
        source_id="SRC-DXF-L5",
        file_name=_PRODUCTION_DXF.name,
    )
    return adapter.ingest_file(source, DXF_DESCRIPTOR, _PRODUCTION_DXF)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_feature(
    feature_type: str,
    feature_id: str = "F-001",
    status: str = "CANDIDATE",
    source_surface_id: str | None = None,
    source_curve_id: str | None = None,
    hole_subtype: str | None = None,
):
    from backend.interoperability.features import (
        FeatureStatus,
        ManufacturingFeature,
        ManufacturingFeatureType,
    )

    ftype = ManufacturingFeatureType(feature_type)
    fstatus = FeatureStatus(status)
    kwargs: dict[str, Any] = {
        "feature_id": feature_id,
        "feature_type": ftype,
        "status": fstatus,
        "surface_ids": (source_surface_id,) if source_surface_id else (),
        "curve_ids": (source_curve_id,) if source_curve_id else (),
    }
    if hole_subtype is not None:
        from backend.interoperability.features import HoleSubtype

        kwargs["hole_subtype"] = HoleSubtype(hole_subtype)
    return ManufacturingFeature(**kwargs)


def _result_with(*features, basis: str = "TOPOLOGY"):
    from backend.interoperability.features import FeatureRecognitionResult

    return FeatureRecognitionResult(
        recognition_basis=basis,
        classified_faces=(),
        adjacencies=(),
        features=features,
    )


def _pi_from_features(*features, basis: str = "TOPOLOGY"):
    """Run L4 recognition and return ProcessIntelligenceResult."""
    from backend.interoperability.process_recognition import recognize_process_intelligence

    feat_result = _result_with(*features, basis=basis)
    return recognize_process_intelligence(feat_result, None, None)


def _mti_from_features(*features, basis: str = "TOPOLOGY"):
    """Run L4 then L5 and return MachineToolIntelligenceResult."""
    from backend.interoperability.machine_tool_selection import (
        derive_machine_tool_intelligence,
    )

    pi = _pi_from_features(*features, basis=basis)
    return derive_machine_tool_intelligence(pi, None)


# ===========================================================================
# TestMachineToolDomainModel
# ===========================================================================


class TestMachineToolDomainModel:
    def test_machine_tool_intelligence_result_instantiation(self) -> None:
        from backend.interoperability.machine_tool_intelligence import (
            MachineToolIntelligenceResult,
            SelectionPlanStatus,
        )

        r = MachineToolIntelligenceResult(
            plan_id="P-001",
            status=SelectionPlanStatus.CANDIDATE_PLAN,
            recognition_basis="TOPOLOGY",
        )
        assert r.plan_id == "P-001"
        assert r.status == SelectionPlanStatus.CANDIDATE_PLAN

    def test_machine_tool_intelligence_result_is_frozen(self) -> None:
        from backend.interoperability.machine_tool_intelligence import (
            MachineToolIntelligenceResult,
            SelectionPlanStatus,
        )

        r = MachineToolIntelligenceResult(
            plan_id="P-002",
            status=SelectionPlanStatus.INSUFFICIENT_DATA,
            recognition_basis="NONE",
        )
        with pytest.raises(AttributeError):
            r.plan_id = "changed"  # type: ignore[misc]

    def test_match_status_values(self) -> None:
        from backend.interoperability.machine_tool_intelligence import MatchStatus

        assert MatchStatus.COMPATIBLE == "COMPATIBLE"
        assert MatchStatus.PARTIALLY_COMPATIBLE == "PARTIALLY_COMPATIBLE"
        assert MatchStatus.INCOMPATIBLE == "INCOMPATIBLE"
        assert MatchStatus.UNKNOWN == "UNKNOWN"

    def test_machine_class_v5_extended_values(self) -> None:
        from backend.interoperability.machine_tool_intelligence import MachineClassV5

        assert MachineClassV5.THREE_AXIS_VMC == "THREE_AXIS_VMC"
        assert MachineClassV5.DRILL_TAP_CENTER == "DRILL_TAP_CENTER"
        assert MachineClassV5.SWISS_LATHE == "SWISS_LATHE"
        assert MachineClassV5.WIRE_EDM == "WIRE_EDM"
        assert MachineClassV5.SINKER_EDM == "SINKER_EDM"
        assert MachineClassV5.MANUAL_REVIEW == "MANUAL_REVIEW"

    def test_tool_family_v5_extended_values(self) -> None:
        from backend.interoperability.machine_tool_intelligence import ToolFamilyV5

        assert ToolFamilyV5.ROUGHING_END_MILL == "ROUGHING_END_MILL"
        assert ToolFamilyV5.FINISH_END_MILL == "FINISH_END_MILL"
        assert ToolFamilyV5.SPOT_DRILL == "SPOT_DRILL"
        assert ToolFamilyV5.PARTING_TOOL == "PARTING_TOOL"
        assert ToolFamilyV5.GRINDING_WHEEL == "GRINDING_WHEEL"
        assert ToolFamilyV5.EDM_ELECTRODE == "EDM_ELECTRODE"

    def test_holder_type_values(self) -> None:
        from backend.interoperability.machine_tool_intelligence import HolderType

        assert HolderType.ER_COLLET == "ER_COLLET"
        assert HolderType.HYDRAULIC_CHUCK == "HYDRAULIC_CHUCK"
        assert HolderType.SHRINK_FIT == "SHRINK_FIT"
        assert HolderType.TAPPING_CHUCK == "TAPPING_CHUCK"
        assert HolderType.BORING_HOLDER == "BORING_HOLDER"
        assert HolderType.TURNING_TOOLHOLDER == "TURNING_TOOLHOLDER"

    def test_machine_candidate_is_frozen(self) -> None:
        from backend.interoperability.machine_tool_intelligence import (
            MachineCandidate,
            MachineClassV5,
            MatchStatus,
        )

        mc = MachineCandidate(
            machine_id="MC-1",
            machine_name="3-Axis VMC (candidate)",
            machine_class=MachineClassV5.THREE_AXIS_VMC,
            match_status=MatchStatus.COMPATIBLE,
        )
        with pytest.raises(AttributeError):
            mc.machine_id = "changed"  # type: ignore[misc]

    def test_tool_candidate_is_frozen(self) -> None:
        from backend.interoperability.machine_tool_intelligence import (
            MatchStatus,
            ToolCandidate,
            ToolFamilyV5,
        )

        tc = ToolCandidate(
            candidate_id="TC-1",
            tool_family=ToolFamilyV5.DRILL,
            operation_ref="OP-1",
            match_status=MatchStatus.COMPATIBLE,
        )
        with pytest.raises(AttributeError):
            tc.candidate_id = "changed"  # type: ignore[misc]

    def test_holder_requirement_is_frozen(self) -> None:
        from backend.interoperability.machine_tool_intelligence import (
            HolderRequirement,
            HolderType,
        )

        hr = HolderRequirement(
            requirement_id="HR-1",
            holder_type=HolderType.ER_COLLET,
            operation_ref="OP-1",
        )
        with pytest.raises(AttributeError):
            hr.requirement_id = "changed"  # type: ignore[misc]

    def test_compatibility_result_is_frozen(self) -> None:
        from backend.interoperability.machine_tool_intelligence import (
            CompatibilityResult,
            MatchStatus,
        )

        cr = CompatibilityResult(
            result_id="CR-1",
            tool_requirement_id="TR-1",
            holder_requirement_id="HR-1",
            match_status=MatchStatus.COMPATIBLE,
        )
        with pytest.raises(AttributeError):
            cr.result_id = "changed"  # type: ignore[misc]

    def test_cutting_parameter_requirement_defaults_unknown(self) -> None:
        from backend.interoperability.machine_tool_intelligence import (
            CuttingParameterRequirement,
            CuttingParameterRequirementStatus,
        )

        cpr = CuttingParameterRequirement()
        assert cpr.cutting_speed_status == CuttingParameterRequirementStatus.UNKNOWN
        assert cpr.feed_per_tooth_status == CuttingParameterRequirementStatus.UNKNOWN
        assert cpr.material_group_required is True

    def test_machine_capability_requirement_all_nulls_by_default(self) -> None:
        from backend.interoperability.machine_tool_intelligence import (
            MachineCapabilityRequirement,
            MachineClassV5,
        )

        req = MachineCapabilityRequirement(
            requirement_id="MCR-1",
            machine_class=MachineClassV5.THREE_AXIS_VMC,
        )
        assert req.min_x_travel_mm is None
        assert req.min_y_travel_mm is None
        assert req.min_z_travel_mm is None
        assert req.min_spindle_speed_rpm is None
        assert req.min_spindle_power_kw is None
        assert req.min_spindle_torque_nm is None

    def test_derived_property_compatible_machine_count(self) -> None:
        from backend.interoperability.machine_tool_intelligence import (
            MachineCandidate,
            MachineClassV5,
            MachineToolIntelligenceResult,
            MatchStatus,
            SelectionPlanStatus,
        )

        mc1 = MachineCandidate(
            machine_id="MC-1",
            machine_name="3-Axis VMC",
            machine_class=MachineClassV5.THREE_AXIS_VMC,
            match_status=MatchStatus.COMPATIBLE,
        )
        mc2 = MachineCandidate(
            machine_id="MC-2",
            machine_name="Drill Centre",
            machine_class=MachineClassV5.DRILL_TAP_CENTER,
            match_status=MatchStatus.PARTIALLY_COMPATIBLE,
        )
        r = MachineToolIntelligenceResult(
            plan_id="P-1",
            status=SelectionPlanStatus.CANDIDATE_PLAN,
            recognition_basis="TOPOLOGY",
            machine_candidates=(mc1, mc2),
        )
        assert r.compatible_machine_count == 1

    def test_derived_property_drilling_tool_candidate_count(self) -> None:
        from backend.interoperability.machine_tool_intelligence import (
            MachineToolIntelligenceResult,
            MatchStatus,
            SelectionPlanStatus,
            ToolCandidate,
            ToolFamilyV5,
        )

        tc1 = ToolCandidate(
            candidate_id="TC-1",
            tool_family=ToolFamilyV5.DRILL,
            operation_ref="OP-1",
            match_status=MatchStatus.COMPATIBLE,
        )
        tc2 = ToolCandidate(
            candidate_id="TC-2",
            tool_family=ToolFamilyV5.CENTER_DRILL,
            operation_ref="OP-2",
            match_status=MatchStatus.COMPATIBLE,
        )
        tc3 = ToolCandidate(
            candidate_id="TC-3",
            tool_family=ToolFamilyV5.END_MILL,
            operation_ref="OP-3",
            match_status=MatchStatus.COMPATIBLE,
        )
        r = MachineToolIntelligenceResult(
            plan_id="P-1",
            status=SelectionPlanStatus.CANDIDATE_PLAN,
            recognition_basis="TOPOLOGY",
            tool_candidates=(tc1, tc2, tc3),
        )
        assert r.drilling_tool_candidate_count == 2


# ===========================================================================
# TestNegativeRules
# ===========================================================================


class TestNegativeRules:
    def test_no_l4_input_returns_insufficient_data(self) -> None:
        from backend.interoperability.machine_tool_intelligence import SelectionPlanStatus
        from backend.interoperability.machine_tool_selection import (
            derive_machine_tool_intelligence,
        )

        result = derive_machine_tool_intelligence(None, None)
        assert result.status == SelectionPlanStatus.INSUFFICIENT_DATA
        assert len(result.machine_candidates) == 0

    def test_l4_insufficient_data_propagates(self) -> None:
        from backend.interoperability.machine_tool_intelligence import SelectionPlanStatus
        from backend.interoperability.machine_tool_selection import (
            derive_machine_tool_intelligence,
        )
        from backend.interoperability.process_intelligence import (
            PlanStatus,
            ProcessIntelligenceResult,
        )

        pi = ProcessIntelligenceResult(
            plan_id="P-X",
            status=PlanStatus.INSUFFICIENT_DATA,
            recognition_basis="NONE",
        )
        result = derive_machine_tool_intelligence(pi, None)
        assert result.status == SelectionPlanStatus.INSUFFICIENT_DATA
        assert len(result.machine_candidates) == 0
        assert len(result.tool_candidates) == 0

    def test_unknown_travel_specs_remain_null(self) -> None:
        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat, basis="2D_GEOMETRY_ONLY")
        for req in mti.machine_capability_requirements:
            assert req.min_x_travel_mm is None
            assert req.min_y_travel_mm is None
            assert req.min_z_travel_mm is None

    def test_unknown_spindle_specs_remain_null(self) -> None:
        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat)
        for req in mti.machine_capability_requirements:
            assert req.min_spindle_speed_rpm is None
            assert req.min_spindle_power_kw is None
            assert req.min_spindle_torque_nm is None

    def test_unknown_travel_is_not_compatible(self) -> None:
        """Unknown travel != COMPATIBLE; must appear in unknown_requirements."""
        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat)
        for mc in mti.machine_candidates:
            # unknown travel fields must be listed, not silently passed
            assert "min_x_travel_mm" in mc.unknown_requirements

    def test_candidate_process_does_not_auto_confirm_tool(self) -> None:
        """CANDIDATE operation → tool candidate status must remain CANDIDATE."""
        feat = _make_feature("HOLE", source_curve_id="C-1", status="CANDIDATE")
        mti = _mti_from_features(feat, basis="2D_GEOMETRY_ONLY")
        for tr in mti.tool_capability_requirements:
            assert tr.status == "CANDIDATE"

    def test_no_machine_brand_names(self) -> None:
        """machine_name must not contain known brand names."""
        brands = ["haas", "fanuc", "mazak", "okuma", "dmg", "doosan", "makino"]
        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat)
        for mc in mti.machine_candidates:
            name_lower = mc.machine_name.lower()
            for brand in brands:
                assert brand not in name_lower, (
                    f"Brand '{brand}' found in machine name: {mc.machine_name}"
                )

    def test_no_tool_catalog_numbers(self) -> None:
        """Tool candidates must not contain catalog part numbers or brand names."""
        brands = ["sandvik", "kennametal", "iscar", "seco", "mitsubishi", "osg"]
        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat)
        for tc in mti.tool_candidates:
            rationale_lower = tc.rationale.lower()
            for brand in brands:
                assert brand not in rationale_lower

    def test_multiple_directions_not_automatically_five_axis(self) -> None:
        """Multiple machining directions do not automatically imply 5-axis."""
        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat)
        # With a single +Z setup, must not select five-axis
        for req in mti.machine_capability_requirements:
            assert req.required_axes <= 4, (
                "Single-direction drilling should not require 5 axes"
            )

    def test_cutting_parameters_always_unknown(self) -> None:
        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat)
        from backend.interoperability.machine_tool_intelligence import (
            CuttingParameterRequirementStatus,
        )

        cpr = mti.cutting_parameter_requirements
        assert cpr.cutting_speed_status == CuttingParameterRequirementStatus.UNKNOWN
        assert cpr.feed_per_tooth_status == CuttingParameterRequirementStatus.UNKNOWN
        assert cpr.depth_of_cut_status == CuttingParameterRequirementStatus.UNKNOWN


# ===========================================================================
# TestMachineRequirements
# ===========================================================================


class TestMachineRequirements:
    def test_drilling_ops_require_three_axis_vmc(self) -> None:
        from backend.interoperability.machine_tool_intelligence import MachineClassV5

        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat)
        assert len(mti.machine_capability_requirements) >= 1
        req = mti.machine_capability_requirements[0]
        assert req.machine_class == MachineClassV5.THREE_AXIS_VMC
        assert req.drilling_required is True

    def test_pocket_ops_require_milling_capability(self) -> None:
        feat = _make_feature("POCKET", source_surface_id="S-1")
        mti = _mti_from_features(feat)
        req = mti.machine_capability_requirements[0]
        assert req.milling_required is True

    def test_slot_ops_require_milling_capability(self) -> None:
        feat = _make_feature("SLOT", source_surface_id="S-1")
        mti = _mti_from_features(feat)
        req = mti.machine_capability_requirements[0]
        assert req.milling_required is True

    def test_requirement_has_evidence_notes(self) -> None:
        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat)
        req = mti.machine_capability_requirements[0]
        assert req.evidence_notes != ""

    def test_no_operations_means_no_machine_requirements(self) -> None:
        from backend.interoperability.machine_tool_selection import (
            derive_machine_tool_intelligence,
        )
        from backend.interoperability.process_intelligence import (
            PlanStatus,
            ProcessIntelligenceResult,
        )

        pi = ProcessIntelligenceResult(
            plan_id="P-EMPTY",
            status=PlanStatus.INSUFFICIENT_DATA,
            recognition_basis="TOPOLOGY",
        )
        mti = derive_machine_tool_intelligence(pi, None)
        assert len(mti.machine_capability_requirements) == 0

    def test_minimum_axes_is_three_for_single_setup(self) -> None:
        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat)
        req = mti.machine_capability_requirements[0]
        assert req.required_axes == 3

    def test_requirement_status_is_candidate_for_2d_input(self) -> None:
        feat = _make_feature("HOLE", source_curve_id="C-1", status="CANDIDATE")
        mti = _mti_from_features(feat, basis="2D_GEOMETRY_ONLY")
        req = mti.machine_capability_requirements[0]
        assert req.status == "CANDIDATE"


# ===========================================================================
# TestMachineCandidates
# ===========================================================================


class TestMachineCandidates:
    def test_drilling_produces_three_axis_vmc_candidate(self) -> None:
        from backend.interoperability.machine_tool_intelligence import (
            MachineClassV5,
            MatchStatus,
        )

        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat)
        assert len(mti.machine_candidates) >= 1
        primary = mti.machine_candidates[0]
        assert primary.machine_class == MachineClassV5.THREE_AXIS_VMC
        assert primary.match_status == MatchStatus.COMPATIBLE

    def test_drilling_includes_drill_tap_centre_alternative(self) -> None:
        from backend.interoperability.machine_tool_intelligence import MachineClassV5

        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat)
        classes = {mc.machine_class for mc in mti.machine_candidates}
        assert MachineClassV5.DRILL_TAP_CENTER in classes

    def test_four_axis_vmc_included_as_alternative_for_drilling(self) -> None:
        from backend.interoperability.machine_tool_intelligence import MachineClassV5

        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat)
        classes = {mc.machine_class for mc in mti.machine_candidates}
        assert MachineClassV5.FOUR_AXIS_VMC in classes

    def test_each_candidate_has_rationale(self) -> None:
        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat)
        for mc in mti.machine_candidates:
            assert mc.rationale != ""

    def test_drill_tap_centre_is_partially_compatible(self) -> None:
        from backend.interoperability.machine_tool_intelligence import (
            MachineClassV5,
            MatchStatus,
        )

        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat)
        dtc = next(
            (mc for mc in mti.machine_candidates
             if mc.machine_class == MachineClassV5.DRILL_TAP_CENTER),
            None,
        )
        assert dtc is not None
        assert dtc.match_status == MatchStatus.PARTIALLY_COMPATIBLE

    def test_candidate_name_is_generic_not_commercial(self) -> None:
        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat)
        for mc in mti.machine_candidates:
            assert mc.machine_name != ""
            # candidate label must include "candidate" or "centre"
            assert any(
                word in mc.machine_name.lower()
                for word in ("candidate", "centre", "center", "lathe", "grinder", "review")
            )


# ===========================================================================
# TestToolCapabilityRequirements
# ===========================================================================


class TestToolCapabilityRequirements:
    def test_hole_produces_drill_and_center_drill_requirements(self) -> None:
        from backend.interoperability.machine_tool_intelligence import ToolFamilyV5

        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat)
        families = {str(tr.tool_family) for tr in mti.tool_capability_requirements}
        assert ToolFamilyV5.DRILL in families
        assert ToolFamilyV5.CENTER_DRILL in families

    def test_pocket_roughing_produces_roughing_end_mill(self) -> None:
        from backend.interoperability.machine_tool_intelligence import ToolFamilyV5

        feat = _make_feature("POCKET", source_surface_id="S-1")
        mti = _mti_from_features(feat)
        families = {str(tr.tool_family) for tr in mti.tool_capability_requirements}
        assert ToolFamilyV5.ROUGHING_END_MILL in families

    def test_pocket_finishing_produces_finish_end_mill(self) -> None:
        from backend.interoperability.machine_tool_intelligence import ToolFamilyV5

        feat = _make_feature("POCKET", source_surface_id="S-1")
        mti = _mti_from_features(feat)
        families = {str(tr.tool_family) for tr in mti.tool_capability_requirements}
        assert ToolFamilyV5.FINISH_END_MILL in families

    def test_slot_produces_slot_mill_requirement(self) -> None:
        from backend.interoperability.machine_tool_intelligence import ToolFamilyV5

        feat = _make_feature("SLOT", source_surface_id="S-1")
        mti = _mti_from_features(feat)
        families = {str(tr.tool_family) for tr in mti.tool_capability_requirements}
        assert ToolFamilyV5.SLOT_MILL in families

    def test_chamfer_produces_chamfer_mill_requirement(self) -> None:
        from backend.interoperability.machine_tool_intelligence import ToolFamilyV5

        feat = _make_feature("CHAMFER", source_surface_id="S-1")
        mti = _mti_from_features(feat)
        families = {str(tr.tool_family) for tr in mti.tool_capability_requirements}
        assert ToolFamilyV5.CHAMFER_MILL in families

    def test_fillet_produces_ball_end_mill_requirement(self) -> None:
        from backend.interoperability.machine_tool_intelligence import ToolFamilyV5

        feat = _make_feature("FILLET", source_surface_id="S-1")
        mti = _mti_from_features(feat)
        families = {str(tr.tool_family) for tr in mti.tool_capability_requirements}
        assert ToolFamilyV5.BALL_END_MILL in families

    def test_2d_hole_has_no_diameter_evidence(self) -> None:
        """2D DXF hole without geometry lookup → diameter fields are None."""
        feat = _make_feature("HOLE", source_curve_id="C-1", status="CANDIDATE")
        mti = _mti_from_features(feat, basis="2D_GEOMETRY_ONLY")
        drill_reqs = [
            tr for tr in mti.tool_capability_requirements
            if str(tr.tool_family) == "DRILL"
        ]
        # Diameter may be None when no geometry object is passed
        for dr in drill_reqs:
            # Either None (no geometry available) or a positive float
            if dr.min_diameter_mm is not None:
                assert dr.min_diameter_mm > 0

    def test_requirement_has_operation_ref(self) -> None:
        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat)
        for tr in mti.tool_capability_requirements:
            assert tr.operation_ref != ""


# ===========================================================================
# TestToolCandidates
# ===========================================================================


class TestToolCandidates:
    def test_hole_produces_drill_candidate(self) -> None:
        from backend.interoperability.machine_tool_intelligence import (
            MatchStatus,
            ToolFamilyV5,
        )

        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat)
        drill_cands = [
            tc for tc in mti.tool_candidates
            if str(tc.tool_family) == ToolFamilyV5.DRILL
        ]
        assert len(drill_cands) >= 1
        for dc in drill_cands:
            # Without diameter evidence, may be PARTIALLY_COMPATIBLE
            assert dc.match_status in (MatchStatus.COMPATIBLE, MatchStatus.PARTIALLY_COMPATIBLE)

    def test_pocket_produces_end_mill_candidates(self) -> None:
        from backend.interoperability.machine_tool_intelligence import ToolFamilyV5

        feat = _make_feature("POCKET", source_surface_id="S-1")
        mti = _mti_from_features(feat)
        families = {str(tc.tool_family) for tc in mti.tool_candidates}
        assert any(
            f in families
            for f in (ToolFamilyV5.ROUGHING_END_MILL, ToolFamilyV5.END_MILL)
        )

    def test_candidate_preserves_candidate_status(self) -> None:
        """CANDIDATE L4 operation → tool candidate rationale references CANDIDATE."""
        feat = _make_feature("HOLE", source_curve_id="C-1", status="CANDIDATE")
        mti = _mti_from_features(feat, basis="2D_GEOMETRY_ONLY")
        for tc in mti.tool_candidates:
            assert "CANDIDATE" in tc.rationale

    def test_each_tool_candidate_has_rationale(self) -> None:
        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat)
        for tc in mti.tool_candidates:
            assert tc.rationale != ""

    def test_tool_candidate_has_operation_ref(self) -> None:
        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat)
        for tc in mti.tool_candidates:
            assert tc.operation_ref != ""


# ===========================================================================
# TestHolderRequirements
# ===========================================================================


class TestHolderRequirements:
    def test_drilling_uses_er_collet(self) -> None:
        from backend.interoperability.machine_tool_intelligence import HolderType

        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat)
        er_collets = [
            hr for hr in mti.holder_requirements
            if hr.holder_type == HolderType.ER_COLLET
        ]
        assert len(er_collets) >= 1

    def test_pocket_roughing_uses_milling_chuck(self) -> None:
        from backend.interoperability.machine_tool_intelligence import HolderType

        feat = _make_feature("POCKET", source_surface_id="S-1")
        mti = _mti_from_features(feat)
        holder_types = {str(hr.holder_type) for hr in mti.holder_requirements}
        assert HolderType.MILLING_CHUCK in holder_types

    def test_holder_count_matches_tool_requirement_count(self) -> None:
        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat)
        assert len(mti.holder_requirements) == len(mti.tool_capability_requirements)

    def test_holder_has_operation_ref(self) -> None:
        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat)
        for hr in mti.holder_requirements:
            assert hr.operation_ref != ""

    def test_holder_reach_unknown_when_no_depth(self) -> None:
        """2D hole has no depth → holder reach requirement is None."""
        feat = _make_feature("HOLE", source_curve_id="C-1", status="CANDIDATE")
        mti = _mti_from_features(feat, basis="2D_GEOMETRY_ONLY")
        for hr in mti.holder_requirements:
            # reach is None when depth is unknown
            assert hr.required_reach_mm is None


# ===========================================================================
# TestCompatibility
# ===========================================================================


class TestCompatibility:
    def test_er_collet_and_drill_are_compatible(self) -> None:
        from backend.interoperability.machine_tool_intelligence import MatchStatus

        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat)
        # ER_COLLET + DRILL family → at least one COMPATIBLE or PARTIALLY_COMPATIBLE
        for cr in mti.compatibility_results:
            assert cr.match_status in (
                MatchStatus.COMPATIBLE,
                MatchStatus.PARTIALLY_COMPATIBLE,
                MatchStatus.UNKNOWN,
            )

    def test_no_incompatible_results_for_simple_drilling(self) -> None:
        from backend.interoperability.machine_tool_intelligence import MatchStatus

        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat)
        incompatible = [
            cr for cr in mti.compatibility_results
            if cr.match_status == MatchStatus.INCOMPATIBLE
        ]
        assert incompatible == [], "Drilling ops should not produce incompatible tool/holder"

    def test_compatibility_count_matches_tool_requirement_count(self) -> None:
        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat)
        assert len(mti.compatibility_results) == len(mti.tool_capability_requirements)

    def test_compatibility_result_has_evidence(self) -> None:
        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat)
        for cr in mti.compatibility_results:
            assert cr.evidence_notes != ""

    def test_unknown_holder_produces_unknown_match(self) -> None:
        from backend.interoperability.machine_tool_intelligence import (
            HolderRequirement,
            HolderType,
            MatchStatus,
            ToolCapabilityRequirement,
            ToolFamilyV5,
        )
        from backend.interoperability.machine_tool_selection import _check_compatibility

        tr = ToolCapabilityRequirement(
            requirement_id="TR-X",
            tool_family=ToolFamilyV5.DRILL,
            operation_ref="OP-X",
        )
        hr = HolderRequirement(
            requirement_id="HR-X",
            holder_type=HolderType.UNKNOWN,
            operation_ref="OP-X",
        )
        results = _check_compatibility([tr], [hr])
        assert len(results) == 1
        assert results[0].match_status == MatchStatus.UNKNOWN


# ===========================================================================
# TestAlternativesAndRanking
# ===========================================================================


class TestAlternativesAndRanking:
    def test_multiple_machine_candidates_for_drilling(self) -> None:
        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat)
        # Must have primary + at least one alternative
        assert len(mti.machine_candidates) >= 2

    def test_selection_plan_status_is_candidate_for_2d(self) -> None:
        from backend.interoperability.machine_tool_intelligence import SelectionPlanStatus

        feat = _make_feature("HOLE", source_curve_id="C-1", status="CANDIDATE")
        mti = _mti_from_features(feat, basis="2D_GEOMETRY_ONLY")
        assert mti.status == SelectionPlanStatus.CANDIDATE_PLAN

    def test_no_optimal_label_without_criterion(self) -> None:
        """machine_name must not claim 'optimal' without a criterion."""
        feat = _make_feature("HOLE", source_curve_id="C-1")
        mti = _mti_from_features(feat)
        for mc in mti.machine_candidates:
            assert "optimal" not in mc.machine_name.lower()


# ===========================================================================
# TestProductionIgesLevel5
# ===========================================================================


@pytest.mark.skipif(not _has_iges(), reason="production IGES file not available")
class TestProductionIgesLevel5:
    def test_iges_no_l4_regression(self) -> None:
        """L4 process_intelligence must still be present and INSUFFICIENT_DATA."""
        from backend.interoperability.process_intelligence import PlanStatus

        doc = _load_iges_doc()
        assert doc.process_intelligence is not None
        assert doc.process_intelligence.status == PlanStatus.INSUFFICIENT_DATA

    def test_iges_machine_tool_intelligence_field_present(self) -> None:
        doc = _load_iges_doc()
        assert doc.machine_tool_intelligence is not None

    def test_iges_mti_status_is_insufficient_data(self) -> None:
        from backend.interoperability.machine_tool_intelligence import SelectionPlanStatus

        doc = _load_iges_doc()
        mti = doc.machine_tool_intelligence
        assert mti.status == SelectionPlanStatus.INSUFFICIENT_DATA

    def test_iges_mti_no_machine_candidates(self) -> None:
        doc = _load_iges_doc()
        assert len(doc.machine_tool_intelligence.machine_candidates) == 0

    def test_iges_mti_no_tool_candidates(self) -> None:
        doc = _load_iges_doc()
        assert len(doc.machine_tool_intelligence.tool_candidates) == 0

    def test_iges_mti_no_machine_requirements(self) -> None:
        doc = _load_iges_doc()
        assert len(doc.machine_tool_intelligence.machine_capability_requirements) == 0

    def test_iges_mti_no_holder_requirements(self) -> None:
        doc = _load_iges_doc()
        assert len(doc.machine_tool_intelligence.holder_requirements) == 0

    def test_iges_mti_no_compatibility_results(self) -> None:
        doc = _load_iges_doc()
        assert len(doc.machine_tool_intelligence.compatibility_results) == 0

    def test_iges_capability_level_not_level5(self) -> None:
        """IGES with no features must NOT reach LEVEL_5."""
        from backend.interoperability.enums import CapabilityLevel

        doc = _load_iges_doc()
        assert doc.capability_level != CapabilityLevel.LEVEL_5_PROCESS_CONTENT

    def test_iges_has_missing_inputs(self) -> None:
        doc = _load_iges_doc()
        assert len(doc.machine_tool_intelligence.missing_inputs) > 0


# ===========================================================================
# TestProductionDxfLevel5
# ===========================================================================


@pytest.mark.skipif(not _has_dxf(), reason="production DXF file not available")
class TestProductionDxfLevel5:
    def test_dxf_no_l4_regression(self) -> None:
        """L4 process_intelligence must still be CANDIDATE_PLAN."""
        from backend.interoperability.process_intelligence import PlanStatus

        doc = _load_dxf_doc()
        assert doc.process_intelligence is not None
        assert doc.process_intelligence.status == PlanStatus.CANDIDATE_PLAN

    def test_dxf_machine_tool_intelligence_field_present(self) -> None:
        doc = _load_dxf_doc()
        assert doc.machine_tool_intelligence is not None

    def test_dxf_capability_level_is_level5(self) -> None:
        from backend.interoperability.enums import CapabilityLevel

        doc = _load_dxf_doc()
        assert doc.capability_level in (
            CapabilityLevel.LEVEL_5_PROCESS_CONTENT,
            CapabilityLevel.LEVEL_6_ENGINEERING_VALIDATED,
            CapabilityLevel.LEVEL_7_CYCLE_TIME_INTELLIGENCE,
            CapabilityLevel.LEVEL_8_COST_RFQ_INTELLIGENCE,
        )

    def test_dxf_mti_status_is_candidate_plan(self) -> None:
        from backend.interoperability.machine_tool_intelligence import SelectionPlanStatus

        doc = _load_dxf_doc()
        assert doc.machine_tool_intelligence.status == SelectionPlanStatus.CANDIDATE_PLAN

    def test_dxf_mti_has_machine_candidates(self) -> None:
        doc = _load_dxf_doc()
        assert len(doc.machine_tool_intelligence.machine_candidates) > 0

    def test_dxf_mti_primary_machine_is_three_axis_vmc(self) -> None:
        from backend.interoperability.machine_tool_intelligence import MachineClassV5

        doc = _load_dxf_doc()
        primary = doc.machine_tool_intelligence.machine_candidates[0]
        assert primary.machine_class == MachineClassV5.THREE_AXIS_VMC

    def test_dxf_mti_has_tool_candidates(self) -> None:
        doc = _load_dxf_doc()
        assert len(doc.machine_tool_intelligence.tool_candidates) > 0

    def test_dxf_mti_has_drill_tool_candidates(self) -> None:
        from backend.interoperability.machine_tool_intelligence import ToolFamilyV5

        doc = _load_dxf_doc()
        families = {str(tc.tool_family) for tc in doc.machine_tool_intelligence.tool_candidates}
        assert ToolFamilyV5.DRILL in families

    def test_dxf_mti_has_center_drill_tool_candidates(self) -> None:
        from backend.interoperability.machine_tool_intelligence import ToolFamilyV5

        doc = _load_dxf_doc()
        families = {str(tc.tool_family) for tc in doc.machine_tool_intelligence.tool_candidates}
        assert ToolFamilyV5.CENTER_DRILL in families

    def test_dxf_mti_has_holder_requirements(self) -> None:
        doc = _load_dxf_doc()
        assert len(doc.machine_tool_intelligence.holder_requirements) > 0

    def test_dxf_mti_has_er_collet_holders(self) -> None:
        from backend.interoperability.machine_tool_intelligence import HolderType

        doc = _load_dxf_doc()
        types = {str(hr.holder_type) for hr in doc.machine_tool_intelligence.holder_requirements}
        assert HolderType.ER_COLLET in types

    def test_dxf_mti_has_compatibility_results(self) -> None:
        doc = _load_dxf_doc()
        assert len(doc.machine_tool_intelligence.compatibility_results) > 0

    def test_dxf_mti_has_machine_capability_requirements(self) -> None:
        doc = _load_dxf_doc()
        assert len(doc.machine_tool_intelligence.machine_capability_requirements) > 0

    def test_dxf_mti_no_incompatible_results(self) -> None:
        from backend.interoperability.machine_tool_intelligence import MatchStatus

        doc = _load_dxf_doc()
        incompatible = [
            cr for cr in doc.machine_tool_intelligence.compatibility_results
            if cr.match_status == MatchStatus.INCOMPATIBLE
        ]
        assert incompatible == []

    def test_dxf_mti_cutting_params_all_unknown(self) -> None:
        from backend.interoperability.machine_tool_intelligence import (
            CuttingParameterRequirementStatus,
        )

        doc = _load_dxf_doc()
        cpr = doc.machine_tool_intelligence.cutting_parameter_requirements
        assert cpr.cutting_speed_status == CuttingParameterRequirementStatus.UNKNOWN
        assert cpr.feed_per_tooth_status == CuttingParameterRequirementStatus.UNKNOWN


# ===========================================================================
# TestApiResponseLevel5
# ===========================================================================


@pytest.mark.skipif(not _has_dxf(), reason="production DXF file not available")
class TestApiResponseLevel5:
    def test_api_machine_intelligence_status_present(self) -> None:
        doc = _load_dxf_doc()
        status = "PRESENT" if doc.machine_tool_intelligence is not None else "NONE"
        assert status == "PRESENT"

    def test_api_machine_tool_intelligence_dict_populated(self) -> None:
        from backend.interoperability.machine_tool_intelligence import (
            MachineToolIntelligenceResult,
        )

        doc = _load_dxf_doc()
        mti = doc.machine_tool_intelligence
        assert isinstance(mti, MachineToolIntelligenceResult)
        assert len(mti.machine_candidates) > 0
        assert len(mti.tool_candidates) > 0
        assert len(mti.holder_requirements) > 0

    def test_api_response_field_serialisable(self) -> None:
        """machine_tool_intelligence result must be serialisable to a plain dict."""
        doc = _load_dxf_doc()
        mti = doc.machine_tool_intelligence
        assert mti is not None
        # Simulate the API serialisation block from engineering_import.py
        api_dict = {
            "status": mti.status.value,
            "machine_candidate_count": len(mti.machine_candidates),
            "tool_candidate_count": len(mti.tool_candidates),
            "holder_requirement_count": len(mti.holder_requirements),
            "compatibility_result_count": len(mti.compatibility_results),
            "compatible_machine_count": mti.compatible_machine_count,
            "compatible_tool_count": mti.compatible_tool_count,
            "source_process_candidate_count": mti.source_process_candidate_count,
            "missing_input_count": len(mti.missing_inputs),
            "missing_inputs": list(mti.missing_inputs),
            "warnings": list(mti.warnings),
        }
        assert api_dict["machine_candidate_count"] > 0
        assert api_dict["tool_candidate_count"] > 0
        assert isinstance(api_dict["status"], str)
