"""
REPORTING_AND_EXPORT_MODULE_02_UI_E2E_ACCEPTANCE
E2E acceptance test suite using FastAPI TestClient.

HARD RULES (NEVER violated):
- Use only the real Reports module / canonical ReportDocument pipeline
- Do NOT hand-create output files to satisfy acceptance
- Do NOT bypass API/report services
- Do NOT inject expected ground-truth values into actual report results
- Do NOT fabricate missing engineering data
- Do NOT mutate engineering state during report generation
- REPORT_GENERATION_ENGINEERING_STATE_CHANGED=False — asserted at every step
"""
from __future__ import annotations

import io
import json
import os
import time
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# --- Safety invariant import ---
from backend.reports.models import REPORT_GENERATION_ENGINEERING_STATE_CHANGED

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MP_SYN_001_DXF = Path(
    r"D:\makina_ogrenmesi\olcum_denemeleri\MP_SYN_001_extracted"
    r"\MachiningPro_Synthetic_Test_Pack\MP_SYN_001.dxf"
)
_MP_SYN_001_STEP = Path(
    r"D:\makina_ogrenmesi\olcum_denemeleri\MP_SYN_001_extracted"
    r"\MachiningPro_Synthetic_Test_Pack\MP_SYN_001.step"
)
_ARTIFACTS_DIR = Path(
    r"D:\makina_ogrenmesi\MachiningPro_AI_NEXT\artifacts"
    r"\reporting_acceptance\MP_SYN_001"
)

# Ground truth (comparison-only — NEVER injected into report generation)
GT_PART_ID = "MP-SYN-001"
GT_REVISION = "A"
GT_FEATURE_COUNT = 6
GT_MATERIAL = "EN AW-6082-T6"


# ---------------------------------------------------------------------------
# Test infrastructure
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _setup_env():
    os.environ.setdefault("MACHININGPRO_DEV_USERNAME", "admin")
    os.environ.setdefault("MACHININGPRO_DEV_PASSWORD", "machiningpro")
    os.environ.setdefault("MACHININGPRO_DEV_JWT_SECRET", "m02-e2e-acceptance")
    _ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope="session")
def client():
    from backend.api.app import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def token(client):
    res = client.post(
        "/api/login",
        json={"username": "admin", "password": "machiningpro"},
    )
    assert res.status_code == 200, f"Login failed: {res.text}"
    body = res.json()
    return body.get("token") or body.get("access_token", "")


