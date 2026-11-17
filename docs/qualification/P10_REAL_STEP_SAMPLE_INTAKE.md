# P10 Real STEP Sample Intake Requirements

**Document class:** Qualification Requirements — P10 Phase 2  
**Status:** ACTIVE — DEFERRED_REAL_STEP_SAMPLES_REQUIRED  
**Applies to:** MachiningPro AI NEXT — P10 manufacturing workflow qualification  
**Date:** 2026-11-17  
**Supersedes/extends:** `STEP_CAM_VERIFICATION_SAMPLE_REQUIREMENTS.md` (P8 scope)  
                       `STEP_REAL_SAMPLE_INTAKE_GUIDE.md` (P3-D scope)

---

## 1. Current State

```
REAL_STEP_SAMPLE_COUNT=0
STEP_IMPORT_READY=NO          (cadquery / pythonocc-core not installed)
BREP_TOPOLOGY_READY=NO        (requires a parser)
FEATURE_EXTRACTION_READY=NO   (requires topology)
P10_STEP_QUALIFICATION_STATUS=DEFERRED_REAL_STEP_SAMPLES_REQUIRED
```

The sample directory `D:\makina_ogrenmesi\olcum_denemeleri\örnek dosyalar` contains:

| Format | Count | 3D solid? | Usable for P10? |
|--------|-------|-----------|-----------------|
| DXF    | 57    | No (2.5D) | P1–P9 DXF pipeline only |
| IGES   | 15    | Surfaces (B-spline/NURBS) | Partial — no closed B-Rep solid |
| CATIA .model | 6 | Proprietary | No — cannot parse without CATIA licence |
| DWG    | 3     | No (2D)   | No |
| PDF    | 3     | No        | No |
| STEP (.stp/.step/.p21) | **0** | — | **None** |

No action is blocked on IGES files for the P10 gate: IGES provides surface data but
not the closed B-Rep solid needed for depth-confirmed features or volumetric stock
simulation.

---

## 2. Why STEP Is the P10 Gate

The P10 workstreams that remain blocked without real STEP:

| Workstream | Current state | STEP unblocks |
|------------|---------------|---------------|
| P10-B: STEP intake | DEFERRED_NO_PARSER | First .stp file through gate |
| P10-C: Fixture geometry provenance | USER_CONFIRMED only | KNOWN provenance from STEP fixture body |
| P10-G: Stock bounding box | VOXEL_APPROXIMATION only | Exact B-Rep stock from STEP solid |
| P10-E: Hole depth validation | NOT_VERIFIABLE | Depth from B-Rep cylinder + planar cap |
| Feature recognition: HOLE_CONFIRMED | CANDIDATE only (DXF circle) | CONFIRMED from cylindrical face + loop |
| Feature recognition: POCKET_CONFIRMED | CANDIDATE only | CONFIRMED from topology adjacency |
| Gouge validation | NOT_VERIFIABLE | Verifiable once part solid is present |

---

## 3. Minimum Viable Sample Set for P10 Gate

The following 3 STEP files constitute the **minimum first intake** for P10 qualification.
All must be real files — no synthetic geometry may substitute.

### Sample P10-S1 — Simple Drilled Plate (Mandatory)

**Features required:**
- 1 through-hole, diameter 8–12 mm (matches Sandvik 860-1 catalog drills)
- 1 blind hole, diameter 8–12 mm, depth 15–25 mm
- Rectangular prismatic stock shape (matches P10-G rectangular block)

**P10 qualification value:**
- HOLE_CONFIRMED exits CANDIDATE → CONFIRMED (cylindrical face + planar cap)
- Blind hole depth verifiable against `cutting_length_mm` for a Sandvik 860-1 drill
- Part bounding box derivable from B-Rep shell → GOUGE_VALIDATED exits NOT_VERIFIABLE

**File spec:** AP214 or AP242 preferred; AP203 acceptable; units: mm

---

### Sample P10-S2 — Prismatic Part with Pocket and Slot (Mandatory)

**Features required:**
- 1 rectangular pocket, depth > 10 mm, vertical walls (0° draft)
- 1 slot (open or closed), depth > 5 mm, AR > 1.5
- Minimum 2 holes (any diameter)

**P10 qualification value:**
- POCKET_CONFIRMED from planar floor + wall faces + inner boundary loop
- SLOT_CONFIRMED from parallel walls + floor + AR
- Holder-clearance scenario: `holder_collision_validated` exits NOT_VERIFIABLE at least once
- Tests P10-C workholding: fixture body in same STEP file (optional but preferred)

**File spec:** AP214 or AP242; units: mm

---

### Sample P10-S3 — Turning Part with Cylindrical Features (Recommended, not mandatory)

**Features required:**
- Cylindrical outer body (turning stock)
- 1 groove or undercut
- 1 chamfer or face chamfer

**P10 qualification value:**
- Tests the turning-route branch of the CAM strategy
- Tests `sandvik-a25t-sducr-11` (CoroTurn 107 boring bar) geometry path
- Establishes that turning-class features are recognizable from STEP cylinders/cones

**File spec:** AP214 or AP242; units: mm

---

## 4. Acquisition Path (No Proprietary Downloads)

STEP samples must be sourced from one of the following:

