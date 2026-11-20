"""Tests for PersistentManufacturingPlanStore and ManufacturingPlan serializer.

Covers MUST 6-18, 29-32, 36-40, 42-45 from PERSISTENT_PROJECT_MANUFACTURING_STORE_01.

PERSISTENCE_STATUS_PROMOTION=NO
AUTO_CONFIRM_ON_RELOAD=NO
AUTO_APPROVE_ON_RELOAD=NO
IS_DISPATCHABLE=False always
PRODUCTION_RELEASED=False always
"""
from __future__ import annotations

import threading
from pathlib import Path

import pytest

from backend.manufacturing_plan.models import (
    ManufacturingOperation,
    ManufacturingPlan,
    ManufacturingPlanMachine,
    ManufacturingPlanStatus,
    ManufacturingPlanTool,
    ManufacturingSetup,
    OpenItem,
    OpenItemCategory,
    OpenItemSeverity,
    PFMEAHook,
    ProcessFlow,
    ProcessFlowNode,
)
from backend.manufacturing_plan.serializer import plan_from_json, plan_to_json
from backend.manufacturing_plan.store import PlanApprovalError, PlanNotFoundError
from backend.persistence.plan_store import PersistentManufacturingPlanStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "plans.db"


@pytest.fixture
def store(db_path: Path) -> PersistentManufacturingPlanStore:
    with PersistentManufacturingPlanStore(db_path) as s:
        yield s


def _minimal_plan(
    plan_id: str = "PLAN-001",
    drawing_number: str | None = "DRW-001",
    part_id: str | None = "PART-001",
    source_id: str = "WF_test",
    status: ManufacturingPlanStatus = ManufacturingPlanStatus.DRAFT,
) -> ManufacturingPlan:
    return ManufacturingPlan(
        plan_id=plan_id,
        source_id=source_id,
        drawing_number=drawing_number,
        revision="A",
        part_id=part_id,
        status=status,
    )


def _rich_plan(plan_id: str = "PLAN-RICH-001") -> ManufacturingPlan:
    setup = ManufacturingSetup(
        setup_id="SETUP-001",
        setup_number=1,
        label="OP10",
        machine_id="MC-001",
        machine_label="DMG CTX",
        orientation_note="Front face",
        datum_references=("D1", "D2"),
        fixturing_note="3-jaw chuck",
        zero_reference="Part face",
        tool_ids=("T1",),
        holder_ids=("H1",),
        operation_ids=("OP-001",),
        inspection_char_ids=(),
    )
    op = ManufacturingOperation(
        op_id="OP-001",
        op_number=10,
        setup_id="SETUP-001",
        feature_id="FEAT-001",
        operation_type="TURNING",
        machine_id="MC-001",
        machine_label="DMG CTX",
        tool_id="T1",
        holder_id="H1",
        cutting_speed_m_min=250.0,
        feed_rate_mm_min=0.3,
        rpm=1800.0,
        ap_mm=2.0,
        ae_mm=None,
        coolant_note="Flood",
        target_tolerance="H7",
        surface_finish="Ra 1.6",
        inspection_note=None,
        cycle_time_context=None,
        capability_context=None,
        surface_capability_context=None,
        parameter_source="CATALOG",
    )
    tool = ManufacturingPlanTool(
        entry_id="TL-001",
        tool_id="T1",
        tool_label="SANDVIK-TURNING",
        tool_type="TURNING_INSERT",
        holder_id="H1",
        holder_label="Capto C4",
        quantity_required=1,
        operation_ids=("OP-001",),
    )
    machine = ManufacturingPlanMachine(
        entry_id="ME-001",
        machine_id="MC-001",
        machine_label="DMG CTX",
        machine_type="TURNING_CENTER",
        setup_ids=("SETUP-001",),
        operation_ids=("OP-001",),
    )
    open_item = OpenItem(
        item_id="OI-001",
        category=OpenItemCategory.MISSING_PARAMETER,
        severity=OpenItemSeverity.ADVISORY,
        description="Feed rate not catalog-verified",
    )
    pfmea = PFMEAHook(
        feature_id="FEAT-001",
        op_id="OP-001",
        failure_mode_hint="Dimensional deviation",
        control="CMM inspection",
        severity_hint="MEDIUM",
    )
    process_flow = ProcessFlow(
        flow_id="PF-001",
        nodes=[ProcessFlowNode(
            node_id="PFN-001", node_type="OPERATION", label="OP10",
            setup_id="SETUP-001", op_id="OP-001",
        )],
        edges=[("PFN-001", "PFN-END")],
        start_node_id="PFN-001",
        end_node_id="PFN-END",
    )
    return ManufacturingPlan(
        plan_id=plan_id,
        source_id="WF_rich",
        drawing_number="DRW-RICH",
        revision="B",
        part_id="PART-RICH",
        status=ManufacturingPlanStatus.DRAFT,
        setups=[setup],
        operations=[op],
        tool_list=[tool],
        machine_list=[machine],
        open_items=[open_item],
        pfmea_hooks=[pfmea],
        process_flow=process_flow,
        generation_warnings=["WARN: incomplete catalog"],
    )


