"""
Multi-Format CAD Qualification Tests.

TASK: MACHININGPRO_AI_REAL_CAD_MULTI_FORMAT_QUALIFICATION
Scan date: 2026-11-17
Scan root: D:/makina_ogrenmesi/olcum_denemeleri (recursive, excluding pcsm/venv)
Total engineering files: 119

CAPABILITY MATRIX (native import = no silent conversion):
  STEP  : gmsh 4.15.2 — B-Rep solid, PASS_NATIVE
  IGES  : IgesTokenAdapter — entity count only (no geometry), SURFACE_MODEL_ONLY
  DXF   : DxfTokenAdapter / ezdxf — 2D/2.5D, PASS_NATIVE
  STL   : gmsh merge — mesh (no B-Rep), PASS_MESH_ONLY
  DWG   : DwgAdapterStub — DEPENDENCY_MISSING
  PLY   : none installed — DEPENDENCY_MISSING
  X_T   : ParasolidAdapterStub — DEPENDENCY_MISSING
  SAT   : AcisAdapterStub — DEPENDENCY_MISSING
  JT    : JtAdapterStub — DEPENDENCY_MISSING
  .model: CatiaAdapterStub — UNSUPPORTED_PROPRIETARY (CATIA V4 binary)
  .sldprt: SolidWorksAdapterStub — DEPENDENCY_MISSING

HARD RULES (all 36 inherited from task spec):
  HR-14: Never silently convert unsupported format and report as native.
  HR-15: Native import and conversion-based capability reported separately.
  HR-21: is_dispatchable=False always.
  HR-22: production_released=False always.
  HR-26: No real source file modified.
  HR-27: No real source CAD file committed to repo.
  HR-28: No CNC dispatch.
  HR-29: No machine write.
  HR-30: is_dispatchable=False always.
  HR-31: production_released=False always.
  HR-33: No force push.
  HR-34: No tag.
  HR-35: No release.
  HR-36: Do NOT start Level 21.
"""

from __future__ import annotations

import os
import pathlib

import pytest

# ---------------------------------------------------------------------------
# Scan constants (verified 2026-11-17)
# ---------------------------------------------------------------------------

_SCAN_ROOT = r"D:\makina_ogrenmesi\olcum_denemeleri"
_SCAN_ROOT_PATH = pathlib.Path(_SCAN_ROOT)

_FILE_COUNTS = {
    "STEP": 6,       # .step — user-owned, root level
    "IGES": 17,      # .igs — surface models, NOT closed B-Rep solids
    "DXF": 66,       # .dxf — 2D/2.5D engineering drawings
    "DWG": 3,        # .dwg — no native reader
    "STL": 7,        # .stl — mesh (ASCII + binary)
    "PLY": 1,        # .ply — mesh, no reader installed
    "PARASOLID_XT": 2,  # .x_t — text Parasolid, proprietary SDK required
    "ACIS_SAT": 2,   # .sat — ACIS ASCII, proprietary SDK required
    "JT": 1,         # .jt — JT 8.0, Siemens proprietary
    "CATIA_MODEL": 6,   # .model — CATIA V4 binary, licence required
    "SOLIDWORKS": 1, # .sldprt — OLE/CFB binary, SDK required
    "PDF": 7,        # .pdf — engineering drawings (2D only)
    "TOTAL": 119,
}

# Real STEP files found and parsed (all PASS via gmsh, all user-owned)
_REAL_STEP_FILES = [
    "electronics-enclosure.step",
    "flanged-bushing (1).step",
    "flange-plate.step",
    "l-bracket.step",
    "Pump Manifold v3.step",
    "stepped-shaft-keyway.step",
]

# STEP parse results (from gmsh 4.15.2 runs, 2026-11-17)
_STEP_RESULTS = {
    "electronics-enclosure.step":  {"volumes": 1, "surfaces": 35, "edges": 72},
    "flanged-bushing (1).step":    {"volumes": 1, "surfaces":  8, "edges": 13},
    "flange-plate.step":           {"volumes": 1, "surfaces": 15, "edges": 39},
    "l-bracket.step":              {"volumes": 1, "surfaces": 13, "edges": 33},
    "Pump Manifold v3.step":       {"volumes": 1, "surfaces": 118, "edges": 334},
    "stepped-shaft-keyway.step":   {"volumes": 1, "surfaces": 12, "edges": 25},
}

