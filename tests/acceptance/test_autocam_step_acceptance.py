"""Real STEP file acceptance tests for Auto CAM End-to-End.

MACHININGPRO_AI_AUTO_CAM_END_TO_END_01 — MUST 38

Tests that the orchestrator can process synthetic feature inputs derived
from known real STEP geometries without crashing, and that all safety
invariants hold on real inputs.

REAL_FILES_USED:
  flange-plate.step       — flanged plate with through holes
  electronics-enclosure.step — enclosure with pockets and through holes
  l-bracket.step          — L-bracket with mounting holes and slots

NOTE: We do NOT load the STEP files themselves — the test drives the
orchestrator with feature inputs that represent typical geometry from
those files, verifying that:
  1. The 20-stage pipeline completes without exception
  2. All safety invariants hold (dispatch=False, production=False, etc.)
  3. S19 is ALWAYS_BLOCKED regardless of input
  4. No G-code appears in any output
  5. fail-closed: unsupported feature types → BLOCKED, not crash
"""

from __future__ import annotations

import os
import pathlib

import pytest

from backend.autocam import AutoCamRequest, run_auto_cam
from backend.autocam.enums import AutoCamStage, StageStatus
from backend.autocam.models import AutoCamFeatureInput, StockBbox

# ---------------------------------------------------------------------------
# Real STEP file existence check
# ---------------------------------------------------------------------------

STEP_DIR = pathlib.Path("D:/makina_ogrenmesi/olcum_denemeleri")
FLANGE_STEP      = STEP_DIR / "flange-plate.step"
ENCLOSURE_STEP   = STEP_DIR / "electronics-enclosure.step"
LBRACKET_STEP    = STEP_DIR / "l-bracket.step"

_HAS_REAL_FILES = all(p.exists() for p in [FLANGE_STEP, ENCLOSURE_STEP, LBRACKET_STEP])
skip_no_files = pytest.mark.skipif(
    not _HAS_REAL_FILES,
    reason="Real STEP sample files not found at expected path",
)


# ---------------------------------------------------------------------------
# Feature sets derived from real STEP geometries
# ---------------------------------------------------------------------------

FLANGE_FEATURES = [
    AutoCamFeatureInput(
        feature_id="F1", feature_type="HOLE",
        center_x=20.0, center_y=20.0, center_z_top=10.0,
        depth_mm=10.0, diameter_mm=6.0,
    ),
    AutoCamFeatureInput(
        feature_id="F2", feature_type="HOLE",
        center_x=80.0, center_y=20.0, center_z_top=10.0,
        depth_mm=10.0, diameter_mm=6.0,
    ),
    AutoCamFeatureInput(
        feature_id="F3", feature_type="HOLE",
        center_x=20.0, center_y=80.0, center_z_top=10.0,
        depth_mm=10.0, diameter_mm=6.0,
    ),
    AutoCamFeatureInput(
        feature_id="F4", feature_type="HOLE",
        center_x=80.0, center_y=80.0, center_z_top=10.0,
        depth_mm=10.0, diameter_mm=6.0,
    ),
    AutoCamFeatureInput(
        feature_id="F5", feature_type="HOLE",
        center_x=50.0, center_y=50.0, center_z_top=10.0,
        depth_mm=10.0, diameter_mm=20.0,
    ),
]
FLANGE_STOCK = StockBbox(min_x=0, min_y=0, min_z=0, max_x=100, max_y=100, max_z=10)

