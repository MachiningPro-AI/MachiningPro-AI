"""Tests for spindle_adapter — holder spindle interface normalization and compatibility.

Verifies:
- normalize_holder_spindle_interface correctly wraps Machine Library normalizer
- None / blank → UNKNOWN (not PASS)
- Recognized strings produce correct InterfaceFamily
- CAT-40 ≠ BT-40 (different families → FAIL)
- Same family, same size → PASS
- Same family, different size → FAIL
- UNKNOWN ≠ anything → UNKNOWN (never PASS)
- Unrecognized raw string → UNVERIFIED status, UNKNOWN family
"""

from backend.integration.spindle_adapter import (
    check_holder_machine_spindle_compatibility,
    normalize_holder_spindle_interface,
)
from backend.machine_library.interfaces import (
    CompatibilityVerdict,
    InterfaceFamily,
    InterfaceVerificationStatus,
)


class TestNormalizeHolderSpindleInterface:
    def test_none_gives_unknown(self):
        r = normalize_holder_spindle_interface(None)
        assert r.family is InterfaceFamily.UNKNOWN

    def test_blank_gives_unknown(self):
        r = normalize_holder_spindle_interface("   ")
        assert r.family is InterfaceFamily.UNKNOWN

    def test_bt40_recognized(self):
        r = normalize_holder_spindle_interface("BT40")
        assert r.family is InterfaceFamily.BT
        assert r.designation == "BT-40"

    def test_cat40_recognized(self):
        r = normalize_holder_spindle_interface("CAT40")
        assert r.family is InterfaceFamily.CAT
        assert r.designation == "CAT-40"

    def test_hsk_a63_recognized(self):
        r = normalize_holder_spindle_interface("HSK-A63")
        assert r.family is InterfaceFamily.HSK
        assert r.designation == "HSK-A63"

    def test_capto_c6_recognized(self):
        r = normalize_holder_spindle_interface("C6")
        assert r.family is InterfaceFamily.CAPTO

    def test_unrecognized_raw_preserved(self):
        r = normalize_holder_spindle_interface("MYSTERY-99")
        assert r.family is InterfaceFamily.UNKNOWN
        assert r.designation == "MYSTERY-99"
        assert r.verification_status is InterfaceVerificationStatus.UNVERIFIED

    def test_known_interface_has_inferred_status(self):
        r = normalize_holder_spindle_interface("BT40")
        assert r.verification_status is InterfaceVerificationStatus.INFERRED

    def test_source_note_applied(self):
        r = normalize_holder_spindle_interface("BT40", source_note="TEST_NOTE")
        assert r.source_note == "TEST_NOTE"

    def test_case_insensitive_bt30(self):
        r = normalize_holder_spindle_interface("bt30")
        assert r.family is InterfaceFamily.BT
        assert r.designation == "BT-30"


class TestCheckHolderMachineSpindleCompatibility:
    def test_bt40_bt40_pass(self):
        r = check_holder_machine_spindle_compatibility("BT40", "BT40")
        assert r.verdict is CompatibilityVerdict.PASS

    def test_hsk_a63_hsk_a63_pass(self):
        r = check_holder_machine_spindle_compatibility("HSK-A63", "HSK-A63")
        assert r.verdict is CompatibilityVerdict.PASS

    def test_cat40_bt40_fail(self):
        """CAT-40 and BT-40 are NOT equivalent — different pull-stud geometry."""
        r = check_holder_machine_spindle_compatibility("CAT40", "BT40")
        assert r.verdict is CompatibilityVerdict.FAIL

    def test_bt40_cat40_fail(self):
        r = check_holder_machine_spindle_compatibility("BT40", "CAT40")
        assert r.verdict is CompatibilityVerdict.FAIL

    def test_bt40_bt50_fail(self):
        """Same family, different size — not compatible."""
        r = check_holder_machine_spindle_compatibility("BT40", "BT50")
        assert r.verdict is CompatibilityVerdict.FAIL

    def test_hsk_a63_hsk_a80_fail(self):
        r = check_holder_machine_spindle_compatibility("HSK-A63", "HSK-A80")
        assert r.verdict is CompatibilityVerdict.FAIL

    def test_none_holder_unknown(self):
        r = check_holder_machine_spindle_compatibility(None, "BT40")
        assert r.verdict is CompatibilityVerdict.UNKNOWN

    def test_none_machine_unknown(self):
        r = check_holder_machine_spindle_compatibility("BT40", None)
        assert r.verdict is CompatibilityVerdict.UNKNOWN

    def test_both_none_unknown(self):
        r = check_holder_machine_spindle_compatibility(None, None)
        assert r.verdict is CompatibilityVerdict.UNKNOWN

    def test_unrecognized_holder_unknown(self):
        r = check_holder_machine_spindle_compatibility("MYSTERY-99", "BT40")
        assert r.verdict is CompatibilityVerdict.UNKNOWN

    def test_unrecognized_machine_unknown(self):
        r = check_holder_machine_spindle_compatibility("BT40", "MYSTERY-99")
        assert r.verdict is CompatibilityVerdict.UNKNOWN

    def test_cat40_cat40_pass(self):
        r = check_holder_machine_spindle_compatibility("CAT40", "CAT40")
        assert r.verdict is CompatibilityVerdict.PASS

    def test_hsk_a50_hsk_a50_pass(self):
        r = check_holder_machine_spindle_compatibility("HSK-A50", "HSK-A50")
        assert r.verdict is CompatibilityVerdict.PASS
