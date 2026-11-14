"""P3-E: GD&T → Process Planning constraint tests.

Tests extract_gdt_process_constraints() and the new R-RT-GDT-007/008
route warnings added to RouteGenerator._gdt_route_warnings().

HARD RULES verified:
  - REVIEW_REQUIRED when confidence is AMBIGUOUS or INFERRED.
  - REVIEW_REQUIRED when datum is missing for datum-requiring characteristics.
  - REVIEW_REQUIRED for UNKNOWN or unsupported characteristics.
  - Provenance (FILE_EVIDENCE/DRAWING_TEXT/OCR/USER_CONFIRMED) is preserved.
  - AUTO_APPROVE=NO — no constraint carries an approval status.
  - FABRICATED_PROCESS_CAPABILITY=NO.
  - FABRICATED_DATUM=NO.

GDT_AUTO_APPROVE=NO
FABRICATED_GDT_PROCESS_CAPABILITY=NO
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.drawing_intelligence.gdt_process_constraints import (
    GdtConstraintType,
    GdtProcessConstraint,
    GdtProcessStatus,
    extract_gdt_process_constraints,
)
from backend.drawing_intelligence.requirements import (
    DatumReference,
    DatumReferenceFrame,
    DrawingRequirementSet,
    ExpandedFeatureControlFrame,
    GdtCharacteristic,
    GdtConfidence,
    GdtModifier,
    GeometricRequirement,
    RequirementExtractionStatus,
)


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def _drf(label: str = "A") -> DatumReferenceFrame:
    return DatumReferenceFrame(
        primary=DatumReference(label=label, precedence=1, modifier=GdtModifier.NONE),
    )


def _fcf(
    char: GdtCharacteristic,
    tol: str = "0.1",
    datum: DatumReferenceFrame | None = None,
) -> ExpandedFeatureControlFrame:
    return ExpandedFeatureControlFrame(
        characteristic=char,
        tolerance_value=Decimal(tol),
        tolerance_unit="mm",
        diameter_zone=False,
        datum_frame=datum,
    )


def _geom(
    req_id: str,
    char: GdtCharacteristic,
    tol: str = "0.1",
    feature_ref: str | None = "F-001",
    datum: DatumReferenceFrame | None = None,
) -> GeometricRequirement:
    return GeometricRequirement(req_id=req_id, feature_ref=feature_ref, fcf=_fcf(char, tol, datum))


def _req_set(*geom_reqs: GeometricRequirement) -> DrawingRequirementSet:
    return DrawingRequirementSet(
        source_id="SRC-TEST",
        drawing_number="DWG-TEST",
        revision="A",
        extraction_status=RequirementExtractionStatus.COMPLETE,
        dimensional=(),
        geometric=tuple(geom_reqs),
        surface_finish=(),
        threads=(),
        material=None,
        heat_treatment=(),
    )


# ---------------------------------------------------------------------------
# P3-E tests: GdtProcessConstraint domain
# ---------------------------------------------------------------------------


class TestGdtProcessConstraintConstruction:

    def test_valid_constraint_constructs(self):
        c = GdtProcessConstraint(
            constraint_id="GPC-001",
            req_id="REQ-001",
            characteristic=GdtCharacteristic.POSITION,
            constraint_type=GdtConstraintType.CAPABILITY_REVIEW,
            constraint_note="test",
            gdnt_status=GdtProcessStatus.VERIFIED,
            provenance="FILE_EVIDENCE",
            feature_ref="F-001",
        )
        assert c.gdnt_status == GdtProcessStatus.VERIFIED

    def test_empty_constraint_id_raises(self):
        with pytest.raises(ValueError, match="constraint_id"):
            GdtProcessConstraint(
                constraint_id="   ",
                req_id="REQ-001",
                characteristic=GdtCharacteristic.POSITION,
                constraint_type=GdtConstraintType.CAPABILITY_REVIEW,
                constraint_note="test",
                gdnt_status=GdtProcessStatus.VERIFIED,
                provenance="FILE_EVIDENCE",
                feature_ref=None,
            )

    def test_invalid_provenance_raises(self):
        with pytest.raises(ValueError, match="provenance"):
            GdtProcessConstraint(
                constraint_id="GPC-001",
                req_id="REQ-001",
                characteristic=GdtCharacteristic.POSITION,
                constraint_type=GdtConstraintType.CAPABILITY_REVIEW,
                constraint_note="test",
                gdnt_status=GdtProcessStatus.VERIFIED,
                provenance="INVENTED",
                feature_ref=None,
            )


# ---------------------------------------------------------------------------
# P3-E tests: extract_gdt_process_constraints
# ---------------------------------------------------------------------------


class TestVerifiedPositionConstraint:

    def test_position_with_datum_produces_capability_review(self):
        req = _geom("REQ-POS-001", GdtCharacteristic.POSITION, datum=_drf("A"))
        constraints = extract_gdt_process_constraints(_req_set(req))
        assert len(constraints) == 1
        c = constraints[0]
        assert c.characteristic == GdtCharacteristic.POSITION
        assert c.constraint_type == GdtConstraintType.CAPABILITY_REVIEW
        assert c.gdnt_status == GdtProcessStatus.VERIFIED

    def test_position_provenance_file_evidence_for_exact(self):
        req = _geom("REQ-POS-002", GdtCharacteristic.POSITION, datum=_drf("A"))
        constraints = extract_gdt_process_constraints(
            _req_set(req),
            {req.req_id: GdtConfidence.EXACT_STRUCTURED},
        )
        assert constraints[0].provenance == "FILE_EVIDENCE"

    def test_position_note_references_datum(self):
        req = _geom("REQ-POS-003", GdtCharacteristic.POSITION, datum=_drf("B"))
        constraints = extract_gdt_process_constraints(_req_set(req))
        assert "B" in constraints[0].constraint_note

    def test_position_auto_approve_not_in_note(self):
        req = _geom("REQ-POS-004", GdtCharacteristic.POSITION, datum=_drf("A"))
        constraints = extract_gdt_process_constraints(_req_set(req))
        # Must say AUTO_APPROVE=NO — not some approval-granting phrase
        assert "AUTO_APPROVE=NO" in constraints[0].constraint_note


class TestVerifiedPerpendicularityConstraint:

    def test_perpendicularity_with_datum_capability_review(self):
        req = _geom("REQ-PERP-001", GdtCharacteristic.PERPENDICULARITY, datum=_drf("A"))
        constraints = extract_gdt_process_constraints(_req_set(req))
        assert constraints[0].constraint_type == GdtConstraintType.CAPABILITY_REVIEW
        assert constraints[0].gdnt_status == GdtProcessStatus.VERIFIED

    def test_perpendicularity_note_mentions_grinding_or_boring(self):
        req = _geom("REQ-PERP-002", GdtCharacteristic.PERPENDICULARITY, datum=_drf("A"))
        constraints = extract_gdt_process_constraints(_req_set(req))
        note = constraints[0].constraint_note.lower()
        assert "grinding" in note or "boring" in note


class TestVerifiedParallelismConstraint:

    def test_parallelism_with_datum_produces_process_choice(self):
        req = _geom("REQ-PARA-001", GdtCharacteristic.PARALLELISM, datum=_drf("A"))
        constraints = extract_gdt_process_constraints(_req_set(req))
        assert len(constraints) == 1
        c = constraints[0]
        assert c.characteristic == GdtCharacteristic.PARALLELISM
        assert c.constraint_type == GdtConstraintType.PROCESS_CHOICE
        assert c.gdnt_status == GdtProcessStatus.VERIFIED

    def test_parallelism_note_mentions_grinding_or_milling(self):
        req = _geom("REQ-PARA-002", GdtCharacteristic.PARALLELISM, datum=_drf("A"))
        constraints = extract_gdt_process_constraints(_req_set(req))
        note = constraints[0].constraint_note.lower()
        assert "grinding" in note or "milling" in note

    def test_parallelism_auto_approve_no(self):
        req = _geom("REQ-PARA-003", GdtCharacteristic.PARALLELISM, datum=_drf("A"))
        constraints = extract_gdt_process_constraints(_req_set(req))
        assert "AUTO_APPROVE=NO" in constraints[0].constraint_note


class TestVerifiedFlatnessConstraint:

    def test_flatness_produces_inspection_required(self):
        req = _geom("REQ-FLAT-001", GdtCharacteristic.FLATNESS)
        constraints = extract_gdt_process_constraints(_req_set(req))
        assert len(constraints) == 1
        c = constraints[0]
        assert c.characteristic == GdtCharacteristic.FLATNESS
        assert c.constraint_type == GdtConstraintType.INSPECTION_REQUIRED
        assert c.gdnt_status == GdtProcessStatus.VERIFIED

    def test_flatness_note_mentions_inspection(self):
        req = _geom("REQ-FLAT-002", GdtCharacteristic.FLATNESS)
        constraints = extract_gdt_process_constraints(_req_set(req))
        note = constraints[0].constraint_note.lower()
        assert "inspection" in note or "plate" in note or "cmm" in note

    def test_flatness_no_datum_still_verified(self):
        # FLATNESS is a form tolerance — no datum required; still VERIFIED
        req = _geom("REQ-FLAT-003", GdtCharacteristic.FLATNESS, datum=None)
        constraints = extract_gdt_process_constraints(_req_set(req))
        assert constraints[0].gdnt_status == GdtProcessStatus.VERIFIED


class TestVerifiedRunoutConstraint:

    def test_circular_runout_with_datum_same_setup(self):
        req = _geom("REQ-RUNOUT-001", GdtCharacteristic.CIRCULAR_RUNOUT, datum=_drf("A"))
        constraints = extract_gdt_process_constraints(_req_set(req))
        assert constraints[0].constraint_type == GdtConstraintType.SAME_SETUP_REQUIRED
        assert constraints[0].gdnt_status == GdtProcessStatus.VERIFIED

    def test_total_runout_with_datum_same_setup(self):
        req = _geom("REQ-RUNOUT-002", GdtCharacteristic.TOTAL_RUNOUT, datum=_drf("A"))
        constraints = extract_gdt_process_constraints(_req_set(req))
        assert constraints[0].constraint_type == GdtConstraintType.SAME_SETUP_REQUIRED
        assert constraints[0].gdnt_status == GdtProcessStatus.VERIFIED

    def test_runout_note_mentions_chucking(self):
        req = _geom("REQ-RUNOUT-003", GdtCharacteristic.CIRCULAR_RUNOUT, datum=_drf("A"))
        constraints = extract_gdt_process_constraints(_req_set(req))
        assert "chucking" in constraints[0].constraint_note.lower()


class TestDatumLinkage:

    def test_position_missing_datum_review_required(self):
        req = _geom("REQ-POS-ND", GdtCharacteristic.POSITION, datum=None)
        constraints = extract_gdt_process_constraints(_req_set(req))
        assert constraints[0].gdnt_status == GdtProcessStatus.REVIEW_REQUIRED
        assert constraints[0].constraint_type == GdtConstraintType.REVIEW_REQUIRED

    def test_perpendicularity_missing_datum_review_required(self):
        req = _geom("REQ-PERP-ND", GdtCharacteristic.PERPENDICULARITY, datum=None)
        constraints = extract_gdt_process_constraints(_req_set(req))
        assert constraints[0].gdnt_status == GdtProcessStatus.REVIEW_REQUIRED

    def test_parallelism_missing_datum_review_required(self):
        req = _geom("REQ-PARA-ND", GdtCharacteristic.PARALLELISM, datum=None)
        constraints = extract_gdt_process_constraints(_req_set(req))
        assert constraints[0].gdnt_status == GdtProcessStatus.REVIEW_REQUIRED

    def test_runout_missing_datum_review_required(self):
        req = _geom("REQ-RO-ND", GdtCharacteristic.TOTAL_RUNOUT, datum=None)
        constraints = extract_gdt_process_constraints(_req_set(req))
        assert constraints[0].gdnt_status == GdtProcessStatus.REVIEW_REQUIRED

    def test_datum_label_preserved_in_constraint(self):
        req = _geom("REQ-POS-DL", GdtCharacteristic.POSITION, datum=_drf("C"))
        constraints = extract_gdt_process_constraints(_req_set(req))
        assert "C" in constraints[0].constraint_note


class TestOcrDerivedGdt:

    def test_inferred_confidence_produces_review_required(self):
        req = _geom("REQ-OCR-001", GdtCharacteristic.POSITION, datum=_drf("A"))
        constraints = extract_gdt_process_constraints(
            _req_set(req),
            {req.req_id: GdtConfidence.INFERRED},
        )
        assert constraints[0].gdnt_status == GdtProcessStatus.REVIEW_REQUIRED
        assert constraints[0].constraint_type == GdtConstraintType.REVIEW_REQUIRED

    def test_inferred_provenance_is_ocr(self):
        req = _geom("REQ-OCR-002", GdtCharacteristic.PERPENDICULARITY, datum=_drf("A"))
        constraints = extract_gdt_process_constraints(
            _req_set(req),
            {req.req_id: GdtConfidence.INFERRED},
        )
        assert constraints[0].provenance == "OCR"

    def test_ocr_derived_note_contains_review_required(self):
        req = _geom("REQ-OCR-003", GdtCharacteristic.FLATNESS)
        constraints = extract_gdt_process_constraints(
            _req_set(req),
            {req.req_id: GdtConfidence.INFERRED},
        )
        assert "REVIEW_REQUIRED" in constraints[0].constraint_note


class TestAmbiguousGdt:

    def test_ambiguous_confidence_produces_review_required(self):
        req = _geom("REQ-AMB-001", GdtCharacteristic.PARALLELISM, datum=_drf("A"))
        constraints = extract_gdt_process_constraints(
            _req_set(req),
            {req.req_id: GdtConfidence.AMBIGUOUS},
        )
        assert constraints[0].gdnt_status == GdtProcessStatus.REVIEW_REQUIRED

    def test_ambiguous_provenance_is_ocr(self):
        req = _geom("REQ-AMB-002", GdtCharacteristic.TOTAL_RUNOUT, datum=_drf("A"))
        constraints = extract_gdt_process_constraints(
            _req_set(req),
            {req.req_id: GdtConfidence.AMBIGUOUS},
        )
        assert constraints[0].provenance == "OCR"


class TestUnsupportedCharacteristic:

    def test_unknown_characteristic_produces_review_required(self):
        req = _geom("REQ-UNK-001", GdtCharacteristic.UNKNOWN)
        constraints = extract_gdt_process_constraints(_req_set(req))
        assert constraints[0].gdnt_status == GdtProcessStatus.REVIEW_REQUIRED
        assert constraints[0].constraint_type == GdtConstraintType.REVIEW_REQUIRED

    def test_unsupported_note_says_review_required(self):
        req = _geom("REQ-UNK-002", GdtCharacteristic.UNKNOWN)
        constraints = extract_gdt_process_constraints(_req_set(req))
        assert "REVIEW_REQUIRED" in constraints[0].constraint_note


class TestProvenancePropagation:

    def test_exact_structured_maps_to_file_evidence(self):
        req = _geom("REQ-PROV-001", GdtCharacteristic.FLATNESS)
        constraints = extract_gdt_process_constraints(
            _req_set(req),
            {req.req_id: GdtConfidence.EXACT_STRUCTURED},
        )
        assert constraints[0].provenance == "FILE_EVIDENCE"

    def test_rule_parsed_maps_to_file_evidence(self):
        req = _geom("REQ-PROV-002", GdtCharacteristic.FLATNESS)
        constraints = extract_gdt_process_constraints(
            _req_set(req),
            {req.req_id: GdtConfidence.RULE_PARSED},
        )
        assert constraints[0].provenance == "FILE_EVIDENCE"

    def test_geometry_matched_maps_to_drawing_text(self):
        req = _geom("REQ-PROV-003", GdtCharacteristic.FLATNESS)
        constraints = extract_gdt_process_constraints(
            _req_set(req),
            {req.req_id: GdtConfidence.GEOMETRY_MATCHED},
        )
        assert constraints[0].provenance == "DRAWING_TEXT"

    def test_pattern_matched_maps_to_drawing_text(self):
        req = _geom("REQ-PROV-004", GdtCharacteristic.FLATNESS)
        constraints = extract_gdt_process_constraints(
            _req_set(req),
            {req.req_id: GdtConfidence.PATTERN_MATCHED},
        )
        assert constraints[0].provenance == "DRAWING_TEXT"

    def test_user_confirmed_maps_to_user_confirmed(self):
        req = _geom("REQ-PROV-005", GdtCharacteristic.FLATNESS)
        constraints = extract_gdt_process_constraints(
            _req_set(req),
            {req.req_id: GdtConfidence.USER_CONFIRMED},
        )
        assert constraints[0].provenance == "USER_CONFIRMED"

    def test_absent_confidence_defaults_to_file_evidence(self):
        req = _geom("REQ-PROV-006", GdtCharacteristic.FLATNESS)
        constraints = extract_gdt_process_constraints(_req_set(req))
        assert constraints[0].provenance == "FILE_EVIDENCE"

    def test_feature_ref_preserved(self):
        req = _geom("REQ-PROV-007", GdtCharacteristic.FLATNESS, feature_ref="F-XYZ")
        constraints = extract_gdt_process_constraints(_req_set(req))
        assert constraints[0].feature_ref == "F-XYZ"


class TestNoAutomaticApproval:

    def test_no_constraint_has_approved_status(self):
        reqs = [
            _geom("REQ-NA-001", GdtCharacteristic.POSITION, datum=_drf("A")),
            _geom("REQ-NA-002", GdtCharacteristic.FLATNESS),
            _geom("REQ-NA-003", GdtCharacteristic.TOTAL_RUNOUT, datum=_drf("A")),
            _geom("REQ-NA-004", GdtCharacteristic.PARALLELISM, datum=_drf("B")),
        ]
        constraints = extract_gdt_process_constraints(_req_set(*reqs))
        # No status value other than VERIFIED or REVIEW_REQUIRED is legal —
        # this explicitly confirms no APPROVED status exists.
        for c in constraints:
            assert c.gdnt_status in (GdtProcessStatus.VERIFIED, GdtProcessStatus.REVIEW_REQUIRED)

    def test_multiple_requirements_produce_separate_constraints(self):
        reqs = [
            _geom("REQ-M-001", GdtCharacteristic.POSITION, datum=_drf("A")),
            _geom("REQ-M-002", GdtCharacteristic.FLATNESS),
        ]
        constraints = extract_gdt_process_constraints(_req_set(*reqs))
        assert len(constraints) == 2

    def test_empty_req_set_produces_no_constraints(self):
        constraints = extract_gdt_process_constraints(_req_set())
        assert constraints == ()


# ---------------------------------------------------------------------------
# P3-E tests: R-RT-GDT-007 (PARALLELISM) and R-RT-GDT-008 (FLATNESS)
# in RouteGenerator._gdt_route_warnings
# ---------------------------------------------------------------------------


class TestRRTGDT007Parallelism:
    """R-RT-GDT-007: PARALLELISM → surface grinding / milling note in route."""

    def _recognized_hole(self, feature_id: str = "F-001"):
        from unittest.mock import MagicMock
        from backend.domain.feature import Feature
        from backend.drawing_intelligence.feature_recognition import RecognizedFeature
        from backend.domain.enums import FeatureType
        feat = MagicMock(spec=Feature)
        feat.feature_id = feature_id
        feat.feature_type = FeatureType.HOLE
        rf = MagicMock(spec=RecognizedFeature)
        rf.feature = feat
        rf.source_req_ids = (feature_id,)
        return rf

    def test_parallelism_generates_r007_warning(self):
        from backend.drawing_intelligence.route_generator import generate_routes
        geom = _geom("REQ-PARA-R", GdtCharacteristic.PARALLELISM, datum=_drf("A"),
                     feature_ref="F-001")
        req_set = _req_set(geom)
        result = generate_routes(self._recognized_hole(), req_set)
        assert "R-RT-GDT-007" in " ".join(result.warnings)

    def test_parallelism_warning_mentions_grinding_or_milling(self):
        from backend.drawing_intelligence.route_generator import generate_routes
        geom = _geom("REQ-PARA-R2", GdtCharacteristic.PARALLELISM, datum=_drf("A"),
                     feature_ref="F-001")
        req_set = _req_set(geom)
        result = generate_routes(self._recognized_hole(), req_set)
        combined = " ".join(result.warnings).lower()
        assert "grinding" in combined or "milling" in combined

    def test_no_parallelism_no_r007_warning(self):
        from backend.drawing_intelligence.route_generator import generate_routes
        geom = _geom("REQ-FLAT-NR", GdtCharacteristic.FLATNESS, feature_ref="F-001")
        req_set = _req_set(geom)
        result = generate_routes(self._recognized_hole(), req_set)
        assert "R-RT-GDT-007" not in " ".join(result.warnings)


class TestRRTGDT008Flatness:
    """R-RT-GDT-008: FLATNESS → inspection / grinding note in route."""

    def _recognized_hole(self, feature_id: str = "F-001"):
        from unittest.mock import MagicMock
        from backend.domain.feature import Feature
        from backend.drawing_intelligence.feature_recognition import RecognizedFeature
        from backend.domain.enums import FeatureType
        feat = MagicMock(spec=Feature)
        feat.feature_id = feature_id
        feat.feature_type = FeatureType.HOLE
        rf = MagicMock(spec=RecognizedFeature)
        rf.feature = feat
        rf.source_req_ids = (feature_id,)
        return rf

    def test_flatness_generates_r008_warning(self):
        from backend.drawing_intelligence.route_generator import generate_routes
        geom = _geom("REQ-FLAT-R", GdtCharacteristic.FLATNESS, feature_ref="F-001")
        req_set = _req_set(geom)
        result = generate_routes(self._recognized_hole(), req_set)
        assert "R-RT-GDT-008" in " ".join(result.warnings)

    def test_flatness_warning_mentions_inspection_or_grinding(self):
        from backend.drawing_intelligence.route_generator import generate_routes
        geom = _geom("REQ-FLAT-R2", GdtCharacteristic.FLATNESS, feature_ref="F-001")
        req_set = _req_set(geom)
        result = generate_routes(self._recognized_hole(), req_set)
        combined = " ".join(result.warnings).lower()
        assert "inspection" in combined or "grinding" in combined

    def test_no_flatness_no_r008_warning(self):
        from backend.drawing_intelligence.route_generator import generate_routes
        geom = _geom("REQ-PERP-NR", GdtCharacteristic.PERPENDICULARITY, datum=_drf("A"),
                     feature_ref="F-001")
        req_set = _req_set(geom)
        result = generate_routes(self._recognized_hole(), req_set)
        assert "R-RT-GDT-008" not in " ".join(result.warnings)