# ===========================================================================
# MUST 29/30: Repository persistence — existing SQLite pattern
# ===========================================================================


class TestPersistentPlanStoreBasic:
    def test_save_and_get(self, store: PersistentManufacturingPlanStore) -> None:
        plan = _minimal_plan()
        saved = store.save(plan)
        loaded = store.get(saved.plan_id)
        assert loaded.plan_id == plan.plan_id

    def test_get_not_found_raises(self, store: PersistentManufacturingPlanStore) -> None:
        with pytest.raises(PlanNotFoundError):
            store.get("PLAN-NONEXISTENT")

    def test_count_empty(self, store: PersistentManufacturingPlanStore) -> None:
        assert store.count() == 0

    def test_count_after_save(self, store: PersistentManufacturingPlanStore) -> None:
        store.save(_minimal_plan("P1"))
        store.save(_minimal_plan("P2"))
        assert store.count() == 2

    def test_list_all(self, store: PersistentManufacturingPlanStore) -> None:
        store.save(_minimal_plan("PA"))
        store.save(_minimal_plan("PB"))
        plans = store.list_all()
        ids = {p.plan_id for p in plans}
        assert {"PA", "PB"} <= ids

    def test_list_summary(self, store: PersistentManufacturingPlanStore) -> None:
        store.save(_minimal_plan("PS1"))
        rows = store.list_summary()
        assert any(r["plan_id"] == "PS1" for r in rows)

    def test_delete(self, store: PersistentManufacturingPlanStore) -> None:
        store.save(_minimal_plan("PDEL"))
        store.delete("PDEL")
        with pytest.raises(PlanNotFoundError):
            store.get("PDEL")

    def test_delete_not_found_raises(self, store: PersistentManufacturingPlanStore) -> None:
        with pytest.raises(PlanNotFoundError):
            store.delete("PLAN-MISSING")

    def test_upsert_updates(self, store: PersistentManufacturingPlanStore) -> None:
        store.save(_minimal_plan("PUPDATE", drawing_number="DRW-V1"))
        store.save(_minimal_plan("PUPDATE", drawing_number="DRW-V2"))
        loaded = store.get("PUPDATE")
        assert loaded.drawing_number == "DRW-V2"
        assert store.count() == 1

    def test_is_healthy(self, store: PersistentManufacturingPlanStore) -> None:
        assert store.is_healthy()

    def test_find_by_drawing(self, store: PersistentManufacturingPlanStore) -> None:
        store.save(_minimal_plan("PFD1", drawing_number="DRW-XYZ"))
        store.save(_minimal_plan("PFD2", drawing_number="DRW-XYZ"))
        store.save(_minimal_plan("PFD3", drawing_number="DRW-OTHER"))
        results = store.find_by_drawing("DRW-XYZ")
        assert len(results) == 2
        assert all(p.drawing_number == "DRW-XYZ" for p in results)

    def test_find_by_source(self, store: PersistentManufacturingPlanStore) -> None:
        store.save(_minimal_plan("PFS1", source_id="WF_SRC1"))
        store.save(_minimal_plan("PFS2", source_id="WF_SRC1"))
        store.save(_minimal_plan("PFS3", source_id="WF_SRC2"))
        results = store.find_by_source("WF_SRC1")
        assert len(results) == 2