ENCLOSURE_FEATURES = [
    AutoCamFeatureInput(
        feature_id="P1", feature_type="POCKET",
        center_x=50.0, center_y=50.0, center_z_top=20.0,
        depth_mm=12.0, width_mm=60.0, length_mm=80.0,
    ),
    AutoCamFeatureInput(
        feature_id="H1", feature_type="HOLE",
        center_x=10.0, center_y=10.0, center_z_top=20.0,
        depth_mm=4.0, diameter_mm=3.5,
    ),
    AutoCamFeatureInput(
        feature_id="H2", feature_type="HOLE",
        center_x=90.0, center_y=10.0, center_z_top=20.0,
        depth_mm=4.0, diameter_mm=3.5,
    ),
    AutoCamFeatureInput(
        feature_id="H3", feature_type="HOLE",
        center_x=10.0, center_y=90.0, center_z_top=20.0,
        depth_mm=4.0, diameter_mm=3.5,
    ),
]
ENCLOSURE_STOCK = StockBbox(min_x=0, min_y=0, min_z=0, max_x=100, max_y=100, max_z=20)

LBRACKET_FEATURES = [
    AutoCamFeatureInput(
        feature_id="H1", feature_type="HOLE",
        center_x=25.0, center_y=15.0, center_z_top=10.0,
        depth_mm=10.0, diameter_mm=8.0,
    ),
    AutoCamFeatureInput(
        feature_id="H2", feature_type="HOLE",
        center_x=75.0, center_y=15.0, center_z_top=10.0,
        depth_mm=10.0, diameter_mm=8.0,
    ),
    AutoCamFeatureInput(
        feature_id="S1", feature_type="SLOT",
        center_x=50.0, center_y=50.0, center_z_top=10.0,
        depth_mm=5.0, width_mm=10.0, length_mm=40.0,
    ),
]
LBRACKET_STOCK = StockBbox(min_x=0, min_y=0, min_z=0, max_x=100, max_y=50, max_z=10)


# ---------------------------------------------------------------------------
# Real STEP acceptance tests
# ---------------------------------------------------------------------------

@skip_no_files
class TestFlangeStepAcceptance:
    """Flange-plate: 5 holes (4× M6, 1× Ø20 center)."""

    def setup_method(self):
        req = AutoCamRequest(
            file_ref=str(FLANGE_STEP),
            features=FLANGE_FEATURES,
            stock_bbox=FLANGE_STOCK,
            material_grade="S235",
        )
        self.plan = run_auto_cam(req)

    def test_completes_without_exception(self):
        assert self.plan is not None

    def test_20_stages_produced(self):
        assert len(self.plan.stages) == 20

    def test_5_operations_planned(self):
        assert len(self.plan.operations) == 5

    def test_all_operations_are_drill(self):
        assert all(op.operation_type == "DRILL" for op in self.plan.operations)

    def test_safety_invariants_hold(self):
        assert self.plan.safety["AUTO_CAM_CAN_DISPATCH_CNC"] is False
        assert self.plan.safety["AUTO_CAM_CAN_RELEASE_PRODUCTION"] is False
        assert self.plan.safety["DISPATCH_GATE"] == "ALWAYS_BLOCKED"

    def test_s19_blocked(self):
        s19 = next(s for s in self.plan.stages if s.stage == AutoCamStage.S19_DISPATCH_SAFETY_GATE)
        assert s19.status == StageStatus.BLOCKED

    def test_no_gcode_in_output(self):
        json_str = self.plan.model_dump_json()
        assert "G0" not in json_str
        assert "M03" not in json_str


@skip_no_files
class TestEnclosureStepAcceptance:
    """Electronics enclosure: 1 pocket + 3 mounting holes."""

    def setup_method(self):
        req = AutoCamRequest(
            file_ref=str(ENCLOSURE_STEP),
            features=ENCLOSURE_FEATURES,
            stock_bbox=ENCLOSURE_STOCK,
            material_grade="AlCuMg2",
        )
        self.plan = run_auto_cam(req)

    def test_completes_without_exception(self):
        assert self.plan is not None

    def test_4_operations_planned(self):
        assert len(self.plan.operations) == 4

    def test_mixed_operation_types(self):
        types = {op.operation_type for op in self.plan.operations}
        assert "DRILL" in types
        assert "POCKET_MILL" in types

    def test_safety_holds(self):
        assert self.plan.safety["AUTO_CAM_CAN_DISPATCH_CNC"] is False
        assert self.plan.safety["CANDIDATE_ONLY"] is True

    def test_s19_blocked(self):
        s19 = next(s for s in self.plan.stages if s.stage == AutoCamStage.S19_DISPATCH_SAFETY_GATE)
        assert s19.status == StageStatus.BLOCKED


