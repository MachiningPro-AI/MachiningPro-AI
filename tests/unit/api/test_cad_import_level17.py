"""
Level-17 CNC Job Planning & Machine Assignment — unit tests.

ASSIGNMENT_IS_PROPOSED_ONLY=YES
NO_AUTOMATIC_DISPATCH=YES
MISSING_DATA_FAILS_CLOSED=YES
NO_FABRICATED_CAPABILITY=YES
HUMAN_APPROVAL_MANDATORY=YES
"""

from __future__ import annotations

import pytest

from backend.job_planning import (
    ASSIGNMENT_IS_PROPOSED_ONLY,
    HUMAN_APPROVAL_MANDATORY,
    MISSING_DATA_FAILS_CLOSED,
    NO_AUTOMATIC_JOB_DISPATCH,
    NO_AUTOMATIC_MACHINE_ASSIGNMENT,
    NO_FABRICATED_CAPABILITY_DATA,
    UNKNOWN_CAPABILITY_IS_NOT_ELIGIBLE,
    AssignmentStatus,
    MaterialCompatibilityResult,
    PlanningBlockReason,
    RankingObjective,
    SpindleMatchResult,
    WorkloadStatus,
    check_material_compatibility,
    check_process_capabilities,
    check_spindle_requirements,
    compute_capability_score,
    compute_overall_score,
    estimate_workload,
    explain_candidate,
    explain_recommendation,
    material_compat_score,
    plan_job_assignment,
    rank_candidates,
    spindle_match_score,
    workload_score,
)
from backend.job_planning.enums import CapabilityMatchLevel as CML
from backend.job_planning.models import (
    AssignmentCandidate,
    AssignmentRecommendation,
    CamOperationRequirements,
    CapabilityCheckResult,
    MachineCapabilityProfile,
    WorkloadEstimate,
)
from backend.scheduling.enums import MachineClass

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_requirements(**kwargs) -> CamOperationRequirements:
    defaults = dict(
        job_id="JOB_TEST_001",
        material="AL_6082_T6",
        operations=["MILLING"],
        required_machine_class=MachineClass.VMC_3AXIS,
        required_axis_count=3,
        required_spindle_rpm=6000.0,
        required_x_travel_mm=400.0,
        required_y_travel_mm=300.0,
        required_z_travel_mm=300.0,
        is_fabricated_requirements=False,
    )
    defaults.update(kwargs)
    return CamOperationRequirements(**defaults)


def _make_profile(**kwargs) -> MachineCapabilityProfile:
    defaults = dict(
        machine_id="VMC_001",
        machine_class=MachineClass.VMC_3AXIS,
        axis_count=3,
        spindle_max_rpm=12000,
        spindle_power_kw=15.0,
        travel_x_mm=600.0,
        travel_y_mm=500.0,
        travel_z_mm=400.0,
        table_load_kg=300.0,
        turning_capable=False,
        milling_capable=True,
        drilling_capable=True,
        through_spindle_coolant=True,
        has_live_tooling=False,
        capable_tapping=True,
        capable_boring=True,
        is_fabricated_capability=False,
    )
    defaults.update(kwargs)
    return MachineCapabilityProfile(**defaults)


def _make_workload(**kwargs) -> WorkloadEstimate:
    defaults = dict(
        machine_id="VMC_001",
        queue_depth=0,
        estimated_cycle_time_min=45.0,
        workload_status=WorkloadStatus.LOW,
        is_fabricated=False,
    )
    defaults.update(kwargs)
    return WorkloadEstimate(**defaults)


def _make_candidate(**kwargs) -> AssignmentCandidate:
    defaults = dict(
        machine_id="VMC_001",
        rank=1,
        capability_score=0.9,
        material_compatibility=MaterialCompatibilityResult.COMPATIBLE,
        spindle_match=SpindleMatchResult.WITHIN_RANGE,
        workload_status=WorkloadStatus.LOW,
        capability_checks=[],
        workload_estimate=_make_workload(),
        incompatibility_reasons=[],
        soft_preference_score=0.5,
        overall_score=0.85,
        explanation="Good match",
        is_proposed_only=True,
        is_automatic_dispatch=False,
    )
    defaults.update(kwargs)
    return AssignmentCandidate(**defaults)


# ===========================================================================
# Safety invariants
# ===========================================================================