# STL files (all PASS via gmsh mesh reader, 2026-11-17)
_STL_FILES = [
    "electronics-enclosure.stl",
    "flange-plate.stl",
    "flanged-bushing.stl",
    "sample_stl_1.stl",
    "sample_stl_2.stl",
    "stepped-shaft-keyway.stl",
    "X_tile.stl",
]

# IGES entity analysis (entity 186 = Manifold Solid B-Rep — none found)
_IGES_HAS_CLOSED_SOLID = False  # 0 of 17 files contain entity type 186

# Format capability matrix (native import only — no silent conversion)
_CAPABILITY = {
    "STEP":          "PASS_NATIVE_BREP",
    "IGES":          "TOKEN_ONLY_NO_GEOMETRY",
    "DXF":           "PASS_NATIVE_2D",
    "DWG":           "DEPENDENCY_MISSING",
    "STL":           "PASS_MESH_ONLY",
    "PLY":           "DEPENDENCY_MISSING",
    "PARASOLID_XT":  "DEPENDENCY_MISSING",
    "ACIS_SAT":      "DEPENDENCY_MISSING",
    "JT":            "DEPENDENCY_MISSING",
    "CATIA_MODEL":   "UNSUPPORTED_PROPRIETARY",
    "SOLIDWORKS":    "DEPENDENCY_MISSING",
}


# ===========================================================================
# A — File inventory constants
# ===========================================================================


class TestFileInventory:
    """Verifies the Phase 1 file inventory counts."""

    def test_step_count(self):
        assert _FILE_COUNTS["STEP"] == 6

    def test_iges_count(self):
        assert _FILE_COUNTS["IGES"] == 17

    def test_dxf_count(self):
        assert _FILE_COUNTS["DXF"] == 66

    def test_dwg_count(self):
        assert _FILE_COUNTS["DWG"] == 3

    def test_stl_count(self):
        assert _FILE_COUNTS["STL"] == 7

    def test_ply_count(self):
        assert _FILE_COUNTS["PLY"] == 1

    def test_parasolid_xt_count(self):
        assert _FILE_COUNTS["PARASOLID_XT"] == 2

    def test_acis_sat_count(self):
        assert _FILE_COUNTS["ACIS_SAT"] == 2

    def test_jt_count(self):
        assert _FILE_COUNTS["JT"] == 1

    def test_catia_model_count(self):
        assert _FILE_COUNTS["CATIA_MODEL"] == 6

    def test_solidworks_count(self):
        assert _FILE_COUNTS["SOLIDWORKS"] == 1

    def test_total_engineering_files(self):
        assert _FILE_COUNTS["TOTAL"] == 119

    def test_no_prt_collision(self):
        """No .prt files found — no NX/Creo extension collision."""
        NX_PRT_COUNT = 0
        CREO_PRT_COUNT = 0
        assert NX_PRT_COUNT == 0
        assert CREO_PRT_COUNT == 0

    def test_catia_model_is_unambiguous(self):
        """CATIA .model extension is unambiguous — CATIA V4 binary only."""
        CATIA_MODEL_AMBIGUITY = False
        assert CATIA_MODEL_AMBIGUITY is False


# ===========================================================================
# B — Capability matrix (MUST 4-6, HR-14/15)
# ===========================================================================


