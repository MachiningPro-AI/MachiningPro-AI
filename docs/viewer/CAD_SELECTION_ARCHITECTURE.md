# CAD Selection Architecture

## Overview

The face/edge selection system maps Three.js triangle indices to engineering
entity identifiers. It operates entirely in the viewer layer and **never alters**
engineering state (feature confirmation, WCS, tool selection, CAM planning, or
production release).

---

## Triangle-to-Face Resolution

```
raycast → faceIndex (triangle index)
         ↓
  face_groups array present?
         ├─ YES → iterate groups → faceIndex ∈ [tri_start, tri_start+tri_count)
         │        entity_tag from OCC → SelectedFace { entityClass: 'CAD_FACE', faceId: entity_tag }
         └─ NO  → SelectedFace { entityClass: 'MESH_FACE', faceId: triIndex }
```

### CAD_FACE Semantics

- Applies when the backend provides `face_groups` via gmsh OCC entity tags.
- `faceId` = OCC `entity_tag` — a canonical B-Rep identifier from the STEP/IGES
  topology, **not** a triangle or screen coordinate.
- Available for STEP and IGES files processed via `_tessellate_brep`.

### MESH_FACE Semantics

- Applies when no `face_groups` are present (STL, raw OBJ, or fallback).
- `faceId` = triangle start index — an approximation, not a canonical B-Rep id.
- UI always displays the label **"Mesh Face \<n\>"** to distinguish it clearly.

---

## Edge Extraction

Boundary edges are derived from the mesh topology via an O(n) edge-count pass:

1. For each triangle, enumerate its 3 directed edges normalised to `min_v:max_v`.
2. Accumulate occurrence counts in a `Map<string, number>`.
3. Edges with count = 1 are boundary edges → `SelectedEdge { entityClass: 'MESH_EDGE' }`.

**Important:** No OCC edge tags are available; all extracted edges are
`MESH_EDGE`, never `CAD_EDGE`.

---

## Hard Rules

| Rule | Constraint |
|------|-----------|
| HR-1 | Never fabricate B-Rep face IDs |
| HR-2 | Never fabricate edge IDs |
| HR-3 | triIndex ≠ CAD face ID unless provenance proves it |
| HR-4 | Measurements use world-space coords, never screen pixels |
| HR-5 | World-space Euclidean distance only |
| HR-6 | Source CAD geometry is never mutated |
| HR-12 | MESH_FACE/MESH_EDGE labels when provenance unavailable |

---

## Component Architecture

```
CadCamWorkspacePage
  ├─ useSelectionState()           → SelectionState, SelectionActions
  ├─ WorkspaceSelectionFilter      → mode toggle (BODY/FACE/EDGE/FEATURE)
  ├─ WorkspaceViewport
  │    ├─ raycaster (mousemove)    → onEntityHover
  │    ├─ raycaster (pointerdown)  → onEntitySelect
  │    ├─ selHighlightGroup        → emissive overlay meshes
  │    └─ measMarkersGroup         → yellow sphere markers
  ├─ WorkspacePropertiesPanel      → context-sensitive entity details
  ├─ WorkspaceMeasurementPanel     → measurement table
  └─ WorkspaceStatusBar            → mode + entity class:id
```

---

## State Immutability Contract

```
SELECTION_ENGINEERING_STATE_CHANGED = NO
FEATURE_CONFIRMATION_CHANGED        = NO
WCS_CHANGED                         = NO
CAM_STATE_CHANGED                   = NO
PRODUCTION_RELEASE_CHANGED          = NO
NO_MACHINE_WRITE                    = YES
NO_CNC_DISPATCH                     = YES
```

Selection, hover, and measurement actions update **viewer state only**
(`useSelectionState`). No action propagates to the workflow, operation summary,
tool selection, or backend CAM planning endpoints.
