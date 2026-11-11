# MachiningPro AI — Customer Demo Guide
Version: 0.5.0-demo | Branch: work/next-stage

## Product Overview
MachiningPro AI transforms engineering drawings and CAD models into traceable, deterministic manufacturing plans with inspection and control plan generation. Every result is REFERENCE_ONLY and requires engineer validation before manufacturing use.

## Supported Inputs
| Format | Support Level | Notes |
|--------|--------------|-------|
| DXF 2D | FULL | Geometric feature recognition |
| Vector PDF | FULL | Text/annotation extraction |
| STEP AP203/214 | LEVEL_1 | Entity inventory; Level 2 requires pythonocc-core |
| Manual req_set JSON | FULL | All pages accept structured JSON input |
| STL / OBJ / 3MF | VIEWER_ONLY | 3D mesh viewer; no feature extraction |

## Demo Part — MP-DEMO-001 (Precision Hydraulic Valve Spool)
- Material: 42CrMo4 alloy steel
- Drawing number: MP-DEMO-001, Revision A
- Features: Main OD ⌀40 f7, Land OD ⌀38 h6, Groove 6 ±0.015, OAL 120 ±0.1
- GD&T: Circular runout ⌀0.005/A, Port position ⌀0.1/A/B
- Surface finish: Ra 0.4 µm (main OD), Ra 0.8 µm (land)
- Thread: G1/4 BSP (port)
- CUSTOMER_DATA_USED=NO — fully synthetic

## 5-Minute Demo Script
1. **Login** — enter credentials → Dashboard
2. **Manufacturing Plan page** → click "Load Demo Part (Hydraulic Spool)"
3. Show DRAFT status + characteristics count + REFERENCE_ONLY disclaimer
4. **Inspection Plan tab** — show method coverage (CMM, surface roughness tester, ring gauge)
5. **Control Plan tab** — show sampling frequency, reaction plan
6. **Review tab** → Review → Approve (gate enforcement demonstration)
7. **Export tab** → Download HTML → show traceability fingerprint

## 10-Minute Demo Script
1. Login → Dashboard (explain deterministic philosophy)
2. Resources: Machines → show INTEGREX i-200S detail
3. Engineering: Compatibility Check → select machine + holder + tool → COMPATIBLE
4. Planning: Drawing Parser → describe spool drawing → confirm detections
5. Process Routes → enter features → generate BALANCED strategy → compare routes
6. Click "Generate Manufacturing Plan →"
7. Manufacturing Plan (pipeline prefill) → all 8 tabs
8. Approve → Export HTML

## 20-Minute Technical Demo
1. Login + positioning statement
2. Machine + Tool + Holder catalog exploration
3. Compatibility and Configuration Selection
4. Technical Drawing Intelligence (PDF upload, Ollama optional)
5. Drawing Parser (DXF upload, confirm requirements)
6. CAD Features (STEP Level 1 / DXF, feature tree, fusion)
7. Route Optimization (BALANCED vs LOWEST_RISK strategy comparison)
8. Generate Manufacturing Plan (pipeline handoff)
9. All 8 Manufacturing Plan tabs
10. Process Capability (tolerance evaluation, IT grade)
11. GD&T Intelligence (FCF validation, bonus tolerance, VC)
12. Export HTML + JSON + NC Handoff package
13. Safety summary (FABRICATED_*=NO, AUTO_GENERATED_PLAN_MARKED_APPROVED=NO)

## Pipeline Navigation
Drawing Parser → CAD Features → Process Routes → Manufacturing Plan → Export

Handoff buttons appear automatically when a session/requirements are confirmed.
Pipeline context persists within the browser session (cleared on refresh).

## Sidebar Navigation
All pipeline pages are accessible from the sidebar under:
- CAD & Drawing: CAD Import, Technical Drawing Intelligence, CAD Features
- Planning & Quality: Drawing Parser, GD&T Intelligence, Route Optimization, Process Capability, Manufacturing Plan

## Demo Credentials
Ask your MachiningPro demo operator for the current credentials.
Never commit credentials to the repository.

