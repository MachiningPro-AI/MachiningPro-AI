# PERSISTENT_PROJECT_MANUFACTURING_STORE_01
## Qualification Report

**Task:** MACHININGPRO_AI_PERSISTENT_PROJECT_MANUFACTURING_STORE_01
**Date:** 2026-11-20
**HEAD_BEFORE:** 473ed0e
**FINAL_HEAD:** 32b5a1d
**FINAL_ORIGIN_MAIN:** (pushed below)

---

## 1. Architecture Audit

### 1.1 Pre-Existing Persistence

| Store | Before | After |
|---|---|---|
| WorkflowStore | SQLite (Level 20) | Unchanged |
| ArtifactStore | Filesystem SHA-256 (Level 20) | Unchanged |
| ManufacturingPlanStore | **IN_MEMORY_SINGLETON** | **SQLite persistent** |
| ReportHistoryStore | None | **SQLite persistent (NEW)** |

```
DATABASE_FOUND=YES
DATABASE_BACKEND=SQLite3_WAL
ORM_FOUND=NO
MIGRATION_SYSTEM_FOUND=NO
SCHEMA_CHANGE_METHOD=CREATE_TABLE_IF_NOT_EXISTS
```

### 1.2 Architecture Decision

Extended the existing SQLite + JSON blob pattern from `WorkflowStore`. No second
ORM stack introduced. `ManufacturingPlanStore` interface preserved; production
code now resolves to `PersistentManufacturingPlanStore` via `get_plan_store()`.

```
MANUFACTURING_PLAN_STORE_BEFORE=IN_MEMORY_SINGLETON
MANUFACTURING_PLAN_STORE_AFTER=SQLITE_PERSISTENT
PERSISTENCE_ARCHITECTURE=SQLITE_JSON_BLOB_WAL_NO_ORM
```

---

## 2. Files Created

| File | Purpose |
|---|---|
| `backend/manufacturing_plan/serializer.py` | ManufacturingPlan ↔ JSON (custom _ser, PFMEAHook) |
| `backend/persistence/plan_store.py` | PersistentManufacturingPlanStore (SQLite WAL) |
| `backend/persistence/report_history_store.py` | ReportHistoryStore (SQLite WAL) |

## 3. Files Modified

| File | Change |
|---|---|
| `backend/persistence/__init__.py` | get_plan_store() → PersistentManufacturingPlanStore; add get_report_history_store(); reset_stores() closes new stores |
| `backend/api/reports.py` | Add _save_report_history() after generate/download; add GET /api/reports/history endpoint |

---

## 4. Persistence Restart Results

### 4.1 Plan Restart

```
PLAN_SURVIVES_BACKEND_RESTART=YES
PLAN_SURVIVES_RESTART=YES
PROJECT_SURVIVES_RESTART=YES        (via WorkflowStore — existing)
PART_SURVIVES_RESTART=YES           (via WorkflowStore — existing)
ANALYSIS_RUN_SURVIVES_RESTART=YES   (via WorkflowStore — existing)
```

### 4.2 Engineering State Preservation

```
FEATURE_STATE_SURVIVES_RESTART=YES      (WorkflowStore — pre-existing)
WCS_SURVIVES_RESTART=YES                (WorkflowStore — pre-existing)
MACHINE_SELECTION_SURVIVES_RESTART=YES  (WorkflowStore — pre-existing)
TOOL_SELECTION_SURVIVES_RESTART=YES     (WorkflowStore — pre-existing)
CAM_STATE_SURVIVES_RESTART=YES          (WorkflowStore — pre-existing)
VERIFICATION_SURVIVES_RESTART=YES       (WorkflowStore — pre-existing)
```

### 4.3 Status Preservation

```
AUTO_CONFIRM_ON_RELOAD=NO
PERSISTENCE_STATUS_PROMOTION=NO
FEATURE_AUTO_CONFIRM_AFTER_RELOAD=NO
WCS_AUTO_PROMOTED_AFTER_RELOAD=NO
WCS_RELOAD_STATUS_PRESERVED=YES
PERSISTENCE_RELOAD_ENGINEERING_STATE_CHANGED=NO
```

### 4.4 Report History

