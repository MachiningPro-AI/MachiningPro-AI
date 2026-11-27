# MachiningPro AI v1.0.0-beta.4 — Advanced Verification Public Beta

**Release Type:** Public Beta (Draft Release Notes)  
**Qualification:** V1_0_0_BETA_4_RELEASE_CANDIDATE_QUALIFICATION_01  
**Date:** 2026-11-27  
**Commit:** 852ca0a  
**Previous:** v1.0.0-beta.3 (2f25fa2)

---

## Summary

v1.0.0-beta.4 completes the Advanced Verification milestone.  
Every collision, envelope, and gouge check now produces a structured,
fidelity-annotated result with explicit fail-closed semantics:
missing geometry → `NOT_PERFORMED`, unavailable engine → `NOT_VERIFIABLE`.
Nothing is fabricated or promoted to `PASS` without evidence.

---

## What's New

### Holder Collision Framework (Phases F–G)

Three new collision sub-checks are added for tool holder geometry:

| Check | Method | Fidelity |
|---|---|---|
| `HOLDER_PART_COLLISION` | BBOX_CYLINDER | SIMPLIFIED_CYLINDER |
| `HOLDER_STOCK_COLLISION` | BBOX_CYLINDER | SIMPLIFIED_CYLINDER |
| `HOLDER_FIXTURE_COLLISION` | BBOX_CYLINDER | SIMPLIFIED_CYLINDER |

Holder geometry is described by `HolderGeometryRecord`:
`HOLDER_ID`, `INTERFACE`, `GAUGE_LENGTH_MM`, `MAX_DIAMETER_MM`, `PROFILE`,
`SOURCE`, `PROVENANCE`, `FIDELITY`.

Without holder geometry: all three checks return `NOT_PERFORMED` (never `PASS`).

### Fixture Collision Framework (Phases H–I)

Two new fixture-aware checks:

| Check | Method |
|---|---|
| `TOOL_FIXTURE_COLLISION` | BBOX_SWEEP |
| `PART_FIXTURE_INTERFERENCE` | BBOX_OVERLAP → PARTIAL |

`PART_FIXTURE_INTERFERENCE` returns `PARTIAL` (not `FAIL`) when fixture-part Z overlap
is detected: clamping overlap is intentional and must be reviewed by the engineer,
not silently rejected.

Without fixture geometry: both checks return `NOT_PERFORMED`.

### Machine Envelope Verification (Phases J–L)

Machine envelope checking is now WCS-aware:

- Real catalog axis limits by `MACHINE_ID`
- `WCS_TRANSFORM`: `machine_x = program_x + wcs_offset_x_mm`
- Z convention: `[-z_travel, 0]` (milling: plunge negative)
- Structured `AxisLimitViolation` per violation:
  `AXIS`, `COMMAND_POSITION`, `LIMIT_MIN`, `LIMIT_MAX`, `EXCESS_MM`, `OPERATION_ID`

TEST_ONLY machines for deterministic qualification:
- `TEST-MACHINE-LARGE-01` (1000 × 800 × 500 mm) → `PASS`
- `TEST-MACHINE-SMALL-01` (10 × 10 × 10 mm) → `FAIL`

### Gouge Check Separation (Phase Y)

Exact and conservative gouge checks are now explicitly separated:

| Check | Status | Reason |
|---|---|---|
| `GOUGE_EXACT` | `NOT_VERIFIABLE` | pythonocc/BRepAlgoAPI not installed |
| `GOUGE_CONSERVATIVE` | `PARTIAL` or `FAIL` | bbox-based, never `PASS` |

**Exact gouge verification remains `NOT_VERIFIABLE` in beta.4.**
The required exact intersection geometry engine (`pythonocc` / OpenCascade `BRepAlgoAPI`
or equivalent mesh/B-Rep intersection capability) is not installed.
This is documented as KL-07 and is correctly fail-closed.
The conservative check (`GOUGE_CONSERVATIVE`) is independent and runs successfully.

### Auto CAM DOCX Report Bridge (Phase R — KL-20 Closed)

