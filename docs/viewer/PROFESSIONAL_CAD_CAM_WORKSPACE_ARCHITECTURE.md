# Professional CAD/CAM Workspace — Architecture

**Status:** PASS_CADCAM_WORKSPACE_PHASE3  
**Commit:** 7f29486 (HEAD = origin/main)  
**Date:** 2026-11-21

---

## Safety Contract (enforced at all layers)

```
IS_DISPATCHABLE=false                  — invariant, never changed
PRODUCTION_RELEASED=false              — invariant, never changed
NO_FABRICATED_GEOMETRY=YES             — viewer only renders real loaded mesh
NO_FABRICATED_TOOLPATHS=YES            — toolpath lines only from real API data
NO_FAKE_SIMULATION=YES                 — simulation calls /api/verification/simulate only
NO_MACHINE_WRITE=YES                   — no machine dispatch controls
NO_AUTO_APPROVAL=YES                   — no auto-approval or auto-confirm
VIEWER_ENGINEERING_STATE_CHANGED=NO    — animation/sim do not alter engineering state
SIMULATION_ENGINEERING_STATE_CHANGED=NO — simulation is offline only
```

---

## Route

```
/app/cad-drawing/cam-workspace
```

Registered in `frontend/app/src/App.tsx` via React Router.

---

## Component Architecture

```
CadCamWorkspacePage (frontend/app/src/pages/CadCamWorkspacePage.tsx)
│
├── MenuBar                    — File / Edit / View / CAM / Simulate / Help menus
├── WorkspaceRibbon            — Grouped command ribbon (Open, View presets, Display mode,
│                                Grid/WCS/Stock toggles, Workflow connect, Play/Pause/Stop)
├── [3-panel row]
│   ├── WorkspaceModelTree     — Model tree: Part → Geometry → CAM → WCS nodes
│   │                            Populates from wsFile + connected workflow
│   ├── WorkspaceViewport      — Three.js 3D viewport (central)
│   │                            Mesh rendering, toolpath overlay, tool pose animation,
│   │                            stock bbox, collision/gouge markers
│   └── WorkspacePropertiesPanel — Context-sensitive properties for selected node
├── WorkspaceCamPanel          — CAM operations list, toolpath timeline,
│                                animation controls, simulation controls,
│                                verification results panel
└── WorkspaceStatusBar         — File name, format, cursor XYZ, units, operation/toolpath count
```

---

## File Format Support

| Format | Render Location | Mechanism | Status |
|--------|----------------|-----------|--------|
| STL    | Client (Three.js STLLoader) | Direct file read | SUPPORTED |
| OBJ    | Client (Three.js OBJLoader) | Direct file read | SUPPORTED |
| 3MF    | Client (Three.js ThreeMFLoader) | Direct file read | SUPPORTED |
| STEP / STP | Backend tessellation | POST /api/engineering-import, returns PreviewMesh | SUPPORTED |
| IGES / IGS | Backend tessellation | POST /api/engineering-import, returns PreviewMesh | SUPPORTED |
| DXF    | 2D viewer / redirect | No 3D render | UNSUPPORTED_3D |
| PDF    | 2D viewer / redirect | No 3D render | UNSUPPORTED_3D |
| PNG/JPG | 2D viewer / redirect | No 3D render | UNSUPPORTED_3D |

Unsupported format opens show a clear status message — no blank screen, no crash.

---

## Viewport (WorkspaceViewport.tsx)

**Technology:** Three.js r170 with `OrbitControls`

**Display modes:** `shaded`, `wireframe`, `shaded_edges`, `hidden_line`, `points`

**View presets:** `iso`, `top`, `front`, `right`, `left`, `back`, `bottom`

**Toolpath colors:**
```
RAPID   → amber   (#ffb300)
FEED    → cyan    (#00e5ff)
PLUNGE  → red-orange (#ff5722)
RETRACT → orange  (#ff9800)
LINK    → gray    (#607d8b)
```

