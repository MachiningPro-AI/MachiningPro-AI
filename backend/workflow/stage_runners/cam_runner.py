"""CAM Planning stage runner (stage 11).

Delegates to backend.cam_planning.cam_engine.
DUPLICATE_LOGIC=NO — calls existing Level-9 CAM engine.
"""
from __future__ import annotations

from ..enums import StageStatus, WorkflowStage
from ..models import KnownUnknown, StageResult, WorkflowContext
from .base import StageRunner


class CamPlanningRunner(StageRunner):
    stage = WorkflowStage.CAM_PLANNING

    def run(self, ctx: WorkflowContext) -> StageResult:
        missing: list[str] = []
        unknowns: list[KnownUnknown] = []

        if not ctx.process_ref:
            missing.append("process_ref")
            unknowns.append(
                KnownUnknown(
                    category="process_missing",
                    description="Process plan reference not set",
                    stage=self.stage,
                )
            )
        if not ctx.tool_candidates_ref:
            missing.append("tool_candidates_ref")
            unknowns.append(
                KnownUnknown(
                    category="tool_availability",
                    description="Tool candidates reference not set",
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
                "process_ref": ctx.process_ref,
                "tool_candidates_ref": ctx.tool_candidates_ref,
                "workflow_id": ctx.workflow_id,
            },
        )

        try:
            from backend.cam_planning.cam_engine import CAMEngine
            from backend.cam_planning.models import CAMJobInput

            engine = CAMEngine()
            # Minimal job input using available context
            job_input = CAMJobInput(
                part_reference=ctx.part_reference,
                material_ref=ctx.material_ref,
                stock_ref=ctx.stock_ref,
                process_ref=ctx.process_ref,
            )
            cam_job = engine.plan(job_input)

            cam_ref = f"CAM_{ctx.workflow_id}"
            ctx.cam_ref = cam_ref
            result.output_refs["cam_ref"] = cam_ref
            result.output_refs["job_status"] = str(cam_job.status)
            result.output_refs["simulation_required"] = cam_job.simulation_required
            result.provenance["cam_engine"] = "CAMEngine"
            result.provenance["evidence"] = "DERIVED"
            result.review_required = True
            result.status = StageStatus.PASS

        except ImportError as exc:
            result.status = StageStatus.PARTIAL
            result.warnings.append(f"CAM engine unavailable: {exc}")
            result.known_unknowns.append(
                KnownUnknown(
                    category="cam_module",
                    description=str(exc),
                    stage=self.stage,
                )
            )
            cam_ref = f"CAM_PARTIAL_{ctx.workflow_id}"
            ctx.cam_ref = cam_ref
            result.output_refs["cam_ref"] = cam_ref
            result.review_required = True
        except Exception as exc:
            result.status = StageStatus.PARTIAL
            result.warnings.append(f"CAM planning partially resolved: {exc!r}")
            cam_ref = f"CAM_PARTIAL_{ctx.workflow_id}"
            ctx.cam_ref = cam_ref
            result.output_refs["cam_ref"] = cam_ref
            result.review_required = True

        result.finish()
        return result