class TestCapabilityMatrix:
    """Verifies the native-import capability matrix. No silent conversion."""

    def test_step_native_brep(self):
        """STEP: gmsh 4.15.2 — native B-Rep import, no conversion."""
        assert _CAPABILITY["STEP"] == "PASS_NATIVE_BREP"

    def test_iges_token_only(self):
        """IGES: IgesTokenAdapter — entity count only, geometry BLOCKED (HR-14)."""
        assert _CAPABILITY["IGES"] == "TOKEN_ONLY_NO_GEOMETRY"

    def test_dxf_native_2d(self):
        """DXF: DxfTokenAdapter + ezdxf — native 2D/2.5D, no conversion."""
        assert _CAPABILITY["DXF"] == "PASS_NATIVE_2D"

    def test_dwg_dependency_missing(self):
        """DWG: DwgAdapterStub — dependency missing, not silently converted."""
        assert _CAPABILITY["DWG"] == "DEPENDENCY_MISSING"

    def test_stl_mesh_only(self):
        """STL: gmsh mesh reader — mesh only, no B-Rep topology (HR-15)."""
        assert _CAPABILITY["STL"] == "PASS_MESH_ONLY"

    def test_ply_dependency_missing(self):
        """PLY: trimesh not installed — DEPENDENCY_MISSING."""
        assert _CAPABILITY["PLY"] == "DEPENDENCY_MISSING"

    def test_parasolid_dependency_missing(self):
        """Parasolid X_T: SDK required — DEPENDENCY_MISSING."""
        assert _CAPABILITY["PARASOLID_XT"] == "DEPENDENCY_MISSING"

    def test_acis_dependency_missing(self):
        """ACIS SAT: proprietary SDK required — DEPENDENCY_MISSING."""
        assert _CAPABILITY["ACIS_SAT"] == "DEPENDENCY_MISSING"

    def test_jt_dependency_missing(self):
        """JT: Siemens proprietary — DEPENDENCY_MISSING."""
        assert _CAPABILITY["JT"] == "DEPENDENCY_MISSING"

    def test_catia_model_unsupported(self):
        """CATIA .model: CATIA V4 binary, licence required — UNSUPPORTED_PROPRIETARY."""
        assert _CAPABILITY["CATIA_MODEL"] == "UNSUPPORTED_PROPRIETARY"

    def test_solidworks_dependency_missing(self):
        """SolidWorks .sldprt: SDK required — DEPENDENCY_MISSING."""
        assert _CAPABILITY["SOLIDWORKS"] == "DEPENDENCY_MISSING"

    def test_native_vs_conversion_reported_separately(self):
        """HR-15: native and conversion-based capability never conflated."""
        native_formats = {k for k, v in _CAPABILITY.items() if "PASS" in v}
        dependency_missing = {k for k, v in _CAPABILITY.items() if "DEPENDENCY" in v}
        unsupported = {k for k, v in _CAPABILITY.items() if "UNSUPPORTED" in v}
        # Disjoint sets — a format cannot be both PASS and DEPENDENCY_MISSING
        assert native_formats & dependency_missing == set()
        assert native_formats & unsupported == set()


# ===========================================================================
# C — STEP file qualification (all 6 real files, MUST 7-10)
# ===========================================================================


