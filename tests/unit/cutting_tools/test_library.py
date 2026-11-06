"""Unit tests for ToolLibrary, ToolFamily, and ToolLibraryQuery.

Phase 1 remediation — covers BLOCKER-4.

Scope:
- ToolFamily enum and bidirectional category-code mappings
- ToolLibrary one-shot helpers, summary, family_coverage
- ToolLibraryQuery all 13 documented filter methods + by_evidence_status
- Chain immutability and branching
- through_coolant None semantics
- GRINDING and EDM record verification
- Provenance / evidence_status classification
- Verified-only filtering
"""

import pytest

from backend.cutting_tools import (
    CATEGORY_CODE_TO_FAMILY,
    FAMILY_TO_CATEGORY_CODES,
    ToolFamily,
    ToolLibrary,
    ToolLibraryQuery,
    category_codes_for_family,
    family_for_category_code,
)


@pytest.fixture
def lib() -> ToolLibrary:
    return ToolLibrary()


# ── ToolFamily ────────────────────────────────────────────────────────────────


class TestToolFamily:
    def test_all_nine_families_defined(self):
        expected = {
            "DRILLING", "MILLING", "TURNING", "BORING", "THREADING",
            "REAMING", "GROOVING", "GRINDING", "EDM",
        }
        assert {f.value for f in ToolFamily} == expected

    def test_family_to_category_codes_all_families_present(self):
        for family in ToolFamily:
            assert family in FAMILY_TO_CATEGORY_CODES
            assert len(FAMILY_TO_CATEGORY_CODES[family]) >= 1

    def test_family_for_category_code_all_known_codes(self):
        mapping = {
            "DRILL": ToolFamily.DRILLING,
            "END_MILL": ToolFamily.MILLING,
            "FACE_MILL_INSERT": ToolFamily.MILLING,
            "FACE_MILL_BODY": ToolFamily.MILLING,
            "TURNING_INSERT": ToolFamily.TURNING,
            "BORING_BAR": ToolFamily.BORING,
            "TAP": ToolFamily.THREADING,
            "THREAD_MILL": ToolFamily.THREADING,
            "REAMER": ToolFamily.REAMING,
            "GROOVING_INSERT": ToolFamily.GROOVING,
            "GRINDING_WHEEL": ToolFamily.GRINDING,
            "EDM_WIRE": ToolFamily.EDM,
            "EDM_ELECTRODE": ToolFamily.EDM,
        }
        for code, expected_family in mapping.items():
            assert family_for_category_code(code) == expected_family, (
                f"family_for_category_code({code!r}) returned {family_for_category_code(code)!r};"
                f" expected {expected_family!r}"
            )

    def test_unknown_category_code_returns_none(self):
        assert family_for_category_code("NONEXISTENT") is None
        assert family_for_category_code("") is None

    def test_category_codes_for_family_returns_frozenset(self):
        codes = category_codes_for_family(ToolFamily.THREADING)
        assert isinstance(codes, frozenset)
        assert "TAP" in codes
        assert "THREAD_MILL" in codes

    def test_bidirectional_mapping_consistent(self):
        """Every code in FAMILY_TO_CATEGORY_CODES maps back to same family."""
        for family, codes in FAMILY_TO_CATEGORY_CODES.items():
            for code in codes:
                assert CATEGORY_CODE_TO_FAMILY[code] == family, (
                    f"CATEGORY_CODE_TO_FAMILY[{code!r}] = "
                    f"{CATEGORY_CODE_TO_FAMILY.get(code)!r}; expected {family!r}"
                )


# ── ToolLibrary ───────────────────────────────────────────────────────────────