`GET /api/autocam/{plan_id}/report/DOCX` now produces a real DOCX artifact
via the existing `docx_exporter.py`. All 6 export formats derive from a single
canonical `ReportDocument` snapshot (`REPORT_SNAPSHOT_CANONICAL=YES`):

| Format | MIME | Status |
|---|---|---|
| PDF | application/pdf | YES |
| DOCX | application/vnd.openxmlformats-officedocument.wordprocessingml.document | YES |
| XLSX | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet | YES |
| CSV | text/csv | YES |
| JSON | application/json | YES |
| ZIP | application/zip | YES |

### Verification UI Expansion (Phase M)

The Auto CAM verification panel now displays all 11 individual checks:

```
Tool-Part        | Tool-Stock      | Tool-Fixture
Holder-Part      | Holder-Stock    | Holder-Fixture
Machine Env.     | Axis Limits     | Tool Reach
Gouge (exact)    | Gouge (conserv.)| Stock Removal
```

`NOT_VERIFIABLE` and `NOT_PERFORMED` are never displayed as green `PASS`.
A dispatch lock banner confirms `DISPATCH LOCKED — engineer review required`.

### Persistence (Phase U)

All new verification fields are persisted in SQLite via `AutoCamPlanStore`:
holder/fixture references, machine limits, WCS ref, gouge fidelity, check details,
report snapshot. Safety invariants (`verification_can_dispatch_cnc=False`) survive restart.

---

## Bug Fixes / Test Fixes

- Fixed `test_collision_check_always_not_verifiable`: assertion updated to reflect
  correct `NOT_PERFORMED` semantic (check not attempted without geometry).
- Fixed `VerificationSummaryResult` TS interface to include all 11 sub-check fields.

---

## Known Limitations

| ID | Description | Status |
|---|---|---|
| KL-07 | `GOUGE_EXACT=NOT_VERIFIABLE` (no mesh intersection engine) | BY_DESIGN, fail-closed |
| KL-21 | Holder collision uses SIMPLIFIED_CYLINDER fidelity | KNOWN |
| KL-22 | Fixture geometry limited to bbox; 3D fixture input deferred | DEFERRED |
| KL-23 | Blocker navigation is message-only (no click-to-operation) | PARTIAL |
| KL-24 | Machine envelope uses catalog travel only | KNOWN |
| KL-25 | Part-fixture interference returns PARTIAL, not FAIL | BY_DESIGN |

---

## Production Readiness

**PRODUCTION_READY=NO**

This release is qualified for public beta and closed beta use.
Production use requires:

1. Exact gouge verification (`KL-07` resolved — mesh intersection engine installed)
2. 3D fixture geometry import (`KL-22` resolved)
3. Full holder profile collision (beyond SIMPLIFIED_CYLINDER, `KL-21`)
4. Human review gate for all machining operations (always required)

---

## Safety

All safety invariants are enforced by design:

```
VERIFICATION_CAN_AUTO_APPROVE=NO
VERIFICATION_CAN_RELEASE_PRODUCTION=NO
VERIFICATION_CAN_DISPATCH_CNC=NO
AUTO_CAM_CAN_DISPATCH_CNC=NO
REAL_MACHINE_WRITE_FOUND=NO
GCODE_DISPATCH_FOUND=NO
```

No path from Auto CAM result to CNC machine execution exists.
Engineer review and explicit production release are always required.

---

## Test Evidence

| Suite | Count | Result |
|---|---|---|
| Verification (holder/fixture/envelope/gouge) | 65 | PASS |
| Auto CAM orchestrator + cost | 45 | PASS |
| Reporting | 370 | PASS |
| Persistence | 175 | PASS |
| Backend API (level11–13) | 319 | PASS |
| Frontend (node:test) | 1072 | PASS |
| Ruff | — | CLEAN |
| TypeScript | — | CLEAN (exit 0) |
| Frontend build | — | CLEAN (1.16s) |

`NEW_FAILURES_INTRODUCED=0`

---

## Upgrade from beta.3

No database migration required. `AutoCamPlanStore` schema auto-migrates via
`IF NOT EXISTS` column adds. Plans created under beta.3 load correctly;
new verification fields default to `NOT_PERFORMED`.
