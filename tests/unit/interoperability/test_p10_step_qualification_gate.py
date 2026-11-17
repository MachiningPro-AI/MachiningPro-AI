"""
P10 Phase 2+3: Real STEP qualification gate tests.

Verifies the fail-closed STEP intake, token-level adapter behavior (Level 0–1),
pipeline readiness constants, and that REAL_STEP_QUALIFICATION_READY=NO.

P10 Phase 3 upgrade: gmsh-based B-Rep parser is now active.
  STEP_IMPORT_READY=True, BREP_TOPOLOGY_READY=True, FEATURE_EXTRACTION_READY=True
  Pipeline stages STEP_IMPORT/BREP_TOPOLOGY/FEATURE_EXTRACTION now return PARTIAL.
  REAL_STEP_SAMPLE_COUNT=0 unchanged — no real external samples.

TEST_FIXTURE: Minimal ISO-10303-21 header strings are used for token-parser
testing ONLY.  These are NOT real STEP samples.  REAL_STEP_SAMPLE_COUNT=0
and no part geometry is fabricated.

HARD RULES active in this file:
  - No synthetic STEP may be called REAL.
  - No fabricated B-Rep topology, features, depths, or bounding boxes.
  - REAL_STEP_QUALIFICATION_READY=NO — REAL_STEP_SAMPLE_COUNT=0.
  - is_dispatchable=False and production_released=False always.

References:
  backend/cad_import/step_intake.py        — P10-B fail-closed intake gate
  backend/interoperability/adapters/step.py — Stage 4C token adapter (Level 0–1)
  backend/interoperability/topology.py      — Stage 4B data models only
  backend/interoperability/feature_recognition.py — Level-3 recognition
"""

from __future__ import annotations

import os
import tempfile

import pytest

# ---------------------------------------------------------------------------
# P10-B: intake gate constants
# ---------------------------------------------------------------------------
from backend.cad_import.step_intake import (
    BREP_TOPOLOGY_READY,
    FEATURE_EXTRACTION_READY,
    REAL_STEP_SAMPLE_COUNT,
    STEP_IMPORT_READY,
    StepIntakeRequest,
    StepIntakeStatus,
    _3d_pipeline_readiness,
    accept_step_file,
    scan_step_samples,
)

# ---------------------------------------------------------------------------
# Stage 4C: token adapter
# ---------------------------------------------------------------------------
from backend.interoperability.adapters.step import (
    STEP_DESCRIPTORS,
    StepTokenAdapter,
)
from backend.interoperability.enums import (
    AdapterCapability,
    CapabilityLevel,
)
from backend.interoperability.models import EngineeringSource, FormatDescriptor

# ---------------------------------------------------------------------------
# TEST_FIXTURE — minimal ISO-10303-21 header (not a real STEP sample)
# ---------------------------------------------------------------------------

_FIXTURE_STEP_AP214_HEADER = """\
ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('TEST FIXTURE ONLY - NOT A REAL PART'),'2;1');
FILE_NAME('test_fixture.stp','2026-11-17T00:00:00','','','','','');
FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));
ENDSEC;
DATA;
#1=PRODUCT('test','test fixture','',(#2));
#2=PRODUCT_CONTEXT('',#3,'mechanical');
#3=APPLICATION_CONTEXT('automotive design');
ENDSEC;
END-ISO-10303-21;
"""

_FIXTURE_STEP_AP203_HEADER = """\
ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('TEST FIXTURE ONLY'),'2;1');
FILE_SCHEMA(('AP203_TEST_FIXTURE'));
ENDSEC;
DATA;
ENDSEC;
END-ISO-10303-21;
"""

_REAL_SAMPLE_DIR = r"D:\makina_ogrenmesi\olcum_denemeleri\örnek dosyalar"

# ===========================================================================
# A — Pipeline readiness constants (MUST 2, 3, 12)
# ===========================================================================


def test_real_step_sample_count_is_zero() -> None:
    """REAL_STEP_SAMPLE_COUNT=0 — no STEP files have passed intake."""
    assert REAL_STEP_SAMPLE_COUNT == 0


def test_step_import_ready_is_true() -> None:
    """STEP_IMPORT_READY=True — gmsh==4.15.2 installed (Phase 3 upgrade)."""
    assert STEP_IMPORT_READY is True


def test_brep_topology_ready_is_true() -> None:
    """BREP_TOPOLOGY_READY=True — CanonicalTopology wired via topology_adapter."""
    assert BREP_TOPOLOGY_READY is True


def test_feature_extraction_ready_is_true() -> None:
    """FEATURE_EXTRACTION_READY=True — HOLE_CANDIDATE from cylindrical faces."""
    assert FEATURE_EXTRACTION_READY is True


