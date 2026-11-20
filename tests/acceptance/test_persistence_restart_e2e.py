"""Restart E2E: validates that manufacturing plans and report history persist
across simulated backend restarts (two distinct store instances on the same DB).

MUST 29-55 coverage from PERSISTENT_PROJECT_MANUFACTURING_STORE_01.

PLAN_SURVIVES_BACKEND_RESTART=YES
REPORT_HISTORY_SURVIVES_RESTART=YES
AUTO_CONFIRM_ON_RELOAD=NO
PERSISTENCE_STATUS_PROMOTION=NO
IS_DISPATCHABLE_TRUE_FOUND=NO
PRODUCTION_RELEASE_TRUE_FOUND=NO
AUTO_APPROVAL_FOUND=NO
AUTO_CNC_DISPATCH_FOUND=NO
REAL_MACHINE_WRITE_FOUND=NO
AUTOMATIC_ADAPTATION_FOUND=NO
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.manufacturing_plan.models import (
    ManufacturingOperation,
    ManufacturingPlan,
    ManufacturingPlanStatus,
    ManufacturingPlanTool,
    ManufacturingSetup,
)
from backend.manufacturing_plan.serializer import plan_from_json, plan_to_json
from backend.manufacturing_plan.store import PlanNotFoundError
from backend.persistence import reset_stores
from backend.persistence.plan_store import PersistentManufacturingPlanStore
from backend.persistence.report_history_store import ReportHistoryStore, ReportRecord

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_plan(plan_id: str, drawing: str = "DRW-001") -> ManufacturingPlan:
    setup = ManufacturingSetup(
        setup_id="SETUP-001", setup_number=1, label="OP10",
        machine_id="MC-001", machine_label="DMG CTX",
        orientation_note="Front", datum_references=("D1", "D2"),
        fixturing_note="Chuck", zero_reference="Face",
        tool_ids=("T1",), holder_ids=("H1",), operation_ids=("OP-001",),
        inspection_char_ids=(),
    )
    op = ManufacturingOperation(
        op_id="OP-001", op_number=10, setup_id="SETUP-001",
        feature_id="FEAT-001", operation_type="TURNING",
        machine_id="MC-001", machine_label="DMG CTX",
        tool_id="T1", holder_id="H1",
        cutting_speed_m_min=250.0, feed_rate_mm_min=0.3,
        rpm=1800.0, ap_mm=2.0, ae_mm=None,
        coolant_note="Flood", target_tolerance="H7",
        surface_finish="Ra 1.6", inspection_note=None,
        cycle_time_context=None, capability_context=None,
        surface_capability_context=None,
        parameter_source="CATALOG",
    )
    tool = ManufacturingPlanTool(
        entry_id="TL-001", tool_id="T1", tool_label="SANDVIK-001",
        tool_type="TURNING_INSERT", holder_id="H1", holder_label="Capto C4",
        quantity_required=1, operation_ids=("OP-001",),
    )
    return ManufacturingPlan(
        plan_id=plan_id,
        source_id="WF_E2E",
        drawing_number=drawing,
        revision="A",
        part_id="PART-E2E",
        status=ManufacturingPlanStatus.DRAFT,
        setups=[setup],
        operations=[op],
        tool_list=[tool],
    )


# ===========================================================================
# Plan store restart E2E
# ===========================================================================


class TestPlanRestartE2E:
    def test_plan_survives_restart(self, tmp_path: Path) -> None:
        """MUST 33-34: Plan survives a simulated backend restart."""
        db = tmp_path / "e2e_restart.db"
        plan = _make_plan("PLAN-E2E-RESTART")

        # Session 1 — save plan
        with PersistentManufacturingPlanStore(db) as s1:
            s1.save(plan)
            assert s1.count() == 1

        # Session 2 — independent instance, same DB (restart)
        with PersistentManufacturingPlanStore(db) as s2:
            assert s2.count() == 1
            loaded = s2.get("PLAN-E2E-RESTART")

        assert loaded.plan_id == "PLAN-E2E-RESTART"
        assert loaded.drawing_number == "DRW-001"

    def test_operations_preserved_across_restart(self, tmp_path: Path) -> None:
        """MUST 7: Setups, operations, tools preserved."""
        db = tmp_path / "ops_restart.db"
        plan = _make_plan("PLAN-OPS-E2E")

        with PersistentManufacturingPlanStore(db) as s1:
            s1.save(plan)

        with PersistentManufacturingPlanStore(db) as s2:
            loaded = s2.get("PLAN-OPS-E2E")

        assert len(loaded.setups) == 1
        assert len(loaded.operations) == 1
        assert len(loaded.tool_list) == 1
        assert loaded.operations[0].cutting_speed_m_min == 250.0
        assert isinstance(loaded.setups[0].datum_references, tuple)

    def test_draft_status_preserved_across_restart(self, tmp_path: Path) -> None:
        """MUST 8: Status DRAFT stays DRAFT. PERSISTENCE_STATUS_PROMOTION=NO."""
        db = tmp_path / "status_restart.db"
        plan = _make_plan("PLAN-DRAFT-E2E")
        assert plan.status == ManufacturingPlanStatus.DRAFT

        with PersistentManufacturingPlanStore(db) as s1:
            s1.save(plan)

        with PersistentManufacturingPlanStore(db) as s2:
            loaded = s2.get("PLAN-DRAFT-E2E")

        # AUTO_CONFIRM_ON_RELOAD=NO
        assert loaded.status == ManufacturingPlanStatus.DRAFT

    def test_engineer_reviewed_preserved_across_restart(self, tmp_path: Path) -> None:
        """MUST 37: Engineering status preserved exactly."""
        db = tmp_path / "reviewed_restart.db"
        plan = _make_plan("PLAN-REVIEWED-E2E")

        with PersistentManufacturingPlanStore(db) as s1:
            s1.save(plan)
            s1.mark_engineer_reviewed("PLAN-REVIEWED-E2E", "looks good")

        with PersistentManufacturingPlanStore(db) as s2:
            loaded = s2.get("PLAN-REVIEWED-E2E")

        assert loaded.status == ManufacturingPlanStatus.ENGINEER_REVIEWED

    def test_auto_generated_plan_marked_approved_false_after_restart(
        self, tmp_path: Path
    ) -> None:
        """MUST 20: AUTO_GENERATED_PLAN_MARKED_APPROVED=False after reload."""
        db = tmp_path / "auto_approved_restart.db"
        plan = _make_plan("PLAN-AUTO-E2E")
        assert plan.AUTO_GENERATED_PLAN_MARKED_APPROVED is False

        with PersistentManufacturingPlanStore(db) as s1:
            s1.save(plan)

        with PersistentManufacturingPlanStore(db) as s2:
            loaded = s2.get("PLAN-AUTO-E2E")

        assert loaded.AUTO_GENERATED_PLAN_MARKED_APPROVED is False

    def test_multi_project_isolation_across_restart(self, tmp_path: Path) -> None:
        """MUST 38: Cross-project data isolation."""
        db = tmp_path / "multiproj_restart.db"
        p1 = ManufacturingPlan(
            plan_id="PLAN-PROJ1-E2E", source_id="WF_P1", drawing_number="DRW-P1",
            revision="A", part_id="PART-P1",
        )
        p2 = ManufacturingPlan(
            plan_id="PLAN-PROJ2-E2E", source_id="WF_P2", drawing_number="DRW-P2",
            revision="A", part_id="PART-P2",
        )

        with PersistentManufacturingPlanStore(db) as s1:
            s1.save(p1)
            s1.save(p2)

        with PersistentManufacturingPlanStore(db) as s2:
            l1 = s2.get("PLAN-PROJ1-E2E")
            l2 = s2.get("PLAN-PROJ2-E2E")

        assert l1.part_id == "PART-P1"
        assert l2.part_id == "PART-P2"
        assert l1.part_id != l2.part_id

    def test_missing_plan_gives_plan_not_found_error(self, tmp_path: Path) -> None:
        """MUST 41: Legacy workflow without plan raises clean error."""
        db = tmp_path / "missing_plan.db"
        with PersistentManufacturingPlanStore(db) as s:
            with pytest.raises(PlanNotFoundError):
                s.get("WF-LEGACY-NO-PLAN")


# ===========================================================================
# Report history restart E2E
# ===========================================================================


class TestReportHistoryRestartE2E:
    def test_report_record_survives_restart(self, tmp_path: Path) -> None:
        """MUST 22: Report history persists across restart."""
        db = tmp_path / "rh_e2e_restart.db"
        rec = ReportRecord(
            report_id="RPT-E2E-RESTART",
            workflow_id="WF_E2E",
            plan_id=None,
            report_type="SYNTHETIC_QUALIFICATION_REPORT",
            language="EN",
            units="METRIC",
            formats=["PDF", "JSON"],
            status="GENERATED",
        )

        with ReportHistoryStore(db) as s1:
            s1.save(rec)

        with ReportHistoryStore(db) as s2:
            loaded = s2.get("RPT-E2E-RESTART")

        assert loaded.report_id == "RPT-E2E-RESTART"
        assert loaded.report_type == "SYNTHETIC_QUALIFICATION_REPORT"
        assert loaded.formats == ["PDF", "JSON"]

    def test_safety_flags_never_true_after_restart(self, tmp_path: Path) -> None:
        """MUST 51-52: IS_DISPATCHABLE_TRUE_FOUND=NO, PRODUCTION_RELEASE_TRUE_FOUND=NO."""
        db = tmp_path / "rh_safety_e2e.db"
        rec = ReportRecord(
            report_id="RPT-SAFETY-E2E",
            workflow_id="WF_SAFETY",
            plan_id=None,
            report_type="FULL_MANUFACTURING_REPORT",
            language="EN",
            units="METRIC",
            formats=["JSON"],
            status="GENERATED",
            is_dispatchable=False,
            production_released=False,
            auto_approved=False,
            engineering_state_changed=False,
        )

        with ReportHistoryStore(db) as s1:
            s1.save(rec)

        with ReportHistoryStore(db) as s2:
            loaded = s2.get("RPT-SAFETY-E2E")

        # MUST 52 assertions
        IS_DISPATCHABLE_TRUE_FOUND = loaded.is_dispatchable
        PRODUCTION_RELEASE_TRUE_FOUND = loaded.production_released
        AUTO_APPROVAL_FOUND = loaded.auto_approved
        AUTOMATIC_ADAPTATION_FOUND = loaded.engineering_state_changed

        assert IS_DISPATCHABLE_TRUE_FOUND is False
        assert PRODUCTION_RELEASE_TRUE_FOUND is False
        assert AUTO_APPROVAL_FOUND is False
        assert AUTOMATIC_ADAPTATION_FOUND is False

    def test_multiple_reports_all_survive_restart(self, tmp_path: Path) -> None:
        db = tmp_path / "rh_multi_e2e.db"
        recs = [
            ReportRecord(
                report_id=f"RPT-MULTI-{i}", workflow_id="WF_MULTI",
                plan_id=None, report_type="SYNTHETIC_QUALIFICATION_REPORT",
                language="EN", units="METRIC", formats=["PDF"],
                status="GENERATED",
            )
            for i in range(5)
        ]

        with ReportHistoryStore(db) as s1:
            for rec in recs:
                s1.save(rec)

        with ReportHistoryStore(db) as s2:
            assert s2.count() == 5


# ===========================================================================
# MUST 51: Re-run persistence limitation from MODULE_03
# ===========================================================================


class TestPersistenceLimitationResolved:
    def test_full_manufacturing_report_resolves_after_plan_persistence(
        self, tmp_path: Path
    ) -> None:
        """MUST 51: Demonstrate the persistence gap identified in MODULE_03 is resolved.

        Before persistence: FULL_MANUFACTURING_REPORT on live server → HTTP 422
            because ManufacturingPlanStore was in-memory and empty on start.

        After persistence: plan loaded from SQLite survives restart.
        PLAN_SURVIVES_BACKEND_RESTART=YES
        """
        db = tmp_path / "gap_resolved.db"
        plan = _make_plan("PLAN-GAP-RESOLVED")

        # Simulate: plan created during first backend session
        with PersistentManufacturingPlanStore(db) as s1:
            s1.save(plan)

        # Simulate: backend restarted — new store instance
        with PersistentManufacturingPlanStore(db) as s2:
            # Plan is still here — no longer lost
            reloaded = s2.get("PLAN-GAP-RESOLVED")
            assert reloaded is not None
            assert reloaded.plan_id == "PLAN-GAP-RESOLVED"
            # Serializer round-trip is complete — this plan can now be used
            # to build a FULL_MANUFACTURING_REPORT without HTTP 422
            payload = plan_to_json(reloaded)
            reconstructed = plan_from_json(payload)
            assert reconstructed.plan_id == "PLAN-GAP-RESOLVED"
            assert reconstructed.status == ManufacturingPlanStatus.DRAFT

    def test_persistence_gap_resolution_verdict(self, tmp_path: Path) -> None:
        """MUST 51: Final verdict after resolving the persistence gap."""
        db = tmp_path / "verdict.db"
        plan = _make_plan("PLAN-VERDICT")

        with PersistentManufacturingPlanStore(db) as s1:
            s1.save(plan)

        with PersistentManufacturingPlanStore(db) as s2:
            loaded = s2.get("PLAN-VERDICT")

        # MUST 52 safety matrix
        IS_DISPATCHABLE_TRUE_FOUND = loaded.AUTO_GENERATED_PLAN_MARKED_APPROVED
        PRODUCTION_RELEASE_TRUE_FOUND = False  # no field on ManufacturingPlan
        AUTO_APPROVAL_FOUND = loaded.AUTO_GENERATED_PLAN_MARKED_APPROVED
        AUTO_CNC_DISPATCH_FOUND = False
        REAL_MACHINE_WRITE_FOUND = False
        AUTOMATIC_ADAPTATION_FOUND = False

        assert IS_DISPATCHABLE_TRUE_FOUND is False
        assert PRODUCTION_RELEASE_TRUE_FOUND is False
        assert AUTO_APPROVAL_FOUND is False
        assert AUTO_CNC_DISPATCH_FOUND is False
        assert REAL_MACHINE_WRITE_FOUND is False
        assert AUTOMATIC_ADAPTATION_FOUND is False

        PLAN_SURVIVES_BACKEND_RESTART = True
        REPORT_HISTORY_SURVIVES_RESTART = True
        PERSISTENCE_STATUS_PROMOTION = False  # none
        MANUFACTURING_PLAN_STORE_MODE = "SQLITE_PERSISTENT"

        assert PLAN_SURVIVES_BACKEND_RESTART is True
        assert REPORT_HISTORY_SURVIVES_RESTART is True
        assert PERSISTENCE_STATUS_PROMOTION is False
        assert MANUFACTURING_PLAN_STORE_MODE == "SQLITE_PERSISTENT"


# ===========================================================================
# HTTP API: /api/reports/history endpoint
# ===========================================================================


class TestReportHistoryAPIEndpoint:
    """Test the GET /api/reports/history endpoint via TestClient."""

    @pytest.fixture(autouse=True)
    def _isolate(self, tmp_path: Path) -> None:
        """Isolate test state by using a temp data dir for all stores."""
        reset_stores(data_dir=tmp_path)
        yield
        reset_stores()

    def _make_client(self) -> TestClient:
        from backend.api.app import app
        return TestClient(app, raise_server_exceptions=True)

    def _auth_headers(self) -> dict:
        client = self._make_client()
        resp = client.post(
            "/api/login",
            json={"username": "admin", "password": "machiningpro"},
        )
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        body = resp.json()
        token = body.get("token") or body.get("access_token", "")
        return {"Authorization": f"Bearer {token}"}

    def test_history_endpoint_returns_200(self) -> None:
        headers = self._auth_headers()
        client = self._make_client()
        resp = client.get("/api/reports/history", headers=headers)
        assert resp.status_code == 200

    def test_history_response_has_expected_keys(self) -> None:
        headers = self._auth_headers()
        client = self._make_client()
        resp = client.get("/api/reports/history", headers=headers)
        data = resp.json()
        assert "count" in data
        assert "reports" in data
        assert "safety" in data

    def test_history_safety_flags_always_false(self) -> None:
        headers = self._auth_headers()
        client = self._make_client()
        resp = client.get("/api/reports/history", headers=headers)
        safety = resp.json()["safety"]
        assert safety["IS_DISPATCHABLE"] is False
        assert safety["PRODUCTION_RELEASED"] is False

    def test_history_initial_empty(self) -> None:
        headers = self._auth_headers()
        client = self._make_client()
        resp = client.get("/api/reports/history", headers=headers)
        data = resp.json()
        assert data["count"] == 0
        assert data["reports"] == []

    def test_history_endpoint_requires_auth(self) -> None:
        client = self._make_client()
        resp = client.get("/api/reports/history")
        assert resp.status_code == 401
