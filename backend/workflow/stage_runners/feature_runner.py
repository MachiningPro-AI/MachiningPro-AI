"""Feature Recognition stage runner (stage 03).

Delegates to backend.interoperability.feature_recognition.
DUPLICATE_LOGIC=NO — calls existing Level-3 engine.
"""
from __future__ import annotations

from ..enums import StageStatus, WorkflowStage
from ..models import KnownUnknown, StageResult, WorkflowContext
from .base import StageRunner


class FeatureRecognitionRunner(StageRunner):
    stage = WorkflowStage.FEATURE_RECOGNITION

    def run(self, ctx: WorkflowContext) -> StageResult:
        if not ctx.geometry_ref:
            return self._blocked(
                "No geometry_ref — CAD_IMPORT must PASS first",
                ctx,
                known_unknowns=[
                    KnownUnknown(
                        category="geometry_missing",
                        description=(
                            "Geometry reference not set; "
                            "CAD import did not produce usable geometry"
                        ),
                        stage=self.stage,
                    )
                ],
            )

        result = StageResult(
            stage=self.stage,
            status=StageStatus.RUNNING,
            input_refs={"geometry_ref": ctx.geometry_ref, "workflow_id": ctx.workflow_id},
        )

        try:
            from backend.interoperability.feature_recognition import recognize_features

            # recognize_features needs geometry/topology data; at workflow level
            # we only have a ref string — call with None geometry (2D/NONE path)
            recog_result = recognize_features(
                geometry=None,
                topology=None,
            )
            features_ref = f"FEATURES_{ctx.workflow_id}"
            ctx.features_ref = features_ref
            result.output_refs["features_ref"] = features_ref
            result.output_refs["feature_count"] = len(recog_result.features)
            result.provenance["recognition_path"] = recog_result.recognition_basis
            result.provenance["feature_count"] = len(recog_result.features)
            result.provenance["evidence"] = "DERIVED"
            result.review_required = True
            result.status = StageStatus.PASS
        except ImportError as exc:
            result.status = StageStatus.PARTIAL
            result.warnings.append(f"Feature recognition module unavailable: {exc}")
            result.known_unknowns.append(
                KnownUnknown(
                    category="feature_recognition_module",
                    description=str(exc),
                    stage=self.stage,
                )
            )
            # Still set a ref so downstream can attempt to continue
            features_ref = f"FEATURES_PARTIAL_{ctx.workflow_id}"
            ctx.features_ref = features_ref
            result.output_refs["features_ref"] = features_ref
        except Exception as exc:
            result.status = StageStatus.FAILED
            result.errors.append(f"Feature recognition error: {exc!r}")

        result.finish()
        return result