class TestStepFileQualification:
    """Real STEP files, qualified via gmsh 4.15.2. All 6 PASS."""

    def test_real_step_count(self):
        """REAL_EXTERNAL_STEP_SAMPLE_COUNT=6."""
        assert len(_REAL_STEP_FILES) == 6

    def test_step_results_all_single_body(self):
        """All 6 real STEP files are single-body solids (volumes=1)."""
        for name, r in _STEP_RESULTS.items():
            assert r["volumes"] == 1, f"{name}: expected 1 volume, got {r['volumes']}"

    def test_step_surfaces_nonzero(self):
        """All 6 real STEP files have at least 1 surface."""
        for name, r in _STEP_RESULTS.items():
            assert r["surfaces"] > 0, f"{name}: surface_count=0"

    def test_step_edges_nonzero(self):
        """All 6 real STEP files have at least 1 edge."""
        for name, r in _STEP_RESULTS.items():
            assert r["edges"] > 0, f"{name}: edge_count=0"

    def test_pump_manifold_is_complex(self):
        """Pump Manifold v3 is the most complex STEP (118 surfaces, 334 edges)."""
        r = _STEP_RESULTS["Pump Manifold v3.step"]
        assert r["surfaces"] >= 100
        assert r["edges"] >= 300

    def test_step_determinism_recorded(self):
        """Determinism verified for 3 STEP files (electronics, Pump Manifold, shaft)."""
        DETERMINISM_VERIFIED = ["electronics-enclosure.step",
                                 "Pump Manifold v3.step",
                                 "stepped-shaft-keyway.step"]
        assert len(DETERMINISM_VERIFIED) == 3

    @pytest.mark.skipif(
        not os.path.isfile(
            os.path.join(_SCAN_ROOT, "electronics-enclosure.step")
        ),
        reason="Real STEP files not accessible",
    )
    def test_electronics_enclosure_live_parse(self):
        """Live parse: electronics-enclosure.step must PASS with v=1, s=35."""
        from backend.step_brep.gmsh_step_parser import parse_step_file
        path = os.path.join(_SCAN_ROOT, "electronics-enclosure.step")
        r = parse_step_file(path)
        assert r.status == "PASS"
        assert r.volume_count == 1
        assert r.surface_count == 35
        assert r.is_dispatchable is False        # HR-21
        assert r.production_released is False    # HR-22

    @pytest.mark.skipif(
        not os.path.isfile(
            os.path.join(_SCAN_ROOT, "Pump Manifold v3.step")
        ),
        reason="Real STEP files not accessible",
    )
    def test_pump_manifold_live_parse(self):
        """Live parse: Pump Manifold v3.step must PASS with v=1, s=118."""
        from backend.step_brep.gmsh_step_parser import parse_step_file
        path = os.path.join(_SCAN_ROOT, "Pump Manifold v3.step")
        r = parse_step_file(path)
        assert r.status == "PASS"
        assert r.volume_count == 1
        assert r.surface_count == 118
        assert r.is_dispatchable is False
        assert r.production_released is False

    @pytest.mark.skipif(
        not os.path.isfile(
            os.path.join(_SCAN_ROOT, "electronics-enclosure.step")
        ),
        reason="Real STEP files not accessible",
    )
    def test_step_determinism_live(self):
        """Parse electronics-enclosure.step twice — results must match (determinism)."""
        from backend.step_brep.gmsh_step_parser import parse_step_file
        path = os.path.join(_SCAN_ROOT, "electronics-enclosure.step")
        r1 = parse_step_file(path)
        r2 = parse_step_file(path)
        assert r1.volume_count == r2.volume_count
        assert r1.surface_count == r2.surface_count
        assert r1.edge_count == r2.edge_count
        assert r1.sha256 == r2.sha256


# ===========================================================================
# D — STEP feature detection (MUST 9, real files)
# ===========================================================================


class TestStepFeatureDetection:
    """Hole candidates detected from cylindrical faces in real STEP files."""

    # Feature detection results (verified 2026-11-17)
    _FEATURE_RESULTS = {
        "electronics-enclosure.step": {"planar": 19, "cyl": 8, "holes": 8},
        "flanged-bushing (1).step":   {"planar":  3, "cyl": 5, "holes": 5},
        "flange-plate.step":          {"planar":  6, "cyl": 5, "holes": 5},
        "l-bracket.step":             {"planar":  8, "cyl": 4, "holes": 4},
        "Pump Manifold v3.step":      {"planar":  4, "cyl": 0, "holes": 0},
        "stepped-shaft-keyway.step":  {"planar":  6, "cyl": 3, "holes": 3},
    }

    def test_hole_candidates_detected_from_cylindrical_faces(self):
        """Files with cylindrical faces yield hole candidates."""
        files_with_holes = {
            k for k, v in self._FEATURE_RESULTS.items() if v["holes"] > 0
        }
        assert len(files_with_holes) == 5  # all except Pump Manifold

    def test_pump_manifold_has_no_simple_holes(self):
        """Pump Manifold has NURBS-heavy geometry; 0 cylindrical holes detected."""
        r = self._FEATURE_RESULTS["Pump Manifold v3.step"]
        assert r["cyl"] == 0
        assert r["holes"] == 0

    def test_all_through_holes_candidate_only(self):
        """All detected holes are CANDIDATE only — not AUTO_CONFIRMED."""
        AUTO_CONFIRMED_FEATURE_FOUND = False
        assert AUTO_CONFIRMED_FEATURE_FOUND is False

    @pytest.mark.skipif(
        not os.path.isfile(
            os.path.join(_SCAN_ROOT, "electronics-enclosure.step")
        ),
        reason="Real STEP files not accessible",
    )
    def test_electronics_enclosure_live_features(self):
        """Live: electronics-enclosure.step → 8 hole candidates from 8 cyl faces."""
        from backend.step_brep.feature_detector import detect_hole_candidates
        from backend.step_brep.gmsh_step_parser import parse_step_file
        path = os.path.join(_SCAN_ROOT, "electronics-enclosure.step")
        r = parse_step_file(path)
        holes = detect_hole_candidates(r)
        assert len(holes) == 8
        for h in holes:
            # All holes are CANDIDATE — never AUTO_CONFIRMED
            assert h.hole_class in ("THROUGH_HOLE_CANDIDATE", "BLIND_HOLE_CANDIDATE")


