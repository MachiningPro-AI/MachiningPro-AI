# MachiningPro AI — Known Limitations

**Qualification:** V1_0_0_BETA_2_RELEASE_CANDIDATE_QUALIFICATION_01  
**Date:** 2026-11-26  
**Commit:** cf06487  

---

## 1. Feature Recognition

**KL-01 — STEP recognition uses surface heuristics, not exact B-Rep**  
STEP files are analyzed via GMSH OCC topology. Features are classified by surface type (PLANAR/CYLINDRICAL), circularity, and bounding-box aspect ratio. This is `GEOMETRY_RULE` confidence, not `EXACT_BREP`.  
*Impact:* Non-standard features (tapered holes, freeform pockets) may not be recognized.  
*Required user action:* Review and confirm all auto-recognized features before generating CAM.

**KL-02 — PYTHONOCC_REQUIRED=NO but recognition is not production-exact**  
Full B-Rep feature recognition (slot depth, chamfer angle, thread geometry) is not available without pythonocc-core. Current recognition covers: HOLE (cylindrical + circular boundary), PLANAR_FACE. All other feature types require manual classification.

**KL-03 — IGES files import with PARTIAL_SUCCESS**  
Complex IGES files with boundary entity types 142/141 (trimmed surfaces) may generate non-fatal warnings and be imported as `PARTIAL_SUCCESS`. Geometry is usable but may have minor tessellation gaps.

**KL-04 — PDF/image files are not 3D-importable**  
PDF and image (PNG/JPG) files cannot be imported as 3D geometry via `/api/import`. PDF drawings are supported through the separate drawing analysis workflow only.

---

## 2. CAM Generation

**KL-05 — Cutting parameters show `NOT_AVAILABLE` for most materials**  
The catalog tool is selected (GEOMETRY_RULE), but feed/speed (`vc_m_per_min`, `rpm`, `feed_mm_per_min`) may be `NOT_AVAILABLE` when no material-specific cutting data record exists. The user must provide cutting parameters manually or through the material database. Affects both Workspace CAM and Auto CAM (S08 = INSUFFICIENT_DATA).

**KL-06 — Only DRILL_CYCLE strategy is available for HOLE features in this release**  
Pocket milling (PLANAR_FACE), contouring, and tapping require additional CAM strategy modules not yet integrated into the workspace CAM API.

**KL-5B — Auto CAM tool catalog ±10% diameter tolerance allows slightly undersized tools**  
The Auto CAM tool search uses a ±10% diameter tolerance window. For a Ø10mm hole, a 9mm drill may be selected if no exact match exists. Undersized tools are within search tolerance but may produce undersized bores. User review is required. Applies to drill operations only; slot operations are constrained by width (BL-SLOT-01 fix).

**KL-12b — Auto CAM → PDF/XLSX/CSV report bridge not yet implemented**  
`POST /api/autocam/run` produces an `AUTO_CAM_SUMMARY_ONLY` plan report. The existing `/api/reports/generate` endpoint requires a `workflow_id` from the manufacturing workflow store. Auto CAM plans use a separate store. PDF/XLSX/CSV generation from Auto CAM plan_id is deferred to a future release. All plan data is persisted and retrievable via `GET /api/autocam/{plan_id}`.

---

## 3. Simulation & Verification

**KL-07 — `GOUGE_EXACT=NOT_VERIFIABLE` always**  
Exact tool-to-part surface gouge detection requires a mesh-vs-mesh comparison against the actual part surface. This is not available in the current simulation profile. `GOUGE_EXACT=NOT_VERIFIABLE` is the correct and expected state. `GOUGE_CONSERVATIVE_WARNING` is derived from bbox checks and is provided as a secondary indicator only.

**KL-08 — `FIXTURE_COLLISION=NOT_PERFORMED` without fixture geometry**  
Fixture collision checking requires the user to provide fixture geometry. Without it, the check status is `NOT_PERFORMED`. This is a correct fail-closed behavior per HR11 (missing input → NOT_PERFORMED, never PASS).

**KL-09 — `HOLDER_COLLISION=NOT_PERFORMED` without holder geometry**  
Same as KL-08. Holder geometry is required for holder collision detection. The field `holder_geometry_required=True` in the simulation response makes this explicit.

**KL-10 — `PART_GOUGE=PARTIAL` for simple drill operations**  
The bbox-based part gouge check on a drill stroke through a plate returns `PARTIAL` because the tool path intersects the part bounding box (by design — the drill goes through). This is expected behavior. `PARTIAL` does not mean machining is unsafe; it means the check is inconclusive at the bbox level.

**KL-11 — Stock removal is `VOXEL_APPROXIMATE`**  
Remaining and removed stock volumes are calculated by voxel grid approximation, not exact geometric subtraction. For small features (sub-5mm) or thin walls, the voxel approximation may over- or under-report volumes. `stock_volume_method=VOXEL_APPROXIMATE` is always disclosed in the simulation response.

**KL-12 — `MACHINE_ENVELOPE=INSUFFICIENT_DATA` without machine configuration**  
Machine envelope checking requires a registered machine with axis limits. Without a machine assignment, this check returns `INSUFFICIENT_DATA`.

---

## 4. Safety Locks (by design — not removable)

These are intentional hard locks, not defects:

- `is_dispatchable=False` — always; CNC dispatch is not enabled
- `production_released=False` — always; production release requires human approval
- `no_auto_approve=True` — always; no automatic machining approval
- `no_cnc_dispatch=True` — always; direct CNC communication is disabled
- `simulation_result_is_not_machining_approval=True` — always

---

## 5. Reporting

**KL-13 — Report generation requires a completed workflow**  
The report API (`/api/reports/generate`) requires a `workflow_id`. Standalone CAM workspace sessions without a saved workflow cannot directly generate a formatted report. Users must save to a workflow first.

**KL-14 — No logout endpoint**  
The current API does not expose a `/api/logout` POST endpoint. JWT tokens expire per their configured TTL. Browser-side logout clears the token from client storage.

---

## 6. UI / UX

**KL-15 — Large JS bundle (~1.6MB pre-gzip, ~425KB gzip)**  
The production build emits a single JS chunk. For users on slow connections, initial load may be 2–5 seconds. Code splitting is a planned optimization.

**KL-16 — `dbDemoCardSubtitle` has EN translation in TR file**  
One i18n key (`dbDemoCardSubtitle`) is present in EN but was confirmed translated in TR at line 1830. The key appears in both files; a regex false-negative in the audit tool caused an initial false alarm. This is not a user-visible leak.

---

## 7. Infrastructure

**KL-17 — Dev mode authentication via environment variables**  
In dev mode, authentication is configured via `MACHININGPRO_DEV_USERNAME`, `MACHININGPRO_DEV_PASSWORD`, and `MACHININGPRO_DEV_JWT_SECRET`. These must be set before starting the backend. Pilot mode uses `MACHININGPRO_PILOT_USERS_FILE`. Neither mode allows anonymous access.

**KL-18 — Pre-existing test: `test_no_hard_coded_cycle_times` reads a missing temp path**  
`tests/unit/api/test_cad_import_level7.py::test_no_hard_coded_cycle_times` reads from a temp restore directory that only exists after a specific test fixture setup. This failure is pre-existing at baseline commit `fb8b1f8` and is not introduced by this release. `NEW_FAILURES_INTRODUCED=0`.
