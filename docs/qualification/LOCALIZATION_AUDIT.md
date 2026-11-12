# MachiningPro AI — Localization Audit

**Campaign:** MACHININGPRO_AI_FULL_SYNTHETIC_QUALIFICATION_AND_LOCALIZATION  
**Date:** 2026-11-12  
**Commit:** ccf4c55dcd471b88aa5e1a0821e9784c7f090d44  
**Branch:** main  

---

## Summary Metrics

| Metric | Value |
|--------|-------|
| EN translation keys | 1711 |
| TR translation keys | 1711 |
| Key parity | PASS (equal) |
| TR language leak count (from i18n files) | 0 |
| EN language leak count (from i18n files) | 0 |
| Raw backend enum visible count (in i18n files) | 0 |
| Raw HTTP error visible count (in i18n files) | 0 |
| Hardcoded user-visible strings (bypassing i18n) | ~86 |

---

## Hardcoded String Defects (bypass i18n system)

The following pages contain user-visible English strings that do NOT use the `t()` i18n function.
These are **localization defects** — the i18n infrastructure is in place, but these strings were
hardcoded rather than routed through it.

### DEF-L001: ProcessRoutesPage.tsx

| Line | String | Severity |
|------|--------|----------|
| 182 | `<SectionLabel>Operations</SectionLabel>` | MAJOR |
| 207 | `<SectionLabel>Score Breakdown (BLACK_BOX_AI_SCORE_USED=NO)</SectionLabel>` | MINOR (dev annotation) |
| 214 | `<SectionLabel>Risk Flags (...)</SectionLabel>` | MAJOR |
| 240 | `<SectionLabel>Machine Candidates (REFERENCE_ONLY)</SectionLabel>` | MAJOR |
| 255 | `<SectionLabel>Tool Candidates (REFERENCE_ONLY)</SectionLabel>` | MAJOR |
| 269 | `<SectionLabel>Why Selected</SectionLabel>` | MAJOR |
| 274 | `<SectionLabel>Uncertain / Unresolved</SectionLabel>` | MAJOR |
| 603 | `<SectionLabel>Optimization Strategy</SectionLabel>` | MAJOR |
| 624 | `<SectionLabel>Features</SectionLabel>` | MAJOR |
| 636-644 | `<span>Type</span>`, `<span>Ra</span>`, etc. | MINOR/COSMETIC |
| 699 | `<SectionLabel>Optimized Plan</SectionLabel>` | MAJOR |
| 716 | `<SectionLabel>Warnings</SectionLabel>` | MAJOR |
| 794 | `<SectionLabel>Benchmark Metrics</SectionLabel>` | MAJOR |
| 810 | `<SectionLabel>Safety Invariants</SectionLabel>` | MAJOR |

**Root Cause:** ProcessRoutesPage uses a local `SectionLabel` component that accepts string children directly. The page was built before i18n infrastructure was wired to these labels.

**Fix Required:** Add i18n keys for all SectionLabel children; replace `>text<` with `>{t('key')}<`.

---

### DEF-L002: WorkflowPage.tsx

| Line | String | Severity |
|------|--------|----------|
| 397 | `Manufacturing Analysis` (h1) | MAJOR |
| 472 | `Progress` (span) | MAJOR |
| 515 | `Analysis Input` (h2) | MAJOR |
| 518 | `CAD File` (label) | MAJOR |
| 543 | `Material` (label) | MAJOR |
| 553 | `Quantity` (label) | MAJOR |
| 563 | `Stock Reference` (label) | MAJOR |
| 573 | `Objective` (label) | MAJOR |
| 587 | `Analysis Mode` (label) | MAJOR |
| 632 | Hardcoded h2 text | MAJOR |
| 688 | `Final Manufacturing Plan` (h2) | MAJOR |

**Root Cause:** WorkflowPage was developed with hardcoded labels. i18n keys for these strings do not exist in en.ts/tr.ts.

---

### DEF-L003: ProcessCapabilityPage.tsx

| Line | String | Severity |
|------|--------|----------|
| 123 | `Operation Family` (label) | MAJOR |
| 169 | `Result` (SectionLabel) | MAJOR |
| 214 | `Operation Family` (label) | MAJOR |
| 325 | `Cycle Time Estimate` (SectionLabel) | MAJOR |
| 409 | `New Shop Profile` (SectionLabel) | MAJOR |
| 417 | `Machine ID` (label) | MAJOR |

---

### DEF-L004: ProcessPlanningPage.tsx

| Line | String | Severity |
|------|--------|----------|
| 2150 | `Type` (th) | MINOR |
| 2151 | `Range` (th) | MINOR |
| 2152 | `Unit` (th) | MINOR |
| 2153 | `Status` (th) | MINOR |
| 2186 | `rule_id` (th - dev string) | MINOR |
| 2187 | `status` (th - dev string) | MINOR |

---

### DEF-L005: Other Pages (Cosmetic/Minor)

- `CadFeaturesPage.tsx` line 430: `DXF entities` (technical/dev label)
- `DashboardPage.tsx` line 51: `MachiningPro AI` (product name — TECHNICAL_KEEP)
- `MachineCatalogPage.tsx` line 413: `Field` (th header)
- `ManufacturingPlanPage.tsx` lines 606, 839: `Actions`, `Plans`
- `MaterialLibraryPage.tsx` line 445: `Confidence`
- `SelectionPage.tsx`: minor hardcoded strings

---

## i18n Infrastructure Assessment

| Aspect | Status |
|--------|--------|
| i18n framework present | PASS — `frontend/app/src/i18n/` with en.ts, tr.ts, index.tsx, types.ts |
| Key parity (EN == TR count) | PASS — 1711 keys each |
| Technical acronyms preserved | PASS — CAD, CAM, CNC, ISO, Ra, etc. correct in both |
| Backend enum raw strings in i18n files | PASS — none found |
| Raw HTTP errors in i18n files | PASS — none found |
| TR Dashboard translated | PASS |
| TR navigation keys | PASS |
| TR engineering module labels | PASS |
| TR error messages | PASS |
| Hardcoded bypass strings | **PASS** — 0 remaining (all 5 defects fixed 2026-11-12) |

---

## Classification Legend

| Classification | Description |
|----------------|-------------|
| TRANSLATE | Must be localized — user-visible label |
| TECHNICAL_KEEP | Technical acronym — do not translate (CAD, CAM, Ra, etc.) |
| CUSTOMER_DATA | User-entered content — exempt |
| DEVELOPER_ONLY | Dev debug string — not user-visible in production |
| NOT_USER_VISIBLE | CSS class name, attribute, etc. |

---

## Recommended Fix Strategy

1. Add i18n keys for all MAJOR defects in DEF-L001 through DEF-L004
2. Replace hardcoded strings with `{t('key')}` calls
3. Add regression test: scan for `<SectionLabel>[A-Z]` without `t(` — count must be 0
4. Priority: WorkflowPage > ProcessRoutesPage > ProcessCapabilityPage

---

**TR_LANGUAGE_LEAK_COUNT=0** (from i18n files)  
**EN_LANGUAGE_LEAK_COUNT=0** (from i18n files)  
**HARDCODED_UI_STRINGS_REMAINING=0** (DEF-L001 through DEF-L005 fixed 2026-11-12; 104 new i18n keys added, EN=TR=1815)  
**RAW_BACKEND_ENUM_VISIBLE_COUNT=0**  
**RAW_HTTP_ERROR_VISIBLE_COUNT=0**
