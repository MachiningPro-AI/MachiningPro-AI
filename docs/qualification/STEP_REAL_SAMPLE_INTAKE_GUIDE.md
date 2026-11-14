# STEP Real Sample Intake Guide — P3-D Assessment

**Assessment Date:** 2026-11-14  
**Assessed by:** P3-D automated scan  
**Repository:** MachiningPro_AI_NEXT  

---

## P3-D Result

**REAL_STEP_SAMPLE_COUNT=0**

No `.step` or `.stp` files were found in the sample directory:

```
D:\makina_ogrenmesi\olcum_denemeleri\örnek dosyalar\
```

The directory contains DXF files only. Per the P3-D hard rules, speculative STEP parser work
is **NOT** implemented when real STEP samples are unavailable.

---

## Why STEP Samples Matter

The existing IGES pipeline reconstructs surface topology and derives `PRECISION_BORE_CANDIDATE`
features, but cannot confirm closed B-Rep solids, depth evidence, or true volumetric topology.
STEP (ISO 10303 AP203/AP214) encodes complete B-Rep with solid-body semantics, which would
enable:

- Confirmed hole depth from B-Rep geometry (eliminating the main P3-A blocker for IGES files)
- Solid face-counts and topology validation
- Material metadata in STEP product attributes
- Feature candidates with higher confidence (closed body available)

---

## Recommended Sample Profile

When real STEP samples become available, intake in this order of priority:

| Priority | Part type | Features expected | Assessment value |
|----------|-----------|-------------------|-----------------|
| 1 | Simple prismatic block | Rectangular pocket, slot | Verifies basic milling route |
| 2 | Drilled plate | Blind hole, through hole | Verifies depth evidence from B-Rep |
| 3 | Turned shaft | Cylindrical surface, groove, chamfer | Verifies turning route |
| 4 | Multi-feature prismatic | Pocket + holes + threads | Full feature recognition exercise |
| 5 | Flanged part | Bolt circle (pattern), face | Tests pattern detection |

**Avoid for initial intake:** Parts with highly complex free-form surfaces, sheet metal, or
weldment assemblies — these require additional pipeline stages not yet implemented.

---

## Acceptance Criteria for STEP Level-1 Assessment

When real STEP files exist, the Level-1 assessment must verify:

| Check | Pass condition |
|-------|----------------|
| Import | File opens without crash |
| B-Rep | At least one shell or solid found |
| Solids | `closed_body_available` reported |
| Faces | Face count > 0 |
| Topology | Surface groups produced (cylindrical / planar) |
| Feature candidates | At least one candidate per expected feature |
| Depth evidence | `depth_mm` non-None for blind holes (from B-Rep) |
| Material metadata | `material_grade` extracted if STEP product attribute present |
| Planning readiness | `cam_prerequisites_met` computable when stock+setup also defined |

**HARD RULES for assessment:**
- Do NOT infer missing STEP geometry.
- Do NOT fabricate STEP samples.
- Do NOT download proprietary STEP files.
- Do NOT modify real sample files.
- Do NOT auto-approve features extracted from STEP.

---

## Infrastructure Status

The STEP adapter placeholder exists at:

```
backend/interoperability/adapters/step.py
```

It is a capability stub — it does not parse real STEP geometry. Full STEP parsing requires
`pythonocc-core` (LGPL) or an equivalent open-geometry kernel, which must be evaluated for
license compatibility before adoption (HARD RULE 16: no proprietary or license-incompatible
dependencies).

---

## Next Step

1. Obtain real STEP samples from customer drawings or public CC0 sources (e.g., NIST test files).
2. Place them in `D:\makina_ogrenmesi\olcum_denemeleri\örnek dosyalar\`.
3. Re-run P3-D assessment: `python -m pytest tests/unit/interoperability/test_p3d_step_assessment.py`
4. Evaluate `pythonocc-core` license compatibility before implementing the parser.

**P3_D_RESULT=NO_REAL_STEP_SAMPLE_DEFERRED**
