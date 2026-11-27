# Holder-Fixture Collision Architecture

**Version**: 1.0.0-beta.4  
**Date**: 2026-11-27

## Overview

MachiningPro AI implements separate collision sub-checks for holder and fixture geometry per the Phase G and Phase I specifications. All checks use fail-closed semantics: missing geometry → `NOT_PERFORMED`, not `PASS`.

## Collision Sub-Check Matrix

| Check | VerificationCheckType | Geometry Required | Method | Never PASS When |
|-------|----------------------|-------------------|--------|-----------------|
| Holder-Part | `HOLDER_PART_COLLISION` | holder + part bbox | BBOX_CYLINDER | No holder geometry |
| Holder-Stock | `HOLDER_STOCK_COLLISION` | holder + stock model | BBOX_CYLINDER | No stock model |
| Holder-Fixture | `HOLDER_FIXTURE_COLLISION` | holder + fixture bboxes | BBOX_CYLINDER | No fixtures provided |
| Tool-Fixture | `TOOL_FIXTURE_COLLISION` | tool diameter + fixture bboxes | BBOX_SWEEP | No fixtures or no tool diam. |
| Part-Fixture | `PART_FIXTURE_INTERFERENCE` | part bbox + fixture bboxes | BBOX_OVERLAP | No part or no fixtures |

## Geometry Fidelity

All holder collision checks use `SIMPLIFIED_CYLINDER` fidelity:
- The holder is modeled as an infinite cylinder of diameter `holder_diameter_mm`
- The cylinder is positioned at each toolpath segment's XY position
- Z range: from `tool_z + tool_length_mm` to `tool_z + tool_length_mm + holder_length_mm`

This is a conservative approximation. Real holders have tapers, flanges, and modular sections. `HOLDER_GEOMETRY_FIDELITY=SIMPLIFIED` unless upgraded to `CATALOG_GEOMETRY`.

## Fail-Closed Behavior

```
holder_diameter_mm is None  → NOT_PERFORMED
holder_length_mm is None    → NOT_PERFORMED
tool_length_mm is None      → INSUFFICIENT_DATA (tool length needed to place holder)
part_bbox is None           → NOT_PERFORMED (for HOLDER_PART_COLLISION)
fixtures is []              → NOT_PERFORMED (for HOLDER_FIXTURE_COLLISION)
```

## Part-Fixture Interference (PARTIAL vs FAIL)

`check_part_fixture_interference()` returns `PARTIAL` (not `FAIL`) when the part bbox overlaps a fixture bbox. This is intentional: clamping fixtures are designed to contact the part in Z, so a bbox overlap is **expected and normal during setup**. The check flags this as `PARTIAL` for engineer review — it cannot determine if the overlap is intentional clamping or a true interference.

## Backward Compatibility

The original `check_holder_collision()` and `check_tool_collision()` aliases are preserved:
- `check_holder_collision` → `check_holder_fixture_collision`
- `check_tool_collision` → `check_tool_fixture_collision`

The combined `check_fixture_collision()` still runs both and returns the worse result.