| Source | License | Notes |
|--------|---------|-------|
| Designed in-house with FreeCAD | Own work | Preferred; author controls content |
| CC0/public-domain repositories (e.g. GrabCAD CC0 filter, Thingiverse CC0) | CC0 | Verify individual file licence before use |
| NIH 3D Print Exchange (CC0 public domain models) | CC0/public domain | Confirm 3D solid, not just surface |
| Manufacturer open-source sample packs | Per licence | Confirm commercial-use terms |

**Do NOT:**
- Download samples from manufacturer product pages (product geometry is proprietary)
- Use samples attached to academic papers without verifying licence
- Accept samples from unknown or unlicensed sources

---

## 5. FreeCAD Export Instructions (In-House Option)

FreeCAD 0.21+ can export any Part/PartDesign solid as STEP AP214:

1. Create a simple prismatic part (e.g. 100×80×30 mm block with 2 through-holes Ø10 mm)
2. File → Export → "STEP with colors (*.step, *.stp, *.p21)"
3. In the export dialog: format = AP214, unit = mm
4. Verify the resulting file passes the Level-1 token check:
   ```python
   from backend.interoperability.adapters.step import StepTokenAdapter
   from backend.interoperability.models import EngineeringSource
   adapter = StepTokenAdapter()
   src = EngineeringSource(source_id='test', source_format_id='STEP-AP214',
                           file_name='part.stp', notes=open('part.stp').read())
   doc = adapter.ingest(src, ...)
   print(doc.normalization_status)  # expect SUCCESS or PARTIAL (Level 1 OK)
   ```
5. Place the file in `D:\makina_ogrenmesi\olcum_denemeleri\örnek dosyalar\`
6. Run the sample scan:
   ```python
   from backend.cad_import.step_intake import scan_step_samples
   results = scan_step_samples(r"D:\makina_ogrenmesi\olcum_denemeleri\örnek dosyalar")
   print(results)  # expect DEFERRED_NO_PARSER until cadquery is installed
   ```

---

## 6. Dependency Installation (After Samples Confirmed)

Install **after** real STEP samples are confirmed in the sample directory:

```
# Option A: conda (recommended — includes geometry kernel)
conda install -c conda-forge cadquery

# Option B: pip (may require Visual C++ redistributable on Windows)
pip install cadquery

# Option C: pythonocc-core (lower-level, used by StepTokenAdapter Level 2)
conda install -c conda-forge pythonocc-core
```

**Do NOT install cadquery/pythonocc-core before samples are confirmed** — there is no
benefit to installing the library when REAL_STEP_SAMPLE_COUNT=0, and the dependency
adds ~150 MB to the environment.

After installation, update `STEP_IMPORT_READY = True` in `backend/cad_import/step_intake.py`
and re-run `scan_step_samples` on the real sample directory.

---

## 7. What Changes After First Intake

| Metric | Before (now) | After P10-S1 passes intake |
|--------|--------------|---------------------------|
| REAL_STEP_SAMPLE_COUNT | 0 | ≥ 1 |
| STEP_IMPORT_READY | False | True (cadquery installed) |
| GOUGE_VALIDATED | NOT_VERIFIABLE | PASS or FAIL (from B-Rep) |
| Feature status (holes) | CANDIDATE | CONFIRMED (with topology) |
| Part bbox provenance | UNKNOWN | KNOWN (STEP_FILE_EVIDENCE) |
| P10_STEP_QUALIFICATION_STATUS | DEFERRED | PARTIAL (1 file) or PASS (3+ files) |

---

## 8. REAL_STEP_QUALIFICATION_READY Gate

```
REAL_STEP_QUALIFICATION_READY = YES  requires ALL of:
  [1] pythonocc-core OR cadquery installed
  [2] REAL_STEP_SAMPLE_COUNT >= 3  (P10-S1, P10-S2 mandatory; P10-S3 recommended)
  [3] StepTokenAdapter Level 2 (NORMALIZED) OR cadquery ingest returns part solid
  [4] At least 1 HOLE_CONFIRMED from B-Rep topology (not CANDIDATE)
  [5] Part bounding box derived from B-Rep (provenance=KNOWN, not fabricated)
  [6] GOUGE_VALIDATED exits NOT_VERIFIABLE (PASS or FAIL on at least 1 candidate)
  [7] All safety invariants maintained: is_dispatchable=False, production_released=False
```

Current status: **[1]–[7] all BLOCKED** → REAL_STEP_QUALIFICATION_READY=NO

---

## 9. References

- `docs/qualification/STEP_CAM_VERIFICATION_SAMPLE_REQUIREMENTS.md` — P8 sample classes A–D
- `docs/qualification/STEP_REAL_SAMPLE_INTAKE_GUIDE.md` — P3-D assessment and intake guide
- `backend/cad_import/step_intake.py` — P10-B fail-closed intake gate
- `backend/interoperability/adapters/step.py` — Stage 4C token adapter (Level 0–1)
- `backend/interoperability/topology.py` — Stage 4B topology data models
- `backend/interoperability/feature_recognition.py` — Level-3 feature recognition
- `tests/unit/interoperability/test_p10_step_qualification_gate.py` — qualification gate tests
