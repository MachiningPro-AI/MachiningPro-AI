"""Tool Selection stage runner (stage 07).

Uses ToolPipelineAdapter (MC-3).
DUPLICATE_LOGIC=NO — delegates to existing Level-5 tool selection engine.
"""
from __future__ import annotations

from ..enums import StageStatus, WorkflowStage
from ..models import KnownUnknown, StageResult, WorkflowContext
from .base import StageRunner


class ToolSelectionRunner(StageRunner):
    stage = WorkflowStage.TOOL_SELECTION

    def run(self, ctx: WorkflowContext) -> StageResult:
        if not ctx.process_ref:
            return self._blocked(
                "No process_ref — PROCESS_PLANNING must PASS first",
                ctx,
                known_unknowns=[
                    KnownUnknown(
                        category="process_missing",
                        description=(
                            "Process plan reference not set; "
                            "cannot select tools without process requirements"
                        ),
                        stage=self.stage,
                    )
                ],
            )

        result = StageResult(
            stage=self.stage,
            status=StageStatus.RUNNING,
            input_refs={"process_ref": ctx.process_ref, "workflow_id": ctx.workflow_id},
        )

        try:
            from backend.integration.tool_adapter import (
                ToolPipelineAdapter,
                ToolPipelineRequest,
            )

            adapter = ToolPipelineAdapter()
            # Build a minimal request using available context
            request = ToolPipelineRequest(
                operation="MILLING",
                iso_material_group=ctx.material_iso_group,
                spindle_interface=None,
            )
            tool_result = adapter.select(request)

            tool_candidates_ref = f"TOOLS_{ctx.workflow_id}"
            ctx.tool_candidates_ref = tool_candidates_ref
            if tool_result.recommended:
                ctx.selected_tool_ids = [t.stable_id for t in tool_result.recommended[:3]]
            else:
                ctx.selected_tool_ids = []

            result.output_refs["tool_candidates_ref"] = tool_candidates_ref
            result.output_refs["recommended_count"] = len(tool_result.recommended)
            result.output_refs["pass_count"] = len(tool_result.pass_candidates)
            result.provenance["tool_provider"] = "ToolPipelineAdapter"
            result.provenance["evidence"] = "CONFIRMED"
            result.status = StageStatus.PASS

            if not tool_result.recommended:
                result.status = StageStatus.PARTIAL
                result.warnings.append("No recommended tools found — tool selection is PARTIAL")
                result.known_unknowns.append(
                    KnownUnknown(
                        category="tool_availability",
                        description="No tools matched the selection criteria",
                        stage=self.stage,
                    )
                )

        except ImportError as exc:
            result.status = StageStatus.PARTIAL
            result.warnings.append(f"Tool library adapter unavailable: {exc}")
            result.known_unknowns.append(
                KnownUnknown(
                    category="tool_library_module",
                    description=str(exc),
                    stage=self.stage,
                )
            )
            tool_candidates_ref = f"TOOLS_PARTIAL_{ctx.workflow_id}"
            ctx.tool_candidates_ref = tool_candidates_ref
            result.output_refs["tool_candidates_ref"] = tool_candidates_ref
        except Exception as exc:
            result.status = StageStatus.FAILED
            result.errors.append(f"Tool selection error: {exc!r}")

        result.finish()
        return result
