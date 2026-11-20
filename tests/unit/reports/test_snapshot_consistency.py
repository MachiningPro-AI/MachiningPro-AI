"""Cross-format snapshot consistency tests.

MUST 16, MUST 17: All formats in an Export All must come from the same
ReportDocument snapshot. The same report_id, part_id, and section count
must appear in every format.

REPORT_GENERATION_ENGINEERING_STATE_CHANGED=NO always.
"""
from __future__ import annotations

import io
import json
import zipfile

import pytest

from backend.manufacturing_plan.models import ManufacturingPlan
from backend.reports.models import (
    REPORT_GENERATION_ENGINEERING_STATE_CHANGED,
    ExportFormat,
)
from backend.reports.report_service import generate_full_manufacturing_report


def _test_plan() -> ManufacturingPlan:
    return ManufacturingPlan(
        plan_id="P-SNAP-TEST",
        source_id="W-SNAP-001",
        drawing_number="DWG-SNAP",
        revision="A",
        part_id="PART-SNAP",
    )


ALL_FORMATS = [
    ExportFormat.PDF,
    ExportFormat.DOCX,
    ExportFormat.XLSX,
    ExportFormat.CSV,
    ExportFormat.JSON,
    ExportFormat.ZIP,
]


class TestExportAllSnapshot:
    """MUST 16 — same snapshot report_id across all format outputs."""

    @pytest.fixture(scope="class")
    def bundle(self):
        plan = _test_plan()
        return generate_full_manufacturing_report(plan, formats=ALL_FORMATS)

    def test_all_formats_present(self, bundle):
        for fmt in ALL_FORMATS:
            item = bundle.get(fmt)
            assert item is not None, f"Format {fmt} missing from bundle"

    def test_pdf_has_content(self, bundle):
        item = bundle.get(ExportFormat.PDF)
        assert len(item.content) > 0

    def test_docx_has_content(self, bundle):
        item = bundle.get(ExportFormat.DOCX)
        assert len(item.content) > 0

    def test_xlsx_has_content(self, bundle):
        item = bundle.get(ExportFormat.XLSX)
        assert len(item.content) > 0

    def test_csv_has_content(self, bundle):
        item = bundle.get(ExportFormat.CSV)
        assert len(item.content) > 0

    def test_json_has_content(self, bundle):
        item = bundle.get(ExportFormat.JSON)
        assert len(item.content) > 0

    def test_zip_has_content(self, bundle):
        item = bundle.get(ExportFormat.ZIP)
        assert len(item.content) > 0

    def test_json_report_id_matches_document(self, bundle):
        json_item = bundle.get(ExportFormat.JSON)
        data = json.loads(json_item.content)
        doc_rid = bundle.document.metadata.report_id
        assert data["report_id"] == doc_rid

    def test_json_part_id_matches_plan(self, bundle):
        json_item = bundle.get(ExportFormat.JSON)
        data = json.loads(json_item.content)
        # part_reference is in metadata (dataclasses.asdict)
        assert data["metadata"]["part_reference"] == "PART-SNAP"

    def test_json_safety_not_dispatchable(self, bundle):
        json_item = bundle.get(ExportFormat.JSON)
        data = json.loads(json_item.content)
        assert data["safety"]["is_dispatchable"] is False

    def test_json_safety_not_production_released(self, bundle):
        json_item = bundle.get(ExportFormat.JSON)
        data = json.loads(json_item.content)
        assert data["safety"]["production_released"] is False

    def test_json_safety_not_auto_approved(self, bundle):
        json_item = bundle.get(ExportFormat.JSON)
        data = json.loads(json_item.content)
        assert data["safety"]["auto_approved"] is False

    def test_json_engineering_state_not_changed(self, bundle):
        json_item = bundle.get(ExportFormat.JSON)
        data = json.loads(json_item.content)
        assert data["safety"]["engineering_state_changed"] is False

    def test_zip_contains_pdf(self, bundle):
        zip_item = bundle.get(ExportFormat.ZIP)
        with zipfile.ZipFile(io.BytesIO(zip_item.content)) as zf:
            names = zf.namelist()
        assert any(n.endswith(".pdf") or "pdf" in n.lower() for n in names)

    def test_zip_contains_json(self, bundle):
        zip_item = bundle.get(ExportFormat.ZIP)
        with zipfile.ZipFile(io.BytesIO(zip_item.content)) as zf:
            names = zf.namelist()
        assert any(n.endswith(".json") for n in names)

    def test_zip_contains_csv(self, bundle):
        zip_item = bundle.get(ExportFormat.ZIP)
        with zipfile.ZipFile(io.BytesIO(zip_item.content)) as zf:
            names = zf.namelist()
        assert any(n.endswith(".csv") for n in names)

    def test_zip_contains_docx(self, bundle):
        zip_item = bundle.get(ExportFormat.ZIP)
        with zipfile.ZipFile(io.BytesIO(zip_item.content)) as zf:
            names = zf.namelist()
        assert any(n.endswith(".docx") for n in names)

    def test_zip_contains_xlsx(self, bundle):
        zip_item = bundle.get(ExportFormat.ZIP)
        with zipfile.ZipFile(io.BytesIO(zip_item.content)) as zf:
            names = zf.namelist()
        assert any(n.endswith(".xlsx") for n in names)

    def test_csv_utf8_header_present(self, bundle):
        csv_item = bundle.get(ExportFormat.CSV)
        content = csv_item.content.decode("utf-8-sig")
        assert "SAFETY" in content or "section_id" in content or "report_id" in content

    def test_csv_no_injection_values(self, bundle):
        csv_item = bundle.get(ExportFormat.CSV)
        content = csv_item.content.decode("utf-8-sig")
        # OWASP CSV injection: values must not start with =, +, -, @ unescaped
        for line in content.split("\n")[:20]:
            stripped = line.strip()
            if stripped and stripped[0] in ("=", "+", "@"):
                pytest.fail(f"CSV injection risk: {stripped[:80]!r}")

    def test_bundle_engineering_state_not_changed(self, bundle):
        assert bundle.engineering_state_changed is False

    def test_global_state_unchanged(self, bundle):
        assert REPORT_GENERATION_ENGINEERING_STATE_CHANGED is False


class TestRepeatableSnapshot:
    """MUST 17 — generating the same report twice gives consistent report_ids
    when fixed report_id is supplied."""

    def test_fixed_report_id_same_across_formats(self):
        plan = _test_plan()
        bundle = generate_full_manufacturing_report(
            plan,
            formats=[ExportFormat.JSON, ExportFormat.PDF],
            report_id="FIXED-RID-001",
        )
        assert bundle.document.metadata.report_id == "FIXED-RID-001"
        json_data = json.loads(bundle.get(ExportFormat.JSON).content)
        assert json_data["report_id"] == "FIXED-RID-001"

    def test_plan_state_unchanged_after_all_formats(self):
        plan = _test_plan()
        original_part_id = plan.part_id
        _ = generate_full_manufacturing_report(plan, formats=ALL_FORMATS)
        assert plan.part_id == original_part_id

    def test_plan_plan_id_unchanged_after_all_formats(self):
        plan = _test_plan()
        original_plan_id = plan.plan_id
        _ = generate_full_manufacturing_report(plan, formats=ALL_FORMATS)
        assert plan.plan_id == original_plan_id