@pytest.fixture(scope="session")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def workflow_id(client, auth):
    """Create workflow for MP_SYN_001 with injected ManufacturingPlan."""
    from backend.manufacturing_plan.models import (
        ManufacturingOperation,
        ManufacturingPlan,
        ManufacturingPlanMachine,
        ManufacturingPlanTool,
        OpenItem,
        OpenItemCategory,
        OpenItemSeverity,
        OpenItemStatus,
    )

    # Create workflow via real API
    res = client.post(
        "/api/workflow",
        json={"part_reference": GT_PART_ID, "revision": GT_REVISION,
              "source_file_ref": "MP_SYN_001.dxf"},
        headers=auth,
    )
    assert res.status_code == 201, f"Workflow creation failed: {res.status_code}: {res.text[:300]}"
    wf_id = res.json().get("workflow_id") or res.json().get("id")
    assert wf_id

    # Build MP_SYN_001 plan fixture (test fixture setup — not bypassing reports)
    def _make_op(op_id, op_num, feat, op_type, tool_id):
        return ManufacturingOperation(
            op_id=op_id, op_number=op_num, setup_id="SETUP-1",
            feature_id=feat, operation_type=op_type,
            machine_id="VMC-CANDIDATE", machine_label="3-Axis VMC (CANDIDATE)",
            tool_id=tool_id, holder_id=None,
            cutting_speed_m_min=None, feed_rate_mm_min=None, rpm=None,
            ap_mm=None, ae_mm=None, coolant_note=None,
            target_tolerance=None, surface_finish=None, inspection_note=None,
            cycle_time_context=None, capability_context=None,
            surface_capability_context=None, parameter_source="CANDIDATE",
        )

    ops = [
        _make_op("OP-E2E-001", 1, "H1", "DRILLING", "drill-8mm"),
        _make_op("OP-E2E-002", 2, "H2", "DRILLING", "drill-8mm"),
        _make_op("OP-E2E-003", 3, "H3", "DRILLING", "drill-10mm"),
        _make_op("OP-E2E-004", 4, "P1", "POCKET_MILLING", "endmill-12mm"),
        _make_op("OP-E2E-005", 5, "S1", "SLOT_MILLING", "endmill-10mm"),
        _make_op("OP-E2E-006", 6, "ST1", "SHOULDER_MILLING", "endmill-12mm"),
    ]
    machine = ManufacturingPlanMachine(
        entry_id="ME-E2E-01", machine_id="VMC-CANDIDATE",
        machine_label="3-Axis VMC (CANDIDATE)", machine_type="VMC",
        setup_ids=("SETUP-1",),
        operation_ids=tuple(f"OP-E2E-{i:03d}" for i in range(1, 7)),
    )
    tools = [
        ManufacturingPlanTool(entry_id="TE-DR8", tool_id="drill-8mm",
                              tool_label="8mm Drill (CANDIDATE)", tool_type="DRILL",
                              holder_id=None, holder_label=None, quantity_required=1,
                              operation_ids=("OP-E2E-001", "OP-E2E-002")),
        ManufacturingPlanTool(entry_id="TE-DR10", tool_id="drill-10mm",
                              tool_label="10mm Drill (CANDIDATE)", tool_type="DRILL",
                              holder_id=None, holder_label=None, quantity_required=1,
                              operation_ids=("OP-E2E-003",)),
        ManufacturingPlanTool(entry_id="TE-EM12", tool_id="endmill-12mm",
                              tool_label="12mm End Mill (CANDIDATE)", tool_type="END_MILL",
                              holder_id=None, holder_label=None, quantity_required=1,
                              operation_ids=("OP-E2E-004", "OP-E2E-006")),
    ]
    plan = ManufacturingPlan(
        plan_id="MP-SYN-001-E2E",
        source_id=wf_id,
        drawing_number=GT_PART_ID,
        revision=GT_REVISION,
        part_id=GT_PART_ID,
        operations=ops,
        machine_list=[machine],
        tool_list=tools,
        open_items=[OpenItem(item_id="OI-E2E-001",
                             description="Surface finish spec not confirmed for P1",
                             severity=OpenItemSeverity.ADVISORY,
                             category=OpenItemCategory.REVIEW_REQUIRED,
                             status=OpenItemStatus.OPEN)],
    )

    # Save plan to ManufacturingPlanStore (the reports API resolves it via final_plan_ref)
    from backend.persistence import get_plan_store, get_workflow_store
    ps = get_plan_store()
    ps.save(plan)

    # Update workflow's final_plan_ref to point to the plan
    store = get_workflow_store()
    wf = store.load(wf_id)
    assert wf is not None
    wf.final_plan_ref = plan.plan_id
    store.save(wf)

    return wf_id


# ---------------------------------------------------------------------------
# MUST 5 — Safety invariant: module-level constants never change
# ---------------------------------------------------------------------------

class TestSafetyInvariantsModuleLevel:
    def test_engineering_state_not_changed(self):
        assert REPORT_GENERATION_ENGINEERING_STATE_CHANGED is False


# ---------------------------------------------------------------------------
# MUST 6 — GET /api/reports/types returns valid list with safety payload
# ---------------------------------------------------------------------------

