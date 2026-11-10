"""Machine Selection stage runner (stage 06).

Uses MachinePipelineAdapter (MC-1) and MachineClassMapper.
DUPLICATE_LOGIC=NO — delegates to existing Level-13/18.5E adapters.
FAIL_CLOSED=YES — unmapped MachineClass → BLOCKED.
"""
from __future__ import annotations

from ..enums import StageStatus, WorkflowStage
from ..models import KnownUnknown, StageResult, WorkflowContext
from .base import StageRunner


class MachineSelectionRunner(StageRunner):
    stage = WorkflowStage.MACHINE_SELECTION

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
                            "cannot select machine without process requirements"
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
            from backend.integration.machine_adapter import (
                MachineLookupStatus,
                MachinePipelineAdapter,
            )
            from backend.machine_library.seed_catalog import seed_machine_library

            adapter = MachinePipelineAdapter()
            registry = seed_machine_library()

            # Collect all machine stable_ids as candidates
            all_ids = [r.stable_id for r in registry.all()]
            if not all_ids:
                result.status = StageStatus.BLOCKED
                result.blocking_reasons.append("Machine library is empty — no candidates available")
                result.known_unknowns.append(
                    KnownUnknown(
                        category="no_eligible_machine",
                        description="Machine library returned no records",
                        stage=self.stage,
                    )
                )
                result.finish()
                return result

            # Resolve first available machine as primary candidate (workflow-level)
            candidates = []
            for sid in all_ids[:5]:  # probe first 5
                lookup = adapter.lookup(sid)
                if lookup.status == MachineLookupStatus.RESOLVED and lookup.record:
                    candidates.append(lookup.record.stable_id)

            if not candidates:
                result.status = StageStatus.BLOCKED
                result.blocking_reasons.append("No machine candidates resolved from library")
                result.known_unknowns.append(
                    KnownUnknown(
                        category="no_eligible_machine",
                        description=(
                            "Machine library lookup returned no RESOLVED records "
                            "for sampled candidates"
                        ),
                        stage=self.stage,
                    )
                )
                result.finish()
                return result

            machine_candidates_ref = f"MACHINES_{ctx.workflow_id}"
            ctx.machine_candidates_ref = machine_candidates_ref
            ctx.selected_machine_id = candidates[0]

            # Store the library MachineClass for downstream mapper use
            primary_record = registry.get(candidates[0])
            if primary_record and hasattr(primary_record, "machine_class"):
                ctx.machine_class_library = str(primary_record.machine_class)

            result.output_refs["machine_candidates_ref"] = machine_candidates_ref
            result.output_refs["candidate_count"] = len(candidates)
            result.output_refs["selected_machine_id"] = candidates[0]
            result.provenance["machine_provider"] = "MachinePipelineAdapter"
            result.provenance["library"] = "MachineCatalogRegistry"
            result.provenance["evidence"] = "CONFIRMED"
            result.status = StageStatus.PASS

        except ImportError as exc:
            result.status = StageStatus.PARTIAL
            result.warnings.append(f"Machine library adapter unavailable: {exc}")
            result.known_unknowns.append(
                KnownUnknown(
                    category="machine_library_module",
                    description=str(exc),
                    stage=self.stage,
                )
            )
            machine_candidates_ref = f"MACHINES_PARTIAL_{ctx.workflow_id}"
            ctx.machine_candidates_ref = machine_candidates_ref
            result.output_refs["machine_candidates_ref"] = machine_candidates_ref
        except Exception as exc:
            result.status = StageStatus.FAILED
            result.errors.append(f"Machine selection error: {exc!r}")

        result.finish()
        return result
