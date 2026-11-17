# STEP CAM Verification — Sample Requirements for P8 Qualification

**Document class:** Qualification Requirements  
**Status:** DRAFT — P8-F  
**Applies to:** MachiningPro AI NEXT — offline geometric verification pipeline  
**Date:** 2026-11-16

---

## 1. Purpose

This document defines the minimum STEP (ISO 10303) sample set required to qualify P8
offline geometric verification beyond its current 2.5D DXF-only baseline.

The P8 architecture audit identified:

```
REAL_STEP_SAMPLE_COUNT=0
REAL_IGES_SAMPLE_COUNT=15
P8_STEP_QUALIFICATION_STATUS=DEFERRED_REAL_SAMPLE_REQUIRED
```

STEP samples are required because:

1. STEP carries full 3D solid geometry (B-rep), enabling actual part bounding-box derivation.
2. Without a part solid, GOUGE checks remain NOT_VERIFIABLE (HARD RULE 19).
3. Without a stock solid, stock-removal simulation is geometry-approximate only.
4. Z-geometry, flute geometry, and holder geometry cannot be fabricated — STEP is the
   only qualified path to KNOWN provenance for those fields.

---

## 2. Hard Rules That Gate STEP Qualification

The following hard rules (see `docs/qualification/`) remain active until STEP samples
are available:

| Rule | Constraint |
|------|-----------|
| HR-19a | Do NOT claim full 3D collision validation from 2D DXF alone |
| HR-19b | Do NOT fabricate Z geometry from 2D cross-section |
| HR-19c | UNKNOWN remains UNKNOWN — missing geometric evidence is a blocker |
| HR-19d | Do NOT mark COLLISION_VALIDATED=YES unless actual geometry test ran |

None of these constraints change with STEP availability alone — they change only when
actual geometry tests have passed on validated STEP samples.

---

## 3. Required Sample Classes

### Class A — Prismatic Part (Mandatory)

**Minimum count:** 2 samples  
**Geometry:** Rectangular solid with through-holes and blind holes  
**Why mandatory:** Covers the dominant use-case for P7 toolpaths (drilling, pocketing)  
**Qualification criteria:**

- Part bounding box derivable from B-rep shell
- At least one through-hole and one blind hole in the STEP solid
- Hole diameter matches a catalog tool (exact match, not compatible)
- Z-depth verifiable against catalog `cutting_length_mm` for a Sandvik 860-1 drill

**Acceptance gate:** `part_bbox_provenance=KNOWN`, `tool_reach_validated` ∈ {PASS, FAIL}
(not INSUFFICIENT_DATA or NOT_VERIFIABLE)

---

### Class B — Prismatic Part with Pocket (Mandatory)

**Minimum count:** 1 sample  
**Geometry:** Closed pocket requiring end-mill reach beyond shoulder  
**Why mandatory:** Tests holder-clearance scenario — the case where `holder_length_mm`
matters and the UNKNOWN provenance of holder geometry is a real blocker  
**Qualification criteria:**

- Pocket depth > 10 mm
- Wall draft angle 0° (vertical walls)
- Associated holder geometry documented (at minimum: holder diameter, length from gauge)

**Acceptance gate:** `holder_collision_validated` exits NOT_VERIFIABLE at least once
(PASS or FAIL — either confirms geometry was present and checked)

---

### Class C — Contoured Surface Part (Recommended, Not Mandatory for P8)

**Minimum count:** 1 sample  
**Geometry:** Non-planar surface requiring 3-axis simultaneous motion  
**Why not mandatory at P8:** Current verification engine check coverage is primarily
static and 2.5D envelope; full 3D surface-collision requires the STEP solid and an
active simulation against each toolpath segment  
**Qualification criteria:**

- Minimum curvature radius ≥ tool_radius in the toolpath
- STEP shell is water-tight (no open edges)

**Acceptance gate:** Deferred to P9 (3-axis simultaneous motion scope)

---

### Class D — Assembly or Fixture Reference (Recommended, Not Mandatory for P8)

