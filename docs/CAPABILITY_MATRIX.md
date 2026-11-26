# MachiningPro AI — Capability Matrix
Version: 1.0.0-beta.2 | Head: cf06487 | Date: 2026-11-26

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
| Exact Gouge Detection | NOT_IMPLEMENTED | GOUGE_EXACT=NOT_VERIFIABLE; mesh-vs-mesh deferred (KL-07) |
| Holder/Fixture Geometry Input | NOT_IMPLEMENTED | Collision checks NOT_PERFORMED without geometry (KL-08/09) |
| PFMEA | NOT_IMPLEMENTED | Deferred |
| SPC | NOT_IMPLEMENTED | Deferred |
| MES/ERP Integration | NOT_IMPLEMENTED | Deferred |
