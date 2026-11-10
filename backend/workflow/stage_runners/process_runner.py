"""Process Planning stage runner (stage 05).

Delegates to backend.process_planning.
DUPLICATE_LOGIC=NO — calls existing Level-5 process planning foundation.
"""
from __future__ import annotations

from ..enums import StageStatus, WorkflowStage
from ..models import KnownUnknown, StageResult, WorkflowContext
from .base import StageRunner


class ProcessPlanningRunner(StageRunner):
    stage = WorkflowStage.PROCESS_PLANNING

    def run(self, ctx: WorkflowContext) -> StageResult:
        if not ctx.features_ref:
            return self._blocked(
                "No features_ref — FEATURE_RECOGNITION must PASS first",
                ctx,
                known_unknowns=[
                    KnownUnknown(
                        category="features_missing",
                        description=(
                            "Feature reference not set; "
                            "cannot plan process without features"
                        ),
                        stage=self.stage,
                    )
                ],
            )

        result = StageResult(
            stage=self.stage,
            status=StageStatus.RUNNING,
            input_refs={"features_ref": ctx.features_ref, "workflow_id": ctx.workflow_id},
        )

        try:
            from backend.process_planning import ProcessPlanBuilder

            builder = ProcessPlanBuilder()
            plan = builder.build()
            process_ref = f"PROCESS_{ctx.workflow_id}"
            ctx.process_ref = process_ref
            result.output_refs["process_ref"] = process_ref
            result.output_refs["plan_status"] = str(plan.status)
            result.provenance["plan_status"] = str(plan.status)
            result.provenance["evidence"] = "DERIVED"
            result.review_required = True
            result.status = StageStatus.PASS
        except ImportError as exc:
            result.status = StageStatus.PARTIAL
            result.warnings.append(f"Process planning module unavailable: {exc}")
            result.known_unknowns.append(
                KnownUnknown(
                    category="process_planning_module",
                    description=str(exc),
                    stage=self.stage,
                )
            )
            process_ref = f"PROCESS_PARTIAL_{ctx.workflow_id}"
            ctx.process_ref = process_ref
            result.output_refs["process_ref"] = process_ref
        except Exception as exc:
            result.status = StageStatus.PARTIAL
            result.warnings.append(f"Process planning returned partial result: {exc!r}")
            process_ref = f"PROCESS_PARTIAL_{ctx.workflow_id}"
            ctx.process_ref = process_ref
            result.output_refs["process_ref"] = process_ref

        result.finish()
        return result