class TestSafetyInvariants:
    def test_no_automatic_machine_assignment_true(self):
        assert NO_AUTOMATIC_MACHINE_ASSIGNMENT is True

    def test_no_automatic_job_dispatch_true(self):
        assert NO_AUTOMATIC_JOB_DISPATCH is True

    def test_no_fabricated_capability_data_true(self):
        assert NO_FABRICATED_CAPABILITY_DATA is True

    def test_missing_data_fails_closed_true(self):
        assert MISSING_DATA_FAILS_CLOSED is True

    def test_assignment_is_proposed_only_true(self):
        assert ASSIGNMENT_IS_PROPOSED_ONLY is True

    def test_human_approval_mandatory_true(self):
        assert HUMAN_APPROVAL_MANDATORY is True

    def test_unknown_capability_is_not_eligible_true(self):
        assert UNKNOWN_CAPABILITY_IS_NOT_ELIGIBLE is True

    def test_requirement_model_fabricated_invariant(self):
        req = _make_requirements()
        assert req.is_fabricated_requirements is False

    def test_capability_profile_fabricated_invariant(self):
        profile = _make_profile()
        assert profile.is_fabricated_capability is False

    def test_workload_estimate_fabricated_invariant(self):
        wl = _make_workload()
        assert wl.is_fabricated is False

    def test_candidate_proposed_only_invariant(self):
        c = _make_candidate()
        assert c.is_proposed_only is True

    def test_candidate_no_automatic_dispatch_invariant(self):
        c = _make_candidate()
        assert c.is_automatic_dispatch is False

    def test_recommendation_proposed_only_invariant(self):
        req = _make_requirements()
        profiles = [_make_profile()]
        rec = plan_job_assignment(req, profiles)
        assert rec.is_proposed_only is True

    def test_recommendation_no_dispatch_invariant(self):
        req = _make_requirements()
        profiles = [_make_profile()]
        rec = plan_job_assignment(req, profiles)
        assert rec.is_automatic_dispatch is False

    def test_recommendation_review_required_invariant(self):
        req = _make_requirements()
        profiles = [_make_profile()]
        rec = plan_job_assignment(req, profiles)
        assert rec.review_required is True

    def test_recommendation_no_fabricated_data_invariant(self):
        req = _make_requirements()
        profiles = [_make_profile()]
        rec = plan_job_assignment(req, profiles)
        assert rec.is_fabricated_data is False

    def test_dispatched_status_not_in_assignment_status(self):
        allowed = {s.value for s in AssignmentStatus}
        assert "DISPATCHED_TO_MACHINE" not in allowed
        assert "EXECUTING" not in allowed
        assert "AUTO_ASSIGNED" not in allowed

    def test_recommendation_always_proposed_or_review(self):
        req = _make_requirements()
        profiles = [_make_profile()]
        rec = plan_job_assignment(req, profiles)
        assert rec.status in (
            AssignmentStatus.PROPOSED,
            AssignmentStatus.REVIEW_REQUIRED,
        )


# ===========================================================================
# CamOperationRequirements model
# ===========================================================================

class TestCamOperationRequirements:
    def test_basic_creation(self):
        req = _make_requirements()
        assert req.job_id == "JOB_TEST_001"
        assert req.material == "AL_6082_T6"
        assert req.operations == ["MILLING"]

    def test_default_operations_empty(self):
        req = CamOperationRequirements(job_id="X", is_fabricated_requirements=False)
        assert req.operations == []

    def test_default_machine_class_unknown(self):
        req = CamOperationRequirements(job_id="X", is_fabricated_requirements=False)
        assert req.required_machine_class == MachineClass.UNKNOWN

    def test_all_optional_fields_default_none(self):
        req = CamOperationRequirements(job_id="X", is_fabricated_requirements=False)
        assert req.material is None
        assert req.required_axis_count is None
        assert req.required_spindle_rpm is None
        assert req.estimated_cycle_time_min is None

    def test_boolean_defaults_false(self):
        req = CamOperationRequirements(job_id="X", is_fabricated_requirements=False)
        assert req.requires_tapping is False
        assert req.requires_boring is False
        assert req.requires_live_tooling is False
        assert req.requires_through_spindle_coolant is False

    def test_data_source_default_cam_plan(self):
        req = CamOperationRequirements(job_id="X", is_fabricated_requirements=False)
        assert req.data_source == "CAM_PLAN"

    def test_multiple_operations(self):
        req = _make_requirements(operations=["TURNING", "MILLING", "DRILLING"])
        assert len(req.operations) == 3


# ===========================================================================
# MachineCapabilityProfile model
# ===========================================================================

class TestMachineCapabilityProfile:
    def test_basic_creation(self):
        profile = _make_profile()
        assert profile.machine_id == "VMC_001"
        assert profile.machine_class == MachineClass.VMC_3AXIS

    def test_all_optional_fields_can_be_none(self):
        profile = MachineCapabilityProfile(
            machine_id="X",
            is_fabricated_capability=False,
        )
        assert profile.axis_count is None
        assert profile.spindle_max_rpm is None
        assert profile.travel_x_mm is None

    def test_boolean_defaults_false(self):
        profile = MachineCapabilityProfile(
            machine_id="X",
            is_fabricated_capability=False,
        )
        assert profile.turning_capable is False
        assert profile.milling_capable is False
        assert profile.has_live_tooling is False

    def test_machine_class_default_unknown(self):
        profile = MachineCapabilityProfile(
            machine_id="X",
            is_fabricated_capability=False,
        )
        assert profile.machine_class == MachineClass.UNKNOWN

    def test_lathe_profile(self):
        profile = _make_profile(
            machine_class=MachineClass.LATHE_2AXIS,
            turning_capable=True,
            milling_capable=False,
        )
        assert profile.turning_capable is True
        assert profile.milling_capable is False


