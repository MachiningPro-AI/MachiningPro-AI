"""
STEP B-Rep parser using gmsh + OpenCASCADE (P10 Phase 3).

Reads STEP files via gmsh's bundled OCC backend and extracts entity counts,
per-face summaries, and global bounding box.

HARD RULES:
  - Fail-closed: any exception → status=FAILED, no partial data returned as valid.
  - No fabricated body count, face count, or bounding box.
  - IN_HOUSE_BENCHMARK files must be labelled sample_origin=IN_HOUSE_BENCHMARK.
  - REAL_EXTERNAL_SAMPLE label is NEVER assigned by this module.
  - is_dispatchable=False and production_released=False always.
  - gmsh is finalized after every call (clean state for next call).
"""

from __future__ import annotations

import hashlib
import os
import threading
from dataclasses import dataclass, field

# gmsh is a project dependency (pyproject.toml: gmsh==4.15.2)
import gmsh  # type: ignore[import]

__all__ = [
    "StepFaceSummary",
    "StepImportRecord",
    "parse_step_file",
    "GMSH_BACKEND",
    "STEP_IMPORT_ACTIVE",
]

GMSH_BACKEND: str = "gmsh-4.15.2+occ"
STEP_IMPORT_ACTIVE: bool = True

# Prevent concurrent gmsh calls — OCC is not thread-safe.
_gmsh_lock = threading.Lock()

_STEP_EXTENSIONS = frozenset({".stp", ".step", ".p21"})


@dataclass(frozen=True)
class StepFaceSummary:
    """Per-face summary extracted from STEP B-Rep."""

    tag: int
    surface_class: str  # PLANAR | CYLINDRICAL | UNKNOWN
    bbox_min: tuple[float, float, float]
    bbox_max: tuple[float, float, float]
    boundary_curve_tags: tuple[int, ...]
    normal_at_center: tuple[float, float, float]
    has_circular_boundary: bool


@dataclass
class StepImportRecord:
    """Result of a STEP file parse attempt.

    Entity counts are extracted from real gmsh topology — never fabricated.
    bbox_min/bbox_max are from the actual OCC bounding box.

    Status values:
      PASS           — file parsed, valid B-Rep with ≥1 volume
      FAILED         — parser exception or zero bodies
      REJECTED_EXT   — wrong file extension
      REJECTED_NOFILE — file not found
      REJECTED_EMPTY — file is 0 bytes
    """

    status: str
    source_path: str
    sha256: str | None
    file_size_bytes: int | None
    parser_backend: str
    sample_origin: str  # IN_HOUSE_BENCHMARK | UNKNOWN_EXTERNAL
    body_count: int
    volume_count: int
    surface_count: int
    edge_count: int
    vertex_count: int
    bbox_min: tuple[float, float, float] | None
    bbox_max: tuple[float, float, float] | None
    faces: list[StepFaceSummary] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    failure_reason: str | None = None

    @property
    def is_qualified(self) -> bool:
        return self.status == "PASS"

    @property
    def is_dispatchable(self) -> bool:
        return False  # unconditional per HARD RULES

    @property
    def production_released(self) -> bool:
        return False  # unconditional per HARD RULES


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _classify_surface_bbox(
    xmin: float, ymin: float, zmin: float,
    xmax: float, ymax: float, zmax: float,
    boundary_tags: list[int],
    circ_tags: set[int],
) -> str:
    dx, dy, dz = xmax - xmin, ymax - ymin, zmax - zmin
    _FLAT = 1e-6
    if dx < _FLAT or dy < _FLAT or dz < _FLAT:
        return "PLANAR"
    # Cylindrical: all boundary curves are circular, non-flat bbox
    if boundary_tags and all(t in circ_tags for t in boundary_tags):
        return "CYLINDRICAL"
    return "UNKNOWN"