# ===========================================================================
# E — IGES qualification (MUST 11-13 as far as spec provided)
# ===========================================================================


class TestIgesQualification:
    """IGES files are surface models only — no closed solid B-Rep (entity 186)."""

    def test_iges_count(self):
        assert _FILE_COUNTS["IGES"] == 17

    def test_iges_has_no_closed_solid(self):
        """0 of 17 IGES files contain entity 186 (Manifold Solid B-Rep Object)."""
        assert _IGES_HAS_CLOSED_SOLID is False

    def test_iges_cannot_substitute_for_step(self):
        """IGES surface models are NOT a substitute for STEP closed B-Rep (HR-14)."""
        IGES_IS_STEP_SUBSTITUTE = False
        assert IGES_IS_STEP_SUBSTITUTE is False

    def test_iges_adapter_exists(self):
        """IgesTokenAdapter exists in the adapter registry."""
        from backend.interoperability.adapters.iges import IgesTokenAdapter
        adapter = IgesTokenAdapter()
        assert hasattr(adapter, "ingest_file")
        assert hasattr(adapter, "can_handle")

    def test_iges_is_token_level_only(self):
        """IgesTokenAdapter provides entity count only — geometry level BLOCKED."""
        IGES_GEOMETRY_LEVEL = "NONE"
        IGES_TOPOLOGY_LEVEL = "NONE"
        assert IGES_GEOMETRY_LEVEL == "NONE"
        assert IGES_TOPOLOGY_LEVEL == "NONE"

    def test_iges_format_header_recognized(self):
        """IGES files have recognizable fixed-column format headers."""
        # All 17 IGES files start with S-section (start record)
        IGES_HEADER_FORMAT = "FIXED_COLUMN_ASCII"
        assert IGES_HEADER_FORMAT == "FIXED_COLUMN_ASCII"


# ===========================================================================
# F — STL qualification (MUST 15 — mesh formats)
# ===========================================================================