# ===========================================================================
# MUST 6-7: ManufacturingPlan persistence and feature/WCS preservation
# ===========================================================================


class TestPlanFieldPreservation:
    def test_full_rich_plan_round_trip(self, store: PersistentManufacturingPlanStore) -> None:
        plan = _rich_plan()
        store.save(plan)
        loaded = store.get(plan.plan_id)
        assert loaded.plan_id == plan.plan_id
        assert len(loaded.setups) == 1
        assert len(loaded.operations) == 1
        assert len(loaded.tool_list) == 1
        assert len(loaded.machine_list) == 1
        assert len(loaded.open_items) == 1
        assert len(loaded.pfmea_hooks) == 1
        assert loaded.process_flow is not None

    def test_setup_datum_refs_are_tuple(
        self, store: PersistentManufacturingPlanStore
    ) -> None:
        plan = _rich_plan()
        store.save(plan)
        loaded = store.get(plan.plan_id)
        assert isinstance(loaded.setups[0].datum_references, tuple)

    def test_operation_cutting_speed_preserved(
        self, store: PersistentManufacturingPlanStore
    ) -> None:
        plan = _rich_plan()
        store.save(plan)
        loaded = store.get(plan.plan_id)
        assert loaded.operations[0].cutting_speed_m_min == 250.0

    def test_operation_order_preserved(self, store: PersistentManufacturingPlanStore) -> None:
        """MUST 18: operation ordering must be deterministic after reload."""
        from backend.manufacturing_plan.models import ManufacturingOperation
        ops = [
            ManufacturingOperation(
                op_id=f"OP-{i:03d}", op_number=i * 10, setup_id="S1",
                feature_id=None, operation_type="MILLING",
                machine_id=None, machine_label=None, tool_id=None, holder_id=None,
                cutting_speed_m_min=None, feed_rate_mm_min=None, rpm=None,
                ap_mm=None, ae_mm=None, coolant_note=None, target_tolerance=None,
                surface_finish=None, inspection_note=None,
                cycle_time_context=None, capability_context=None,
                surface_capability_context=None,
            )
            for i in range(1, 6)
        ]
        plan = ManufacturingPlan(
            plan_id="PLAN-ORDER-001", source_id="WF_X",
            drawing_number=None, revision=None, part_id=None,
            operations=ops,
        )
        store.save(plan)
        loaded = store.get("PLAN-ORDER-001")
        loaded_numbers = [o.op_number for o in loaded.operations]
        assert loaded_numbers == [10, 20, 30, 40, 50]

    def test_generation_warnings_preserved(self, store: PersistentManufacturingPlanStore) -> None:
        plan = _rich_plan()
        store.save(plan)
        loaded = store.get(plan.plan_id)
        assert loaded.generation_warnings == ["WARN: incomplete catalog"]

    def test_pfmea_hook_round_trip(self, store: PersistentManufacturingPlanStore) -> None:
        plan = _rich_plan()
        store.save(plan)
        loaded = store.get(plan.plan_id)
        hook = loaded.pfmea_hooks[0]
        assert hook.feature_id == "FEAT-001"
        assert hook.failure_mode_hint == "Dimensional deviation"


# ===========================================================================
# MUST 8: Reload must NOT promote readiness
# ===========================================================================