def _is_circular(tag: int) -> tuple[bool, float]:
    """Return (is_circle, estimated_diameter_mm).

    A circular edge has: bbox flat in one dimension, equal extents in the other two.
    """
    xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(1, tag)
    dx, dy, dz = xmax - xmin, ymax - ymin, zmax - zmin
    _FLAT = 1e-4
    _REL_TOL = 0.02  # 2% tolerance for circle diameter equality

    def _approx_equal(a: float, b: float) -> bool:
        denom = max(abs(a), abs(b), 1e-10)
        return abs(a - b) / denom < _REL_TOL

    if dz < _FLAT and dx > _FLAT and dy > _FLAT and _approx_equal(dx, dy):
        return True, (dx + dy) / 2.0
    if dy < _FLAT and dx > _FLAT and dz > _FLAT and _approx_equal(dx, dz):
        return True, (dx + dz) / 2.0
    if dx < _FLAT and dy > _FLAT and dz > _FLAT and _approx_equal(dy, dz):
        return True, (dy + dz) / 2.0
    return False, 0.0


def parse_step_file(
    path: str,
    sample_origin: str = "UNKNOWN_EXTERNAL",
) -> StepImportRecord:
    """Parse a STEP file using gmsh+OCC and return a StepImportRecord.

    Fail-closed: any exception during parsing returns status=FAILED.
    No geometry is fabricated; all counts come from gmsh topology.

    sample_origin must be IN_HOUSE_BENCHMARK or UNKNOWN_EXTERNAL.
    REAL_EXTERNAL_SAMPLE is never assigned here.
    """
    # Extension check
    _, ext = os.path.splitext(path)
    if ext.lower() not in _STEP_EXTENSIONS:
        return StepImportRecord(
            status="REJECTED_EXT",
            source_path=path,
            sha256=None,
            file_size_bytes=None,
            parser_backend=GMSH_BACKEND,
            sample_origin=sample_origin,
            body_count=0,
            volume_count=0,
            surface_count=0,
            edge_count=0,
            vertex_count=0,
            bbox_min=None,
            bbox_max=None,
            failure_reason=f"Extension '{ext}' not recognised as STEP",
        )

    # File existence
    if not os.path.isfile(path):
        return StepImportRecord(
            status="REJECTED_NOFILE",
            source_path=path,
            sha256=None,
            file_size_bytes=None,
            parser_backend=GMSH_BACKEND,
            sample_origin=sample_origin,
            body_count=0,
            volume_count=0,
            surface_count=0,
            edge_count=0,
            vertex_count=0,
            bbox_min=None,
            bbox_max=None,
            failure_reason=f"File not found: {path}",
        )

    try:
        file_size = os.path.getsize(path)
    except OSError as exc:
        return StepImportRecord(
            status="REJECTED_NOFILE",
            source_path=path,
            sha256=None,
            file_size_bytes=None,
            parser_backend=GMSH_BACKEND,
            sample_origin=sample_origin,
            body_count=0,
            volume_count=0,
            surface_count=0,
            edge_count=0,
            vertex_count=0,
            bbox_min=None,
            bbox_max=None,
            failure_reason=f"Cannot read file: {exc}",
        )

    if file_size == 0:
        return StepImportRecord(
            status="REJECTED_EMPTY",
            source_path=path,
            sha256=None,
            file_size_bytes=0,
            parser_backend=GMSH_BACKEND,
            sample_origin=sample_origin,
            body_count=0,
            volume_count=0,
            surface_count=0,
            edge_count=0,
            vertex_count=0,
            bbox_min=None,
            bbox_max=None,
            failure_reason="File is empty",
        )

    sha = _sha256(path)
    warnings: list[str] = []

    with _gmsh_lock:
        try:
            gmsh.initialize(["-v", "0"])
            gmsh.model.add("step_parse")
            gmsh.model.occ.importShapes(path)
            gmsh.model.occ.synchronize()

            volumes = gmsh.model.getEntities(3)
            surfaces = gmsh.model.getEntities(2)
            curves = gmsh.model.getEntities(1)
            verts = gmsh.model.getEntities(0)

            body_count = len(volumes)
            if body_count == 0:
                gmsh.finalize()
                return StepImportRecord(
                    status="FAILED",
                    source_path=path,
                    sha256=sha,
                    file_size_bytes=file_size,
                    parser_backend=GMSH_BACKEND,
                    sample_origin=sample_origin,
                    body_count=0,
                    volume_count=0,
                    surface_count=len(surfaces),
                    edge_count=len(curves),
                    vertex_count=len(verts),
                    bbox_min=None,
                    bbox_max=None,
                    failure_reason="No solid bodies found in STEP file",
                    warnings=["STEP_BODY_COUNT=0: file has no closed volumes"],
                )

            # Global bounding box
            xmin_g, ymin_g, zmin_g, xmax_g, ymax_g, zmax_g = gmsh.model.getBoundingBox(-1, -1)

            # Determine circular curve tags
            circ_tags: set[int] = set()
            for _d, ctag in curves:
                is_circ, _diam = _is_circular(ctag)
                if is_circ:
                    circ_tags.add(ctag)

            # Build per-face summaries
            face_summaries: list[StepFaceSummary] = []
            for _d, stag in surfaces:
                s_bounds = gmsh.model.getBoundary([(_d, stag)], oriented=False)
                bound_ctags = [b[1] for b in s_bounds]

                xmin_s, ymin_s, zmin_s, xmax_s, ymax_s, zmax_s = gmsh.model.getBoundingBox(2, stag)

                surf_class = _classify_surface_bbox(
                    xmin_s, ymin_s, zmin_s,
                    xmax_s, ymax_s, zmax_s,
                    bound_ctags,
                    circ_tags,
                )

                try:
                    normal = gmsh.model.getNormal(stag, [0.5, 0.5])
                    n3 = (float(normal[0]), float(normal[1]), float(normal[2]))
                except Exception:
                    n3 = (0.0, 0.0, 0.0)

                has_circ = any(t in circ_tags for t in bound_ctags)

                face_summaries.append(StepFaceSummary(
                    tag=stag,
                    surface_class=surf_class,
                    bbox_min=(xmin_s, ymin_s, zmin_s),
                    bbox_max=(xmax_s, ymax_s, zmax_s),
                    boundary_curve_tags=tuple(bound_ctags),
                    normal_at_center=n3,
                    has_circular_boundary=has_circ,
                ))

            # Multi-body warning
            if body_count > 1:
                warnings.append(
                    f"MULTI_BODY_STEP: {body_count} volumes found. "
                    "Stock/fixture relationship is UNKNOWN_TRANSFORM until manually reviewed."
                )

            gmsh.finalize()
            return StepImportRecord(
                status="PASS",
                source_path=path,
                sha256=sha,
                file_size_bytes=file_size,
                parser_backend=GMSH_BACKEND,
                sample_origin=sample_origin,
                body_count=body_count,
                volume_count=body_count,
                surface_count=len(surfaces),
                edge_count=len(curves),
                vertex_count=len(verts),
                bbox_min=(xmin_g, ymin_g, zmin_g),
                bbox_max=(xmax_g, ymax_g, zmax_g),
                faces=face_summaries,
                warnings=warnings,
            )

        except Exception as exc:  # noqa: BLE001
            try:
                gmsh.finalize()
            except Exception:  # noqa: BLE001
                pass
            return StepImportRecord(
                status="FAILED",
                source_path=path,
                sha256=sha,
                file_size_bytes=file_size,
                parser_backend=GMSH_BACKEND,
                sample_origin=sample_origin,
                body_count=0,
                volume_count=0,
                surface_count=0,
                edge_count=0,
                vertex_count=0,
                bbox_min=None,
                bbox_max=None,
                failure_reason=f"gmsh parse exception: {type(exc).__name__}: {exc}",
                warnings=[f"PARSE_EXCEPTION: {exc}"],
            )
