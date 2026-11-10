"""Tests for the Level-20 export service."""
import json

from backend.export.export_service import (
    export_dfm_json,
    export_nc_manifest_json,
    export_plan_html,
    export_plan_json,
    export_stage_csv,
)
from backend.workflow.enums import WorkflowMode, WorkflowObjective, WorkflowStatus
from backend.workflow.models import ManufacturingWorkflow


def _make_wf(part: str = "PART-EXPORT") -> ManufacturingWorkflow:
    return ManufacturingWorkflow.create(
        part_reference=part,
        revision="REV-A",
        source_file_ref=None,
        requested_mode=WorkflowMode.ANALYSIS_ONLY,
        objective=WorkflowObjective.BALANCED,
        material_ref="MAT-304",
        quantity=3,
        stock_ref=None,
    )


class TestPlanJsonExport:
    def test_returns_bytes(self):
        wf = _make_wf()
        result = export_plan_json(wf)
        assert isinstance(result, bytes)

    def test_valid_json(self):
        wf = _make_wf()
        data = json.loads(export_plan_json(wf))
        assert isinstance(data, dict)

    def test_no_final_plan_returns_error_json(self):
        wf = _make_wf()
        data = json.loads(export_plan_json(wf))
        assert "error" in data

    def test_safety_flags_present(self):
        wf = _make_wf()
        wf.status = WorkflowStatus.COMPLETED
        # Create a minimal final plan

        from backend.workflow.models import ManufacturingPlanSummary, _id
        plan = ManufacturingPlanSummary(
            plan_id=_id("PLAN", wf.workflow_id),
            workflow_id=wf.workflow_id,
        )
        wf.final_plan = plan
        data = json.loads(export_plan_json(wf))
        assert data["safety"]["PRODUCTION_APPROVED"] is False
        assert data["safety"]["DISPATCHED"] is False
        assert data["safety"]["MACHINE_STARTED"] is False

    def test_workflow_id_present(self):
        wf = _make_wf("PART-EXPORT-X")
        from backend.workflow.models import ManufacturingPlanSummary, _id
        plan = ManufacturingPlanSummary(
            plan_id=_id("PLAN", wf.workflow_id), workflow_id=wf.workflow_id
        )
        wf.final_plan = plan
        data = json.loads(export_plan_json(wf))
        assert data["workflow_id"] == wf.workflow_id
        assert data["part_reference"] == "PART-EXPORT-X"

    def test_format_identifier_present(self):
        wf = _make_wf()
        from backend.workflow.models import ManufacturingPlanSummary, _id
        wf.final_plan = ManufacturingPlanSummary(
            plan_id=_id("PLAN", wf.workflow_id), workflow_id=wf.workflow_id
        )
        data = json.loads(export_plan_json(wf))
        assert data["export_format"] == "MachiningPro-Plan-JSON"


class TestPlanHtmlExport:
    def test_returns_bytes(self):
        wf = _make_wf()
        result = export_plan_html(wf)
        assert isinstance(result, bytes)

    def test_valid_html(self):
        wf = _make_wf()
        html = export_plan_html(wf).decode("utf-8")
        assert "<!doctype html>" in html.lower()
        assert "<title>" in html

    def test_safety_warning_present(self):
        wf = _make_wf()
        html = export_plan_html(wf).decode("utf-8")
        assert "PRODUCTION_APPROVED" in html
        assert "Engineering Review Required" in html

    def test_part_reference_present(self):
        wf = _make_wf("PART-HTML-CHECK")
        html = export_plan_html(wf).decode("utf-8")
        assert "PART-HTML-CHECK" in html

    def test_no_server_path_in_html(self):
        wf = _make_wf()
        html = export_plan_html(wf).decode("utf-8")
        # Should not contain filesystem-like paths
        assert "C:\\" not in html
        assert "/home/" not in html
        assert "/usr/" not in html

    def test_stage_rows_present(self):
        wf = _make_wf()
        html = export_plan_html(wf).decode("utf-8")
        assert "CAD Import" in html
        assert "NOT_STARTED" in html


class TestStagesCsvExport:
    def test_returns_bytes(self):
        wf = _make_wf()
        result = export_stage_csv(wf)
        assert isinstance(result, bytes)

    def test_csv_has_header(self):
        wf = _make_wf()
        csv_text = export_stage_csv(wf).decode("utf-8")
        assert "stage" in csv_text
        assert "status" in csv_text
        assert "duration_ms" in csv_text

    def test_csv_has_19_data_rows(self):
        wf = _make_wf()
        csv_text = export_stage_csv(wf).decode("utf-8")
        lines = [ln for ln in csv_text.strip().splitlines() if ln]
        # 1 header + 19 stage rows
        assert len(lines) == 20

    def test_csv_stage_values(self):
        wf = _make_wf()
        csv_text = export_stage_csv(wf).decode("utf-8")
        assert "01_CAD_IMPORT" in csv_text
        assert "19_FINAL_MANUFACTURING_PLAN" in csv_text


class TestDfmJsonExport:
    def test_returns_bytes(self):
        wf = _make_wf()
        assert isinstance(export_dfm_json(wf), bytes)

    def test_valid_json(self):
        wf = _make_wf()
        data = json.loads(export_dfm_json(wf))
        assert "dfm_stage_status" in data
        assert data["dfm_stage_status"] == "NOT_RUN"

    def test_format_identifier(self):
        wf = _make_wf()
        data = json.loads(export_dfm_json(wf))
        assert data["export_format"] == "MachiningPro-DFM-JSON"


class TestNcManifestExport:
    def test_returns_bytes(self):
        wf = _make_wf()
        assert isinstance(export_nc_manifest_json(wf), bytes)

    def test_offline_safety_labels_present(self):
        wf = _make_wf()
        data = json.loads(export_nc_manifest_json(wf))
        assert data["safety"]["OFFLINE_CANDIDATE"] is True
        assert data["safety"]["NOT_MACHINE_APPROVED"] is True
        assert data["safety"]["NOT_DISPATCHED"] is True
        assert data["safety"]["NO_CNC_TRANSFER"] is True

    def test_format_identifier(self):
        wf = _make_wf()
        data = json.loads(export_nc_manifest_json(wf))
        assert data["export_format"] == "MachiningPro-NC-Manifest-JSON"