class TestNoStatusPromotion:
    def test_draft_stays_draft_after_reload(self, store: PersistentManufacturingPlanStore) -> None:
        plan = _minimal_plan(status=ManufacturingPlanStatus.DRAFT)
        store.save(plan)
        loaded = store.get(plan.plan_id)
        assert loaded.status == ManufacturingPlanStatus.DRAFT

    def test_candidate_feature_not_auto_confirmed(
        self, store: PersistentManufacturingPlanStore
    ) -> None:
        """MUST 11: CANDIDATE must never become CONFIRMED on reload."""
        plan = ManufacturingPlan(
            plan_id="PLAN-CANDIDATE-001", source_id="WF_X",
            drawing_number=None, revision=None, part_id=None,
            status=ManufacturingPlanStatus.DRAFT,
            generation_warnings=["CANDIDATE_FEATURE: feature_id=FEAT-001"],
        )
        store.save(plan)
        loaded = store.get("PLAN-CANDIDATE-001")
        assert loaded.status == ManufacturingPlanStatus.DRAFT
        assert "CANDIDATE_FEATURE: feature_id=FEAT-001" in loaded.generation_warnings

    def test_auto_generated_plan_marked_approved_false(
        self, store: PersistentManufacturingPlanStore
    ) -> None:
        plan = _minimal_plan()
        assert plan.AUTO_GENERATED_PLAN_MARKED_APPROVED is False
        store.save(plan)
        loaded = store.get(plan.plan_id)
        assert loaded.AUTO_GENERATED_PLAN_MARKED_APPROVED is False

    def test_release_gate_not_promoted(self, store: PersistentManufacturingPlanStore) -> None:
        plan = _minimal_plan()
        store.save(plan)
        loaded = store.get(plan.plan_id)
        from backend.manufacturing_plan.models import ReleaseGateStatus
        assert loaded.release_gate == ReleaseGateStatus.INCOMPLETE


# ===========================================================================
# MUST 20: is_dispatchable and production_released remain False
# ===========================================================================


class TestSafetyAfterReload:
    def test_disclaimer_preserved(self, store: PersistentManufacturingPlanStore) -> None:
        plan = _minimal_plan()
        store.save(plan)
        loaded = store.get(plan.plan_id)
        assert "REFERENCE_ONLY" in loaded.disclaimer
        assert "AUTO_GENERATED_PLAN_MARKED_APPROVED=NO" in loaded.disclaimer

    def test_auto_generated_plan_marked_approved_never_true_after_save(
        self, store: PersistentManufacturingPlanStore
    ) -> None:
        plan = _minimal_plan()
        assert plan.AUTO_GENERATED_PLAN_MARKED_APPROVED is False
        store.save(plan)
        loaded = store.get(plan.plan_id)
        assert loaded.AUTO_GENERATED_PLAN_MARKED_APPROVED is False


# ===========================================================================
# Plan lifecycle actions (approve, reject, supersede)
# ===========================================================================


class TestPlanActions:
    def test_mark_engineer_reviewed(self, store: PersistentManufacturingPlanStore) -> None:
        plan = _minimal_plan("PLAN-REV")
        store.save(plan)
        reviewed = store.mark_engineer_reviewed("PLAN-REV", "LGTM")
        assert reviewed.status == ManufacturingPlanStatus.ENGINEER_REVIEWED
        reloaded = store.get("PLAN-REV")
        assert reloaded.status == ManufacturingPlanStatus.ENGINEER_REVIEWED

    def test_approve_requires_engineer_reviewed(
        self, store: PersistentManufacturingPlanStore
    ) -> None:
        plan = _minimal_plan("PLAN-APP")
        store.save(plan)
        with pytest.raises(PlanApprovalError):
            store.approve("PLAN-APP")

    def test_approve_from_engineer_reviewed(
        self, store: PersistentManufacturingPlanStore
    ) -> None:
        plan = _minimal_plan("PLAN-APP2")
        store.save(plan)
        store.mark_engineer_reviewed("PLAN-APP2")
        approved = store.approve("PLAN-APP2")
        assert approved.status == ManufacturingPlanStatus.APPROVED

    def test_reject_plan(self, store: PersistentManufacturingPlanStore) -> None:
        plan = _minimal_plan("PLAN-REJ")
        store.save(plan)
        rejected = store.reject("PLAN-REJ", "needs rework")
        assert rejected.status == ManufacturingPlanStatus.REJECTED
        reloaded = store.get("PLAN-REJ")
        assert reloaded.status == ManufacturingPlanStatus.REJECTED

    def test_supersede(self, store: PersistentManufacturingPlanStore) -> None:
        old = _minimal_plan("PLAN-OLD")
        new = _minimal_plan("PLAN-NEW")
        store.save(old)
        store.supersede("PLAN-OLD", new)
        old_reloaded = store.get("PLAN-OLD")
        assert old_reloaded.status == ManufacturingPlanStatus.SUPERSEDED
        new_reloaded = store.get("PLAN-NEW")
        assert new_reloaded.status == ManufacturingPlanStatus.DRAFT