class TestToolLibrary:
    def test_all_returns_47_records(self, lib):
        assert len(lib.all()) == 47

    def test_summary_tool_count(self, lib):
        assert lib.summary().tool_count == 47

    def test_summary_manufacturer_count(self, lib):
        assert lib.summary().manufacturer_count == 9

    def test_summary_category_count(self, lib):
        assert lib.summary().category_count == 12

    def test_summary_evidence_status_dominant(self, lib):
        # 44 MANUFACTURER_CATALOG > 3 UNVERIFIED — Counter.most_common picks dominant
        assert lib.summary().evidence_status == "MANUFACTURER_CATALOG"

    def test_summary_iso_groups_all_six(self, lib):
        assert set(lib.summary().iso_material_groups) == {"P", "M", "K", "N", "S", "H"}

    def test_find_by_id_known_record(self, lib):
        r = lib.find_by_id("sandvik-835b-0801-a1-mf-1024")
        assert r is not None
        assert r.manufacturer == "Sandvik Coromant"
        assert r.tool_category_code == "REAMER"

    def test_find_by_id_unknown_returns_none(self, lib):
        assert lib.find_by_id("nonexistent-tool-xyz-99999") is None

    def test_family_coverage_all_nine_present(self, lib):
        cov = lib.family_coverage()
        assert set(cov.keys()) == {f.value for f in ToolFamily}

    def test_family_coverage_counts(self, lib):
        cov = lib.family_coverage()
        assert cov["DRILLING"] == 5
        assert cov["MILLING"] == 12
        assert cov["TURNING"] == 11
        assert cov["BORING"] == 1
        assert cov["THREADING"] == 6
        assert cov["REAMING"] == 1
        assert cov["GROOVING"] == 4
        assert cov["GRINDING"] == 3
        assert cov["EDM"] == 4

    def test_all_stable_ids_unique(self, lib):
        ids = [r.stable_id for r in lib.all()]
        assert len(ids) == len(set(ids))

    def test_query_returns_toollibraryquery(self, lib):
        assert isinstance(lib.query(), ToolLibraryQuery)

    def test_by_family_shortcut(self, lib):
        drills = lib.by_family(ToolFamily.DRILLING)
        assert all(r.tool_category_code == "DRILL" for r in drills)

    def test_by_operation_shortcut(self, lib):
        assert len(lib.by_operation("grinding")) == 3

    def test_by_material_groups_shortcut(self, lib):
        h = lib.by_material_groups(["H"])
        assert len(h) >= 2

    def test_by_manufacturer_shortcut(self, lib):
        sandvik = lib.by_manufacturer("Sandvik Coromant")
        assert len(sandvik) > 0
        assert all(r.manufacturer == "Sandvik Coromant" for r in sandvik)


# ── ToolLibraryQuery — all 13 filters ────────────────────────────────────────


class TestFilterByFamily:
    def test_drilling_count_and_category_code(self, lib):
        r = lib.query().by_family(ToolFamily.DRILLING).results()
        assert len(r) == 5
        assert all(rec.tool_category_code == "DRILL" for rec in r)

    def test_milling_includes_face_mill_insert(self, lib):
        codes = {
            rec.tool_category_code for rec in lib.query().by_family(ToolFamily.MILLING).results()
        }
        assert "END_MILL" in codes
        assert "FACE_MILL_INSERT" in codes

    def test_threading_includes_tap_and_thread_mill(self, lib):
        codes = {
            rec.tool_category_code for rec in lib.query().by_family(ToolFamily.THREADING).results()
        }
        assert "TAP" in codes
        assert "THREAD_MILL" in codes

    def test_edm_includes_wire_and_electrode(self, lib):
        codes = {rec.tool_category_code for rec in lib.query().by_family(ToolFamily.EDM).results()}
        assert "EDM_WIRE" in codes
        assert "EDM_ELECTRODE" in codes

    def test_grinding_category_codes(self, lib):
        r = lib.query().by_family(ToolFamily.GRINDING).results()
        assert len(r) == 3
        assert all(rec.tool_category_code == "GRINDING_WHEEL" for rec in r)


class TestFilterByOperation:
    def test_grinding_operation(self, lib):
        assert lib.query().by_operation("grinding").count() == 3

    def test_case_insensitive(self, lib):
        assert (
            lib.query().by_operation("GRINDING").count()
            == lib.query().by_operation("grinding").count()
        )

    def test_edm_operation(self, lib):
        assert lib.query().by_operation("edm").count() >= 4

    def test_no_match_returns_empty(self, lib):
        assert lib.query().by_operation("thermalspray").count() == 0

    def test_tapping_returns_taps(self, lib):
        r = lib.query().by_operation("tapping").results()
        assert len(r) >= 4
        assert all("tapping" in rec.supported_operations for rec in r)


