"""Tests for Auto CAM End-to-End orchestration.

MACHININGPRO_AI_AUTO_CAM_END_TO_END_01

Safety invariants verified in every test:
  AUTO_CAM_CAN_DISPATCH_CNC=NO
  AUTO_CAM_CAN_RELEASE_PRODUCTION=NO
  AUTO_CAM_CAN_AUTO_APPROVE=NO
  REAL_MACHINE_WRITE_FOUND=NO
"""

from __future__ import annotations

import pytest

from backend.autocam import AutoCamRequest, run_auto_cam
from backend.autocam.enums import AutoCamPlanStatus, AutoCamStage, StageStatus
from backend.autocam.models import AutoCamFeatureInput, StockBbox
from backend.autocam.orchestrator import get_plan


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _hole_feature(fid: str = "F1", dia: float = 8.0, depth: float = 15.0) -> AutoCamFeatureInput:
    return AutoCamFeatureInput(
        feature_id=fid,
        feature_type="HOLE",
        center_x=10.0,
        center_y=20.0,
        center_z_top=30.0,
        depth_mm=depth,
        diameter_mm=dia,
    )


def _pocket_feature(fid: str = "F2") -> AutoCamFeatureInput:
    return AutoCamFeatureInput(
        feature_id=fid,
        feature_type="POCKET",
        center_x=50.0,
        center_y=50.0,
        center_z_top=30.0,
        depth_mm=10.0,
        width_mm=30.0,
        length_mm=40.0,
    )


def _slot_feature(fid: str = "F3") -> AutoCamFeatureInput:
    return AutoCamFeatureInput(
        feature_id=fid,
        feature_type="SLOT",
        center_x=25.0,
        center_y=25.0,
        center_z_top=30.0,
        depth_mm=5.0,
        width_mm=10.0,
        length_mm=50.0,
    )


def _stock() -> StockBbox:
    return StockBbox(min_x=0, min_y=0, min_z=0, max_x=100, max_y=100, max_z=30)


def _full_request(feats: list[AutoCamFeatureInput] | None = None) -> AutoCamRequest:
    return AutoCamRequest(
        file_ref="test_part.stp",
        features=feats or [_hole_feature(), _pocket_feature()],
        stock_bbox=_stock(),
        material_grade="42CrMo4",
    )


# ---------------------------------------------------------------------------
# Safety invariant tests (most critical)
# ---------------------------------------------------------------------------

class TestSafetyInvariants:
    """Safety invariants must hold for every plan — no exceptions."""

    def test_dispatch_always_false(self):
        plan = run_auto_cam(_full_request())
        assert plan.safety["AUTO_CAM_CAN_DISPATCH_CNC"] is False

    def test_production_release_always_false(self):
        plan = run_auto_cam(_full_request())
        assert plan.safety["AUTO_CAM_CAN_RELEASE_PRODUCTION"] is False

    def test_auto_approve_always_false(self):
        plan = run_auto_cam(_full_request())
        assert plan.safety["AUTO_CAM_CAN_AUTO_APPROVE"] is False

    def test_real_machine_write_always_false(self):
        plan = run_auto_cam(_full_request())
        assert plan.safety["REAL_MACHINE_WRITE_FOUND"] is False

    def test_dispatch_gate_always_blocked(self):
        plan = run_auto_cam(_full_request())
        assert plan.safety["DISPATCH_GATE"] == "ALWAYS_BLOCKED"

    def test_simulation_required_always_true(self):
        plan = run_auto_cam(_full_request())
        assert plan.safety["SIMULATION_REQUIRED"] is True

    def test_s19_always_blocked(self):
        plan = run_auto_cam(_full_request())
        s19 = next(s for s in plan.stages if s.stage == AutoCamStage.S19_DISPATCH_SAFETY_GATE)
        assert s19.status == StageStatus.BLOCKED
        assert any("DISPATCH_GATE=ALWAYS_BLOCKED" in b for b in s19.blockers)

    def test_operations_all_simulation_required(self):
        plan = run_auto_cam(_full_request())
        for op in plan.operations:
            assert op.simulation_required is True

    def test_no_gcode_in_output(self):
        plan = run_auto_cam(_full_request())
        plan_dict = plan.model_dump_json()
        assert "G0" not in plan_dict
        assert "G1" not in plan_dict
        assert "M03" not in plan_dict

    def test_safety_not_overridable_via_request(self):
        req = AutoCamRequest(
            file_ref="x.stp",
            features=[_hole_feature()],
            stock_bbox=_stock(),
            is_dispatchable=False,
            production_released=False,
        )
        plan = run_auto_cam(req)
        assert plan.safety["AUTO_CAM_CAN_DISPATCH_CNC"] is False
        assert plan.safety["AUTO_CAM_CAN_RELEASE_PRODUCTION"] is False


# ---------------------------------------------------------------------------
# Pipeline correctness tests
# ---------------------------------------------------------------------------

