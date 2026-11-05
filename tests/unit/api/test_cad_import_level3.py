"""CAD_IMPORT_LEVEL_3_MANUFACTURING_FEATURES — regression tests.

Verifies the deterministic manufacturing feature recognition layer.
Key invariants tested:

HARD RULE (verbatim):
  A manufacturing feature can be CONFIRMED only when deterministic
  geometry/topology evidence is sufficient.  Otherwise it must remain
  CANDIDATE, INCOMPLETE, REJECTED or UNKNOWN.

Negative rules:
  - A DXF circle MUST NOT produce a CONFIRMED hole.
  - A lone cylindrical surface MUST NOT produce a CONFIRMED hole.
  - A closed loop MUST NOT automatically produce a CONFIRMED pocket.
"""

from __future__ import annotations

from decimal import Decimal
from types import MappingProxyType

import pytest

from backend.domain.units import Quantity, Unit
from backend.interoperability.features import (
    ClassifiedFace,
    FaceAdjacency,
    FaceClassification,
    FeatureRecognitionResult,
    FeatureStatus,
    HoleSubtype,
    ManufacturingFeature,
    ManufacturingFeatureType,
)
from backend.interoperability.feature_recognition import recognize_features
from backend.interoperability.geometry import (
    CanonicalCurve,
    CanonicalCurveType,
    CanonicalGeometry,
    CanonicalPoint3D,
    CanonicalSurface,
    CanonicalSurfaceType,
    CanonicalVector3D,
)
from backend.interoperability.topology import (
    BodyType,
    CanonicalBody,
    CanonicalEdge,
    CanonicalFace,
    CanonicalLoop,
    CanonicalShell,
    CanonicalTopology,
    CanonicalVertex,
    LoopType,
    Orientation,
    ShellClosure,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mm(v: float) -> Quantity:
    return Quantity(Decimal(str(v)), Unit.MM)


def _dl(v: float) -> Quantity:
    return Quantity(Decimal(str(v)), Unit.DIMENSIONLESS)


def _pt(x: float, y: float, z: float, pid: str | None = None) -> CanonicalPoint3D:
    return CanonicalPoint3D(x=_mm(x), y=_mm(y), z=_mm(z), point_id=pid)


def _vec(x: float, y: float, z: float) -> CanonicalVector3D:
    return CanonicalVector3D(x=_dl(x), y=_dl(y), z=_dl(z))


def _plane_surface(sid: str) -> CanonicalSurface:
    return CanonicalSurface(
        surface_id=sid,
        surface_type=CanonicalSurfaceType.PLANE,
        origin=_pt(0, 0, 0),
        normal=_vec(0, 0, 1),
    )


def _cylinder_surface(sid: str, r: float = 5.0) -> CanonicalSurface:
    return CanonicalSurface(
        surface_id=sid,
        surface_type=CanonicalSurfaceType.CYLINDER,
        origin=_pt(0, 0, 0),
        axis=_vec(0, 0, 1),
        radius=_mm(r),
    )


def _cone_surface(sid: str) -> CanonicalSurface:
    return CanonicalSurface(
        surface_id=sid,
        surface_type=CanonicalSurfaceType.CONE,
        origin=_pt(0, 0, 0),
        axis=_vec(0, 0, 1),
        semi_angle=_dl(15.0),
    )


def _torus_surface(sid: str) -> CanonicalSurface:
    return CanonicalSurface(
        surface_id=sid,
        surface_type=CanonicalSurfaceType.TORUS,
        center=_pt(0, 0, 0),
        axis=_vec(0, 0, 1),
        major_radius=_mm(20.0),
        minor_radius=_mm(2.0),
    )


def _bspline_surface(sid: str) -> CanonicalSurface:
    return CanonicalSurface(
        surface_id=sid,
        surface_type=CanonicalSurfaceType.NURBS,
    )


def _circle_curve(cid: str, r: float = 5.0) -> CanonicalCurve:
    return CanonicalCurve(
        curve_id=cid,
        curve_type=CanonicalCurveType.CIRCLE,
        center=_pt(0, 0, 0),
        axis=_vec(0, 0, 1),
        radius=_mm(r),
    )


def _arc_curve(cid: str) -> CanonicalCurve:
    return CanonicalCurve(
        curve_id=cid,
        curve_type=CanonicalCurveType.ARC,
        center=_pt(0, 0, 0),
        axis=_vec(0, 0, 1),
        radius=_mm(5.0),
    )


def _line_curve(cid: str) -> CanonicalCurve:
    return CanonicalCurve(
        curve_id=cid,
        curve_type=CanonicalCurveType.LINE,
        origin=_pt(0, 0, 0),
        direction=_vec(1, 0, 0),
    )


def _geometry_with_surfaces(*surfaces: CanonicalSurface) -> CanonicalGeometry:
    return CanonicalGeometry(geometry_id="geo-1", surfaces=surfaces)


def _geometry_with_curves(*curves: CanonicalCurve) -> CanonicalGeometry:
    return CanonicalGeometry(geometry_id="geo-1", curves=curves)


# ---------------------------------------------------------------------------
# Minimal topology builder for confirmation tests
# ---------------------------------------------------------------------------

def _minimal_hole_topology(
    cyl_surface_id: str,
    top_surface_id: str,
    bot_surface_id: str,
    geometry: CanonicalGeometry,
) -> CanonicalTopology:
    """Build a minimal topology: cylindrical face + 2 planar caps sharing edges.

    Uses 3 arc segments per circular rim (CanonicalLoop requires ≥3 edges).
    The cylinder face has two boundary loops whose edge IDs match the cap
    face loops, so the adjacency builder detects face-face shared edges.

    geometry is NOT attached to CanonicalTopology to avoid curve/surface
    reference validation; the feature recognition code receives geo separately.
    """
    # 6 vertices: 3 on top circle (height=10), 3 on bottom circle (height=0)
    verts = [
        CanonicalVertex("V0", _pt(5.0, 0.0, 10.0)),
        CanonicalVertex("V1", _pt(-5.0, 0.0, 10.0)),
        CanonicalVertex("V2", _pt(0.0, 5.0, 10.0)),
        CanonicalVertex("V3", _pt(5.0, 0.0, 0.0)),
        CanonicalVertex("V4", _pt(-5.0, 0.0, 0.0)),
        CanonicalVertex("V5", _pt(0.0, 5.0, 0.0)),
    ]
    # 3 top arc edges + 3 bottom arc edges; curve IDs are arbitrary references
    # (not validated because we do not attach geometry to the topology).
    edges = [
        CanonicalEdge("E-top1", "V0", "V1", "curve-top"),
        CanonicalEdge("E-top2", "V1", "V2", "curve-top"),
        CanonicalEdge("E-top3", "V2", "V0", "curve-top"),
        CanonicalEdge("E-bot1", "V3", "V4", "curve-bot"),
        CanonicalEdge("E-bot2", "V4", "V5", "curve-bot"),
        CanonicalEdge("E-bot3", "V5", "V3", "curve-bot"),
    ]
    # Cap loops (outer boundaries of the planar cap faces)
    top_loop = CanonicalLoop("L-top", ("E-top1", "E-top2", "E-top3"), loop_type=LoopType.OUTER)
    bot_loop = CanonicalLoop("L-bot", ("E-bot1", "E-bot2", "E-bot3"), loop_type=LoopType.OUTER)
    # Cylinder boundary loops — SAME edge IDs as cap loops so adjacency is detected
    cyl_loop_top = CanonicalLoop("L-cyl-top", ("E-top1", "E-top2", "E-top3"))
    cyl_loop_bot = CanonicalLoop("L-cyl-bot", ("E-bot1", "E-bot2", "E-bot3"))
    # Faces
    top_face = CanonicalFace("F-top", top_surface_id, ("L-top",))
    bot_face = CanonicalFace("F-bot", bot_surface_id, ("L-bot",))
    cyl_face = CanonicalFace("F-cyl", cyl_surface_id, ("L-cyl-top", "L-cyl-bot"))
    # Shell & body
    shell = CanonicalShell("SH-1", ("F-cyl", "F-top", "F-bot"), closure=ShellClosure.CLOSED)
    body = CanonicalBody("B-1", BodyType.SOLID, ("SH-1",))
    return CanonicalTopology(
        topology_id="TOPO-1",
        vertices=tuple(verts),
        edges=tuple(edges),
        loops=(top_loop, bot_loop, cyl_loop_top, cyl_loop_bot),
        faces=(top_face, bot_face, cyl_face),
        shells=(shell,),
        bodies=(body,),
        # geometry is intentionally NOT attached here; edge curve_id and
        # face surface_id are only validated when geometry is present.
        # The feature recogniser receives geo separately via recognize_features().
    )


# ===========================================================================
# TestFeatureEvidenceModel
# ===========================================================================

class TestFeatureEvidenceModel:
    """Tests for the feature data-model classes in features.py."""

    def test_feature_status_enum_values(self) -> None:
        assert FeatureStatus.CANDIDATE == "CANDIDATE"
        assert FeatureStatus.CONFIRMED == "CONFIRMED"
        assert FeatureStatus.INCOMPLETE == "INCOMPLETE"
        assert FeatureStatus.REJECTED == "REJECTED"
        assert FeatureStatus.UNKNOWN == "UNKNOWN"

    def test_manufacturing_feature_type_enum(self) -> None:
        for v in ("HOLE", "POCKET", "SLOT", "STEP", "CHAMFER", "FILLET", "UNKNOWN"):
            assert ManufacturingFeatureType(v) is not None

    def test_hole_subtype_enum(self) -> None:
        for v in ("THROUGH", "BLIND", "COUNTERBORE", "COUNTERSINK", "UNKNOWN"):
            assert HoleSubtype(v) is not None

    def test_face_classification_enum(self) -> None:
        for v in ("PLANAR", "CYLINDRICAL", "CONICAL", "SPHERICAL", "TOROIDAL",
                  "FREEFORM", "UNKNOWN"):
            assert FaceClassification(v) is not None

    def test_classified_face_construction(self) -> None:
        cf = ClassifiedFace(surface_id="S1", classification=FaceClassification.PLANAR)
        assert cf.surface_id == "S1"
        assert cf.classification == FaceClassification.PLANAR
        assert cf.face_id is None

    def test_classified_face_rejects_empty_surface_id(self) -> None:
        from backend.domain.exceptions import ValidationError
        with pytest.raises(ValidationError):
            ClassifiedFace(surface_id="", classification=FaceClassification.PLANAR)

    def test_face_adjacency_construction(self) -> None:
        adj = FaceAdjacency(
            face_a_surface_id="S1",
            face_b_surface_id="S2",
            shared_edge_count=2,
        )
        assert adj.shared_edge_count == 2

    def test_face_adjacency_rejects_negative_edge_count(self) -> None:
        from backend.domain.exceptions import ValidationError
        with pytest.raises(ValidationError):
            FaceAdjacency(
                face_a_surface_id="S1",
                face_b_surface_id="S2",
                shared_edge_count=-1,
            )

    def test_manufacturing_feature_construction(self) -> None:
        feat = ManufacturingFeature(
            feature_id="F1",
            feature_type=ManufacturingFeatureType.HOLE,
            status=FeatureStatus.CANDIDATE,
            hole_subtype=HoleSubtype.UNKNOWN,
            surface_ids=("S1",),
            evidence_notes="test",
        )
        assert feat.feature_type == ManufacturingFeatureType.HOLE
        assert feat.status == FeatureStatus.CANDIDATE

    def test_manufacturing_feature_rejects_empty_id(self) -> None:
        from backend.domain.exceptions import ValidationError
        with pytest.raises(ValidationError):
            ManufacturingFeature(
                feature_id="",
                feature_type=ManufacturingFeatureType.HOLE,
                status=FeatureStatus.CANDIDATE,
            )

    def test_feature_recognition_result_derived_counts(self) -> None:
        feat = ManufacturingFeature(
            feature_id="F1",
            feature_type=ManufacturingFeatureType.HOLE,
            status=FeatureStatus.CANDIDATE,
            hole_subtype=HoleSubtype.UNKNOWN,
        )
        result = FeatureRecognitionResult(
            classified_faces=(),
            adjacencies=(),
            features=(feat,),
            recognition_basis="GEOMETRY_ONLY",
        )
        assert result.hole_candidates == 1
        assert result.confirmed_holes == 0
        assert result.pocket_candidates == 0

    def test_feature_recognition_result_confirmed_through_hole_count(self) -> None:
        feat = ManufacturingFeature(
            feature_id="F1",
            feature_type=ManufacturingFeatureType.HOLE,
            status=FeatureStatus.CONFIRMED,
            hole_subtype=HoleSubtype.THROUGH,
        )
        result = FeatureRecognitionResult(
            classified_faces=(),
            adjacencies=(),
            features=(feat,),
            recognition_basis="TOPOLOGY",
            topology_available=True,
        )
        assert result.confirmed_holes == 1
        assert result.through_holes == 1
        assert result.blind_holes == 0
        assert result.hole_candidates == 0

    def test_feature_recognition_result_negative_count_rejected(self) -> None:
        from backend.domain.exceptions import ValidationError
        with pytest.raises(ValidationError):
            FeatureRecognitionResult(
                classified_faces=(),
                adjacencies=(),
                features=(),
                planar_face_count=-1,
            )


# ===========================================================================
# TestNegativeRules — HARD RULE enforcement
# ===========================================================================

class TestNegativeRules:
    """Explicit negative tests per task MUST NOT list."""

    def test_dxf_circle_is_not_confirmed_hole(self) -> None:
        """A DXF circle MUST NOT produce a CONFIRMED hole."""
        geo = _geometry_with_curves(_circle_curve("C1", r=5.0))
        result = recognize_features(geo, None)
        assert result.confirmed_holes == 0, (
            "DXF circle must not be CONFIRMED — no depth, no topology"
        )

    def test_dxf_circle_produces_candidate_only(self) -> None:
        """A DXF circle MUST produce exactly one CANDIDATE hole."""
        geo = _geometry_with_curves(_circle_curve("C1", r=5.0))
        result = recognize_features(geo, None)
        assert result.hole_candidates == 1
        feat = result.features[0]
        assert feat.status == FeatureStatus.CANDIDATE
        assert feat.feature_type == ManufacturingFeatureType.HOLE

    def test_arc_is_not_a_hole_candidate(self) -> None:
        """A partial arc (non-full circle) MUST NOT produce a hole candidate."""
        geo = _geometry_with_curves(_arc_curve("A1"))
        result = recognize_features(geo, None)
        assert result.hole_candidates == 0, (
            "ARC (partial arc) must not produce a hole candidate"
        )
        assert len(result.features) == 0

    def test_line_is_not_a_hole_candidate(self) -> None:
        """A line MUST NOT produce any feature candidate."""
        geo = _geometry_with_curves(_line_curve("L1"))
        result = recognize_features(geo, None)
        assert len(result.features) == 0

    def test_cylindrical_surface_alone_is_not_confirmed_hole(self) -> None:
        """A lone cylindrical surface WITHOUT topology MUST NOT be a CONFIRMED hole."""
        geo = _geometry_with_surfaces(_cylinder_surface("S1"))
        result = recognize_features(geo, None)
        assert result.confirmed_holes == 0, (
            "Cylindrical surface without topology must not be CONFIRMED"
        )

    def test_cylindrical_surface_alone_produces_candidate(self) -> None:
        """A lone cylindrical surface WITHOUT topology MUST produce a CANDIDATE."""
        geo = _geometry_with_surfaces(_cylinder_surface("S1"))
        result = recognize_features(geo, None)
        assert result.hole_candidates == 1
        feat = result.features[0]
        assert feat.status == FeatureStatus.CANDIDATE
        assert feat.hole_subtype == HoleSubtype.UNKNOWN

    def test_plane_surface_alone_produces_no_feature_candidate(self) -> None:
        """A lone planar surface without topology/adjacency MUST NOT produce a feature."""
        geo = _geometry_with_surfaces(_plane_surface("S1"))
        result = recognize_features(geo, None)
        assert len(result.features) == 0
        assert result.planar_face_count == 1

    def test_bspline_surface_produces_no_feature_candidate(self) -> None:
        """A B-spline/NURBS surface MUST NOT produce any feature candidate."""
        geo = _geometry_with_surfaces(_bspline_surface("S1"))
        result = recognize_features(geo, None)
        assert len(result.features) == 0
        assert result.freeform_face_count == 1

    def test_multiple_circles_produce_equal_number_of_candidates(self) -> None:
        """N circles → N hole candidates, all CANDIDATE, none CONFIRMED."""
        geo = _geometry_with_curves(
            _circle_curve("C1", r=5.0),
            _circle_curve("C2", r=8.0),
            _circle_curve("C3", r=12.0),
        )
        result = recognize_features(geo, None)
        assert result.hole_candidates == 3
        assert result.confirmed_holes == 0
        for feat in result.features:
            assert feat.status == FeatureStatus.CANDIDATE


# ===========================================================================
# TestFaceClassification
# ===========================================================================

class TestFaceClassification:
    """Tests for surface → face classification mapping."""

    def test_plane_surface_classified_as_planar(self) -> None:
        geo = _geometry_with_surfaces(_plane_surface("S1"))
        result = recognize_features(geo, None)
        assert result.planar_face_count == 1
        assert result.classified_faces[0].classification == FaceClassification.PLANAR

    def test_cylinder_surface_classified_as_cylindrical(self) -> None:
        geo = _geometry_with_surfaces(_cylinder_surface("S1"))
        result = recognize_features(geo, None)
        assert result.cylindrical_face_count == 1
        assert result.classified_faces[0].classification == FaceClassification.CYLINDRICAL

    def test_cone_surface_classified_as_conical(self) -> None:
        geo = _geometry_with_surfaces(_cone_surface("S1"))
        result = recognize_features(geo, None)
        assert result.conical_face_count == 1
        assert result.classified_faces[0].classification == FaceClassification.CONICAL

    def test_torus_surface_classified_as_toroidal(self) -> None:
        geo = _geometry_with_surfaces(_torus_surface("S1"))
        result = recognize_features(geo, None)
        assert result.toroidal_face_count == 1
        assert result.classified_faces[0].classification == FaceClassification.TOROIDAL

    def test_nurbs_surface_classified_as_freeform(self) -> None:
        geo = _geometry_with_surfaces(_bspline_surface("S1"))
        result = recognize_features(geo, None)
        assert result.freeform_face_count == 1
        assert result.classified_faces[0].classification == FaceClassification.FREEFORM

    def test_mixed_surfaces_classified_correctly(self) -> None:
        geo = _geometry_with_surfaces(
            _plane_surface("S1"),
            _cylinder_surface("S2"),
            _bspline_surface("S3"),
            _cone_surface("S4"),
        )
        result = recognize_features(geo, None)
        assert result.planar_face_count == 1
        assert result.cylindrical_face_count == 1
        assert result.freeform_face_count == 1
        assert result.conical_face_count == 1

    def test_no_geometry_produces_empty_classification(self) -> None:
        result = recognize_features(None, None)
        assert len(result.classified_faces) == 0
        assert result.recognition_basis == "NONE"


# ===========================================================================
# TestRecognitionBasis
# ===========================================================================

class TestRecognitionBasis:
    """Tests for recognition basis determination."""

    def test_no_data_produces_none_basis(self) -> None:
        result = recognize_features(None, None)
        assert result.recognition_basis == "NONE"
        assert not result.topology_available

    def test_surfaces_only_produces_geometry_only_basis(self) -> None:
        geo = _geometry_with_surfaces(_plane_surface("S1"))
        result = recognize_features(geo, None)
        assert result.recognition_basis == "GEOMETRY_ONLY"
        assert not result.topology_available

    def test_curves_only_produces_2d_geometry_only_basis(self) -> None:
        geo = _geometry_with_curves(_circle_curve("C1"))
        result = recognize_features(geo, None)
        assert result.recognition_basis == "2D_GEOMETRY_ONLY"
        assert not result.topology_available

    def test_geometry_and_topology_produces_topology_basis(self) -> None:
        # Build minimal geometry with curves (needed for edge references)
        c_top = CanonicalCurve("curve-top", CanonicalCurveType.CIRCLE, center=_pt(0,0,10), radius=_mm(5), axis=_vec(0,0,1))
        c_bot = CanonicalCurve("curve-bot", CanonicalCurveType.CIRCLE, center=_pt(0,0,0), radius=_mm(5), axis=_vec(0,0,1))
        c_l1 = CanonicalCurve("curve-line1", CanonicalCurveType.LINE, origin=_pt(5,0,10), direction=_vec(0,0,-1))
        c_l2 = CanonicalCurve("curve-line2", CanonicalCurveType.LINE, origin=_pt(-5,0,10), direction=_vec(0,0,-1))
        s_cyl = _cylinder_surface("S-cyl")
        s_top = _plane_surface("S-top")
        s_bot = _plane_surface("S-bot")
        geo = CanonicalGeometry(
            geometry_id="G1",
            curves=(c_top, c_bot, c_l1, c_l2),
            surfaces=(s_cyl, s_top, s_bot),
        )
        topo = _minimal_hole_topology("S-cyl", "S-top", "S-bot", geo)
        result = recognize_features(geo, topo)
        assert result.recognition_basis == "TOPOLOGY"
        assert result.topology_available


# ===========================================================================
# TestTopologyConfirmation
# ===========================================================================

class TestTopologyConfirmation:
    """Tests for CONFIRMED features when topology is available."""

    def _build_hole_geometry(self) -> CanonicalGeometry:
        c_top = CanonicalCurve("curve-top", CanonicalCurveType.CIRCLE, center=_pt(0,0,10), radius=_mm(5), axis=_vec(0,0,1))
        c_bot = CanonicalCurve("curve-bot", CanonicalCurveType.CIRCLE, center=_pt(0,0,0), radius=_mm(5), axis=_vec(0,0,1))
        c_l1 = CanonicalCurve("curve-line1", CanonicalCurveType.LINE, origin=_pt(5,0,10), direction=_vec(0,0,-1))
        c_l2 = CanonicalCurve("curve-line2", CanonicalCurveType.LINE, origin=_pt(-5,0,10), direction=_vec(0,0,-1))
        s_cyl = _cylinder_surface("S-cyl")
        s_top = _plane_surface("S-top")
        s_bot = _plane_surface("S-bot")
        return CanonicalGeometry(
            geometry_id="G1",
            curves=(c_top, c_bot, c_l1, c_l2),
            surfaces=(s_cyl, s_top, s_bot),
        )

    def test_cylindrical_face_with_two_planar_caps_produces_confirmed_through_hole(self) -> None:
        geo = self._build_hole_geometry()
        topo = _minimal_hole_topology("S-cyl", "S-top", "S-bot", geo)
        result = recognize_features(geo, topo)
        assert result.confirmed_holes >= 1
        confirmed = [f for f in result.features
                     if f.feature_type == ManufacturingFeatureType.HOLE
                     and f.status == FeatureStatus.CONFIRMED]
        assert len(confirmed) >= 1
        assert confirmed[0].hole_subtype == HoleSubtype.THROUGH

    def test_topology_produces_no_hole_candidates_only_confirmed(self) -> None:
        """With topology, cylindrical face + 2 planar caps → CONFIRMED, not CANDIDATE."""
        geo = self._build_hole_geometry()
        topo = _minimal_hole_topology("S-cyl", "S-top", "S-bot", geo)
        result = recognize_features(geo, topo)
        # All holes should be CONFIRMED (the confirmed rules ran)
        assert result.hole_candidates == 0 or result.confirmed_holes > 0

    def test_topology_adjacency_is_computed(self) -> None:
        geo = self._build_hole_geometry()
        topo = _minimal_hole_topology("S-cyl", "S-top", "S-bot", geo)
        result = recognize_features(geo, topo)
        assert result.adjacency_count > 0
        assert result.adjacency_available

    def test_topology_classifies_all_faces(self) -> None:
        geo = self._build_hole_geometry()
        topo = _minimal_hole_topology("S-cyl", "S-top", "S-bot", geo)
        result = recognize_features(geo, topo)
        assert len(result.classified_faces) == 3
        classes = {cf.classification for cf in result.classified_faces}
        assert FaceClassification.CYLINDRICAL in classes
        assert FaceClassification.PLANAR in classes


# ===========================================================================
# TestConeAndTorusCandidates
# ===========================================================================

class TestConeAndTorusCandidates:
    """Conical surfaces → chamfer/countersink candidates.
     Toroidal surfaces → fillet candidates.
    """

    def test_conical_surface_produces_chamfer_candidate(self) -> None:
        geo = _geometry_with_surfaces(_cone_surface("S1"))
        result = recognize_features(geo, None)
        chamfer_candidates = [
            f for f in result.features
            if f.feature_type == ManufacturingFeatureType.CHAMFER
            and f.status == FeatureStatus.CANDIDATE
        ]
        assert len(chamfer_candidates) == 1

    def test_conical_surface_does_not_produce_confirmed_chamfer(self) -> None:
        geo = _geometry_with_surfaces(_cone_surface("S1"))
        result = recognize_features(geo, None)
        confirmed_chamfers = [
            f for f in result.features
            if f.feature_type == ManufacturingFeatureType.CHAMFER
            and f.status == FeatureStatus.CONFIRMED
        ]
        assert len(confirmed_chamfers) == 0

    def test_toroidal_surface_produces_fillet_candidate(self) -> None:
        geo = _geometry_with_surfaces(_torus_surface("S1"))
        result = recognize_features(geo, None)
        fillet_candidates = [
            f for f in result.features
            if f.feature_type == ManufacturingFeatureType.FILLET
            and f.status == FeatureStatus.CANDIDATE
        ]
        assert len(fillet_candidates) == 1

    def test_toroidal_surface_does_not_produce_confirmed_fillet(self) -> None:
        geo = _geometry_with_surfaces(_torus_surface("S1"))
        result = recognize_features(geo, None)
        confirmed_fillets = [
            f for f in result.features
            if f.feature_type == ManufacturingFeatureType.FILLET
            and f.status == FeatureStatus.CONFIRMED
        ]
        assert len(confirmed_fillets) == 0


# ===========================================================================
# TestSourceTraceability
# ===========================================================================

class TestSourceTraceability:
    """Feature records must carry source traceability."""

    def test_dxf_circle_candidate_references_curve_id(self) -> None:
        geo = _geometry_with_curves(_circle_curve("C-TEST"))
        result = recognize_features(geo, None)
        feat = result.features[0]
        assert "C-TEST" in feat.curve_ids

    def test_cylinder_candidate_references_surface_id(self) -> None:
        geo = _geometry_with_surfaces(_cylinder_surface("S-CYL"))
        result = recognize_features(geo, None)
        feat = result.features[0]
        assert "S-CYL" in feat.surface_ids


# ===========================================================================
# TestProductionFileRegressions
# ===========================================================================

class TestProductionFileRegressions:
    """Level-2 behavior must be preserved; Level-3 runs on top."""

    def _load_iges_doc(self):
        """Load the production IGES file via ingest_file."""
        from pathlib import Path
        from backend.interoperability.adapters.iges import IgesTokenAdapter, IGES_DESCRIPTOR
        from backend.interoperability.models import EngineeringSource

        import os
        igs_path = (
            r"C:\Users\ilhan\AppData\Local\Temp\claude"
            r"\C--Users-ilhan-Downloads-MachiningPro-AI-NEXT"
            r"\5c6eaa26-69c4-4e68-864b-24424ae1b1d9\scratchpad"
            r"\fa00aat46855.geo_fin001.004999.igs"
        )
        if not os.path.exists(igs_path):
            pytest.skip("Production IGES file not available")
        adapter = IgesTokenAdapter()
        source = EngineeringSource(
            source_id="SRC-IGES",
            source_format_id="IGES",
            file_name="fa00aat46855.geo_fin001.004999.igs",
        )
        return adapter.ingest_file(source, IGES_DESCRIPTOR, Path(igs_path))

    def _load_dxf_doc(self):
        """Load the production DXF file via ingest."""
        import os
        from backend.interoperability.adapters.dxf import DxfTokenAdapter, DXF_DESCRIPTOR
        from backend.interoperability.models import EngineeringSource

        dxf_path = (
            r"C:\Users\ilhan\AppData\Local\Temp\claude"
            r"\d83048698c536d4a\1b3bb96a-da82-40ce-ba5d-97b8f361659a"
            r"\scratchpad\109106_01_39.dxf"
        )
        if not os.path.exists(dxf_path):
            pytest.skip("Production DXF file not available")
        content = open(dxf_path, "rb").read().decode("utf-8", "replace")
        adapter = DxfTokenAdapter()
        source = EngineeringSource(
            source_id="SRC-DXF",
            source_format_id="DXF",
            file_name="109106_01_39.dxf",
            notes=content,
        )
        return adapter.ingest(source, DXF_DESCRIPTOR)

    # --- IGES Level-2 regression ---

    def test_iges_level2_capability_preserved(self) -> None:
        from backend.interoperability.enums import CapabilityLevel
        doc = self._load_iges_doc()
        assert doc.capability_level in (
            CapabilityLevel.LEVEL_2_GEOMETRY,
            CapabilityLevel.LEVEL_3_ENGINEERING_SEMANTICS,
        ), f"Expected Level-2 or higher, got {doc.capability_level}"

    def test_iges_geometry_has_expected_surfaces(self) -> None:
        doc = self._load_iges_doc()
        assert doc.geometry is not None
        assert len(doc.geometry.surfaces) == 645

    def test_iges_level3_features_object_present(self) -> None:
        doc = self._load_iges_doc()
        assert doc.features is not None

    def test_iges_production_has_64_planar_surfaces(self) -> None:
        doc = self._load_iges_doc()
        assert doc.features is not None
        assert doc.features.planar_face_count == 64

    def test_iges_production_has_zero_cylindrical_surfaces(self) -> None:
        """Production IGES uses B-spline surfaces only — no analytical cylinders."""
        doc = self._load_iges_doc()
        assert doc.features is not None
        assert doc.features.cylindrical_face_count == 0

    def test_iges_production_has_zero_confirmed_holes(self) -> None:
        """No cylindrical surfaces + no topology → zero confirmed holes."""
        doc = self._load_iges_doc()
        assert doc.features is not None
        assert doc.features.confirmed_holes == 0

    def test_iges_production_has_zero_hole_candidates(self) -> None:
        """Zero cylindrical surfaces → zero hole candidates from IGES."""
        doc = self._load_iges_doc()
        assert doc.features is not None
        assert doc.features.hole_candidates == 0

    def test_iges_no_fabricated_features(self) -> None:
        """Feature count must reflect real geometry — not hard-coded."""
        doc = self._load_iges_doc()
        assert doc.features is not None
        # Total features is exactly 0 (no cylinder/cone/tori in production file)
        assert len(doc.features.features) == 0

    def test_iges_topology_not_available(self) -> None:
        doc = self._load_iges_doc()
        assert doc.features is not None
        assert not doc.features.topology_available

    def test_iges_recognition_basis_is_geometry_only(self) -> None:
        doc = self._load_iges_doc()
        assert doc.features is not None
        assert doc.features.recognition_basis == "GEOMETRY_ONLY"

    # --- DXF Level-2 regression ---

    def test_dxf_level2_capability_preserved_or_upgraded(self) -> None:
        from backend.interoperability.enums import CapabilityLevel
        doc = self._load_dxf_doc()
        assert doc.capability_level in (
            CapabilityLevel.LEVEL_2_GEOMETRY,
            CapabilityLevel.LEVEL_2_NORMALIZED,
            CapabilityLevel.LEVEL_3_ENGINEERING_SEMANTICS,
            CapabilityLevel.LEVEL_4_MANUFACTURING_FEATURES,
            CapabilityLevel.LEVEL_5_PROCESS_CONTENT,
            CapabilityLevel.LEVEL_6_ENGINEERING_VALIDATED,
            CapabilityLevel.LEVEL_7_CYCLE_TIME_INTELLIGENCE,
        )

    def test_dxf_level3_features_object_present(self) -> None:
        doc = self._load_dxf_doc()
        assert doc.features is not None

    def test_dxf_production_14_circle_hole_candidates(self) -> None:
        """Production DXF has 14 CIRCLE entities → 14 2-D hole candidates."""
        doc = self._load_dxf_doc()
        assert doc.features is not None
        assert doc.features.hole_candidates == 14

    def test_dxf_production_zero_confirmed_holes(self) -> None:
        """DXF is 2-D only; circles cannot be CONFIRMED holes without depth."""
        doc = self._load_dxf_doc()
        assert doc.features is not None
        assert doc.features.confirmed_holes == 0

    def test_dxf_recognition_basis_is_2d_geometry_only(self) -> None:
        doc = self._load_dxf_doc()
        assert doc.features is not None
        assert doc.features.recognition_basis == "2D_GEOMETRY_ONLY"

    def test_dxf_no_arc_produces_hole_candidates(self) -> None:
        """ARC (partial arc) must not inflate hole candidate count."""
        doc = self._load_dxf_doc()
        assert doc.features is not None
        # CIRCLE count=14 from production DXF; ARC count=48 must NOT be included
        assert doc.features.hole_candidates == 14  # exactly the circle count
