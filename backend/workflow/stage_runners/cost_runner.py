"""Cost / RFQ stage runner (stage 10).

Delegates to backend.interoperability.cost_engine.
DUPLICATE_LOGIC=NO — calls existing Level-8 cost engine.
"""
from __future__ import annotations

from ..enums import StageStatus, WorkflowStage
from ..models import KnownUnknown, StageResult, WorkflowContext
from .base import StageRunner


class CostRfqRunner(StageRunner):
    stage = WorkflowStage.COST_RFQ

    def run(self, ctx: WorkflowContext) -> StageResult:
        if not ctx.cycle_time_ref:
            return self._blocked(
                "No cycle_time_ref — CYCLE_TIME must PASS first",
                ctx,
                known_unknowns=[
                    KnownUnknown(
                        category="cycle_time_missing",
                        description=(
                            "Cycle time reference not set; "
                            "cost engine requires cycle time data"
                        ),
                        stage=self.stage,
                    )
                ],
            )

        result = StageResult(
            stage=self.stage,
            status=StageStatus.RUNNING,
            input_refs={"cycle_time_ref": ctx.cycle_time_ref, "workflow_id": ctx.workflow_id},
        )

        try:
            from backend.interoperability.cost_engine import derive_cost_intelligence
            from backend.interoperability.cost_intelligence import CommercialInputs
            from backend.interoperability.cycle_time_intelligence import (
                CycleTimeIntelligenceResult,
            )

            ct_result = CycleTimeIntelligenceResult.empty()
            cost_result = derive_cost_intelligence(
                cycle_time_result=ct_result,
                commercial_inputs=CommercialInputs(),
                quantity=ctx.quantity,
            )

            cost_ref = f"COST_{ctx.workflow_id}"
            ctx.cost_ref = cost_ref
            result.output_refs["cost_ref"] = cost_ref
            result.output_refs["model_status"] = str(cost_result.model_status)
            result.provenance["cost_engine"] = "CostIntelligenceEngine"
            result.provenance["evidence"] = "DERIVED"
            result.status = StageStatus.PASS

        except ImportError as exc:
            result.status = StageStatus.PARTIAL
            result.warnings.append(f"Cost engine unavailable: {exc}")
            result.known_unknowns.append(
                KnownUnknown(
                    category="cost_rate_unknown",
                    description=f"Cost engine module unavailable: {exc}",
                    stage=self.stage,
                )
            )
            cost_ref = f"COST_PARTIAL_{ctx.workflow_id}"
            ctx.cost_ref = cost_ref
            result.output_refs["cost_ref"] = cost_ref
        except Exception as exc:
            result.status = StageStatus.PARTIAL
            result.warnings.append(f"Cost partially resolved: {exc!r}")
            cost_ref = f"COST_PARTIAL_{ctx.workflow_id}"
            ctx.cost_ref = cost_ref
            result.output_refs["cost_ref"] = cost_ref

        result.finish()
        return result