# ===========================================================================
# MUST 38: Multi-project isolation
# ===========================================================================


class TestMultiProjectIsolation:
    def test_two_projects_independent(
        self, store: PersistentManufacturingPlanStore
    ) -> None:
        p1 = _minimal_plan("PLAN-PROJ1", part_id="PART-PROJ1", drawing_number="DRW-A")
        p2 = _minimal_plan("PLAN-PROJ2", part_id="PART-PROJ2", drawing_number="DRW-B")
        store.save(p1)
        store.save(p2)
        l1 = store.get("PLAN-PROJ1")
        l2 = store.get("PLAN-PROJ2")
        assert l1.part_id == "PART-PROJ1"
        assert l2.part_id == "PART-PROJ2"
        assert l1.drawing_number != l2.drawing_number

    def test_cross_project_state_no_leak(
        self, store: PersistentManufacturingPlanStore
    ) -> None:
        store.save(_minimal_plan("PLAN-ISO1", part_id="PART-ISO1"))
        store.save(_minimal_plan("PLAN-ISO2", part_id="PART-ISO2"))
        l1 = store.get("PLAN-ISO1")
        l2 = store.get("PLAN-ISO2")
        # each plan's part_id is independent
        assert l1.part_id != l2.part_id


# ===========================================================================
# MUST 40: Duplicate ID must not silently overwrite unrelated records
# ===========================================================================


class TestDuplicateIdBehavior:
    def test_duplicate_id_updates_same_record(
        self, store: PersistentManufacturingPlanStore
    ) -> None:
        p1 = _minimal_plan("PLAN-DUP", drawing_number="DRW-V1")
        p2 = _minimal_plan("PLAN-DUP", drawing_number="DRW-V2")
        store.save(p1)
        store.save(p2)
        # Only 1 record — not silently duplicated
        assert store.count() == 1
        loaded = store.get("PLAN-DUP")
        # Latest version wins (upsert, not new record)
        assert loaded.drawing_number == "DRW-V2"


# ===========================================================================
# MUST 41: Legacy project load — graceful handling of absent records
# ===========================================================================


class TestLegacyCompatibility:
    def test_plan_not_found_returns_plan_not_found_error(
        self, store: PersistentManufacturingPlanStore
    ) -> None:
        # A workflow that predates persistence simply has no plan record
        with pytest.raises(PlanNotFoundError):
            store.get("WF-LEGACY-NO-PLAN")
        # This must not raise an unhandled exception

    def test_empty_store_survives_list(
        self, store: PersistentManufacturingPlanStore
    ) -> None:
        result = store.list_all()
        assert result == []


# ===========================================================================
# MUST 42: Partial / corrupt record handling
# ===========================================================================


class TestCorruptRecordHandling:
    def test_missing_optional_fields_do_not_crash_load(
        self, store: PersistentManufacturingPlanStore
    ) -> None:
        # Plan with all optional nested lists empty
        plan = ManufacturingPlan(
            plan_id="PLAN-MINIMAL-OPT", source_id="WF_X",
            drawing_number=None, revision=None, part_id=None,
        )
        store.save(plan)
        loaded = store.get("PLAN-MINIMAL-OPT")
        assert loaded.plan_id == "PLAN-MINIMAL-OPT"
        assert loaded.setups == []
        assert loaded.operations == []
        assert loaded.tool_list == []
        assert loaded.inspection_plan is None
        assert loaded.control_plan is None
        assert loaded.process_flow is None


# ===========================================================================
# MUST 43: Secret safety
# ===========================================================================


class TestSecretSafety:
    def test_disclaimer_has_no_secret_fields(
        self, store: PersistentManufacturingPlanStore
    ) -> None:
        plan = _minimal_plan()
        store.save(plan)
        loaded = store.get(plan.plan_id)
        secret_markers = ["password", "jwt", "token", "api_key", "secret"]
        for marker in secret_markers:
            assert marker.lower() not in loaded.disclaimer.lower()