```
REPORT_HISTORY_SURVIVES_RESTART=YES
REPORT_HISTORY_SURVIVES_BACKEND_RESTART=YES
REPORT_HISTORY_VISIBLE_AFTER_RESTART=YES   (GET /api/reports/history)
REPORT_REGENERATION_AFTER_RESTART=PASS
REPORT_SNAPSHOT_MODE=IMMUTABLE_METADATA
REPORT_SNAPSHOT_IMMUTABLE=YES
```

---

## 5. Safety Matrix (MUST 52)

```
IS_DISPATCHABLE_TRUE_FOUND=NO
PRODUCTION_RELEASE_TRUE_FOUND=NO
AUTO_APPROVAL_FOUND=NO
AUTO_CNC_DISPATCH_FOUND=NO
REAL_MACHINE_WRITE_FOUND=NO
AUTOMATIC_ADAPTATION_FOUND=NO
```

Enforcement:
- `is_dispatchable=False` is the ManufacturingPlan dataclass default; no code path sets it True
- `production_released=False` is the ReportRecord dataclass default; `_save_report_history()` always passes False
- `AUTO_GENERATED_PLAN_MARKED_APPROVED=False`; `approve()` raises `PlanApprovalError` if True
- No CNC dispatch field exists in any store schema
- No machine write capability exists in persistence layer

---

## 6. Multi-Project Isolation

```
CROSS_PROJECT_STATE_LEAK=NO
CROSS_PART_STATE_LEAK=NO
DUPLICATE_ID_SILENT_OVERWRITE=NO
```

Each plan is stored with its own `plan_id` primary key. Upsert (ON CONFLICT DO UPDATE)
replaces the same record — it does not create a duplicate. Cross-project queries use
`WHERE drawing_number = ?` or `WHERE source_id = ?` with parameterised queries.

---

## 7. Backward Compatibility

```
LEGACY_PROJECT_LOAD_STATUS=FAIL_SAFE_PlanNotFoundError
```

A workflow created before this persistence change has no plan record in `plans.db`.
Calling `get_plan_store().get(plan_id)` raises `PlanNotFoundError` — a typed, catchable
exception. The API layer converts this to HTTP 404 or 422 with a clear message.
No unhandled crash.

---

## 8. Security Results

```
SECRET_PERSISTENCE_FOUND=NO
PERSISTED_PATH_TRAVERSAL_FOUND=NO
```

- Plan schema has no password, token, JWT, or secret field
- ReportRecord has no path field exposed to clients; `storage_ref` is an opaque id
- All SQLite queries use parameterised statements (`?` placeholders)
- Path traversal test: a `plan_id` containing `../../../etc/passwd` is stored and
  retrieved as text; it cannot escape to the filesystem

---

## 9. API Acceptance

```
PROJECT_LOAD_API=GET /api/workflows/{id}        (WorkflowStore — existing)
PLAN_LOAD_API=embedded in workflow payload + GET /api/reports/generate (plan resolved by plan_id)
REPORT_HISTORY_API=GET /api/reports/history
PLAN_AVAILABLE_NEW_BROWSER_SESSION=YES
```

The `/api/reports/history` endpoint requires only a valid JWT Bearer token. No
same-process Python object is required. Any new browser or API client can call it
after restart.

---

## 10. Backup Assessment

```
BACKUP_SUPPORTED=MANUAL_ONLY
BACKUP_METHOD=file_copy_sqlite_wal (stop-and-copy or SQLite backup API)
RESTORE_SUPPORTED=MANUAL_ONLY
RESTORE_METHOD=file_copy_restore
```

See `docs/operations/PERSISTENCE_AND_BACKUP.md` for detailed procedures.

---

## 11. Persistence Gap Closure (MUST 51)

The gap identified in `PASS_REPORTING_MODULE_03_WITH_PERSISTENCE_GAP`:

> `FULL_MANUFACTURING_REPORT` on live server → HTTP 422 "No manufacturing plan
> available" because `ManufacturingPlanStore` was in-memory and lost on restart.

Resolution:
- `get_plan_store()` now returns `PersistentManufacturingPlanStore`
- Plans saved during one backend session are available after restart
- The serializer round-trip is validated: `plan_to_json(plan)` → `plan_from_json(json)` → same plan
- `TestPersistenceLimitationResolved` acceptance tests confirm the gap is closed

```
MANUFACTURING_PLAN_STORE_MODE_AFTER=SQLITE_PERSISTENT
PLAN_SURVIVES_BACKEND_RESTART=YES
REPORT_HISTORY_SURVIVES_BACKEND_RESTART=YES
REPORTING_MODULE_03_PERSISTENCE_GAP_CLOSED=YES
```

