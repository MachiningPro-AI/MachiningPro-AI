# Real Sample Major Defect Fix — Before / After Comparison

**Campaign:** MACHININGPRO_AI_REAL_SAMPLE_MAJOR_DEFECT_CLOSURE  
**Date:** 2026-11-13  
**Branch:** main  
**HEAD (before):** 645b7d4  
**HEAD (after):** (this commit — see git log)  
**Defects addressed:** DEF-RSQ-002, DEF-RSQ-004, DEF-RSQ-005, DEF-RSQ-006, DEF-RSQ-007  
**Defects intentionally left unchanged:** DEF-RSQ-001 (MINOR), DEF-RSQ-003 (MINOR)  
`MINOR_DEFECTS_UNCHANGED=YES`  
`ALL_SOURCE_FILES_UNCHANGED=YES`  
`SOURCE_SAMPLE_FILES_COMMITTED=NO`

---

## Summary of Changes

| Defect | Root Cause Fixed | File Changed |
|--------|-----------------|-------------|
| DEF-RSQ-002 | `ezdxf` added to `pyproject.toml` production dependencies | `pyproject.toml` |
| DEF-RSQ-004 | `mark_unsupported()` → `mark_partial()` when `mapping.geometry is not None` | `adapters/iges.py` |
| DEF-RSQ-005 | Hollerith tokenizer `.strip()` removed for Hollerith tokens | `iges_parser.py` |
| DEF-RSQ-005 (cascade) | Non-rigid transformation on arc/plane now non-fatal (_UnsupportedEntityError) | `iges_mapping.py` |
| DEF-RSQ-006 | Added `strip_mtext_codes()` function; wired into `run_token_extraction()` for DXF source | `semantic_extraction.py` |
| DEF-RSQ-007 | PLANAR surfaces now produce UNKNOWN CANDIDATE manufacturing features in GEOMETRY_ONLY mode | `feature_recognition.py` |

---

## Before / After Comparison — Supported File Tests

### DXF Files (DXF-01=109106_01_30, DXF-02=109106_01_38, DXF-03=Pense_Sema)

| Metric | Before (645b7d4) | After (this commit) |
|--------|-----------------|---------------------|
| ezdxf installed | NO | YES (1.4.5) |
| DXF-01 entity_refs | 1 (DxfHeader only) | 20 |
| DXF-02 entity_refs | 1 (DxfHeader only) | 599 |
| DXF-03 entity_refs | 1 (DxfHeader only) | 20 |
| DXF import status | DEGRADED (ezdxf absent) | DEGRADED (partial feature data) |
| DXF succeeded | True | True |
| DXF drawing parser — strip_mtext_codes available | NO | YES |
| DXF run_token_extraction MTEXT preprocessing | NO | YES (source_type=DXF path) |
| `\W0.8;H7` → FIT detection | 0 | 1 |
| DXF-01 annotation tokens (ezdxf path) | 0 (not extracted) | collected (plain_mtext()) |

### IGES Files

| Metric | Before (645b7d4) | After (this commit) |
|--------|-----------------|---------------------|
| IGS-01 (agv03773) import status | UNSUPPORTED | DEGRADED |
| IGS-01 succeeded | False | True |
| IGS-01 entity_refs | 521 | 521 |
| IGS-01 surfaces | 119 | 119 |
| IGS-01 manufacturing_features | 0 | 96 (PLANAR CANDIDATE) |
| IGS-02 (fa00aaj27500) import status | PARTIAL (header only) | DEGRADED |
| IGS-02 succeeded | False (Hollerith parse error) | True |
| IGS-02 entity_refs | 1 (IgesHeader) | 560 |
| IGS-02 geometry | None | 16 surfaces |
| IGS-02 manufacturing_features | 0 | 16 (PLANAR CANDIDATE) |
| IGS-03 (fa00aas38521) import status | DEGRADED | DEGRADED |
| IGS-03 manufacturing_features | 0 | 64 (PLANAR CANDIDATE) |

