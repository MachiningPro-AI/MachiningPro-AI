# Machine Envelope Verification

**Version**: 1.0.0-beta.4  
**Date**: 2026-11-27

## Overview

The machine envelope check verifies that the entire toolpath fits within the machine's physical travel limits, applying the WCS (Work Coordinate System) offset before comparison.

## Check Function

```python
check_machine_envelope_with_wcs(
    segments: list[VerificationSegment],
    travel_x_mm: float | None,
    travel_y_mm: float | None,
    travel_z_mm: float | None,
    wcs_offset_x_mm: float = 0.0,
    wcs_offset_y_mm: float = 0.0,
    wcs_offset_z_mm: float = 0.0,
    machine_id: str | None = None,
    machine_limit_source: str = "CATALOG",
) -> VerificationResult
```

## WCS Transform (Phase K)

Toolpath coordinates are in part-program space (WCS). Before comparing against machine travel, the WCS offset is applied:

```
machine_x = program_x + wcs_offset_x_mm
machine_y = program_y + wcs_offset_y_mm
machine_z = program_z + wcs_offset_z_mm
```

The machine travel is centered at zero: `[-travel/2, +travel/2]` per axis.

## Status Semantics

| Condition | Status |
|-----------|--------|
| travel_x/y/z all None | `INSUFFICIENT_DATA` |
| Any travel is None | `INSUFFICIENT_DATA` |
| No segments | `PASS` (no motion to check) |
| All points within envelope | `PASS` |
| Any point outside envelope | `FAIL` |

## Axis Limit Violations (Phase L)

When a segment endpoint exceeds machine limits, a structured `AxisLimitViolation` is recorded:
- `AXIS`: axis name (X, Y, Z, A, B, C)
- `COMMAND_POSITION`: the machine-space coordinate
- `LIMIT_MIN` / `LIMIT_MAX`: the machine travel limits
- `EXCESS_MM`: how far out of range (always positive)
- `OPERATION_ID`: the operation that caused it (if known)
- `TOOLPATH_SEGMENT`: segment identifier (if known)

Violations are reported without silent clamping. The check never adjusts coordinates.

## TEST_ONLY Machine Configurations (Phase Z)

| Machine ID | X Travel | Y Travel | Z Travel | Expected Result |
|------------|----------|----------|----------|-----------------|
| `TEST-MACHINE-LARGE-01` | 1000mm | 800mm | 500mm | PASS for typical parts |
| `TEST-MACHINE-SMALL-01` | 10mm | 10mm | 10mm | FAIL for typical toolpaths |

These machine IDs are for deterministic testing only (`machine_limit_source="TEST_ONLY"`).

## Data Sources

`machine_limit_source` documents where the travel limits came from:
- `"CATALOG"`: from the machine library catalog (default)
- `"USER_INPUT"`: manually entered by the operator
- `"TEST_ONLY"`: deterministic test fixture, not production data

## Integration with AutoCAM

The orchestrator populates `MachineEnvelopeRecord` and `WCSEnvelopeRecord` from the simulation result:

```python
# S12: machine envelope check
result = check_machine_envelope_with_wcs(
    segments,
    travel_x_mm=machine.x_travel_mm,
    travel_y_mm=machine.y_travel_mm,
    travel_z_mm=machine.z_travel_mm,
    machine_id=machine.machine_id,
    machine_limit_source=machine.machine_limit_source,
)
```
