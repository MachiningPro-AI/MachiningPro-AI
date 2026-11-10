"""Digital Twin stage runner (stage 18).

Delegates to backend.digital_twin.
DUPLICATE_LOGIC=NO — calls existing Level-18 digital twin module.
NO_CNC_WRITE=YES — no machine writes, scenarios only.
"""
from __future__ import annotations

from ..enums import StageStatus, WorkflowStage
from ..models import KnownUnknown, StageResult, WorkflowContext
from .base import StageRunner


class DigitalTwinRunner(StageRunner):
    stage = WorkflowStage.DIGITAL_TWIN

    def run(self, ctx: WorkflowContext) -> StageResult:
        missing: list[str] = []
        unknowns: list[KnownUnknown] = []

        if not ctx.machine_candidates_ref:
            missing.append("machine_candidates_ref")
            unknowns.append(
                KnownUnknown(
                    category="machine_availability_unknown",
                    description="Machine candidates reference not set",
                    stage=self.stage,
                )
            )
        if not ctx.cutting_data_ref:
            missing.append("cutting_data_ref")
            unknowns.append(
                KnownUnknown(
                    category="cutting_data_missing",
                    description=(
                        "Cutting data reference not set; "
                        "digital twin requires cutting data"
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
                "machine_candidates_ref": ctx.machine_candidates_ref,
                "cutting_data_ref": ctx.cutting_data_ref,
                "workflow_id": ctx.workflow_id,
            },
        )

        try:
            from backend.digital_twin import (
                HUMAN_REVIEW_MANDATORY,
                NO_AUTOMATIC_DISPATCH,
                NO_CNC_WRITE,
                SCENARIO_IS_NOT_PRODUCTION_PLAN,
            )
            from backend.digital_twin.generator import generate_machine_alternatives
            from backend.digital_twin.models import ManufacturingTwinScenario

            # Verify safety constants
            assert NO_CNC_WRITE, "SAFETY: NO_CNC_WRITE must be True"
            assert NO_AUTOMATIC_DISPATCH, "SAFETY: NO_AUTOMATIC_DISPATCH must be True"
            assert SCENARIO_IS_NOT_PRODUCTION_PLAN, (
                "SAFETY: SCENARIO_IS_NOT_PRODUCTION_PLAN must be True"
            )
            assert HUMAN_REVIEW_MANDATORY, "SAFETY: HUMAN_REVIEW_MANDATORY must be True"

            # Create a baseline scenario from available context
            baseline = ManufacturingTwinScenario.create_baseline(
                machine_ref=ctx.selected_machine_id or ctx.machine_candidates_ref,
                cutting_data_ref=ctx.cutting_data_ref,
                workflow_id=ctx.workflow_id,
            )
            scenarios = generate_machine_alternatives(
                baseline=baseline,
                machine_refs=[ctx.selected_machine_id] if ctx.selected_machine_id else [],
            )

            twin_refs = [f"TWIN_{ctx.workflow_id}_{i}" for i, _ in enumerate(scenarios)]
            ctx.digital_twin_refs = twin_refs
            result.output_refs["digital_twin_refs"] = twin_refs
            result.output_refs["scenario_count"] = len(twin_refs)
            result.output_refs["is_production_plan"] = False
            result.output_refs["cnc_write"] = False
            result.provenance["digital_twin"] = "ManufacturingTwinGenerator"
            result.provenance["no_cnc_write"] = True
            result.provenance["evidence"] = "PREDICTED"
            result.review_required = True
            result.status = StageStatus.PASS

        except ImportError as exc:
            result.status = StageStatus.PARTIAL
            result.warnings.append(f"Digital twin module unavailable: {exc}")
            result.known_unknowns.append(
                KnownUnknown(
                    category="digital_twin_module",
                    description=str(exc),
                    stage=self.stage,
                )
            )
            twin_ref = f"TWIN_PARTIAL_{ctx.workflow_id}"
            ctx.digital_twin_refs = [twin_ref]
            result.output_refs["digital_twin_refs"] = ctx.digital_twin_refs
            result.output_refs["cnc_write"] = False
            result.review_required = True
        except Exception as exc:
            result.status = StageStatus.PARTIAL
            result.warnings.append(f"Digital twin partially generated: {exc!r}")
            twin_ref = f"TWIN_PARTIAL_{ctx.workflow_id}"
            ctx.digital_twin_refs = [twin_ref]
            result.output_refs["digital_twin_refs"] = ctx.digital_twin_refs
            result.output_refs["cnc_write"] = False
            result.review_required = True

        result.finish()
        return result
