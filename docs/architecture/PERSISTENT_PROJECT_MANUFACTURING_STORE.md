# Persistent Project Manufacturing Store

**Version:** 1.0
**Date:** 2026-11-20
**Status:** IMPLEMENTED

---

## 1. Architecture Overview

MachiningPro AI uses a layered SQLite persistence architecture. All stores follow
the same design contract established by `WorkflowStore` (Level 20):

```
Application Layer
  ├── FastAPI Routes  (backend/api/)
  └── Domain Logic    (backend/manufacturing_plan/, backend/reports/)

Persistence Layer
  ├── WorkflowStore            → data/workflows.db
  ├── PersistentManufacturingPlanStore → data/plans.db      ← NEW
  ├── ReportHistoryStore       → data/report_history.db    ← NEW
  └── ArtifactStore            → data/artifacts/           (filesystem)
```

Each store is:
- **Thread-safe**: `threading.Lock()` around all SQLite operations
- **WAL mode**: `PRAGMA journal_mode=WAL` + `PRAGMA synchronous=NORMAL`
- **Schema-safe**: `CREATE TABLE IF NOT EXISTS` — no destructive migration on startup
- **Fail-closed**: operations raise typed exceptions rather than returning None silently

---

## 2. Database Backend

| Store | File | Schema version | Backend |
|---|---|---|---|
| WorkflowStore | `data/workflows.db` | internal | SQLite 3 |
| PersistentManufacturingPlanStore | `data/plans.db` | 1.0 | SQLite 3 |
| ReportHistoryStore | `data/report_history.db` | 1.0 | SQLite 3 |
| ArtifactStore | `data/artifacts/` | n/a | Filesystem |

**ORM:** None. All stores use the Python `sqlite3` standard library with
parameterised queries. No SQLAlchemy, Tortoise, or Peewee.

**Migration system:** None (yet). `CREATE TABLE IF NOT EXISTS` performs safe
no-op re-runs. Schema changes requiring column additions require manual review;
see Section 9 (Known Gaps).

---

## 3. ManufacturingPlan Persistence

### 3.1 Schema

```sql
CREATE TABLE manufacturing_plans (
    plan_id        TEXT PRIMARY KEY,
    drawing_number TEXT,
    part_id        TEXT,
    source_id      TEXT,
    status         TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    payload        TEXT NOT NULL         -- full JSON blob
);
CREATE INDEX idx_plans_part_id    ON manufacturing_plans(part_id);
CREATE INDEX idx_plans_drawing    ON manufacturing_plans(drawing_number);
CREATE INDEX idx_plans_status     ON manufacturing_plans(status);
```

### 3.2 JSON Serializer

`backend/manufacturing_plan/serializer.py` provides:

- `plan_to_json(plan: ManufacturingPlan) -> str`
- `plan_from_json(payload: str) -> ManufacturingPlan`

The serializer uses a custom `_ser()` recursive helper (not `dataclasses.asdict()`)
because `ManufacturingPlan` contains `PFMEAHook`, which is not a dataclass.
`PFMEAHook` is handled via `.to_dict()` before the dataclass path is reached.

Tuple fields (e.g. `datum_references`, `tool_ids`) are restored from JSON arrays
with explicit `tuple(list)` calls during deserialization.

Schema version `"__schema_version__": "1.0"` is embedded in every payload.

### 3.3 What is Persisted

| Entity | Persisted | Notes |
|---|---|---|
| Setups (ManufacturingSetup) | YES | Frozen dataclass, datum_references as tuple |
| Operations (ManufacturingOperation) | YES | Deterministic order preserved |
| Tool list | YES | stable_id preserved as text |
| Machine list | YES | machine_id preserved as text |
| Open items | YES | Category, severity, status |
| PFMEA hooks | YES | Via .to_dict() / explicit reconstruction |
| Process flow | YES | Nodes, edges, start/end node ids |
| Inspection plan | YES | FAI, inspection rows, frequencies |
| Control plan | YES | Control plan rows, reaction plans |
| Characteristics | YES | Type, criticality, review status |
| Revision history | YES | Full PlanRevisionEntry list |
| Generation warnings | YES | String list |
| Disclaimer | YES | Fixed string from model default |

### 3.4 What is NOT Persisted in Plan Records

- Raw CAD file content (CAD stays in ArtifactStore)
- Passwords / JWT / API keys
- Arbitrary filesystem paths
- Machine catalog records (reference by stable_id only)
- Tool catalog records (reference by tool_id only)

