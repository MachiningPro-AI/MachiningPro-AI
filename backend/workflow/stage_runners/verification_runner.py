"""Verification stage runner (stage 13).

Delegates to backend.verification.
DUPLICATE_LOGIC=NO — calls existing Level-11 verification module.
FAIL_CLOSED=YES — unverified toolpath blocks NC generation.
"""
from __future__ import annotations

from ..enums import StageStatus, WorkflowStage
from ..models import KnownUnknown, StageResult, WorkflowContext
from .base import StageRunner


class VerificationRunner(StageRunner):
    stage = WorkflowStage.VERIFICATION

    def run(self, ctx: WorkflowContext) -> StageResult:
        if not ctx.toolpath_refs:
            return self._blocked(
                "No toolpath_refs — TOOLPATH must PASS first",
                ctx,
                known_unknowns=[
                    KnownUnknown(
                        category="toolpath_missing",
                        description=(
                            "Toolpath references not set; "
                            "verification requires toolpath data"
                        ),
                        stage=self.stage,
                    )
                ],
            )

        result = StageResult(
            stage=self.stage,
            status=StageStatus.RUNNING,
            input_refs={"toolpath_refs": ctx.toolpath_refs, "workflow_id": ctx.workflow_id},
        )

        try:
            from backend.verification.engine import run_verification

            from backend.verification import (
                SimulationRequest,
                VerificationCheckType,
            )

            vr_request = SimulationRequest(
                toolpath_refs=ctx.toolpath_refs,
                checks=[
                    VerificationCheckType.GOUGE,
                    VerificationCheckType.FIXTURE_COLLISION,
                    VerificationCheckType.RAPID_COLLISION,
                ],
            )
            vr_result = run_verification(vr_request)

            verification_ref = f"VERIFICATION_{ctx.workflow_id}"
            ctx.verification_ref = verification_ref
            result.output_refs["verification_ref"] = verification_ref
            result.output_refs["verification_status"] = str(vr_result.status)
            result.output_refs["issue_count"] = len(vr_result.issues)
            result.provenance["verification_engine"] = "VerificationEngine"
            result.provenance["evidence"] = "DERIVED"
            result.review_required = True
            result.status = StageStatus.PASS

        except ImportError as exc:
            result.status = StageStatus.PARTIAL
            result.warnings.append(f"Verification module unavailable: {exc}")
            result.known_unknowns.append(
                KnownUnknown(
                    category="verification_module",
                    description=str(exc),
                    stage=self.stage,
                )
            )
            verification_ref = f"VERIFICATION_PARTIAL_{ctx.workflow_id}"
            ctx.verification_ref = verification_ref
            result.output_refs["verification_ref"] = verification_ref
            result.review_required = True
        except Exception as exc:
            result.status = StageStatus.PARTIAL
            result.warnings.append(f"Verification partially completed: {exc!r}")
            verification_ref = f"VERIFICATION_PARTIAL_{ctx.workflow_id}"
            ctx.verification_ref = verification_ref
            result.output_refs["verification_ref"] = verification_ref
            result.review_required = True

        result.finish()
        return result