# ===========================================================================
# Material compatibility
# ===========================================================================

class TestMaterialCompatibility:
    def test_al6082_vmc3axis_compatible(self):
        result = check_material_compatibility("AL_6082_T6", MachineClass.VMC_3AXIS)
        assert result.result == MaterialCompatibilityResult.COMPATIBLE

    def test_al7075_vmc5axis_compatible(self):
        result = check_material_compatibility("AL_7075_T6", MachineClass.VMC_5AXIS)
        assert result.result == MaterialCompatibilityResult.COMPATIBLE

    def test_titanium_vmc3axis_incompatible(self):
        result = check_material_compatibility("TITANIUM_TI6AL4V", MachineClass.VMC_3AXIS)
        assert result.result == MaterialCompatibilityResult.INCOMPATIBLE

    def test_titanium_vmc5axis_compatible(self):
        result = check_material_compatibility("TITANIUM_TI6AL4V", MachineClass.VMC_5AXIS)
        assert result.result == MaterialCompatibilityResult.COMPATIBLE

    def test_none_material_returns_unknown(self):
        result = check_material_compatibility(None, MachineClass.VMC_3AXIS)
        assert result.result == MaterialCompatibilityResult.UNKNOWN

    def test_unknown_machine_class_returns_unknown(self):
        result = check_material_compatibility("AL_6082_T6", MachineClass.UNKNOWN)
        assert result.result == MaterialCompatibilityResult.UNKNOWN

    def test_unknown_material_returns_unknown(self):
        result = check_material_compatibility("EXOTIC_XYZ", MachineClass.VMC_3AXIS)
        assert result.result == MaterialCompatibilityResult.UNKNOWN

    def test_check_has_reason(self):
        result = check_material_compatibility("AL_6082_T6", MachineClass.VMC_3AXIS)
        assert len(result.reason) > 0

    def test_incompatibility_reason_set(self):
        result = check_material_compatibility("TITANIUM_TI6AL4V", MachineClass.VMC_3AXIS)
        assert "not in the compatible set" in result.reason

    def test_lathe_with_aluminium_compatible(self):
        result = check_material_compatibility("AL_6082_T6", MachineClass.LATHE_2AXIS)
        assert result.result == MaterialCompatibilityResult.COMPATIBLE

    def test_stainless_hmc3axis_compatible(self):
        result = check_material_compatibility("SS_304", MachineClass.HMC_3AXIS)
        assert result.result == MaterialCompatibilityResult.COMPATIBLE

    def test_grinder_class_unknown_for_aluminium(self):
        result = check_material_compatibility("AL_6082_T6", MachineClass.GRINDER)
        # GRINDER is not in the compatible set for aluminium in standard machining
        assert result.result == MaterialCompatibilityResult.INCOMPATIBLE


# ===========================================================================
# Spindle matching
# ===========================================================================

class TestSpindleMatching:
    def test_within_range(self):
        result = check_spindle_requirements(6000.0, 12000)
        assert result.result == SpindleMatchResult.WITHIN_RANGE

    def test_utilization_calculated(self):
        result = check_spindle_requirements(6000.0, 12000)
        assert result.utilization_pct == pytest.approx(50.0)

    def test_over_limit(self):
        result = check_spindle_requirements(15000.0, 12000)
        assert result.result == SpindleMatchResult.OVER_LIMIT

    def test_at_limit(self):
        result = check_spindle_requirements(11500.0, 12000)
        assert result.result == SpindleMatchResult.AT_LIMIT

    def test_no_requirement_within_range(self):
        result = check_spindle_requirements(None, 12000)
        assert result.result == SpindleMatchResult.WITHIN_RANGE
        assert result.utilization_pct is None

    def test_unknown_machine_rpm_returns_unknown(self):
        result = check_spindle_requirements(6000.0, None)
        assert result.result == SpindleMatchResult.UNKNOWN

    def test_zero_machine_rpm_returns_under_spec(self):
        result = check_spindle_requirements(6000.0, 0)
        assert result.result == SpindleMatchResult.UNDER_SPEC

    def test_exact_limit_at_100pct(self):
        result = check_spindle_requirements(12000.0, 12000)
        # 100% utilization > AT_LIMIT threshold (95%)
        assert result.result == SpindleMatchResult.AT_LIMIT
        assert result.utilization_pct == pytest.approx(100.0)


# ===========================================================================
# Process capability matching
# ===========================================================================

