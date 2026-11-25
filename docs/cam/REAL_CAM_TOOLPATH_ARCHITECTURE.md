# Real CAM Toolpath Architecture

**Module:** MACHININGPRO_AI_REAL_CAM_TOOLPATH_STOCK_REMOVAL_SIMULATION_01
**Date:** 2026-11-25
**Status:** ACTIVE

---

## Overview

The workspace feature-aware CAM toolpath system converts detected manufacturing
features (HOLE, POCKET, SLOT) into real CNC tool motion paths using the existing
Level-10 toolpath generation engine.

```
CAD Feature Data
  → /api/workspace-cam/feature-cam
  → Level-10 Toolpath Generators
  → ToolpathLineGroups (frontend)
  → /api/workspace-sim/run
  → Level-11 Simulation Engine
  → SimulationResult
```

---

## Toolpath Generator Integration

Generators called (Level-10 — `backend/toolpath/generators.py`):

| Feature Type | Generator | Input Model |
|-------------|-----------|-------------|
| HOLE, DRILL | `generate_drill_toolpath` | `DrillInput` |
| POCKET, POCKET_MILLING | `generate_pocket_toolpath` | `PocketInput` |
| SLOT, SLOT_MILLING | `generate_slot_toolpath` | `SlotInput` |

### Fail-Closed Rule (HR-11)

If any required geometry field is missing (center, depth, clearance), the
endpoint returns `toolpath_status=BLOCKED` with the missing fields listed in
`missing_inputs`. It never fabricates placeholder coordinates.

---

## Clearance Derivation

Clearance Z is resolved from three sources in priority order:

1. `feature.clearance_z` (USER_DEFINED)
2. `stock_bbox.max_z + max(height × 15%, 5mm)` (BBOX_DERIVED)
3. None → `clearance_z=null`, `ClearanceSource.UNKNOWN` → generator returns BLOCKED

---

## Tool Selection

Tools are selected from the real catalog (`backend/cutting_tools/library.py`)
using `ToolLibraryQuery`:

- HOLE → `ToolFamily.DRILLING` → closest diameter match
- POCKET/SLOT → `ToolFamily.MILLING` → closest diameter match (prefers END_MILL)

If no catalog tool is found → `tool_status=INSUFFICIENT_DATA`. The endpoint
never invents tool geometry.

---

## Frontend Representation

Backend toolpath groups are converted to `ToolpathLineGroup[]` for Three.js
rendering:

```
flat points [x0,y0,z0,x1,y1,z1,...] + motionType + operationRef
```

Motion type mapping:
- `APPROACH`, `LINK`, `RAPID` → `RAPID` (amber)
- `PLUNGE` → `PLUNGE` (red-orange)
- `RETRACT` → `RETRACT` (orange)
- `CUT`, `ENTRY`, `EXIT`, `RAMP`, `HELIX`, `ARC` → `FEED` (cyan)

---

## Safety Invariants

| Invariant | Value |
|-----------|-------|
| `is_dispatchable` | `false` — always |
| `production_released` | `false` — always |
| `simulation_required` | `true` — always |
| `no_cnc_dispatch` | `true` — always |
| Hard Rule 11 | Missing input → BLOCKED, never PASS |
| Hard Rule 19 | No duplicate CAM engine created |
| Hard Rule 20 | Uses existing Level-10 generators only |

---

## Coordinate System

All toolpath points use `CoordinateFrame.WCS_COORDINATES` (Part origin
aligned). The `wcs_ref` field defaults to `WCS_PART_ORIGIN`. No machine
coordinate system transformations are applied at this layer.

---

## Endpoints

### `POST /api/workspace-cam/feature-cam`

**Auth:** Bearer token required

**Request fields:**
- `file_ref` — string identifying the loaded CAD file
- `features[]` — list of `FeatureCamFeatureInput` (see models)
- `stock_bbox` — optional stock bounding box for clearance derivation
- `material_grade` — optional (not yet used for cutting parameter selection)
- `wcs_ref` — defaults to `WCS_PART_ORIGIN`

**Response fields:**
- `operations[]` — per-feature operation results with tool info, counts, status
- `toolpath_groups[]` — flat-point toolpath groups for viewport rendering
- `warnings[]` — non-fatal issues
- `safety` — safety invariant dictionary

---

## Extension Points

Future extensions (require separate PO approval):

- **Cutting parameters**: add `vc_m_per_min`, `rpm`, `feed_mm_per_min` from
  material+tool pairs via `backend/cutting_parameters/`
- **Face milling**: `generate_face_mill_toolpath` for PLANAR_FACE features
- **Profile operations**: `generate_profile_toolpath` for STEP_SHOULDER/contour
