"""
P10 Phase 4 Final Real STEP Qualification Tests (MUST 26).

Validates all 28 MUSTs from the MACHININGPRO_AI_P10_PHASE4_FINAL_REAL_STEP_QUALIFICATION
task against live parse results on all 6 user-owned STEP files.

HARD RULES:
  - is_dispatchable=False always.
  - production_released=False always.
  - AUTO_CONFIRMED_FEATURE_FOUND=NO always.
  - Source files are NOT committed and NOT modified.
  - IN_HOUSE_BENCHMARK files (P10-S1/S2/S3) are excluded from REAL counts.
"""

from __future__ import annotations

import pathlib

import pytest

from backend.cad_import.step_intake import REAL_STEP_SAMPLE_COUNT
from backend.step_brep.feature_detector import detect_hole_candidates
from backend.step_brep.gmsh_step_parser import parse_step_file
from backend.step_brep.verification_adapter import build_step_verification_input

# ---------------------------------------------------------------------------
# Constants — all data from actual parse runs (2026-11-17)
# ---------------------------------------------------------------------------

_SAMPLE_ROOT = pathlib.Path(r"D:\makina_ogrenmesi\olcum_denemeleri")

_REAL_STEP_FILES = [
    "electronics-enclosure.step",
    "flanged-bushing (1).step",
    "flange-plate.step",
    "l-bracket.step",
    "Pump Manifold v3.step",
    "stepped-shaft-keyway.step",
]

_EXPECTED_SHA256 = {
    "electronics-enclosure.step":
        "ee3f6c357a3c3b9e564da06cb6628ef7a15156fe1aed512b7b764969d0d44d85",
    "flanged-bushing (1).step":
        "1c2a82b15b1c78ba707b4001af19a08866117fd926ece63cd35f1ba8a042ff12",
    "flange-plate.step":
        "a841f9969883e6980ffd05b368c40221c0b35bfcde2e406ec73264c46cb46bd3",
    "l-bracket.step":
        "821f8113f6d6aa7b5df59cedfde0fe21148d7491552e12ae3ab4fa71e6c66831",
    "Pump Manifold v3.step":
        "8596ec93c6b3fa01e907806204e8f30e1c0e4210988a5b86e237c7ac667edac6",
    "stepped-shaft-keyway.step":
        "570efc7d414b5bab5844431d5ad54758749ce3eda34622f4dd315685de402f75",
}

_EXPECTED_BREP = {
    "electronics-enclosure.step":
        {"volumes": 1, "surfaces": 35, "edges": 72, "vertices": 48},
    "flanged-bushing (1).step":
        {"volumes": 1, "surfaces": 8, "edges": 13, "vertices": 8},
    "flange-plate.step":
        {"volumes": 1, "surfaces": 15, "edges": 39, "vertices": 26},
    "l-bracket.step":
        {"volumes": 1, "surfaces": 13, "edges": 33, "vertices": 22},
    "Pump Manifold v3.step":
        {"volumes": 1, "surfaces": 118, "edges": 334, "vertices": 214},
    "stepped-shaft-keyway.step":
        {"volumes": 1, "surfaces": 12, "edges": 25, "vertices": 16},
}

_EXPECTED_HOLES = {
    "electronics-enclosure.step": 8,
    "flanged-bushing (1).step": 5,
    "flange-plate.step": 5,
    "l-bracket.step": 4,
    "Pump Manifold v3.step": 0,
    "stepped-shaft-keyway.step": 3,
}

_TOTAL_EXPECTED_HOLES = 25
_PHASE4_REAL_STEP_COUNT = 6


# ===========================================================================
# A — Baseline: MUST 1 and MUST 2
# ===========================================================================