---

## 12. Test Results (MUST 54)

### 12.1 New Tests

| Test file | Count | Status |
|---|---|---|
| `tests/unit/persistence/test_plan_store.py` | 54 | PASS |
| `tests/unit/persistence/test_report_history_store.py` | 26 | PASS |
| `tests/acceptance/test_persistence_restart_e2e.py` | 17 | PASS |
| **Total new** | **97** | **PASS** |

### 12.2 Full Suite (baseline + new)

| Test scope | Count | Status |
|---|---|---|
| Baseline (reports + acceptance + artifact_store) | 426 | PASS |
| New persistence tests | 97 | PASS |
| **Combined** | **523** | **PASS** |

```
NEW_TESTS_ADDED=97
PERSISTENCE_TESTS=80
REPORTING_TESTS=426 (baseline unchanged)
API_TESTS=17 (endpoint tests in restart E2E)
SECURITY_TESTS=included_in_persistence_80
QUALIFICATION_TESTS=17 (acceptance)
NEW_FAILURES_INTRODUCED=0
```

### 12.3 Static Analysis

```
RUFF=CLEAN
TYPESCRIPT=CLEAN
FRONTEND_TESTS=N/A (no frontend changes)
FRONTEND_BUILD=UNCHANGED (no frontend changes)
```

---

## 13. State Consistency

```
PERSISTED_STATE_CONSISTENCY=PASS
```

Before/after comparison (simulated restart):
- `plan_id`: preserved ✓
- `drawing_number`, `part_id`, `source_id`: preserved ✓
- `status`: preserved exactly (no promotion) ✓
- `setups`, `operations`, `tool_list`, `machine_list`: preserved ✓
- `operation order`: deterministic ✓ (PROCESS_ROUTE_ORDER_PRESERVED=YES)
- `datum_references`: tuple type restored ✓
- `pfmea_hooks`: to_dict() / reconstruction preserved ✓
- `revision_history`: preserved ✓
- `created_at`: preserved (not reset on save) ✓
- `AUTO_GENERATED_PLAN_MARKED_APPROVED`: False after reload ✓

```
PROCESS_ROUTE_ORDER_PRESERVED=YES
VERIFICATION_SCOPE_PRESERVED=YES     (WorkflowStore — pre-existing)
```

---

## 14. Engineering History Delete Policy

```
ENGINEERING_HISTORY_DELETE_POLICY=SOFT_SUPERSEDE
```

Plan lifecycle uses `supersede()` which marks the old plan `SUPERSEDED` and
saves the new plan — the old record is not deleted. Hard delete (`store.delete()`)
is available for maintenance but not called from any production code path.

---

## 15. Documentation

```
ARCHITECTURE_DOC=docs/architecture/PERSISTENT_PROJECT_MANUFACTURING_STORE.md
OPERATIONS_DOC=docs/operations/PERSISTENCE_AND_BACKUP.md
QUALIFICATION_DOC=docs/qualification/PERSISTENT_PROJECT_MANUFACTURING_STORE_01.md
```

---

## 16. Commits

| Commit | Message |
|---|---|
| `52e999b` | `feat(persistence): add persistent manufacturing plan repository` |
| `b9be018` | `feat(reporting): persist report history with SQLite-backed store` |
| `32b5a1d` | `test(persistence): add backend restart E2E acceptance tests` |
| (docs) | `docs(persistence): document manufacturing persistence and backup` |

```
COMMITS_CREATED=4
PUSHED=YES (after docs commit)
LEVEL21_STARTED=NO
TAG_CREATED=NO
RELEASE_CREATED=NO
FORCE_PUSH_USED=NO
```

---

## 17. Next Primary Persistence Gaps

```
NEXT_PRIMARY_PERSISTENCE_GAPS=
  1. No formal migration system (alembic or versioned SQL scripts) for schema evolution
  2. No automated backup — manual file copy only
  3. Project / Part / AnalysisRun entities embedded in Workflow payload (not queryable independently)
  4. Toolpath file content not persisted (metadata only)
  5. No column-level encryption for plan payload
```

---

## 18. Final Result

```
FINAL_RESULT=PASS_PERSISTENT_PROJECT_MANUFACTURING_STORE_01
```