class TestProcessCapabilityMatching:
    def test_milling_full_match(self):
        req = _make_requirements(operations=["MILLING"])
        profile = _make_profile(milling_capable=True)
        checks = check_process_capabilities(req, profile)
        milling = next((c for c in checks if c.check_name == "milling_capability"), None)
        assert milling is not None
        assert milling.match_level == CML.FULL_MATCH

    def test_milling_no_match_when_not_capable(self):
        req = _make_requirements(operations=["MILLING"])
        profile = _make_profile(milling_capable=False)
        checks = check_process_capabilities(req, profile)
        milling = next((c for c in checks if c.check_name == "milling_capability"), None)
        assert milling is not None
        assert milling.match_level == CML.NO_MATCH

    def test_turning_full_match(self):
        req = _make_requirements(operations=["TURNING"])
        profile = _make_profile(turning_capable=True)
        checks = check_process_capabilities(req, profile)
        turning = next((c for c in checks if c.check_name == "turning_capability"), None)
        assert turning is not None
        assert turning.match_level == CML.FULL_MATCH

    def test_turning_no_match(self):
        req = _make_requirements(operations=["TURNING"])
        profile = _make_profile(turning_capable=False)
        checks = check_process_capabilities(req, profile)
        turning = next((c for c in checks if c.check_name == "turning_capability"), None)
        assert turning is not None
        assert turning.match_level == CML.NO_MATCH

    def test_tapping_unknown_when_capability_none(self):
        req = _make_requirements(requires_tapping=True)
        profile = _make_profile(capable_tapping=None)
        checks = check_process_capabilities(req, profile)
        tapping = next((c for c in checks if c.check_name == "tapping_capability"), None)
        assert tapping is not None
        assert tapping.match_level == CML.UNKNOWN

    def test_boring_no_match(self):
        req = _make_requirements(requires_boring=True)
        profile = _make_profile(capable_boring=False)
        checks = check_process_capabilities(req, profile)
        boring = next((c for c in checks if c.check_name == "boring_capability"), None)
        assert boring is not None
        assert boring.match_level == CML.NO_MATCH

    def test_live_tooling_no_match(self):
        req = _make_requirements(requires_live_tooling=True)
        profile = _make_profile(has_live_tooling=False)
        checks = check_process_capabilities(req, profile)
        lt = next((c for c in checks if c.check_name == "live_tooling"), None)
        assert lt is not None
        assert lt.match_level == CML.NO_MATCH

    def test_tsc_unknown_when_none(self):
        req = _make_requirements(requires_through_spindle_coolant=True)
        profile = _make_profile(through_spindle_coolant=None)
        checks = check_process_capabilities(req, profile)
        tsc = next((c for c in checks if c.check_name == "through_spindle_coolant"), None)
        assert tsc is not None
        assert tsc.match_level == CML.UNKNOWN

    def test_axis_count_no_match(self):
        req = _make_requirements(required_axis_count=5)
        profile = _make_profile(axis_count=3)
        checks = check_process_capabilities(req, profile)
        axis = next((c for c in checks if c.check_name == "axis_count"), None)
        assert axis is not None
        assert axis.match_level == CML.NO_MATCH

    def test_axis_count_full_match_exact(self):
        req = _make_requirements(required_axis_count=3)
        profile = _make_profile(axis_count=3)
        checks = check_process_capabilities(req, profile)
        axis = next((c for c in checks if c.check_name == "axis_count"), None)
        assert axis is not None
        assert axis.match_level == CML.FULL_MATCH

    def test_x_travel_no_match(self):
        req = _make_requirements(required_x_travel_mm=800.0)
        profile = _make_profile(travel_x_mm=600.0)
        checks = check_process_capabilities(req, profile)
        x = next((c for c in checks if c.check_name == "x_travel"), None)
        assert x is not None
        assert x.match_level == CML.NO_MATCH


# ===========================================================================
# Workload estimation
# ===========================================================================

class TestWorkloadEstimation:
    def test_no_queue_low_workload(self):
        wl = estimate_workload("M1", queue_depth=0)
        assert wl.workload_status == WorkloadStatus.LOW

    def test_queue_1_low(self):
        wl = estimate_workload("M1", queue_depth=1)
        assert wl.workload_status == WorkloadStatus.LOW

    def test_queue_2_moderate(self):
        wl = estimate_workload("M1", queue_depth=2)
        assert wl.workload_status == WorkloadStatus.MODERATE

    def test_queue_4_high(self):
        wl = estimate_workload("M1", queue_depth=4)
        assert wl.workload_status == WorkloadStatus.HIGH

    def test_queue_7_overloaded(self):
        wl = estimate_workload("M1", queue_depth=7)
        assert wl.workload_status == WorkloadStatus.OVERLOADED

    def test_none_queue_unknown(self):
        wl = estimate_workload("M1", queue_depth=None)
        assert wl.workload_status == WorkloadStatus.UNKNOWN

    def test_never_fabricated(self):
        wl = estimate_workload("M1", queue_depth=5)
        assert wl.is_fabricated is False

    def test_cycle_time_preserved(self):
        wl = estimate_workload("M1", queue_depth=0, estimated_cycle_time_min=45.0)
        assert wl.estimated_cycle_time_min == 45.0


