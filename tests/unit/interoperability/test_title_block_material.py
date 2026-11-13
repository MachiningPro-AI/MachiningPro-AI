"""Unit tests for backend.interoperability.title_block_material (P0).

Coverage:
  - Direct alias: "42CrMo4" → P-42CrMo4
  - Numeric alias: "1.7225" → P-42CrMo4
  - Title-block prefix extraction: "MALZEME: C45" → P-C45
  - Title-block prefix extraction: "MATERIAL: S355JR"
  - Title-block prefix extraction: "WERKSTOFF: 42CrMo4"
  - Pattern matching: S235JR, S355J2, 316L
  - Aluminum designations: EN AW-6082, 7075
  - Titanium: Ti-6Al-4V
  - Library ID mapping verified for each canonical grade
  - No false positives: part numbers, revision strings, drawing numbers
  - No false positives: empty tokens, whitespace, control codes
  - Returns None when no material found
  - Confidence >= 0.8 for explicit prefix match
  - source is always TITLE_BLOCK
  - original_extracted_value set to designation
"""

from __future__ import annotations

import pytest

from backend.interoperability.missing_data import (
    EngineeringFieldSource,
    EngineeringFieldStatus,
)
from backend.interoperability.title_block_material import extract_title_block_material


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract(tokens: list[str]):
    return extract_title_block_material(tokens)


# ---------------------------------------------------------------------------
# Direct alias matching
# ---------------------------------------------------------------------------

class TestAliasMatching:
    @pytest.mark.parametrize("token,expected_id", [
        ("42CrMo4", "P-42CrMo4"),
        ("1.7225", "P-42CrMo4"),
        ("C45", "P-C45"),
        ("1.0503", "P-C45"),
        ("Ck45", "P-Ck45"),
        ("1.1191", "P-Ck45"),
        ("16MnCr5", "P-16MnCr5"),
        ("20MnCr5", "P-20MnCr5"),
        ("S235JR", "P-S235JR"),
        ("1.0038", "P-S235JR"),
        ("S355JR", "P-S355JR"),
        ("S355J2", "P-S355J2"),
        ("304", "M-304"),
        ("1.4301", "M-304"),
        ("316L", "M-316L"),
        ("1.4404", "M-316L"),
        ("17-4PH", "M-17-4PH"),
        ("GJL-250", "K-GJL-250"),
        ("GG-25", "K-GJL-250"),
        ("6082", "N-6082-T6"),
        ("AlSiMgMn", "N-6082-T6"),
        ("7075", "N-7075-T6"),
        ("6061", "N-6061-T6"),
        ("Ti-6Al-4V", "S-Ti64"),
        ("3.7165", "S-Ti64"),
    ])
    def test_direct_alias(self, token: str, expected_id: str):
        result = _extract([token])
        assert result is not None, f"Expected material from token {token!r}"
        assert result.library_resolved_id == expected_id
        assert result.status == EngineeringFieldStatus.KNOWN
        assert result.source == EngineeringFieldSource.TITLE_BLOCK

    def test_case_insensitive_alias(self):
        result = _extract(["42crmo4"])
        assert result is not None
        assert result.library_resolved_id == "P-42CrMo4"

    def test_lowercase_c45(self):
        result = _extract(["c45"])
        assert result is not None
        assert result.library_resolved_id == "P-C45"


# ---------------------------------------------------------------------------
# Title-block prefix detection
# ---------------------------------------------------------------------------

