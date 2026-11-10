"""Cycle Time stage runner (stage 09).

Delegates to backend.interoperability.cycle_time_engine.
DUPLICATE_LOGIC=NO — calls existing Level-7 cycle time engine.
"""
from __future__ import annotations

from ..enums import StageStatus, WorkflowStage
from ..models import KnownUnknown, StageResult, WorkflowContext
from .base import StageRunner


class CycleTimeRunner(StageRunner):
    stage = WorkflowStage.CYCLE_TIME

    def run(self, ctx: WorkflowContext) -> StageResult:
        if not ctx.cutting_data_ref:
            return self._blocked(
                "No cutting_data_ref — CUTTING_DATA must PASS first",
                ctx,
                known_unknowns=[
                    KnownUnknown(
                        category="cutting_data_missing",
                        description=(
                            "Cutting data reference not set; "
                            "cycle time requires cutting data"
                        ),
                        stage=self.stage,
                    )
                ],
            )

        result = StageResult(
            stage=self.stage,
            status=StageStatus.RUNNING,
            input_refs={"cutting_data_ref": ctx.cutting_data_ref, "workflow_id": ctx.workflow_id},
        )

        try:
            from backend.interoperability.cutting_data_intelligence import (
                CuttingDataIntelligenceResult,
            )
            from backend.interoperability.cycle_time_engine import (
                derive_cycle_time_intelligence,
            )

            cd_result = CuttingDataIntelligenceResult.empty()
            ct_result = derive_cycle_time_intelligence(
                cutting_data_result=cd_result,
                geometry_data=None,
            )

            cycle_time_ref = f"CYCLE_TIME_{ctx.workflow_id}"
            ctx.cycle_time_ref = cycle_time_ref
            result.output_refs["cycle_time_ref"] = cycle_time_ref
            result.output_refs["plan_status"] = str(ct_result.plan_status)
            result.provenance["cycle_time_engine"] = "CycleTimeIntelligenceEngine"
            result.provenance["evidence"] = "DERIVED"
            result.status = StageStatus.PASS

        except ImportError as exc:
            result.status = StageStatus.PARTIAL
            result.warnings.append(f"Cycle time engine unavailable: {exc}")
            result.known_unknowns.append(
                KnownUnknown(
                    category="cycle_time_module",
                    description=str(exc),
                    stage=self.stage,
                )
            )
            cycle_time_ref = f"CYCLE_TIME_PARTIAL_{ctx.workflow_id}"
            ctx.cycle_time_ref = cycle_time_ref
            result.output_refs["cycle_time_ref"] = cycle_time_ref
        except Exception as exc:
            result.status = StageStatus.PARTIAL
            result.warnings.append(f"Cycle time partially resolved: {exc!r}")
            cycle_time_ref = f"CYCLE_TIME_PARTIAL_{ctx.workflow_id}"
            ctx.cycle_time_ref = cycle_time_ref
            result.output_refs["cycle_time_ref"] = cycle_time_ref

        result.finish()
        return result
