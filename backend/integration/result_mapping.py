"""Unified PASS/FAIL/UNKNOWN verdict type for cross-library integration.

PROBLEM
-------
Three separate StrEnums represent the same three-state verdict in the
integrated codebase, each scoped to its own library:

  machine_library.material_context.MaterialCompatibilityVerdict  (PASS/FAIL/UNKNOWN)
  machine_library.interfaces.CompatibilityVerdict                (PASS/FAIL/UNKNOWN)
  cutting_tools.compatibility.CompatibilityStatus                (PASS/FAIL/UNKNOWN)

They are structurally identical but different Python types, so they cannot be
compared with ``is`` or used interchangeably without explicit conversion.

This module provides:
  IntegrationVerdict — a single unified StrEnum for the integration layer.
  Conversion helpers from each library type.
  combine_verdicts() — conservative multi-verdict combiner (FAIL > UNKNOWN > PASS).

Design constraints:
  UNKNOWN_AS_PASS=NO — UNKNOWN never collapses to PASS.
  FABRICATED_VERDICT=NO — only direct value-to-value mapping, no inference.
"""

from __future__ import annotations

from enum import StrEnum

from backend.cutting_tools.compatibility import CompatibilityStatus
from backend.machine_library.interfaces import (
    CompatibilityVerdict as InterfaceCompatibilityVerdict,
)
from backend.machine_library.material_context import (
    MaterialCompatibilityVerdict,
)

__all__ = [
    "IntegrationVerdict",
    "from_compatibility_status",
    "from_material_compatibility_verdict",
    "from_interface_compatibility_verdict",
    "combine_verdicts",
]


class IntegrationVerdict(StrEnum):
    """Unified three-state verdict for cross-library integration results.

    Precedence (conservative): FAIL > UNKNOWN > PASS.
    UNKNOWN is never promoted to PASS — missing data stays UNKNOWN.
    """

    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------


def from_compatibility_status(status: CompatibilityStatus) -> IntegrationVerdict:
    """Convert Tool Library CompatibilityStatus to IntegrationVerdict."""
    return IntegrationVerdict(status.value)


def from_material_compatibility_verdict(
    verdict: MaterialCompatibilityVerdict,
) -> IntegrationVerdict:
    """Convert Machine Library MaterialCompatibilityVerdict to IntegrationVerdict."""
    return IntegrationVerdict(verdict.value)


def from_interface_compatibility_verdict(
    verdict: InterfaceCompatibilityVerdict,
) -> IntegrationVerdict:
    """Convert Machine Library interface CompatibilityVerdict to IntegrationVerdict."""
    return IntegrationVerdict(verdict.value)


# ---------------------------------------------------------------------------
# Conservative combiner
# ---------------------------------------------------------------------------

_PRECEDENCE: dict[IntegrationVerdict, int] = {
    IntegrationVerdict.PASS: 0,
    IntegrationVerdict.UNKNOWN: 1,
    IntegrationVerdict.FAIL: 2,
}


def combine_verdicts(*verdicts: IntegrationVerdict) -> IntegrationVerdict:
    """Return the most conservative verdict from a set of verdicts.

    Precedence: FAIL > UNKNOWN > PASS.
    Empty input returns UNKNOWN (conservative default — not PASS).

    Examples:
      combine_verdicts(PASS, PASS) → PASS
      combine_verdicts(PASS, UNKNOWN) → UNKNOWN
      combine_verdicts(PASS, FAIL) → FAIL
      combine_verdicts(UNKNOWN, FAIL) → FAIL
      combine_verdicts() → UNKNOWN
    """
    if not verdicts:
        return IntegrationVerdict.UNKNOWN
    return max(verdicts, key=lambda v: _PRECEDENCE[v])
