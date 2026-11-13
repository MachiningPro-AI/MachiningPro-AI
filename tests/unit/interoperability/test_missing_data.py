"""Unit tests for backend.interoperability.missing_data (P0).

Coverage:
  - EngineeringField construction (unknown, known, not_applicable)
  - apply_user_confirmation: sets USER_CONFIRMED, records history
  - apply_user_confirmation: CONFLICT when file value differs from user value
  - apply_user_confirmation: blank input rejected — stays UNKNOWN
  - is_resolved / is_blocking properties
  - apply_user_confirmations: multi-field confirmation
  - apply_user_confirmations: phase changes to AFTER_USER_CONFIRMATION
  - Provenance tags: source is never FILE_EVIDENCE after user confirms
  - original_extracted_value is never overwritten
  - UNKNOWN remains UNKNOWN when no confirmation provided
  - _compute_readiness: BLOCKED_FOR_PROCESS_PLANNING when material unknown
  - _compute_readiness: READY_FOR_PROCESS_PLANNING when unit+material resolved
  - _compute_readiness: BLOCKED_FOR_CUTTING_DATA when tolerance unknown
  - Downstream unblocking after user confirms material
  - Negative: blank value leaves field UNKNOWN
  - Negative: unrecognized field name in confirmations is silently ignored
"""

from __future__ import annotations

import pytest

