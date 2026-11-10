"""Security tests per MUST 34 — verify no machine writes, no auto-dispatch, etc."""
import ast
import inspect
import pathlib
import pytest


WORKFLOW_DIR = pathlib.Path(__file__).parents[3] / "backend" / "workflow"


def _get_all_py_sources() -> list[tuple[str, str]]:
    """Return (path_str, source) for all .py files in backend/workflow/."""
    sources = []
    for p in WORKFLOW_DIR.rglob("*.py"):
        sources.append((str(p), p.read_text(encoding="utf-8")))
    return sources


class TestNoRealMachineWrite:
    """REAL_MACHINE_WRITE_FOUND=NO — checks for actual call patterns, not constant declarations."""

    def test_no_cnc_connection_calls(self):
        """Check for actual cnc connection calls (not safety constant declarations)."""
        prohibited_calls = [
            "cnc.connect(", "cnc.write(", "machine.write(",
            "socket.connect(", "serial.write(",
        ]
        for path, src in _get_all_py_sources():
            for term in prohibited_calls:
                assert term not in src, f"Prohibited call '{term}' in {path}"

    def test_no_machine_write_function_calls(self):
        prohibited = ["write_to_machine(", "send_to_cnc(", "machine_write("]
        for path, src in _get_all_py_sources():
            for term in prohibited:
                assert term not in src, f"Prohibited call '{term}' in {path}"

    def test_engine_no_cnc_write_constant(self):
        from backend.workflow.engine import WorkflowEngine
        engine = WorkflowEngine()
        assert engine.NO_CNC_WRITE is True


class TestNoAutoCncDispatch:
    """AUTO_CNC_DISPATCH_FOUND=NO"""

    def test_no_dispatch_function_calls(self):
        """Check for actual dispatch call patterns (not constant declarations)."""
        prohibited_calls = [
            "dispatch_to_machine(", "cnc_dispatch(", "auto_dispatch(",
        ]
        for path, src in _get_all_py_sources():
            for term in prohibited_calls:
                assert term not in src, f"Prohibited call '{term}' in {path}"

    def test_engine_no_auto_dispatch_constant(self):
        from backend.workflow.engine import WorkflowEngine
        engine = WorkflowEngine()
        assert engine.NO_AUTO_DISPATCH is True


class TestNoAutoApproval:
    """AUTO_APPROVAL_FOUND=NO"""

    def test_no_auto_approve_calls(self):
        """Check for actual auto-approve call patterns."""
        prohibited_calls = [
            "approve_automatically(", "auto_approve(", "approve_without_review(",
        ]
        for path, src in _get_all_py_sources():
            for term in prohibited_calls:
                assert term not in src, f"Prohibited call '{term}' in {path}"

    def test_engine_no_auto_approval_constant(self):
        from backend.workflow.engine import WorkflowEngine
        engine = WorkflowEngine()
        assert engine.NO_AUTO_APPROVAL is True

    def test_plan_production_approved_is_false(self):
        from backend.api.workflow import PlanResponse
        # production_approved default must be False
        response_fields = PlanResponse.model_fields
        assert "production_approved" in response_fields
        default = response_fields["production_approved"].default
        assert default is False


class TestNoAutomaticAdaptation:
    """AUTOMATIC_ADAPTATION_FOUND=NO"""

    def test_no_auto_adaptation_calls(self):
        """Check for actual auto-adaptation call patterns."""
        prohibited_calls = [
            "apply_adaptation(", "auto_adapt_parameters(", "automatic_parameter_change(",
        ]
        for path, src in _get_all_py_sources():
            for term in prohibited_calls:
                assert term not in src, f"Prohibited call '{term}' in {path}"

    def test_engine_no_auto_adaptive(self):
        from backend.workflow.engine import WorkflowEngine
        engine = WorkflowEngine()
        assert engine.NO_AUTO_ADAPTIVE_APPLICATION is True

    def test_adaptive_runner_sets_auto_application_false(self):
        from backend.workflow.stage_runners.adaptive_runner import AdaptiveIntelligenceRunner
        from backend.workflow.models import WorkflowContext
        from backend.workflow.enums import WorkflowObjective

        ctx = WorkflowContext(
            workflow_id="WF_ADAPT",
            part_reference="PART",
            revision="R1",
            source_file_ref=None,
            material_ref=None,
            quantity=1,
            stock_ref=None,
            objective=WorkflowObjective.BALANCED,
        )
        ctx.process_ref = "PROCESS_WF_ADAPT"
        runner = AdaptiveIntelligenceRunner()
        result = runner.run(ctx)
        # auto_application must be False in output_refs or not set
        auto_app = result.output_refs.get("auto_application", False)
        assert auto_app is False


class TestNoMachineStarted:
    """MACHINE_STARTED=NO — API endpoint never starts a machine."""

    def test_no_machine_start_endpoint(self):
        from backend.api.workflow import router
        # Check no route contains 'start' in path that implies machine start
        for route in router.routes:
            path = getattr(route, "path", "")
            # Reject any path with /machine-start, /start-machine, /cnc-start
            assert "machine-start" not in path
            assert "cnc-start" not in path
            assert "start-machine" not in path

    def test_no_machine_started_flag_in_plan(self):
        from backend.api.workflow import PlanResponse
        response_fields = PlanResponse.model_fields
        assert "machine_started" in response_fields
        default = response_fields["machine_started"].default
        assert default is False