---

## 4. Entity Relationships

```
Workflow (WorkflowStore)
  └── final_plan_ref (plan_id) ──→ ManufacturingPlan (PersistentManufacturingPlanStore)
                                        └── operations / setups / tools
                                        └── inspection_plan
                                        └── control_plan
                                        └── pfmea_hooks

Report (ReportHistoryStore)
  ├── workflow_id  ──→ Workflow
  └── plan_id      ──→ ManufacturingPlan
```

---

## 5. Restart Behaviour

### 5.1 ManufacturingPlan

`PLAN_SURVIVES_BACKEND_RESTART=YES`

On backend restart:
1. `get_plan_store()` creates a new `PersistentManufacturingPlanStore(data/plans.db)`
2. All previously saved plans are available immediately via `store.get(plan_id)`
3. Status is restored exactly as stored — no promotion, no confirmation

**AUTO_CONFIRM_ON_RELOAD=NO**
**PERSISTENCE_STATUS_PROMOTION=NO**

Statuses restored exactly:
- `DRAFT` → `DRAFT`
- `ENGINEER_REVIEWED` → `ENGINEER_REVIEWED`
- `APPROVED` → `APPROVED`
- `REJECTED` → `REJECTED`
- `SUPERSEDED` → `SUPERSEDED`

### 5.2 WCS / Feature / Machine / Tool State

WCS, feature engineering state, machine selection, and tool selection are part of
the **Workflow payload** stored in `WorkflowStore` (SQLite-backed since Level 20).
These already survive backend restart.

`WCS_SURVIVES_RESTART=YES` (via WorkflowStore)
`FEATURE_STATE_SURVIVES_RESTART=YES` (via WorkflowStore)
`MACHINE_SELECTION_SURVIVES_RESTART=YES` (via WorkflowStore)
`TOOL_SELECTION_SURVIVES_RESTART=YES` (via WorkflowStore)
`CAM_STATE_SURVIVES_RESTART=YES` (via WorkflowStore)
`VERIFICATION_SURVIVES_RESTART=YES` (via WorkflowStore)

**WCS_AUTO_PROMOTED_AFTER_RELOAD=NO** — SUGGESTED remains SUGGESTED
**FEATURE_AUTO_CONFIRM_AFTER_RELOAD=NO** — CANDIDATE remains CANDIDATE

### 5.3 Report History

`REPORT_HISTORY_SURVIVES_RESTART=YES`

Report metadata is saved after each successful generate or download call.
`GET /api/reports/history` lists persisted records after restart.

---

## 6. Safety Boundaries

The following invariants are enforced at every persistence layer boundary:

| Invariant | Enforcement |
|---|---|
| `is_dispatchable=False` | Plan model default; never set True in persistence |
| `production_released=False` | ReportRecord field always False |
| `AUTO_GENERATED_PLAN_MARKED_APPROVED=False` | Dataclass default; approve() refuses if True |
| No auto-confirmation on reload | Deserialization restores stored enum value only |
| No arbitrary path write | ArtifactStore uses content-addressed storage |
| No secret persistence | No password/JWT/key fields in any store schema |
| No CNC dispatch state | No dispatch field in any store |

---

## 7. Report Snapshot Mode

`REPORT_SNAPSHOT_MODE=IMMUTABLE_METADATA`

Generated report files are stored in `ArtifactStore` (filesystem) referenced
by an opaque `artifact_id`. The `ReportHistoryStore` stores only metadata;
the content cannot be changed after generation.

`REPORT_SNAPSHOT_IMMUTABLE=YES` — regeneration creates a new record with a new
`report_id`, leaving prior records unchanged.

---

## 8. API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/reports/history` | List persisted report records (newest first) |
| `GET /api/reports/history?workflow_id=WF_xxx` | Filter by workflow |
| `GET /api/reports/history?limit=N` | Limit result count |

Authentication required (Bearer token).

---

## 9. Known Gaps

| Gap | Status |
|---|---|
| No formal migration system | Future work — `alembic` or custom versioned migration |
| No column-level encryption for plan payload | Future work |
| No distributed backup | SQLite file copy only; see PERSISTENCE_AND_BACKUP.md |
| Project / Part / AnalysisRun entities | Not standalone — embedded in Workflow payload |
| Toolpath file content | Not persisted — metadata only |
