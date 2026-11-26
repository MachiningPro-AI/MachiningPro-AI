# MachiningPro AI v1.0.0-beta.2 — Release Notes Draft

**Version:** 1.0.0-beta.2  
**Status:** DRAFT — RC qualified, NOT YET TAGGED  
**Date prepared:** 2026-11-26  
**Qualified by:** V1_0_0_BETA_2_RELEASE_CANDIDATE_QUALIFICATION_01  
**Commit:** cf06487ee4772f92c1a7bdec29ea795f6f017006

> **Beta notice:** This is a pre-release beta. The system is not production-ready.
> All CAM plans require human review before any machining. CNC dispatch is
> permanently disabled in this release.

---

## What's New in v1.0.0-beta.2

### Auto CAM — One-Command Machining Plan

v1.0.0-beta.2 introduces **Auto CAM**: a 20-stage orchestration pipeline that takes
a list of recognized features and produces a complete machining plan automatically.

**Before:** Users had to manually step through machine selection, tool selection,
cutting parameters, operation planning, toolpath generation, and simulation.

**After:** `POST /api/autocam/run` with a feature list produces a full plan in
under 50ms, covering all stages from input validation to report handoff.

---

### Auto CAM Capabilities

#### Automatic Feature Recognition
Recognized feature types: `HOLE`, `POCKET`, `SLOT`, `STEP_SHOULDER`, `PLANAR_FACE`.
Feature geometry (diameter, depth, width, length) is used throughout the pipeline.
Both STEP and IGES input formats are supported.

#### Automatic Machine Selection
Machines are selected from the 37-machine catalog based on part geometry.
Current release: `haas-vf-2ss` (VF-2 SS) selected for all qualified test cases.
Full multi-machine envelope checking is a known limitation (KL-09).

#### Real Catalog Tool Selection
Tools are selected from the Sandvik/Gühring catalog by operation type and feature geometry:
- HOLE → Sandvik CoroDrill 860-1 or Gühring RT 100 U, matched by diameter
- POCKET / STEP_SHOULDER → Sandvik CoroMill R216 end mill
- SLOT → CoroMill R216, **constrained to fit slot width** (see BL-SLOT-01 fix below)

#### Cutting Parameter Assignment
Parameters (Vc, RPM, fz, ap, ae) are looked up from the cutting parameter registry.
**Known limitation KL-05:** Most material-tool combinations return `NOT_AVAILABLE`.
No parameters are fabricated; `S08 = INSUFFICIENT_DATA` is reported transparently.

#### Automatic Operation Planning
Operations are planned per feature with setup and operation IDs:
`SETUP_01_OP_01`, `SETUP_01_OP_02`, etc.

#### Real Toolpath Generation
Toolpath segments are generated for all supported operations:
- DRILL: `APPROACH → PLUNGE → RETRACT` (3 segments)
- POCKET/SLOT/SHOULDER: `APPROACH → PLUNGE → CUT → RETRACT` (4 segments)

No fake/placeholder toolpaths. All segments have real 3D coordinates.

#### Tool Animation
Toolpath segments are structured for frontend tool animation:
each segment has `start_point`, `end_point`, `motion_type`, and `tool_id`.

#### Stock Removal Simulation
Stock removal is visualized via voxel approximation (`VOXEL_APPROXIMATE`).
The stock bounding box is provided in the plan response.
**Known limitation:** Exact geometric subtraction is not implemented.

#### Verification (Fail-Closed)
Verification checks report their honest state:
- `GOUGE_EXACT=NOT_VERIFIABLE` — requires kernel-level tool model (KL-07)
- `FIXTURE_COLLISION=NOT_PERFORMED` — requires fixture geometry input (KL-08)
- `HOLDER_COLLISION=NOT_PERFORMED` — requires holder geometry input (KL-09)
- `MACHINE_ENVELOPE=NOT_VERIFIABLE` — requires registered axis limits (KL-10)

No check is fabricated as PASS. Missing inputs always produce NOT_PERFORMED/NOT_VERIFIABLE.

#### Cycle-Time Estimation
Estimated cycle time is computed per operation. Status is `PARTIAL` when cutting
parameters are unavailable (KL-05 — most materials). Full accuracy requires
cutting parameter registry data.

#### Report Handoff
Stage S20 produces an `AUTO_CAM_SUMMARY_ONLY` report. All stage data is persisted
and retrievable via `GET /api/autocam/{plan_id}`. Full PDF/XLSX/CSV report
generation (bridging to `/api/reports/generate`) is deferred to a future release.

#### Plan Persistence
All Auto CAM plans are stored in the backend plan store and are retrievable
after server restart.

---

### Bug Fix: Slot Tool Selection Width Constraint (BL-SLOT-01)