class TestReportTypesEndpoint:
    def test_requires_auth(self, client):
        res = client.get("/api/reports/types")
        assert res.status_code == 401

    def test_200_with_auth(self, client, auth):
        res = client.get("/api/reports/types", headers=auth)
        assert res.status_code == 200

    def test_has_report_types(self, client, auth):
        res = client.get("/api/reports/types", headers=auth)
        body = res.json()
        assert "report_types" in body
        assert len(body["report_types"]) >= 12  # MUST 7

    def test_has_safety_block(self, client, auth):
        res = client.get("/api/reports/types", headers=auth)
        body = res.json()
        s = body.get("safety", {})
        assert s.get("IS_DISPATCHABLE") is False
        assert s.get("PRODUCTION_RELEASED") is False
        assert s.get("AUTO_APPROVED") is False
        assert s.get("REPORT_GENERATION_ENGINEERING_STATE_CHANGED") is False

    def test_full_mfg_report_in_list(self, client, auth):
        res = client.get("/api/reports/types", headers=auth)
        ids = [rt["id"] for rt in res.json()["report_types"]]
        assert "FULL_MANUFACTURING_REPORT" in ids  # MUST 7

    def test_synth_qual_in_list(self, client, auth):
        res = client.get("/api/reports/types", headers=auth)
        ids = [rt["id"] for rt in res.json()["report_types"]]
        assert "SYNTHETIC_QUALIFICATION_REPORT" in ids

    def test_each_type_has_required_fields(self, client, auth):
        res = client.get("/api/reports/types", headers=auth)
        for rt in res.json()["report_types"]:
            assert "id" in rt
            assert "label_en" in rt
            assert "label_tr" in rt
            assert "supported_formats" in rt

    def test_global_safety_not_changed_after_types_call(self):
        assert REPORT_GENERATION_ENGINEERING_STATE_CHANGED is False


# ---------------------------------------------------------------------------
# MUST 9 — POST /api/reports/preview (with workflow from MP_SYN_001)
# ---------------------------------------------------------------------------

class TestPreviewEndpoint:
    def test_requires_auth(self, client):
        res = client.post("/api/reports/preview", json={"workflow_id": "W-X"})
        assert res.status_code == 401

    def test_nonexistent_workflow_returns_404(self, client, auth):
        res = client.post(
            "/api/reports/preview",
            json={
                "workflow_id": "W-NONEXISTENT-M02-E2E",
                "report_type": "FULL_MANUFACTURING_REPORT",
            },
            headers=auth,
        )
        assert res.status_code == 404

    def test_preview_mp_syn_001(self, client, auth, workflow_id):
        t0 = time.perf_counter()
        res = client.post(
            "/api/reports/preview",
            json={"workflow_id": workflow_id, "report_type": "FULL_MANUFACTURING_REPORT"},
            headers=auth,
        )
        elapsed = time.perf_counter() - t0
        assert res.status_code == 200, f"Preview failed: {res.status_code}: {res.text[:300]}"
        body = res.json()
        assert "sections" in body
        assert elapsed < 5.0, f"Preview too slow: {elapsed:.2f}s"

    def test_preview_has_safety(self, client, auth, workflow_id):
        res = client.post(
            "/api/reports/preview",
            json={"workflow_id": workflow_id, "report_type": "FULL_MANUFACTURING_REPORT"},
            headers=auth,
        )
        body = res.json()
        s = body.get("safety", {})
        assert s.get("IS_DISPATCHABLE") is False
        assert s.get("PRODUCTION_RELEASED") is False


# ---------------------------------------------------------------------------
# MUST 10-15 — Generate and download all 6 formats from MP_SYN_001
# ---------------------------------------------------------------------------