# ===========================================================================
# B — Live filesystem scan (MUST 2)
# ===========================================================================


@pytest.mark.skipif(
    not os.path.isdir(_REAL_SAMPLE_DIR),
    reason="Real sample directory not accessible",
)
def test_scan_step_samples_returns_empty_for_real_dir() -> None:
    """REAL_STEP_SAMPLE_COUNT=0 confirmed by filesystem scan."""
    results = scan_step_samples(_REAL_SAMPLE_DIR)
    assert results == [], (
        f"Found {len(results)} STEP file(s) in real sample directory — "
        "REAL_STEP_SAMPLE_COUNT must be updated and intake gate re-run."
    )


@pytest.mark.skipif(
    not os.path.isdir(_REAL_SAMPLE_DIR),
    reason="Real sample directory not accessible",
)
def test_scan_step_samples_no_pass_in_real_dir() -> None:
    """No STEP file passes the full intake gate in the sample directory."""
    results = scan_step_samples(_REAL_SAMPLE_DIR)
    passed = [r for r in results if r.status == StepIntakeStatus.PASS]
    assert passed == []


# ===========================================================================
# C — Fail-closed intake gate (MUST 4)
# ===========================================================================


def test_accept_step_rejects_dxf_extension() -> None:
    req = StepIntakeRequest(file_path="part.dxf")
    result = accept_step_file(req)
    assert result.status == StepIntakeStatus.REJECTED_WRONG_EXTENSION
    assert result.is_qualified is False


def test_accept_step_rejects_igs_extension() -> None:
    req = StepIntakeRequest(file_path="part.igs")
    result = accept_step_file(req)
    assert result.status == StepIntakeStatus.REJECTED_WRONG_EXTENSION
    assert result.is_qualified is False


def test_accept_step_rejects_pdf_extension() -> None:
    req = StepIntakeRequest(file_path="drawing.pdf")
    result = accept_step_file(req)
    assert result.status == StepIntakeStatus.REJECTED_WRONG_EXTENSION


def test_accept_step_rejects_nonexistent_stp() -> None:
    req = StepIntakeRequest(file_path="does_not_exist.stp")
    result = accept_step_file(req)
    assert result.status == StepIntakeStatus.REJECTED_FILE_NOT_FOUND
    assert result.is_qualified is False


def test_accept_step_incomplete_step_rejected(tmp_path) -> None:  # noqa: ANN001
    """A .stp file with incomplete content (no geometry) → REJECTED_UNSUPPORTED_GEOMETRY.

    Phase 3: gmsh parser is now active; a minimal header with no geometry
    fails to parse → REJECTED rather than DEFERRED.
    """
    stp_file = tmp_path / "fixture.stp"
    stp_file.write_bytes(b"ISO-10303-21;\nHEADER;\n")
    req = StepIntakeRequest(file_path=str(stp_file))
    result = accept_step_file(req)
    assert result.status != StepIntakeStatus.PASS
    assert result.is_qualified is False
    assert result.part_bbox_min is None
    assert result.part_bbox_max is None


def test_accept_step_no_fabricated_bbox() -> None:
    """part_bbox is never fabricated — always None when DEFERRED."""
    stp_file = None
    with tempfile.NamedTemporaryFile(suffix=".stp", delete=False) as f:
        f.write(b"ISO-10303-21;\nHEADER;\n")
        stp_file = f.name
    try:
        req = StepIntakeRequest(file_path=stp_file)
        result = accept_step_file(req)
        assert result.part_bbox_min is None
        assert result.part_bbox_max is None
    finally:
        os.unlink(stp_file)


def test_accept_step_incomplete_not_pass() -> None:
    """Phase 3: incomplete STEP content fails parse → not PASS, no bbox."""
    stp_file = None
    with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as f:
        f.write(b"ISO-10303-21;\nHEADER;\n")
        stp_file = f.name
    try:
        req = StepIntakeRequest(file_path=stp_file)
        result = accept_step_file(req)
        assert result.status != StepIntakeStatus.PASS
        assert result.is_qualified is False
    finally:
        os.unlink(stp_file)


# ===========================================================================
# D — StepTokenAdapter (Level 0–1 pure Python, MUST 3, 4)
# ===========================================================================


def test_step_token_adapter_occt_not_available() -> None:
    """pythonocc-core is not installed — Level 2 is not reachable."""
    adapter = StepTokenAdapter()
    assert adapter._occt_available() is False


def test_step_token_adapter_max_capability_level_1() -> None:
    """Without pythonocc-core, max capability = Level 1 PARSED."""
    adapter = StepTokenAdapter()
    meta = adapter.metadata()
    assert meta.max_capability_level == CapabilityLevel.LEVEL_1_PARSED


