"""Cross-library compatibility tests — Machine × Material × Tool integration.

Exercises the integration adapters against real seed catalog data from all
three libraries.  Uses only public data from the seed catalogs; no fabricated
specs.

Test areas:
  1. Machine + Material ISO group cross-reference via result_mapping
  2. Machine + Tool spindle interface compatibility via spindle_adapter
  3. Material ISO group identity between machine_library and material_library
  4. PASS/FAIL/UNKNOWN preservation through cross-library evaluation chains
  5. combine_verdicts representative cross-library scenario
"""

from __future__ import annotations

import pytest

from backend.integration.material_namespace import MachineConditionState
from backend.integration.result_mapping import (
    IntegrationVerdict,
    combine_verdicts,
    from_interface_compatibility_verdict,
    from_material_compatibility_verdict,
)
from backend.integration.spindle_adapter import (
    check_holder_machine_spindle_compatibility,
    normalize_holder_spindle_interface,
)
from backend.machine_library.interfaces import (
    CompatibilityVerdict as InterfaceCompatibilityVerdict,
)
from backend.machine_library.interfaces import (
    InterfaceFamily,
)
from backend.machine_library.material_context import (
    MachiningOperation,
    MaterialMachiningContext,
    evaluate_material_context,
)
from backend.machine_library.material_context import (
    MaterialISOGroup as MachineISOGroup,
)
from backend.machine_library.registry import MachineCatalogRegistry
from backend.machine_library.seed_catalog import seed_machine_library
from backend.material_library.enums import MaterialISOGroup as MaterialISOGroupEnum
from backend.material_library.registry import MaterialCatalogRegistry
from backend.material_library.seed_catalog import seed_material_library

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def machine_registry() -> MachineCatalogRegistry:
    r = MachineCatalogRegistry()
    for rec in seed_machine_library():
        r.register(rec)
    return r


@pytest.fixture(scope="module")
def material_registry() -> MaterialCatalogRegistry:
    return MaterialCatalogRegistry(seed_material_library())


# ---------------------------------------------------------------------------
# 1. ISO group identity between machine_library and material_library
# ---------------------------------------------------------------------------


class TestISOGroupIdentity:
    """MaterialISOGroup in both libraries must share the same string values."""

    def test_p_value_matches(self):
        assert str(MachineISOGroup.P) == str(MaterialISOGroupEnum.P)

    def test_m_value_matches(self):
        assert str(MachineISOGroup.M) == str(MaterialISOGroupEnum.M)

    def test_k_value_matches(self):
        assert str(MachineISOGroup.K) == str(MaterialISOGroupEnum.K)

    def test_n_value_matches(self):
        assert str(MachineISOGroup.N) == str(MaterialISOGroupEnum.N)

    def test_s_value_matches(self):
        assert str(MachineISOGroup.S) == str(MaterialISOGroupEnum.S)

    def test_h_value_matches(self):
        assert str(MachineISOGroup.H) == str(MaterialISOGroupEnum.H)

    def test_unknown_value_matches(self):
        assert str(MachineISOGroup.UNKNOWN) == str(MaterialISOGroupEnum.UNKNOWN)

    def test_machine_iso_group_from_material_iso_group(self):
        """MachineISOGroup can be constructed from MaterialISOGroup string values."""
        for mat_group in MaterialISOGroupEnum:
            mach_group = MachineISOGroup(mat_group.value)
            assert mach_group.value == mat_group.value


# ---------------------------------------------------------------------------
# 2. Machine + Material: evaluate machine against material ISO group context
# ---------------------------------------------------------------------------


