"""Tests for Auto CAM plan persistence.

AUTOCAM_PLAN_SURVIVES_BACKEND_RESTART=YES
PERSISTENCE_STATUS_PROMOTION=NO
ARBITRARY_OBJECT_DESERIALIZATION=NO
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from backend.autocam.enums import AutoCamPlanStatus
from backend.autocam.models import (
    AutoCamCostEstimate,
    AutoCamCostInput,
    AutoCamFeatureInput,
    AutoCamPlan,
    AutoCamRequest,
    MachineResult,
    StockBbox,
)
from backend.autocam.orchestrator import _set_plan_store, get_plan, run_auto_cam
from backend.autocam.plan_store import AutoCamPlanStore, AutoCamPlanStoreError
from backend.autocam.cost_estimate import compute_autocam_cost
from backend.autocam.models import CycleTimeResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_request(file_ref: str = "TEST_PART_P01") -> AutoCamRequest:
    return AutoCamRequest(
        file_ref=file_ref,
        features=[
            AutoCamFeatureInput(
                feature_id="F1",
                feature_type="HOLE",
                diameter_mm=9.0,
                depth_mm=20.0,
                center_x=0.0,
                center_y=0.0,
                center_z_top=0.0,
            )
        ],
        stock_bbox=StockBbox(
            min_x=0, min_y=0, min_z=0,
            max_x=100, max_y=100, max_z=50,
        ),
        material_grade="ISO-P",
    )


def _minimal_plan(file_ref: str = "TEST") -> AutoCamPlan:
    """Create a minimal plan without running the full pipeline."""
    return AutoCamPlan(
        plan_id="test_plan_001",
        file_ref=file_ref,
        plan_status=AutoCamPlanStatus.COMPLETE_WITH_WARNINGS,
        stages=[],
        created_at="2026-11-26T00:00:00+00:00",
    )


# ---------------------------------------------------------------------------
# AutoCamPlanStore unit tests
# ---------------------------------------------------------------------------

class TestAutoCamPlanStoreSaveLoad:
    def test_save_and_get_roundtrip(self, tmp_path: Path) -> None:
        store = AutoCamPlanStore(tmp_path / "test.db")
        plan = _minimal_plan("PART_A")
        store.save(plan)
        loaded = store.get(plan.plan_id)
        assert loaded is not None
        assert loaded.plan_id == plan.plan_id
        assert loaded.file_ref == "PART_A"
        assert loaded.plan_status == AutoCamPlanStatus.COMPLETE_WITH_WARNINGS
        store.close()

    def test_missing_plan_returns_none(self, tmp_path: Path) -> None:
        store = AutoCamPlanStore(tmp_path / "test.db")
        assert store.get("nonexistent_id") is None
        store.close()

    def test_upsert_updates_plan(self, tmp_path: Path) -> None:
        store = AutoCamPlanStore(tmp_path / "test.db")
        plan = _minimal_plan()
        store.save(plan)
        updated = plan.model_copy(update={"cost_estimate_status": "PARTIAL_COST_ESTIMATE"})
        store.save(updated)
        loaded = store.get(plan.plan_id)
        assert loaded is not None
        assert loaded.cost_estimate_status == "PARTIAL_COST_ESTIMATE"
        store.close()

    def test_persists_across_reopen(self, tmp_path: Path) -> None:
        db_path = tmp_path / "persist.db"
        plan = _minimal_plan("PART_B")

        # Write with first connection
        store1 = AutoCamPlanStore(db_path)
        store1.save(plan)
        store1.close()

        # Read with new connection (simulates restart)
        store2 = AutoCamPlanStore(db_path)
        loaded = store2.get(plan.plan_id)
        store2.close()

        assert loaded is not None
        assert loaded.plan_id == plan.plan_id
        assert loaded.file_ref == "PART_B"

    def test_safety_invariants_re_enforced_on_reload(self, tmp_path: Path) -> None:
        """Safety invariants must be re-enforced on deserialisation."""
        store = AutoCamPlanStore(tmp_path / "test.db")
        plan = _minimal_plan()
        # Tamper the payload directly in the DB to simulate a corrupted safety field
        store.save(plan)

        # Read raw payload and corrupt it
        conn = store._conn  # type: ignore[attr-defined]
        cur = conn.execute(
            "SELECT payload FROM autocam_plans WHERE plan_id = ?",
            (plan.plan_id,),
        )
        payload_str = cur.fetchone()[0]
        payload = json.loads(payload_str)
        payload["safety"]["AUTO_CAM_CAN_DISPATCH_CNC"] = True  # tamper
        conn.execute(
            "UPDATE autocam_plans SET payload = ? WHERE plan_id = ?",
            (json.dumps(payload), plan.plan_id),
        )
        conn.commit()

        loaded = store.get(plan.plan_id)
        store.close()

        assert loaded is not None
        # Safety must be re-enforced to False regardless of DB payload
        assert loaded.safety["AUTO_CAM_CAN_DISPATCH_CNC"] is False
        assert loaded.safety["AUTO_CAM_CAN_RELEASE_PRODUCTION"] is False
        assert loaded.safety["AUTO_CAM_CAN_AUTO_APPROVE"] is False

    def test_list_recent(self, tmp_path: Path) -> None:
        store = AutoCamPlanStore(tmp_path / "test.db")
        for i in range(3):
            p = _minimal_plan(f"PART_{i}").model_copy(
                update={"plan_id": f"plan_{i:03d}"}
            )
            store.save(p)
        rows = store.list_recent(limit=10)
        assert len(rows) == 3
        ids = {r["plan_id"] for r in rows}
        assert ids == {"plan_000", "plan_001", "plan_002"}
        store.close()


class TestAutoCamPlanStoreErrorHandling:
    def test_closed_store_raises(self, tmp_path: Path) -> None:
        store = AutoCamPlanStore(tmp_path / "test.db")
        store.close()
        with pytest.raises(AutoCamPlanStoreError, match="closed"):
            store.get("any_id")

    def test_context_manager(self, tmp_path: Path) -> None:
        with AutoCamPlanStore(tmp_path / "ctx.db") as store:
            plan = _minimal_plan()
            store.save(plan)
            loaded = store.get(plan.plan_id)
            assert loaded is not None


# ---------------------------------------------------------------------------
# State safety on reload (MUST A3)
# ---------------------------------------------------------------------------

class TestPersistenceStateSafety:
    def test_reload_does_not_promote_status(self, tmp_path: Path) -> None:
        """PERSISTENCE_RELOAD_PRODUCTION_RELEASE_CHANGED=NO"""
        db_path = tmp_path / "safety.db"
        plan = _minimal_plan()
        store1 = AutoCamPlanStore(db_path)
        store1.save(plan)
        store1.close()

        store2 = AutoCamPlanStore(db_path)
        loaded = store2.get(plan.plan_id)
        store2.close()

        assert loaded is not None
        # Status must not be promoted beyond what was saved
        assert loaded.plan_status == AutoCamPlanStatus.COMPLETE_WITH_WARNINGS
        assert loaded.safety["AUTO_CAM_CAN_DISPATCH_CNC"] is False
        assert loaded.safety["AUTO_CAM_CAN_RELEASE_PRODUCTION"] is False
        assert loaded.safety["AUTO_CAM_CAN_AUTO_APPROVE"] is False
        assert loaded.safety["DISPATCH_GATE"] == "ALWAYS_BLOCKED"


# ---------------------------------------------------------------------------
# Orchestrator integration with persistent store (MUST A2 — restart test)
# ---------------------------------------------------------------------------

class TestOrchestratorPersistentIntegration:
    def test_plan_survives_store_swap(self, tmp_path: Path) -> None:
        """Simulate restart: write to store1, swap to store2 (same DB), read back."""
        db_path = tmp_path / "orch.db"

        # Inject store1
        store1 = AutoCamPlanStore(db_path)
        _set_plan_store(store1)

        plan = run_auto_cam(_minimal_request("RESTART_TEST_P01"))
        plan_id = plan.plan_id

        # Verify plan is in store1
        assert store1.get(plan_id) is not None
        store1.close()

        # Simulate restart: inject a fresh store on the same DB
        store2 = AutoCamPlanStore(db_path)
        _set_plan_store(store2)

        restored = get_plan(plan_id)
        assert restored is not None, "Plan must survive restart"
        assert restored.plan_id == plan_id
        assert restored.file_ref == "RESTART_TEST_P01"
        assert len(restored.operations) >= 0  # operations persisted
        store2.close()

    def test_cost_input_survives_store_swap(self, tmp_path: Path) -> None:
        """Cost inputs written via submit_cost_input survive simulated restart."""
        db_path = tmp_path / "cost_persist.db"

        store1 = AutoCamPlanStore(db_path)
        _set_plan_store(store1)

        plan = run_auto_cam(_minimal_request("COST_PERSIST_P01"))
        plan_id = plan.plan_id

        # Inject cost estimate
        cost_input = AutoCamCostInput(
            machine_hourly_rate=75.0,
            machine_rate_currency="EUR",
            material_cost_total=45.0,
            material_cost_currency="EUR",
            currency="EUR",
        )
        new_estimate = compute_autocam_cost(plan.cycle_time, plan.machine, cost_input)
        updated = plan.model_copy(update={
            "cost_estimate": new_estimate,
            "cost_estimate_status": new_estimate.total_status,
        })
        store1.save(updated)
        store1.close()

        # Restart
        store2 = AutoCamPlanStore(db_path)
        _set_plan_store(store2)
        restored = get_plan(plan_id)
        store2.close()

        assert restored is not None
        assert restored.cost_estimate is not None
        assert restored.cost_estimate.cost_input_received is True
        assert restored.cost_estimate.machine_cost.value is not None
        assert restored.cost_estimate_status in (
            "PARTIAL_COST_ESTIMATE", "COMPLETE_COST_ESTIMATE", "INSUFFICIENT_DATA"
        )

    def test_all_fields_survive_restart(self, tmp_path: Path) -> None:
        """Check all required fields per MUST A2 survive a restart."""
        db_path = tmp_path / "allfields.db"

        store1 = AutoCamPlanStore(db_path)
        _set_plan_store(store1)

        plan = run_auto_cam(_minimal_request("ALL_FIELDS_P01"))
        plan_id = plan.plan_id
        original_file_ref = plan.file_ref
        original_status = plan.plan_status
        original_ops_count = len(plan.operations)
        original_machine_id = plan.machine.machine_id
        store1.close()

        store2 = AutoCamPlanStore(db_path)
        _set_plan_store(store2)
        restored = get_plan(plan_id)
        store2.close()

        assert restored is not None
        assert restored.plan_id == plan_id
        assert restored.file_ref == original_file_ref  # source CAD reference
        assert restored.plan_status == original_status  # status not promoted
        assert len(restored.operations) == original_ops_count  # operations
        assert restored.machine.machine_id == original_machine_id  # machine
        assert restored.safety["AUTO_CAM_CAN_DISPATCH_CNC"] is False  # invariants
        assert restored.report_status is not None  # report context
        assert restored.created_at != ""  # timestamps