**Minimum count:** 1 sample  
**Geometry:** STEP file containing both part and vise/fixture as separate bodies  
**Why needed:** Enables fixture provenance upgrade from USER_CONFIRMED to KNOWN  
**Qualification criteria:**

- Fixture body has a recognized `stable_id` matching the machine catalog
- Coordinate system matches machine WCS (not local part CS)

**Acceptance gate:** `fixture_inputs[0].provenance == GeometryFieldProvenance.KNOWN`

---

## 4. Minimum Viable Sample Set for P8 Gate

| Class | Count | Mandatory | Gate |
|-------|-------|-----------|------|
| A — Prismatic (holes) | 2 | YES | P8 |
| B — Prismatic (pocket) | 1 | YES | P8 |
| C — Contoured | 1 | NO | P9 |
| D — Assembly+Fixture | 1 | NO | P9 |

**P8 minimum: 3 STEP files (2× Class A + 1× Class B)**

---

## 5. File Requirements

Each STEP sample must satisfy:

1. Format: AP214 or AP242 (AP203 acceptable if no color/material required)
2. Minimum entity coverage: closed shell B-rep, face normals consistent
3. Unit declaration: mm (LENGTH_UNIT = MILLIMETRE)
4. No external file references (embedded geometry only)
5. Origin documented: either designed in-house (preferred) or CC0/public-domain sourced

---

## 6. Verification Scope Changes After STEP Integration

| Scope Label | Current (DXF-only) | After STEP Class A |
|-------------|--------------------|--------------------|
| `TOOLPATH_WIRED` | YES | YES |
| `TOOL_REACH_CHECK` | INSUFFICIENT_DATA (flute=0/18) | PASS/FAIL |
| `STATIC_ENVELOPE_CHECK` | PASS/FAIL (travel known) | PASS/FAIL |
| `GOUGE_CHECK` | NOT_VERIFIABLE | PASS/FAIL |
| `STOCK_CHECK` | PASS/FAIL (approximate) | PASS/FAIL (exact) |
| `COLLISION_CHECK_3D` | NOT_PERFORMED | PASS/FAIL |
| `COLLISION_VALIDATED=YES` | NEVER | Allowed when check=PASS |

---

## 7. Relationship to P7 Real Samples

The 15 IGES samples in `D:\makina_ogrenmesi\olcum_denemeleri\örnek dosyalar` provide
2D cross-section geometry used in P7 feature recognition. They are NOT STEP solids and
do NOT satisfy P8 sample requirements. P8 qualification requires separate STEP files.

---

## 8. Procurement Path

Recommended sources (in order of preference):

1. **In-house design:** Author a minimal prismatic part meeting Class A/B criteria in the
   project's CAD reference directory. This gives full provenance and version control.
2. **CC0 public domain:** NIST Test CAD Models (STEP AP214/AP242), publicly released under
   open terms. Confirm license before use.
3. **Customer-supplied:** Any customer STEP file used for qualification must be anonymized
   (feature geometry preserved, metadata/identification removed) before committing.

---

## 9. What Changes After STEP Samples Are Qualified

- `P8_STEP_QUALIFICATION_STATUS` moves from `DEFERRED_REAL_SAMPLE_REQUIRED` to `PASS`
- `part_bbox_provenance` can exit `UNKNOWN` for STEP-sourced candidates
- `GOUGE_CHECK` can exit `NOT_VERIFIABLE`
- A new test file `tests/unit/manufacturing/test_p8f_step_integration.py` will be required
  covering at minimum: bbox extraction, gouge check with known solid, end-to-end STEP→P8

---

---

## 10. P9-F Update (2026-11-16)

```
P9_F_STATUS            = DEFERRED
REAL_STEP_SAMPLE_COUNT = 0   (unchanged from P8-F)
```

P9 adds fixture geometry (P9-C), holder geometry wiring (P9-B), flute-length
enrichment (P9-A), and voxel stock wiring (P9-D) for the existing DXF-based
pathway.  None of these change the STEP qualification gate.

P9-F (STEP-based solid verification) remains DEFERRED for the same reason as
P8-F: no real STEP samples are available.

