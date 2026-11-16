"""Tests for P5-A: tool catalog expansion and tool selection (MUST 40, 7, 8)."""
from backend.cutting_tools.seed_catalog import get_catalog
from backend.manufacturing.tool_selection import ToolMatchStatus, select_tools

# ---------------------------------------------------------------------------
# P5-A: Catalog coverage after expansion
# ---------------------------------------------------------------------------

class TestP5AToolCatalogExpansion:
    def test_drill_count_after_expansion(self):
        drills = [t for t in get_catalog() if t.tool_category_code == "DRILL"]
        assert len(drills) >= 15, f"Expected >= 15 drills after P5-A expansion, got {len(drills)}"

    def test_min_drill_diameter_is_3mm(self):
        drills = [t for t in get_catalog() if t.tool_category_code == "DRILL"]
        diams = [t.cutting_diameter_mm for t in drills if t.cutting_diameter_mm]
        assert min(diams) == 3.0

    def test_5mm_drill_exists(self):
        drills = [
            t for t in get_catalog()
            if t.tool_category_code == "DRILL" and t.cutting_diameter_mm == 5.0
        ]
        assert len(drills) >= 1

    def test_6mm_drill_exists(self):
        drills = [
            t for t in get_catalog()
            if t.tool_category_code == "DRILL" and t.cutting_diameter_mm == 6.0
        ]
        assert len(drills) >= 1

    def test_all_new_drills_have_source_note(self):
        new_drills = [
            t for t in get_catalog()
            if t.tool_category_code == "DRILL" and t.cutting_diameter_mm in {3.0, 4.0, 5.0, 6.0}
        ]
        for d in new_drills:
            assert d.source_note, f"{d.stable_id} missing source_note"

    def test_no_fabricated_diameters_added(self):
        drills = [t for t in get_catalog() if t.tool_category_code == "DRILL"]
        # P5-baseline: 3/4/5/6/8/12 mm Sandvik 860-1 + other drills.
        # P7-D addition: 16/18/24 mm Sandvik CoroDrill 860-1 — manufacturer-sourced
        #   from coromant.sandvik.com CoroDrill 860-1 standard range (GC4234 PVD TiAlN).
        #   Not fabricated; source_note cites coromant.sandvik.com in each record.
        standard_sizes = {3.0, 4.0, 5.0, 6.0, 8.0, 12.0, 16.0, 18.0, 24.0}
        for d in drills:
            diam = d.cutting_diameter_mm
            assert diam in standard_sizes, (
                f"{d.stable_id}: {diam} mm is not a standard catalogued size"
            )


# ---------------------------------------------------------------------------
# P5-A: Tool matching (MUST 7, 8)
# ---------------------------------------------------------------------------

class TestP5AToolMatching:
    def test_exact_match_5mm(self):
        result = select_tools(feature_diameter_mm=5.0, operation="drilling")
        assert result.tool_selection_ready
        best = result.best_match
        assert best is not None
        assert best.match_status == ToolMatchStatus.EXACT
        assert best.tool.cutting_diameter_mm == 5.0

    def test_exact_match_6mm(self):
        result = select_tools(feature_diameter_mm=6.0, operation="drilling")
        assert result.tool_selection_ready
        assert result.best_match.match_status == ToolMatchStatus.EXACT

    def test_exact_match_8mm(self):
        result = select_tools(feature_diameter_mm=8.0, operation="drilling")
        assert result.tool_selection_ready
        assert result.best_match.match_status == ToolMatchStatus.EXACT

    def test_compatible_match_4891mm(self):
        """4.891 mm: not standard; closest is 5.0 mm (COMPATIBLE, +0.109 mm oversize)."""
        result = select_tools(feature_diameter_mm=4.891, operation="drilling")
        assert result.tool_selection_ready
        best = result.best_match
        assert best.match_status == ToolMatchStatus.COMPATIBLE
        assert best.tool.cutting_diameter_mm == 5.0
        assert abs(best.diameter_delta_mm - 0.109) < 0.001

    def test_no_match_too_large(self):
        """60 mm feature -- no drill in catalog."""
        result = select_tools(feature_diameter_mm=60.0, operation="drilling")
        assert not result.tool_selection_ready
        assert result.best_match is None

    def test_no_match_too_small(self):
        """1.5 mm -- below minimum drill in catalog."""
        result = select_tools(feature_diameter_mm=1.5, operation="drilling")
        assert not result.tool_selection_ready

    def test_no_match_incompatible_material(self):
        """Filter on ISO H (hardened steel) -- no drills in catalog for H."""
        result = select_tools(
            feature_diameter_mm=5.0,
            operation="drilling",
            iso_material_groups=["H"],
        )
        assert not result.tool_selection_ready

    def test_cutting_length_filter(self):
        """Require cutting length 1000 mm -- no drill qualifies."""
        result = select_tools(
            feature_diameter_mm=5.0,
            operation="drilling",
            required_cutting_length_mm=1000.0,
        )
        # Only tools with cutting_length_mm >= 1000 or cutting_length_mm=None pass
        # The 5mm drill has cutting_length_mm=26 → should not pass the length check
        for c in result.candidates:
            if c.tool.cutting_length_mm and c.tool.cutting_length_mm < 1000.0:
                assert c.match_status == ToolMatchStatus.NO_MATCH

    def test_match_returns_exact_before_compatible(self):
        """EXACT match must rank before COMPATIBLE."""
        result = select_tools(feature_diameter_mm=5.0, operation="drilling")
        assert result.best_match.match_status == ToolMatchStatus.EXACT


# ---------------------------------------------------------------------------
# P5-C: Cutting data availability for matched tools
# ---------------------------------------------------------------------------

class TestP5AToolCuttingData:
    def test_cutting_data_ready_for_dxf01_5mm_c45(self):
        result = select_tools(feature_diameter_mm=5.0, operation="drilling", material_grade="C45")
        assert result.cutting_data_ready

    def test_cutting_data_ready_for_6mm_c45(self):
        result = select_tools(feature_diameter_mm=6.0, operation="drilling", material_grade="C45")
        assert result.cutting_data_ready

    def test_cutting_data_not_ready_no_material(self):
        result = select_tools(feature_diameter_mm=5.0, operation="drilling", material_grade=None)
        assert not result.cutting_data_ready