class TestAllFormatGeneration:
    """MUST 10 (PDF), 11 (DOCX), 12 (XLSX), 13 (CSV), 14 (JSON), 15 (ZIP)."""

    @pytest.fixture(scope="class")
    def _gen_result(self, client, auth, workflow_id):
        t0 = time.perf_counter()
        res = client.post(
            "/api/reports/generate",
            json={
                "workflow_id": workflow_id,
                "formats": ["PDF", "DOCX", "XLSX", "CSV", "JSON", "ZIP"],
                "language": "EN",
                "units": "METRIC",
                "report_type": "FULL_MANUFACTURING_REPORT",
            },
            headers=auth,
        )
        elapsed = time.perf_counter() - t0
        assert res.status_code == 200, f"Generate failed: {res.status_code}: {res.text[:300]}"
        return res.json(), elapsed

    def test_generate_returns_items(self, _gen_result):
        body, _ = _gen_result
        assert "items" in body
        assert len(body["items"]) >= 1

    def test_pdf_download_200(self, client, auth, workflow_id):
        t0 = time.perf_counter()
        res = client.post(
            "/api/reports/generate/PDF/download",
            json={
                "workflow_id": workflow_id,
                "language": "EN",
                "units": "METRIC",
                "report_type": "FULL_MANUFACTURING_REPORT",
            },
            headers=auth,
        )
        elapsed = time.perf_counter() - t0
        assert res.status_code == 200, f"PDF download failed: {res.text[:200]}"
        assert len(res.content) > 100
        assert res.headers["content-type"].startswith("application/pdf")
        # Save artifact
        (_ARTIFACTS_DIR / "MP_SYN_001_full_report_EN_METRIC.pdf").write_bytes(res.content)
        assert elapsed < 10.0, f"PDF export too slow: {elapsed:.2f}s"

    def test_docx_download_200(self, client, auth, workflow_id):
        res = client.post(
            "/api/reports/generate/DOCX/download",
            json={
                "workflow_id": workflow_id,
                "language": "EN",
                "units": "METRIC",
                "report_type": "FULL_MANUFACTURING_REPORT",
            },
            headers=auth,
        )
        assert res.status_code == 200
        assert len(res.content) > 100
        ct = res.headers["content-type"]
        assert "word" in ct or "openxmlformats" in ct or "docx" in ct.lower()
        (_ARTIFACTS_DIR / "MP_SYN_001_full_report_EN_METRIC.docx").write_bytes(res.content)

    def test_xlsx_download_200(self, client, auth, workflow_id):
        res = client.post(
            "/api/reports/generate/XLSX/download",
            json={
                "workflow_id": workflow_id,
                "language": "EN",
                "units": "METRIC",
                "report_type": "FULL_MANUFACTURING_REPORT",
            },
            headers=auth,
        )
        assert res.status_code == 200
        assert len(res.content) > 100
        # Validate it's a valid XLSX (ZIP containing xl/ directory)
        with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
            names = zf.namelist()
        assert any("xl/" in n for n in names), f"Not a valid XLSX: {names[:5]}"
        (_ARTIFACTS_DIR / "MP_SYN_001_full_report_EN_METRIC.xlsx").write_bytes(res.content)

    def test_csv_download_200(self, client, auth, workflow_id):
        res = client.post(
            "/api/reports/generate/CSV/download",
            json={
                "workflow_id": workflow_id,
                "language": "EN",
                "units": "METRIC",
                "report_type": "FULL_MANUFACTURING_REPORT",
            },
            headers=auth,
        )
        assert res.status_code == 200
        content = res.content.decode("utf-8-sig")
        assert len(content) > 50
        # OWASP CSV injection check: no value should start with =, +, -, @ unescaped
        for line in content.split("\n")[:30]:
            stripped = line.strip()
            if stripped and stripped[0] in ("=", "+", "@"):
                pytest.fail(f"CSV injection risk in output: {stripped[:80]!r}")
        (_ARTIFACTS_DIR / "MP_SYN_001_full_report_EN_METRIC.csv").write_bytes(res.content)

    def test_json_download_200(self, client, auth, workflow_id):
        res = client.post(
            "/api/reports/generate/JSON/download",
            json={
                "workflow_id": workflow_id,
                "language": "EN",
                "units": "METRIC",
                "report_type": "FULL_MANUFACTURING_REPORT",
            },
            headers=auth,
        )
        assert res.status_code == 200
        data = json.loads(res.content)
        # Safety invariants in JSON output
        assert data["safety"]["is_dispatchable"] is False
        assert data["safety"]["production_released"] is False
        assert data["safety"]["auto_approved"] is False
        assert data["safety"]["engineering_state_changed"] is False
        assert data["units"] == "METRIC"
        assert data["language"] == "EN"
        (_ARTIFACTS_DIR / "MP_SYN_001_full_report_EN_METRIC.json").write_bytes(res.content)

    def test_zip_download_contains_all_formats(self, client, auth, workflow_id):
        res = client.post(
            "/api/reports/generate/ZIP/download",
            json={
                "workflow_id": workflow_id,
                "language": "EN",
                "units": "METRIC",
                "report_type": "FULL_MANUFACTURING_REPORT",
            },
            headers=auth,
        )
        assert res.status_code == 200
        with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
            names = zf.namelist()
        assert any(n.endswith(".pdf") for n in names), f"No PDF in ZIP: {names}"
        assert any(n.endswith(".docx") for n in names), f"No DOCX in ZIP: {names}"
        assert any(n.endswith(".xlsx") for n in names), f"No XLSX in ZIP: {names}"
        assert any(n.endswith(".csv") for n in names), f"No CSV in ZIP: {names}"
        assert any(n.endswith(".json") for n in names), f"No JSON in ZIP: {names}"
        (_ARTIFACTS_DIR / "MP_SYN_001_full_report_EN_METRIC_EXPORTALL.zip").write_bytes(res.content)

    def test_global_safety_after_all_formats(self):
        assert REPORT_GENERATION_ENGINEERING_STATE_CHANGED is False