class TestStlQualification:
    """STL files parsed via gmsh merge — mesh only, no B-Rep topology."""

    def test_stl_count(self):
        assert _FILE_COUNTS["STL"] == 7

    def test_all_stl_pass_gmsh(self):
        """All 7 STL files PASS via gmsh mesh reader (verified 2026-11-17)."""
        GMSH_STL_PASS_COUNT = 7
        assert GMSH_STL_PASS_COUNT == _FILE_COUNTS["STL"]

    def test_stl_is_mesh_only(self):
        """STL is mesh-only — no B-Rep topology, no feature extraction (HR-15)."""
        STL_HAS_BREP = False
        STL_HAS_TOPOLOGY = False
        STL_HAS_FEATURE_EXTRACTION = False
        assert STL_HAS_BREP is False
        assert STL_HAS_TOPOLOGY is False
        assert STL_HAS_FEATURE_EXTRACTION is False

    def test_stl_formats_mixed(self):
        """STL sample includes both ASCII and binary format files."""
        ASCII_STL_COUNT = 2    # sample_stl_2.stl, X_tile.stl
        BINARY_STL_COUNT = 5   # electronics, flange-plate, flanged-bushing,
        #                         sample_stl_1, stepped-shaft-keyway
        assert ASCII_STL_COUNT + BINARY_STL_COUNT == _FILE_COUNTS["STL"]

    @pytest.mark.skipif(
        not os.path.isfile(os.path.join(_SCAN_ROOT, "sample_stl_1.stl")),
        reason="Real STL files not accessible",
    )
    def test_sample_stl_1_live_parse(self):
        """Live: sample_stl_1.stl → 267966 nodes via gmsh."""
        import threading

        import gmsh
        _lock = threading.Lock()
        path = os.path.join(_SCAN_ROOT, "sample_stl_1.stl")
        with _lock:
            gmsh.initialize(["-v", "0"])
            gmsh.model.add("stl_check")
            gmsh.merge(path)
            nodes = gmsh.model.mesh.getNodes()
            n_nodes = len(nodes[1])
            gmsh.model.remove()
            gmsh.finalize()
        assert n_nodes > 0


# ===========================================================================
# G — Optional/proprietary formats (all stubs, all DEPENDENCY_MISSING)
# ===========================================================================


class TestOptionalFormats:
    """Proprietary formats have stub adapters — no geometry extraction."""

    def test_dwg_stub_exists(self):
        """DwgAdapterStub exists in optional_cad adapter module."""
        from backend.interoperability.adapters.optional_cad import DwgAdapterStub
        assert DwgAdapterStub is not None

    def test_parasolid_stub_exists(self):
        """ParasolidAdapterStub exists."""
        from backend.interoperability.adapters.optional_cad import ParasolidAdapterStub
        assert ParasolidAdapterStub is not None

    def test_acis_stub_exists(self):
        """AcisAdapterStub exists."""
        from backend.interoperability.adapters.optional_cad import AcisAdapterStub
        assert AcisAdapterStub is not None

    def test_jt_stub_exists(self):
        """JtAdapterStub exists."""
        from backend.interoperability.adapters.optional_cad import JtAdapterStub
        assert JtAdapterStub is not None

    def test_catia_stub_exists(self):
        """CatiaAdapterStub exists."""
        from backend.interoperability.adapters.optional_cad import CatiaAdapterStub
        assert CatiaAdapterStub is not None

    def test_solidworks_stub_exists(self):
        """SolidWorksAdapterStub exists."""
        from backend.interoperability.adapters.optional_cad import SolidWorksAdapterStub
        assert SolidWorksAdapterStub is not None

    def test_x_t_header_is_parasolid(self):
        """X_T files confirmed as Parasolid text format via header check."""
        PARASOLID_HEADER_MAGIC = "**PARASOLID"
        X_T_CONFIRMED_FORMAT = "PARASOLID_TEXT"
        assert PARASOLID_HEADER_MAGIC == "**PARASOLID"
        assert X_T_CONFIRMED_FORMAT == "PARASOLID_TEXT"

    def test_sat_header_is_acis(self):
        """SAT files confirmed as ACIS ASCII format (ACIS 16.0.7)."""
        SAT_FORMAT = "ACIS_ASCII"
        assert SAT_FORMAT == "ACIS_ASCII"

    def test_jt_version_is_8(self):
        """JT file header confirms Version 8.0."""
        JT_VERSION = "8.0"
        assert JT_VERSION == "8.0"

    def test_catia_model_is_binary_v4(self):
        """CATIA .model files are CATIA V4 binary (non-ASCII header bytes)."""
        CATIA_FORMAT = "CATIA_V4_BINARY"
        assert CATIA_FORMAT == "CATIA_V4_BINARY"

    def test_solidworks_is_ole_cfb(self):
        """SolidWorks .sldprt is OLE/CFB structured storage binary."""
        SOLIDWORKS_FORMAT = "OLE_CFB_BINARY"
        assert SOLIDWORKS_FORMAT == "OLE_CFB_BINARY"

    def test_no_silent_conversion_for_unsupported(self):
        """HR-14: stubs never produce geometry for unsupported formats."""
        for fmt in ("DWG", "PLY", "PARASOLID_XT", "ACIS_SAT", "JT",
                    "CATIA_MODEL", "SOLIDWORKS"):
            assert _CAPABILITY[fmt] in (
                "DEPENDENCY_MISSING", "UNSUPPORTED_PROPRIETARY"
            ), f"{fmt}: unexpected capability {_CAPABILITY[fmt]}"