| Module | Route | Notes |
|--------|-------|-------|
| Machine Catalog | `/app/resources/machines` | 15 machines, 4 manufacturers |
| Cutting Tool Catalog | `/app/resources/cutting-tools` | 18 tools, ISO material groups |
| Tool Holder Catalog | `/app/resources/tool-holders` | 17 holders, 5 interfaces |
| Cutting Parameters | `/app/engineering/cutting-parameters` | REFERENCE_ONLY evidence |
| Compatibility Check | `/app/engineering/compatibility` | 3-state engine: COMPATIBLE / INCOMPATIBLE / INSUFFICIENT_DATA |
| Configuration Selection | `/app/engineering/configuration-selection` | Deterministic RPM-margin selection |
| Process Planning / NC | `/app/planning-quality/process-planning` | Full NC engineering review, export, traceability |
| CAD Import | `/app/cad-drawing/cad-import` | DXF, STEP, IGES, STL, NC |
| Drawing Intelligence | `/app/cad-drawing/technical-drawing-intelligence` | Advisory AI (local Ollama only) |
| Tool Life Explorer | `/app/engineering/tool-life` | Empirical dataset (requires `MACHININGPRO_TOOLLIFE968_SOURCE_PATH`) |
| Manufacturing Workflow | `/app/workflow/manufacturing-analysis` | Level 19: 19-stage end-to-end analysis (see Step 06) |
| GD&T Intelligence | `/app/planning-quality/gdt-intelligence` | EPIC_04B — engineer review required |
| Drawing Parser | `/app/planning-quality/drawing-parser` | EPIC_04C — detections require confirm/edit/reject |
| Process Routes | `/app/planning-quality/process-routes` | EPIC_04E — engineer selects preferred route |
| Manufacturing Plan | `/app/planning-quality/manufacturing-plan` | EPIC_04G — explicit review/approve, never auto-approved |
| Process Capability | `/app/planning-quality/process-capability` | EPIC_04F — calibration profiles |

## Review Gates (Required Human Actions)
- Drawing extraction detections: confirm/edit/reject each
- GD&T interpretation: PENDING_REVIEW (engineer must approve)
- Feature associations: confirm/reject
- Route selection: engineer selects preferred route
- Manufacturing plan approval: explicit /review then /approve (never auto-approved)

## Safety Boundaries
- AUTO_GENERATED_PLAN_MARKED_APPROVED=NO — always DRAFT on generation
- KEY_CHARACTERISTIC — engineer-only designation, never auto-assigned
- INSUFFICIENT_DATA returned for unknowns — never fabricated
- No production release authorization in this system
- All exports marked REFERENCE_ONLY

## Known Limitations
- In-memory storage only (restart clears all sessions)
- STEP Level 2 feature recognition requires pythonocc-core (see STEP_LEVEL2_DEPENDENCY.md)
- XLSX export deferred
- Playwright browser tests require: cd frontend/app && npx playwright install --with-deps chromium
- VLM/OCR analysis requires local Ollama with granite3.2-vision:2b
- PipelineContext is in-memory: browser refresh loses pipeline state
- No multi-user authentication on most endpoints

## Deployment
See DEPLOYMENT.md and render.yaml. Deploy to Render from `main` branch after merging work/next-stage.

---

## 3. Recommended Demo Workflow (Scenarios A–E)

### Step 01 — Catalog

1. Open **Machines** → select a machine (e.g. INTEGREX i-200S)
2. Note spindle RPM limit
3. Open **Cutting Tools** → select an end mill
4. Open **Tool Holders** → select a matching holder

**Key point:** All catalog data has provenance. Show the "Source" section on any detail card.

### Step 02 — Compatibility Check

1. Open **Compatibility Check**
2. Select the machine, holder, and tool from step 01
3. Choose an operation and ISO material group
4. Run evaluation → show COMPATIBLE result and rule trace

**Key point:** Every rule is deterministic and traceable. Show the rule ID and reason code.

### Step 03 — Configuration Selection

1. Open **Configuration Selection**
2. Enter operation, ISO group, cutting speed, diameter
3. Run → show ranked candidates with RPM margin criterion
4. Show rejected candidates and their disqualification reasons

**Key point:** No black-box ranking. Every criterion is shown explicitly.

### Step 04 — Process Planning with NC Review

1. Open **Process Planning**
2. Enter part name, material group, add 2–3 operations
3. Generate plan → show PLANNED steps with tooling and cutting parameters
4. Paste a sample NC program (G0/G1 linear, M3/M6):
   ```
   %
   O0001
   G21 G90 G94
   M6 T1
   M3 S3500
   G0 X0 Y0 Z5.
   G1 Z-2. F200.
   G1 X50. F300.
   G1 Y50.
   G1 X0.
   G1 Y0.
   G0 Z5.
   M5
   M30
   ```