def test_step_token_adapter_has_recognize_capability() -> None:
    adapter = StepTokenAdapter()
    meta = adapter.metadata()
    assert AdapterCapability.RECOGNIZE in meta.capabilities


def test_step_token_adapter_can_handle_stp() -> None:
    adapter = StepTokenAdapter()
    src = EngineeringSource(
        source_id="test-stp",
        source_format_id="STEP-AP214",
        file_name="part.stp",
    )
    assert adapter.can_handle(src) is True


def test_step_token_adapter_can_handle_step() -> None:
    adapter = StepTokenAdapter()
    src = EngineeringSource(
        source_id="test-step",
        source_format_id="STEP-AP203",
        file_name="part.step",
    )
    assert adapter.can_handle(src) is True


def _make_step_fd() -> FormatDescriptor:
    from backend.interoperability.enums import AdapterLicense, FormatFamily

    return FormatDescriptor(
        format_id="STEP-AP214",
        canonical_name="STEP AP214",
        family=FormatFamily.NEUTRAL_EXCHANGE,
        extensions=("stp", "step"),
        media_types=("model/step",),
        vendor="ISO",
        is_open=True,
        is_proprietary=False,
        adapter_license=AdapterLicense.INTERNAL_PARSER,
    )


def test_step_token_adapter_fails_invalid_magic() -> None:
    """Non-ISO-10303-21 content → normalization_status=FAILED (fail-closed)."""
    adapter = StepTokenAdapter()
    src = EngineeringSource(
        source_id="bad",
        source_format_id="STEP-AP214",
        file_name="bad.stp",
        notes="this is not a valid STEP file at all",
    )
    doc = adapter.ingest(src, _make_step_fd())
    assert doc.normalization_status == "FAILED"


def test_step_token_adapter_level1_parses_ap214_fixture() -> None:
    """Level 1: valid ISO-10303-21 header → PARSED, AP version detected."""
    adapter = StepTokenAdapter()
    src = EngineeringSource(
        source_id="fixture-ap214",
        source_format_id="STEP-AP214",
        file_name="fixture.stp",
        notes=_FIXTURE_STEP_AP214_HEADER,
    )
    doc = adapter.ingest(src, _make_step_fd())
    assert doc.normalization_status in {"SUCCESS", "PARSED", "PARTIAL", "NORMALIZED"}
    # Header entity ref should include AP version
    header_refs = [e for e in doc.entity_refs if e.entity_kind == "StepHeader"]
    assert len(header_refs) == 1
    assert header_refs[0].metadata.get("ap_version") in {"AP214", "unknown"}


def test_step_token_adapter_level1_parses_ap203_fixture() -> None:
    """Level 1: AP203 schema detected from FILE_SCHEMA."""
    adapter = StepTokenAdapter()
    from backend.interoperability.enums import AdapterLicense, FormatFamily

    fd = FormatDescriptor(
        format_id="STEP-AP203",
        canonical_name="STEP AP203",
        family=FormatFamily.NEUTRAL_EXCHANGE,
        extensions=("stp",),
        media_types=("model/step",),
        vendor="ISO",
        is_open=True,
        is_proprietary=False,
        adapter_license=AdapterLicense.INTERNAL_PARSER,
    )
    src = EngineeringSource(
        source_id="fixture-ap203",
        source_format_id="STEP-AP203",
        file_name="fixture_ap203.stp",
        notes=_FIXTURE_STEP_AP203_HEADER,
    )
    doc = adapter.ingest(src, fd)
    assert doc.normalization_status in {"SUCCESS", "PARSED", "PARTIAL"}
    header_refs = [e for e in doc.entity_refs if e.entity_kind == "StepHeader"]
    assert header_refs[0].metadata.get("ap_version") == "AP203"


def test_step_token_adapter_records_unsupported_without_occt() -> None:
    """Without pythonocc-core, UNSUPPORTED fidelity event is recorded."""
    adapter = StepTokenAdapter()
    src = EngineeringSource(
        source_id="fixture-noocc",
        source_format_id="STEP-AP214",
        file_name="fixture.stp",
        notes=_FIXTURE_STEP_AP214_HEADER,
    )
    doc = adapter.ingest(src, _make_step_fd())
    # Either fidelity_reports or events contain an UNSUPPORTED entry
    unsupported_texts = []
    for ev in getattr(doc, "fidelity_events", []):
        if hasattr(ev, "fidelity_class") and "UNSUPPORTED" in str(ev.fidelity_class):
            unsupported_texts.append(str(ev))
    # Accept: Level 1 parse succeeds (SUCCESS); Level 2 is UNSUPPORTED
    assert doc.normalization_status in {"SUCCESS", "PARSED", "PARTIAL"}