class TestFilterByManufacturer:
    def test_exact_case_insensitive(self, lib):
        r1 = lib.query().by_manufacturer("Sandvik Coromant").count()
        r2 = lib.query().by_manufacturer("sandvik coromant").count()
        assert r1 == r2 > 0

    def test_bedra(self, lib):
        r = lib.query().by_manufacturer("Bedra (Berkenhoff)").results()
        assert len(r) == 2

    def test_unknown_returns_empty(self, lib):
        assert lib.query().by_manufacturer("FakeMfr99").count() == 0


class TestFilterByMaterialGroups:
    def test_any_h_group(self, lib):
        r = lib.query().by_material_groups(["H"]).results()
        assert all("H" in rec.iso_material_groups for rec in r)
        assert len(r) >= 2

    def test_any_semantics_union(self, lib):
        both = lib.query().by_material_groups(["N", "S"]).count()
        only_n = lib.query().by_material_groups(["N"]).count()
        only_s = lib.query().by_material_groups(["S"]).count()
        assert both >= only_n
        assert both >= only_s

    def test_all_semantics_intersection(self, lib):
        all_pm = lib.query().by_material_groups_all(["P", "M"]).count()
        any_p = lib.query().by_material_groups(["P"]).count()
        assert all_pm <= any_p

    def test_all_six_groups_returns_edm_wire_only(self, lib):
        r = lib.query().by_material_groups_all(["P", "M", "K", "N", "S", "H"]).results()
        assert len(r) == 2
        assert all(rec.tool_category_code == "EDM_WIRE" for rec in r)


class TestFilterByDiameter:
    def test_8mm_exact(self, lib):
        r = lib.query().by_diameter(min_mm=8.0, max_mm=8.0).results()
        assert all(rec.cutting_diameter_mm == 8.0 for rec in r)
        assert len(r) >= 3

    def test_no_bounds_returns_all(self, lib):
        assert lib.query().by_diameter().count() == 47

    def test_excludes_records_without_diameter(self, lib):
        ids = {rec.stable_id for rec in lib.query().by_diameter(min_mm=1.0).results()}
        assert "sandvik-a25t-sducr-11" not in ids  # boring bar has no cutting_diameter_mm

    def test_edm_wire_0_25mm(self, lib):
        r = lib.query().by_diameter(min_mm=0.1, max_mm=0.3).results()
        assert len(r) == 2
        assert all(rec.tool_category_code == "EDM_WIRE" for rec in r)

    def test_max_bound_only(self, lib):
        r = lib.query().by_diameter(max_mm=6.0).results()
        for rec in r:
            assert rec.cutting_diameter_mm <= 6.0


class TestFilterByShankDiameter:
    def test_12mm_exact(self, lib):
        r = lib.query().by_shank_diameter(min_mm=12.0, max_mm=12.0).results()
        assert all(rec.shank_diameter_mm == 12.0 for rec in r)

    def test_excludes_records_without_shank_diameter(self, lib):
        r = lib.query().by_shank_diameter(min_mm=1.0).results()
        assert all(rec.shank_diameter_mm is not None for rec in r)


class TestFilterByOverallLength:
    def test_range_inclusive(self, lib):
        r = lib.query().by_overall_length(min_mm=50.0, max_mm=100.0).results()
        for rec in r:
            assert 50.0 <= rec.overall_length_mm <= 100.0

    def test_excludes_none_overall_length(self, lib):
        r = lib.query().by_overall_length(min_mm=1.0).results()
        assert all(rec.overall_length_mm is not None for rec in r)

    def test_no_bounds_returns_all(self, lib):
        assert lib.query().by_overall_length().count() == 47


class TestFilterByCuttingLength:
    def test_min_bound(self, lib):
        r = lib.query().by_cutting_length(min_mm=10.0).results()
        assert all(rec.cutting_length_mm >= 10.0 for rec in r)

    def test_excludes_none_cutting_length(self, lib):
        r = lib.query().by_cutting_length(min_mm=1.0).results()
        assert all(rec.cutting_length_mm is not None for rec in r)


class TestFilterByFluteCount:
    def test_exactly_four_flutes(self, lib):
        r = lib.query().by_flute_count(min_flutes=4, max_flutes=4).results()
        assert all(rec.number_of_flutes == 4 for rec in r)
        assert len(r) >= 3

    def test_excludes_none_flute_count(self, lib):
        r = lib.query().by_flute_count(min_flutes=1).results()
        assert all(rec.number_of_flutes is not None for rec in r)

    def test_six_flute_reamer(self, lib):
        r = lib.query().by_flute_count(min_flutes=6, max_flutes=6).results()
        assert any(rec.tool_category_code == "REAMER" for rec in r)


