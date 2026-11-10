"""Tests for Level-19 workflow enumerations."""
import pytest

from backend.workflow.enums import (
    WorkflowMode,
    WorkflowStatus,
    StageStatus,
    WorkflowStage,
    WorkflowObjective,
    EvidenceLabel,
    AuditEventType,
    AlternativePlanType,
)


class TestWorkflowMode:
    def test_all_modes_exist(self):
        expected = {
            "ANALYSIS_ONLY", "DFM_ONLY", "QUOTE_ONLY", "CAM_PLAN_ONLY",
            "CAM_AND_TOOLPATH", "OFFLINE_NC", "MACHINE_SELECTION", "FULL_MANUFACTURING_PLAN",
        }
        assert {m.value for m in WorkflowMode} == expected

    def test_full_mode(self):
        assert WorkflowMode.FULL_MANUFACTURING_PLAN == "FULL_MANUFACTURING_PLAN"


class TestStageStatus:
    def test_all_statuses(self):
        expected = {
            "NOT_STARTED", "RUNNING", "PASS", "PARTIAL", "BLOCKED",
            "FAILED", "REVIEW_REQUIRED", "SKIPPED_NOT_REQUESTED",
        }
        assert {s.value for s in StageStatus} == expected

    def test_no_success_fabrication(self):
        # PARTIAL and BLOCKED must exist (valid workflow outcomes per MUST 4)
        assert StageStatus.PARTIAL in StageStatus
        assert StageStatus.BLOCKED in StageStatus


class TestWorkflowStage:
    def test_exactly_19_stages(self):
        assert len(WorkflowStage) == 19

    def test_stage_order(self):
        stages = list(WorkflowStage)
        assert stages[0] == WorkflowStage.CAD_IMPORT
        assert stages[-1] == WorkflowStage.FINAL_MANUFACTURING_PLAN

    def test_stage_values_numbered(self):
        for stage in WorkflowStage:
            assert stage.value.startswith("0") or stage.value.startswith("1"), stage


class TestWorkflowObjective:
    def test_all_objectives(self):
        expected = {
            "MINIMUM_CYCLE_TIME", "MINIMUM_COST", "MAXIMUM_TOOL_LIFE",
            "MINIMUM_RISK", "BALANCED",
        }
        assert {o.value for o in WorkflowObjective} == expected


class TestEvidenceLabel:
    def test_all_labels(self):
        expected = {"CONFIRMED", "DERIVED", "PREDICTED", "PROPOSED", "UNKNOWN"}
        assert {l.value for l in EvidenceLabel} == expected


class TestAuditEventType:
    def test_all_audit_events(self):
        expected = {
            "WORKFLOW_CREATED", "WORKFLOW_STARTED", "STAGE_STARTED",
            "STAGE_PASSED", "STAGE_PARTIAL", "STAGE_BLOCKED", "STAGE_FAILED",
            "REVIEW_REQUIRED", "STAGE_RETRIED", "WORKFLOW_COMPLETED", "WORKFLOW_CANCELLED",
        }
        assert {e.value for e in AuditEventType} == expected


class TestAlternativePlanType:
    def test_all_plan_types(self):
        expected = {
            "FASTEST_VALID", "LOWEST_KNOWN_COST", "BEST_TOOL_LIFE_EVIDENCE",
            "LOWEST_RISK", "PARETO_ALTERNATIVE",
        }
        assert {t.value for t in AlternativePlanType} == expected