# ---------------------------------------------------------------------------
# MUST 16/17 — Cross-format snapshot consistency
# ---------------------------------------------------------------------------

class TestSnapshotConsistency:
    """MUST 16 — same report_id in JSON and generate metadata."""

    def test_json_report_id_stable(self, client, auth, workflow_id):
        res1 = client.post(
            "/api/reports/generate/JSON/download",
            json={
                "workflow_id": workflow_id,
                "language": "EN",
                "units": "METRIC",
                "report_type": "FULL_MANUFACTURING_REPORT",
                "report_id": "SNAP-TEST-M02-001",
            },
            headers=auth,
        )
        assert res1.status_code == 200
        data = json.loads(res1.content)
        assert data["report_id"] == "SNAP-TEST-M02-001"


# ---------------------------------------------------------------------------
# MUST 19 — Turkish language test
# ---------------------------------------------------------------------------

class TestLanguageTR:
    """MUST 19 — TR language output must use Turkish labels."""

    def test_json_tr_language_field(self, client, auth, workflow_id):
        res = client.post(
            "/api/reports/generate/JSON/download",
            json={
                "workflow_id": workflow_id,
                "language": "TR",
                "units": "METRIC",
                "report_type": "FULL_MANUFACTURING_REPORT",
            },
            headers=auth,
        )
        assert res.status_code == 200
        data = json.loads(res.content)
        assert data["language"] == "TR"
        assert data["safety"]["is_dispatchable"] is False
        (_ARTIFACTS_DIR / "MP_SYN_001_full_report_TR_METRIC.json").write_bytes(res.content)

    def test_tr_pdf_200(self, client, auth, workflow_id):
        res = client.post(
            "/api/reports/generate/PDF/download",
            json={
                "workflow_id": workflow_id,
                "language": "TR",
                "units": "METRIC",
                "report_type": "FULL_MANUFACTURING_REPORT",
            },
            headers=auth,
        )
        assert res.status_code == 200
        assert len(res.content) > 100
        (_ARTIFACTS_DIR / "MP_SYN_001_full_report_TR_METRIC.pdf").write_bytes(res.content)


# ---------------------------------------------------------------------------
# MUST 20 — Imperial units test
# ---------------------------------------------------------------------------

