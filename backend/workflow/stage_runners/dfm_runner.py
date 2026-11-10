"""DFM stage runner (stage 04).

Delegates to backend.dfm.
DUPLICATE_LOGIC=NO — calls existing Level-4 DFM foundation.
"""
from __future__ import annotations

from ..enums import StageStatus, WorkflowStage
from ..models import KnownUnknown, StageResult, WorkflowContext
from .base import StageRunner


class DfmRunner(StageRunner):
    stage = WorkflowStage.DFM

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
                            "feature recognition did not complete"
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
            from backend.dfm import foundational_dfm_rules

            rules = foundational_dfm_rules()
            dfm_ref = f"DFM_{ctx.workflow_id}"
            ctx.dfm_ref = dfm_ref
            result.output_refs["dfm_ref"] = dfm_ref
            result.output_refs["rule_count"] = len(rules)
            result.provenance["dfm_rules_count"] = len(rules)
            result.provenance["evidence"] = "DERIVED"
            result.review_required = True
            result.status = StageStatus.PASS
        except ImportError as exc:
            result.status = StageStatus.PARTIAL
            result.warnings.append(f"DFM module unavailable: {exc}")
            result.known_unknowns.append(
                KnownUnknown(
                    category="dfm_module",
                    description=str(exc),
                    stage=self.stage,
                )
            )
            dfm_ref = f"DFM_PARTIAL_{ctx.workflow_id}"
            ctx.dfm_ref = dfm_ref
            result.output_refs["dfm_ref"] = dfm_ref
        except Exception as exc:
            result.status = StageStatus.FAILED
            result.errors.append(f"DFM error: {exc!r}")

        result.finish()
        return result