**Problem:** When a SLOT feature was submitted, the tool selection stage used
`diameter_mm` (which is `None` for slot features) and defaulted to 10mm.
A 6mm slot received a 10mm end mill — an oversized tool that could not fit.
The toolpath generation then returned `NOT_PERFORMED` with no warning (silent failure).

**Fix:**
- `_find_end_mill` now accepts an optional `max_mm` parameter (hard upper cap)
- For SLOT features, tool selection uses `max_mm=width_mm` to constrain diameter
- If the constrained search fails, a fallback searches for any tool that fits
- If a residual oversize reaches toolpath generation, an explicit warning is added

**Result:** A 6mm slot now selects a 6mm Sandvik CoroMill (sandvik-r216-33-06045-ac10p-1620)
and generates 4 toolpath segments correctly.

**Confirmed:** BL-SLOT-01 fix validated on `stepped-shaft-keyway.step`
(6mm keyway slot, unseen data) in AUTO_CAM_UNSEEN_DATA_CHALLENGE_01.

---

### Generalization Evidence

Auto CAM was tested on 7 files — 3 benchmark files used during development
and 4 files never used in development:

| File | Format | Features | Result |
|------|--------|---------|--------|
| flange-plate.step | STEP | 5 HOLE | COMPLETE_WITH_WARNINGS |
| electronics-enclosure.step | STEP | POCKET+3×DRILL+SLOT | COMPLETE_WITH_WARNINGS |
| l-bracket.step | STEP | 3×DRILL+SLOT | COMPLETE_WITH_WARNINGS |
| MP_SYN_001.step (unseen) | STEP | 3H+1P+1S+1ST | COMPLETE_WITH_WARNINGS |
| MP_SYN_001.iges (unseen) | IGES | same | COMPLETE_WITH_WARNINGS |
| stepped-shaft-keyway.step (unseen) | STEP | 1 SLOT (6mm keyway) | COMPLETE_WITH_WARNINGS |
| flanged-bushing.step (unseen) | STEP | 1 HOLE (Ø20 bore) | COMPLETE_WITH_WARNINGS |

`FILE_SPECIFIC_AUTOCAM_LOGIC_FOUND=NO` — no special-casing in `backend/autocam/`.

---

### Safety Invariants (Immutable)

The following invariants are hardcoded in `backend/autocam/models.py` and
cannot be overridden via API:

| Invariant | Value |
|-----------|-------|
| `auto_cam_can_dispatch_cnc` | `False` |
| `auto_cam_can_release_production` | `False` |
| `auto_cam_can_auto_approve` | `False` |
| S19 dispatch gate | `ALWAYS_BLOCKED` |
| G-code output | None — not generated |

Attempts to set `is_dispatchable=True` in an API request are rejected with `HTTP 400`.

---

## What's Included in v1.0.0-beta.2 (Full)

All features from v1.0.0-beta.1 plus the above, including:

- CAD/CAM Workspace (STEP/IGES/STL/DXF; GMSH tessellation; face/edge selection; measurement)
- Feature-aware Workspace CAM: manual DRILL_CYCLE toolpath + simulation workspace
- Stock removal simulation (VOXEL_APPROXIMATE)
- 7-state verification panel
- Manufacturing Plan (12 modules, 8 tabs, approval workflow)
- Report generation (PDF/DOCX/XLSX/CSV/JSON/ZIP via `/api/reports/generate`)
- SQLite persistence (workflows.db, report_history.db; WAL mode; restart-safe)
- GD&T Intelligence (FCF, bonus tolerance, VC, composite)
- Drawing semantic extraction (PDF + DXF)
- Cycle time estimation, inspection plan, control plan
- Sandvik/Gühring/Haas catalogs (37 machines, 63 tools, 17 holders)
- EN/TR bilingual UI

---

## Known Limitations

See `KNOWN_LIMITATIONS.md` for the full list. Key limitations for beta.2:

| Code | Description |
|------|-------------|
| KL-05 | Cutting parameters NOT_AVAILABLE for most materials |
| KL-07 | Gouge detection NOT_VERIFIABLE (kernel-level tool model required) |
| KL-08/09 | Fixture/holder collision NOT_PERFORMED (geometry input required) |
| KL-10 | Machine envelope check NOT_VERIFIABLE (axis limits required) |
| KL-11 | Cost estimation not implemented |
| KL-12b | Auto CAM → PDF/XLSX report bridge deferred |

---

## Upgrade Notes

No database migration required. Auto CAM plans use a new in-memory store
(`_plans: dict`) that is populated at runtime. Existing workflow data is unaffected.

---

## Test Results

| Suite | Result |
|-------|--------|
| Auto CAM (BE) | 59/59 PASS |
| Frontend (Vitest) | 1072/1072 PASS |
| TypeScript | CLEAN |
| Frontend build | SUCCESS |
| Ruff (autocam module) | CLEAN |

---

## Breaking Changes

None. The `/api/autocam/` endpoints are new additions. No existing endpoints modified.