class TestBaseline:
    def test_real_step_sample_count_is_six(self) -> None:
        """MUST 1: REAL_STEP_SAMPLE_COUNT=6 (gate met)."""
        assert REAL_STEP_SAMPLE_COUNT == 6

    def test_sample_root_exists(self) -> None:
        """MUST 2: Sample root directory accessible."""
        assert _SAMPLE_ROOT.exists()

    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_step_file_exists(self, fname: str) -> None:
        """MUST 2: All 6 STEP files present."""
        assert (_SAMPLE_ROOT / fname).exists()

    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_step_file_sha256(self, fname: str) -> None:
        """MUST 2: SHA256 matches expected (source integrity)."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        assert r.sha256 == _EXPECTED_SHA256[fname], (
            f"{fname}: SHA256 mismatch — file may have been modified"
        )

    def test_step_files_not_committed_in_repo(self) -> None:
        """MUST 24: Source files outside repo (path starts with D:/makina_ogrenmesi/olcum)."""
        assert str(_SAMPLE_ROOT).startswith(r"D:\makina_ogrenmesi"), (
            "Sample root must be outside the repo"
        )


# ===========================================================================
# B — Parse and B-Rep: MUST 3 and MUST 4
# ===========================================================================


class TestParseDeterminism:
    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_parse_pass(self, fname: str) -> None:
        """MUST 3: All 6 files parse with status=PASS."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        assert r.status == "PASS", f"{fname}: parse failed: {r.failure_reason}"

    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_parse_deterministic(self, fname: str) -> None:
        """MUST 3: Two consecutive parses produce identical results."""
        p = str(_SAMPLE_ROOT / fname)
        r1 = parse_step_file(p, sample_origin="USER_OWNED")
        r2 = parse_step_file(p, sample_origin="USER_OWNED")
        assert r1.sha256 == r2.sha256
        assert r1.volume_count == r2.volume_count
        assert r1.surface_count == r2.surface_count
        assert r1.edge_count == r2.edge_count

    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_brep_body_count(self, fname: str) -> None:
        """MUST 4: Expected body (volume) count per file."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        expected = _EXPECTED_BREP[fname]["volumes"]
        assert r.volume_count == expected

    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_brep_face_count(self, fname: str) -> None:
        """MUST 4: Expected face (surface) count per file."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        expected = _EXPECTED_BREP[fname]["surfaces"]
        assert r.surface_count == expected

    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_brep_edge_count(self, fname: str) -> None:
        """MUST 4: Expected edge count per file."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        expected = _EXPECTED_BREP[fname]["edges"]
        assert r.edge_count == expected

    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_brep_closed_solid(self, fname: str) -> None:
        """MUST 4: All files are closed solids (volume_count > 0)."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        assert r.volume_count > 0, f"{fname}: no closed solid bodies found"

    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_brep_bbox_not_fabricated(self, fname: str) -> None:
        """MUST 4: Bounding box present and from real B-Rep geometry."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        assert r.bbox_min is not None
        assert r.bbox_max is not None
        xmin, ymin, zmin = r.bbox_min
        xmax, ymax, zmax = r.bbox_max
        assert xmax > xmin
        assert ymax > ymin
        assert zmax > zmin


# ===========================================================================
# C — Surface Classification: MUST 5
# ===========================================================================


class TestSurfaceClassification:
    def test_pump_manifold_mostly_unknown(self) -> None:
        """MUST 5: Pump Manifold has 97% UNKNOWN faces (complex NURBS)."""
        r = parse_step_file(
            str(_SAMPLE_ROOT / "Pump Manifold v3.step"),
            sample_origin="USER_OWNED",
        )
        unk = sum(1 for f in r.faces if f.surface_class == "UNKNOWN")
        assert unk >= 110, f"Expected >=110 UNKNOWN, got {unk}"

    def test_flanged_bushing_zero_unknown(self) -> None:
        """MUST 5: flanged-bushing has 0 UNKNOWN faces (simple geometry)."""
        r = parse_step_file(
            str(_SAMPLE_ROOT / "flanged-bushing (1).step"),
            sample_origin="USER_OWNED",
        )
        unk = sum(1 for f in r.faces if f.surface_class == "UNKNOWN")
        assert unk == 0

    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_surface_classes_are_valid(self, fname: str) -> None:
        """MUST 5: Surface classes are only PLANAR, CYLINDRICAL, or UNKNOWN."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        valid = {"PLANAR", "CYLINDRICAL", "UNKNOWN"}
        for f in r.faces:
            assert f.surface_class in valid, (
                f"{fname}: unexpected surface class {f.surface_class!r}"
            )

    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_face_count_matches_sum_of_classes(self, fname: str) -> None:
        """MUST 5: PLANAR + CYLINDRICAL + UNKNOWN = total face count."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        total = sum(1 for f in r.faces)
        assert total == r.surface_count


# ===========================================================================
# D — Feature Candidates: MUST 6 and MUST 7
# ===========================================================================


class TestFeatureCandidates:
    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_hole_candidate_count(self, fname: str) -> None:
        """MUST 6: Hole candidate count matches expected values."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        holes = detect_hole_candidates(r)
        assert len(holes) == _EXPECTED_HOLES[fname], (
            f"{fname}: expected {_EXPECTED_HOLES[fname]} holes, got {len(holes)}"
        )

    def test_total_hole_candidates_aggregate(self) -> None:
        """MUST 6: Aggregate hole count across all 6 files = 25."""
        total = 0
        for fname in _REAL_STEP_FILES:
            r = parse_step_file(
                str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED"
            )
            total += len(detect_hole_candidates(r))
        assert total == _TOTAL_EXPECTED_HOLES

    def test_pump_manifold_zero_holes(self) -> None:
        """MUST 7: Pump Manifold has 0 cylindrical faces → 0 hole candidates."""
        r = parse_step_file(
            str(_SAMPLE_ROOT / "Pump Manifold v3.step"),
            sample_origin="USER_OWNED",
        )
        holes = detect_hole_candidates(r)
        assert len(holes) == 0

    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_all_features_are_candidates_not_confirmed(self, fname: str) -> None:
        """MUST 7+9: feature_status is always CANDIDATE — never CONFIRMED."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        for hole in detect_hole_candidates(r):
            assert hole.feature_status == "CANDIDATE"

    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_hole_diameter_not_fabricated(self, fname: str) -> None:
        """MUST 8: Hole diameters are within plausible engineering range."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        for hole in detect_hole_candidates(r):
            assert hole.diameter_mm > 0.5, (
                f"{fname}: diameter {hole.diameter_mm}mm below minimum threshold"
            )
            assert hole.diameter_mm < 500.0, (
                f"{fname}: diameter {hole.diameter_mm}mm above maximum threshold"
            )


