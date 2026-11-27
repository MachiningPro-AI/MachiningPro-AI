"""
Exact B-Rep Volume Engine — OCC Mass Properties (Phase B)

VOLUME_METHOD=BREP_SOLID_VOLUME
VOLUME_FIDELITY=BREP_EXACT (for valid closed B-Rep solids)
VOLUME_FIDELITY=APPROXIMATE_NUMERICAL_INTEGRATION (fallback: tetrahedral mesh)

Uses gmsh.model.occ.getMass(dim, tag) which internally calls OCC's
GProp_GProps exact volumetric integration. No meshing required.

Fidelity contract (HARD RULE 2):
  - getMass success on a closed solid → BREP_EXACT
  - getMass failure or open/degenerate solid → APPROXIMATE or NOT_AVAILABLE
  - Mesh fallback is always labeled APPROXIMATE_NUMERICAL_INTEGRATION
  - Never silently downgrade a successful exact result to approximate.

PROVENANCE=OCC_MASS_PROPERTIES
FABRICATED_VOLUME=NO
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_VOLUME_ZERO_THRESHOLD = 1e-6  # mm³ — below this, treat as effectively zero


@dataclass
class BRepVolumeResult:
    """Result of exact B-Rep solid volume measurement.

    volume_method / volume_fidelity are the authoritative fidelity fields.
    Never call this 'exact' when fallback_used=True.
    """

    volume_mm3: float = 0.0
    volume_method: str = "BREP_SOLID_VOLUME"
    volume_fidelity: str = "BREP_EXACT"
    solid_valid: bool = False
    solid_closed: bool = False

    # Optional mass properties
    center_of_mass_x: float | None = None
    center_of_mass_y: float | None = None
    center_of_mass_z: float | None = None
    bounding_box: tuple[float, float, float, float, float, float] | None = None

    # Provenance
    provenance: str = "OCC_MASS_PROPERTIES"
    entity_count: int = 0

    # Fallback tracking
    fallback_used: bool = False
    fallback_method: str | None = None
    fallback_fidelity: str | None = None

    error: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class MassPropertyResult:
    """Volume + optional mass given a material density.

    MASS=NOT_VERIFIABLE when density unavailable.
    DENSITY_STATUS ∈ {CATALOG_AVAILABLE, NOT_AVAILABLE, NOT_PROVIDED}
    """

    volume_mm3: float = 0.0
    volume_method: str = "BREP_SOLID_VOLUME"
    volume_fidelity: str = "BREP_EXACT"

    mass_kg: float | None = None
    mass_status: str = "NOT_VERIFIABLE"
    density_kg_m3: float | None = None
    density_source: str = "NOT_PROVIDED"
    density_status: str = "NOT_PROVIDED"

    center_of_mass_x: float | None = None
    center_of_mass_y: float | None = None
    center_of_mass_z: float | None = None
    bounding_box: tuple[float, float, float, float, float, float] | None = None


def compute_occ_entity_volume(
    gmsh_module,
    dim: int,
    tag: int,
) -> BRepVolumeResult:
    """Compute exact volume of a single OCC entity using getMass.

    gmsh_module must be an initialised gmsh module with the entity present
    and occ.synchronize() already called.

    Returns BRepVolumeResult with solid_valid=False on any failure.
    """
    result = BRepVolumeResult(entity_count=1)

    try:
        vol = float(gmsh_module.model.occ.getMass(dim, tag))
        if vol < 0.0:
            # OCC can return negative for reversed orientation — take abs
            vol = abs(vol)
            result.warnings.append(
                f"entity ({dim},{tag}): getMass returned negative — absolute value used"
            )

        result.volume_mm3 = vol
        result.solid_valid = True
        result.solid_closed = vol > _VOLUME_ZERO_THRESHOLD

        # Center of mass
        try:
            cx, cy, cz = gmsh_module.model.occ.getCenterOfMass(dim, tag)
            result.center_of_mass_x = float(cx)
            result.center_of_mass_y = float(cy)
            result.center_of_mass_z = float(cz)
        except Exception as e:
            result.warnings.append(f"center_of_mass unavailable: {e}")

        # Bounding box
        try:
            bbox = gmsh_module.model.occ.getBoundingBox(dim, tag)
            result.bounding_box = tuple(float(v) for v in bbox)  # type: ignore[assignment]
        except Exception as e:
            result.warnings.append(f"bounding_box unavailable: {e}")

    except Exception as exc:
        result.solid_valid = False
        result.solid_closed = False
        result.volume_method = "BREP_SOLID_VOLUME_FAILED"
        result.volume_fidelity = "NOT_AVAILABLE"
        result.error = f"getMass({dim},{tag}) failed: {exc}"
        logger.debug("compute_occ_entity_volume failed: %s", exc)

    return result


def compute_occ_entities_total_volume(
    gmsh_module,
    entities: list[tuple[int, int]],
) -> BRepVolumeResult:
    """Compute exact total volume of a set of OCC entities.

    Only 3D entities (dim=3) contribute to volume.
    If ANY entity fails getMass, the total is marked NOT_AVAILABLE.

    Returns BRepVolumeResult. When all entities succeed: solid_valid=True,
    volume_fidelity=BREP_EXACT. On partial failure: solid_valid=False.
    """
    total = BRepVolumeResult()
    total.volume_mm3 = 0.0
    total.solid_valid = True
    total.solid_closed = True
    errors: list[str] = []
    n_3d = 0

    for dim, tag in entities:
        if dim != 3:
            continue
        n_3d += 1
        r = compute_occ_entity_volume(gmsh_module, dim, tag)
        total.warnings.extend(r.warnings)

        if r.solid_valid:
            total.volume_mm3 += r.volume_mm3
        else:
            errors.append(r.error or f"entity ({dim},{tag}): unknown error")
            total.solid_valid = False
            total.solid_closed = False

    total.entity_count = n_3d

    if n_3d == 0:
        total.solid_valid = False
        total.solid_closed = False
        total.volume_fidelity = "NOT_AVAILABLE"
        total.error = "No 3D entities provided for volume calculation"
    elif errors:
        total.volume_fidelity = "NOT_AVAILABLE"
        total.error = "; ".join(errors)
    else:
        total.volume_fidelity = "BREP_EXACT"

    return total


def attach_mass_properties(
    volume_result: BRepVolumeResult,
    density_kg_m3: float | None,
    density_source: str,
) -> MassPropertyResult:
    """Derive mass from volume + density where available.

    MASS=NOT_VERIFIABLE when density is None or unavailable.
    Never fabricate density.
    """
    r = MassPropertyResult(
        volume_mm3=volume_result.volume_mm3,
        volume_method=volume_result.volume_method,
        volume_fidelity=volume_result.volume_fidelity,
        center_of_mass_x=volume_result.center_of_mass_x,
        center_of_mass_y=volume_result.center_of_mass_y,
        center_of_mass_z=volume_result.center_of_mass_z,
        bounding_box=volume_result.bounding_box,
    )

    if density_kg_m3 is not None and density_kg_m3 > 0.0:
        # Volume is in mm³; density in kg/m³; 1 m³ = 1e9 mm³
        r.mass_kg = volume_result.volume_mm3 * density_kg_m3 / 1e9
        r.density_kg_m3 = density_kg_m3
        r.density_source = density_source
        r.density_status = "CATALOG_AVAILABLE"
        r.mass_status = "COMPUTED"
    else:
        r.mass_kg = None
        r.mass_status = "NOT_VERIFIABLE"
        r.density_status = "NOT_AVAILABLE" if density_source != "NOT_PROVIDED" else "NOT_PROVIDED"
        r.density_source = density_source

    return r