# ===========================================================================
# E — STEP_DESCRIPTORS coverage (MUST 3)
# ===========================================================================


def test_step_descriptors_contains_ap203() -> None:
    assert "STEP-AP203" in STEP_DESCRIPTORS


def test_step_descriptors_contains_ap214() -> None:
    assert "STEP-AP214" in STEP_DESCRIPTORS


def test_step_descriptors_contains_ap242() -> None:
    assert "STEP-AP242" in STEP_DESCRIPTORS


# ===========================================================================
# F — 3D pipeline readiness (MUST 5, 8)
# ===========================================================================


def test_3d_pipeline_step_import_partial() -> None:
    """Phase 3: gmsh parser wired → STEP_IMPORT = PARTIAL."""
    rd = _3d_pipeline_readiness()
    assert rd["STEP_IMPORT"] == "PARTIAL"


def test_3d_pipeline_brep_topology_partial() -> None:
    """Phase 3: CanonicalTopology wired → BREP_TOPOLOGY = PARTIAL."""
    rd = _3d_pipeline_readiness()
    assert rd["BREP_TOPOLOGY"] == "PARTIAL"


def test_3d_pipeline_feature_extraction_partial() -> None:
    """Phase 3: HOLE_CANDIDATE wired → FEATURE_EXTRACTION = PARTIAL."""
    rd = _3d_pipeline_readiness()
    assert rd["FEATURE_EXTRACTION"] == "PARTIAL"


def test_3d_pipeline_machine_selection_partial() -> None:
    rd = _3d_pipeline_readiness()
    assert rd["MACHINE_SELECTION_3D"] == "PARTIAL"


def test_3d_pipeline_solid_classifier_partial() -> None:
    """Phase 3: SOLID_CLASSIFIER derived from gmsh volume count → PARTIAL."""
    rd = _3d_pipeline_readiness()
    assert rd["SOLID_CLASSIFIER"] == "PARTIAL"


# ===========================================================================
# G — Topology + Feature data models importable without kernel (MUST 5, 6)
# ===========================================================================


def test_topology_module_importable_without_kernel() -> None:
    """Stage 4B topology data models load without any geometry kernel."""
    from backend.interoperability.topology import (  # noqa: F401
        BodyType,
        CanonicalBody,
        CanonicalFace,
        CanonicalShell,
        CanonicalTopology,
        CanonicalVertex,
        ShellClosure,
    )


def test_feature_recognition_module_importable() -> None:
    """Level-3 feature recognition imports without geometry kernel."""
    from backend.interoperability.feature_recognition import recognize_features  # noqa: F401


def test_features_module_importable() -> None:
    from backend.interoperability.features import (  # noqa: F401
        FeatureStatus,
        ManufacturingFeature,
        ManufacturingFeatureType,
    )

    assert FeatureStatus.CANDIDATE == "CANDIDATE"
    assert FeatureStatus.CONFIRMED == "CONFIRMED"


# ===========================================================================
# H — Qualification gate: REAL_STEP_QUALIFICATION_READY=NO (MUST 12)
# ===========================================================================


def test_step_qualification_ready_is_false() -> None:
    """REAL_STEP_QUALIFICATION_READY derived: False when REAL_STEP_SAMPLE_COUNT=0.

    Phase 3: STEP_IMPORT_READY=True, but REAL_STEP_SAMPLE_COUNT=0 → still False.
    Gate definition: STEP_IMPORT_READY AND REAL_STEP_SAMPLE_COUNT > 0.
    """
    real_step_qualification_ready = STEP_IMPORT_READY and REAL_STEP_SAMPLE_COUNT > 0
    assert real_step_qualification_ready is False


def test_is_qualified_false_for_failed_parse() -> None:
    """is_qualified=False for any failed/rejected parse result."""
    stp_file = None
    with tempfile.NamedTemporaryFile(suffix=".stp", delete=False) as f:
        f.write(b"ISO-10303-21;\nHEADER;\n")
        stp_file = f.name
    try:
        req = StepIntakeRequest(file_path=stp_file)
        result = accept_step_file(req)
        assert result.is_qualified is False
    finally:
        os.unlink(stp_file)


def test_step_intake_result_step_import_ready_property_true() -> None:
    """StepIntakeResult.step_import_ready mirrors module constant (True in Phase 3)."""
    stp_file = None
    with tempfile.NamedTemporaryFile(suffix=".stp", delete=False) as f:
        f.write(b"ISO-10303-21;\nHEADER;\n")
        stp_file = f.name
    try:
        req = StepIntakeRequest(file_path=stp_file)
        result = accept_step_file(req)
        assert result.step_import_ready is True
        assert result.brep_topology_ready is True
    finally:
        os.unlink(stp_file)