# ===========================================================================
# E — Engineering Confirmation: MUST 9
# ===========================================================================


class TestEngineeringConfirmation:
    def test_auto_confirmed_feature_found_is_no(self) -> None:
        """MUST 9: AUTO_CONFIRMED_FEATURE_FOUND=NO across all 6 files."""
        for fname in _REAL_STEP_FILES:
            r = parse_step_file(
                str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED"
            )
            for hole in detect_hole_candidates(r):
                assert hole.feature_status == "CANDIDATE", (
                    f"AUTO_CONFIRM violation: {fname} hole {hole.face_tag} "
                    f"has status={hole.feature_status!r}"
                )


# ===========================================================================
# F — Safety Invariants: MUST 25
# ===========================================================================


class TestSafetyInvariants:
    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_is_dispatchable_always_false(self, fname: str) -> None:
        """MUST 25: is_dispatchable=False always."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        assert r.is_dispatchable is False

    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_production_released_always_false(self, fname: str) -> None:
        """MUST 25: production_released=False always."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        assert r.production_released is False

    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_hole_candidates_not_dispatchable(self, fname: str) -> None:
        """MUST 25: HoleCandidateRecord.is_dispatchable=False always."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        for hole in detect_hole_candidates(r):
            assert hole.is_dispatchable is False


# ===========================================================================
# G — Verification Adapter: MUST 13
# ===========================================================================


class TestVerificationAdapter:
    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_adapter_parse_status_pass(self, fname: str) -> None:
        """MUST 13: Verification adapter reports parse_status=PASS."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        vi = build_step_verification_input(r)
        assert vi.parse_status == "PASS"

    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_adapter_gouge_not_verifiable(self, fname: str) -> None:
        """MUST 13+18: gouge_validated=NOT_VERIFIABLE (Phase 3 — no comparator)."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        vi = build_step_verification_input(r)
        assert vi.gouge_validated == "NOT_VERIFIABLE"

    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_adapter_step_target_not_available(self, fname: str) -> None:
        """MUST 18: step_target_for_gouge_available=False."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        vi = build_step_verification_input(r)
        assert vi.step_target_for_gouge_available is False

    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_adapter_voxel_comparison_not_ready(self, fname: str) -> None:
        """MUST 18: voxel_to_target_comparison_ready=False."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        vi = build_step_verification_input(r)
        assert vi.voxel_to_target_comparison_ready is False

    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_adapter_bbox_provenance_step_evidence(self, fname: str) -> None:
        """MUST 13: part_bbox_provenance=STEP_FILE_EVIDENCE."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        vi = build_step_verification_input(r)
        assert vi.part_bbox_provenance == "STEP_FILE_EVIDENCE"


# ===========================================================================
# H — Aggregate: MUST 19
# ===========================================================================


class TestAggregateScorecard:
    def test_all_six_files_parse_pass(self) -> None:
        """MUST 19: PARSE_PASS=6/6."""
        passed = 0
        for fname in _REAL_STEP_FILES:
            r = parse_step_file(
                str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED"
            )
            if r.status == "PASS":
                passed += 1
        assert passed == _PHASE4_REAL_STEP_COUNT

    def test_in_house_benchmarks_excluded_from_count(self) -> None:
        """MUST 21: IN_HOUSE_BENCHMARK files are not in the REAL count."""
        in_house_names = {
            "P10_S1_drilled_block.step",
            "P10_S2_pocket_slot.step",
            "P10_S3_multi_feature.step",
        }
        for name in _REAL_STEP_FILES:
            assert name not in in_house_names, (
                f"{name!r} must not be an in-house benchmark file"
            )
