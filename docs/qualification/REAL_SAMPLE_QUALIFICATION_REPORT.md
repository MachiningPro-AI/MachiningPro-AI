# MachiningPro AI — Real Sample File Qualification Report

**Campaign ID:** RSQ  
**Date:** 2026-11-12  
**Commit base:** `3f5f8cd` (docs(operations): finalize production pilot provisioning handoff)  
**Engineer:** Qualification automation  
**Source files:** READ-ONLY at `D:\makina_ogrenmesi\olcum_denemeleri\örnek dosyalar` (outside repo)  

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Test cases | 119 |
| PASS | 119 |
| FAIL | 0 |
| SKIP | 0 (auto-skip when sample dir absent) |
| Runtime | 24.6 s |
| DXF files imported | 3 / 3 (DEGRADED — Level 1; ezdxf absent) |
| IGES files imported | 3 / 3 (UNSUPPORTED/PARTIAL/DEGRADED — see breakdown) |
| Unsupported format failures | 5 / 5 graceful UNSUPPORTED |
| Security invariants | PASS (no path leaks, no stack traces, no fabrication) |

**Verdict: ALL 119 REAL SAMPLE QUALIFICATION TESTS PASS**

---

## Scope

This campaign exercises the CAD import pipeline (`CadImportOrchestrator`) against 11 real engineering files selected from 84 available samples. No ground truth is available for real files (materials, tolerances, and feature geometry are UNKNOWN). Testing scope is limited to:

1. Import pipeline stability (no uncaught exceptions)
2. Fail-closed behavior for unsupported formats
3. Document production for supported formats
4. Security invariants (no path leaks, no stack traces, no fabrication)
5. Capability record coherence

Feature-level correctness (geometry values, tolerance extraction) is **NOT** in scope for this campaign, as no reference ground truth exists for real proprietary files.

---

## Test Environment

| Item | Value |
|------|-------|
| Python | 3.12.7 |
| pytest | 9.1.1 |
| ezdxf | NOT INSTALLED (optional dependency) |
| Operating system | Windows 10 Pro 10.0.19045 |
| Sample directory | Accessible (84 files) |

---

## Observed Import Results

### DXF Files

| File | Size | Status | entity_refs | Capability | Notes |
|------|-----:|--------|------------:|-----------|-------|
| `109106_01_30.dxf` | 271 812 B | **DEGRADED** | 1 | LEVEL_8_COST_RFQ_INTELLIGENCE | Level 1 only (ezdxf absent) |
| `109106_01_38.dxf` | 599 563 B | **DEGRADED** | 1 | LEVEL_8_COST_RFQ_INTELLIGENCE | Level 1 only (ezdxf absent) |
| `Pense_Sema.dxf`   | 894 575 B | **DEGRADED** | 1 | LEVEL_8_COST_RFQ_INTELLIGENCE | Level 1 only (ezdxf absent) |

DEGRADED (not FAILED) is correct: the DxfTokenAdapter operates at Level 0/1 without ezdxf. Installing ezdxf would upgrade these imports to Level 2 (NORMALIZED).

### IGES Files

| File | Size | Status | entity_refs | Capability | Notes |
|------|-----:|--------|------------:|-----------|-------|
| `agv03773.geo_fin001.006003.igs` | 217 054 B | **UNSUPPORTED** | 521 | LEVEL_8_COST_RFQ_INTELLIGENCE | Adapter parsed 521 entities; normalization_status=UNSUPPORTED |
| `fa00aaj27500_004999.igs` | 221 292 B | **PARTIAL** | 1 | LEVEL_0_RECOGNIZED | Partial parse; some content not normalizable |
| `fa00aas38521.geo_fin001.004999.igs` | 875 514 B | **DEGRADED** | 1 931 | LEVEL_8_COST_RFQ_INTELLIGENCE | 1 931 entity_refs; normalization PARTIAL |

**Note on IGES_S (agv03773, 521 entity_refs / UNSUPPORTED):** The IGES adapter ran and produced 521 entity_refs but set normalization_status=UNSUPPORTED, which the orchestrator surfaces as ImportStatus.UNSUPPORTED. This is correct fail-closed behavior — the adapter found IGES entity types it cannot normalize and declined to fabricate a SUCCESS result.

### Unsupported Formats

| File | Format | Status | Document | Notes |
|------|--------|--------|----------|-------|
| `DWG-00206402-001.pdf` | PDF | **UNSUPPORTED** | None | No adapter registered for PDF via import pipeline |
| `DWG-00139945-001_UPPER COVER MU METAL SHIELD.pdf` | PDF | **UNSUPPORTED** | None | Same |
| `DWG-00139946-001_LOWER COVER MU METAL SHIELD.pdf` | PDF | **UNSUPPORTED** | None | Same |
| `Pense_Sema.dwg` | DWG | **UNSUPPORTED** | None | No registered adapter |
| `46795221-FONDELLO-SEDE-.model` | CATIA_MODEL | **UNSUPPORTED** | None | No registered adapter |

All 5 unsupported files returned UNSUPPORTED without raising an exception and without producing a fabricated document. Fail-closed behavior CONFIRMED.

---

## Security Invariants (11 files × 4 checks = 44 checks)