class TestFilterBySubstrateCode:
    def test_cbn_returns_one_record(self, lib):
        r = lib.query().by_substrate_code("CBN").results()
        assert len(r) == 1
        assert r[0].stable_id == "norton-bn200-cbn-wheel-150x10"

    def test_case_insensitive(self, lib):
        assert (
            lib.query().by_substrate_code("carbide").count()
            == lib.query().by_substrate_code("CARBIDE").count()
        )

    def test_unknown_returns_empty(self, lib):
        assert lib.query().by_substrate_code("UNOBTAINIUM").count() == 0

    def test_graphite_returns_poco_electrode(self, lib):
        r = lib.query().by_substrate_code("GRAPHITE").results()
        assert len(r) == 1
        assert r[0].stable_id == "poco-edm-200-graphite-electrode"


class TestFilterByCoatingType:
    def test_cvd_count(self, lib):
        r = lib.query().by_coating_type("CVD").results()
        assert len(r) == 7
        assert all(rec.coating_type == "CVD" for rec in r)

    def test_pvd_non_empty(self, lib):
        r = lib.query().by_coating_type("PVD").results()
        assert len(r) > 0
        assert all(rec.coating_type == "PVD" for rec in r)

    def test_case_insensitive(self, lib):
        assert (
            lib.query().by_coating_type("cvd").count()
            == lib.query().by_coating_type("CVD").count()
        )

    def test_unknown_returns_empty(self, lib):
        assert lib.query().by_coating_type("ALD").count() == 0


class TestFilterByThroughCoolant:
    def test_true_count(self, lib):
        r = lib.query().by_through_coolant(True).results()
        assert len(r) == 9
        assert all(rec.through_coolant is True for rec in r)

    def test_false_excludes_none(self, lib):
        """through_coolant=False must NOT include records where it is None."""
        r = lib.query().by_through_coolant(False).results()
        assert len(r) == 4
        assert all(rec.through_coolant is False for rec in r)

    def test_none_records_excluded_from_both_sides(self, lib):
        """True + False + None counts must equal total."""
        tc_true = lib.query().by_through_coolant(True).count()
        tc_false = lib.query().by_through_coolant(False).count()
        none_count = sum(1 for r in lib.all() if r.through_coolant is None)
        assert tc_true + tc_false + none_count == 47

    def test_taps_are_explicitly_false(self, lib):
        """OSG taps have through_coolant=False."""
        taps = lib.query().by_family(ToolFamily.THREADING).by_category_code("TAP").results()
        assert all(r.through_coolant is False for r in taps)


class TestFilterByCategoryCode:
    def test_grooving_insert(self, lib):
        assert lib.query().by_category_code("GROOVING_INSERT").count() == 4

    def test_edm_wire(self, lib):
        assert lib.query().by_category_code("EDM_WIRE").count() == 2

    def test_edm_electrode(self, lib):
        assert lib.query().by_category_code("EDM_ELECTRODE").count() == 2

    def test_nonexistent_returns_empty(self, lib):
        assert lib.query().by_category_code("LATHE_INSERT").count() == 0


class TestFilterByShankInterface:
    def test_din6535_match(self, lib):
        r = lib.query().by_shank_interface("DIN 6535").count()
        assert r >= 10

    def test_case_insensitive(self, lib):
        r1 = lib.query().by_shank_interface("din 6535").count()
        r2 = lib.query().by_shank_interface("DIN 6535").count()
        assert r1 == r2

    def test_spool_matches_edm_wire(self, lib):
        r = lib.query().by_shank_interface("spool").results()
        assert len(r) == 2
        assert all(rec.tool_category_code == "EDM_WIRE" for rec in r)


class TestFilterByEvidenceStatus:
    def test_manufacturer_catalog_count(self, lib):
        r = lib.query().by_evidence_status("MANUFACTURER_CATALOG").results()
        assert len(r) == 44

    def test_unverified_count(self, lib):
        r = lib.query().by_evidence_status("UNVERIFIED").results()
        assert len(r) == 3

    def test_manufacturer_catalog_plus_unverified_equals_total(self, lib):
        mc = lib.query().by_evidence_status("MANUFACTURER_CATALOG").count()
        uv = lib.query().by_evidence_status("UNVERIFIED").count()
        assert mc + uv == 47

    def test_nonexistent_status_returns_empty(self, lib):
        assert lib.query().by_evidence_status("DRAFT").count() == 0


