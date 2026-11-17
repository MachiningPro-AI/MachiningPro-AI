"""
P10-B: Fail-closed STEP/B-Rep qualification intake.

Provides the production-ready intake path for future real STEP qualification.
No STEP files are fabricated or simulated here. The intake gate is fail-closed:
any path that cannot be verified produces a DEFERRED or REJECTED status.

Architecture prepared for (not yet implemented — cadquery not installed):
  STEP file reading       → cadquery STEP reader (AP214/AP242/AP203)
  Topology extraction     → closed-shell B-Rep face list
  Solid/shell classifier  → SOLID_PART / SHELL_ASSEMBLY / SURFACE_PART / UNKNOWN
  Feature candidates      → bbox from B-Rep shell faces
  Provenance              → STEP_FILE_EVIDENCE (once verified)
  Fail-closed unsupported → REJECTED with explicit reason

Current status:
  STEP_IMPORT_READY=NO      (cadquery not installed)
  BREP_TOPOLOGY_READY=NO    (requires cadquery)
  FEATURE_EXTRACTION_READY=NO (requires topology)
  REAL_3D_CAM_PIPELINE_READY=PARTIAL (DXF pipeline only)

HARD RULES:
  - REAL_STEP_SAMPLE_COUNT counts only files that PASS intake; never incremented by code.
  - Do NOT fabricate part_bbox from non-STEP sources.
  - Do NOT claim STEP_QUALIFIED without a real sample passing the intake gate.
  - GOUGE_VALIDATED remains NOT_VERIFIABLE until a real STEP sample qualifies.
  - Unsupported geometry → REJECTED (not silently downgraded to 2.5D).

OFFLINE_ONLY=YES  IS_DISPATCHABLE=ALWAYS_FALSE
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import StrEnum

__all__ = [
    "StepIntakeStatus",
    "StepIntakeRequest",
    "StepIntakeResult",
    "accept_step_file",
    "scan_step_samples",
    "REAL_STEP_SAMPLE_COUNT",
    "STEP_IMPORT_READY",
    "BREP_TOPOLOGY_READY",
    "FEATURE_EXTRACTION_READY",
]

# ---------------------------------------------------------------------------
# Pipeline readiness constants (updated when dependencies installed)
# ---------------------------------------------------------------------------

STEP_IMPORT_READY: bool = False
BREP_TOPOLOGY_READY: bool = False
FEATURE_EXTRACTION_READY: bool = False
REAL_STEP_SAMPLE_COUNT: int = 0  # incremented only by accept_step_file returning PASS

# Valid STEP file extensions (ISO 10303-21)
_STEP_EXTENSIONS = frozenset({".stp", ".step", ".p21"})

# Maximum file size accepted without explicit override (100 MB)
_MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024


# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------


class StepIntakeStatus(StrEnum):
    """STEP intake gate status."""

    PASS = "PASS"
    REJECTED_WRONG_EXTENSION = "REJECTED_WRONG_EXTENSION"
    REJECTED_FILE_NOT_FOUND = "REJECTED_FILE_NOT_FOUND"
    REJECTED_FILE_TOO_LARGE = "REJECTED_FILE_TOO_LARGE"
    REJECTED_EMPTY_FILE = "REJECTED_EMPTY_FILE"
    REJECTED_UNSUPPORTED_GEOMETRY = "REJECTED_UNSUPPORTED_GEOMETRY"
    DEFERRED_NO_PARSER = "DEFERRED_NO_PARSER"
    DEFERRED_NO_SAMPLES = "DEFERRED_NO_SAMPLES"


# ---------------------------------------------------------------------------
# Request and result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StepIntakeRequest:
    """Request to accept a STEP file into the qualification intake.

    file_path:
        Absolute path to the STEP/STP file.
    expected_class:
        Optional expected sample class (A, B, C, D per STEP_CAM_VERIFICATION
        _SAMPLE_REQUIREMENTS.md). None means unclassified — intake runs
        but class-specific criteria are not checked.
    max_file_size_bytes:
        Maximum file size accepted. Default 100 MB.
    """

    file_path: str
    expected_class: str | None = None
    max_file_size_bytes: int = _MAX_FILE_SIZE_BYTES


@dataclass
class StepIntakeResult:
    """Result of a STEP file intake attempt.

    status:
        PASS — file passed all intake checks (requires cadquery installed).
        DEFERRED_NO_PARSER — cadquery not installed; file not parsed.
        REJECTED_* — intake failed; reason in rejection_reason.

    part_bbox_min / part_bbox_max:
        None in all cases until cadquery is installed and a real file passes.
        Never fabricated from non-STEP sources.

    provenance:
        STEP_FILE_EVIDENCE when PASS. UNKNOWN otherwise.

    is_qualified:
        True only when status=PASS. Never True from this implementation
        (cadquery not installed → always False).
    """

    status: StepIntakeStatus
    file_path: str
    rejection_reason: str | None = None
    part_bbox_min: tuple[float, float, float] | None = None
    part_bbox_max: tuple[float, float, float] | None = None
    provenance: str = "UNKNOWN"
    solid_count: int | None = None
    shell_count: int | None = None
    geometry_class: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def is_qualified(self) -> bool:
        return self.status == StepIntakeStatus.PASS

    @property
    def step_import_ready(self) -> bool:
        return STEP_IMPORT_READY

    @property
    def brep_topology_ready(self) -> bool:
        return BREP_TOPOLOGY_READY


# ---------------------------------------------------------------------------
# Intake gate
# ---------------------------------------------------------------------------


def accept_step_file(request: StepIntakeRequest) -> StepIntakeResult:
    """Run the intake gate for a STEP/B-Rep file.

    Validation order (fail-closed):
      1. Extension check: must be .stp / .step / .p21
      2. File existence: must exist on disk
      3. File size: must not be empty; must be below max_file_size_bytes
      4. Parser availability: cadquery must be installed (currently not)
      5. (Future) Parse → topology → solid/shell classification → bbox extraction

    Returns a StepIntakeResult. Status PASS requires cadquery installed AND
    a real STEP file that passes all checks.

    DO NOT fabricate part_bbox. This function never sets part_bbox_min/max
    from non-STEP sources.
    """
    path = request.file_path
    warnings: list[str] = []

    # 1. Extension check
    _, ext = os.path.splitext(path)
    if ext.lower() not in _STEP_EXTENSIONS:
        return StepIntakeResult(
            status=StepIntakeStatus.REJECTED_WRONG_EXTENSION,
            file_path=path,
            rejection_reason=(
                f"File extension '{ext}' is not a recognised STEP extension. "
                f"Accepted: {', '.join(sorted(_STEP_EXTENSIONS))}"
            ),
        )

    # 2. File existence
    if not os.path.isfile(path):
        return StepIntakeResult(
            status=StepIntakeStatus.REJECTED_FILE_NOT_FOUND,
            file_path=path,
            rejection_reason=f"File not found: {path}",
        )

    # 3. File size
    try:
        size = os.path.getsize(path)
    except OSError as exc:
        return StepIntakeResult(
            status=StepIntakeStatus.REJECTED_FILE_NOT_FOUND,
            file_path=path,
            rejection_reason=f"Cannot read file size: {exc}",
        )

    if size == 0:
        return StepIntakeResult(
            status=StepIntakeStatus.REJECTED_EMPTY_FILE,
            file_path=path,
            rejection_reason="File is empty (0 bytes)",
        )

    if size > request.max_file_size_bytes:
        return StepIntakeResult(
            status=StepIntakeStatus.REJECTED_FILE_TOO_LARGE,
            file_path=path,
            rejection_reason=(
                f"File size {size:,} bytes exceeds maximum "
                f"{request.max_file_size_bytes:,} bytes"
            ),
        )

    # 4. Parser availability
    if not STEP_IMPORT_READY:
        warnings.append(
            "STEP_IMPORT_READY=NO: cadquery is not installed. "
            "File passed extension and size checks but cannot be parsed. "
            "Install cadquery (conda or pip) to enable topology extraction. "
            "P10-B qualification remains DEFERRED_REAL_STEP_SAMPLE_REQUIRED."
        )
        return StepIntakeResult(
            status=StepIntakeStatus.DEFERRED_NO_PARSER,
            file_path=path,
            rejection_reason=None,
            warnings=warnings,
        )

    # 5. Future: parse → topology → bbox (cadquery not installed)
    # This path is never reached in the current build.
    # When cadquery is installed, this branch would call:
    #   import cadquery as cq
    #   result = cq.importers.importStep(path)
    #   bbox = result.val().BoundingBox()
    #   part_bbox_min = (bbox.xmin, bbox.ymin, bbox.zmin)
    #   part_bbox_max = (bbox.xmax, bbox.ymax, bbox.zmax)
    #   provenance = "STEP_FILE_EVIDENCE"
    # Until then: DEFERRED_NO_PARSER.
    return StepIntakeResult(  # pragma: no cover
        status=StepIntakeStatus.DEFERRED_NO_PARSER,
        file_path=path,
        rejection_reason=None,
        warnings=["STEP_IMPORT_READY=NO: cadquery not installed"],
    )


# ---------------------------------------------------------------------------
# Sample directory scanner
# ---------------------------------------------------------------------------


def scan_step_samples(directory: str) -> list[StepIntakeResult]:
    """Scan a directory for STEP files and run intake on each.

    Returns a list of StepIntakeResult objects.
    An empty list means no STEP files were found.

    Does NOT modify REAL_STEP_SAMPLE_COUNT (that is a module constant updated
    only when this function's design is updated to track qualified samples).

    Use this to verify REAL_STEP_SAMPLE_COUNT=0 at qualification time.
    """
    if not os.path.isdir(directory):
        return []

    results: list[StepIntakeResult] = []
    try:
        entries = os.listdir(directory)
    except OSError:
        return []

    for entry in sorted(entries):
        _, ext = os.path.splitext(entry)
        if ext.lower() in _STEP_EXTENSIONS:
            full_path = os.path.join(directory, entry)
            results.append(accept_step_file(StepIntakeRequest(file_path=full_path)))

    return results


def _3d_pipeline_readiness() -> dict[str, str]:
    """Return the current 3D CAM pipeline readiness status per stage.

    Used by qualification reports (MUST 23).
    """
    return {
        "STEP_IMPORT":          "NOT_IMPLEMENTED" if not STEP_IMPORT_READY else "PARTIAL",
        "BREP_TOPOLOGY":        "NOT_IMPLEMENTED" if not BREP_TOPOLOGY_READY else "PARTIAL",
        "SOLID_CLASSIFIER":     "NOT_IMPLEMENTED",
        "FEATURE_EXTRACTION":   "NOT_IMPLEMENTED" if not FEATURE_EXTRACTION_READY else "PARTIAL",
        "ROUTE_GENERATION_3D":  "NOT_IMPLEMENTED",
        "MACHINE_SELECTION_3D": "PARTIAL",
        "TOOL_SELECTION_3D":    "PARTIAL",
        "CAM_STRATEGY_3D":      "PARTIAL",
        "TOOLPATH_3D":          "PARTIAL",
        "VERIFICATION_3D":      "PARTIAL",
        "SIMULATION_3D":        "PARTIAL",
    }