class TestMachineMaterialCompatibility:
    def test_haas_vf2ss_p_milling_pass(self, machine_registry):
        """Haas VF-2SS (milling_capable=True) + ISO P milling context → PASS."""
        haas = machine_registry.get("ml-haas-vf-2ss")
        ctx = MaterialMachiningContext(
            iso_group=MachineISOGroup.P,
            operation=MachiningOperation.MILLING,
        )
        result = evaluate_material_context(ctx, haas)
        iv = from_material_compatibility_verdict(result.verdict)
        assert iv is IntegrationVerdict.PASS

    def test_haas_vf2ss_p_turning_fail_or_unknown(self, machine_registry):
        """Haas VF-2SS is a VMC — turning operation returns FAIL or UNKNOWN."""
        haas = machine_registry.get("ml-haas-vf-2ss")
        ctx = MaterialMachiningContext(
            iso_group=MachineISOGroup.P,
            operation=MachiningOperation.TURNING,
        )
        result = evaluate_material_context(ctx, haas)
        iv = from_material_compatibility_verdict(result.verdict)
        assert iv in (IntegrationVerdict.FAIL, IntegrationVerdict.UNKNOWN)

    def test_p_material_in_registry(self, material_registry):
        """P-C45 material is in the material registry with ISO group P."""
        rec = material_registry.get("P-C45")
        assert rec is not None
        assert rec.iso_group is MaterialISOGroupEnum.P

    def test_s_material_in_registry(self, material_registry):
        """S-Ti64 (titanium) is in the material registry with ISO group S."""
        rec = material_registry.get("S-Ti64")
        assert rec is not None
        assert rec.iso_group is MaterialISOGroupEnum.S

    def test_haas_vf2ss_s_milling_pass_with_warning(self, machine_registry):
        """Haas VF-2SS + ISO S milling — machine PASSES but advisory warning expected."""
        haas = machine_registry.get("ml-haas-vf-2ss")
        ctx = MaterialMachiningContext(
            iso_group=MachineISOGroup.S,
            operation=MachiningOperation.MILLING,
        )
        result = evaluate_material_context(ctx, haas)
        iv = from_material_compatibility_verdict(result.verdict)
        assert iv is IntegrationVerdict.PASS
        assert any("ISO_S" in w for w in result.warnings)

    def test_unknown_operation_gives_unknown(self, machine_registry):
        """UNKNOWN operation must give UNKNOWN verdict, never PASS."""
        haas = machine_registry.get("ml-haas-vf-2ss")
        ctx = MaterialMachiningContext(
            iso_group=MachineISOGroup.P,
            operation=MachiningOperation.UNKNOWN,
        )
        result = evaluate_material_context(ctx, haas)
        iv = from_material_compatibility_verdict(result.verdict)
        assert iv is IntegrationVerdict.UNKNOWN


# ---------------------------------------------------------------------------
# 3. Machine + Tool: spindle interface compatibility
# ---------------------------------------------------------------------------


class TestMachineToolSpindleCompatibility:
    def test_haas_cat40_holder_cat40_pass(self, machine_registry):
        """Haas VF-2SS spindle is CAT-40 — holder with CAT40 → PASS."""
        haas = machine_registry.get("ml-haas-vf-2ss")
        machine_spindle_raw = haas.spindle.interface  # "CAT-40"
        result = check_holder_machine_spindle_compatibility("CAT40", machine_spindle_raw)
        assert result.verdict is InterfaceCompatibilityVerdict.PASS

    def test_haas_cat40_holder_bt40_fail(self, machine_registry):
        """Haas VF-2SS (CAT-40) vs BT40 holder → FAIL (CAT40 ≠ BT40)."""
        haas = machine_registry.get("ml-haas-vf-2ss")
        machine_spindle_raw = haas.spindle.interface
        result = check_holder_machine_spindle_compatibility("BT40", machine_spindle_raw)
        assert result.verdict is InterfaceCompatibilityVerdict.FAIL

    def test_haas_cat40_holder_hsk_a63_fail(self, machine_registry):
        """Haas VF-2SS (CAT-40) vs HSK-A63 holder → FAIL (family mismatch)."""
        haas = machine_registry.get("ml-haas-vf-2ss")
        machine_spindle_raw = haas.spindle.interface
        result = check_holder_machine_spindle_compatibility("HSK-A63", machine_spindle_raw)
        assert result.verdict is InterfaceCompatibilityVerdict.FAIL

    def test_none_holder_spindle_gives_unknown(self, machine_registry):
        """Holder with no spindle_interface (None) → UNKNOWN."""
        haas = machine_registry.get("ml-haas-vf-2ss")
        machine_spindle_raw = haas.spindle.interface
        result = check_holder_machine_spindle_compatibility(None, machine_spindle_raw)
        assert result.verdict is InterfaceCompatibilityVerdict.UNKNOWN

    def test_normalized_family_bt40(self):
        """BT40 normalizes to BT family, not CAT."""
        norm = normalize_holder_spindle_interface("BT40")
        assert norm.family is InterfaceFamily.BT

    def test_normalized_family_cat40(self):
        """CAT40 normalizes to CAT family, not BT."""
        norm = normalize_holder_spindle_interface("CAT40")
        assert norm.family is InterfaceFamily.CAT


