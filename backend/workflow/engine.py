"""Level-19 WorkflowEngine — single-entry orchestrator.

Design constraints:
  DUPLICATE_LOGIC=NO          — stages delegate to Levels 1-18
  FABRICATED_RESULT=NO        — PARTIAL/BLOCKED are valid outcomes
  NO_CNC_WRITE=YES
  NO_AUTO_DISPATCH=YES
  NO_AUTO_APPROVAL=YES
  FAIL_CLOSED=YES             — dependency failures cascade as BLOCKED
  RESUME_SUPPORT=YES          — skips stages already PASS with valid hash
  RETRY_SUPPORT=YES           — retries individual FAILED/BLOCKED stages
  INVALIDATION_SUPPORT=YES    — resets stages per INVALIDATION_MAP
"""
from __future__ import annotations

from .dependency import dependencies_satisfied, execution_order, invalidated_by, required_stages
from .enums import (
    AuditEventType,
    StageStatus,
    WorkflowMode,
    WorkflowObjective,
    WorkflowStage,
    WorkflowStatus,
)
from .models import (
    ManufacturingWorkflow,
    StageResult,
)
from .stage_runners import RUNNERS


class WorkflowEngine:
    """Orchestrates the full 19-stage manufacturing workflow.

    Safety invariants (never violated):
      - No real CNC writes
      - No automatic dispatch
      - No automatic approval
      - No automatic adaptive parameter application
      - Engineering review mandatory for CAM/NC/assignment/twin stages
    """

    # Safety constants — module-level, always True
    NO_CNC_WRITE: bool = True
    NO_AUTO_DISPATCH: bool = True
    NO_AUTO_APPROVAL: bool = True
    NO_AUTO_ADAPTIVE_APPLICATION: bool = True

    def create_workflow(
        self,
        part_reference: str,
        revision: str,
        source_file_ref: str | None,
        requested_mode: WorkflowMode,
        objective: WorkflowObjective,
        material_ref: str | None,
        quantity: int,
        stock_ref: str | None,
    ) -> ManufacturingWorkflow:
        wf = ManufacturingWorkflow.create(
            part_reference=part_reference,
            revision=revision,
            source_file_ref=source_file_ref,
            requested_mode=requested_mode,
            objective=objective,
            material_ref=material_ref,
            quantity=quantity,
            stock_ref=stock_ref,
        )
        wf.add_audit(
            AuditEventType.WORKFLOW_CREATED,
            detail=f"mode={requested_mode} objective={objective}",
        )
        return wf

    def run_workflow(self, workflow: ManufacturingWorkflow) -> ManufacturingWorkflow:
        """Run all required stages in topological dependency order."""
        if workflow.status == WorkflowStatus.CANCELLED:
            return workflow

        workflow.status = WorkflowStatus.RUNNING
        workflow.add_audit(AuditEventType.WORKFLOW_STARTED)

        req = required_stages(workflow.requested_mode)
        ordered = execution_order(req)

        for stage in ordered:
            self._run_stage(workflow, stage, force=False)
            if workflow.status == WorkflowStatus.CANCELLED:
                break

        self._finalize_status(workflow)
        return workflow

    def resume_workflow(self, workflow: ManufacturingWorkflow) -> ManufacturingWorkflow:
        """Resume workflow — skip stages that already PASS with valid input hash."""
        if workflow.status == WorkflowStatus.CANCELLED:
            return workflow

        workflow.status = WorkflowStatus.RUNNING
        workflow.add_audit(AuditEventType.WORKFLOW_STARTED, detail="RESUME")

        req = required_stages(workflow.requested_mode)
        ordered = execution_order(req)

        for stage in ordered:
            existing = workflow.stage_results.get(stage)
            if existing and existing.status == StageStatus.PASS:
                # Stage already passed — check hash validity
                current_hash = workflow.context.input_hash(
                    ["source_file_ref", "material_ref", "stock_ref"]
                )
                if existing.input_hash and existing.input_hash == current_hash:
                    continue  # Skip: still valid

            self._run_stage(workflow, stage, force=False)
            if workflow.status == WorkflowStatus.CANCELLED:
                break

        self._finalize_status(workflow)
        return workflow

    def retry_stage(
        self, workflow: ManufacturingWorkflow, stage: WorkflowStage
    ) -> ManufacturingWorkflow:
        """Retry a single FAILED or BLOCKED stage."""
        existing = workflow.stage_results.get(stage)
        if existing and existing.status not in (StageStatus.FAILED, StageStatus.BLOCKED):
            return workflow  # Nothing to retry

        workflow.add_audit(AuditEventType.STAGE_RETRIED, stage=stage)
        self._run_stage(workflow, stage, force=True)
        self._finalize_status(workflow)
        return workflow

    def cancel_workflow(self, workflow: ManufacturingWorkflow) -> ManufacturingWorkflow:
        """Cancel the workflow cleanly."""
        workflow.status = WorkflowStatus.CANCELLED
        workflow.add_audit(AuditEventType.WORKFLOW_CANCELLED)
        return workflow

    def invalidate_stages(
        self, workflow: ManufacturingWorkflow, change_key: str
    ) -> ManufacturingWorkflow:
        """Reset stages that are invalidated by a named input change."""
        to_invalidate = invalidated_by(change_key)
        for stage in to_invalidate:
            if stage in workflow.stage_results:
                del workflow.stage_results[stage]
        return workflow

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _run_stage(
        self, workflow: ManufacturingWorkflow, stage: WorkflowStage, force: bool
    ) -> None:
        req = required_stages(workflow.requested_mode)

        if stage not in req:
            # Mark skipped if not already
            if stage not in workflow.stage_results:
                result = StageResult(
                    stage=stage,
                    status=StageStatus.SKIPPED_NOT_REQUESTED,
                    input_refs={"workflow_id": workflow.workflow_id},
                )
                result.finish()
                workflow.record_stage(result)
            return

        # Check dependency graph
        stage_statuses = {s: str(r.status) for s, r in workflow.stage_results.items()}
        ok, reasons = dependencies_satisfied(stage, stage_statuses)

        if not ok:
            result = StageResult(
                stage=stage,
                status=StageStatus.BLOCKED,
                blocking_reasons=reasons,
                input_refs={"workflow_id": workflow.workflow_id},
            )
            result.finish()
            workflow.record_stage(result)
            workflow.add_audit(AuditEventType.STAGE_BLOCKED, stage=stage, detail="; ".join(reasons))
            return

        # Stamp input hash for stale detection
        input_hash = workflow.context.input_hash([
            "source_file_ref", "material_ref", "stock_ref",
            "process_ref", "features_ref", "cutting_data_ref",
        ])

        workflow.current_stage = stage
        workflow.add_audit(AuditEventType.STAGE_STARTED, stage=stage)

        runner_cls = RUNNERS.get(stage)
        if runner_cls is None:
            result = StageResult(
                stage=stage,
                status=StageStatus.FAILED,
                errors=[f"No runner registered for stage {stage}"],
                input_refs={"workflow_id": workflow.workflow_id},
            )
            result.finish()
            workflow.record_stage(result)
            return

        runner = runner_cls()
        result = runner.run(workflow.context)
        result.stage = stage  # RC1-DEF-001: ensure result is stored under the correct stage key
        result.input_hash = input_hash

        # Pick up final plan from plan runner if present
        if stage == WorkflowStage.FINAL_MANUFACTURING_PLAN:
            plan_obj = result.output_refs.pop("_plan_object", None)
            if plan_obj is not None:
                workflow.final_plan = plan_obj
                workflow.final_plan_ref = plan_obj.plan_id

        workflow.record_stage(result)
        self._emit_stage_audit(workflow, result)

    def _emit_stage_audit(
        self, workflow: ManufacturingWorkflow, result: StageResult
    ) -> None:
        mapping = {
            StageStatus.PASS: AuditEventType.STAGE_PASSED,
            StageStatus.PARTIAL: AuditEventType.STAGE_PARTIAL,
            StageStatus.BLOCKED: AuditEventType.STAGE_BLOCKED,
            StageStatus.FAILED: AuditEventType.STAGE_FAILED,
            StageStatus.REVIEW_REQUIRED: AuditEventType.REVIEW_REQUIRED,
        }
        event = mapping.get(result.status)
        if event:
            detail = "; ".join(result.errors or result.blocking_reasons or result.warnings or [])
            workflow.add_audit(event, stage=result.stage, detail=detail[:500])

    def _finalize_status(self, workflow: ManufacturingWorkflow) -> None:
        if workflow.status == WorkflowStatus.CANCELLED:
            return

        req = required_stages(workflow.requested_mode)
        statuses = [
            workflow.stage_results[s].status
            for s in req
            if s in workflow.stage_results
        ]

        if not statuses:
            workflow.status = WorkflowStatus.FAILED
        elif all(s == StageStatus.PASS for s in statuses):
            workflow.status = WorkflowStatus.COMPLETED
            workflow.add_audit(AuditEventType.WORKFLOW_COMPLETED)
        elif any(s == StageStatus.FAILED for s in statuses):
            workflow.status = WorkflowStatus.FAILED
        elif any(s in (StageStatus.BLOCKED, StageStatus.PARTIAL) for s in statuses):
            workflow.status = WorkflowStatus.PARTIAL
        else:
            workflow.status = WorkflowStatus.COMPLETED
            workflow.add_audit(AuditEventType.WORKFLOW_COMPLETED)
