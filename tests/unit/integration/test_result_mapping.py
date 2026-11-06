"""Tests for result_mapping — unified IntegrationVerdict across library types.

Verifies:
- IntegrationVerdict is a StrEnum with PASS/FAIL/UNKNOWN
- from_compatibility_status converts all three Tool Library values
- from_material_compatibility_verdict converts all three Machine Library material values
- from_interface_compatibility_verdict converts all three Machine Library interface values
- combine_verdicts: conservative precedence (FAIL > UNKNOWN > PASS)
- combine_verdicts with empty input → UNKNOWN (not PASS)
- UNKNOWN never collapses to PASS in combine_verdicts
"""
from enum import StrEnum

from backend.cutting_tools.compatibility import CompatibilityStatus
from backend.integration.result_mapping import (
    IntegrationVerdict,
    combine_verdicts,
    from_compatibility_status,
    from_interface_compatibility_verdict,
    from_material_compatibility_verdict,
)
from backend.machine_library.interfaces import (
    CompatibilityVerdict as InterfaceCompatibilityVerdict,
)
from backend.machine_library.material_context import MaterialCompatibilityVerdict


class TestIntegrationVerdict:
    def test_is_str_enum(self):
        assert issubclass(IntegrationVerdict, StrEnum)

    def test_has_pass(self):
        assert IntegrationVerdict.PASS == "PASS"

    def test_has_fail(self):
        assert IntegrationVerdict.FAIL == "FAIL"

    def test_has_unknown(self):
        assert IntegrationVerdict.UNKNOWN == "UNKNOWN"

    def test_exactly_three_members(self):
        assert len(IntegrationVerdict) == 3


class TestFromCompatibilityStatus:
    def test_pass(self):
        assert from_compatibility_status(CompatibilityStatus.PASS) is IntegrationVerdict.PASS

    def test_fail(self):
        assert from_compatibility_status(CompatibilityStatus.FAIL) is IntegrationVerdict.FAIL

    def test_unknown(self):
        assert from_compatibility_status(CompatibilityStatus.UNKNOWN) is IntegrationVerdict.UNKNOWN

    def test_all_values_covered(self):
        for cs in CompatibilityStatus:
            iv = from_compatibility_status(cs)
            assert iv.value == cs.value


class TestFromMaterialCompatibilityVerdict:
    def test_pass(self):
        v = from_material_compatibility_verdict(MaterialCompatibilityVerdict.PASS)
        assert v is IntegrationVerdict.PASS

    def test_fail(self):
        v = from_material_compatibility_verdict(MaterialCompatibilityVerdict.FAIL)
        assert v is IntegrationVerdict.FAIL

    def test_unknown(self):
        v = from_material_compatibility_verdict(MaterialCompatibilityVerdict.UNKNOWN)
        assert v is IntegrationVerdict.UNKNOWN

    def test_all_values_covered(self):
        for mv in MaterialCompatibilityVerdict:
            iv = from_material_compatibility_verdict(mv)
            assert iv.value == mv.value


class TestFromInterfaceCompatibilityVerdict:
    def test_pass(self):
        v = from_interface_compatibility_verdict(InterfaceCompatibilityVerdict.PASS)
        assert v is IntegrationVerdict.PASS

    def test_fail(self):
        v = from_interface_compatibility_verdict(InterfaceCompatibilityVerdict.FAIL)
        assert v is IntegrationVerdict.FAIL

    def test_unknown(self):
        v = from_interface_compatibility_verdict(InterfaceCompatibilityVerdict.UNKNOWN)
        assert v is IntegrationVerdict.UNKNOWN


class TestCombineVerdicts:
    def test_all_pass_gives_pass(self):
        r = combine_verdicts(IntegrationVerdict.PASS, IntegrationVerdict.PASS)
        assert r is IntegrationVerdict.PASS

    def test_pass_and_unknown_gives_unknown(self):
        r = combine_verdicts(IntegrationVerdict.PASS, IntegrationVerdict.UNKNOWN)
        assert r is IntegrationVerdict.UNKNOWN

    def test_pass_and_fail_gives_fail(self):
        r = combine_verdicts(IntegrationVerdict.PASS, IntegrationVerdict.FAIL)
        assert r is IntegrationVerdict.FAIL

    def test_unknown_and_fail_gives_fail(self):
        r = combine_verdicts(IntegrationVerdict.UNKNOWN, IntegrationVerdict.FAIL)
        assert r is IntegrationVerdict.FAIL

    def test_all_unknown_gives_unknown(self):
        r = combine_verdicts(
            IntegrationVerdict.UNKNOWN,
            IntegrationVerdict.UNKNOWN,
            IntegrationVerdict.UNKNOWN,
        )
        assert r is IntegrationVerdict.UNKNOWN

    def test_empty_gives_unknown(self):
        """Empty combination → UNKNOWN (conservative — not PASS)."""
        r = combine_verdicts()
        assert r is IntegrationVerdict.UNKNOWN

    def test_single_pass(self):
        r = combine_verdicts(IntegrationVerdict.PASS)
        assert r is IntegrationVerdict.PASS

    def test_single_fail(self):
        r = combine_verdicts(IntegrationVerdict.FAIL)
        assert r is IntegrationVerdict.FAIL

    def test_fail_dominates_all(self):
        r = combine_verdicts(
            IntegrationVerdict.PASS,
            IntegrationVerdict.UNKNOWN,
            IntegrationVerdict.FAIL,
            IntegrationVerdict.PASS,
        )
        assert r is IntegrationVerdict.FAIL

    def test_unknown_dominates_pass(self):
        r = combine_verdicts(IntegrationVerdict.PASS, IntegrationVerdict.UNKNOWN)
        assert r is not IntegrationVerdict.PASS

    def test_unknown_never_becomes_pass(self):
        """UNKNOWN must NOT be promoted to PASS under any combination."""
        for v in [IntegrationVerdict.UNKNOWN, IntegrationVerdict.FAIL]:
            result = combine_verdicts(v, IntegrationVerdict.PASS)
            assert result is not IntegrationVerdict.PASS or v is IntegrationVerdict.PASS
