"""Final Manufacturing Plan stage runner (stage 19).

Aggregates all available stage results into ManufacturingPlanSummary.
DUPLICATE_LOGIC=NO — only aggregates; does not re-run any stage logic.
EVIDENCE_LABELS=YES — every value is classified per stage completeness.
"""
from __future__ import annotations

import hashlib

from ..enums import (
    AlternativePlanType,
    EvidenceLabel,
    StageStatus,
    WorkflowObjective,
    WorkflowStage,
)
from ..models import (
    AlternativePlan,
    EvidenceValue,
    KnownUnknown,
    ManufacturingPlanSummary,
    StageResult,
    WorkflowContext,
)
from .base import StageRunner


def _status_to_evidence(status: StageStatus) -> EvidenceLabel:
    if status == StageStatus.PASS:
        return EvidenceLabel.CONFIRMED
    if status == StageStatus.PARTIAL:
        return EvidenceLabel.DERIVED
    return EvidenceLabel.UNKNOWN


class FinalPlanRunner(StageRunner):
    stage = WorkflowStage.FINAL_MANUFACTURING_PLAN

    def run(self, ctx: WorkflowContext) -> StageResult:
        if not ctx.process_ref:
            return self._blocked(
                "No process_ref — minimum PROCESS_PLANNING must PASS for a plan to be generated",
                ctx,
                known_unknowns=[
                    KnownUnknown(
                        category="process_missing",
                        description="Cannot generate manufacturing plan without process plan",
                        stage=self.stage,
                    )
                ],
            )

        result = StageResult(
            stage=self.stage,
            status=StageStatus.RUNNING,
            input_refs={"workflow_id": ctx.workflow_id},
        )

        # We need access to the workflow's stage results, stored externally.
        # The plan runner works from context refs only (stage results are on the workflow).
        # Build the plan from available ctx refs — evidence labels reflect what's known.

        try:
            plan_id = hashlib.sha256(ctx.workflow_id.encode()).hexdigest()[:16]

            def _ev(value, ref: str | None, source: str = "") -> EvidenceValue:
                label = EvidenceLabel.CONFIRMED if ref else EvidenceLabel.UNKNOWN
                return EvidenceValue(value=value, label=label, source=source)

            plan = ManufacturingPlanSummary(
                plan_id=plan_id,
                workflow_id=ctx.workflow_id,
                part=EvidenceValue(ctx.part_reference, EvidenceLabel.CONFIRMED, "workflow_input"),
                revision=EvidenceValue(ctx.revision, EvidenceLabel.CONFIRMED, "workflow_input"),
                material=EvidenceValue(
                    ctx.material_ref,
                    EvidenceLabel.CONFIRMED if ctx.material_ref else EvidenceLabel.UNKNOWN,
                    "material_library",
                ),
                quantity=EvidenceValue(ctx.quantity, EvidenceLabel.CONFIRMED, "workflow_input"),
                features=[_ev(ctx.features_ref, ctx.features_ref, "feature_recognition")],
                dfm_summary=_ev(ctx.dfm_ref, ctx.dfm_ref, "dfm_engine"),
                process_route=[_ev(ctx.process_ref, ctx.process_ref, "process_planning")],
                machine_candidates=[
                    _ev(ctx.machine_candidates_ref, ctx.machine_candidates_ref, "machine_library")
                ],
                recommended_machine=_ev(
                    ctx.selected_machine_id,
                    ctx.selected_machine_id,
                    "machine_selection",
                ),
                tool_plan=[_ev(ctx.tool_candidates_ref, ctx.tool_candidates_ref, "tool_library")],
                cutting_data=[
                    _ev(ctx.cutting_data_ref, ctx.cutting_data_ref, "cutting_data_engine")
                ],
                cycle_time=_ev(ctx.cycle_time_ref, ctx.cycle_time_ref, "cycle_time_engine"),
                cost_rfq=_ev(ctx.cost_ref, ctx.cost_ref, "cost_engine"),
                cam_operations=[_ev(ctx.cam_ref, ctx.cam_ref, "cam_engine")],
                toolpath_status=_ev(
                    ctx.toolpath_refs or None, ctx.toolpath_refs or None, "toolpath"
                ),
                verification_status=_ev(ctx.verification_ref, ctx.verification_ref, "verification"),
                nc_status=_ev(ctx.nc_ref, ctx.nc_ref, "nc_generator"),
                scheduling=_ev(ctx.schedule_ref, ctx.schedule_ref, "scheduler"),
                job_assignment=_ev(ctx.job_assignment_ref, ctx.job_assignment_ref, "job_planning"),
                adaptive_recommendations=[
                    _ev(ctx.adaptive_ref, ctx.adaptive_ref, "adaptive_intelligence")
                ],
                digital_twin_scenarios=[
                    _ev(ref, ref, "digital_twin") for ref in ctx.digital_twin_refs
                ],
            )

            # Build alternative plans based on objective
            alternatives = _build_alternatives(ctx)
            plan.alternative_plans = alternatives

            result.output_refs["plan_id"] = plan_id
            result.output_refs["complete"] = True
            result.output_refs["production_approved"] = False
            result.output_refs["dispatched"] = False
            result.output_refs["machine_started"] = False
            result.provenance["aggregator"] = "FinalPlanRunner"
            result.provenance["evidence"] = "DERIVED"
            result.review_required = True

            # Store plan on result for engine to pick up
            result.output_refs["_plan_object"] = plan

            result.status = StageStatus.PASS

        except Exception as exc:
            result.status = StageStatus.FAILED
            result.errors.append(f"Final plan aggregation error: {exc!r}")

        result.finish()
        return result