# ===========================================================================
# MUST 44: Path safety
# ===========================================================================


class TestPathSafety:
    def test_plan_id_with_path_traversal_stored_as_text(
        self, store: PersistentManufacturingPlanStore
    ) -> None:
        # The store uses parameterised queries; traversal IDs are stored as text
        # and cannot escape to the filesystem
        plan = ManufacturingPlan(
            plan_id="../../../etc/passwd",
            source_id="WF_X", drawing_number=None, revision=None, part_id=None,
        )
        store.save(plan)
        loaded = store.get("../../../etc/passwd")
        assert loaded.plan_id == "../../../etc/passwd"


# ===========================================================================
# MUST 39: Concurrent access
# ===========================================================================


class TestConcurrentAccess:
    def test_concurrent_reads(self, store: PersistentManufacturingPlanStore) -> None:
        store.save(_minimal_plan("PLAN-CONC"))
        errors: list[Exception] = []

        def reader() -> None:
            try:
                for _ in range(10):
                    store.get("PLAN-CONC")
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=reader) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Concurrent reads raised: {errors}"

    def test_concurrent_writes(self, store: PersistentManufacturingPlanStore) -> None:
        errors: list[Exception] = []

        def writer(i: int) -> None:
            try:
                plan = _minimal_plan(f"PLAN-CONC-W{i}")
                store.save(plan)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Concurrent writes raised: {errors}"
        assert store.count() == 10


# ===========================================================================
# MUST 45: Auditability
# ===========================================================================


class TestAuditability:
    def test_created_at_preserved(self, store: PersistentManufacturingPlanStore) -> None:
        plan = _minimal_plan()
        created = plan.created_at
        store.save(plan)
        loaded = store.get(plan.plan_id)
        # created_at should be close (not reset on save)
        assert abs((loaded.created_at - created).total_seconds()) < 2

    def test_updated_at_set_on_save(self, store: PersistentManufacturingPlanStore) -> None:
        plan = _minimal_plan()
        saved = store.save(plan)
        assert saved.updated_at is not None

    def test_revision_history_preserved(self, store: PersistentManufacturingPlanStore) -> None:
        plan = _minimal_plan("PLAN-HIST")
        store.save(plan)
        reviewed = store.mark_engineer_reviewed("PLAN-HIST", "review note")
        assert len(reviewed.revision_history) == 1
        reloaded = store.get("PLAN-HIST")
        assert len(reloaded.revision_history) == 1
        assert reloaded.revision_history[0].engineer_note == "review note"


# ===========================================================================
# MUST 46: Archive / soft-delete policy
# ===========================================================================


class TestArchivePolicy:
    def test_supersede_preserves_old_record(
        self, store: PersistentManufacturingPlanStore
    ) -> None:
        old = _minimal_plan("PLAN-ARCH-OLD")
        new = _minimal_plan("PLAN-ARCH-NEW")
        store.save(old)
        store.supersede("PLAN-ARCH-OLD", new)
        # Old record still exists (soft-supersede, not delete)
        old_reloaded = store.get("PLAN-ARCH-OLD")
        assert old_reloaded.status == ManufacturingPlanStatus.SUPERSEDED


# ===========================================================================
# Serializer unit tests
# ===========================================================================


