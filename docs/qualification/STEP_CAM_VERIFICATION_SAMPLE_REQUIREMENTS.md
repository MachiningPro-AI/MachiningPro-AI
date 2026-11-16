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

*This document does not change any hard rule. UNKNOWN remains UNKNOWN until actual
geometric evidence is present and tested.*
