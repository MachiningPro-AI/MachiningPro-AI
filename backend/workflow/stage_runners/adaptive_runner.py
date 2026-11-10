"""Adaptive Intelligence stage runner (stage 17).

Delegates to backend.adaptive.
DUPLICATE_LOGIC=NO — calls existing Level-16 adaptive module.
NO_AUTOMATIC_CNC_CHANGE=YES — recommendations only, no auto-application.
"""
from __future__ import annotations

from ..enums import StageStatus, WorkflowStage
from ..models import KnownUnknown, StageResult, WorkflowContext
from .base import StageRunner


class AdaptiveIntelligenceRunner(StageRunner):
    stage = WorkflowStage.ADAPTIVE_INTELLIGENCE

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
                            "adaptive intelligence requires process data"
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
            from backend.adaptive import (
                HUMAN_REVIEW_MANDATORY,
                NO_AUTOMATIC_CNC_CHANGE,
                RECOMMENDATION_ONLY,
            )
            from backend.adaptive.models import AdaptiveContext
            from backend.adaptive.recommendations import build_recommendations

            # Verify safety constants are enforced
            assert NO_AUTOMATIC_CNC_CHANGE, "SAFETY: NO_AUTOMATIC_CNC_CHANGE must be True"
            assert RECOMMENDATION_ONLY, "SAFETY: RECOMMENDATION_ONLY must be True"
            assert HUMAN_REVIEW_MANDATORY, "SAFETY: HUMAN_REVIEW_MANDATORY must be True"

            adaptive_ctx = AdaptiveContext(
                process_ref=ctx.process_ref,
                workflow_id=ctx.workflow_id,
                cutting_data_ref=ctx.cutting_data_ref,
            )
            recs = build_recommendations(adaptive_ctx)

            adaptive_ref = f"ADAPTIVE_{ctx.workflow_id}"
            ctx.adaptive_ref = adaptive_ref
            result.output_refs["adaptive_ref"] = adaptive_ref
            result.output_refs["recommendation_count"] = len(recs)
            result.output_refs["auto_application"] = False
            result.provenance["adaptive_engine"] = "AdaptiveRecommendationEngine"
            result.provenance["no_auto_application"] = True
            result.provenance["evidence"] = "PREDICTED"
            result.review_required = True
            result.status = StageStatus.PASS

        except ImportError as exc:
            result.status = StageStatus.PARTIAL
            result.warnings.append(f"Adaptive module unavailable: {exc}")
            result.known_unknowns.append(
                KnownUnknown(
                    category="adaptive_module",
                    description=str(exc),
                    stage=self.stage,
                )
            )
            adaptive_ref = f"ADAPTIVE_PARTIAL_{ctx.workflow_id}"
            ctx.adaptive_ref = adaptive_ref
            result.output_refs["adaptive_ref"] = adaptive_ref
            result.output_refs["auto_application"] = False
            result.review_required = True
        except Exception as exc:
            result.status = StageStatus.PARTIAL
            result.warnings.append(f"Adaptive intelligence partially completed: {exc!r}")
            adaptive_ref = f"ADAPTIVE_PARTIAL_{ctx.workflow_id}"
            ctx.adaptive_ref = adaptive_ref
            result.output_refs["adaptive_ref"] = adaptive_ref
            result.output_refs["auto_application"] = False
            result.review_required = True

        result.finish()
        return result