def _build_alternatives(ctx: WorkflowContext) -> list[AlternativePlan]:
    alternatives: list[AlternativePlan] = []

    # Always generate one based on the user objective
    if ctx.objective == WorkflowObjective.MINIMUM_CYCLE_TIME:
        alternatives.append(
            AlternativePlan(
                plan_type=AlternativePlanType.FASTEST_VALID,
                description="Minimum cycle time plan based on selected machine and cutting data",
                machine_id=ctx.selected_machine_id,
                tool_ids=ctx.selected_tool_ids,
                evidence=EvidenceLabel.PROPOSED,
            )
        )
    elif ctx.objective == WorkflowObjective.MINIMUM_COST:
        alternatives.append(
            AlternativePlan(
                plan_type=AlternativePlanType.LOWEST_KNOWN_COST,
                description="Minimum cost plan based on cost RFQ analysis",
                machine_id=ctx.selected_machine_id,
                tool_ids=ctx.selected_tool_ids,
                evidence=EvidenceLabel.PROPOSED,
            )
        )
    elif ctx.objective == WorkflowObjective.MAXIMUM_TOOL_LIFE:
        alternatives.append(
            AlternativePlan(
                plan_type=AlternativePlanType.BEST_TOOL_LIFE_EVIDENCE,
                description="Maximum tool life plan with conservative cutting parameters",
                machine_id=ctx.selected_machine_id,
                tool_ids=ctx.selected_tool_ids,
                evidence=EvidenceLabel.PROPOSED,
            )
        )
    elif ctx.objective == WorkflowObjective.MINIMUM_RISK:
        alternatives.append(
            AlternativePlan(
                plan_type=AlternativePlanType.LOWEST_RISK,
                description="Minimum risk plan with verified toolpath and conservative parameters",
                machine_id=ctx.selected_machine_id,
                tool_ids=ctx.selected_tool_ids,
                evidence=EvidenceLabel.PROPOSED,
            )
        )
    else:  # BALANCED
        alternatives.append(
            AlternativePlan(
                plan_type=AlternativePlanType.PARETO_ALTERNATIVE,
                description="Balanced plan balancing cycle time, cost, and tool life",
                machine_id=ctx.selected_machine_id,
                tool_ids=ctx.selected_tool_ids,
                evidence=EvidenceLabel.PROPOSED,
            )
        )

    return alternatives
