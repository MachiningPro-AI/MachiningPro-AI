# Measurement User Guide

## Overview

The workspace measurement tools allow you to inspect distances and edge lengths
directly in the 3D viewer. All measurements use **world-space engineering
coordinates** (millimetres by default) derived from the loaded model geometry.

> **Important:** Measurements from mesh tessellation are approximate.
> They are **not** metrology-grade inspection results and must not be used
> as a substitute for CMM or certified dimensional inspection.

---

## Selection Filter Toolbar

Located above the 3D viewport. Click a mode to change what a click selects:

| Button | Mode | Selects |
|--------|------|---------|
| BODY | BODY | The entire mesh as one entity |
| FACE | FACE | A single face (CAD_FACE or MESH_FACE) |
| EDGE | EDGE | A boundary edge (MESH_EDGE) |
| FEATURE | FEATURE | A named CAD feature (if available) |

**Clear** (×) button removes all selections.

---

## Point-to-Point Distance

1. Set mode to **FACE** or **BODY**.
2. Click the first point on the model — a yellow sphere marker appears.
3. Click the second point — the distance is calculated and added to the
   Measurement Panel below the Properties Panel.

The result is `|B − A|` in model units (Euclidean straight-line distance).

---

## Edge Length

1. Set mode to **EDGE**.
2. Click a boundary edge — the edge is highlighted and its length appears in
   the Properties Panel instantly.
3. The measurement is also added to the Measurement Panel with status
   `APPROXIMATE` (derived from mesh tessellation, not analytic geometry).

---

## Measurement Panel

Shown at the bottom of the Properties Panel when at least one measurement exists.

| Column | Description |
|--------|-------------|
| Type | POINT_DISTANCE / EDGE_LENGTH / RADIUS / DIAMETER / ANGLE |
| Value | Numeric result with unit (e.g. `12.345 mm`) |
| Status | OK (from CAD topology) or APPROXIMATE (from mesh) |

- **Clear all** (bin icon): removes all measurements.
- **Remove** (× on a row): removes that single measurement.

---

## Entity Provenance Labels

| Label | Meaning |
|-------|---------|
| CAD_FACE | Face mapped to an OCC B-Rep entity tag (STEP/IGES via gmsh) |
| MESH_FACE | Triangle group without canonical B-Rep mapping (STL, fallback) |
| MESH_EDGE | Boundary edge derived from mesh topology |

IGES files may show MESH_FACE labels even when the file contains B-Rep data,
because IGES topology support depends on file content and gmsh processing depth.

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Esc | Clear all selections |
| Shift+Click / Ctrl+Click | Add to / remove from multi-selection |

---

## Status Bar

The status bar (bottom of the workspace) shows the active selection mode and
the entity class:id of the currently selected entity, e.g. `CAD_FACE:7` or
`MESH_EDGE:0_1`.