---

## Root Cause Descriptions

### DEF-RSQ-002 — ezdxf absent

**Before:** `ezdxf` was an optional dependency. Without it, DXF imports reach Level 1 only
(1 entity_ref = DxfHeader). The `else` branch in `_ingest_text` calls `record_unsupported()`
and returns early.

**Fix:** Added `"ezdxf>=1.3,<2"` to `[project].dependencies` in `pyproject.toml`.
With ezdxf present, `_normalize_geometry_ezdxf()` runs and creates one `CanonicalEntityRef`
per modelspace entity.

---

### DEF-RSQ-004 — IGS-01 UNSUPPORTED despite geometry

**Before:** In `adapters/iges.py` lines 433–435:
```python
elif unsupported_fatal_issue:
    session.mark_unsupported()
    session.set_fidelity_completeness(FidelityReportCompleteness.PARTIAL)
```
This unconditionally set `NormalizationStatus.UNSUPPORTED` → `ImportStatus.UNSUPPORTED`
(`succeeded=False`) even when `mapping.geometry is not None`.

**Fix:** Downgrade to `mark_partial()` when geometry was extracted:
```python
elif unsupported_fatal_issue:
    if mapping.geometry is not None:
        session.mark_partial()
    else:
        session.mark_unsupported()
    session.set_fidelity_completeness(FidelityReportCompleteness.PARTIAL)
```
IGS-01 now: `NormalizationStatus.PARTIAL` → `ImportStatus.DEGRADED` (`succeeded=True`).

---

### DEF-RSQ-005 — IGS-02 header-only due to Hollerith parse bug

**Before:** `_tokenize_parameter_stream()` in `iges_parser.py` applied `.strip()` to ALL
accumulated token parts, including Hollerith string tokens. A Hollerith string like
`35HCATIA Version 5 Release 19 SP 7 ` (with trailing space) was stripped to 34 chars,
but the declared length was 35. When `_parse_hollerith` later validated the token,
`content_end (35) > len(token) (34)` → `IgesParseError`.  The global section parse
failure cascaded to zero geometry entities.

**Fix:** Added `_is_hollerith_token` boolean flag in the tokenizer loop. Hollerith
tokens are appended without `.strip()`:
```python
raw = "".join(token_parts)
tokens.append(raw if _is_hollerith_token else raw.strip())
```

**Cascade fix:** After the Hollerith fix, entity type 100 (circular arc) with a non-rigid
transformation raised `_MappingError` → `fatal=True` → `ImportStatus.FAILED`.
Added `_UnsupportedEntityError(ValueError)` as a sibling of `_MappingError`. Arcs and
planes with non-rigid transforms now raise this, which is caught non-fatally:
the arc is skipped and recorded as a partial issue. Result: `ImportStatus.DEGRADED`
(`succeeded=True`) with 560 entity_refs and 16 surfaces.

---

### DEF-RSQ-006 — DXF MTEXT codes not stripped

**Before:** `run_token_extraction()` in `semantic_extraction.py` received raw DXF MTEXT
tokens containing AutoCAD formatting codes (`\W0.963;`, `\fsimplex.shx;`, `\H1.50;`).
No preprocessing was applied. Pattern matchers (fit, thread, surface finish) could not
recognize values obscured by codes.

**Fix:**
1. Added `strip_mtext_codes(text: str) -> str` as a public function in `semantic_extraction.py`.
   Strips AutoCAD MTEXT codes (`\W...;`, `\f...;`, `\H...;`, `\P`, `{\\...}`) and converts
   `%%c→Ø`, `%%d→°`, `%%p→±`.
2. In `run_token_extraction()`, when `source_type == DetectionSourceType.DXF`, applies
   `strip_mtext_codes()` to each token before passing to pattern parsers.

**Result:** `\W0.8;H7` → strip → `H7` → FIT detection (confirmed by test).
For the actual real DXF files, most annotation content is Turkish dimension values which
do not match fit/thread/surface-finish patterns — 0 detections is CORRECT and not a defect.

