"""Tool Selection Engine — Phase 4.

Discovers, evaluates and ranks candidate cutting tools for a machining
operation using the existing Phase 1–3 Tool Library.

Design rules
------------
- PASS candidates are recommended; UNKNOWN are preserved as uncertain;
  FAIL candidates are excluded from recommendations but included in
  ``rejected`` for diagnostics.
- Missing data never produces confirmed compatibility (PASS).
- UNVERIFIED records may be UNKNOWN at best, never PASS.
- Rankings are deterministic: score descending, then stable_id ascending.
- No cutting speeds, feeds, cycle times or prices are invented.
- No holders or inserts are invented to complete an assembly.
"""
from __future__ import annotations

from pydantic import BaseModel

from .assembly_compatibility import validate_assembly
from .assembly_models import (
    ToolAssemblyGeometry,
    ToolAssemblyRecord,
    ToolAssemblySourceMetadata,
    ToolAssemblyValidationResult,
)
from .catalog_models import CuttingToolCatalogRecord
from .compatibility import CompatibilityStatus
from .holder_models import ToolHolderRecord
from .insert_models import InsertRecord

# ── Request ───────────────────────────────────────────────────────────────────

class ToolSelectionRequest(BaseModel):
    """Declared process requirements for tool selection.

    Machine Library integration point
    ----------------------------------
    ``spindle_interface`` carries the required machine spindle type as a plain
    string; wire from Machine Library when available.

    Material Library integration point
    ------------------------------------
    ``iso_material_group`` carries the ISO 513 group code (P/M/K/N/S/H) as a
    plain string; wire from Material Library when available.
    """

    operation: str
    required_diameter_mm: float | None = None
    machining_depth_mm: float | None = None
    required_reach_mm: float | None = None
    required_cutting_length_mm: float | None = None
    iso_material_group: str | None = None           # P / M / K / N / S / H
    spindle_interface: str | None = None            # BT40, HSK-A63, …
    coolant_required: bool | None = None
    require_insert: bool = False                     # only indexable insert tools
    require_manufacturer_catalog: bool = False       # only MANUFACTURER_CATALOG provenance
    diameter_tolerance_mm: float = 0.001            # allowed deviation on diameter match

    # Optional holders / inserts for assembly-level evaluation
    holders: list[ToolHolderRecord] = []
    inserts: list[InsertRecord] = []


# ── Reason and candidate ──────────────────────────────────────────────────────

class ToolSelectionReason(BaseModel):
    """One selection-criterion evaluation with an explicit outcome."""

    code: str           # OPERATION_MATCH, DIAMETER_FAIL, MATERIAL_UNKNOWN, …
    description: str
    is_pass: bool
    is_unknown: bool
    is_fail: bool


class ToolSelectionCandidate(BaseModel):
    """A candidate tool (optionally with holder/insert) and its evaluation."""

    tool: CuttingToolCatalogRecord
    holder: ToolHolderRecord | None = None
    insert: InsertRecord | None = None
    readiness_status: CompatibilityStatus
    reasons: list[ToolSelectionReason]
    ranking_score: int
    ranking_explanation: str
    assembly_validation: ToolAssemblyValidationResult | None = None


# ── Result ────────────────────────────────────────────────────────────────────

class ToolSelectionResult(BaseModel):
    """Full selection result for one request."""

    request: ToolSelectionRequest
    recommended: list[ToolSelectionCandidate]   # PASS, ranked descending
    uncertain: list[ToolSelectionCandidate]      # UNKNOWN, ranked descending
    rejected: list[ToolSelectionCandidate]       # FAIL, diagnostic only
    total_candidates_evaluated: int
    selection_note: str | None = None


# ── Reason helpers ────────────────────────────────────────────────────────────

def _pass_reason(code: str, description: str) -> ToolSelectionReason:
    return ToolSelectionReason(
        code=code, description=description,
        is_pass=True, is_unknown=False, is_fail=False,
    )


def _unknown_reason(code: str, description: str) -> ToolSelectionReason:
    return ToolSelectionReason(
        code=code, description=description,
        is_pass=False, is_unknown=True, is_fail=False,
    )


def _fail_reason(code: str, description: str) -> ToolSelectionReason:
    return ToolSelectionReason(
        code=code, description=description,
        is_pass=False, is_unknown=False, is_fail=True,
    )


# ── Engine ────────────────────────────────────────────────────────────────────

