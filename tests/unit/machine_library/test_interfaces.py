"""Tests for backend.machine_library.interfaces.

Covers:
- Interface normalization: known families, case/spacing variants
- Unknown and unrecognised string handling
- None / blank input handling
- Multiple interface representations for same machine
- Tool-holder compatibility: PASS / FAIL / UNKNOWN
- NO_SPINDLE machines
- UNVERIFIED status preservation
- Contradiction: same family, different size
"""

from __future__ import annotations

import pytest

from backend.machine_library.interfaces import (
    CompatibilityVerdict,
    InterfaceFamily,
    InterfaceVerificationStatus,
    NormalizedMachineInterface,
    check_interface_compatibility,
    normalize_interface_string,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _norm(raw: str | None, **kw) -> NormalizedMachineInterface:
    return normalize_interface_string(raw, **kw)


# ===========================================================================
# TestNormalizationKnownFamilies
# ===========================================================================


class TestNormalizationKnownFamilies:
    # CAT
    def test_cat40_canonical(self):
        r = _norm("CAT-40")
        assert r.family is InterfaceFamily.CAT
        assert r.designation == "CAT-40"

    def test_cat40_no_hyphen(self):
        r = _norm("CAT40")
        assert r.family is InterfaceFamily.CAT
        assert r.designation == "CAT-40"

    def test_cat50(self):
        r = _norm("CAT-50")
        assert r.family is InterfaceFamily.CAT
        assert r.designation == "CAT-50"

    def test_cat30(self):
        r = _norm("cat-30")
        assert r.family is InterfaceFamily.CAT
        assert r.designation == "CAT-30"

    # BT
    def test_bt30(self):
        r = _norm("BT-30")
        assert r.family is InterfaceFamily.BT
        assert r.designation == "BT-30"

    def test_bt40(self):
        r = _norm("bt40")
        assert r.family is InterfaceFamily.BT
        assert r.designation == "BT-40"

    def test_bt50(self):
        r = _norm("BT-50")
        assert r.family is InterfaceFamily.BT
        assert r.designation == "BT-50"

    # HSK
    def test_hsk_a63(self):
        r = _norm("HSK-A63")
        assert r.family is InterfaceFamily.HSK
        assert r.designation == "HSK-A63"

    def test_hsk_a63_compact(self):
        r = _norm("HSKA63")
        assert r.family is InterfaceFamily.HSK
        assert r.designation == "HSK-A63"

    def test_hsk_e40(self):
        r = _norm("HSK-E40")
        assert r.family is InterfaceFamily.HSK
        assert r.designation == "HSK-E40"

    def test_hsk_a100(self):
        r = _norm("HSK-A100")
        assert r.family is InterfaceFamily.HSK
        assert r.designation == "HSK-A100"

    # SK (DIN 69871)
    def test_sk40(self):
        r = _norm("SK40")
        assert r.family is InterfaceFamily.SK
        assert r.designation == "SK-40"

    def test_sk40_hyphen(self):
        r = _norm("SK-40")
        assert r.family is InterfaceFamily.SK
        assert r.designation == "SK-40"

    def test_iso40_maps_to_sk(self):
        r = _norm("ISO-40")
        assert r.family is InterfaceFamily.SK
        assert r.designation == "SK-40"

    def test_iso40_no_hyphen(self):
        r = _norm("ISO40")
        assert r.family is InterfaceFamily.SK
        assert r.designation == "SK-40"

    # Capto
    def test_capto_c6(self):
        r = _norm("C6")
        assert r.family is InterfaceFamily.CAPTO
        assert r.designation == "C6"

    def test_capto_c8_prefix(self):
        r = _norm("Capto C8")
        assert r.family is InterfaceFamily.CAPTO
        assert r.designation == "C8"

    # Lathe chuck / collet
    def test_lathe_chuck(self):
        r = _norm("lathe-chuck")
        assert r.family is InterfaceFamily.LATHE_CHUCK
        assert r.designation == "LATHE_CHUCK"

    def test_chuck_bare(self):
        r = _norm("Chuck")
        assert r.family is InterfaceFamily.LATHE_CHUCK

    def test_collet(self):
        r = _norm("collet")
        assert r.family is InterfaceFamily.COLLET
        assert r.designation == "COLLET"

    def test_er32_collet(self):
        r = _norm("ER32")
        assert r.family is InterfaceFamily.COLLET

    # VDI
    def test_vdi_40(self):
        r = _norm("VDI40")
        assert r.family is InterfaceFamily.VDI

    # NO_SPINDLE
    def test_no_spindle_string(self):
        r = _norm("no_spindle")
        assert r.family is InterfaceFamily.NO_SPINDLE
        assert r.designation == "NO_SPINDLE"

    def test_edm_no_spindle(self):
        r = _norm("EDM")
        assert r.family is InterfaceFamily.NO_SPINDLE

    def test_wire_edm_no_spindle(self):
        r = _norm("wire-edm")
        assert r.family is InterfaceFamily.NO_SPINDLE


# ===========================================================================
# TestNormalizationUnknownHandling
# ===========================================================================


class TestNormalizationUnknownHandling:
    def test_none_input_returns_unknown(self):
        r = _norm(None)
        assert r.family is InterfaceFamily.UNKNOWN
        assert r.verification_status is InterfaceVerificationStatus.UNKNOWN
        assert r.designation == "UNKNOWN"

    def test_empty_string_returns_unknown(self):
        r = _norm("")
        assert r.family is InterfaceFamily.UNKNOWN
        assert r.verification_status is InterfaceVerificationStatus.UNKNOWN

    def test_whitespace_only_returns_unknown(self):
        r = _norm("   ")
        assert r.family is InterfaceFamily.UNKNOWN

    def test_unrecognised_string_preserves_unverified(self):
        r = _norm("MYSTERY-99")
        assert r.family is InterfaceFamily.UNKNOWN
        assert r.verification_status is InterfaceVerificationStatus.UNVERIFIED
        assert r.designation == "MYSTERY-99"

    def test_unrecognised_raw_input_preserved(self):
        raw = "CustomTaper-XYZ"
        r = _norm(raw)
        assert r.raw_input == raw
        assert r.designation == raw

    def test_unknown_is_not_known(self):
        r = _norm(None)
        assert not r.is_known

    def test_known_interface_is_known(self):
        r = _norm("CAT-40")
        assert r.is_known

    def test_no_spindle_is_not_known(self):
        r = _norm("no_spindle")
        assert not r.is_known

    def test_unverified_status_means_not_verified(self):
        r = _norm("MYSTERY-99")
        assert not r.is_verified

    def test_manufacturer_confirmed_is_verified(self):
        r = _norm("CAT-40", verification_status=InterfaceVerificationStatus.MANUFACTURER_CONFIRMED)
        assert r.is_verified


# ===========================================================================
# TestNormalizationSourceNote
# ===========================================================================


class TestNormalizationSourceNote:
    def test_source_note_passed_through(self):
        r = _norm("CAT-40", source_note="Haas datasheet 2023")
        assert r.source_note == "Haas datasheet 2023"

    def test_source_note_on_unknown(self):
        r = _norm(None, source_note="no data")
        assert r.source_note == "no data"

    def test_default_source_note_empty(self):
        r = _norm("BT-30")
        assert r.source_note == ""


# ===========================================================================
# TestNormalizationSeedCatalogInterfaces
# ===========================================================================


class TestNormalizationSeedCatalogInterfaces:
    """Verify all interface strings present in seed catalog normalise correctly."""

    @pytest.mark.parametrize("raw,expected_family,expected_designation", [
        ("CAT-40",  InterfaceFamily.CAT, "CAT-40"),
        ("HSK-A63", InterfaceFamily.HSK, "HSK-A63"),
        ("BT-30",   InterfaceFamily.BT,  "BT-30"),
        ("SK40",    InterfaceFamily.SK,  "SK-40"),
    ])
    def test_seed_interface_strings(self, raw, expected_family, expected_designation):
        r = _norm(raw)
        assert r.family is expected_family
        assert r.designation == expected_designation

    def test_none_interfaces_from_lathes_grinders_edm(self):
        # 14 seed records have None interface — must return UNKNOWN
        r = _norm(None)
        assert r.family is InterfaceFamily.UNKNOWN

    def test_sk40_normalises_to_sk_family(self):
        # DMG MORI CMX 600 V uses "SK40" in seed
        r = _norm("SK40")
        assert r.family is InterfaceFamily.SK
        assert r.designation == "SK-40"


# ===========================================================================
# TestCheckInterfaceCompatibility
# ===========================================================================


class TestCheckInterfaceCompatibility:
    def _make(self, raw: str | None, **kw) -> NormalizedMachineInterface:
        return normalize_interface_string(raw, **kw)

    # PASS cases
    def test_cat40_vs_cat40_pass(self):
        mi = self._make("CAT-40")
        ti = self._make("CAT-40")
        result = check_interface_compatibility(mi, ti)
        assert result.verdict is CompatibilityVerdict.PASS

    def test_hsk_a63_vs_hsk_a63_pass(self):
        mi = self._make("HSK-A63")
        ti = self._make("HSK-A63")
        result = check_interface_compatibility(mi, ti)
        assert result.verdict is CompatibilityVerdict.PASS

    def test_bt30_vs_bt30_pass(self):
        mi = self._make("BT-30")
        ti = self._make("BT-30")
        result = check_interface_compatibility(mi, ti)
        assert result.verdict is CompatibilityVerdict.PASS

    # FAIL — family mismatch
    def test_cat40_vs_bt40_fail(self):
        mi = self._make("CAT-40")
        ti = self._make("BT-40")
        result = check_interface_compatibility(mi, ti)
        assert result.verdict is CompatibilityVerdict.FAIL
        assert "mismatch" in result.reason.lower()

    def test_cat40_vs_hsk_a63_fail(self):
        mi = self._make("CAT-40")
        ti = self._make("HSK-A63")
        result = check_interface_compatibility(mi, ti)
        assert result.verdict is CompatibilityVerdict.FAIL

    # FAIL — same family, different size
    def test_cat40_vs_cat50_fail(self):
        mi = self._make("CAT-40")
        ti = self._make("CAT-50")
        result = check_interface_compatibility(mi, ti)
        assert result.verdict is CompatibilityVerdict.FAIL
        assert "size mismatch" in result.reason.lower()

    def test_hsk_a63_vs_hsk_a50_fail(self):
        mi = self._make("HSK-A63")
        ti = self._make("HSK-A50")
        result = check_interface_compatibility(mi, ti)
        assert result.verdict is CompatibilityVerdict.FAIL

    def test_bt30_vs_bt40_fail(self):
        mi = self._make("BT-30")
        ti = self._make("BT-40")
        result = check_interface_compatibility(mi, ti)
        assert result.verdict is CompatibilityVerdict.FAIL

    # UNKNOWN — either side unknown
    def test_unknown_machine_gives_unknown(self):
        mi = self._make(None)
        ti = self._make("CAT-40")
        result = check_interface_compatibility(mi, ti)
        assert result.verdict is CompatibilityVerdict.UNKNOWN

    def test_unknown_tool_gives_unknown(self):
        mi = self._make("CAT-40")
        ti = self._make(None)
        result = check_interface_compatibility(mi, ti)
        assert result.verdict is CompatibilityVerdict.UNKNOWN

    def test_both_unknown_gives_unknown(self):
        mi = self._make(None)
        ti = self._make(None)
        result = check_interface_compatibility(mi, ti)
        assert result.verdict is CompatibilityVerdict.UNKNOWN

    def test_unrecognised_machine_gives_unknown(self):
        mi = self._make("MYSTERY-99")
        ti = self._make("CAT-40")
        result = check_interface_compatibility(mi, ti)
        assert result.verdict is CompatibilityVerdict.UNKNOWN

    # FAIL — NO_SPINDLE
    def test_no_spindle_machine_fails(self):
        mi = self._make("no_spindle")
        ti = self._make("CAT-40")
        result = check_interface_compatibility(mi, ti)
        assert result.verdict is CompatibilityVerdict.FAIL
        assert "NO_SPINDLE" in result.reason

    def test_no_spindle_tool_fails(self):
        mi = self._make("CAT-40")
        ti = self._make("no_spindle")
        result = check_interface_compatibility(mi, ti)
        assert result.verdict is CompatibilityVerdict.FAIL

    def test_both_no_spindle_fails(self):
        mi = self._make("no_spindle")
        ti = self._make("no_spindle")
        result = check_interface_compatibility(mi, ti)
        assert result.verdict is CompatibilityVerdict.FAIL

    # Result fields
    def test_result_carries_input_interfaces(self):
        mi = self._make("CAT-40")
        ti = self._make("BT-40")
        result = check_interface_compatibility(mi, ti)
        assert result.machine_interface is mi
        assert result.tool_interface is ti

    def test_pass_reason_contains_designation(self):
        mi = self._make("CAT-40")
        ti = self._make("CAT-40")
        result = check_interface_compatibility(mi, ti)
        assert "CAT-40" in result.reason

    def test_unknown_reason_mentions_unknown(self):
        mi = self._make(None)
        ti = self._make("CAT-40")
        result = check_interface_compatibility(mi, ti)
        assert "UNKNOWN" in result.reason


# ===========================================================================
# TestMultipleInterfacesScenario
# ===========================================================================


class TestMultipleInterfacesScenario:
    """Verify that multiple interface representations are independent and not conflated."""

    def test_cat40_and_bt40_are_distinct(self):
        r1 = _norm("CAT-40")
        r2 = _norm("BT-40")
        assert r1.family is not r2.family
        assert r1.designation != r2.designation

    def test_hsk_a63_and_hsk_a50_are_not_interchangeable(self):
        r1 = _norm("HSK-A63")
        r2 = _norm("HSK-A50")
        result = check_interface_compatibility(r1, r2)
        assert result.verdict is CompatibilityVerdict.FAIL

    def test_sk40_and_cat40_different_families(self):
        # SK-40 (DIN 69871) and CAT-40 (ANSI) are geometrically similar
        # but NOT interchangeable without an adapter
        r1 = _norm("SK40")
        r2 = _norm("CAT-40")
        assert r1.family is InterfaceFamily.SK
        assert r2.family is InterfaceFamily.CAT
        result = check_interface_compatibility(r1, r2)
        assert result.verdict is CompatibilityVerdict.FAIL

    def test_multiple_interfaces_normalised_independently(self):
        raws = ["CAT-40", "HSK-A63", "BT-30", "SK40", None]
        normed = [_norm(r) for r in raws]
        families = [n.family for n in normed]
        assert families[0] is InterfaceFamily.CAT
        assert families[1] is InterfaceFamily.HSK
        assert families[2] is InterfaceFamily.BT
        assert families[3] is InterfaceFamily.SK
        assert families[4] is InterfaceFamily.UNKNOWN