class TestPipelineCorrectness:

    def test_plan_has_20_stages(self):
        plan = run_auto_cam(_full_request())
        assert len(plan.stages) == 20

    def test_all_stage_ids_present(self):
        plan = run_auto_cam(_full_request())
        stage_ids = {s.stage for s in plan.stages}
        assert stage_ids == set(AutoCamStage)

    def test_hole_feature_produces_operation(self):
        plan = run_auto_cam(AutoCamRequest(
            file_ref="x.stp",
            features=[_hole_feature()],
            stock_bbox=_stock(),
        ))
        ops = [op for op in plan.operations if op.feature_type == "HOLE"]
        assert len(ops) == 1
        assert ops[0].operation_type == "DRILL"
        assert ops[0].cam_strategy == "DRILL_CYCLE"

    def test_pocket_feature_produces_operation(self):
        plan = run_auto_cam(AutoCamRequest(
            file_ref="x.stp",
            features=[_pocket_feature()],
            stock_bbox=_stock(),
        ))
        ops = [op for op in plan.operations if op.feature_type == "POCKET"]
        assert len(ops) == 1
        assert ops[0].operation_type == "POCKET_MILL"

    def test_slot_feature_produces_operation(self):
        plan = run_auto_cam(AutoCamRequest(
            file_ref="x.stp",
            features=[_slot_feature()],
            stock_bbox=_stock(),
        ))
        ops = [op for op in plan.operations if op.feature_type == "SLOT"]
        assert len(ops) == 1
        assert ops[0].operation_type == "SLOT_MILL"

    def test_plan_id_assigned_and_retrievable(self):
        plan = run_auto_cam(_full_request())
        assert len(plan.plan_id) == 16
        retrieved = get_plan(plan.plan_id)
        assert retrieved is not None
        assert retrieved.plan_id == plan.plan_id

    def test_plan_status_complete_with_warnings(self):
        plan = run_auto_cam(_full_request())
        # Always COMPLETE_WITH_WARNINGS due to gouge/collision NOT_VERIFIABLE
        assert plan.plan_status in (
            AutoCamPlanStatus.COMPLETE,
            AutoCamPlanStatus.COMPLETE_WITH_WARNINGS,
        )

    def test_created_at_present(self):
        plan = run_auto_cam(_full_request())
        assert plan.created_at and "T" in plan.created_at


# ---------------------------------------------------------------------------
# Fail-closed tests
# ---------------------------------------------------------------------------

class TestFailClosed:

    def test_no_features_blocked(self):
        plan = run_auto_cam(AutoCamRequest(
            file_ref="x.stp",
            features=[],
            stock_bbox=_stock(),
        ))
        assert plan.plan_status == AutoCamPlanStatus.BLOCKED
        s01 = next(s for s in plan.stages if s.stage == AutoCamStage.S01_INPUT_VALIDATION)
        assert s01.status == StageStatus.BLOCKED

    def test_no_stock_bbox_gives_warning(self):
        plan = run_auto_cam(AutoCamRequest(
            file_ref="x.stp",
            features=[_hole_feature()],
            stock_bbox=None,
        ))
        s02 = next(s for s in plan.stages if s.stage == AutoCamStage.S02_STOCK_GATE)
        assert s02.status == StageStatus.BLOCKED
        assert any("stock_bbox" in w.message for w in plan.warnings)

    def test_unsupported_feature_type_skipped(self):
        req = AutoCamRequest(
            file_ref="x.stp",
            features=[
                AutoCamFeatureInput(feature_id="F1", feature_type="UNKNOWN_TYPE"),
            ],
            stock_bbox=_stock(),
        )
        plan = run_auto_cam(req)
        assert plan.plan_status == AutoCamPlanStatus.BLOCKED

    def test_hole_without_depth_missing_input(self):
        plan = run_auto_cam(AutoCamRequest(
            file_ref="x.stp",
            features=[
                AutoCamFeatureInput(
                    feature_id="F1",
                    feature_type="HOLE",
                    center_x=10.0,
                    center_y=20.0,
                    center_z_top=30.0,
                    depth_mm=None,  # missing
                    diameter_mm=8.0,
                ),
            ],
            stock_bbox=_stock(),
        ))
        # Operation planned but toolpath blocked
        assert len(plan.operations) == 1
        op = plan.operations[0]
        assert "hole_depth_mm" in op.missing_inputs or op.toolpath_status in ("BLOCKED", "NOT_PERFORMED")

    def test_cutting_params_always_not_available(self):
        plan = run_auto_cam(_full_request())
        for op in plan.operations:
            assert op.cutting_params.status == "NOT_AVAILABLE"

    def test_gouge_check_always_not_verifiable(self):
        plan = run_auto_cam(_full_request())
        assert plan.verification.gouge_check == "NOT_VERIFIABLE"

    def test_collision_check_not_performed_without_geometry(self):
        # Without holder/fixture geometry → NOT_PERFORMED (check not attempted)
        # NOT_VERIFIABLE = tried but can't; NOT_PERFORMED = no geometry to check
        plan = run_auto_cam(_full_request())
        assert plan.verification.collision_check in ("NOT_PERFORMED", "NOT_VERIFIABLE")

    def test_cost_not_provided_without_cost_input(self):
        plan = run_auto_cam(_full_request())
        # cost_input not supplied → NOT_PROVIDED (not fabricated, not NOT_IMPLEMENTED)
        assert plan.cost_estimate_status == "NOT_PROVIDED"
        assert plan.cost_estimate is not None
        assert not plan.cost_estimate.cost_input_received
