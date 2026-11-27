# MachiningPro AI — Capability Matrix
Version: 1.0.0-beta.5-dev | Date: 2026-11-27

| Capability | Status | Notes |
|------------|--------|-------|
| Machine Catalog | BETA_READY | 37 machines, 11 manufacturers |
| Cutting Tool Catalog | BETA_READY | 40 tools, 5 manufacturers |
| Tool Holder Catalog | BETA_READY | 17 holders, 5 manufacturers |
| Cutting Parameters | BETA_READY | 74 REFERENCE_ONLY records; most materials NOT_AVAILABLE (KL-05) |
| Tool Life (Empirical) | BETA_READY | Taylor equation, tool wear model |
| Machine-Tool-Holder Compatibility | BETA_READY | 3-state engine, 494 COMPATIBLE |
| Configuration Selection | BETA_READY | RPM margin + reference criteria |
| Material Intelligence | PREVIEW | 19 materials, 6 API endpoints |
| Process Route Optimization | BETA_READY | 5 strategies, 10-component scoring, Pareto |
| GD&T Intelligence | BETA_READY | FCF, bonus tolerance, VC, composite FCF |
| Drawing Semantic Extraction | BETA_READY | PDF + DXF, 6 parsers |
| CAD Feature Recognition | BETA_READY | B-Rep engine, DXF, STEP L1 (HOLE + PLANAR_FACE) |
| CAD Workspace (3D viewer) | BETA_READY | STEP/IGES/STL/DXF; GMSH tessellation; face/edge selection |
| Auto CAM (20-stage pipeline) | BETA_READY | POST /api/autocam/run; HOLE/POCKET/SLOT/SHOULDER; real catalog tools; real toolpath; safety gate locked |
| CAM Workspace | BETA_READY | Feature-aware toolpath; DRILL_CYCLE; catalog tool lookup |
| Simulation Workspace | BETA_READY | Stock removal VOXEL_APPROXIMATE; 7-state verification panel |
| Process Capability | BETA_READY | IT table, tolerance/surface capability |
| Cycle Time Estimation | BETA_READY | Operation-level, bounded NC parser |
| Manufacturing Plan | BETA_READY | 12 modules, 8 tabs, approval workflow |
| Inspection Plan | BETA_READY | 20 methods, coverage rate |
| Control Plan | BETA_READY | Frequency, sampling, reaction plan |
| Export (JSON/CSV/HTML/NC Handoff) | BETA_READY | Traceability fingerprint, REFERENCE_ONLY |
| Export (PDF/DOCX/XLSX/ZIP) | BETA_READY | /api/reports/generate/{format}/download |
| Workflow Persistence | BETA_READY | SQLite (data/workflows.db); WAL mode; survives restart |
| Report History Persistence | BETA_READY | SQLite (data/report_history.db); persistent artifact store |
| STEP Level 2 B-Rep | OPTIONAL_DEPENDENCY | Requires pythonocc-core |
| VLM/OCR Analysis | OPTIONAL_DEPENDENCY | Requires Ollama + granite3.2-vision:2b |
| Multi-user Auth | NOT_IMPLEMENTED | Single shared credential |
| Exact Gouge Detection | BETA_READY | GOUGE_EXACT_METHOD=BREP_BOOLEAN_OCC; gmsh OCC B-Rep Boolean engine; STEP target input; KL-07 RESOLVED in beta.5 |
| Conservative Gouge Check | BETA_READY | GOUGE_CONSERVATIVE=PARTIAL/FAIL; bbox-based; never PASS; independent from exact |
| Holder Collision (3 checks) | BETA_READY | HOLDER_PART/STOCK/FIXTURE_COLLISION; SIMPLIFIED_CYLINDER fidelity; NOT_PERFORMED without geometry (KL-21) |
| Fixture Collision (2 checks) | BETA_READY | TOOL_FIXTURE_COLLISION + PART_FIXTURE_INTERFERENCE; bbox; NOT_PERFORMED without fixture geometry (KL-22) |
| Machine Envelope (WCS-aware) | BETA_READY | Catalog axis limits; WCS transform; structured AxisLimitViolation; PASS/FAIL/NOT_VERIFIABLE |
| Auto CAM DOCX Report | BETA_READY | DOCX via docx_exporter.py; canonical snapshot; KL-20 closed |
| Verification UI (11 checks) | BETA_READY | All tool/holder/fixture/envelope/gouge checks displayed; NOT_VERIFIABLE/NOT_PERFORMED never green |
| PFMEA | NOT_IMPLEMENTED | Deferred |
| SPC | NOT_IMPLEMENTED | Deferred |
| MES/ERP Integration | NOT_IMPLEMENTED | Deferred |
