# Auto CAM DOCX Report Bridge

**Version**: 1.0.0-beta.4  
**KL-20 Status**: RESOLVED  
**Date**: 2026-11-27

## Summary

The Auto CAM report bridge generates reports in all 6 export formats from a **single canonical ReportDocument snapshot** (Phase R + Phase S). No duplicate engine exists; all formats are produced by the existing exporters.

## Phase S: Canonical Snapshot

```
REPORT_SNAPSHOT_CANONICAL=YES

AutoCamPlan → build_autocam_report_document() → ReportDocument
                                                       │
                              ┌────────────────────────┼─────────────────────────┐
                              ▼        ▼        ▼       ▼        ▼        ▼
                           JSON    CSV     PDF     XLSX    DOCX    ZIP
```

`build_autocam_report_document()` builds the canonical document once. All formats are then derived from that same object by calling `generate_autocam_report(plan, fmt)`. Engineering calculations, verification results, and provenance data are **not recomputed per format**.

## Report Sections

| Section ID | Title | Contents |
|------------|-------|----------|
| `01_PART` | Part & CAD Source | Part name, CAD file, format, import status |
| `02_FEATURES` | Feature Recognition | Detected features, types, counts |
| `03_OPERATIONS` | Operations & Toolpaths | Per-operation details |
| `04_TOOLS` | Cutting Tools | Tool IDs, diameters, lengths, materials |
| `05_CUTTING` | Cutting Parameters | Feed, speed, depth per operation |
| `06_VERIFICATION` | Verification Summary | All check statuses, safety invariants |
| `06b_CHECK_DETAILS` | Verification Check Details | Per-check status/method/fidelity/source |
| `07_COST` | Cost & Cycle Time | Estimated cycle time and cost |
| `08_BLOCKERS` | Blockers & Warnings | All issues requiring engineer review |

## DOCX Export (KL-20)

The DOCX format is wired via the existing `docx_exporter.py`. It is called by `generate_autocam_report(plan, fmt="DOCX")` and produces a `.docx` artifact.

```python
# backend/autocam/report_bridge.py
from backend.reports.docx_exporter import DocxExporter

exporter = DocxExporter()
result = exporter.export(doc)
# result.content = bytes of .docx file
```

**AUTOCAM_DOCX_EXPORT=YES** — no placeholder, real artifact produced.

## Safety Notice in All Reports

All generated reports include:

```
VERIFICATION_CAN_AUTO_APPROVE=NO
VERIFICATION_CAN_RELEASE_PRODUCTION=NO
VERIFICATION_CAN_DISPATCH_CNC=NO
ENGINEER_REVIEW_REQUIRED=YES
CANDIDATE_ONLY — not for production use without qualified engineer review
```

## Export Format Claims

| Format | AUTOCAM_*_EXPORT | Real Artifact |
|--------|------------------|---------------|
| JSON | YES | ReportDocument serialized to JSON |
| CSV | YES | Flattened key-value pairs |
| PDF | YES | Rendered PDF via pdf_exporter |
| XLSX | YES | Multi-sheet Excel workbook |
| DOCX | YES | Word document via docx_exporter |
| ZIP | YES | Bundle of all above formats |

No format claims PASS or YES without producing a real artifact.
