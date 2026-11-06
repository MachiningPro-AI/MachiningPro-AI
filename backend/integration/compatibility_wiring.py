"""MC-4 / MC-5 — Spindle normalization and IntegrationVerdict wiring.

MC-4 (SPINDLE)
--------------
Wires ``check_holder_machine_spindle_compatibility()`` from the spindle adapter
into the machine-holder interface check, replacing the legacy plain-string
comparison with normalized interface-family matching.

  CAT-40 ≠ BT-40 — different interface families; normalization enforces this.
  Missing spindle spec → IntegrationVerdict.UNKNOWN (never promoted to PASS).
  Multiple machine interfaces checked; PASS if any normalized match found.

MC-5 (VERDICT)
--------------
Wires ``IntegrationVerdict`` and ``combine_verdicts()`` from result_mapping into
the compatibility decision aggregation.

  Rule status mapping: PASS→PASS, FAIL→FAIL, UNKNOWN→UNKNOWN, NOT_APPLICABLE→skipped.
  FAIL > UNKNOWN > PASS precedence (conservative).
  Empty rule set → UNKNOWN (never PASS).
  Provenance list records which rule_id produced which verdict.

Design constraints:
  LEGACY_PIPELINE_UNCHANGED=YES   — engine.evaluate() unmodified; called as-is.
  OPT_IN_ONLY=YES                 — both flags default True; legacy path accessible.
  FALSE_PASS_FROM_MISSING_DATA=NO
  CAT40_EQ_BT40=NO
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.compatibility.engine import (
    _HOLDERS,
    _MACHINES,
    evaluate,
)
from backend.compatibility.models import CompatibilityRequest, CompatibilityResponse
from backend.integration.result_mapping import (
    IntegrationVerdict,
    combine_verdicts,
    from_interface_compatibility_verdict,
)
from backend.integration.spindle_adapter import check_holder_machine_spindle_compatibility
from backend.machines.catalog_models import MachineCatalogRecord
from backend.tool_holders.catalog_models import ToolHolderCatalogRecord

__all__ = [
    "SpindleCheckDetail",
    "EnhancedCompatibilityResult",
    "enhanced_evaluate",
]


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SpindleCheckDetail:
    """Provenance record for the normalized spindle interface check (MC-4)."""

    holder_spindle_raw: str | None
    machine_spindle_primary: str | None
    verdict: IntegrationVerdict
    compatible_interface: str | None  # which machine interface normalized-matched, or None
    provenance: str


@dataclass(frozen=True)
class EnhancedCompatibilityResult:
    """Wraps a legacy CompatibilityResponse with integration-layer enhancements.

    ``base_response`` is the unmodified result from ``engine.evaluate()`` and is
    always present regardless of which flags are set.

    ``spindle_verdict``   — MC-4: normalized spindle check result.
    ``spindle_detail``    — MC-4: full provenance record (None if spindle normalization off).
    ``overall_verdict``   — MC-5: combined IntegrationVerdict over all applicable rules.
    ``verdict_provenance`` — MC-5: per-rule (rule_id, verdict) trace list.
    """

    base_response: CompatibilityResponse
    spindle_verdict: IntegrationVerdict
    spindle_detail: SpindleCheckDetail | None
    overall_verdict: IntegrationVerdict
    verdict_provenance: list[str]
    use_spindle_normalization: bool
    use_integration_verdict: bool


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _map_rule_status(status: str) -> IntegrationVerdict | None:
    """Map a rule status string to IntegrationVerdict; NOT_APPLICABLE → None."""
    if status == "PASS":
        return IntegrationVerdict.PASS
    if status == "FAIL":
        return IntegrationVerdict.FAIL
    if status == "UNKNOWN":
        return IntegrationVerdict.UNKNOWN
    return None  # NOT_APPLICABLE: rule does not contribute to verdict


def _check_spindle_normalized(
    machine: MachineCatalogRecord,
    holder: ToolHolderCatalogRecord,
) -> SpindleCheckDetail:
    """Check holder spindle interface against all machine spindle interfaces.

    Returns PASS if any normalized interface matches, FAIL if none match,
    UNKNOWN if machine has no published interfaces or any comparison is unresolvable.

    Multiple machine interfaces are checked in declaration order; PASS wins
    immediately (early exit). UNKNOWN beats FAIL (conservative).
    """
    holder_raw: str | None = holder.machine_interface_key

    machine_interfaces: list[str] = []
    if machine.spindle_interface is not None:
        machine_interfaces.append(machine.spindle_interface)
    if getattr(machine, "spindle_interfaces_supported", None):
        machine_interfaces.extend(machine.spindle_interfaces_supported)  # type: ignore[arg-type]

    if not machine_interfaces:
        return SpindleCheckDetail(
            holder_spindle_raw=holder_raw,
            machine_spindle_primary=None,
            verdict=IntegrationVerdict.UNKNOWN,
            compatible_interface=None,
            provenance=(
                f"Machine '{machine.stable_id}' has no published spindle interface. "
                "UNKNOWN (not PASS)."
            ),
        )

    best = IntegrationVerdict.FAIL
    compatible_interface: str | None = None

    for iface in machine_interfaces:
        result = check_holder_machine_spindle_compatibility(holder_raw, iface)
        v = from_interface_compatibility_verdict(result.verdict)
        if v == IntegrationVerdict.PASS:
            best = IntegrationVerdict.PASS
            compatible_interface = iface
            break
        if v == IntegrationVerdict.UNKNOWN and best == IntegrationVerdict.FAIL:
            best = IntegrationVerdict.UNKNOWN

    if best == IntegrationVerdict.PASS:
        provenance = (
            f"Holder '{holder_raw}' normalized-matches machine interface "
            f"'{compatible_interface}'. CAT40≠BT40 enforced."
        )
    elif best == IntegrationVerdict.FAIL:
        provenance = (
            f"Holder '{holder_raw}' does not normalized-match any of machine "
            f"interfaces {machine_interfaces}. CAT40≠BT40 enforced."
        )
    else:
        provenance = (
            f"Holder '{holder_raw}' vs machine interfaces {machine_interfaces}: "
            "one or more interfaces unrecognized — UNKNOWN (not PASS)."
        )

    return SpindleCheckDetail(
        holder_spindle_raw=holder_raw,
        machine_spindle_primary=machine_interfaces[0],
        verdict=best,
        compatible_interface=compatible_interface,
        provenance=provenance,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def enhanced_evaluate(
    req: CompatibilityRequest,
    *,
    use_spindle_normalization: bool = True,
    use_integration_verdict: bool = True,
) -> EnhancedCompatibilityResult:
    """Evaluate compatibility with optional spindle normalization and verdict wiring.

    Calls ``engine.evaluate(req)`` unchanged (legacy path preserved), then
    optionally applies integration-layer enhancements:

      use_spindle_normalization=True (MC-4):
        Replaces the legacy plain-string spindle check with the normalized
        interface-family comparison from ``spindle_adapter``.

      use_integration_verdict=True (MC-5):
        Aggregates all applicable rule statuses into a single
        ``IntegrationVerdict`` via ``combine_verdicts()``.

    Both flags default to True (new opt-in behavior). Pass False for either to
    fall back to the legacy behavior for that component.
    """
    base = evaluate(req)

    # -- MC-4: spindle normalization -----------------------------------------
    spindle_detail: SpindleCheckDetail | None = None

    if use_spindle_normalization:
        machine = _MACHINES[req.machine_id]
        holder = _HOLDERS[req.holder_id]
        spindle_detail = _check_spindle_normalized(machine, holder)
        spindle_verdict = spindle_detail.verdict
    else:
        # Derive spindle verdict from legacy MACHINE_HOLDER_INTERFACE rule result
        mhi = next(
            (r for r in base.rule_results if r.rule_id == "MACHINE_HOLDER_INTERFACE"),
            None,
        )
        spindle_verdict = (
            _map_rule_status(mhi.status) or IntegrationVerdict.UNKNOWN
        ) if mhi else IntegrationVerdict.UNKNOWN

    # -- MC-5: IntegrationVerdict aggregation --------------------------------
    if use_integration_verdict:
        rule_verdicts: list[IntegrationVerdict] = []
        provenance: list[str] = []

        for r in base.rule_results:
            if r.rule_id == "MACHINE_HOLDER_INTERFACE" and use_spindle_normalization:
                # Substitute normalized spindle verdict for this rule
                rule_verdicts.append(spindle_verdict)
                provenance.append(
                    f"MACHINE_HOLDER_INTERFACE(normalized)={spindle_verdict}"
                )
            else:
                v = _map_rule_status(r.status)
                if v is not None:
                    rule_verdicts.append(v)
                    provenance.append(f"{r.rule_id}={v}")

        overall_verdict = combine_verdicts(*rule_verdicts)
    else:
        # Map overall_status from legacy response
        _legacy_map: dict[str, IntegrationVerdict] = {
            "COMPATIBLE": IntegrationVerdict.PASS,
            "INCOMPATIBLE": IntegrationVerdict.FAIL,
            "INSUFFICIENT_DATA": IntegrationVerdict.UNKNOWN,
        }
        overall_verdict = _legacy_map.get(base.overall_status, IntegrationVerdict.UNKNOWN)
        provenance = [f"legacy_overall_status={base.overall_status}"]

    return EnhancedCompatibilityResult(
        base_response=base,
        spindle_verdict=spindle_verdict,
        spindle_detail=spindle_detail,
        overall_verdict=overall_verdict,
        verdict_provenance=provenance,
        use_spindle_normalization=use_spindle_normalization,
        use_integration_verdict=use_integration_verdict,
    )