---

### DEF-RSQ-007 — IGES manufacturing_features = 0

**Before:** `_recognize_geometry_only()` in `feature_recognition.py` created CANDIDATE
features only for CYLINDRICAL (→ HOLE), CONICAL (→ CHAMFER), TOROIDAL (→ FILLET)
surfaces. CATIA V5 IGES files encode all surfaces as NURBS (type 128 → FREEFORM) or
planes (type 108 → PLANAR). Neither FREEFORM nor PLANAR had feature candidates.

**Fix:** Added PLANAR case in `_recognize_geometry_only()`:
```python
elif cls == FaceClassification.PLANAR:
    features.append(ManufacturingFeature(
        feature_id=_fid(),
        feature_type=ManufacturingFeatureType.UNKNOWN,
        status=FeatureStatus.CANDIDATE,
        ...
        evidence_notes=(
            "planar surface without topology: "
            "machining operation undetermined (facing/step/pocket floor); "
            "topology required for CONFIRMED"
        ),
    ))
```
FREEFORM surfaces remain without feature candidates (too uncertain without topology).

**Result:**
- IGS-01: 96 PLANAR → 96 UNKNOWN CANDIDATE features
- IGS-02: 16 surfaces → 16 UNKNOWN CANDIDATE features
- IGS-03: 64 PLANAR → 64 UNKNOWN CANDIDATE features

---

## Anti-Fabrication Audit (Post-Fix)

| CHECK | STATUS |
|-------|--------|
| FABRICATED_FEATURE_FOUND | NO — all PLANAR features are type=UNKNOWN (not invented) |
| FABRICATED_DIAMETER_FOUND | NO |
| FABRICATED_TOLERANCE_FOUND | NO |
| FABRICATED_RA_FOUND | NO |
| FABRICATED_MATERIAL_FOUND | NO |
| UNSUPPORTED_STATUS_CHANGED_WITHOUT_GEOMETRY | NO — only changed when geometry is present |
| HOLLERITH_FIX_ALTERS_GEOMETRY_VALUES | NO — only whitespace handling in tokenizer |
| MTEXT_STRIP_INVENTS_TOKENS | NO — stripping removes codes, never adds content |

Note: `feature_type=UNKNOWN` and `status=CANDIDATE` are intentionally set to avoid
fabricating specific machining operations without topology confirmation.

---

## Security/Safety Invariants (Post-Fix)

| INVARIANT | STATUS |
|-----------|--------|
| REAL_MACHINE_WRITE_FOUND | NO |
| AUTO_CNC_DISPATCH_FOUND | NO |
| AUTO_APPROVAL_FOUND | NO |
| AUTOMATIC_ADAPTATION_FOUND | NO |
| SOURCE_SAMPLE_FILES_COMMITTED | NO |
| NC_DISPATCHED | NO |

---

## Test Results (Post-Fix)

| Suite | PASS | FAIL | NOTE |
|-------|-----:|-----:|------|
| RSQ-10 new defect-closure tests | 20 | 0 | 20 new tests added |
| RSQ-01..RSQ-06 existing tests | 119 | 0 | No regressions |
| Total qualification suite | 139 | 0 | — |
| Unit: interoperability normalization/adapter | 156 | 0 | No regressions |
| Unit: drawing intelligence feature recognition | 166 | 0 | No regressions |
| Ruff lint | 0 errors | — | All changed files clean |

---

## Remaining Open Defects

| Defect | Severity | Status |
|--------|----------|--------|
| DEF-RSQ-001 | MINOR | OPEN (not fixed by design) |
| DEF-RSQ-003 | MINOR | OPEN (not fixed by design) |

---

*MINOR_DEFECTS_UNCHANGED=YES*  
*ALL_SOURCE_FILES_UNCHANGED=YES*  
*SOURCE_SAMPLE_FILES_COMMITTED=NO*