The following checks added or made more visible in P9 remain `NOT_VERIFIABLE`
until real STEP samples satisfy the gate above:

| Check | P9 State | STEP Required? |
|-------|----------|----------------|
| `gouge_validated` | NOT_VERIFIABLE | YES |
| `part_bbox_provenance` | UNKNOWN | YES |
| Solid 3D tool reach | NOT_VERIFIABLE | YES |
| Full 3D collision (STEP fixture) | NOT_PERFORMED | YES |

P9-F will be executed as a separate qualification cycle once Class A + Class B
STEP samples (defined in §3 above) are provided.

**STEP_CAM_VERIFICATION_QUALIFIED = NO**  
**Next action: Provide at least 3 STEP samples (2× Class A + 1× Class B).**

---

*This document does not change any hard rule. UNKNOWN remains UNKNOWN until actual
geometric evidence is present and tested.*

---

## 11. P10-B Update — 10 Required Sample Classes (2026-11-17)

```
P10_B_STATUS              = DEFERRED_REAL_STEP_SAMPLE_REQUIRED
REAL_STEP_SAMPLE_COUNT    = 0   (unchanged from P9-F)
STEP_IMPORT_READY         = NO  (cadquery not installed)
```

P10-B extends the sample class definition to 10 classes to cover the full range
of features expected in production NC generation. The gate remains unchanged:
no STEP files in `D:\makina_ogrenmesi\örnek dosyalar` and cadquery not installed.

### Complete 10-Class Required Sample Set

| Class | Name | Mandatory | Min Count | Gate |
|-------|------|-----------|-----------|------|
| 1 | Simple Drilling Block | YES | 2 | P8 |
| 2 | Blind-Hole Prismatic | YES | 1 | P8 |
| 3 | Through-Hole Prismatic | YES | 1 | P8 |
| 4 | Pocket Feature | YES | 1 | P9 |
| 5 | Slot Feature | YES | 1 | P9 |
| 6 | Step Feature | YES | 1 | P9 |
| 7 | Multi-Depth Prismatic | NO | 1 | P10 |
| 8 | Multi-Feature Prismatic | NO | 1 | P10 |
| 9 | Turned Part (round stock) | NO | 1 | P10 |
| 10 | Multi-Setup Part | NO | 1 | P10 |

**P8 minimum (3 files): Classes 1 (×2) + 2 (×1)**
**P9 minimum (6 files): Classes 1–6 each ×1 (minimum)**
**P10 minimum (10 files): All 10 classes**

---

#### Class 1 — Simple Drilling Block

**Geometry:** Rectangular solid with ≥2 through-holes and ≥1 blind hole.  
**Tool coverage target:** Sandvik 860-1 drill (catalog flute_length_mm available).  
**Qualification criteria:**
- part_bbox derivable from closed B-rep shell
- Hole diameters match catalog tools (Sandvik 860-1 series, 3–24 mm range)
- tool_reach_validated exits INSUFFICIENT_DATA → PASS or FAIL

**Acceptance gate:** `part_bbox_provenance=KNOWN`, tool_reach_validated ∈ {PASS, FAIL}

---

#### Class 2 — Blind-Hole Prismatic

**Geometry:** Prismatic block with ≥2 blind holes at different depths.  
**Why mandatory:** Verifies tool reach FAIL when depth > flute_length_mm.  
**Qualification criteria:**
- One hole depth > available flute_length_mm for that diameter → reach=FAIL
- One hole depth ≤ flute_length_mm → reach=PASS
- Both confirmable from STEP B-rep only

**Acceptance gate:** tool_reach_validated=FAIL confirmed from STEP depth, not assumed.

---

#### Class 3 — Through-Hole Prismatic

**Geometry:** Prismatic block with through-holes only (consistent Z entry/exit).  
**Why mandatory:** Covers standard drill-through use case; validates stock removal path.  
**Qualification criteria:**
- stock_removal_validated exits NOT_VERIFIABLE (requires voxel simulation)
- Entry and exit faces both on the closed shell

**Acceptance gate:** `stock_removal_validated` ∈ {PASS, FAIL}

---

#### Class 4 — Pocket Feature