# ===========================================================================
# Capability scoring
# ===========================================================================

class TestCapabilityScoring:
    def test_all_full_match_score_1(self):
        checks = [
            CapabilityCheckResult(check_name="a", match_level=CML.FULL_MATCH),
            CapabilityCheckResult(check_name="b", match_level=CML.FULL_MATCH),
        ]
        assert compute_capability_score(checks) == pytest.approx(1.0)

    def test_all_no_match_score_0(self):
        checks = [
            CapabilityCheckResult(check_name="a", match_level=CML.NO_MATCH),
        ]
        assert compute_capability_score(checks) == pytest.approx(0.0)

    def test_empty_checks_score_1(self):
        assert compute_capability_score([]) == pytest.approx(1.0)

    def test_mixed_checks_average(self):
        checks = [
            CapabilityCheckResult(check_name="a", match_level=CML.FULL_MATCH),
            CapabilityCheckResult(check_name="b", match_level=CML.NO_MATCH),
        ]
        # (1.0 + 0.0) / 2 = 0.5
        assert compute_capability_score(checks) == pytest.approx(0.5)

    def test_unknown_check_score_04(self):
        checks = [
            CapabilityCheckResult(check_name="a", match_level=CML.UNKNOWN),
        ]
        assert compute_capability_score(checks) == pytest.approx(0.4)

    def test_material_compat_score_compatible(self):
        assert material_compat_score(MaterialCompatibilityResult.COMPATIBLE) == pytest.approx(1.0)

    def test_material_compat_score_incompatible(self):
        assert material_compat_score(MaterialCompatibilityResult.INCOMPATIBLE) == pytest.approx(0.0)

    def test_material_compat_score_unknown(self):
        assert material_compat_score(MaterialCompatibilityResult.UNKNOWN) == pytest.approx(0.4)

    def test_spindle_score_within_range(self):
        assert spindle_match_score(SpindleMatchResult.WITHIN_RANGE) == pytest.approx(1.0)

    def test_spindle_score_over_limit(self):
        assert spindle_match_score(SpindleMatchResult.OVER_LIMIT) == pytest.approx(0.0)

    def test_workload_score_low(self):
        assert workload_score(WorkloadStatus.LOW) == pytest.approx(1.0)

    def test_workload_score_overloaded(self):
        assert workload_score(WorkloadStatus.OVERLOADED) == pytest.approx(0.1)

    def test_overall_score_clamped_0_1(self):
        score = compute_overall_score(
            capability=1.0,
            material=MaterialCompatibilityResult.COMPATIBLE,
            spindle=SpindleMatchResult.WITHIN_RANGE,
            workload=WorkloadStatus.LOW,
        )
        assert 0.0 <= score <= 1.0


# ===========================================================================
# Ranking
# ===========================================================================