**Scene:** dark background (#0d1117), infinite grid plane, axis triad overlay,
raycasted cursor position (XYZ shown in status bar).

---

## Workflow Connection

The workspace connects to an existing MachiningPro manufacturing workflow via:

```
GET /api/workflow/{workflowId}
```

The response is parsed to extract:
- `OperationSummary[]` from `manufacturing_plan.operations`
- `ToolpathLineGroup[]` from `stages[].result.visualization.polyline_points`
- `StockBbox` from `stages[].result.visualization.stock_bbox` (fidelity=SUGGESTED unless user-confirmed)

---

## Toolpath Animation

Animation frames are extracted from `ToolpathLineGroup[]` as flat `[x,y,z]` triples.

Controls: Play / Pause / Stop / Step Forward / Step Backward / Seek (scrubber)

Speed presets: 0.25x, 0.5x, 1x, 2x, 5x, 10x

Animation loop: `setInterval` at `30 * animSpeed` FPS, state-only update (no geometry change).

Tool position source: `animFrames[animFrame]` — real toolpath points only.

---

## Simulation Service (frontend/app/src/services/simulationService.ts)

Converts `ToolpathLineGroup[]` to `VerificationSegmentFE[]` and calls:

```
POST /api/verification/simulate
Authorization: Bearer {token}
Content-Type: application/json
```

Response mapped to `SimulationState` which drives the verification panel.

---

## Backend Verification Endpoint (backend/api/verification.py)

```
POST /api/verification/simulate
```

Runs all 12 verification check types against provided toolpath segments.
Missing geometry → `NOT_PERFORMED` / `INSUFFICIENT_DATA` (never `PASS`).
`COMPLETED` simulation ≠ `VERIFIED` toolpath.

---

## Stock

Stock is sourced from workflow API visualization data as `fidelity=SUGGESTED`.
Display clearly shows `SUGGESTED STOCK` when not user-confirmed.
No fabricated stock dimensions.

---

## Stock Removal Simulation

```
STOCK_REMOVAL_SIMULATION_READY=NO
```

The backend `run_simulation` performs geometric checks but does not compute
voxel/boolean stock removal. Volume fields (`initial_stock_volume_mm3`,
`remaining_stock_volume_mm3`, `removed_volume_mm3`) are populated only when
the backend has sufficient geometry data; otherwise `null`.

No cosmetic/fake stock removal animation is generated.

---

## Collision / Gouge Visualization

Collision points and gouge points are sourced **only** from:
```
POST /api/verification/simulate → visualization.collision_points
POST /api/verification/simulate → visualization.gouge_points
```

No fabricated markers. Missing fixture/holder geometry reports
`NOT_VERIFIABLE` or `INSUFFICIENT_DATA`, not `PASS`.

---

## Development Start

### Backend (port 8001 standard / 8002 when 8001 occupied)

```sh
# From repo root
python -m uvicorn backend.api.app:app --host 127.0.0.1 --port 8001 --reload
```

Requires one of:
- `MACHININGPRO_PILOT_USERS_FILE=<path>` (pilot mode)
- `MACHININGPRO_DEV_USERNAME=<u> MACHININGPRO_DEV_PASSWORD=<p> MACHININGPRO_DEV_JWT_SECRET=<s>` (dev mode)

Health check: `GET http://127.0.0.1:8001/api/health`

### Frontend (port 8003+)

```sh
cd frontend/app
npm run dev -- --port 8003 --host 127.0.0.1
```

Vite dev proxy (`vite.config.ts`): `/api → http://127.0.0.1:8001`

**Note:** If port 8001 is occupied by another service, start the MachiningPro backend
on a different port and update `vite.config.ts` proxy target accordingly.

---

## Test Baseline (Phase 3 — 2026-11-21)

| Suite | Count | Status |
|-------|-------|--------|
| Frontend unit tests | 895 | PASS |
| Backend relevant tests (manufacturing/workflow/step_brep/persistence) | 1954 | PASS |
| Backend pre-existing failures (P10 blockers) | 25 | FAIL (pre-existing, not from workspace) |
| TypeScript | — | CLEAN |
| Production build | — | CLEAN |
| Ruff (workspace files) | 2 | Auto-fixable import sort (pre-existing) |

New failures introduced by workspace phase: **0**

---

## Engineering State Immutability

The following operations do NOT alter any engineering state:
- File open (adds display mesh only)
- Rotate / Pan / Zoom / Fit
- Select feature or operation
- Play / Pause / Stop / Seek animation
- Run simulation (reads and displays results only)

The workspace cannot:
- Confirm a feature
- Confirm WCS
- Approve a CAM operation
- Release to production
- Dispatch to CNC

---

## File Locations

```
frontend/app/src/pages/CadCamWorkspacePage.tsx     — page root, state management
frontend/app/src/components/workspace/
  WorkspaceViewport.tsx      — Three.js 3D viewport
  WorkspaceModelTree.tsx     — model tree panel
  WorkspacePropertiesPanel.tsx — properties panel
  WorkspaceRibbon.tsx        — command ribbon
  WorkspaceCamPanel.tsx      — CAM + simulation panel
  WorkspaceStatusBar.tsx     — status bar
  WorkspaceTypes.ts          — shared types and constants
frontend/app/src/services/simulationService.ts     — simulation API client
backend/api/verification.py                        — /api/verification/simulate endpoint
backend/verification/simulation.py                 — simulation engine
backend/verification/models.py                     — request/response models
```