**Geometry:** Prismatic block with ≥1 closed pocket, pocket depth > 10 mm.  
**Why mandatory:** Tests holder collision scope — holder length matters.  
**Qualification criteria:**
- Pocket depth > 10 mm with vertical walls (0° draft)
- Holder geometry documented (body_diameter_mm, length_from_gauge_mm)

**Acceptance gate:** `holder_collision_validated` exits NOT_VERIFIABLE.

---

#### Class 5 — Slot Feature

**Geometry:** Prismatic block with ≥1 open-ended slot (end-mill accessible).  
**Why mandatory:** Exercises lateral approach path; validates RAPID_CLEARANCE check.  
**Qualification criteria:**
- Slot width matches end-mill catalog diameter
- rapid_clearance_validated exits NOT_VERIFIABLE

**Acceptance gate:** `rapid_clearance_validated` ∈ {PASS, FAIL}

---

#### Class 6 — Step Feature

**Geometry:** Prismatic block with ≥2 Z levels (stepped shoulder geometry).  
**Why mandatory:** Exercises depth step from one Z datum to another; multi-pass check.  
**Qualification criteria:**
- ≥2 distinct Z levels derivable from B-rep shell faces
- Toolpath segments span both levels

**Acceptance gate:** Segments span correct Z levels verified against STEP shell.

---

#### Class 7 — Multi-Depth Prismatic (P10 gate)

**Geometry:** Prismatic block with ≥4 distinct Z levels and mixed hole depths.  
**Purpose:** Stresses reach check across multiple feature depths; more realistic DXF-02 analog.  
**Qualification criteria:**
- ≥4 hole features at different depths (all verifiable from STEP)
- Mixed Sandvik 860-1 (covered) and Kennametal B221A (flute_length=INSUFFICIENT_DATA)

**Acceptance gate:** Demonstrates fail-closed behavior per drill per feature.

---

#### Class 8 — Multi-Feature Prismatic (P10 gate)

**Geometry:** Prismatic block combining holes + pocket + slot on the same solid.  
**Purpose:** End-to-end multi-operation verification; tests collision scope across all checks.  
**Qualification criteria:**
- ≥1 hole, ≥1 pocket, ≥1 slot on a single STEP solid
- fixture_collision_validated, holder_collision_validated, tool_reach_validated all exercised

**Acceptance gate:** collision_scope_validated ∈ {SCOPED_PASS, SCOPED_FAIL, PARTIAL}

---

#### Class 9 — Turned Part, Round Stock (P10 gate)

**Geometry:** Cylindrical solid (lathe/turned part) — round stock geometry.  
**Purpose:** Validates CYLINDER stock path in voxel engine; exercises round_bar StockShape.  
**Qualification criteria:**
- Stock shape = ROUND_BAR (outer_diameter_mm required, inner_diameter_mm for boring)
- stock_model.shape = CYLINDER in StockModel after stock_definition_to_stock_model()

**Acceptance gate:** `stock_removal_validated` with CYLINDER stock model ∈ {PASS, FAIL}

---

#### Class 10 — Multi-Setup Part (P10 gate)

**Geometry:** Prismatic or complex part requiring ≥2 setups (Op-10 + Op-20).  
**Purpose:** Tests setup isolation in verification workflow; fixture WCS changes between ops.  
**Qualification criteria:**
- ≥2 fixture WCS positions (one per setup)
- Verification input assembled separately per setup
- fixture_collision_validated independent per setup

**Acceptance gate:** Independent WorkflowVerificationResult per setup_id.

---

### P10-B Summary

```
REAL_STEP_SAMPLE_COUNT          = 0
örnek_dosyalar_STEP_COUNT       = 0  (directory does not exist)
STEP_IMPORT_READY               = NO (cadquery not installed)
P10_B_STATUS                    = DEFERRED_REAL_STEP_SAMPLE_REQUIRED
10_CLASS_SPEC_WRITTEN           = YES (this document, §11)
NEXT_ACTION                     = Provide Class 1–3 STEP files + install cadquery
```

**STEP_CAM_VERIFICATION_QUALIFIED = NO**