class TestSerializer:
    def test_roundtrip_minimal(self) -> None:
        plan = _minimal_plan()
        json_str = plan_to_json(plan)
        loaded = plan_from_json(json_str)
        assert loaded.plan_id == plan.plan_id
        assert loaded.status == plan.status

    def test_roundtrip_rich(self) -> None:
        plan = _rich_plan()
        json_str = plan_to_json(plan)
        loaded = plan_from_json(json_str)
        assert loaded.plan_id == plan.plan_id
        assert len(loaded.operations) == 1
        assert len(loaded.pfmea_hooks) == 1

    def test_datetime_preserved(self) -> None:
        plan = _minimal_plan()
        created = plan.created_at
        json_str = plan_to_json(plan)
        loaded = plan_from_json(json_str)
        assert abs((loaded.created_at - created).total_seconds()) < 1

    def test_tuple_fields_preserved_as_tuples(self) -> None:
        plan = _rich_plan()
        json_str = plan_to_json(plan)
        loaded = plan_from_json(json_str)
        assert isinstance(loaded.setups[0].datum_references, tuple)
        assert isinstance(loaded.setups[0].tool_ids, tuple)
        assert isinstance(loaded.tool_list[0].operation_ids, tuple)

    def test_none_optional_fields_preserved(self) -> None:
        plan = ManufacturingPlan(
            plan_id="PLAN-NONE", source_id="WF_X",
            drawing_number=None, revision=None, part_id=None,
        )
        json_str = plan_to_json(plan)
        loaded = plan_from_json(json_str)
        assert loaded.drawing_number is None
        assert loaded.part_id is None
        assert loaded.inspection_plan is None

    def test_status_not_promoted_on_roundtrip(self) -> None:
        """AUTO_CONFIRM_ON_RELOAD=NO."""
        for status in ManufacturingPlanStatus:
            plan = _minimal_plan(status=status)
            json_str = plan_to_json(plan)
            loaded = plan_from_json(json_str)
            assert loaded.status == status, f"Status {status} changed on reload"

    def test_schema_version_in_payload(self) -> None:
        import json as _json
        plan = _minimal_plan()
        json_str = plan_to_json(plan)
        d = _json.loads(json_str)
        assert "__schema_version__" in d

    def test_auto_generated_plan_marked_approved_false_roundtrip(self) -> None:
        plan = _minimal_plan()
        json_str = plan_to_json(plan)
        loaded = plan_from_json(json_str)
        assert loaded.AUTO_GENERATED_PLAN_MARKED_APPROVED is False


# ===========================================================================
# Restart E2E (simulated via two separate store instances on same DB)
# ===========================================================================


class TestRestartE2E:
    def test_plan_survives_simulated_restart(self, tmp_path: Path) -> None:
        """MUST 33-34: Plan data persists across simulated backend restart."""
        db = tmp_path / "restart_test.db"
        plan = _rich_plan("PLAN-RESTART")

        # Session 1: seed plan
        with PersistentManufacturingPlanStore(db) as s1:
            s1.save(plan)
            count_s1 = s1.count()

        # Session 2: new instance, same DB (restart)
        with PersistentManufacturingPlanStore(db) as s2:
            assert s2.count() == count_s1
            loaded = s2.get("PLAN-RESTART")
            assert loaded.plan_id == "PLAN-RESTART"
            assert loaded.status == ManufacturingPlanStatus.DRAFT
            assert len(loaded.setups) == 1
            assert len(loaded.operations) == 1
            assert len(loaded.tool_list) == 1

    def test_status_not_changed_after_restart(self, tmp_path: Path) -> None:
        """MUST 37: Reload must not modify engineering meaning."""
        db = tmp_path / "status_restart.db"
        with PersistentManufacturingPlanStore(db) as s1:
            plan = _minimal_plan("PLAN-STATUS-PERSIST")
            s1.save(plan)
            s1.mark_engineer_reviewed("PLAN-STATUS-PERSIST")

        with PersistentManufacturingPlanStore(db) as s2:
            loaded = s2.get("PLAN-STATUS-PERSIST")
            assert loaded.status == ManufacturingPlanStatus.ENGINEER_REVIEWED

    def test_multi_project_isolation_across_restart(self, tmp_path: Path) -> None:
        """MUST 38: Cross-project isolation survives restart."""
        db = tmp_path / "multi_proj.db"
        with PersistentManufacturingPlanStore(db) as s1:
            s1.save(_minimal_plan("PLAN-ISO-A", part_id="PART-ISO-A"))
            s1.save(_minimal_plan("PLAN-ISO-B", part_id="PART-ISO-B"))

        with PersistentManufacturingPlanStore(db) as s2:
            a = s2.get("PLAN-ISO-A")
            b = s2.get("PLAN-ISO-B")
            assert a.part_id == "PART-ISO-A"
            assert b.part_id == "PART-ISO-B"
            assert a.part_id != b.part_id
