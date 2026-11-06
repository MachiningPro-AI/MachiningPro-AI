"""Tests for the Tool Selection Engine — Phase 4."""
from __future__ import annotations

import pytest

from backend.cutting_tools.catalog_models import CuttingToolCatalogRecord
from backend.cutting_tools.compatibility import CompatibilityStatus
from backend.cutting_tools.holder_models import (
    HolderCapacity,
    HolderInterface,
    HolderSourceMetadata,
    ToolHolderRecord,
)
from backend.cutting_tools.insert_models import (
    InsertGeometry,
    InsertGrade,
    InsertRecord,
    InsertSourceMetadata,
)
from backend.cutting_tools.library import ToolLibrary
from backend.cutting_tools.selection_engine import (
    ToolSelectionEngine,
    ToolSelectionReason,
    ToolSelectionRequest,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_tool(
    stable_id: str = "acme-drill-8mm",
    operations: list[str] | None = None,
    diameter_mm: float | None = 8.0,
    cutting_len_mm: float | None = 30.0,
    shank_mm: float | None = 8.0,
    through_coolant: bool | None = None,
    iso_groups: list[str] | None = None,
    evidence_status: str = "MANUFACTURER_CATALOG",
    catalog_code: str | None = "CAT-001",
    insert_designation: str | None = None,
) -> CuttingToolCatalogRecord:
    return CuttingToolCatalogRecord(
        stable_id=stable_id,
        manufacturer="Acme",
        product_name="Test Tool",
        tool_category="Drilling",
        tool_category_code="DRILL",
        iso_material_groups=iso_groups or ["P", "M", "K"],
        supported_operations=operations or ["drilling"],
        cutting_diameter_mm=diameter_mm,
        cutting_length_mm=cutting_len_mm,
        shank_diameter_mm=shank_mm,
        through_coolant=through_coolant,
        iso_insert_designation=insert_designation,
        catalog_code=catalog_code,
        source_title="Test Catalog",
        source_authority="Acme Tooling",
        evidence_status=evidence_status,
        missing_fields=[],
    )


def _make_holder(
    stable_id: str = "acme-er32-collet",
    holder_type: HolderInterface = HolderInterface.ER_COLLET,
    min_shank: float = 3.0,
    max_shank: float = 20.0,
    spindle: str | None = "BT40",
    supports_coolant: bool | None = None,
) -> ToolHolderRecord:
    return ToolHolderRecord(
        stable_id=stable_id,
        manufacturer="Acme",
        product_name="Test Holder",
        holder_type=holder_type,
        spindle_interface=spindle,
        capacity=HolderCapacity(min_shank_mm=min_shank, max_shank_mm=max_shank),
        supports_coolant=supports_coolant,
        compatible_operations=["drilling", "milling", "reaming"],
        provenance=HolderSourceMetadata(
            source_title="Acme Catalog",
            source_authority="Acme",
            evidence_status="MANUFACTURER_CATALOG",
        ),
    )


def _make_insert(stable_id: str = "sandvik-cnmg-120408") -> InsertRecord:
    from backend.cutting_tools.iso1832_parser import parse_iso1832
    return InsertRecord(
        stable_id=stable_id,
        manufacturer="Sandvik",
        product_name="Test Insert",
        designation=parse_iso1832("CNMG120408"),
        geometry=InsertGeometry(shape_code="C"),
        grade=InsertGrade(),
        provenance=InsertSourceMetadata(
            source_title="Sandvik Catalog",
            source_authority="Sandvik",
            evidence_status="MANUFACTURER_CATALOG",
        ),
        iso_material_groups=["P", "M"],
        supported_operations=["turning"],
    )


def _engine(*tools: CuttingToolCatalogRecord) -> ToolSelectionEngine:
    return ToolSelectionEngine(list(tools))


# ── ToolSelectionRequest ──────────────────────────────────────────────────────

class TestToolSelectionRequest:
    def test_minimal_construction(self):
        req = ToolSelectionRequest(operation="drilling")
        assert req.operation == "drilling"
        assert req.required_diameter_mm is None
        assert req.iso_material_group is None
        assert not req.require_insert
        assert not req.require_manufacturer_catalog
        assert req.diameter_tolerance_mm == pytest.approx(0.001)

    def test_full_construction(self):
        req = ToolSelectionRequest(
            operation="milling",
            required_diameter_mm=12.0,
            machining_depth_mm=50.0,
            required_reach_mm=60.0,
            required_cutting_length_mm=35.0,
            iso_material_group="P",
            spindle_interface="BT40",
            coolant_required=True,
            require_insert=True,
            require_manufacturer_catalog=True,
            diameter_tolerance_mm=0.05,
        )
        assert req.operation == "milling"
        assert req.required_diameter_mm == pytest.approx(12.0)
        assert req.iso_material_group == "P"
        assert req.require_insert

    def test_holders_and_inserts_default_empty(self):
        req = ToolSelectionRequest(operation="drilling")
        assert req.holders == []
        assert req.inserts == []


# ── ToolSelectionReason ───────────────────────────────────────────────────────

class TestToolSelectionReason:
    def test_exactly_one_outcome(self):
        r = ToolSelectionReason(
            code="TEST", description="test",
            is_pass=True, is_unknown=False, is_fail=False,
        )
        assert r.is_pass
        assert not r.is_unknown
        assert not r.is_fail

    def test_fail_reason(self):
        r = ToolSelectionReason(
            code="DIAM", description="wrong",
            is_pass=False, is_unknown=False, is_fail=True,
        )
        assert r.is_fail

    def test_unknown_reason(self):
        r = ToolSelectionReason(
            code="UNKNOWN_X", description="unknown",
            is_pass=False, is_unknown=True, is_fail=False,
        )
        assert r.is_unknown


# ── Engine — discovery ────────────────────────────────────────────────────────

class TestDiscovery:
    def test_no_records_returns_empty(self):
        eng = ToolSelectionEngine([])
        result = eng.select(ToolSelectionRequest(operation="drilling"))
        assert result.total_candidates_evaluated == 0
        assert result.recommended == []
        assert result.uncertain == []
        assert result.rejected == []

    def test_no_matching_operation_returns_empty(self):
        tool = _make_tool(operations=["milling"])
        eng = _engine(tool)
        result = eng.select(ToolSelectionRequest(operation="drilling"))
        assert result.total_candidates_evaluated == 0
        assert "No tools found" in result.selection_note

    def test_matching_operation_included(self):
        tool = _make_tool(operations=["drilling"])
        eng = _engine(tool)
        result = eng.select(ToolSelectionRequest(operation="drilling"))
        assert result.total_candidates_evaluated == 1

    def test_operation_case_insensitive(self):
        tool = _make_tool(operations=["Drilling"])
        eng = _engine(tool)
        result = eng.select(ToolSelectionRequest(operation="DRILLING"))
        assert result.total_candidates_evaluated == 1

    def test_require_manufacturer_catalog_excludes_unverified(self):
        verified = _make_tool(stable_id="a", evidence_status="MANUFACTURER_CATALOG")
        unverified = _make_tool(stable_id="b", evidence_status="UNVERIFIED")
        eng = _engine(verified, unverified)
        result = eng.select(ToolSelectionRequest(
            operation="drilling",
            require_manufacturer_catalog=True,
        ))
        assert result.total_candidates_evaluated == 1
        ids = [c.tool.stable_id for c in result.recommended + result.uncertain + result.rejected]
        assert "a" in ids
        assert "b" not in ids

    def test_require_insert_excludes_non_insert_tools(self):
        solid = _make_tool(stable_id="solid", insert_designation=None)
        indexable = _make_tool(stable_id="idx", insert_designation="CNMG120408")
        eng = _engine(solid, indexable)
        result = eng.select(ToolSelectionRequest(operation="drilling", require_insert=True))
        ids = [c.tool.stable_id for c in result.recommended + result.uncertain + result.rejected]
        assert "idx" in ids
        assert "solid" not in ids

    def test_multiple_operations_match(self):
        t1 = _make_tool(stable_id="t1", operations=["drilling", "reaming"])
        t2 = _make_tool(stable_id="t2", operations=["milling"])
        eng = _engine(t1, t2)
        result = eng.select(ToolSelectionRequest(operation="reaming"))
        assert result.total_candidates_evaluated == 1
        ids = [c.tool.stable_id for c in result.recommended + result.uncertain + result.rejected]
        assert "t1" in ids


# ── Engine — evaluation ───────────────────────────────────────────────────────

class TestEvaluation:
    def test_pass_when_all_criteria_met(self):
        tool = _make_tool(
            diameter_mm=8.0,
            iso_groups=["P"],
            cutting_len_mm=30.0,
            through_coolant=True,
            evidence_status="MANUFACTURER_CATALOG",
        )
        eng = _engine(tool)
        result = eng.select(ToolSelectionRequest(
            operation="drilling",
            required_diameter_mm=8.0,
            iso_material_group="P",
            required_cutting_length_mm=25.0,
            coolant_required=True,
        ))
        assert len(result.recommended) == 1
        assert result.recommended[0].readiness_status == CompatibilityStatus.PASS

    def test_fail_on_diameter_mismatch(self):
        tool = _make_tool(diameter_mm=10.0)
        eng = _engine(tool)
        result = eng.select(ToolSelectionRequest(operation="drilling", required_diameter_mm=8.0))
        assert len(result.rejected) == 1
        codes = [r.code for r in result.rejected[0].reasons]
        assert "DIAMETER_MISMATCH" in codes

    def test_unknown_when_diameter_is_none(self):
        tool = _make_tool(diameter_mm=None)
        eng = _engine(tool)
        result = eng.select(ToolSelectionRequest(operation="drilling", required_diameter_mm=8.0))
        assert len(result.uncertain) == 1
        codes = [r.code for r in result.uncertain[0].reasons]
        assert "DIAMETER_UNKNOWN" in codes

    def test_fail_on_material_mismatch(self):
        tool = _make_tool(iso_groups=["K", "N"])
        eng = _engine(tool)
        result = eng.select(ToolSelectionRequest(operation="drilling", iso_material_group="P"))
        assert len(result.rejected) == 1
        codes = [r.code for r in result.rejected[0].reasons]
        assert "MATERIAL_FAIL" in codes

    def test_pass_when_no_material_specified(self):
        tool = _make_tool()
        eng = _engine(tool)
        result = eng.select(ToolSelectionRequest(operation="drilling"))
        # MANUFACTURER_CATALOG → PASS
        assert len(result.recommended) == 1

    def test_fail_when_cutting_length_too_short(self):
        tool = _make_tool(cutting_len_mm=20.0)
        eng = _engine(tool)
        result = eng.select(ToolSelectionRequest(
            operation="drilling", required_cutting_length_mm=30.0,
        ))
        assert len(result.rejected) == 1
        codes = [r.code for r in result.rejected[0].reasons]
        assert "CUTTING_LENGTH_FAIL" in codes

    def test_unknown_when_cutting_length_none(self):
        tool = _make_tool(cutting_len_mm=None)
        eng = _engine(tool)
        result = eng.select(ToolSelectionRequest(
            operation="drilling", required_cutting_length_mm=30.0,
        ))
        assert len(result.uncertain) == 1

    def test_fail_when_coolant_required_and_false(self):
        tool = _make_tool(through_coolant=False)
        eng = _engine(tool)
        result = eng.select(ToolSelectionRequest(operation="drilling", coolant_required=True))
        assert len(result.rejected) == 1
        codes = [r.code for r in result.rejected[0].reasons]
        assert "COOLANT_FAIL" in codes

    def test_unknown_when_coolant_required_and_none(self):
        tool = _make_tool(through_coolant=None)
        eng = _engine(tool)
        result = eng.select(ToolSelectionRequest(operation="drilling", coolant_required=True))
        assert len(result.uncertain) == 1

    def test_pass_when_coolant_not_required(self):
        tool = _make_tool(through_coolant=None)
        eng = _engine(tool)
        result = eng.select(ToolSelectionRequest(operation="drilling", coolant_required=False))
        assert len(result.recommended) == 1

    def test_unverified_provenance_gives_unknown_at_best(self):
        tool = _make_tool(evidence_status="UNVERIFIED", catalog_code=None)
        eng = _engine(tool)
        result = eng.select(ToolSelectionRequest(operation="drilling"))
        # UNVERIFIED → UNKNOWN, never PASS
        assert len(result.recommended) == 0
        assert len(result.uncertain) == 1

    def test_fail_takes_precedence_over_unknown(self):
        # Diameter mismatch (FAIL) + cutting_length=None (UNKNOWN)
        tool = _make_tool(diameter_mm=10.0, cutting_len_mm=None)
        eng = _engine(tool)
        result = eng.select(ToolSelectionRequest(
            operation="drilling",
            required_diameter_mm=8.0,
            required_cutting_length_mm=25.0,
        ))
        assert len(result.rejected) == 1
        assert result.rejected[0].readiness_status == CompatibilityStatus.FAIL

    def test_diameter_tolerance_respected(self):
        tool = _make_tool(diameter_mm=8.005)
        eng = _engine(tool)
        # Default tolerance 0.001 — 8.005 is 0.005 off → FAIL
        result_tight = eng.select(ToolSelectionRequest(
            operation="drilling", required_diameter_mm=8.0,
        ))
        assert len(result_tight.rejected) == 1

        # With 0.01 tolerance → PASS
        result_loose = eng.select(ToolSelectionRequest(
            operation="drilling", required_diameter_mm=8.0, diameter_tolerance_mm=0.01,
        ))
        assert len(result_loose.recommended) == 1

    def test_pass_includes_operation_match_reason(self):
        tool = _make_tool()
        eng = _engine(tool)
        result = eng.select(ToolSelectionRequest(operation="drilling"))
        candidate = result.recommended[0]
        codes = [r.code for r in candidate.reasons]
        assert "OPERATION_MATCH" in codes

    def test_provenance_verified_reason_present(self):
        tool = _make_tool(evidence_status="MANUFACTURER_CATALOG", catalog_code="X123")
        eng = _engine(tool)
        result = eng.select(ToolSelectionRequest(operation="drilling"))
        codes = [r.code for r in result.recommended[0].reasons]
        assert "PROVENANCE_VERIFIED" in codes


# ── Engine — ranking ──────────────────────────────────────────────────────────

class TestRanking:
    def test_recommended_before_uncertain(self):
        # PASS tool should come first in final grouping
        pass_tool = _make_tool(stable_id="a-pass", diameter_mm=8.0)
        unknown_tool = _make_tool(stable_id="b-unknown", diameter_mm=None)
        eng = _engine(pass_tool, unknown_tool)
        result = eng.select(ToolSelectionRequest(operation="drilling", required_diameter_mm=8.0))
        assert len(result.recommended) == 1
        assert len(result.uncertain) == 1
        assert result.recommended[0].tool.stable_id == "a-pass"
        assert result.uncertain[0].tool.stable_id == "b-unknown"

    def test_fail_in_rejected_not_recommended(self):
        fail_tool = _make_tool(stable_id="bad", diameter_mm=10.0)
        eng = _engine(fail_tool)
        result = eng.select(ToolSelectionRequest(operation="drilling", required_diameter_mm=8.0))
        assert len(result.rejected) == 1
        assert len(result.recommended) == 0
        assert len(result.uncertain) == 0

    def test_deterministic_tie_break_by_stable_id(self):
        # Two identical PASS tools — tie-break by stable_id ascending
        t_z = _make_tool(stable_id="z-tool", diameter_mm=8.0)
        t_a = _make_tool(stable_id="a-tool", diameter_mm=8.0)
        eng = _engine(t_z, t_a)
        result = eng.select(ToolSelectionRequest(operation="drilling", required_diameter_mm=8.0))
        assert len(result.recommended) == 2
        assert result.recommended[0].tool.stable_id == "a-tool"
        assert result.recommended[1].tool.stable_id == "z-tool"

    def test_higher_pass_count_ranks_first(self):
        # t_rich passes diameter + material + cutting_length
        # t_lean passes only operation (no constraints given so both PASS the same)
        # To differentiate: t_rich has catalog_code, t_lean does not
        t_rich = _make_tool(
            stable_id="b-rich",
            evidence_status="MANUFACTURER_CATALOG",
            catalog_code="RICH-001",
        )
        t_lean = _make_tool(
            stable_id="a-lean",
            evidence_status="MANUFACTURER_CATALOG",
            catalog_code=None,
        )
        eng = _engine(t_rich, t_lean)
        result = eng.select(ToolSelectionRequest(operation="drilling"))
        assert len(result.recommended) == 2
        # t_rich has catalog_code bonus → higher score → first
        assert result.recommended[0].tool.stable_id == "b-rich"

    def test_ranking_score_positive_for_recommended(self):
        tool = _make_tool()
        eng = _engine(tool)
        result = eng.select(ToolSelectionRequest(operation="drilling"))
        assert result.recommended[0].ranking_score > 0

    def test_ranking_explanation_non_empty(self):
        tool = _make_tool()
        eng = _engine(tool)
        result = eng.select(ToolSelectionRequest(operation="drilling"))
        assert len(result.recommended[0].ranking_explanation) > 0


# ── Engine — result structure ─────────────────────────────────────────────────

class TestResultStructure:
    def test_result_carries_original_request(self):
        eng = ToolSelectionEngine([])
        req = ToolSelectionRequest(operation="drilling", required_diameter_mm=8.0)
        result = eng.select(req)
        assert result.request is req

    def test_total_candidates_count(self):
        tools = [_make_tool(stable_id=f"t{i}") for i in range(5)]
        eng = ToolSelectionEngine(tools)
        result = eng.select(ToolSelectionRequest(operation="drilling"))
        assert result.total_candidates_evaluated == 5

    def test_all_rejected_gives_note(self):
        tool = _make_tool(diameter_mm=10.0)
        eng = _engine(tool)
        result = eng.select(ToolSelectionRequest(operation="drilling", required_diameter_mm=8.0))
        assert result.selection_note is not None
        assert "rejected" in result.selection_note

    def test_no_matching_operation_gives_note(self):
        eng = ToolSelectionEngine([])
        result = eng.select(ToolSelectionRequest(operation="exotic-op"))
        assert result.selection_note is not None

    def test_successful_result_has_no_note(self):
        tool = _make_tool()
        eng = _engine(tool)
        result = eng.select(ToolSelectionRequest(operation="drilling"))
        assert result.selection_note is None


# ── Engine — assembly candidates ─────────────────────────────────────────────

class TestAssemblyCandidates:
    def test_tool_only_when_no_holders(self):
        tool = _make_tool()
        eng = _engine(tool)
        result = eng.select(ToolSelectionRequest(operation="drilling"))
        candidate = result.recommended[0] if result.recommended else result.uncertain[0]
        assert candidate.holder is None
        assert candidate.assembly_validation is None

    def test_assembly_candidate_created_per_holder(self):
        tool = _make_tool(shank_mm=8.0)
        holder = _make_holder(min_shank=3.0, max_shank=20.0)
        eng = _engine(tool)
        result = eng.select(ToolSelectionRequest(
            operation="drilling",
            holders=[holder],
        ))
        assert result.total_candidates_evaluated == 1
        candidate = result.recommended[0] if result.recommended else result.uncertain[0]
        assert candidate.holder is not None
        assert candidate.assembly_validation is not None

    def test_shank_too_large_for_holder_gives_fail_or_unknown(self):
        # shank 25mm > holder max 20mm → FAIL on tool-holder compatibility
        tool = _make_tool(shank_mm=25.0)
        holder = _make_holder(min_shank=3.0, max_shank=20.0)
        eng = _engine(tool)
        result = eng.select(ToolSelectionRequest(
            operation="drilling",
            holders=[holder],
        ))
        # Should produce at least one candidate, and it should not be PASS
        all_candidates = result.recommended + result.uncertain + result.rejected
        assert len(all_candidates) == 1
        assert all_candidates[0].readiness_status != CompatibilityStatus.PASS

    def test_multiple_holders_produce_multiple_candidates(self):
        tool = _make_tool(shank_mm=8.0)
        h1 = _make_holder(stable_id="holder-a", min_shank=3.0, max_shank=20.0)
        h2 = _make_holder(stable_id="holder-b", min_shank=3.0, max_shank=20.0)
        eng = _engine(tool)
        result = eng.select(ToolSelectionRequest(
            operation="drilling",
            holders=[h1, h2],
        ))
        assert result.total_candidates_evaluated == 2

    def test_assembly_validation_stored_on_candidate(self):
        tool = _make_tool(shank_mm=8.0)
        holder = _make_holder()
        eng = _engine(tool)
        result = eng.select(ToolSelectionRequest(operation="drilling", holders=[holder]))
        all_cands = result.recommended + result.uncertain + result.rejected
        assert all(c.assembly_validation is not None for c in all_cands)

    def test_assembly_with_insert(self):
        tool = _make_tool(shank_mm=8.0)
        holder = _make_holder()
        insert = _make_insert()
        eng = _engine(tool)
        result = eng.select(ToolSelectionRequest(
            operation="drilling",
            holders=[holder],
            inserts=[insert],
        ))
        all_cands = result.recommended + result.uncertain + result.rejected
        assert len(all_cands) == 1
        # The candidate carries the insert reference
        c = all_cands[0]
        assert c.insert is not None


# ── Integration tests with real ToolLibrary ───────────────────────────────────

class TestIntegrationWithRealLibrary:
    @pytest.fixture(scope="class")
    @classmethod
    def eng(cls):
        return ToolSelectionEngine(ToolLibrary().all())

    def test_select_drilling_returns_candidates(self, eng: ToolSelectionEngine):
        result = eng.select(ToolSelectionRequest(operation="drilling"))
        total = result.total_candidates_evaluated
        assert total > 0

    def test_select_nonexistent_operation_returns_empty(self, eng: ToolSelectionEngine):
        result = eng.select(ToolSelectionRequest(operation="zapping"))
        assert result.total_candidates_evaluated == 0
        assert result.recommended == []
        assert result.uncertain == []
        assert result.rejected == []

    def test_select_milling_returns_candidates(self, eng: ToolSelectionEngine):
        result = eng.select(ToolSelectionRequest(operation="milling"))
        assert result.total_candidates_evaluated > 0

    def test_recommended_are_pass_status(self, eng: ToolSelectionEngine):
        result = eng.select(ToolSelectionRequest(operation="drilling"))
        for c in result.recommended:
            assert c.readiness_status == CompatibilityStatus.PASS

    def test_uncertain_are_unknown_status(self, eng: ToolSelectionEngine):
        result = eng.select(ToolSelectionRequest(operation="drilling"))
        for c in result.uncertain:
            assert c.readiness_status == CompatibilityStatus.UNKNOWN

    def test_rejected_are_fail_status(self, eng: ToolSelectionEngine):
        result = eng.select(ToolSelectionRequest(operation="drilling"))
        for c in result.rejected:
            assert c.readiness_status == CompatibilityStatus.FAIL

    def test_recommended_ordered_by_score_desc(self, eng: ToolSelectionEngine):
        result = eng.select(ToolSelectionRequest(operation="drilling"))
        scores = [c.ranking_score for c in result.recommended]
        assert scores == sorted(scores, reverse=True)

    def test_uncertain_ordered_by_score_desc(self, eng: ToolSelectionEngine):
        result = eng.select(ToolSelectionRequest(operation="drilling"))
        scores = [c.ranking_score for c in result.uncertain]
        assert scores == sorted(scores, reverse=True)

    def test_tie_break_within_same_score_by_stable_id(self, eng: ToolSelectionEngine):
        result = eng.select(ToolSelectionRequest(operation="drilling"))
        # Group by score, check stable_id ascending within each score tier
        for clist in [result.recommended, result.uncertain]:
            prev_score = None
            ids_at_score: list[str] = []
            for c in clist:
                if c.ranking_score != prev_score:
                    if ids_at_score:
                        assert ids_at_score == sorted(ids_at_score)
                    ids_at_score = [c.tool.stable_id]
                    prev_score = c.ranking_score
                else:
                    ids_at_score.append(c.tool.stable_id)

    def test_strict_diameter_filter_reduces_candidates(self, eng: ToolSelectionEngine):
        all_result = eng.select(ToolSelectionRequest(operation="drilling"))
        narrow_result = eng.select(ToolSelectionRequest(
            operation="drilling",
            required_diameter_mm=8.0,
            diameter_tolerance_mm=0.001,
        ))
        # Filtering by exact 8mm must not produce MORE candidates
        all_total = all_result.total_candidates_evaluated
        narrow_total = narrow_result.total_candidates_evaluated
        assert narrow_total <= all_total

    def test_material_group_p_selects_subset(self, eng: ToolSelectionEngine):
        all_result = eng.select(ToolSelectionRequest(operation="drilling"))
        p_result = eng.select(ToolSelectionRequest(
            operation="drilling", iso_material_group="P",
        ))
        # Filtering should not increase the PASS count
        p_recommended = len(p_result.recommended)
        all_total = all_result.total_candidates_evaluated
        assert p_recommended <= all_total

    def test_manufacturer_catalog_filter_excludes_unverified(self, eng: ToolSelectionEngine):
        all_result = eng.select(ToolSelectionRequest(operation="drilling"))
        cat_result = eng.select(ToolSelectionRequest(
            operation="drilling",
            require_manufacturer_catalog=True,
        ))
        assert cat_result.total_candidates_evaluated <= all_result.total_candidates_evaluated

    def test_result_total_equals_sum_of_buckets(self, eng: ToolSelectionEngine):
        result = eng.select(ToolSelectionRequest(operation="drilling"))
        assert result.total_candidates_evaluated == (
            len(result.recommended) + len(result.uncertain) + len(result.rejected)
        )