from backend.interoperability.missing_data import (
    EngineeringField,
    EngineeringFieldSource,
    EngineeringFieldStatus,
    FieldRequirementTier,
    MissingDataAnalysis,
    ReadinessState,
    _compute_readiness,
    apply_user_confirmations,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_analysis(
    *,
    unit: str | None = None,
    material: str | None = None,
    tolerance: str | None = None,
    surface_finish: str | None = None,
    has_geometry: bool = True,
    has_topology: bool = False,
    document_format: str = "DXF",
) -> MissingDataAnalysis:
    """Build a minimal MissingDataAnalysis for testing."""
    from datetime import UTC, datetime

    def _field(name: str, value: str | None, source: EngineeringFieldSource | None = None) -> EngineeringField:
        if value is None:
            return EngineeringField.unknown(name)
        return EngineeringField.known(
            name, value, source or EngineeringFieldSource.FILE_METADATA, confidence=0.9
        )

    fields: dict[str, EngineeringField] = {
        "unit": _field("unit", unit),
        "material": _field("material", material),
        "tolerance_general": _field("tolerance_general", tolerance),
        "surface_finish": _field("surface_finish", surface_finish),
        "hole_depth": EngineeringField.unknown("hole_depth"),
        "topology": EngineeringField.not_applicable("topology"),
    }

    readiness = _compute_readiness(fields, document_format, has_geometry, has_topology)

    known = [n for n, f in fields.items() if f.is_resolved]
    unknown = [n for n, f in fields.items() if f.is_blocking]
    required_missing = [
        n for n in unknown
        if n in ("unit", "material", "tolerance_general")
    ]
    optional_missing = [n for n in unknown if n not in required_missing]
    blocking = [s for s, r in readiness.items() if "BLOCKED" in r.value]
    can_resolve = any(n in ("unit", "material", "tolerance_general", "surface_finish") for n in required_missing)

    return MissingDataAnalysis(
        import_id="test-import-001",
        document_format=document_format,
        source_file_name="test.dxf",
        fields=fields,
        readiness_states=readiness,
        known_field_names=known,
        unknown_field_names=unknown,
        required_missing_field_names=required_missing,
        optional_missing_field_names=optional_missing,
        geometry_ok=has_geometry,
        geometry_note="Test geometry note",
        blocking_stage_names=blocking,
        can_proceed_with_user_input=can_resolve,
        phase="RAW_FILE",
        analyzed_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# EngineeringField construction
# ---------------------------------------------------------------------------

class TestEngineeringFieldConstruction:
    def test_unknown_has_none_value(self):
        f = EngineeringField.unknown("material")
        assert f.value is None
        assert f.status == EngineeringFieldStatus.UNKNOWN
        assert f.source is None
        assert not f.confirmed_by_user
        assert f.original_extracted_value is None

    def test_known_carries_value_and_source(self):
        f = EngineeringField.known(
            "unit", "Millimeters", EngineeringFieldSource.FILE_METADATA, confidence=0.95
        )
        assert f.value == "Millimeters"
        assert f.status == EngineeringFieldStatus.KNOWN
        assert f.source == EngineeringFieldSource.FILE_METADATA
        assert f.confidence == pytest.approx(0.95)
        assert f.original_extracted_value == "Millimeters"
        assert not f.confirmed_by_user

    def test_not_applicable_status(self):
        f = EngineeringField.not_applicable("topology")
        assert f.status == EngineeringFieldStatus.NOT_APPLICABLE
        assert f.value is None
        assert f.is_resolved  # NOT_APPLICABLE counts as resolved

    def test_is_blocking_only_for_unknown(self):
        f_unknown = EngineeringField.unknown("material")
        f_known = EngineeringField.known("material", "C45", EngineeringFieldSource.FILE_METADATA)
        f_na = EngineeringField.not_applicable("topology")
        assert f_unknown.is_blocking
        assert not f_known.is_blocking
        assert not f_na.is_blocking

    def test_is_resolved_states(self):
        assert not EngineeringField.unknown("x").is_resolved
        assert EngineeringField.known("x", "v", EngineeringFieldSource.FILE_METADATA).is_resolved
        assert EngineeringField.not_applicable("x").is_resolved


# ---------------------------------------------------------------------------
# User confirmation
# ---------------------------------------------------------------------------

class TestApplyUserConfirmation:
    def test_unknown_becomes_user_confirmed(self):
        f = EngineeringField.unknown("material")
        updated = f.apply_user_confirmation("42CrMo4", library_id="P-42CrMo4")
        assert updated.status == EngineeringFieldStatus.USER_CONFIRMED
        assert updated.value == "42CrMo4"
        assert updated.source == EngineeringFieldSource.USER_CONFIRMED
        assert updated.confirmed_by_user
        assert updated.library_resolved_id == "P-42CrMo4"
        assert updated.confidence == pytest.approx(1.0)

    def test_original_extracted_value_preserved(self):
        f = EngineeringField.known(
            "material", "C45", EngineeringFieldSource.FILE_METADATA, confidence=0.8
        )
        updated = f.apply_user_confirmation("42CrMo4")
        # original_extracted_value must NOT change
        assert updated.original_extracted_value == "C45"
        # but new value is user's value
        assert updated.value == "42CrMo4"

    def test_conflict_when_file_and_user_differ(self):
        f = EngineeringField.known(
            "material", "C45", EngineeringFieldSource.FILE_METADATA, confidence=0.8
        )
        updated = f.apply_user_confirmation("42CrMo4")
        assert updated.status == EngineeringFieldStatus.CONFLICT
        assert updated.value == "42CrMo4"
        assert updated.original_extracted_value == "C45"

    def test_no_conflict_when_values_match(self):
        f = EngineeringField.known(
            "material", "42CrMo4", EngineeringFieldSource.FILE_METADATA, confidence=0.8
        )
        updated = f.apply_user_confirmation("42CrMo4")
        assert updated.status == EngineeringFieldStatus.USER_CONFIRMED

    def test_history_recorded(self):
        f = EngineeringField.unknown("material")
        updated = f.apply_user_confirmation("S355JR")
        assert len(updated.history) == 1
        change = updated.history[0]
        assert change.previous_status == EngineeringFieldStatus.UNKNOWN
        assert change.previous_value is None
        assert change.new_value == "S355JR"
        assert change.changed_by == "user"

    def test_original_field_not_mutated(self):
        f = EngineeringField.unknown("material")
        _ = f.apply_user_confirmation("42CrMo4")
        # original must be unchanged
        assert f.status == EngineeringFieldStatus.UNKNOWN
        assert f.value is None

    def test_blank_rejection_via_apply_user_confirmations(self):
        analysis = _make_analysis(unit=None, material=None)
        updated = apply_user_confirmations(analysis, {"material": ""})
        # blank must remain UNKNOWN
        assert updated.fields["material"].status == EngineeringFieldStatus.UNKNOWN
        assert updated.fields["material"].value is None

    def test_whitespace_only_rejected(self):
        analysis = _make_analysis()
        updated = apply_user_confirmations(analysis, {"material": "   "})
        assert updated.fields["material"].status == EngineeringFieldStatus.UNKNOWN


# ---------------------------------------------------------------------------
# apply_user_confirmations (multi-field)
# ---------------------------------------------------------------------------

class TestApplyUserConfirmations:
    def test_phase_changes_to_after_confirmation(self):
        analysis = _make_analysis(unit=None, material=None)
        updated = apply_user_confirmations(analysis, {"material": "42CrMo4"})
        assert updated.phase == "AFTER_USER_CONFIRMATION"

    def test_multiple_fields_confirmed(self):
        analysis = _make_analysis(unit=None, material=None)
        updated = apply_user_confirmations(
            analysis,
            {"unit": "mm", "material": "42CrMo4"},
        )
        assert updated.fields["unit"].status == EngineeringFieldStatus.USER_CONFIRMED
        assert updated.fields["material"].status == EngineeringFieldStatus.USER_CONFIRMED

    def test_dict_form_with_library_id(self):
        analysis = _make_analysis(material=None)
        updated = apply_user_confirmations(
            analysis,
            {"material": {"value": "C45", "library_id": "P-C45"}},
        )
        f = updated.fields["material"]
        assert f.status == EngineeringFieldStatus.USER_CONFIRMED
        assert f.library_resolved_id == "P-C45"

    def test_unknown_field_name_silently_ignored(self):
        analysis = _make_analysis(material=None)
        updated = apply_user_confirmations(
            analysis,
            {"does_not_exist": "some_value"},
        )
        # No error, existing fields unchanged
        assert updated.fields["material"].status == EngineeringFieldStatus.UNKNOWN

    def test_original_analysis_not_mutated(self):
        analysis = _make_analysis(material=None)
        apply_user_confirmations(analysis, {"material": "C45"})
        assert analysis.fields["material"].status == EngineeringFieldStatus.UNKNOWN

    def test_user_confirmed_never_changes_to_file_source(self):
        analysis = _make_analysis(material=None)
        updated = apply_user_confirmations(analysis, {"material": "42CrMo4"})
        f = updated.fields["material"]
        assert f.source == EngineeringFieldSource.USER_CONFIRMED
        assert f.confirmed_by_user is True


# ---------------------------------------------------------------------------
# Readiness computation
# ---------------------------------------------------------------------------

class TestComputeReadiness:
    def test_blocked_when_material_unknown(self):
        fields = {
            "unit": EngineeringField.known("unit", "mm", EngineeringFieldSource.FILE_METADATA),
            "material": EngineeringField.unknown("material"),
            "tolerance_general": EngineeringField.unknown("tolerance_general"),
            "surface_finish": EngineeringField.unknown("surface_finish"),
            "hole_depth": EngineeringField.unknown("hole_depth"),
            "topology": EngineeringField.not_applicable("topology"),
        }
        states = _compute_readiness(fields, "DXF", has_geometry=True, has_topology=False)
        assert states["PROCESS_PLANNING"] == ReadinessState.BLOCKED_FOR_PROCESS_PLANNING
        assert states["CUTTING_DATA"] == ReadinessState.BLOCKED_FOR_CUTTING_DATA

    def test_blocked_when_unit_unknown(self):
        fields = {
            "unit": EngineeringField.unknown("unit"),
            "material": EngineeringField.known("material", "C45", EngineeringFieldSource.FILE_METADATA),
            "tolerance_general": EngineeringField.unknown("tolerance_general"),
            "surface_finish": EngineeringField.unknown("surface_finish"),
            "hole_depth": EngineeringField.unknown("hole_depth"),
            "topology": EngineeringField.not_applicable("topology"),
        }
        states = _compute_readiness(fields, "DXF", has_geometry=True, has_topology=False)
        assert states["PROCESS_PLANNING"] == ReadinessState.BLOCKED_FOR_PROCESS_PLANNING

    def test_ready_when_unit_and_material_known(self):
        fields = {
            "unit": EngineeringField.known("unit", "mm", EngineeringFieldSource.FILE_METADATA),
            "material": EngineeringField.known("material", "C45", EngineeringFieldSource.FILE_METADATA),
            "tolerance_general": EngineeringField.unknown("tolerance_general"),
            "surface_finish": EngineeringField.unknown("surface_finish"),
            "hole_depth": EngineeringField.unknown("hole_depth"),
            "topology": EngineeringField.not_applicable("topology"),
        }
        states = _compute_readiness(fields, "DXF", has_geometry=True, has_topology=False)
        assert states["PROCESS_PLANNING"] == ReadinessState.READY_FOR_PROCESS_PLANNING
        # still blocked for cutting data (tolerance missing)
        assert states["CUTTING_DATA"] == ReadinessState.BLOCKED_FOR_CUTTING_DATA

    def test_geometry_blocked_when_no_geometry(self):
        fields = {
            "unit": EngineeringField.unknown("unit"),
            "material": EngineeringField.unknown("material"),
            "tolerance_general": EngineeringField.unknown("tolerance_general"),
            "surface_finish": EngineeringField.unknown("surface_finish"),
            "hole_depth": EngineeringField.unknown("hole_depth"),
            "topology": EngineeringField.not_applicable("topology"),
        }
        states = _compute_readiness(fields, "DXF", has_geometry=False, has_topology=False)
        assert states["GEOMETRY"] != ReadinessState.READY_FOR_GEOMETRY_ANALYSIS

    def test_iges_blocked_for_cam_without_topology(self):
        fields = {
            "unit": EngineeringField.known("unit", "mm", EngineeringFieldSource.FILE_METADATA),
            "material": EngineeringField.known("material", "C45", EngineeringFieldSource.FILE_METADATA),
            "tolerance_general": EngineeringField.known("tolerance_general", "ISO 2768-m", EngineeringFieldSource.DRAWING_TEXT),
            "surface_finish": EngineeringField.known("surface_finish", "Ra 1.6", EngineeringFieldSource.DRAWING_TEXT),
            "hole_depth": EngineeringField.not_applicable("hole_depth"),
            "topology": EngineeringField.unknown("topology"),
        }
        states = _compute_readiness(fields, "IGES", has_geometry=True, has_topology=False)
        assert states["CAM"] == ReadinessState.BLOCKED_FOR_CAM

    def test_unblocked_after_user_confirmation(self):
        analysis = _make_analysis(unit="mm", material=None, tolerance=None)
        # Before: PROCESS_PLANNING blocked
        assert "PROCESS_PLANNING" in analysis.blocking_stage_names

        updated = apply_user_confirmations(analysis, {"material": "42CrMo4"})
        # After: PROCESS_PLANNING should be unblocked
        pp_state = updated.readiness_states.get("PROCESS_PLANNING")
        assert pp_state == ReadinessState.READY_FOR_PROCESS_PLANNING
        assert "PROCESS_PLANNING" not in updated.blocking_stage_names

    def test_user_confirmed_field_resolves_blocking(self):
        analysis = _make_analysis(unit=None, material=None)
        updated = apply_user_confirmations(analysis, {"unit": "mm", "material": "S355JR"})
        assert updated.fields["unit"].status == EngineeringFieldStatus.USER_CONFIRMED
        assert updated.fields["material"].status == EngineeringFieldStatus.USER_CONFIRMED
        assert "PROCESS_PLANNING" not in updated.blocking_stage_names


# ---------------------------------------------------------------------------
# Provenance invariants
# ---------------------------------------------------------------------------

class TestProvenanceInvariants:
    def test_user_confirmed_source_never_file_metadata(self):
        f = EngineeringField.unknown("material")
        updated = f.apply_user_confirmation("42CrMo4")
        assert updated.source != EngineeringFieldSource.FILE_METADATA
        assert updated.source == EngineeringFieldSource.USER_CONFIRMED

    def test_user_confirmed_source_never_drawing_text(self):
        f = EngineeringField.unknown("tolerance_general")
        updated = f.apply_user_confirmation("ISO 2768-m")
        assert updated.source != EngineeringFieldSource.DRAWING_TEXT

    def test_user_confirmed_source_never_cad_geometry(self):
        f = EngineeringField.unknown("topology")
        updated = f.apply_user_confirmation("present")
        assert updated.source != EngineeringFieldSource.CAD_GEOMETRY

    def test_conflict_records_both_values(self):
        f = EngineeringField.known(
            "material", "C45", EngineeringFieldSource.FILE_METADATA, confidence=0.8
        )
        updated = f.apply_user_confirmation("42CrMo4")
        assert updated.status == EngineeringFieldStatus.CONFLICT
        assert updated.original_extracted_value == "C45"  # file value preserved
        assert updated.value == "42CrMo4"               # user value is active value

    def test_no_fabricated_defaults_in_analysis(self):
        analysis = _make_analysis(unit=None, material=None, tolerance=None)
        for fname in ("unit", "material", "tolerance_general"):
            f = analysis.fields[fname]
            assert f.value is None, f"Field {fname} should have None value, got {f.value!r}"
            assert f.status == EngineeringFieldStatus.UNKNOWN

    def test_unknown_stays_unknown_without_confirmation(self):
        analysis = _make_analysis(unit=None, material=None)
        updated = apply_user_confirmations(analysis, {})
        assert updated.fields["material"].status == EngineeringFieldStatus.UNKNOWN
        assert updated.fields["unit"].status == EngineeringFieldStatus.UNKNOWN

    def test_as_dict_reports_correct_status_strings(self):
        f = EngineeringField.unknown("material")
        d = f.as_dict()
        assert d["status"] == "UNKNOWN"
        assert d["value"] is None
        assert d["confirmed_by_user"] is False
