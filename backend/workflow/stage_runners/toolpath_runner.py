"""Toolpath stage runner (stage 12).

Delegates to backend.toolpath.
DUPLICATE_LOGIC=NO — calls existing Level-10 toolpath foundation.
NO_GCODE=YES, NO_NC_CODE=YES — preserved from toolpath module.
"""
from __future__ import annotations

from ..enums import StageStatus, WorkflowStage
from ..models import KnownUnknown, StageResult, WorkflowContext
from .base import StageRunner


class ToolpathRunner(StageRunner):
    stage = WorkflowStage.TOOLPATH

    def run(self, ctx: WorkflowContext) -> StageResult:
        if not ctx.cam_ref:
            return self._blocked(
                "No cam_ref — CAM_PLANNING must PASS first",
                ctx,
                known_unknowns=[
                    KnownUnknown(
                        category="cam_missing",
                        description=(
                            "CAM plan reference not set; "
                            "toolpath requires CAM planning output"
                        ),
                        stage=self.stage,
                    )
                ],
            )

        result = StageResult(
            stage=self.stage,
            status=StageStatus.RUNNING,
            input_refs={"cam_ref": ctx.cam_ref, "workflow_id": ctx.workflow_id},
        )

        try:
            from backend.toolpath import ToolpathGeneratorRegistry
            from backend.toolpath.models import ToolpathGenerationRequest

            registry = ToolpathGeneratorRegistry()
            request = ToolpathGenerationRequest(
                cam_ref=ctx.cam_ref,
                operation_type="MILLING",
            )
            tp_result = registry.generate(request)

            toolpath_ref = f"TOOLPATH_{ctx.workflow_id}"
            ctx.toolpath_refs = [toolpath_ref]
            result.output_refs["toolpath_refs"] = ctx.toolpath_refs
            result.output_refs["toolpath_status"] = str(tp_result.status)
            result.provenance["toolpath_generator"] = "ToolpathGeneratorRegistry"
            result.provenance["no_gcode"] = True
            result.provenance["evidence"] = "DERIVED"
            result.review_required = True
            result.status = StageStatus.PASS

        except ImportError as exc:
            result.status = StageStatus.PARTIAL
            result.warnings.append(f"Toolpath module unavailable: {exc}")
            result.known_unknowns.append(
                KnownUnknown(
                    category="toolpath_module",
                    description=str(exc),
                    stage=self.stage,
                )
            )
            toolpath_ref = f"TOOLPATH_PARTIAL_{ctx.workflow_id}"
            ctx.toolpath_refs = [toolpath_ref]
            result.output_refs["toolpath_refs"] = ctx.toolpath_refs
            result.review_required = True
        except Exception as exc:
            result.status = StageStatus.PARTIAL
            result.warnings.append(f"Toolpath partially generated: {exc!r}")
            toolpath_ref = f"TOOLPATH_PARTIAL_{ctx.workflow_id}"
            ctx.toolpath_refs = [toolpath_ref]
            result.output_refs["toolpath_refs"] = ctx.toolpath_refs
            result.review_required = True

        result.finish()
        return result
