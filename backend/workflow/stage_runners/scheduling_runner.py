"""Scheduling stage runner (stage 15).

Delegates to backend.scheduling.scheduler.
Uses MachineClass mapper — fail-closed for unmapped classes.
DUPLICATE_LOGIC=NO — calls existing Level-13 scheduler.
"""
from __future__ import annotations

from ..enums import StageStatus, WorkflowStage
from ..models import KnownUnknown, StageResult, WorkflowContext
from .base import StageRunner


class SchedulingRunner(StageRunner):
    stage = WorkflowStage.SCHEDULING

    def run(self, ctx: WorkflowContext) -> StageResult:
        if not ctx.machine_candidates_ref:
            return self._blocked(
                "No machine_candidates_ref — MACHINE_SELECTION must PASS first",
                ctx,
                known_unknowns=[
                    KnownUnknown(
                        category="machine_availability_unknown",
                        description=(
                            "Machine candidates not available; "
                            "scheduling requires machine selection"
                        ),
                        stage=self.stage,
                    )
                ],
            )

        result = StageResult(
            stage=self.stage,
            status=StageStatus.RUNNING,
            input_refs={
                "machine_candidates_ref": ctx.machine_candidates_ref,
                "workflow_id": ctx.workflow_id,
            },
        )

        # MachineClass mapper — fail-closed for unmapped classes
        if ctx.machine_class_library:
            try:
                from backend.integration.machine_class_mapper import library_to_scheduling
                from backend.machine_library.enums import MachineClass as LibraryMachineClass

                lib_class = LibraryMachineClass(ctx.machine_class_library)
                sched_class = library_to_scheduling(lib_class)
                ctx.machine_class_scheduling = str(sched_class)
                result.provenance["machine_class_mapping"] = (
                    f"{ctx.machine_class_library} → {sched_class}"
                )

            except Exception as exc:
                # Unmapped MachineClass — fail-closed
                result.status = StageStatus.BLOCKED
                result.blocking_reasons.append(
                    f"MachineClass mapping failed (fail-closed): {exc!r}"
                )
                result.known_unknowns.append(
                    KnownUnknown(
                        category="machine_class_unmapped",
                        description=(
                            f"MachineClass '{ctx.machine_class_library}' cannot be mapped "
                            f"to scheduling namespace: {exc!r}"
                        ),
                        stage=self.stage,
                    )
                )
                result.finish()
                return result

        try:
            from backend.scheduling.enums import MachineAvailabilityStatus
            from backend.scheduling.models import MachineResource, ProductionJob
            from backend.scheduling.scheduler import evaluate_machine_candidates

            # Create a minimal job for scheduling
            job = ProductionJob(
                job_id=f"JOB_{ctx.workflow_id}",
                part_reference=ctx.part_reference,
                quantity=ctx.quantity,
                machine_class=ctx.machine_class_scheduling or "VMC_3AXIS",
                priority="NORMAL",
            )

            # Create a minimal synthetic resource for the available machine
            resource = MachineResource(
                machine_id=ctx.selected_machine_id or f"MACHINE_{ctx.workflow_id}",
                machine_class=ctx.machine_class_scheduling or "VMC_3AXIS",
                availability_status=MachineAvailabilityStatus.AVAILABLE,
            )

            reports = evaluate_machine_candidates(job, [resource])

            schedule_ref = f"SCHEDULE_{ctx.workflow_id}"
            ctx.schedule_ref = schedule_ref
            result.output_refs["schedule_ref"] = schedule_ref
            result.output_refs["evaluated_machines"] = len(reports)
            result.provenance["scheduler"] = "evaluate_machine_candidates"
            result.provenance["evidence"] = "DERIVED"
            result.status = StageStatus.PASS

        except ImportError as exc:
            result.status = StageStatus.PARTIAL
            result.warnings.append(f"Scheduling module unavailable: {exc}")
            result.known_unknowns.append(
                KnownUnknown(
                    category="scheduling_module",
                    description=str(exc),
                    stage=self.stage,
                )
            )
            schedule_ref = f"SCHEDULE_PARTIAL_{ctx.workflow_id}"
            ctx.schedule_ref = schedule_ref
            result.output_refs["schedule_ref"] = schedule_ref
        except Exception as exc:
            result.status = StageStatus.PARTIAL
            result.warnings.append(f"Scheduling partially completed: {exc!r}")
            schedule_ref = f"SCHEDULE_PARTIAL_{ctx.workflow_id}"
            ctx.schedule_ref = schedule_ref
            result.output_refs["schedule_ref"] = schedule_ref

        result.finish()
        return result
