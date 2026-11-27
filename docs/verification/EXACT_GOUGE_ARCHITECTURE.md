# Exact Gouge Architecture

**Version**: 1.0.0-beta.4  
**Status**: GOUGE_EXACT_READY=NO  
**Date**: 2026-11-27

## Summary

MachiningPro AI implements two gouge check modes with strict status semantics:

| Check | Function | Status | Method |
|-------|----------|--------|--------|
| `GOUGE_EXACT` | `check_part_gouge_exact()` | Always `NOT_VERIFIABLE` | N/A — mesh engine not installed |
| `GOUGE_CONSERVATIVE` (PART_GOUGE) | `check_part_gouge()` | `PARTIAL` or `FAIL`, never `PASS` | BBOX conservative |

## Why GOUGE_EXACT is NOT_VERIFIABLE

Exact gouge checking requires a mesh-vs-mesh intersection engine (e.g. `pythonocc` / `BRepAlgoAPI`). This capability is not installed in the current environment (KL-07). Until the mesh engine is installed and validated:

- `check_part_gouge_exact()` **always** returns `NOT_VERIFIABLE`
- It will **never** return `PASS`, `PARTIAL`, or `FAIL`
- The evidence block documents: `gouge_exact_ready=False`, `reason="MESH_INTERSECTION_ENGINE_NOT_AVAILABLE"`

## Why GOUGE_CONSERVATIVE Never Returns PASS

The conservative bbox check (`check_part_gouge()`) uses a bounding-box approximation:
- Compares cutting segment Z-coordinates against the part bottom Z
- If a cutting segment goes below `part_min_z`, that is a potential gouge
- Returns `FAIL` when segments penetrate below the part floor
- Returns `PARTIAL` when no violation is found — because a bbox check cannot certify the entire surface is safe

**HARD RULE**: `PART_GOUGE` conservative check **never** returns `PASS`. This prevents false confidence.

## Status Separation Contract

The two checks run independently and report to different `VerificationCheckType` entries:

```python
result.checks[VerificationCheckType.GOUGE_EXACT]       # always NOT_VERIFIABLE
result.checks[VerificationCheckType.PART_GOUGE]        # PARTIAL or FAIL, never PASS
```

## Future: Upgrading GOUGE_EXACT

When a mesh intersection engine becomes available:

1. Install `pythonocc-core` or equivalent
2. Implement `_mesh_gouge_exact()` in `checks.py`
3. Update `check_part_gouge_exact()` to call `_mesh_gouge_exact()`
4. Set `gouge_exact_ready=True` in evidence
5. The check can then return `PASS`, `FAIL`, or `PARTIAL`
6. Update `GOUGE_EXACT_READY=YES` in orchestrator outputs

**GOUGE_EXACT_READY=NO** until these steps are complete.