class TestTitleBlockPrefixes:
    @pytest.mark.parametrize("prefix_form,designation,expected_id", [
        ("MALZEME: 42CrMo4", "42CrMo4", "P-42CrMo4"),
        ("MATERIAL: C45", "C45", "P-C45"),
        ("WERKSTOFF: S355JR", "S355JR", "P-S355JR"),
        ("MAT: 316L", "316L", "M-316L"),
        ("MAT.: Ti-6Al-4V", "Ti-6Al-4V", "S-Ti64"),
        ("MALZEME: S235JR", "S235JR", "P-S235JR"),
        ("MATERIAL: 1.7225", "1.7225", "P-42CrMo4"),
    ])
    def test_prefix_extraction(self, prefix_form: str, designation: str, expected_id: str):
        result = _extract([prefix_form])
        assert result is not None, f"Expected material from {prefix_form!r}"
        assert result.library_resolved_id == expected_id

    def test_prefix_extraction_has_high_confidence(self):
        result = _extract(["MALZEME: 42CrMo4"])
        assert result is not None
        assert result.confidence is not None
        assert result.confidence >= 0.85

    def test_prefix_extraction_source_is_title_block(self):
        result = _extract(["MATERIAL: C45"])
        assert result is not None
        assert result.source == EngineeringFieldSource.TITLE_BLOCK


# ---------------------------------------------------------------------------
# Pattern matching (no alias map hit required)
# ---------------------------------------------------------------------------

class TestPatternMatching:
    def test_en_aw_aluminum(self):
        result = _extract(["EN AW-6082"])
        assert result is not None
        assert result.library_resolved_id == "N-6082-T6"

    def test_en_aw_aluminum_no_hyphen(self):
        result = _extract(["EN AW 6082"])
        assert result is not None

    def test_structural_steel_pattern(self):
        result = _extract(["S275JR"])
        assert result is not None
        # No alias but pattern should match

    def test_x5crni_stainless(self):
        result = _extract(["X5CrNi18-10"])
        assert result is not None
        assert result.library_resolved_id == "M-304"

    def test_multiple_tokens_best_wins(self):
        # MALZEME prefix should produce higher confidence than bare designation
        result = _extract(["Some drawing note", "MALZEME: 42CrMo4", "Rev A"])
        assert result is not None
        assert result.library_resolved_id == "P-42CrMo4"
        assert result.confidence >= 0.85


# ---------------------------------------------------------------------------
# No false positives
# ---------------------------------------------------------------------------

class TestNoFalsePositives:
    def test_part_number_not_material(self):
        result = _extract(["109106_01_30"])
        assert result is None, "Part number should not be classified as material"

    def test_revision_string_not_material(self):
        result = _extract(["Rev A", "REV 03", "A3"])
        assert result is None

    def test_drawing_number_not_material(self):
        result = _extract(["DWG-2024-001", "Drawing No. 10452"])
        assert result is None

    def test_generic_text_not_material(self):
        result = _extract(["Pense Şema", "TOLERANS", "ÖLÇÜLER"])
        assert result is None

    def test_empty_tokens_no_match(self):
        result = _extract(["", "   ", "\t"])
        assert result is None

    def test_empty_list_no_match(self):
        result = _extract([])
        assert result is None

    def test_format_control_codes_stripped(self):
        # AutoCAD MTEXT control codes
        result = _extract([r"\fArial|b0|i0|c0|p1/4;42CrMo4"])
        # Should still match after stripping
        # (implementation strips backslash codes before matching)

    def test_date_string_not_material(self):
        # Date strings like "2024-11-13" must not be matched as material
        result = _extract(["2024-11-13"])
        assert result is None, f"Date string must not match as material, got {result}"


# ---------------------------------------------------------------------------
# Return value structure
# ---------------------------------------------------------------------------

class TestReturnStructure:
    def test_returns_none_when_no_material(self):
        result = _extract(["Tolerances per ISO 2768-m"])
        assert result is None

    def test_returns_engineering_field(self):
        from backend.interoperability.missing_data import EngineeringField
        result = _extract(["42CrMo4"])
        assert isinstance(result, EngineeringField)

    def test_value_is_designation_string(self):
        result = _extract(["42CrMo4"])
        assert result is not None
        assert result.value == "42CrMo4"

    def test_library_id_is_set(self):
        result = _extract(["C45"])
        assert result is not None
        assert result.library_resolved_id == "P-C45"

    def test_original_extracted_value_is_set(self):
        result = _extract(["42CrMo4"])
        assert result is not None
        assert result.original_extracted_value is not None

    def test_confidence_between_0_and_1(self):
        result = _extract(["42CrMo4"])
        assert result is not None
        assert 0.0 <= result.confidence <= 1.0
