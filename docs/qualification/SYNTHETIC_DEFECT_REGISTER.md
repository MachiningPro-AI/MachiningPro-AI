# MachiningPro AI — Synthetic Qualification Defect Register

**Campaign:** MACHININGPRO_AI_FULL_SYNTHETIC_QUALIFICATION_AND_LOCALIZATION  
**Date:** 2026-11-12  
**Commit:** ccf4c55dcd471b88aa5e1a0821e9784c7f090d44  

---

## Defects Found

### DEF-L001 — ProcessRoutesPage: ~14 hardcoded English SectionLabel strings

| Field | Value |
|-------|-------|
| Defect ID | DEF-L001 |
| Severity | MAJOR |
| Module | ProcessRoutesPage (frontend) |
| Synthetic Part | N/A — localization |
| Steps | Switch UI to TR mode → open Process Routes page |
| Expected | All section labels translated to Turkish |
| Actual | Labels "Operations", "Score Breakdown", "Machine Candidates", "Tool Candidates", "Why Selected", "Optimization Strategy", "Features", "Optimized Plan", "Warnings", "Benchmark Metrics", "Safety Invariants" remain in English |
| Evidence | `frontend/app/src/pages/ProcessRoutesPage.tsx` lines 182, 207, 214, 240, 255, 269, 274, 603, 624, 699, 716, 794, 810 |
| Root Cause | SectionLabel children hardcoded as strings, not routed through `t()` |
| Recommended Fix | Add i18n keys; replace hardcoded strings with `{t('key')}` |
| Production Risk | Medium — Process Routes is a core engineering page |
| Demo Risk | HIGH — visible in any TR demo |
| Status | FIXED (2026-11-12) |

---

### DEF-L002 — WorkflowPage: ~11 hardcoded English labels

| Field | Value |
|-------|-------|
| Defect ID | DEF-L002 |
| Severity | MAJOR |
| Module | WorkflowPage (frontend) |
| Synthetic Part | N/A — localization |
| Steps | Switch UI to TR mode → open Workflow/Manufacturing Analysis page |
| Expected | "Manufacturing Analysis", "Progress", "Analysis Input", "CAD File", "Material", "Quantity", "Stock Reference", "Objective", "Analysis Mode", "Final Manufacturing Plan" translated |
| Actual | All above remain in English in TR mode |
| Evidence | `frontend/app/src/pages/WorkflowPage.tsx` lines 397, 472, 515, 518, 543, 553, 563, 573, 587, 632, 688 |
| Root Cause | WorkflowPage i18n keys were not defined for these strings |
| Recommended Fix | Add keys to en.ts/tr.ts; use `{t('key')}` |
| Production Risk | Medium |
| Demo Risk | HIGH — Manufacturing Analysis is the flagship feature |
| Status | FIXED (2026-11-12) |

---

### DEF-L003 — ProcessCapabilityPage: ~6 hardcoded English labels

| Field | Value |
|-------|-------|
| Defect ID | DEF-L003 |
| Severity | MAJOR |
| Module | ProcessCapabilityPage (frontend) |
| Steps | Switch to TR → open Process Capability page |
| Expected | "Operation Family", "Result", "Cycle Time Estimate", "New Shop Profile", "Machine ID" translated |
| Actual | Remain in English |
| Evidence | `frontend/app/src/pages/ProcessCapabilityPage.tsx` lines 123, 169, 214, 325, 409, 417 |
| Root Cause | Hardcoded SectionLabel and label text |
| Recommended Fix | Add i18n keys + t() calls |
| Demo Risk | MEDIUM |
| Status | FIXED (2026-11-12) |

---

### DEF-L004 — ProcessPlanningPage: 4 hardcoded table headers

| Field | Value |
|-------|-------|
| Defect ID | DEF-L004 |
| Severity | MINOR |
| Module | ProcessPlanningPage (frontend) |
| Steps | Switch to TR → open Process Planning page, expand parameter table |
| Expected | Column headers "Type", "Range", "Unit", "Status" translated |
| Actual | Remain in English |
| Evidence | `frontend/app/src/pages/ProcessPlanningPage.tsx` lines 2150-2153 |
| Root Cause | Table headers hardcoded |
| Recommended Fix | Add i18n keys |
| Demo Risk | LOW |
| Status | FIXED (2026-11-12) |

---

### DEF-L005 — Minor cosmetic hardcoded strings (5 pages)

| Field | Value |
|-------|-------|
| Defect ID | DEF-L005 |
| Severity | COSMETIC |
| Module | CadFeaturesPage, DashboardPage, MachineCatalogPage, ManufacturingPlanPage, MaterialLibraryPage, SelectionPage |
| Steps | Switch to TR mode → various pages |
| Expected | Minor labels translated |
| Actual | "DXF entities", "Field", "Actions", "Plans", "Confidence" remain English |
| Evidence | Various page files (see LOCALIZATION_AUDIT.md) |
| Root Cause | Minor labels not wired to i18n |
| Demo Risk | LOW |
| Status | FIXED (2026-11-12) |

---

## Defect Summary

| Severity | Count | Status |
|----------|-------|--------|
| BLOCKER | 0 | — |
| CRITICAL | 0 | — |
| MAJOR | 3 (DEF-L001, DEF-L002, DEF-L003) | FIXED 2026-11-12 |
| MINOR | 1 (DEF-L004) | FIXED 2026-11-12 |
| COSMETIC | 1 (DEF-L005) | FIXED 2026-11-12 |
| **Total** | **5** | **ALL FIXED** |

---

## Security Confirmation (from MUST 57)

| Check | Result |
|-------|--------|
| REAL_MACHINE_WRITE_FOUND | NO |
| AUTO_CNC_DISPATCH_FOUND | NO |
| AUTO_APPROVAL_FOUND | NO |
| AUTOMATIC_ADAPTATION_FOUND | NO |
| CUSTOMER_CAD_COMMITTED | NO |
| HARDCODED_SECRET_FOUND | NO |
| SERVER_PATH_LEAK_FOUND | NO |
| PATH_TRAVERSAL_FOUND | NO |

No security-critical defects found in this qualification campaign.

---

## Engineering Accuracy Verification (MUST 55)

Independent ground truth was established for:

| Test Case | Formula | Expected | Actual | Error |
|-----------|---------|---------|--------|-------|
| Spindle speed (Vc=100, D=20) | n=1000Vc/(πD) | 1591.549 RPM | 1591.549 RPM | 0.000% |
| Spindle speed (Vc=100, D=60) | n=1000Vc/(πD) | 530.516 RPM | 530.516 RPM | 0.000% |
| Surface roughness Ra (fz=0.1, R=0.4) | Ra=fz²/(16R) | 1.5625 µm | 1.5625 µm | 0.000% |
| Taylor T (C=500, n=0.25, Vc=100) | T=(C/Vc)^(1/n) | 625 min | 625 min | 0.000% |
| Taylor T (C=200, n=0.3, Vc=200) | T=(C/Vc)^(1/n) | 1 min | 1 min | 0.000% |
| Machining time (L=120, vf=500) | t=L/vf | 0.24 min | 0.24 min | 0.000% |

All verified formula implementations are CORRECT.
