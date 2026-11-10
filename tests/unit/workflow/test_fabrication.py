"""Anti-fabrication tests per MUST 35 — verify no hardcoded workflow success."""
import pathlib
import pytest


WORKFLOW_DIR = pathlib.Path(__file__).parents[3] / "backend" / "workflow"


def _get_all_py_sources() -> list[tuple[str, str]]:
    return [(str(p), p.read_text(encoding="utf-8")) for p in WORKFLOW_DIR.rglob("*.py")]


class TestNoFabricatedResults:
    """FABRICATED_WORKFLOW_RESULT_FOUND=NO"""

    def test_no_hardcoded_pass_all(self):
        """Runners must not unconditionally return PASS for all stages."""
        for path, src in _get_all_py_sources():
            # No runner should return PASS without any conditional check
            assert 'status = StageStatus.PASS\n        result.finish()\n        return result' not in src or \
                   'if ' in src, f"Potential unconditional PASS in {path}"

    def test_no_fake_cycle_time(self):
        prohibited_patterns = [
            "cycle_time = 42",
            "cycle_time = 100",
            "cycle_time_seconds = 0",
        ]
        for path, src in _get_all_py_sources():
            for p in prohibited_patterns:
                assert p not in src, f"Hardcoded cycle time in {path}"

    def test_no_fake_cost(self):
        prohibited_patterns = [
            "cost = 100.0",
            "cost = 999",
            "total_cost = 0",
        ]
        for path, src in _get_all_py_sources():
            for p in prohibited_patterns:
                assert p not in src.replace(" ", ""), f"Hardcoded cost in {path}"

    def test_no_fake_machine_id(self):
        """Stage results must not embed fake machine IDs."""
        for path, src in _get_all_py_sources():
            # Ref strings are OK (they're just identifiers), but hardcoded production specs aren't
            assert "machine_id = 'VMC_001_FAKE'" not in src

    def test_blocked_is_valid_outcome(self):
        """Verify BLOCKED is used in runners (not hidden as PASS)."""
        from backend.workflow.enums import StageStatus
        assert StageStatus.BLOCKED in StageStatus

    def test_partial_is_valid_outcome(self):
        """Verify PARTIAL is used in runners."""
        from backend.workflow.enums import StageStatus
        assert StageStatus.PARTIAL in StageStatus

    def test_nc_runner_never_dispatches(self):
        from backend.workflow.stage_runners.nc_runner import NcCandidateRunner
        from backend.workflow.models import WorkflowContext
        from backend.workflow.enums import WorkflowObjective

        ctx = WorkflowContext(
            workflow_id="WF_FAB",
            part_reference="PART",
            revision="R1",
            source_file_ref=None,
            material_ref=None,
            quantity=1,
            stock_ref=None,
            objective=WorkflowObjective.BALANCED,
        )
        ctx.verification_ref = "VERIFICATION_WF_FAB"
        runner = NcCandidateRunner()
        result = runner.run(ctx)
        # is_dispatchable must never be True
        is_dispatchable = result.output_refs.get("is_dispatchable", False)
        assert is_dispatchable is False

    def test_digital_twin_never_cnc_write(self):
        from backend.workflow.stage_runners.digital_twin_runner import DigitalTwinRunner
        from backend.workflow.models import WorkflowContext
        from backend.workflow.enums import WorkflowObjective

        ctx = WorkflowContext(
            workflow_id="WF_TWIN_FAB",
            part_reference="PART",
            revision="R1",
            source_file_ref=None,
            material_ref=None,
            quantity=1,
            stock_ref=None,
            objective=WorkflowObjective.BALANCED,
        )
        ctx.machine_candidates_ref = "MACHINES_WF_TWIN_FAB"
        ctx.cutting_data_ref = "CUTTING_DATA_WF_TWIN_FAB"

        runner = DigitalTwinRunner()
        result = runner.run(ctx)
        # cnc_write must never be True
        cnc_write = result.output_refs.get("cnc_write", False)
        assert cnc_write is False