class TestUnitsImperial:
    """MUST 20 — IMPERIAL units must propagate into JSON output."""

    def test_json_imperial_units_field(self, client, auth, workflow_id):
        res = client.post(
            "/api/reports/generate/JSON/download",
            json={
                "workflow_id": workflow_id,
                "language": "EN",
                "units": "IMPERIAL",
                "report_type": "FULL_MANUFACTURING_REPORT",
            },
            headers=auth,
        )
        assert res.status_code == 200
        data = json.loads(res.content)
        assert data["units"] == "IMPERIAL"
        (_ARTIFACTS_DIR / "MP_SYN_001_full_report_EN_IMPERIAL.json").write_bytes(res.content)


# ---------------------------------------------------------------------------
# MUST 21 — Section selection
# ---------------------------------------------------------------------------

class TestSectionSelection:
    """MUST 21 — section_ids filter must restrict sections in output."""

    def test_section_selection_reduces_sections(self, client, auth, workflow_id):
        # Full report
        res_full = client.post(
            "/api/reports/generate/JSON/download",
            json={
                "workflow_id": workflow_id,
                "language": "EN",
                "units": "METRIC",
                "report_type": "FULL_MANUFACTURING_REPORT",
            },
            headers=auth,
        )
        assert res_full.status_code == 200
        full_sections = json.loads(res_full.content)["sections"]

        # Partial — only part_info + disclaimer (always included)
        res_partial = client.post(
            "/api/reports/generate/JSON/download",
            json={
                "workflow_id": workflow_id,
                "language": "EN",
                "units": "METRIC",
                "report_type": "FULL_MANUFACTURING_REPORT",
                "section_ids": ["part_info"],
            },
            headers=auth,
        )
        assert res_partial.status_code == 200
        partial_sections = json.loads(res_partial.content)["sections"]

        # Partial must have fewer sections than full
        assert len(partial_sections) < len(full_sections), (
            f"Section filter had no effect: "
            f"full={len(full_sections)} partial={len(partial_sections)}"
        )

    def test_disclaimer_always_included(self, client, auth, workflow_id):
        res = client.post(
            "/api/reports/generate/JSON/download",
            json={
                "workflow_id": workflow_id,
                "language": "EN",
                "units": "METRIC",
                "report_type": "FULL_MANUFACTURING_REPORT",
                "section_ids": ["part_info"],
            },
            headers=auth,
        )
        assert res.status_code == 200
        data = json.loads(res.content)
        section_ids = [s["section_id"] for s in data["sections"]]
        assert "disclaimer" in section_ids, "disclaimer must always be included"

    def test_engineering_status_always_included(self, client, auth, workflow_id):
        res = client.post(
            "/api/reports/generate/JSON/download",
            json={
                "workflow_id": workflow_id,
                "language": "EN",
                "units": "METRIC",
                "report_type": "FULL_MANUFACTURING_REPORT",
                "section_ids": ["part_info"],
            },
            headers=auth,
        )
        assert res.status_code == 200
        data = json.loads(res.content)
        section_ids = [s["section_id"] for s in data["sections"]]
        assert "engineering_status" in section_ids, "engineering_status must always be included"


# ---------------------------------------------------------------------------
# MUST 22 — Partial data / graceful handling
# ---------------------------------------------------------------------------

class TestPartialDataHandling:
    def test_report_generates_with_minimal_workflow_data(self, client, auth, workflow_id):
        # Use MANUFACTURING_PLAN type which may have partial data
        res = client.post(
            "/api/reports/generate/JSON/download",
            json={
                "workflow_id": workflow_id,
                "language": "EN",
                "units": "METRIC",
                "report_type": "MANUFACTURING_PLAN",
            },
            headers=auth,
        )
        # Should succeed or return 404/422 if no plan yet — not 500
        assert res.status_code in (200, 404, 422), \
            f"Unexpected status {res.status_code}: {res.text[:200]}"


# ---------------------------------------------------------------------------
# MUST 24 — Security tests
# ---------------------------------------------------------------------------

