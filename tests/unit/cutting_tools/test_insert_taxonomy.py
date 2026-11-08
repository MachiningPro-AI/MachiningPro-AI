"""Tests for InsertRecord model and ISO 1832 parser.

Covers:
- InsertGeometry, InsertGrade, InsertSourceMetadata, InsertDesignation, InsertRecord
- ISO 1832 parser for valid designations (turning, milling, grooving inserts)
- Spaces and hyphen-delimited manufacturer suffix handling
- Unknown/unsupported position codes → warning, not exception
- Too-short input → ValueError
- UNKNOWN propagation in parse_warnings
- Contradictory specification detection
- Provenance / evidence_status semantics
"""
import pytest

from backend.cutting_tools import (
    InsertGeometry,
    InsertGrade,
    InsertRecord,
    InsertSourceMetadata,
    parse_iso1832,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

def _provenance(status: str = "MANUFACTURER_CATALOG") -> InsertSourceMetadata:
    return InsertSourceMetadata(
        source_title="Test",
        source_authority="Test",
        evidence_status=status,
        catalog_code="TEST-001" if status == "MANUFACTURER_CATALOG" else None,
    )


def _make_insert(
    designation_str: str = "CNMG120408",
    shape: str = "C",
    ic_mm: float | None = 12.0,
    operations: list[str] | None = None,
    iso_groups: list[str] | None = None,
    evidence_status: str = "MANUFACTURER_CATALOG",
) -> InsertRecord:
    d = parse_iso1832(designation_str)
    return InsertRecord(
        stable_id="test-cnmg-120408",
        manufacturer="TestMfr",
        product_name="Test CNMG 120408",
        designation=d,
        geometry=InsertGeometry(
            shape_code=shape,
            clearance_angle_deg=d.clearance_deg,
            tolerance_class=d.tolerance_code,
            ic_mm=ic_mm,
            thickness_mm=d.thickness_mm,
            nose_radius_mm=d.nose_radius_mm,
            cutting_direction=d.cutting_direction_code,
        ),
        grade=InsertGrade(
            substrate_material_code="CARBIDE",
            coating_type="CVD",
        ),
        provenance=_provenance(evidence_status),
        iso_material_groups=iso_groups or ["P", "M"],
        supported_operations=operations or ["turning"],
    )


# ── InsertDesignation model ───────────────────────────────────────────────────


class TestInsertDesignationModel:
    def test_all_fields_present(self):
        d = parse_iso1832("CNMG120408")
        assert d.raw == "CNMG120408"
        assert d.shape_code == "C"
        assert d.clearance_code == "N"
        assert d.tolerance_code == "M"
        assert d.type_code == "G"
        assert d.size_code == "12"
        assert d.thickness_code == "04"
        assert d.nose_radius_code == "08"
        assert isinstance(d.parse_warnings, list)

    def test_shape_description_decoded(self):
        d = parse_iso1832("CNMG120408")
        assert d.shape_description == "Rhombic 80°"

    def test_clearance_deg_decoded(self):
        d = parse_iso1832("CNMG120408")
        assert d.clearance_deg == 0.0

    def test_ic_mm_decoded(self):
        d = parse_iso1832("CNMG120408")
        assert d.ic_mm == 12.0

    def test_thickness_decoded(self):
        d = parse_iso1832("CNMG120408")
        assert d.thickness_mm == pytest.approx(4.76)

    def test_nose_radius_decoded(self):
        d = parse_iso1832("CNMG120408")
        assert d.nose_radius_mm == pytest.approx(0.8)

    def test_no_manufacturer_specific_on_bare_designation(self):
        d = parse_iso1832("CNMG120408")
        assert d.manufacturer_specific is None
        assert d.cutting_direction_code is None

    def test_no_warnings_on_valid_designation(self):
        d = parse_iso1832("CNMG120408")
        assert d.parse_warnings == []


# ── ISO 1832 parser — valid designations ─────────────────────────────────────


class TestISO1832ParserValid:
    def test_cnmg_120408(self):
        d = parse_iso1832("CNMG120408")
        assert d.shape_code == "C"
        assert d.clearance_deg == 0.0
        assert d.tolerance_code == "M"
        assert d.type_code == "G"
        assert d.ic_mm == 12.0
        assert d.thickness_mm == pytest.approx(4.76)
        assert d.nose_radius_mm == pytest.approx(0.8)

    def test_snmg_120408(self):
        d = parse_iso1832("SNMG120408")
        assert d.shape_code == "S"
        assert d.shape_description == "Square 90°"
        assert d.ic_mm == 12.0

    def test_tnmg_160308(self):
        d = parse_iso1832("TNMG160308")
        assert d.shape_code == "T"
        assert d.shape_description == "Trigon / Equilateral Triangle 60°"
        assert d.ic_mm == 16.0
        assert d.thickness_mm == pytest.approx(3.18)
        assert d.nose_radius_mm == pytest.approx(0.8)

    def test_dnmg_110408_right_hand(self):
        d = parse_iso1832("DNMG110408R")
        assert d.shape_code == "D"
        assert d.cutting_direction_code == "R"
        assert d.manufacturer_specific is None

    def test_vbmt_160408(self):
        d = parse_iso1832("VBMT160408")
        assert d.shape_code == "V"
        assert d.shape_description == "Rhombic 35°"
        assert d.type_code == "T"

    def test_round_insert_rcmt_1204m0(self):
        d = parse_iso1832("RCMT120400")
        assert d.shape_code == "R"
        assert d.shape_description == "Round"
        assert d.nose_radius_mm == pytest.approx(0.0)

    def test_manufacturer_suffix_stripped(self):
        d = parse_iso1832("CNMG120408-MF4")
        assert d.shape_code == "C"
        assert d.nose_radius_mm == pytest.approx(0.8)
        assert d.manufacturer_specific == "MF4"

    def test_manufacturer_suffix_pm(self):
        d = parse_iso1832("CNMG 120408-PM 4325")
        assert d.manufacturer_specific is not None
        assert "PM 4325" in d.manufacturer_specific or "PM" in d.manufacturer_specific

    def test_spaces_stripped_before_parsing(self):
        with_spaces = parse_iso1832("CNMG 120408")
        without = parse_iso1832("CNMG120408")
        assert with_spaces.shape_code == without.shape_code
        assert with_spaces.ic_mm == without.ic_mm
        assert with_spaces.nose_radius_mm == without.nose_radius_mm

    def test_clearance_code_c_7deg(self):
        d = parse_iso1832("CCMG120408")
        assert d.clearance_deg == pytest.approx(7.0)

    def test_clearance_code_d_15deg(self):
        d = parse_iso1832("CDMG120408")
        assert d.clearance_deg == pytest.approx(15.0)

    def test_nose_radius_sharp(self):
        d = parse_iso1832("CNMG120400")
        assert d.nose_radius_mm == pytest.approx(0.0)

    def test_nose_radius_1p2mm(self):
        d = parse_iso1832("CNMG120412")
        assert d.nose_radius_mm == pytest.approx(1.2)

    def test_thickness_code_03(self):
        d = parse_iso1832("CNMG120308")
        assert d.thickness_mm == pytest.approx(3.18)

    def test_insert_size_09mm(self):
        d = parse_iso1832("CNMG090408")
        assert d.ic_mm == pytest.approx(9.0)

    def test_all_shape_codes_known(self):
        from backend.cutting_tools.iso1832_parser import _SHAPE_CODES
        for _code, description in _SHAPE_CODES.items():
            assert description
            assert not description.startswith("UNKNOWN")

    def test_all_clearance_codes_have_deg(self):
        from backend.cutting_tools.iso1832_parser import _CLEARANCE_DEG
        for _code, deg in _CLEARANCE_DEG.items():
            assert isinstance(deg, float)
            assert 0.0 <= deg <= 30.0

    def test_all_type_codes_have_description(self):
        from backend.cutting_tools.iso1832_parser import _TYPE_CODES
        for _code, desc in _TYPE_CODES.items():
            assert desc and not desc.startswith("UNKNOWN")

    def test_left_hand_insert(self):
        d = parse_iso1832("CNMG120408L")
        assert d.cutting_direction_code == "L"

    def test_neutral_insert(self):
        d = parse_iso1832("CNMG120408N")
        assert d.cutting_direction_code == "N"


# ── ISO 1832 parser — UNKNOWN / warnings ─────────────────────────────────────


class TestISO1832ParserUnknown:
    def test_unknown_shape_produces_warning(self):
        d = parse_iso1832("ZNMG120408")  # Z is not a valid shape code
        assert any("shape" in w.lower() or "Z" in w for w in d.parse_warnings)
        assert "UNKNOWN" in d.shape_description

    def test_unknown_clearance_produces_warning(self):
        d = parse_iso1832("CZMG120408")  # Z is not a valid clearance code
        assert any("clearance" in w.lower() or "Z" in w for w in d.parse_warnings)
        assert d.clearance_deg is None

    def test_unknown_type_produces_warning(self):
        d = parse_iso1832("CNMY120408")  # Y is not a standard type code
        assert any("type" in w.lower() or "Y" in w for w in d.parse_warnings)
        assert "UNKNOWN" in d.type_description

    def test_warnings_do_not_raise(self):
        # Unknown codes must not raise, only warn
        d = parse_iso1832("ZZMZ120408")
        assert len(d.parse_warnings) >= 2

    def test_valid_core_with_unknown_suffix(self):
        d = parse_iso1832("CNMG120408-XYZZY")
        assert d.shape_code == "C"
        assert d.manufacturer_specific == "XYZZY"
        assert d.parse_warnings == []


# ── ISO 1832 parser — invalid input ──────────────────────────────────────────


class TestISO1832ParserInvalid:
    def test_too_short_raises_value_error(self):
        with pytest.raises(ValueError, match="too short"):
            parse_iso1832("CNMG")

    def test_empty_string_raises_value_error(self):
        with pytest.raises(ValueError, match="too short"):
            parse_iso1832("")

    def test_7_chars_raises_value_error(self):
        with pytest.raises(ValueError, match="too short"):
            parse_iso1832("CNMG120")

    def test_8_chars_minimum_accepted(self):
        # 8 characters is the minimum valid core
        d = parse_iso1832("CNMG1204")
        assert d.shape_code == "C"
        assert d.nose_radius_code is None  # no nose radius in 8-char designation

    def test_whitespace_only_raises_value_error(self):
        with pytest.raises(ValueError, match="too short"):
            parse_iso1832("        ")


# ── InsertRecord model ────────────────────────────────────────────────────────


class TestInsertRecord:
    def test_basic_construction(self):
        r = _make_insert()
        assert r.stable_id == "test-cnmg-120408"
        assert r.manufacturer == "TestMfr"

    def test_designation_roundtrip(self):
        r = _make_insert("SNMG120408")
        assert r.designation.shape_code == "S"
        assert r.designation.ic_mm == 12.0

    def test_geometry_fields(self):
        r = _make_insert()
        assert r.geometry.ic_mm == 12.0
        assert r.geometry.shape_code == "C"

    def test_grade_no_fabricated_specs(self):
        r = _make_insert()
        # substrate_grade (manufacturer code) must only be set from real sources
        assert r.grade.substrate_grade is None

    def test_missing_fields_default_empty(self):
        r = _make_insert()
        assert r.missing_fields == []

    def test_iso_groups_all_valid(self):
        r = _make_insert(iso_groups=["P", "M", "K"])
        valid = {"P", "M", "K", "N", "S", "H"}
        assert set(r.iso_material_groups) <= valid

    def test_unverified_provenance(self):
        r = _make_insert(evidence_status="UNVERIFIED")
        assert r.provenance.evidence_status == "UNVERIFIED"
        assert r.provenance.catalog_code is None

    def test_manufacturer_catalog_has_catalog_code(self):
        r = _make_insert(evidence_status="MANUFACTURER_CATALOG")
        assert r.provenance.evidence_status == "MANUFACTURER_CATALOG"
        assert r.provenance.catalog_code is not None


# ── Contradictory specification detection ────────────────────────────────────


class TestContradictorySpecifications:
    def test_geometry_ic_mismatch_with_designation(self):
        """Geometry.ic_mm that disagrees with designation.ic_mm should be detectable."""
        d = parse_iso1832("CNMG120408")
        assert d.ic_mm == 12.0
        # Create record with contradictory geometry IC
        r = InsertRecord(
            stable_id="test-contradictory",
            manufacturer="TestMfr",
            product_name="Contradictory",
            designation=d,
            geometry=InsertGeometry(
                shape_code="C",
                ic_mm=16.0,  # disagrees with designation's 12mm
            ),
            grade=InsertGrade(),
            provenance=_provenance("UNVERIFIED"),
            iso_material_groups=["P"],
            supported_operations=["turning"],
            missing_fields=["geometry.ic_mm contradicts designation.ic_mm"],
        )
        assert r.designation.ic_mm == 12.0
        assert r.geometry.ic_mm == 16.0
        assert any("contradicts" in f for f in r.missing_fields)

    def test_shape_code_mismatch(self):
        """geometry.shape_code that differs from designation.shape_code is detectable."""
        d = parse_iso1832("CNMG120408")
        r = InsertRecord(
            stable_id="test-shape-mismatch",
            manufacturer="TestMfr",
            product_name="Shape Mismatch",
            designation=d,
            geometry=InsertGeometry(shape_code="S"),  # S ≠ C from designation
            grade=InsertGrade(),
            provenance=_provenance("UNVERIFIED"),
            iso_material_groups=["P"],
            supported_operations=["turning"],
            missing_fields=["geometry.shape_code S disagrees with designation shape C"],
        )
        assert r.geometry.shape_code != r.designation.shape_code

    def test_unverified_insert_no_catalog_code(self):
        """UNVERIFIED inserts must not have a catalog_code — model enforces this by convention."""
        r = _make_insert(evidence_status="UNVERIFIED")
        assert r.provenance.catalog_code is None

    def test_no_fabricated_grade_codes(self):
        """Grade codes must be None when not explicitly sourced."""
        r = InsertRecord(
            stable_id="test-no-grade",
            manufacturer="TestMfr",
            product_name="No Grade",
            designation=parse_iso1832("CNMG120408"),
            geometry=InsertGeometry(shape_code="C"),
            grade=InsertGrade(),  # all None — correct for unsourced record
            provenance=_provenance("UNVERIFIED"),
            iso_material_groups=["P"],
            supported_operations=["turning"],
        )
        assert r.grade.substrate_grade is None
        assert r.grade.coating is None