class ToolSelectionEngine:
    """Discovers and ranks candidate tools from a record collection.

    Usage::

        from backend.cutting_tools import ToolLibrary
        from backend.cutting_tools.selection_engine import (
            ToolSelectionEngine, ToolSelectionRequest,
        )

        engine = ToolSelectionEngine(ToolLibrary().all())
        result = engine.select(ToolSelectionRequest(
            operation="drilling",
            required_diameter_mm=8.0,
            iso_material_group="P",
        ))
        for c in result.recommended:
            print(c.tool.stable_id, c.ranking_score)
    """

    def __init__(self, records: list[CuttingToolCatalogRecord]) -> None:
        self._records = list(records)

    # ── Public API ────────────────────────────────────────────────────────────

    def select(self, request: ToolSelectionRequest) -> ToolSelectionResult:
        """Run tool selection for *request*.

        Returns a :class:`ToolSelectionResult` with PASS/UNKNOWN/FAIL candidates
        ranked deterministically.
        """
        discovered = self._discover(request)

        if not request.holders:
            # Tool-only evaluation
            raw_candidates = [
                self._build_candidate(tool, request)
                for tool in discovered
            ]
        else:
            # Assembly evaluation: tool × holder combinations
            raw_candidates = []
            for tool in discovered:
                for holder in request.holders:
                    inserts_to_try: list[InsertRecord | None] = (
                        list(request.inserts) if request.inserts else [None]
                    )
                    for insert in inserts_to_try:
                        c = self._build_assembly_candidate(
                            tool, holder, insert, request
                        )
                        raw_candidates.append(c)
            # If no holders produced candidates, fall back to tool-only
            if not raw_candidates:
                raw_candidates = [
                    self._build_candidate(tool, request) for tool in discovered
                ]

        recommended = sorted(
            [c for c in raw_candidates if c.readiness_status == CompatibilityStatus.PASS],
            key=lambda c: (-c.ranking_score, c.tool.stable_id),
        )
        uncertain = sorted(
            [c for c in raw_candidates if c.readiness_status == CompatibilityStatus.UNKNOWN],
            key=lambda c: (-c.ranking_score, c.tool.stable_id),
        )
        rejected = sorted(
            [c for c in raw_candidates if c.readiness_status == CompatibilityStatus.FAIL],
            key=lambda c: (-c.ranking_score, c.tool.stable_id),
        )

        note: str | None = None
        if not raw_candidates:
            note = (
                f"No tools found for operation={request.operation!r}. "
                "Check that the catalog contains tools for this operation."
            )
        elif not recommended and not uncertain:
            note = (
                f"All {len(rejected)} candidate(s) were rejected. "
                "Review rejection reasons for guidance."
            )

        return ToolSelectionResult(
            request=request,
            recommended=recommended,
            uncertain=uncertain,
            rejected=rejected,
            total_candidates_evaluated=len(raw_candidates),
            selection_note=note,
        )

    # ── Discovery ─────────────────────────────────────────────────────────────

    def _discover(
        self, request: ToolSelectionRequest
    ) -> list[CuttingToolCatalogRecord]:
        """Pre-filter records by operation and hard requirements."""
        op = request.operation.lower().strip()
        results = [
            r for r in self._records
            if op in {o.lower() for o in r.supported_operations}
        ]
        if request.require_manufacturer_catalog:
            results = [
                r for r in results
                if r.evidence_status == "MANUFACTURER_CATALOG"
            ]
        if request.require_insert:
            results = [
                r for r in results
                if r.iso_insert_designation is not None
            ]
        return results

    # ── Tool-only candidate ───────────────────────────────────────────────────

    def _build_candidate(
        self,
        tool: CuttingToolCatalogRecord,
        request: ToolSelectionRequest,
    ) -> ToolSelectionCandidate:
        status, reasons = self._evaluate_tool(tool, request)
        score = self._rank_score(status, reasons, tool, None)
        explanation = self._rank_explanation(status, reasons, tool, None)
        return ToolSelectionCandidate(
            tool=tool,
            readiness_status=status,
            reasons=reasons,
            ranking_score=score,
            ranking_explanation=explanation,
        )

    # ── Assembly candidate ────────────────────────────────────────────────────

    def _build_assembly_candidate(
        self,
        tool: CuttingToolCatalogRecord,
        holder: ToolHolderRecord,
        insert: InsertRecord | None,
        request: ToolSelectionRequest,
    ) -> ToolSelectionCandidate:
        # Tool-level evaluation
        tool_status, tool_reasons = self._evaluate_tool(tool, request)

        # Assembly validation using minimal declared geometry
        assembly = ToolAssemblyRecord(
            stable_id=f"{tool.stable_id}+{holder.stable_id}",
            tool=tool,
            holder=holder,
            insert=insert,
            geometry=ToolAssemblyGeometry(
                shank_diameter_mm=tool.shank_diameter_mm,
                spindle_interface=holder.spindle_interface,
                coolant_enabled=(
                    True if tool.through_coolant is True and holder.supports_coolant is True
                    else None
                ),
            ),
            provenance=ToolAssemblySourceMetadata(
                source_title="ToolSelectionEngine",
                source_authority="selection_engine",
                evidence_status="UNVERIFIED",
                assembly_note="Synthetic assembly created during selection",
            ),
        )
        asm_validation = validate_assembly(assembly)

        # Merge statuses: worst of tool and assembly
        combined_statuses = [tool_status, asm_validation.overall_status]
        if CompatibilityStatus.FAIL in combined_statuses:
            final_status = CompatibilityStatus.FAIL
        elif CompatibilityStatus.UNKNOWN in combined_statuses:
            final_status = CompatibilityStatus.UNKNOWN
        else:
            final_status = CompatibilityStatus.PASS

        # Merge reasons
        assembly_reasons: list[ToolSelectionReason] = []
        for r in asm_validation.all_reasons:
            assembly_reasons.append(_pass_reason("ASSEMBLY_CHECK", r))

        all_reasons = tool_reasons + assembly_reasons

        score = self._rank_score(final_status, all_reasons, tool, asm_validation)
        explanation = self._rank_explanation(final_status, all_reasons, tool, asm_validation)

        return ToolSelectionCandidate(
            tool=tool,
            holder=holder,
            insert=insert,
            readiness_status=final_status,
            reasons=all_reasons,
            ranking_score=score,
            ranking_explanation=explanation,
            assembly_validation=asm_validation,
        )

    # ── Evaluation logic ──────────────────────────────────────────────────────

    def _evaluate_tool(
        self,
        tool: CuttingToolCatalogRecord,
        request: ToolSelectionRequest,
    ) -> tuple[CompatibilityStatus, list[ToolSelectionReason]]:
        """Evaluate a tool against the selection request criteria."""
        reasons: list[ToolSelectionReason] = []
        has_fail = False
        has_unknown = False

        # 1. Operation (soft-confirm: already pre-filtered, but record reason)
        op = request.operation.lower().strip()
        tool_ops = {o.lower() for o in tool.supported_operations}
        if op in tool_ops:
            reasons.append(_pass_reason(
                "OPERATION_MATCH",
                f"Tool supports operation {op!r}",
            ))
        else:
            reasons.append(_fail_reason(
                "OPERATION_FAIL",
                f"Tool does not support {op!r}; supports: {sorted(tool_ops)}",
            ))
            has_fail = True

        # 2. Diameter
        if request.required_diameter_mm is not None:
            tol = request.diameter_tolerance_mm
            if tool.cutting_diameter_mm is None:
                reasons.append(_unknown_reason(
                    "DIAMETER_UNKNOWN",
                    f"cutting_diameter_mm is None — cannot verify required "
                    f"{request.required_diameter_mm}mm",
                ))
                has_unknown = True
            elif abs(tool.cutting_diameter_mm - request.required_diameter_mm) > tol:
                reasons.append(_fail_reason(
                    "DIAMETER_MISMATCH",
                    f"cutting_diameter_mm={tool.cutting_diameter_mm}mm ≠ required "
                    f"{request.required_diameter_mm}mm (±{tol}mm tolerance)",
                ))
                has_fail = True
            else:
                reasons.append(_pass_reason(
                    "DIAMETER_MATCH",
                    f"Diameter {tool.cutting_diameter_mm}mm matches required "
                    f"{request.required_diameter_mm}mm",
                ))

        # 3. ISO material group
        if request.iso_material_group is not None:
            g = request.iso_material_group.upper().strip()
            if g in {m.upper() for m in tool.iso_material_groups}:
                reasons.append(_pass_reason(
                    "MATERIAL_MATCH",
                    f"Tool supports workpiece material group {g!r}",
                ))
            else:
                reasons.append(_fail_reason(
                    "MATERIAL_FAIL",
                    f"Tool does not support material group {g!r}; "
                    f"supports: {sorted(tool.iso_material_groups)}",
                ))
                has_fail = True

        # 4. Cutting length
        if request.required_cutting_length_mm is not None:
            if tool.cutting_length_mm is None:
                reasons.append(_unknown_reason(
                    "CUTTING_LENGTH_UNKNOWN",
                    f"cutting_length_mm is None — cannot verify required "
                    f"{request.required_cutting_length_mm}mm",
                ))
                has_unknown = True
            elif tool.cutting_length_mm < request.required_cutting_length_mm:
                reasons.append(_fail_reason(
                    "CUTTING_LENGTH_FAIL",
                    f"cutting_length_mm={tool.cutting_length_mm}mm < required "
                    f"{request.required_cutting_length_mm}mm",
                ))
                has_fail = True
            else:
                reasons.append(_pass_reason(
                    "CUTTING_LENGTH_OK",
                    f"Cutting length {tool.cutting_length_mm}mm ≥ required "
                    f"{request.required_cutting_length_mm}mm",
                ))

        # 5. Coolant requirement
        if request.coolant_required is True:
            if tool.through_coolant is True:
                reasons.append(_pass_reason(
                    "COOLANT_OK",
                    "Tool has through_coolant=True",
                ))
            elif tool.through_coolant is False:
                reasons.append(_fail_reason(
                    "COOLANT_FAIL",
                    "Tool has through_coolant=False — cannot satisfy coolant requirement",
                ))
                has_fail = True
            else:
                reasons.append(_unknown_reason(
                    "COOLANT_UNKNOWN",
                    "through_coolant is None — coolant capability unverified",
                ))
                has_unknown = True

        # 6. Provenance
        if tool.evidence_status == "MANUFACTURER_CATALOG" and tool.catalog_code:
            reasons.append(_pass_reason(
                "PROVENANCE_VERIFIED",
                f"Catalog-verified: catalog_code={tool.catalog_code!r}",
            ))
        elif tool.evidence_status != "MANUFACTURER_CATALOG":
            reasons.append(_unknown_reason(
                "PROVENANCE_UNVERIFIED",
                f"evidence_status={tool.evidence_status!r} — treat with caution",
            ))
            has_unknown = True

        if has_fail:
            return CompatibilityStatus.FAIL, reasons
        if has_unknown:
            return CompatibilityStatus.UNKNOWN, reasons
        return CompatibilityStatus.PASS, reasons

    # ── Ranking ───────────────────────────────────────────────────────────────

    def _rank_score(
        self,
        status: CompatibilityStatus,
        reasons: list[ToolSelectionReason],
        tool: CuttingToolCatalogRecord,
        asm: ToolAssemblyValidationResult | None,
    ) -> int:
        score = 0

        # Base by status
        if status == CompatibilityStatus.PASS:
            score += 1000
        elif status == CompatibilityStatus.UNKNOWN:
            score += 100
        # FAIL stays 0

        # Passes per criterion (more explicit passes = more confidence)
        score += sum(10 for r in reasons if r.is_pass)

        # Provenance quality
        if tool.evidence_status == "MANUFACTURER_CATALOG":
            score += 5
        if tool.catalog_code:
            score += 3

        # Assembly bonus
        if asm is not None:
            if asm.overall_status == CompatibilityStatus.PASS:
                score += 50
            elif asm.overall_status == CompatibilityStatus.UNKNOWN:
                score += 10

        return score

    def _rank_explanation(
        self,
        status: CompatibilityStatus,
        reasons: list[ToolSelectionReason],
        tool: CuttingToolCatalogRecord,
        asm: ToolAssemblyValidationResult | None,
    ) -> str:
        pass_codes = [r.code for r in reasons if r.is_pass]
        fail_codes = [r.code for r in reasons if r.is_fail]
        unknown_codes = [r.code for r in reasons if r.is_unknown]
        parts = [f"status={status.value}"]
        if pass_codes:
            parts.append(f"pass=[{', '.join(pass_codes)}]")
        if fail_codes:
            parts.append(f"fail=[{', '.join(fail_codes)}]")
        if unknown_codes:
            parts.append(f"unknown=[{', '.join(unknown_codes)}]")
        if asm is not None:
            parts.append(f"assembly={asm.overall_status.value}")
        parts.append(f"score={self._rank_score(status, reasons, tool, asm)}")
        return "; ".join(parts)