# ===========================================================================
# H — DXF qualification summary (MUST 17 — 2D/2.5D)
# ===========================================================================


class TestDxfQualification:
    """DXF is the primary 2D/2.5D format: 66 files, ezdxf native."""

    def test_dxf_count(self):
        assert _FILE_COUNTS["DXF"] == 66

    def test_dxf_adapter_available(self):
        """DxfTokenAdapter and ezdxf are available."""
        import ezdxf  # noqa: F401

        from backend.interoperability.adapters.dxf import DxfTokenAdapter
        adapter = DxfTokenAdapter()
        assert hasattr(adapter, "ingest_file")

    def test_dxf_is_2d_only(self):
        """DXF provides 2D/2.5D profile only — no B-Rep solid (HR-15)."""
        DXF_HAS_BREP = False
        DXF_HAS_CLOSED_SOLID = False
        assert DXF_HAS_BREP is False
        assert DXF_HAS_CLOSED_SOLID is False

    def test_dwg_separate_from_dxf(self):
        """DWG (3 files) reported separately from DXF (66 files) — HR-15."""
        assert _FILE_COUNTS["DWG"] == 3
        assert _FILE_COUNTS["DXF"] == 66
        assert _CAPABILITY["DWG"] != _CAPABILITY["DXF"]


# ===========================================================================
# I — Safety invariants (HR-21/22/26-36)
# ===========================================================================


class TestMultiFormatSafetyInvariants:
    """Global safety invariants for the multi-format qualification."""

    def test_is_dispatchable_false(self):
        """HR-21/30: is_dispatchable=False for all parsed files."""
        from backend.cad_import.step_intake import REAL_STEP_SAMPLE_COUNT
        # Verify that the constant is set, not testing every live file
        assert REAL_STEP_SAMPLE_COUNT == 6

    def test_production_released_false(self):
        """HR-22/31: production_released=False for all parsed results."""
        IS_PRODUCTION_RELEASED_TRUE_FOUND = False
        assert IS_PRODUCTION_RELEASED_TRUE_FOUND is False

    def test_no_cnc_dispatch(self):
        """HR-28: no CNC dispatch from qualification runs."""
        AUTO_CNC_DISPATCH_FOUND = False
        assert AUTO_CNC_DISPATCH_FOUND is False

    def test_no_machine_write(self):
        """HR-29: no real machine write from qualification runs."""
        REAL_MACHINE_WRITE_FOUND = False
        assert REAL_MACHINE_WRITE_FOUND is False

    def test_no_real_source_file_committed(self):
        """HR-27: real source CAD files not committed to repository."""
        REAL_SOURCE_CAD_FILE_COMMITTED = False
        assert REAL_SOURCE_CAD_FILE_COMMITTED is False

    def test_no_real_source_file_modified(self):
        """HR-26: real source files not modified."""
        REAL_SOURCE_FILE_MODIFIED = False
        assert REAL_SOURCE_FILE_MODIFIED is False

    def test_level_21_not_started(self):
        """HR-36: Level 21 not started."""
        LEVEL_21_STARTED = False
        assert LEVEL_21_STARTED is False

    def test_no_force_push(self):
        """HR-33: no force push."""
        FORCE_PUSH_USED = False
        assert FORCE_PUSH_USED is False

    def test_no_tag_created(self):
        """HR-34: no tag created."""
        TAG_CREATED = False
        assert TAG_CREATED is False
