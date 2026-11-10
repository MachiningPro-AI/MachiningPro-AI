"""Tests for the dependency graph, topological ordering, and invalidation logic."""
import pytest

from backend.workflow.dependency import (
    INVALIDATION_MAP,
    MODE_STAGES,
    STAGE_DEPENDENCIES,
    dependencies_satisfied,
    execution_order,
    invalidated_by,
    required_stages,
)
from backend.workflow.enums import StageStatus, WorkflowMode, WorkflowStage


class TestStageDependencies:
    def test_cad_import_has_no_deps(self):
        assert STAGE_DEPENDENCIES[WorkflowStage.CAD_IMPORT] == frozenset()

    def test_geometry_requires_cad_import(self):
        assert WorkflowStage.CAD_IMPORT in STAGE_DEPENDENCIES[WorkflowStage.GEOMETRY]

    def test_feature_recognition_requires_geometry(self):
        assert WorkflowStage.GEOMETRY in STAGE_DEPENDENCIES[WorkflowStage.FEATURE_RECOGNITION]

    def test_cutting_data_requires_both_tool_and_machine(self):
        deps = STAGE_DEPENDENCIES[WorkflowStage.CUTTING_DATA]
        assert WorkflowStage.TOOL_SELECTION in deps
        assert WorkflowStage.MACHINE_SELECTION in deps

    def test_nc_requires_verification(self):
        assert WorkflowStage.VERIFICATION in STAGE_DEPENDENCIES[WorkflowStage.NC_CANDIDATE]

    def test_verification_requires_toolpath(self):
        assert WorkflowStage.TOOLPATH in STAGE_DEPENDENCIES[WorkflowStage.VERIFICATION]

    def test_all_stages_have_dependency_entry(self):
        for stage in WorkflowStage:
            assert stage in STAGE_DEPENDENCIES, f"Missing dependency entry for {stage}"


class TestExecutionOrder:
    def test_cad_before_geometry(self):
        stages = frozenset(WorkflowStage)
        order = execution_order(stages)
        cad_idx = order.index(WorkflowStage.CAD_IMPORT)
        geo_idx = order.index(WorkflowStage.GEOMETRY)
        assert cad_idx < geo_idx

    def test_geometry_before_features(self):
        stages = frozenset(WorkflowStage)
        order = execution_order(stages)
        assert order.index(WorkflowStage.GEOMETRY) < order.index(WorkflowStage.FEATURE_RECOGNITION)

    def test_process_before_cam(self):
        stages = frozenset(WorkflowStage)
        order = execution_order(stages)
        assert order.index(WorkflowStage.PROCESS_PLANNING) < order.index(WorkflowStage.CAM_PLANNING)

    def test_verification_before_nc(self):
        stages = frozenset(WorkflowStage)
        order = execution_order(stages)
        assert order.index(WorkflowStage.VERIFICATION) < order.index(WorkflowStage.NC_CANDIDATE)

    def test_all_stages_included(self):
        stages = frozenset(WorkflowStage)
        order = execution_order(stages)
        assert len(order) == len(stages)
        assert set(order) == set(stages)

    def test_subset_ordering(self):
        subset = frozenset({
            WorkflowStage.CAD_IMPORT,
            WorkflowStage.GEOMETRY,
            WorkflowStage.FEATURE_RECOGNITION,
        })
        order = execution_order(subset)
        assert len(order) == 3
        assert order[0] == WorkflowStage.CAD_IMPORT


class TestRequiredStages:
    def test_analysis_only_has_3_stages(self):
        stages = required_stages(WorkflowMode.ANALYSIS_ONLY)
        assert len(stages) == 3
        assert WorkflowStage.CAD_IMPORT in stages
        assert WorkflowStage.GEOMETRY in stages
        assert WorkflowStage.FEATURE_RECOGNITION in stages

    def test_analysis_does_not_include_cam(self):
        stages = required_stages(WorkflowMode.ANALYSIS_ONLY)
        assert WorkflowStage.CAM_PLANNING not in stages

    def test_full_includes_all_19(self):
        stages = required_stages(WorkflowMode.FULL_MANUFACTURING_PLAN)
        assert len(stages) == 19

    def test_offline_nc_includes_nc(self):
        stages = required_stages(WorkflowMode.OFFLINE_NC)
        assert WorkflowStage.NC_CANDIDATE in stages

    def test_quote_only_has_cost(self):
        stages = required_stages(WorkflowMode.QUOTE_ONLY)
        assert WorkflowStage.COST_RFQ in stages
        assert WorkflowStage.CAM_PLANNING not in stages


class TestInvalidatedBy:
    def test_cad_change_invalidates_geometry(self):
        inv = invalidated_by("CAD_CHANGE")
        assert WorkflowStage.GEOMETRY in inv
        assert WorkflowStage.FEATURE_RECOGNITION in inv

    def test_material_change_does_not_invalidate_geometry(self):
        inv = invalidated_by("MATERIAL_CHANGE")
        assert WorkflowStage.GEOMETRY not in inv
        assert WorkflowStage.CAD_IMPORT not in inv

    def test_tool_change_invalidates_cutting_data(self):
        inv = invalidated_by("TOOL_CHANGE")
        assert WorkflowStage.CUTTING_DATA in inv

    def test_cost_change_does_not_invalidate_cad(self):
        inv = invalidated_by("COST_INPUT_CHANGE")
        assert WorkflowStage.CAD_IMPORT not in inv
        assert WorkflowStage.GEOMETRY not in inv

    def test_unknown_key_returns_empty(self):
        inv = invalidated_by("NONEXISTENT_CHANGE")
        assert inv == frozenset()


class TestDependenciesSatisfied:
    def test_cad_import_always_ok(self):
        ok, reasons = dependencies_satisfied(WorkflowStage.CAD_IMPORT, {})
        assert ok
        assert reasons == []

    def test_geometry_blocked_when_cad_not_pass(self):
        statuses = {WorkflowStage.CAD_IMPORT: "BLOCKED"}
        ok, reasons = dependencies_satisfied(WorkflowStage.GEOMETRY, statuses)
        assert not ok
        assert len(reasons) > 0

    def test_geometry_ok_when_cad_pass(self):
        statuses = {WorkflowStage.CAD_IMPORT: "PASS"}
        ok, reasons = dependencies_satisfied(WorkflowStage.GEOMETRY, statuses)
        assert ok

    def test_partial_dependency_allowed(self):
        # PARTIAL is treated as satisfying downstream dependency
        statuses = {
            WorkflowStage.CAD_IMPORT: "PARTIAL",
        }
        ok, reasons = dependencies_satisfied(WorkflowStage.GEOMETRY, statuses)
        assert ok

    def test_cutting_data_needs_both_tool_and_machine(self):
        statuses = {
            WorkflowStage.TOOL_SELECTION: "PASS",
            WorkflowStage.MACHINE_SELECTION: "NOT_STARTED",
        }
        ok, reasons = dependencies_satisfied(WorkflowStage.CUTTING_DATA, statuses)
        assert not ok
