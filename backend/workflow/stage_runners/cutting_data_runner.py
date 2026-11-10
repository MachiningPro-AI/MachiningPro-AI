"""Cutting Data stage runner (stage 08).

Delegates to backend.interoperability.cutting_data_engine.
DUPLICATE_LOGIC=NO — calls existing Level-6 cutting data engine.
"""
from __future__ import annotations

from ..enums import StageStatus, WorkflowStage
from ..models import KnownUnknown, StageResult, WorkflowContext
from .base import StageRunner


class CuttingDataRunner(StageRunner):
    stage = WorkflowStage.CUTTING_DATA

    def run(self, ctx: WorkflowContext) -> StageResult:
        missing: list[str] = []
        unknowns: list[KnownUnknown] = []

        if not ctx.tool_candidates_ref:
            missing.append("tool_candidates_ref")
            unknowns.append(
                KnownUnknown(
                    category="tool_availability",
                    description="Tool candidates not available; tool selection must complete first",
                    stage=self.stage,
                )
            )
        if not ctx.material_ref:
            missing.append("material_ref")
            unknowns.append(
                KnownUnknown(
                    category="material_unknown",
                    description=(
                        "Material reference is missing; "
                        "cutting data requires material identity"
                    ),
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
                "tool_candidates_ref": ctx.tool_candidates_ref,
                "material_ref": ctx.material_ref,
                "workflow_id": ctx.workflow_id,
            },
        )

        try:
            from backend.interoperability.cutting_data_engine import (
                derive_cutting_data_intelligence,
            )
            from backend.interoperability.cutting_data_intelligence import OperationContext
            from backend.interoperability.machine_tool_intelligence import (
                MachineToolIntelligenceResult,
            )

            # Create a minimal MachineToolIntelligenceResult stub for the engine
            mt_result = MachineToolIntelligenceResult.empty()
            cd_result = derive_cutting_data_intelligence(
                machine_tool_result=mt_result,
                operation_context=OperationContext(
                    operation_type="MILLING",
                    material_name=ctx.material_ref,
                ),
            )

            cutting_data_ref = f"CUTTING_DATA_{ctx.workflow_id}"
            ctx.cutting_data_ref = cutting_data_ref
            result.output_refs["cutting_data_ref"] = cutting_data_ref
            result.output_refs["plan_status"] = str(cd_result.plan_status)
            result.provenance["cutting_data_engine"] = "CuttingDataIntelligenceEngine"
            result.provenance["evidence"] = "DERIVED"
            result.status = StageStatus.PASS

        except ImportError as exc:
            result.status = StageStatus.PARTIAL
            result.warnings.append(f"Cutting data engine unavailable: {exc}")
            result.known_unknowns.append(
                KnownUnknown(
                    category="cutting_data_module",
                    description=str(exc),
                    stage=self.stage,
                )
            )
            cutting_data_ref = f"CUTTING_DATA_PARTIAL_{ctx.workflow_id}"
            ctx.cutting_data_ref = cutting_data_ref
            result.output_refs["cutting_data_ref"] = cutting_data_ref
        except Exception as exc:
            result.status = StageStatus.PARTIAL
            result.warnings.append(f"Cutting data partially resolved: {exc!r}")
            cutting_data_ref = f"CUTTING_DATA_PARTIAL_{ctx.workflow_id}"
            ctx.cutting_data_ref = cutting_data_ref
            result.output_refs["cutting_data_ref"] = cutting_data_ref

        result.finish()
        return result
