# MachiningPro AI — Module Inventory

**Campaign:** MACHININGPRO_AI_FULL_SYNTHETIC_QUALIFICATION_AND_LOCALIZATION  
**Date:** 2026-11-12  
**Commit:** ccf4c55dcd471b88aa5e1a0821e9784c7f090d44  
**Branch:** main  

---

## Discovery Method

Performed by enumerating:
- `backend/api/*.py` — all API routers
- `backend/*/` — all domain modules
- `frontend/app/src/pages/*.tsx` — all UI pages
- `frontend/app/src/components/` — all UI components
- `backend/workflow/stage_runners/` — all workflow stages

**MODULES_DISCOVERED=38**

---

## Backend API Modules

| # | Module | Path | Description |
|---|--------|------|-------------|
| 1 | CAD Upload | `backend/api/cad_upload.py` | Universal engineering file upload (DXF, STEP, IGES, PDF, PNG) |
| 2 | Drawing Parser | `backend/api/drawing_parser.py` | Drawing annotation extraction |
| 3 | Drawing Analysis | `backend/api/drawing_analysis.py` | AI-assisted drawing analysis |
| 4 | CAD Features | `backend/api/cad_features.py` | CAD feature recognition from DXF geometry |
| 5 | GD&T Intelligence | `backend/api/gdt.py` | GD&T validation and inspection planning |
| 6 | Drawing to Process | `backend/api/drawing_to_process.py` | Drawing→process route generation |
| 7 | Engineering Import | `backend/api/engineering_import.py` | Universal format import (smoke) |
| 8 | Cutting Parameters | `backend/api/cutting_parameters.py` | Reference cutting parameter queries |
| 9 | Cutting Tools | `backend/api/cutting_tools.py` | Tool catalog lookup |
| 10 | Tool Holders | `backend/api/tool_holders.py` | Tool holder catalog |
| 11 | Tool Life | `backend/api/tool_life.py` | Empirical tool-life explorer |
| 12 | Machines | `backend/api/machines.py` | Machine catalog |
| 13 | Materials | `backend/api/materials.py` | Material library |
| 14 | Compatibility | `backend/api/compatibility.py` | Machine-holder-tool compatibility check |
| 15 | Selection | `backend/api/selection.py` | Machine/tool selection engine |
| 16 | Process Planning | `backend/api/process_planning.py` | Process plan generation |
| 17 | Process Routes | `backend/api/process_routes.py` | Route optimization |
| 18 | Manufacturing Plan | `backend/api/manufacturing_plan.py` | Full manufacturing plan |
| 19 | CAM Planning | `backend/api/cam_planning.py` | CAM operation planning |
| 20 | Toolpath | `backend/api/toolpath.py` | Toolpath generation |
| 21 | Verification | `backend/api/verification.py` | NC/toolpath verification |
| 22 | NC Generation | `backend/api/nc_generation.py` | NC program generation (offline) |
| 23 | Dispatch | `backend/api/dispatch.py` | Dispatch readiness (review-gated) |
| 24 | Scheduling | `backend/api/scheduling.py` | Job scheduling |
| 25 | Job Planning | `backend/api/job_planning.py` | Job assignment and workload |
| 26 | Monitoring | `backend/api/monitoring.py` | Shop-floor monitoring |
| 27 | Adaptive Intelligence | `backend/api/adaptive.py` | Adaptive recommendations (proposed only) |
| 28 | Digital Twin | `backend/api/digital_twin.py` | Scenario simulation |
| 29 | Workflow | `backend/api/workflow.py` | Full workflow orchestration |
| 30 | Export | `backend/api/export.py` | Plan/data exports |
| 31 | Calibration | `backend/api/calibration.py` | Shop calibration / capability |
| 32 | NC Path | `backend/api/nc_path.py` | NC file path handling |
| 33 | DXF Render | `backend/api/dxf_render.py` | DXF preview rendering |
| 34 | Auth | `backend/api/auth.py` | Authentication |

## Domain / Library Modules

| # | Module | Path |
|---|--------|------|
| 35 | Material Library | `backend/material_library/` |
| 36 | Machine Library | `backend/machine_library/` |
| 37 | Cutting Tool Library | `backend/cutting_tools/` |
| 38 | Tool Holder Library | `backend/tool_holders/` |

## Frontend Pages

| # | Page | Path | Key Features |
|---|------|------|--------------|
| F1 | Dashboard | `DashboardPage.tsx` | System status, quick links |
| F2 | CAD Import | `CadImportPage.tsx` | File upload, format detection |
| F3 | CAD Features | `CadFeaturesPage.tsx` | Feature recognition UI |
| F4 | Drawing Parser | `DrawingParserPage.tsx` | Annotation extraction |
| F5 | Technical Drawing Intelligence | `TechnicalDrawingIntelligencePage.tsx` | AI+deterministic review |
| F6 | GD&T Intelligence | `GdtIntelligencePage.tsx` | GD&T validation |
| F7 | Drawing to Process | `DrawingToProcessPage.tsx` | Full CAD-to-route workflow |
| F8 | Cutting Parameters | `CuttingParametersPage.tsx` | Reference parameter lookup + calculator |
| F9 | Tool Life | `ToolLifePage.tsx` | Empirical tool-life explorer |
| F10 | Machine Catalog | `MachineCatalogPage.tsx` | Machine reference catalog |
| F11 | Cutting Tool Catalog | `CuttingToolCatalogPage.tsx` | Tool reference catalog |
| F12 | Tool Holder Catalog | `ToolHolderCatalogPage.tsx` | Holder reference catalog |
| F13 | Material Library | `MaterialLibraryPage.tsx` | Material lookup |
| F14 | Compatibility Check | `CompatibilityPage.tsx` | Machine-holder-tool compatibility |
| F15 | Selection | `SelectionPage.tsx` | Machine and tool selection |
| F16 | Process Planning | `ProcessPlanningPage.tsx` | Full process plan UI |
| F17 | Process Routes | `ProcessRoutesPage.tsx` | Route optimization |
| F18 | Process Capability | `ProcessCapabilityPage.tsx` | Capability and cycle time |
| F19 | Manufacturing Plan | `ManufacturingPlanPage.tsx` | Manufacturing plan viewer |
| F20 | Workflow | `WorkflowPage.tsx` | Full workflow execution |
| F21 | Login | `LoginPage.tsx` | Authentication |

## Workflow Stage Runners (Backend)

adaptive_runner, base, cad_runner, cam_runner, cost_runner, cutting_data_runner, cycle_time_runner, dfm_runner, digital_twin_runner, feature_runner, job_runner, machine_runner, nc_runner, plan_runner, process_runner, scheduling_runner, toolpath_runner, tool_runner, verification_runner (19 runners)

---

**MODULES_DISCOVERED=38 (backend API+library) + 21 frontend pages + 19 workflow runners**