class TestRanking:
    def _make_candidates(self) -> list[AssignmentCandidate]:
        return [
            _make_candidate(machine_id="A", overall_score=0.3),
            _make_candidate(machine_id="B", overall_score=0.9),
            _make_candidate(machine_id="C", overall_score=0.6),
        ]

    def test_ranked_by_descending_score(self):
        candidates = self._make_candidates()
        ranked = rank_candidates(candidates)
        scores = [c.overall_score for c in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_rank_field_updated(self):
        candidates = self._make_candidates()
        ranked = rank_candidates(candidates)
        assert ranked[0].rank == 1
        assert ranked[1].rank == 2
        assert ranked[2].rank == 3

    def test_best_candidate_first(self):
        candidates = self._make_candidates()
        ranked = rank_candidates(candidates)
        assert ranked[0].machine_id == "B"

    def test_different_objectives_rank_differently(self):
        # Higher workload score dominates under WORKLOAD_BALANCE
        low_wl = _make_candidate(
            machine_id="LOW",
            overall_score=compute_overall_score(
                0.9, MaterialCompatibilityResult.COMPATIBLE,
                SpindleMatchResult.WITHIN_RANGE, WorkloadStatus.LOW,
                RankingObjective.WORKLOAD_BALANCE,
            ),
        )
        high_wl = _make_candidate(
            machine_id="HIGH",
            overall_score=compute_overall_score(
                0.9, MaterialCompatibilityResult.COMPATIBLE,
                SpindleMatchResult.WITHIN_RANGE, WorkloadStatus.OVERLOADED,
                RankingObjective.WORKLOAD_BALANCE,
            ),
        )
        ranked = rank_candidates([high_wl, low_wl], RankingObjective.WORKLOAD_BALANCE)
        assert ranked[0].machine_id == "LOW"


# ===========================================================================
# Assignment recommendation
# ===========================================================================

class TestAssignmentRecommendation:
    def test_basic_plan_returns_recommendation(self):
        req = _make_requirements()
        profiles = [_make_profile()]
        rec = plan_job_assignment(req, profiles)
        assert isinstance(rec, AssignmentRecommendation)

    def test_recommendation_has_candidates(self):
        req = _make_requirements()
        profiles = [_make_profile()]
        rec = plan_job_assignment(req, profiles)
        assert len(rec.candidates) == 1

    def test_best_candidate_set_when_eligible(self):
        req = _make_requirements()
        profiles = [_make_profile()]
        rec = plan_job_assignment(req, profiles)
        assert rec.best_candidate_id == "VMC_001"

    def test_multiple_machines_ranked(self):
        req = _make_requirements()
        profiles = [
            _make_profile(machine_id="A"),
            _make_profile(machine_id="B"),
            _make_profile(machine_id="C"),
        ]
        rec = plan_job_assignment(req, profiles)
        assert len(rec.candidates) == 3
        ranks = [c.rank for c in rec.candidates]
        assert ranks == [1, 2, 3]

    def test_no_machines_returns_blocked_recommendation(self):
        req = _make_requirements()
        rec = plan_job_assignment(req, machines=[])
        assert PlanningBlockReason.NO_MACHINES_PROVIDED in rec.blocking_reasons
        assert rec.best_candidate_id is None

    def test_incompatible_material_no_best_candidate(self):
        req = _make_requirements(material="TITANIUM_TI6AL4V")
        profiles = [_make_profile(machine_class=MachineClass.VMC_3AXIS)]
        rec = plan_job_assignment(req, profiles)
        assert rec.best_candidate_id is None

    def test_recommendation_explanation_set(self):
        req = _make_requirements()
        profiles = [_make_profile()]
        rec = plan_job_assignment(req, profiles)
        assert len(rec.explanation) > 0

    def test_candidate_explanation_set(self):
        req = _make_requirements()
        profiles = [_make_profile()]
        rec = plan_job_assignment(req, profiles)
        assert all(len(c.explanation) > 0 for c in rec.candidates)

    def test_missing_material_adds_warning(self):
        req = _make_requirements(material=None)
        profiles = [_make_profile()]
        rec = plan_job_assignment(req, profiles)
        assert any("material" in w.lower() for w in rec.planning_warnings)

    def test_queue_depths_affect_workload_status(self):
        req = _make_requirements()
        profiles = [_make_profile(machine_id="BUSY")]
        rec = plan_job_assignment(req, profiles, queue_depths={"BUSY": 7})
        assert rec.candidates[0].workload_status == WorkloadStatus.OVERLOADED

    def test_ranking_objective_propagated(self):
        req = _make_requirements()
        profiles = [_make_profile()]
        rec = plan_job_assignment(req, profiles, objective=RankingObjective.WORKLOAD_BALANCE)
        assert rec.ranking_objective == RankingObjective.WORKLOAD_BALANCE

    def test_all_candidates_have_proposed_only(self):
        req = _make_requirements()
        profiles = [_make_profile(machine_id="A"), _make_profile(machine_id="B")]
        rec = plan_job_assignment(req, profiles)
        for c in rec.candidates:
            assert c.is_proposed_only is True
            assert c.is_automatic_dispatch is False


# ===========================================================================
# Fail-closed behavior
# ===========================================================================

class TestFailClosed:
    def test_unknown_material_does_not_fabricate_compatibility(self):
        result = check_material_compatibility(None, MachineClass.VMC_3AXIS)
        assert result.result == MaterialCompatibilityResult.UNKNOWN
        assert result.result != MaterialCompatibilityResult.COMPATIBLE

    def test_unknown_machine_class_does_not_fabricate_compatibility(self):
        result = check_material_compatibility("AL_6082_T6", MachineClass.UNKNOWN)
        assert result.result == MaterialCompatibilityResult.UNKNOWN

    def test_unknown_spindle_rpm_returns_unknown(self):
        result = check_spindle_requirements(6000.0, None)
        assert result.result == SpindleMatchResult.UNKNOWN

    def test_unknown_tapping_does_not_assume_capable(self):
        req = _make_requirements(requires_tapping=True)
        profile = _make_profile(capable_tapping=None)
        checks = check_process_capabilities(req, profile)
        tapping = next((c for c in checks if c.check_name == "tapping_capability"), None)
        assert tapping is not None
        assert tapping.match_level != CML.FULL_MATCH

    def test_unknown_tsc_does_not_assume_available(self):
        req = _make_requirements(requires_through_spindle_coolant=True)
        profile = _make_profile(through_spindle_coolant=None)
        checks = check_process_capabilities(req, profile)
        tsc = next((c for c in checks if c.check_name == "through_spindle_coolant"), None)
        assert tsc is not None
        assert tsc.match_level != CML.FULL_MATCH

    def test_unknown_axis_count_not_assumed_sufficient(self):
        req = _make_requirements(required_axis_count=5)
        profile = _make_profile(axis_count=None)
        checks = check_process_capabilities(req, profile)
        axis = next((c for c in checks if c.check_name == "axis_count"), None)
        assert axis is not None
        assert axis.match_level == CML.UNKNOWN

    def test_none_queue_depth_returns_unknown_workload(self):
        wl = estimate_workload("M1", queue_depth=None)
        assert wl.workload_status == WorkloadStatus.UNKNOWN

    def test_unknown_material_lowers_score(self):
        score_known = compute_overall_score(
            1.0, MaterialCompatibilityResult.COMPATIBLE,
            SpindleMatchResult.WITHIN_RANGE, WorkloadStatus.LOW,
        )
        score_unknown = compute_overall_score(
            1.0, MaterialCompatibilityResult.UNKNOWN,
            SpindleMatchResult.WITHIN_RANGE, WorkloadStatus.LOW,
        )
        assert score_unknown < score_known

    def test_incompatible_machine_has_incompatibility_reasons(self):
        req = _make_requirements(operations=["TURNING"])
        profile = _make_profile(turning_capable=False)
        rec = plan_job_assignment(req, [profile])
        # Candidate exists but has incompatibility reasons
        assert len(rec.candidates) == 1
        c = rec.candidates[0]
        assert len(c.incompatibility_reasons) > 0

    def test_over_limit_spindle_no_best_candidate(self):
        req = _make_requirements(required_spindle_rpm=20000.0)
        profile = _make_profile(spindle_max_rpm=12000)
        rec = plan_job_assignment(req, [profile])
        # Over-limit spindle blocks best candidate
        assert rec.best_candidate_id is None


# ===========================================================================
# Explainability
# ===========================================================================

class TestExplainability:
    def test_explain_candidate_contains_machine_id(self):
        req = _make_requirements()
        profile = _make_profile()
        rec = plan_job_assignment(req, [profile])
        c = rec.candidates[0]
        explanation = explain_candidate(c, req)
        assert "VMC_001" in explanation

    def test_explain_candidate_contains_proposed_only(self):
        req = _make_requirements()
        profile = _make_profile()
        rec = plan_job_assignment(req, [profile])
        c = rec.candidates[0]
        explanation = explain_candidate(c, req)
        assert "PROPOSED ONLY" in explanation

    def test_explain_candidate_contains_rank(self):
        req = _make_requirements()
        profile = _make_profile()
        rec = plan_job_assignment(req, [profile])
        c = rec.candidates[0]
        explanation = explain_candidate(c, req)
        assert "rank #1" in explanation

    def test_explain_recommendation_contains_job_id(self):
        req = _make_requirements()
        profile = _make_profile()
        rec = plan_job_assignment(req, [profile])
        explanation = explain_recommendation(rec, req)
        assert req.job_id in explanation

    def test_explain_recommendation_contains_important_disclaimer(self):
        req = _make_requirements()
        profile = _make_profile()
        rec = plan_job_assignment(req, [profile])
        explanation = explain_recommendation(rec, req)
        assert "PROPOSED recommendation only" in explanation

    def test_explain_candidate_contains_material_info(self):
        req = _make_requirements(material="AL_6082_T6")
        profile = _make_profile()
        rec = plan_job_assignment(req, [profile])
        c = rec.candidates[0]
        explanation = explain_candidate(c, req)
        assert "AL_6082_T6" in explanation

    def test_explain_candidate_shows_gaps_for_no_match(self):
        req = _make_requirements(operations=["TURNING"])
        profile = _make_profile(turning_capable=False)
        rec = plan_job_assignment(req, [profile])
        c = rec.candidates[0]
        explanation = explain_candidate(c, req)
        assert "GAPS" in explanation or "turning_capability" in explanation

    def test_explain_recommendation_no_machines(self):
        req = _make_requirements()
        rec = plan_job_assignment(req, machines=[])
        explanation = explain_recommendation(rec, req)
        assert len(explanation) > 0


# ===========================================================================
# Capability profile building
# ===========================================================================

class TestCapabilityProfileBuilding:
    def test_build_from_catalog(self):
        from backend.job_planning.capability import build_capability_profile_from_catalog
        from backend.machines.catalog_models import MachineCatalogRecord

        record = MachineCatalogRecord(
            stable_id="CAT_001",
            manufacturer="TestMfr",
            model="TestVMC",
            machine_type="Vertical Machining Center",
            machine_type_code="VMC",
            supported_processes=["MILLING", "DRILLING"],
            axis_count=3,
            turning_capable=False,
            milling_capable=True,
            drilling_capable=True,
            spindle_max_rpm=12000,
            spindle_power_kw=15.0,
            travel_x_mm=600.0,
            travel_y_mm=500.0,
            travel_z_mm=400.0,
            source_title="Test Datasheet",
            evidence_status="MANUFACTURER_DATASHEET",
            missing_fields=[],
        )
        profile = build_capability_profile_from_catalog("CAT_001", record)
        assert profile.machine_id == "CAT_001"
        assert profile.milling_capable is True
        assert profile.spindle_max_rpm == 12000
        assert profile.is_fabricated_capability is False

    def test_build_from_resource(self):
        from backend.job_planning.capability import build_capability_profile_from_resource
        from backend.scheduling.models import MachineResource

        resource = MachineResource(
            machine_id="RES_001",
            machine_name="Test VMC",
            machine_class=MachineClass.VMC_3AXIS,
            axis_count=3,
            spindle_speed_max_rpm=12000.0,
            spindle_power_kw=15.0,
            x_travel_mm=600.0,
            y_travel_mm=500.0,
            z_travel_mm=400.0,
            supports_turning=False,
            supports_milling=True,
        )
        profile = build_capability_profile_from_resource(resource)
        assert profile.machine_id == "RES_001"
        assert profile.spindle_max_rpm == 12000
        assert profile.milling_capable is True
        assert profile.is_fabricated_capability is False

    def test_build_from_resource_none_fields_preserved(self):
        from backend.job_planning.capability import build_capability_profile_from_resource
        from backend.scheduling.models import MachineResource

        resource = MachineResource(machine_id="MIN_001", machine_name="Minimal")
        profile = build_capability_profile_from_resource(resource)
        assert profile.axis_count is None
        assert profile.spindle_max_rpm is None
        assert profile.is_fabricated_capability is False


# ===========================================================================
# Negative / safety tests
# ===========================================================================

class TestNegativeTests:
    def test_no_dispatch_status_allowed(self):
        for status in AssignmentStatus:
            assert status.value not in (
                "DISPATCHED_TO_MACHINE", "EXECUTING", "AUTO_ASSIGNED"
            ), f"Forbidden status {status!r} found in AssignmentStatus"

    def test_recommendation_is_proposed_only_cannot_be_true_false(self):
        # Pydantic allows bool override but the invariant must hold for real logic
        req = _make_requirements()
        profiles = [_make_profile()]
        rec = plan_job_assignment(req, profiles)
        # Must never be False in real output
        assert rec.is_proposed_only is True
        assert rec.is_automatic_dispatch is False

    def test_workload_is_never_fabricated(self):
        for depth in [None, 0, 1, 5, 10]:
            wl = estimate_workload("M1", queue_depth=depth)
            assert wl.is_fabricated is False

    def test_overall_score_never_negative(self):
        score = compute_overall_score(
            capability=0.0,
            material=MaterialCompatibilityResult.INCOMPATIBLE,
            spindle=SpindleMatchResult.OVER_LIMIT,
            workload=WorkloadStatus.OVERLOADED,
        )
        assert score >= 0.0

    def test_overall_score_never_exceeds_1(self):
        score = compute_overall_score(
            capability=1.0,
            material=MaterialCompatibilityResult.COMPATIBLE,
            spindle=SpindleMatchResult.WITHIN_RANGE,
            workload=WorkloadStatus.LOW,
        )
        assert score <= 1.0

    def test_capability_score_never_negative(self):
        checks = [CapabilityCheckResult(check_name="x", match_level=CML.NO_MATCH)]
        assert compute_capability_score(checks) >= 0.0

    def test_all_safety_constants_are_bool_true(self):
        from backend.job_planning import (
            ASSIGNMENT_IS_PROPOSED_ONLY,
            HUMAN_APPROVAL_MANDATORY,
            MISSING_DATA_FAILS_CLOSED,
            NO_AUTOMATIC_JOB_DISPATCH,
            NO_AUTOMATIC_MACHINE_ASSIGNMENT,
            NO_FABRICATED_CAPABILITY_DATA,
            UNKNOWN_CAPABILITY_IS_NOT_ELIGIBLE,
        )
        for const in [
            NO_AUTOMATIC_MACHINE_ASSIGNMENT,
            NO_AUTOMATIC_JOB_DISPATCH,
            NO_FABRICATED_CAPABILITY_DATA,
            MISSING_DATA_FAILS_CLOSED,
            ASSIGNMENT_IS_PROPOSED_ONLY,
            HUMAN_APPROVAL_MANDATORY,
            UNKNOWN_CAPABILITY_IS_NOT_ELIGIBLE,
        ]:
            assert const is True, f"Safety constant {const!r} must be True"

    def test_grader_class_not_in_aluminium_compatible_set(self):
        result = check_material_compatibility("AL_6082_T6", MachineClass.GRINDER)
        # Grinder is not standard for aluminium machining
        assert result.result != MaterialCompatibilityResult.LIKELY_COMPATIBLE

    def test_plan_with_all_incompatible_machines_returns_review_required(self):
        req = _make_requirements(material="TITANIUM_TI6AL4V")
        profiles = [
            _make_profile(machine_id="A", machine_class=MachineClass.VMC_3AXIS),
            _make_profile(machine_id="B", machine_class=MachineClass.VMC_3AXIS),
        ]
        rec = plan_job_assignment(req, profiles)
        assert rec.status == AssignmentStatus.REVIEW_REQUIRED
        assert rec.best_candidate_id is None