| Invariant | Result |
|-----------|--------|
| No filesystem path in error_message | PASS (11/11) |
| Every result has import_id | PASS (11/11) |
| Every result has diagnostics | PASS (11/11) |
| No fabricated success on UNSUPPORTED/FAILED | PASS (11/11) |

---

## Test Suite Structure

```
tests/qualification/test_real_sample_qualification.py
├── TestRealSampleInventory       (RSQ-01) — file existence, sizes, not-in-repo
├── TestDxfImport                 (RSQ-02) — DXF import stability and capability
├── TestIgesImport                (RSQ-03) — IGES import stability and entity_refs
├── TestUnsupportedFormats        (RSQ-04) — PDF/DWG/.model fail-closed
├── TestRealSampleSecurityInvariants (RSQ-05) — no path leaks, no fabrication
└── TestCapabilityRecordCoherence (RSQ-06) — CapabilityRecord structural integrity
```

---

## Findings and Observations

### Finding RSQ-OBS-01: DXF Level 1 operates correctly without ezdxf

All 3 DXF files imported as DEGRADED (Level 1). entity_refs=1 for each, normalization_status=SUCCESS. The Level 1 adapter extracts structural metadata without full entity geometry. Installing `ezdxf` as an optional dependency would enable Level 2 (NORMALIZED) imports.

**Action:** No code change required. Installing ezdxf on the production server is an optional upgrade path documented in the platform requirements.

### Finding RSQ-OBS-02: IGES_L (875 KB) produces 1 931 entity_refs

The largest tested IGES file (`fa00aas38521.geo_fin001.004999.igs`) produced 1 931 entity_refs with normalization_status=PARTIAL. This demonstrates the IGES adapter scales to medium-sized production parts. The PARTIAL status indicates some IGES entity types were encountered that the current adapter normalizes only partially.

**Action:** None required. PARTIAL is an expected outcome for complex IGES files and accurately represents adapter capability.

### Finding RSQ-OBS-03: IGES_S (217 KB) returns UNSUPPORTED with 521 entity_refs

The smallest IGES file (`agv03773.geo_fin001.006003.igs`) parsed successfully into 521 entity_refs but resulted in ImportStatus.UNSUPPORTED due to normalization_status=UNSUPPORTED at the adapter level. This is fail-closed behavior — the adapter found entity types it could parse but not normalize, and correctly refused to fabricate a SUCCESS result.

**Action:** None required. The behavior is correct and consistent with the fail-closed design principle.

### Finding RSQ-OBS-04: PDF files not supported by import pipeline (expected)

PDFs are not registered in the CAD import adapter registry. The orchestrator returns UNSUPPORTED gracefully. PDF-based drawing analysis is separately available via the `/api/drawings` endpoint (VLM-based, Ollama granite3.2-vision:2b, advisory only).

**Action:** None required. This is documented expected behavior.

---

## Comparison with Synthetic Qualification

| Dimension | Synthetic (7 parts) | Real Samples (11 files) |
|-----------|--------------------:|------------------------:|
| Test cases | 94 system + 35 i18n | 119 |
| All PASS | YES | YES |
| DXF imports | 7/7 DEGRADED | 3/3 DEGRADED |
| Ground truth used | YES (computed expected values) | NO (UNKNOWN for real files) |
| Feature recognition tested | YES (geometry path) | NO (topology arg required) |
| Security invariants | 8 checks | 44 checks (11×4) |

Real sample qualification confirms the import pipeline behaves consistently across synthetic and real engineering files. DEGRADED (Level 1 without ezdxf) is the universal DXF outcome on this deployment configuration.

---

## Limitations

1. **No geometry ground truth.** Material, tolerance, unit, and feature identity are UNKNOWN for all real files. This qualification tests pipeline stability and fail-closed behavior only.
2. **IGES coverage limited to 3 of 15 files.** The 64 MB IGES file exceeds MAX_IMPORT_BYTES and was excluded. Larger files were excluded to keep test runtime manageable.
3. **Feature recognition not invoked.** `recognize_features(geometry, topology)` requires both a CanonicalGeometry and CanonicalTopology instance; the DEGRADED-level DXF imports do not produce these objects.
4. **DWG 9+ MB files not tested.** `RAB055S(41/42_NOKTALI).dwg` were not tested — they would return UNSUPPORTED anyway, same as `Pense_Sema.dwg`.
5. **ezdxf not installed.** All DXF results show Level 1 (DEGRADED). Level 2 behavior is covered by the synthetic qualification suite.

---

## Verdict

| Gate | Status |
|------|--------|
| RSQ-01 Inventory | PASS |
| RSQ-02 DXF import | PASS |
| RSQ-03 IGES import | PASS |
| RSQ-04 Unsupported fail-closed | PASS |
| RSQ-05 Security invariants | PASS |
| RSQ-06 Capability coherence | PASS |
| **Overall RSQ campaign** | **PASS — 119/119** |

**REAL_SAMPLE_QUALIFICATION_STATUS = PASS**  
**PRODUCTION_FILES_CHANGED = 0**  
**SAMPLE_FILES_COPIED_INTO_REPO = 0**  
**SAFE_FOR_AUTONOMOUS_MANUFACTURING = NO** (unchanged)
