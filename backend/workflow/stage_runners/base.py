"""Base class for all stage runners."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..enums import StageStatus, WorkflowStage
from ..models import KnownUnknown, StageResult, WorkflowContext


class StageRunner(ABC):
    """Abstract base — each concrete runner wraps one or more existing Level-N functions.

    Design constraints:
      DUPLICATE_LOGIC=NO       — runners call existing backend modules, never re-implement
      FABRICATED_OUTPUT=NO     — PARTIAL/BLOCKED are valid; never invent data to appear complete
      REVIEW_REQUIRED=YES      — set review_required=True wherever human oversight is mandatory
    """

    stage: WorkflowStage  # set on each concrete class

    @abstractmethod
    def run(self, ctx: WorkflowContext) -> StageResult:
        """Execute the stage. Must not raise — all errors become FAILED/BLOCKED results."""
        ...

    def _blocked(
        self,
        reason: str,
        ctx: WorkflowContext,
        known_unknowns: list[KnownUnknown] | None = None,
    ) -> StageResult:
        result = StageResult(
            stage=self.stage,
            status=StageStatus.BLOCKED,
            blocking_reasons=[reason],
            known_unknowns=known_unknowns or [],
            input_refs={"workflow_id": ctx.workflow_id},
        )
        result.finish()
        return result

    def _failed(self, error: str, ctx: WorkflowContext) -> StageResult:
        result = StageResult(
            stage=self.stage,
            status=StageStatus.FAILED,
            errors=[error],
            input_refs={"workflow_id": ctx.workflow_id},
        )
        result.finish()
        return result
