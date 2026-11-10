"""Job Assignment stage runner (stage 16).

Delegates to backend.job_planning.
DUPLICATE_LOGIC=NO — calls existing Level-17 job planning module.
ASSIGNMENT_IS_PROPOSED_ONLY=YES — no automatic machine assignment.
"""
from __future__ import annotations

from ..enums import StageStatus, WorkflowStage
from ..models import KnownUnknown, StageResult, WorkflowContext
from .base import StageRunner


class JobAssignmentRunner(StageRunner):
    stage = WorkflowStage.JOB_ASSIGNMENT

    def run(self, ctx: WorkflowContext) -> StageResult:
        missing: list[str] = []
        unknowns: list[KnownUnknown] = []

        if not ctx.schedule_ref:
            missing.append("schedule_ref")
            unknowns.append(
                KnownUnknown(
                    category="schedule_missing",
                    description="Schedule reference not set",
                    stage=self.stage,
                )
            )
        if not ctx.machine_candidates_ref:
            missing.append("machine_candidates_ref")
            unknowns.append(
                KnownUnknown(
                    category="machine_availability_unknown",
                    description="Machine candidates reference not set",
                    stage=self.stage,
                )
            )

        if missing:
            return self._blocked(
                f"Missing required inputs: {', '.join(missing)}",
                ctx,
                known_unknowns=unknowns,
            )

        result = StageResult(
            stage=self.stage,
            status=StageStatus.RUNNING,
            input_refs={
                "schedule_ref": ctx.schedule_ref,
                "machine_candidates_ref": ctx.machine_candidates_ref,
                "workflow_id": ctx.workflow_id,
            },
        )

        try:
            from backend.job_planning import plan_job_assignment
            from backend.job_planning.models import JobAssignmentRequest

            request = JobAssignmentRequest(
                job_id=f"JOB_{ctx.workflow_id}",
                part_reference=ctx.part_reference,
                machine_candidates_ref=ctx.machine_candidates_ref,
                schedule_ref=ctx.schedule_ref,
                quantity=ctx.quantity,
            )
            assignment = plan_job_assignment(request)

            job_assignment_ref = f"JOB_ASSIGN_{ctx.workflow_id}"
            ctx.job_assignment_ref = job_assignment_ref
            result.output_refs["job_assignment_ref"] = job_assignment_ref
            result.output_refs["assignment_status"] = str(assignment.status)
            result.output_refs["proposal_only"] = True
            result.provenance["job_planner"] = "plan_job_assignment"
            result.provenance["no_auto_dispatch"] = True
            result.provenance["evidence"] = "PROPOSED"
            result.review_required = True
            result.status = StageStatus.PASS

        except ImportError as exc:
            result.status = StageStatus.PARTIAL
            result.warnings.append(f"Job planning module unavailable: {exc}")
            result.known_unknowns.append(
                KnownUnknown(
                    category="job_planning_module",
                    description=str(exc),
                    stage=self.stage,
                )
            )
            job_assignment_ref = f"JOB_ASSIGN_PARTIAL_{ctx.workflow_id}"
            ctx.job_assignment_ref = job_assignment_ref
            result.output_refs["job_assignment_ref"] = job_assignment_ref
            result.review_required = True
        except Exception as exc:
            result.status = StageStatus.PARTIAL
            result.warnings.append(f"Job assignment partially completed: {exc!r}")
            job_assignment_ref = f"JOB_ASSIGN_PARTIAL_{ctx.workflow_id}"
            ctx.job_assignment_ref = job_assignment_ref
            result.output_refs["job_assignment_ref"] = job_assignment_ref
            result.review_required = True

        result.finish()
        return result
