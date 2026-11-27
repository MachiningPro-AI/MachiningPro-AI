# MachiningPro AI — Known Limitations

**Qualification:** V1_0_0_BETA_4_RELEASE_CANDIDATE_QUALIFICATION_01  
**Date:** 2026-11-27  
**Commit:** 852ca0a  

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

**KL-12b — RESOLVED** ~~Auto CAM → PDF/XLSX/CSV report bridge not yet implemented~~  
Resolved in beta.3: `GET /api/autocam/{plan_id}/report/{fmt}` generates PDF/XLSX/CSV/JSON/ZIP reports. Auto CAM plan persistence is now SQLite-backed (`data/autocam_plans.db`). Plans survive backend restart.

**KL-19 — `other_cost` always NOT_PROVIDED; max completeness 87.5%**  
The `AutoCamCostInput` model has no `other_cost_total` field. The `other_cost` category is structurally always `NOT_PROVIDED`. As a result, `COMPLETE_COST_ESTIMATE` (100% completeness) is never reached; maximum is `PARTIAL_COST_ESTIMATE` at 87.5% (7/8 categories). This is intentional per HR-8 (no fabricated totals). Users requiring a complete total should include other costs in `material_cost_total`.

**KL-20 — RESOLVED (beta.4)** ~~Auto CAM report does not expose DOCX format~~  
Resolved in beta.4: `GET /api/autocam/{plan_id}/report/DOCX` now produces a real DOCX artifact via `docx_exporter.py`. All 6 formats (PDF/DOCX/XLSX/CSV/JSON/ZIP) derive from a single canonical `ReportDocument` snapshot (`REPORT_SNAPSHOT_CANONICAL=YES`).

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

---

## 8. Beta.4 New Limitations

**KL-21 — Holder and fixture collision use SIMPLIFIED_CYLINDER fidelity**  
Holder geometry is modeled as a cylinder (diameter × gauge length). Full 3D holder profile collision (HSK tapers, retention knobs, side protrusions) is not checked. `HOLDER_GEOMETRY_FIDELITY=SIMPLIFIED_CYLINDER` is always disclosed in check results. Users must review toolholder clearance with actual CAM post-processor data for production.

**KL-22 — Fixture geometry limited to bbox; STEP/IGES fixture input deferred**  
The fixture collision framework accepts geometry source declarations (STEP/IGES/STL/PROJECT_ARTIFACT) but actual 3D fixture geometry is not yet imported. Collision checks use a bounding-box approximation when dimensions are provided, or return `NOT_PERFORMED` when no fixture geometry is supplied. Upload of fixture CAD files is deferred.

**KL-23 — Blocker navigation is message-only (no click-to-operation)**  
Verification blockers display stage code and message. Click-to-navigate (select the relevant operation, highlight the offending toolpath segment, move camera) is not yet implemented. `VERIFICATION_BLOCKER_NAVIGATION_READY=PARTIAL`.

**KL-24 — Machine envelope uses catalog travel; actual installed options not queried**  
Axis travel limits are sourced from `MACHINE_LIMIT_SOURCE=CATALOG`. Installed rotary tables, tombstones, or machine-specific runtime configurations that reduce effective travel are not accounted for. Users must verify envelope against actual machine setup.

**KL-25 — Part-fixture interference returns PARTIAL, not FAIL**  
Fixture clamping intentionally contacts the part in Z. `PART_FIXTURE_INTERFERENCE` returns `PARTIAL` (flagged for review) rather than `FAIL` for Z-overlap. This is correct semantics but requires engineer review for every overlap detected.

**KL-07 — `GOUGE_EXACT=NOT_VERIFIABLE` always (unchanged from beta.3)**  
Exact tool-to-part surface gouge detection requires `pythonocc`/`BRepAlgoAPI` or equivalent mesh intersection capability, which is not installed. `GOUGE_EXACT=NOT_VERIFIABLE` is the correct and expected behavior. This is a production-readiness limitation, not a public-beta blocker, because fail-closed semantics are preserved: the check never returns PASS.