5. Click **Analyze NC** → show engineering review (PASS_WITH_EVIDENCE or PASS_WITH_ADVISORIES)
6. Show traceability section: SHA-256 fingerprints, audit log

### Step 05 — Export & Traceability

1. Export findings as **CSV** → show formula-injection safety (tab-prefix on flagged cells)
2. Export **JSON** → show `schema_version`, safety flags
3. Open **Print** → show "NOT AN APPROVAL DOCUMENT" disclaimer
4. Show **NC Change Review**: load the prior JSON export as baseline, modify one S-word, re-analyze, compare

### Step 06 — Manufacturing Workflow (Level 19)

1. Open **Manufacturing Analysis** (`/app/workflow/manufacturing-analysis`)
2. Click **Choose File** → select a `.dxf`, `.igs`, `.iges`, `.stp`, or `.step` file
   - File is uploaded to the server immediately; green checkmark confirms
   - Supported formats: DXF (group-code 0 header), IGES (S-section col 73), STEP (ISO-10303-21)
   - Maximum upload size: 50 MB (configurable via `CAD_UPLOAD_MAX_BYTES`)
3. Enter Material (e.g. `AL6061`), Quantity, Stock Reference
4. Choose Objective and Analysis Mode
5. Click **RUN MANUFACTURING ANALYSIS**
6. Watch 19 stages progress (left panel): CAD → Geometry → Features → DFM → Process → Machine → Tool → Cutting Data → Cycle Time → Cost/RFQ → CAM → Toolpath → Verification → NC → Scheduling → Assignment → Adaptive AI → Digital Twin → Final Plan
7. Click any stage to see its status, warnings, errors, and blocking reasons
8. Final Plan dashboard shows safety flags: **PRODUCTION_APPROVED=NO**, **DISPATCHED=NO**, **MACHINE_STARTED=NO**

**Key safety boundary:** The plan is a proposal only. No CNC machine is written to, no job is auto-dispatched, and no parameter change is applied automatically. All outputs require engineering review.

---

## 4. Tool Life Explorer (if dataset configured)

- Set `MACHININGPRO_TOOLLIFE968_SOURCE_PATH` to the dataset path
- Restart backend
- Open **Tool Life** → empirical exploration with lifecycle charts
- If dataset not configured: page shows "Dataset Not Configured" message (not a crash)

---

## 5. Drawing Intelligence (if Ollama configured)

- Requires local Ollama with a vision-capable model
- Upload a technical drawing (PDF, JPEG, PNG, DXF, STEP, NC, STL)
- All AI suggestions require human review before use
- Drawing Intelligence is advisory only — deterministic results take precedence

---

## 6. Language Switch (EN/TR)

- Use the language toggle in the top bar
- All customer-visible strings translate
- Verify: NC review labels, catalog headers, compatibility result text

---

## 7. Responsive Layout

- Test at 390px (mobile), 1024px (tablet), 1440px (desktop)
- Process Planning NC section stacks vertically on mobile
- No horizontal scroll at any tested width

---

## 8. What NOT to Claim

| Do Not Say | Reason |
|------------|--------|
| "The NC program was executed" | Text is parsed as data only |
| "This is production-approved" | Alpha preview only |
| "AI made the decision" | All decisions are deterministic; AI is advisory |
| "The hashes are digital signatures" | SHA-256 detects change; not a PKI signature |
| "The change review is an approval" | Explicitly labeled NOT AN APPROVAL DOCUMENT |
| "The workflow plan is approved" | PRODUCTION_APPROVED=NO; engineering review required |
| "The workflow dispatched a job" | DISPATCHED=NO; no machine dispatch from this UI |
| "The machine was started" | MACHINE_STARTED=NO; no CNC write of any kind |
| "Feed rates are verified against the machine" | Machine feed_rate_max not in catalog (deferred) |

---

## 9. Known Demo Limitations

- G96 CSS RPM derivation: deferred
- R-format arcs (G2/G3 R…): not parsed (use IJK format)
- M98/M99 subprograms: UNSUPPORTED_SEMANTICS
- Macro variables (#): UNSUPPORTED_SEMANTICS
- Machine feed-rate limit check: deferred (no feed_rate_max in catalog)
- Cycle time = feed-distance only (no rapid, tool-change, or acceleration time)

---

*See [`docs/nc/NC_MODULE_RELEASE.md`](nc/NC_MODULE_RELEASE.md) for the full NC feature matrix and demo scenarios A–J.*

## Version
RC1 (Levels 1–20) + EPIC_04A–EPIC_05 remote capabilities integrated.