# ── Chain immutability and edge cases ─────────────────────────────────────────


class TestQueryChain:
    def test_base_query_unaffected_by_branch(self, lib):
        base = lib.query().by_family(ToolFamily.MILLING)
        base_count = base.count()
        _ = base.by_manufacturer("Sandvik Coromant")
        assert base.count() == base_count

    def test_branching_subsets_sum_at_most_base(self, lib):
        base = lib.query().by_family(ToolFamily.DRILLING)
        sandvik = base.by_manufacturer("Sandvik Coromant")
        kennametal = base.by_manufacturer("Kennametal")
        assert sandvik.count() + kennametal.count() <= base.count()

    def test_empty_chain_first_returns_none(self, lib):
        r = lib.query().by_family(ToolFamily.DRILLING).by_substrate_code("CBN").first()
        assert r is None

    def test_non_empty_chain_first_returns_record(self, lib):
        r = lib.query().by_family(ToolFamily.EDM).first()
        assert r is not None

    def test_count_matches_results_length(self, lib):
        q = lib.query().by_family(ToolFamily.THREADING)
        assert q.count() == len(q.results())

    def test_results_returns_list_copy(self, lib):
        r1 = lib.query().results()
        r2 = lib.query().results()
        assert r1 is not r2
        assert len(r1) == len(r2)

    def test_multi_filter_chain(self, lib):
        r = (
            lib.query()
            .by_family(ToolFamily.DRILLING)
            .by_manufacturer("Sandvik Coromant")
            .by_material_groups(["P", "M"])
            .by_through_coolant(True)
            .results()
        )
        assert len(r) >= 1
        for rec in r:
            assert rec.tool_category_code == "DRILL"
            assert rec.manufacturer == "Sandvik Coromant"
            assert rec.through_coolant is True


# ── GRINDING and EDM record verification ─────────────────────────────────────


class TestGrindingAndEDMRecords:
    def test_norton_32a_aluminum_oxide(self, lib):
        r = lib.find_by_id("norton-32a60-h8vbe-200x25")
        assert r is not None
        assert r.manufacturer == "Norton Abrasives"
        assert r.tool_category_code == "GRINDING_WHEEL"
        assert r.cutting_diameter_mm == 200.0
        assert r.substrate_material_code == "ABRASIVE_OXIDE"
        assert "grinding" in r.supported_operations
        assert "P" in r.iso_material_groups

    def test_norton_bn200_cbn_wheel(self, lib):
        r = lib.find_by_id("norton-bn200-cbn-wheel-150x10")
        assert r is not None
        assert r.tool_material == "CBN"
        assert r.substrate_material_code == "CBN"
        assert r.cutting_diameter_mm == 150.0
        assert "H" in r.iso_material_groups

    def test_3m_cubitron2_disc(self, lib):
        r = lib.find_by_id("3m-cubitron2-984f-t27-115x22")
        assert r is not None
        assert r.manufacturer == "3M"
        assert r.cutting_diameter_mm == 115.0

    def test_bedra_cobra_cut_a(self, lib):
        r = lib.find_by_id("bedra-cobra-cut-a-0.25mm")
        assert r is not None
        assert r.manufacturer == "Bedra (Berkenhoff)"
        assert r.cutting_diameter_mm == 0.25
        assert r.tool_material == "brass"
        assert "edm wire cutting" in r.supported_operations
        assert "edm" in r.supported_operations

    def test_bedra_broncocut_xh(self, lib):
        r = lib.find_by_id("bedra-broncocut-xh-0.25mm")
        assert r is not None
        assert r.tool_category_code == "EDM_WIRE"

    def test_poco_edm_200_graphite(self, lib):
        r = lib.find_by_id("poco-edm-200-graphite-electrode")
        assert r is not None
        assert r.tool_material == "graphite"
        assert r.substrate_material_code == "GRAPHITE"
        assert "edm sinker" in r.supported_operations

    def test_poco_ck10_copper(self, lib):
        r = lib.find_by_id("poco-ck10-copper-electrode")
        assert r is not None
        assert r.tool_material == "copper"
        assert r.substrate_material_code == "COPPER"

    def test_edm_no_fabricated_cutting_guidance(self, lib):
        for r in lib.by_family(ToolFamily.EDM):
            assert r.vc_min_mpm is None
            assert r.vc_max_mpm is None
            assert r.fz_min_mm is None

    def test_grinding_no_fabricated_cutting_guidance(self, lib):
        for r in lib.by_family(ToolFamily.GRINDING):
            assert r.vc_min_mpm is None
            assert r.vc_max_mpm is None


