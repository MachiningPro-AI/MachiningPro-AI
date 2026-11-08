"""Tests for backend.machine_library.validation."""


from backend.machine_library.enums import (
    MachineClass,
)
from backend.machine_library.models import (
    MachineCapability,
    MachineCatalogRecord,
    MachineEnvelope,
    MachineSourceMetadata,
    MachineSpindleSpecification,
)
from backend.machine_library.validation import (
    MachineCatalogValidationResult,
    validate_machine_catalog_record,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_record(
    stable_id: str = "valid-001",
    machine_class: MachineClass = MachineClass.THREE_AXIS_VMC,
    controlled_axes: int = 3,
    milling: bool = True,
    turning: bool = False,
    drilling: bool = True,
    grinding: bool = False,
    edm: bool = False,
    max_rpm: int | None = 10_000,
    power_kw: float | None = 11.0,
) -> MachineCatalogRecord:
    return MachineCatalogRecord(
        stable_id=stable_id,
        manufacturer="Test Mfr",
        model="Test Model",
        capability=MachineCapability(
            machine_class=machine_class,
            controlled_axes=controlled_axes,
            milling_capable=milling,
            turning_capable=turning,
            drilling_capable=drilling,
            grinding_capable=grinding,
            edm_capable=edm,
        ),
        spindle=MachineSpindleSpecification(max_rpm=max_rpm, power_kw=power_kw),
        envelope=MachineEnvelope(
            travel_x_mm=600.0, travel_y_mm=400.0, travel_z_mm=400.0
        ),
        source=MachineSourceMetadata(source_title="Test Source"),
    )


# ---------------------------------------------------------------------------
# V-ML-01: stable_id
# ---------------------------------------------------------------------------

class TestVML01:
    def test_pass_valid_stable_id(self):
        r = _valid_record(stable_id="good-id")
        result = validate_machine_catalog_record(r)
        assert "V-ML-01" not in " ".join(result.errors)

    def test_fail_empty_stable_id(self):
        r = _valid_record(stable_id="  ")
        # Pydantic will accept whitespace-only string but V-ML-01 should catch it
        result = validate_machine_catalog_record(r)
        assert any("V-ML-01" in e for e in result.errors)
        assert result.is_valid is False


# ---------------------------------------------------------------------------
# V-ML-05: controlled_axes
# ---------------------------------------------------------------------------

class TestVML05:
    def test_pass_positive_axes(self):
        r = _valid_record(controlled_axes=3)
        result = validate_machine_catalog_record(r)
        assert "V-ML-05" not in " ".join(result.errors)


# ---------------------------------------------------------------------------
# V-ML-06: simultaneous_axes
# ---------------------------------------------------------------------------

class TestVML06:
    def test_pass_simultaneous_eq_controlled(self):
        r = MachineCatalogRecord(
            stable_id="sim-01",
            manufacturer="M",
            model="Mod",
            capability=MachineCapability(
                machine_class=MachineClass.FIVE_AXIS_VMC,
                controlled_axes=5,
                simultaneous_axes=5,
                milling_capable=True,
            ),
            spindle=MachineSpindleSpecification(max_rpm=14_000, power_kw=16.0),
            envelope=MachineEnvelope(travel_x_mm=500.0, travel_y_mm=450.0, travel_z_mm=400.0),
            source=MachineSourceMetadata(source_title="Test"),
        )
        result = validate_machine_catalog_record(r)
        assert "V-ML-06" not in " ".join(result.errors)

    def test_fail_simultaneous_exceeds_controlled(self):
        r = MachineCatalogRecord(
            stable_id="sim-fail",
            manufacturer="M",
            model="Mod",
            capability=MachineCapability(
                machine_class=MachineClass.THREE_AXIS_VMC,
                controlled_axes=3,
                simultaneous_axes=5,   # violates V-ML-06
                milling_capable=True,
            ),
            spindle=MachineSpindleSpecification(max_rpm=10_000, power_kw=11.0),
            envelope=MachineEnvelope(),
            source=MachineSourceMetadata(source_title="Test"),
        )
        result = validate_machine_catalog_record(r)
        assert any("V-ML-06" in e for e in result.errors)
        assert result.is_valid is False


# ---------------------------------------------------------------------------
# V-ML-07: at least one primary capability
# ---------------------------------------------------------------------------

class TestVML07:
    def test_fail_no_capability(self):
        r = MachineCatalogRecord(
            stable_id="nocap-01",
            manufacturer="M",
            model="Mod",
            capability=MachineCapability(
                machine_class=MachineClass.THREE_AXIS_VMC,
                controlled_axes=3,
                # all capability flags False
            ),
            spindle=MachineSpindleSpecification(max_rpm=10_000, power_kw=11.0),
            envelope=MachineEnvelope(travel_x_mm=600.0, travel_y_mm=400.0, travel_z_mm=400.0),
            source=MachineSourceMetadata(source_title="Test"),
        )
        result = validate_machine_catalog_record(r)
        assert any("V-ML-07" in e for e in result.errors)
        assert result.is_valid is False

    def test_pass_grinding_capable(self):
        r = _valid_record(milling=False, drilling=False, grinding=True)
        result = validate_machine_catalog_record(r)
        assert "V-ML-07" not in " ".join(result.errors)

    def test_pass_edm_capable(self):
        r = _valid_record(milling=False, drilling=False, edm=True)
        result = validate_machine_catalog_record(r)
        assert "V-ML-07" not in " ".join(result.errors)


# ---------------------------------------------------------------------------
# V-ML-08: source_title
# ---------------------------------------------------------------------------

class TestVML08:
    def test_fail_empty_source_title(self):
        r = MachineCatalogRecord(
            stable_id="src-fail",
            manufacturer="M",
            model="Mod",
            capability=MachineCapability(
                machine_class=MachineClass.THREE_AXIS_VMC,
                controlled_axes=3,
                milling_capable=True,
            ),
            spindle=MachineSpindleSpecification(max_rpm=10_000, power_kw=11.0),
            envelope=MachineEnvelope(travel_x_mm=600.0, travel_y_mm=400.0, travel_z_mm=400.0),
            source=MachineSourceMetadata(source_title="  "),
        )
        result = validate_machine_catalog_record(r)
        assert any("V-ML-08" in e for e in result.errors)


# ---------------------------------------------------------------------------
# V-ML-09, V-ML-10: spindle RPM validation
# ---------------------------------------------------------------------------

class TestVML09VML10:
    def test_fail_max_rpm_zero(self):
        r = MachineCatalogRecord(
            stable_id="rpm-zero",
            manufacturer="M",
            model="Mod",
            capability=MachineCapability(
                machine_class=MachineClass.THREE_AXIS_VMC,
                controlled_axes=3,
                milling_capable=True,
            ),
            spindle=MachineSpindleSpecification(max_rpm=0, power_kw=11.0),
            envelope=MachineEnvelope(travel_x_mm=600.0, travel_y_mm=400.0, travel_z_mm=400.0),
            source=MachineSourceMetadata(source_title="Test"),
        )
        result = validate_machine_catalog_record(r)
        assert any("V-ML-09" in e for e in result.errors)

    def test_fail_min_rpm_exceeds_max_rpm(self):
        r = MachineCatalogRecord(
            stable_id="rpm-inv",
            manufacturer="M",
            model="Mod",
            capability=MachineCapability(
                machine_class=MachineClass.THREE_AXIS_VMC,
                controlled_axes=3,
                milling_capable=True,
            ),
            spindle=MachineSpindleSpecification(min_rpm=5_000, max_rpm=1_000),
            envelope=MachineEnvelope(travel_x_mm=600.0, travel_y_mm=400.0, travel_z_mm=400.0),
            source=MachineSourceMetadata(source_title="Test"),
        )
        result = validate_machine_catalog_record(r)
        assert any("V-ML-10" in e for e in result.errors)
        assert result.is_valid is False


# ---------------------------------------------------------------------------
# V-ML-16, V-ML-17: turning field warnings
# ---------------------------------------------------------------------------

class TestTurningWarnings:
    def test_warn_bar_capacity_without_turning(self):
        r = MachineCatalogRecord(
            stable_id="bar-warn",
            manufacturer="M",
            model="Mod",
            capability=MachineCapability(
                machine_class=MachineClass.THREE_AXIS_VMC,
                controlled_axes=3,
                milling_capable=True,
            ),
            spindle=MachineSpindleSpecification(max_rpm=10_000, power_kw=11.0),
            envelope=MachineEnvelope(
                travel_x_mm=600.0, travel_y_mm=400.0, travel_z_mm=400.0,
                bar_capacity_mm=65.0,
            ),
            source=MachineSourceMetadata(source_title="Test"),
        )
        result = validate_machine_catalog_record(r)
        assert any("V-ML-16" in w for w in result.warnings)
        assert result.is_valid is True  # warning, not error


# ---------------------------------------------------------------------------
# V-ML-22: Swiss lathe bar_capacity warning
# ---------------------------------------------------------------------------

class TestVML22:
    def test_warn_swiss_lathe_no_bar_capacity(self):
        r = MachineCatalogRecord(
            stable_id="swiss-warn",
            manufacturer="M",
            model="Mod",
            capability=MachineCapability(
                machine_class=MachineClass.SWISS_LATHE,
                controlled_axes=7,
                turning_capable=True,
            ),
            spindle=MachineSpindleSpecification(max_rpm=10_000, power_kw=5.5),
            envelope=MachineEnvelope(),   # bar_capacity_mm absent
            source=MachineSourceMetadata(source_title="Test"),
        )
        result = validate_machine_catalog_record(r)
        assert any("V-ML-22" in w for w in result.warnings)

    def test_no_warn_swiss_lathe_with_bar_capacity(self):
        r = MachineCatalogRecord(
            stable_id="swiss-ok",
            manufacturer="M",
            model="Mod",
            capability=MachineCapability(
                machine_class=MachineClass.SWISS_LATHE,
                controlled_axes=7,
                turning_capable=True,
            ),
            spindle=MachineSpindleSpecification(max_rpm=10_000, power_kw=5.5),
            envelope=MachineEnvelope(bar_capacity_mm=20.0),
            source=MachineSourceMetadata(source_title="Test"),
        )
        result = validate_machine_catalog_record(r)
        assert not any("V-ML-22" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# V-ML-27: TURN_MILL both milling+turning
# ---------------------------------------------------------------------------

class TestVML27:
    def test_warn_turn_mill_missing_milling(self):
        r = MachineCatalogRecord(
            stable_id="tm-warn",
            manufacturer="M",
            model="Mod",
            capability=MachineCapability(
                machine_class=MachineClass.TURN_MILL,
                controlled_axes=5,
                turning_capable=True,
                milling_capable=False,  # violates V-ML-27 convention
                drilling_capable=True,
            ),
            spindle=MachineSpindleSpecification(max_rpm=5_000, power_kw=18.5),
            envelope=MachineEnvelope(max_turning_diameter_mm=400.0),
            source=MachineSourceMetadata(source_title="Test"),
        )
        result = validate_machine_catalog_record(r)
        assert any("V-ML-27" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# V-ML-26: year_discontinued < year_introduced
# ---------------------------------------------------------------------------

class TestVML26:
    def test_fail_discontinued_before_introduced(self):
        r = MachineCatalogRecord(
            stable_id="yr-fail",
            manufacturer="M",
            model="Mod",
            capability=MachineCapability(
                machine_class=MachineClass.THREE_AXIS_VMC,
                controlled_axes=3,
                milling_capable=True,
            ),
            spindle=MachineSpindleSpecification(max_rpm=10_000, power_kw=11.0),
            envelope=MachineEnvelope(travel_x_mm=600.0, travel_y_mm=400.0, travel_z_mm=400.0),
            source=MachineSourceMetadata(source_title="Test"),
            year_introduced=2020,
            year_discontinued=2010,
        )
        result = validate_machine_catalog_record(r)
        assert any("V-ML-26" in e for e in result.errors)
        assert result.is_valid is False


# ---------------------------------------------------------------------------
# ValidationResult dataclass
# ---------------------------------------------------------------------------

class TestValidationResultDataclass:
    def test_error_count_property(self):
        result = MachineCatalogValidationResult(
            stable_id="test",
            is_valid=False,
            errors=["E1", "E2"],
        )
        assert result.error_count == 2

    def test_warning_count_property(self):
        result = MachineCatalogValidationResult(
            stable_id="test",
            is_valid=True,
            warnings=["W1"],
        )
        assert result.warning_count == 1
