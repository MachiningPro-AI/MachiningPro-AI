"""NC Candidate stage runner (stage 14).

Delegates to backend.nc.
DUPLICATE_LOGIC=NO — calls existing Level-12 NC generation module.
OFFLINE_ONLY=YES — no CNC dispatch, no machine writes.
"""
from __future__ import annotations

from ..enums import StageStatus, WorkflowStage
from ..models import KnownUnknown, StageResult, WorkflowContext
from .base import StageRunner


class NcCandidateRunner(StageRunner):
    stage = WorkflowStage.NC_CANDIDATE

    def run(self, ctx: WorkflowContext) -> StageResult:
        if not ctx.verification_ref:
            return self._blocked(
                "No verification_ref — VERIFICATION must PASS first "
                "(unverified toolpath blocks NC generation)",
                ctx,
                known_unknowns=[
                    KnownUnknown(
                        category="verification_missing",
                        description=(
                            "Verification reference not set; "
                            "NC generation requires verified toolpath"
                        ),
                        stage=self.stage,
                    )
                ],
            )

        result = StageResult(
            stage=self.stage,
            status=StageStatus.RUNNING,
            input_refs={"verification_ref": ctx.verification_ref, "workflow_id": ctx.workflow_id},
        )

        try:
            from backend.nc.generator import generate_nc_candidate

            nc_input = {
                "verification_ref": ctx.verification_ref,
                "toolpath_refs": ctx.toolpath_refs,
                "workflow_id": ctx.workflow_id,
            }
            generate_nc_candidate(nc_input)

            nc_ref = f"NC_{ctx.workflow_id}"
            ctx.nc_ref = nc_ref
            result.output_refs["nc_ref"] = nc_ref
            result.output_refs["is_dispatchable"] = False
            result.output_refs["offline_only"] = True
            result.provenance["nc_generator"] = "NCGenerator"
            result.provenance["no_dispatch"] = True
            result.provenance["evidence"] = "DERIVED"
            result.review_required = True
            result.status = StageStatus.PASS

        except ImportError as exc:
            result.status = StageStatus.PARTIAL
            result.warnings.append(f"NC module unavailable: {exc}")
            result.known_unknowns.append(
                KnownUnknown(
                    category="postprocessor_unavailable",
                    description=f"NC generation module unavailable: {exc}",
                    stage=self.stage,
                )
            )
            nc_ref = f"NC_PARTIAL_{ctx.workflow_id}"
            ctx.nc_ref = nc_ref
            result.output_refs["nc_ref"] = nc_ref
            result.output_refs["is_dispatchable"] = False
            result.review_required = True
        except Exception as exc:
            result.status = StageStatus.PARTIAL
            result.warnings.append(f"NC generation partially completed: {exc!r}")
            nc_ref = f"NC_PARTIAL_{ctx.workflow_id}"
            ctx.nc_ref = nc_ref
            result.output_refs["nc_ref"] = nc_ref
            result.output_refs["is_dispatchable"] = False
            result.review_required = True

        result.finish()
        return result