# ── Provenance and evidence_status ────────────────────────────────────────────


UNVERIFIED_IDS = frozenset({
    "kennametal-4cfl-12mm-solid-carbide",
    "kennametal-ecs-d12-4fl",
    "iscar-ecf-d10-4fl",
})


class TestProvenanceAndEvidence:
    def test_three_records_are_unverified(self, lib):
        for sid in UNVERIFIED_IDS:
            r = lib.find_by_id(sid)
            assert r is not None, f"{sid} not found in catalog"
            assert r.evidence_status == "UNVERIFIED", (
                f"{sid}: evidence_status={r.evidence_status!r}; expected 'UNVERIFIED'"
            )

    def test_unverified_records_have_no_catalog_code(self, lib):
        for sid in UNVERIFIED_IDS:
            r = lib.find_by_id(sid)
            assert r.catalog_code is None, f"{sid} unexpectedly has catalog_code={r.catalog_code!r}"

    def test_all_manufacturer_catalog_records_have_catalog_code(self, lib):
        """After remediation: no MANUFACTURER_CATALOG record may lack a catalog_code."""
        no_code = [
            r.stable_id for r in lib.all()
            if r.evidence_status == "MANUFACTURER_CATALOG" and r.catalog_code is None
        ]
        assert no_code == [], f"MANUFACTURER_CATALOG records missing catalog_code: {no_code}"

    def test_verified_only_query_excludes_unverified(self, lib):
        verified_ids = {
            r.stable_id
            for r in lib.query().by_evidence_status("MANUFACTURER_CATALOG").results()
        }
        for sid in UNVERIFIED_IDS:
            assert sid not in verified_ids, f"{sid} appeared in verified-only query"

    def test_unverified_only_query_returns_exactly_three(self, lib):
        unverified = lib.query().by_evidence_status("UNVERIFIED").results()
        assert len(unverified) == 3
        assert {r.stable_id for r in unverified} == UNVERIFIED_IDS

    def test_all_records_have_evidence_status(self, lib):
        for r in lib.all():
            assert r.evidence_status, f"{r.stable_id} has empty evidence_status"

    def test_no_private_paths_in_any_source_note(self, lib):
        forbidden = ["C:\\Users\\", "D:\\Users\\", "/home/", "C:/Users/"]
        for r in lib.all():
            note = r.source_note or ""
            for path in forbidden:
                assert path not in note, f"Private path {path!r} in {r.stable_id}.source_note"

    def test_no_fabricated_vc_fz_on_any_record(self, lib):
        """Cutting guidance must be None, never zero (MISSING_VALUE_AS_ZERO=NO)."""
        for r in lib.all():
            for field in ("vc_min_mpm", "vc_max_mpm", "fz_min_mm", "fz_max_mm"):
                assert getattr(r, field) != 0, (
                    f"{r.stable_id}.{field}=0 — MISSING_VALUE_AS_ZERO violation"
                )

    def test_no_ai_recommendation_claims(self, lib):
        forbidden_terms = ["ai recommended", "best tool", "optimal tool", "guaranteed"]
        for r in lib.all():
            combined = (r.product_name + " " + (r.source_note or "")).lower()
            for term in forbidden_terms:
                assert term not in combined, f"False claim {term!r} in {r.stable_id}"

    def test_iso_groups_all_valid(self, lib):
        valid = {"P", "M", "K", "N", "S", "H"}
        for r in lib.all():
            assert r.iso_material_groups, f"{r.stable_id} has empty iso_material_groups"
            invalid = set(r.iso_material_groups) - valid
            assert not invalid, f"{r.stable_id} has invalid ISO groups: {invalid}"