# ---------------------------------------------------------------------------
# 4. Cross-library combine_verdicts representative scenario
# ---------------------------------------------------------------------------


class TestCrossLibraryCombineVerdicts:
    def test_machine_pass_spindle_pass_gives_pass(self, machine_registry):
        """Machine capability PASS + spindle PASS → combined PASS."""
        haas = machine_registry.get("ml-haas-vf-2ss")
        ctx = MaterialMachiningContext(
            iso_group=MachineISOGroup.P,
            operation=MachiningOperation.MILLING,
        )
        machine_v = from_material_compatibility_verdict(
            evaluate_material_context(ctx, haas).verdict
        )
        spindle_r = check_holder_machine_spindle_compatibility(
            "CAT40", haas.spindle.interface
        )
        spindle_v = from_interface_compatibility_verdict(spindle_r.verdict)
        combined = combine_verdicts(machine_v, spindle_v)
        assert combined is IntegrationVerdict.PASS

    def test_machine_pass_spindle_fail_gives_fail(self, machine_registry):
        """Machine capability PASS + spindle FAIL (wrong interface) → combined FAIL."""
        haas = machine_registry.get("ml-haas-vf-2ss")
        ctx = MaterialMachiningContext(
            iso_group=MachineISOGroup.P,
            operation=MachiningOperation.MILLING,
        )
        machine_v = from_material_compatibility_verdict(
            evaluate_material_context(ctx, haas).verdict
        )
        spindle_r = check_holder_machine_spindle_compatibility(
            "BT40", haas.spindle.interface
        )
        spindle_v = from_interface_compatibility_verdict(spindle_r.verdict)
        combined = combine_verdicts(machine_v, spindle_v)
        assert combined is IntegrationVerdict.FAIL

    def test_machine_pass_spindle_unknown_gives_unknown(self, machine_registry):
        """Machine capability PASS + spindle UNKNOWN → combined UNKNOWN (not PASS)."""
        haas = machine_registry.get("ml-haas-vf-2ss")
        ctx = MaterialMachiningContext(
            iso_group=MachineISOGroup.P,
            operation=MachiningOperation.MILLING,
        )
        machine_v = from_material_compatibility_verdict(
            evaluate_material_context(ctx, haas).verdict
        )
        spindle_r = check_holder_machine_spindle_compatibility(
            None, haas.spindle.interface
        )
        spindle_v = from_interface_compatibility_verdict(spindle_r.verdict)
        combined = combine_verdicts(machine_v, spindle_v)
        assert combined is IntegrationVerdict.UNKNOWN

    def test_unknown_never_promoted_to_pass_in_chain(self, machine_registry):
        """A chain containing UNKNOWN must never resolve to PASS."""
        haas = machine_registry.get("ml-haas-vf-2ss")
        ctx = MaterialMachiningContext(
            iso_group=MachineISOGroup.P,
            operation=MachiningOperation.UNKNOWN,
        )
        machine_v = from_material_compatibility_verdict(
            evaluate_material_context(ctx, haas).verdict
        )
        assert machine_v is IntegrationVerdict.UNKNOWN
        combined = combine_verdicts(machine_v, IntegrationVerdict.PASS)
        assert combined is not IntegrationVerdict.PASS


# ---------------------------------------------------------------------------
# 5. MachineConditionState used in planning context
# ---------------------------------------------------------------------------


class TestMachineConditionStateInContext:
    def test_known_condition_states_valid(self):
        """MachineConditionState values can be used in machine-library context."""
        for state in MachineConditionState:
            assert state.value  # non-empty string

    def test_condition_state_unknown_preserved(self):
        assert MachineConditionState.UNKNOWN.value == "UNKNOWN"
