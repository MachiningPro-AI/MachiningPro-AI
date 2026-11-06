"""Tests for ToolHolderRecord, HolderInterface and HolderCapacity models.

Covers:
- All 9 HolderInterface enum values
- HolderCapacity dimensional validation
- ToolHolderRecord construction and field access
- Provenance / evidence_status semantics
- Invalid dimension detection
- Missing-field propagation
"""
import pytest

from backend.cutting_tools import (
    HolderCapacity,
    HolderInterface,
    HolderSourceMetadata,
    ToolHolderRecord,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

def _er32_holder(
    min_shank: float = 1.0,
    max_shank: float = 20.0,
    reach: float | None = 80.0,
    coolant: bool | None = True,
    evidence_status: str = "MANUFACTURER_CATALOG",
) -> ToolHolderRecord:
    return ToolHolderRecord(
        stable_id="test-er32-collet",
        manufacturer="TestMfr",
        product_name="Test ER32 Collet Chuck",
        holder_type=HolderInterface.ER_COLLET,
        spindle_interface="BT40",
        capacity=HolderCapacity(
            min_shank_mm=min_shank,
            max_shank_mm=max_shank,
            max_tool_reach_mm=reach,
            gauge_length_mm=63.0,
            max_runout_mm=0.003,
        ),
        supports_coolant=coolant,
        compatible_operations=["drilling", "milling", "reaming"],
        provenance=HolderSourceMetadata(
            source_title="Test",
            source_authority="Test",
            evidence_status=evidence_status,
            catalog_code="TEST-ER32" if evidence_status == "MANUFACTURER_CATALOG" else None,
        ),
    )


def _turning_holder(
    insert_shape: str | None = "C",
    insert_ic: float | None = 12.0,
    insert_hand: str | None = "R",
) -> ToolHolderRecord:
    return ToolHolderRecord(
        stable_id="test-turning-holder",
        manufacturer="TestMfr",
        product_name="Test Turning Toolholder",
        holder_type=HolderInterface.TURNING_TOOLHOLDER,
        capacity=HolderCapacity(min_shank_mm=0.0, max_shank_mm=0.0),
        supports_coolant=True,
        insert_shape_code=insert_shape,
        insert_ic_mm=insert_ic,
        insert_hand=insert_hand,
        compatible_operations=["turning"],
        provenance=HolderSourceMetadata(
            source_title="Test",
            source_authority="Test",
            evidence_status="MANUFACTURER_CATALOG",
            catalog_code="TEST-TURN",
        ),
    )


# ── HolderInterface enum ──────────────────────────────────────────────────────


class TestHolderInterface:
    def test_all_nine_types_defined(self):
        expected = {
            "ER_COLLET", "HYDRAULIC_CHUCK", "SHRINK_FIT", "MILLING_CHUCK",
            "SIDE_LOCK", "FACE_MILL_HOLDER", "BORING_HOLDER",
            "TAPPING_CHUCK", "TURNING_TOOLHOLDER",
        }
        assert {h.value for h in HolderInterface} == expected

    def test_is_str_enum(self):
        assert isinstance(HolderInterface.ER_COLLET, str)
        assert HolderInterface.ER_COLLET == "ER_COLLET"

    def test_turning_toolholder_value(self):
        assert HolderInterface.TURNING_TOOLHOLDER == "TURNING_TOOLHOLDER"

    def test_tapping_chuck_value(self):
        assert HolderInterface.TAPPING_CHUCK == "TAPPING_CHUCK"


# ── HolderCapacity model ──────────────────────────────────────────────────────


class TestHolderCapacity:
    def test_basic_construction(self):
        c = HolderCapacity(min_shank_mm=3.0, max_shank_mm=20.0)
        assert c.min_shank_mm == 3.0
        assert c.max_shank_mm == 20.0

    def test_optional_fields_default_none(self):
        c = HolderCapacity(min_shank_mm=0.0, max_shank_mm=10.0)
        assert c.max_tool_reach_mm is None
        assert c.gauge_length_mm is None
        assert c.max_runout_mm is None

    def test_full_construction(self):
        c = HolderCapacity(
            min_shank_mm=1.0,
            max_shank_mm=20.0,
            max_tool_reach_mm=100.0,
            gauge_length_mm=63.0,
            max_runout_mm=0.003,
        )
        assert c.max_tool_reach_mm == 100.0
        assert c.gauge_length_mm == 63.0
        assert c.max_runout_mm == pytest.approx(0.003)

    def test_zero_range_allowed_for_insert_holders(self):
        # Turning toolholders hold inserts, not round shanks
        c = HolderCapacity(min_shank_mm=0.0, max_shank_mm=0.0)
        assert c.min_shank_mm == 0.0
        assert c.max_shank_mm == 0.0


# ── ToolHolderRecord model ────────────────────────────────────────────────────


class TestToolHolderRecord:
    def test_er_collet_construction(self):
        h = _er32_holder()
        assert h.holder_type == HolderInterface.ER_COLLET
        assert h.spindle_interface == "BT40"
        assert h.capacity.max_shank_mm == 20.0

    def test_turning_holder_insert_pocket(self):
        h = _turning_holder()
        assert h.insert_shape_code == "C"
        assert h.insert_ic_mm == 12.0
        assert h.insert_hand == "R"

    def test_insert_fields_default_none_for_collet(self):
        h = _er32_holder()
        assert h.insert_shape_code is None
        assert h.insert_ic_mm is None
        assert h.insert_hand is None

    def test_missing_fields_default_empty(self):
        h = _er32_holder()
        assert h.missing_fields == []

    def test_no_coolant_holder(self):
        h = _er32_holder(coolant=False)
        assert h.supports_coolant is False

    def test_unknown_coolant(self):
        h = _er32_holder(coolant=None)
        assert h.supports_coolant is None

    def test_stable_id_set(self):
        h = _er32_holder()
        assert h.stable_id == "test-er32-collet"

    def test_all_nine_holder_types_constructable(self):
        for ht in HolderInterface:
            h = ToolHolderRecord(
                stable_id=f"test-{ht.lower()}",
                manufacturer="TestMfr",
                product_name=f"Test {ht}",
                holder_type=ht,
                capacity=HolderCapacity(min_shank_mm=0.0, max_shank_mm=20.0),
                provenance=HolderSourceMetadata(
                    source_title="Test",
                    source_authority="Test",
                    evidence_status="UNVERIFIED",
                ),
            )
            assert h.holder_type == ht


# ── Provenance tests ──────────────────────────────────────────────────────────


class TestHolderProvenance:
    def test_manufacturer_catalog_has_catalog_code(self):
        h = _er32_holder(evidence_status="MANUFACTURER_CATALOG")
        assert h.provenance.evidence_status == "MANUFACTURER_CATALOG"
        assert h.provenance.catalog_code is not None

    def test_unverified_no_catalog_code(self):
        h = _er32_holder(evidence_status="UNVERIFIED")
        assert h.provenance.evidence_status == "UNVERIFIED"
        assert h.provenance.catalog_code is None

    def test_source_title_and_authority_required(self):
        # Cannot construct without both
        with pytest.raises(ValueError):
            HolderSourceMetadata(source_authority="Test", evidence_status="UNVERIFIED")

    def test_evidence_status_field_non_empty(self):
        h = _er32_holder()
        assert h.provenance.evidence_status


# ── Invalid dimension tests ───────────────────────────────────────────────────


class TestHolderInvalidDimensions:
    def test_min_gt_max_is_allowed_by_model(self):
        # Pydantic does not enforce min<=max; that is the caller's responsibility
        c = HolderCapacity(min_shank_mm=20.0, max_shank_mm=5.0)
        assert c.min_shank_mm > c.max_shank_mm

    def test_negative_runout_stored_as_is(self):
        # Model stores what it receives; validation is external
        c = HolderCapacity(min_shank_mm=1.0, max_shank_mm=10.0, max_runout_mm=-0.001)
        assert c.max_runout_mm == pytest.approx(-0.001)

    def test_missing_reach_is_none_not_zero(self):
        h = _er32_holder(reach=None)
        assert h.capacity.max_tool_reach_mm is None

    def test_missing_fields_list_records_gaps(self):
        h = ToolHolderRecord(
            stable_id="test-gaps",
            manufacturer="TestMfr",
            product_name="Test With Gaps",
            holder_type=HolderInterface.HYDRAULIC_CHUCK,
            capacity=HolderCapacity(min_shank_mm=3.0, max_shank_mm=20.0),
            provenance=HolderSourceMetadata(
                source_title="Test",
                source_authority="Test",
                evidence_status="UNVERIFIED",
            ),
            missing_fields=[
                "spindle_interface not published",
                "max_tool_reach_mm not published",
            ],
        )
        assert len(h.missing_fields) == 2
        assert "spindle_interface not published" in h.missing_fields