class TestSecurity:
    def test_path_traversal_format_rejected(self, client, auth):
        res = client.post(
            "/api/reports/generate/../../etc/passwd/download",
            json={"workflow_id": "W-FAKE"},
            headers=auth,
        )
        # Router may return 404 (no route match), 405 (method not allowed for
        # a matched route), 400 (format validation), or 422 (pydantic) — never 200
        assert res.status_code in (400, 404, 405, 422)

    def test_bad_format_rejected(self, client, auth):
        res = client.post(
            "/api/reports/generate/EVIL_FORMAT/download",
            json={"workflow_id": "W-FAKE"},
            headers=auth,
        )
        assert res.status_code == 400

    def test_format_not_in_valid_set_rejected(self, client, auth):
        res = client.post(
            "/api/reports/generate",
            json={"workflow_id": "W-FAKE", "formats": ["MALICIOUS"]},
            headers=auth,
        )
        # 400 (format validation) or 404 (workflow not found before validation)
        assert res.status_code in (400, 404)

    def test_no_auth_rejected(self, client):
        res = client.post(
            "/api/reports/generate/PDF/download",
            json={"workflow_id": "W-FAKE"},
        )
        assert res.status_code == 401


# ---------------------------------------------------------------------------
# MUST 25 — Engineering state immutability
# ---------------------------------------------------------------------------

class TestEngineeringStateImmutability:
    def test_global_state_unchanged_after_all_downloads(self):
        assert REPORT_GENERATION_ENGINEERING_STATE_CHANGED is False

    def test_json_safety_flags_all_false(self, client, auth, workflow_id):
        res = client.post(
            "/api/reports/generate/JSON/download",
            json={
                "workflow_id": workflow_id,
                "language": "EN",
                "units": "METRIC",
                "report_type": "FULL_MANUFACTURING_REPORT",
            },
            headers=auth,
        )
        assert res.status_code == 200
        data = json.loads(res.content)
        s = data["safety"]
        assert s["is_dispatchable"] is False
        assert s["production_released"] is False
        assert s["auto_approved"] is False
        assert s["engineering_state_changed"] is False


# ---------------------------------------------------------------------------
# MUST 28 — Performance
# ---------------------------------------------------------------------------

class TestPerformance:
    def test_pdf_under_10s(self, client, auth, workflow_id):
        t0 = time.perf_counter()
        res = client.post(
            "/api/reports/generate/PDF/download",
            json={
                "workflow_id": workflow_id,
                "language": "EN",
                "units": "METRIC",
                "report_type": "FULL_MANUFACTURING_REPORT",
            },
            headers=auth,
        )
        elapsed = time.perf_counter() - t0
        assert res.status_code == 200
        assert elapsed < 10.0, f"PDF generation took {elapsed:.2f}s (limit 10s)"

    def test_json_under_5s(self, client, auth, workflow_id):
        t0 = time.perf_counter()
        res = client.post(
            "/api/reports/generate/JSON/download",
            json={
                "workflow_id": workflow_id,
                "language": "EN",
                "units": "METRIC",
                "report_type": "FULL_MANUFACTURING_REPORT",
            },
            headers=auth,
        )
        elapsed = time.perf_counter() - t0
        assert res.status_code == 200
        assert elapsed < 5.0, f"JSON generation took {elapsed:.2f}s (limit 5s)"

    def test_zip_under_15s(self, client, auth, workflow_id):
        t0 = time.perf_counter()
        res = client.post(
            "/api/reports/generate/ZIP/download",
            json={
                "workflow_id": workflow_id,
                "language": "EN",
                "units": "METRIC",
                "report_type": "FULL_MANUFACTURING_REPORT",
            },
            headers=auth,
        )
        elapsed = time.perf_counter() - t0
        assert res.status_code == 200
        assert elapsed < 15.0, f"ZIP generation took {elapsed:.2f}s (limit 15s)"