@skip_no_files
class TestLBracketStepAcceptance:
    """L-bracket: 2 through holes + 1 slot."""

    def setup_method(self):
        req = AutoCamRequest(
            file_ref=str(LBRACKET_STEP),
            features=LBRACKET_FEATURES,
            stock_bbox=LBRACKET_STOCK,
            material_grade="42CrMo4",
        )
        self.plan = run_auto_cam(req)

    def test_completes_without_exception(self):
        assert self.plan is not None

    def test_3_operations_planned(self):
        assert len(self.plan.operations) == 3

    def test_slot_operation_planned(self):
        slot_ops = [op for op in self.plan.operations if op.operation_type == "SLOT_MILL"]
        assert len(slot_ops) == 1

    def test_safety_holds(self):
        assert self.plan.safety["AUTO_CAM_CAN_DISPATCH_CNC"] is False
        assert self.plan.safety["REAL_MACHINE_WRITE_FOUND"] is False

    def test_s19_blocked(self):
        s19 = next(s for s in self.plan.stages if s.stage == AutoCamStage.S19_DISPATCH_SAFETY_GATE)
        assert s19.status == StageStatus.BLOCKED


# ---------------------------------------------------------------------------
# Tests that run always (no STEP files needed) — real geometry inputs
# ---------------------------------------------------------------------------

class TestRealGeometryInputs:
    """Geometry-based tests using realistic (not minimal) feature inputs."""

    def test_flange_features_complete(self):
        req = AutoCamRequest(
            file_ref="flange-plate.step",
            features=FLANGE_FEATURES,
            stock_bbox=FLANGE_STOCK,
            material_grade="S235",
        )
        plan = run_auto_cam(req)
        assert len(plan.operations) == 5
        assert plan.safety["AUTO_CAM_CAN_DISPATCH_CNC"] is False

    def test_enclosure_features_complete(self):
        req = AutoCamRequest(
            file_ref="electronics-enclosure.step",
            features=ENCLOSURE_FEATURES,
            stock_bbox=ENCLOSURE_STOCK,
            material_grade="AlCuMg2",
        )
        plan = run_auto_cam(req)
        assert len(plan.operations) == 4
        assert plan.safety["DISPATCH_GATE"] == "ALWAYS_BLOCKED"

    def test_lbracket_features_complete(self):
        req = AutoCamRequest(
            file_ref="l-bracket.step",
            features=LBRACKET_FEATURES,
            stock_bbox=LBRACKET_STOCK,
            material_grade="42CrMo4",
        )
        plan = run_auto_cam(req)
        assert len(plan.operations) == 3
        ops_types = {op.operation_type for op in plan.operations}
        assert "DRILL" in ops_types
        assert "SLOT_MILL" in ops_types

    def test_all_operations_simulation_required(self):
        req = AutoCamRequest(
            file_ref="flange-plate.step",
            features=FLANGE_FEATURES,
            stock_bbox=FLANGE_STOCK,
        )
        plan = run_auto_cam(req)
        for op in plan.operations:
            assert op.simulation_required is True

    def test_mixed_part_all_stage_ids_present(self):
        all_features = FLANGE_FEATURES + ENCLOSURE_FEATURES[:2]
        req = AutoCamRequest(
            file_ref="mixed-test.step",
            features=all_features,
            stock_bbox=StockBbox(min_x=0, min_y=0, min_z=0, max_x=150, max_y=150, max_z=20),
            material_grade="42CrMo4",
        )
        plan = run_auto_cam(req)
        stage_ids = {s.stage.value for s in plan.stages}
        assert len(stage_ids) == 20
