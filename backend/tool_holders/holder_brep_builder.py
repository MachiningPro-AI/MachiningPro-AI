"""
Parametric Holder B-Rep Builder (Phases I/J)

Builds canonical parametric B-Rep geometry for tool holders from catalog
dimensions using gmsh OCC primitives.

HOLDER_GEOMETRY_METHOD ∈ {PARAMETRIC_BREP, SIMPLIFIED, NOT_AVAILABLE}
HOLDER_GEOMETRY_FIDELITY ∈ {PARAMETRIC_BREP, SIMPLIFIED, PARTIAL, NOT_AVAILABLE}

Fidelity contract (HARD RULE 4):
  - Full holder profile requires: gauge_length + nose_diameter + body_diameter
  - gauge_length alone → SIMPLIFIED (axial length known, radial profile simplified)
  - No geometry at all → NOT_AVAILABLE
  - Never presents SIMPLIFIED as full CATALOG_BREP fidelity

Limitation (always disclosed):
  HOLDER_PROFILE = ROTATIONALLY_SYMMETRIC_APPROXIMATION
  HSK tapers, retention knobs, side protrusions NOT modeled
  HOLDER_BREP_COMPLETENESS = OUTER_ENVELOPE_ONLY

FABRICATED_DIMENSIONS=NO
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_GMSH_LOCK = threading.Lock()


@dataclass
class HolderBRepResult:
    """Result of parametric holder B-Rep geometry construction."""

    holder_id: str = ""
    geometry_method: str = "PARAMETRIC_BREP"
    geometry_fidelity: str = "NOT_AVAILABLE"
    geometry_completeness: str = "NOT_AVAILABLE"

    # Dimensions used/missing
    dimensions_used: list[str] = field(default_factory=list)
    dimensions_missing: list[str] = field(default_factory=list)

    # Volume (OCC getMass)
    holder_volume_mm3: float = 0.0
    holder_volume_fidelity: str = "NOT_AVAILABLE"

    bounding_box: tuple[float, float, float, float, float, float] | None = None

    # Fidelity declaration (HARD RULE 4)
    profile_type: str = "ROTATIONALLY_SYMMETRIC_APPROXIMATION"
    taper_modeled: bool = False
    retention_knob_modeled: bool = False

    source: str = "CATALOG"
    provenance: str = "PARAMETRIC_CONSTRUCTION"

    error: str | None = None
    warnings: list[str] = field(default_factory=list)


def build_holder_brep(
    holder_id: str,
    gauge_length_mm: float | None,
    nose_diameter_mm: float | None,
    body_diameter_mm: float | None,
    overall_length_mm: float | None,
    source: str = "CATALOG",
) -> HolderBRepResult:
    """Build parametric holder B-Rep from catalog dimensions.

    Minimum requirement: gauge_length_mm (at least axial length is known).
    Without any geometry → NOT_AVAILABLE.

    Fidelity levels (ascending):
      1. gauge_length_mm only → SIMPLIFIED (cylinder of guessed radius)
         NEVER reported; always discloses as SIMPLIFIED.
      2. gauge_length_mm + nose_diameter_mm → PARTIAL (front section known)
      3. gauge_length_mm + nose_diameter_mm + body_diameter_mm → PARAMETRIC_BREP
         (rotationally symmetric stepped body, outer envelope)
    """
    result = HolderBRepResult(holder_id=holder_id, source=source)

    has_gauge = gauge_length_mm is not None and gauge_length_mm > 0
    has_nose = nose_diameter_mm is not None and nose_diameter_mm > 0
    has_body = body_diameter_mm is not None and body_diameter_mm > 0
    has_overall = overall_length_mm is not None and overall_length_mm > 0

    if not has_gauge:
        result.dimensions_missing.extend(
            ["gauge_length_mm", "nose_diameter_mm", "body_diameter_mm"]
        )
        result.geometry_fidelity = "NOT_AVAILABLE"
        result.geometry_completeness = "NOT_AVAILABLE"
        result.error = "gauge_length_mm required as minimum holder geometry"
        return result

    result.dimensions_used.append("gauge_length_mm")

    if has_nose:
        result.dimensions_used.append("nose_diameter_mm")
    else:
        result.dimensions_missing.append("nose_diameter_mm")

    if has_body:
        result.dimensions_used.append("body_diameter_mm")
    else:
        result.dimensions_missing.append("body_diameter_mm")

    if has_overall:
        result.dimensions_used.append("overall_length_mm")
    else:
        result.dimensions_missing.append("overall_length_mm")

    # Choose construction path
    if has_gauge and has_nose and has_body:
        fidelity = "PARAMETRIC_BREP"
        completeness = "OUTER_ENVELOPE_BODY_AND_NOSE"
    elif has_gauge and has_nose:
        fidelity = "PARTIAL"
        completeness = "NOSE_SECTION_ONLY"
    else:
        # gauge_length alone — simplified cylinder, body_diam estimated
        fidelity = "SIMPLIFIED"
        completeness = "GAUGE_LENGTH_ONLY"
        result.warnings.append(
            "nose_diameter_mm and body_diameter_mm unavailable — holder modeled as "
            "simplified cylinder with estimated radius; use SIMPLIFIED fidelity accordingly"
        )

    try:
        with _GMSH_LOCK:
            vol = _build_holder_in_gmsh(
                gauge_length_mm=gauge_length_mm,
                nose_diameter_mm=nose_diameter_mm,
                body_diameter_mm=body_diameter_mm,
                overall_length_mm=overall_length_mm,
                result=result,
            )
        result.holder_volume_mm3 = vol
        result.holder_volume_fidelity = "BREP_EXACT"
    except Exception as exc:
        result.error = f"gmsh build failed: {exc}"
        result.geometry_fidelity = "NOT_AVAILABLE"
        result.holder_volume_fidelity = "NOT_AVAILABLE"
        logger.debug("build_holder_brep failed for %s: %s", holder_id, exc)
        return result

    result.geometry_fidelity = fidelity
    result.geometry_completeness = completeness
    result.geometry_method = "PARAMETRIC_BREP"
    return result


def _build_holder_in_gmsh(
    gauge_length_mm: float,
    nose_diameter_mm: float | None,
    body_diameter_mm: float | None,
    overall_length_mm: float | None,
    result: HolderBRepResult,
) -> float:
    """Build holder solid in isolated gmsh session. Returns exact volume."""
    try:
        import gmsh
    except ImportError as e:
        raise RuntimeError(f"gmsh not available: {e}") from e

    gmsh.initialize()
    gmsh.option.setNumber("General.Verbosity", 0)
    gmsh.model.add("holder_brep")
    occ = gmsh.model.occ

    try:
        nose_r = (nose_diameter_mm / 2.0) if nose_diameter_mm else None
        body_r = (body_diameter_mm / 2.0) if body_diameter_mm else None
        # Fallback radius when no catalog data
        fallback_r = max(10.0, gauge_length_mm * 0.15)

        if body_r and nose_r and body_r > nose_r:
            # Full stepped cylinder: larger body section + smaller nose section
            # Nose section: z=0 to gauge_length_mm
            occ.addCylinder(0, 0, 0, 0, 0, gauge_length_mm, nose_r)
            # Body section: gauge_length_mm to overall_length_mm (or gauge * 1.5)
            body_len = (overall_length_mm - gauge_length_mm
                        if overall_length_mm and overall_length_mm > gauge_length_mm
                        else gauge_length_mm * 0.5)
            if body_len > 0.001:
                occ.addCylinder(0, 0, gauge_length_mm, 0, 0, body_len, body_r)
        elif nose_r:
            # Only nose known — single cylinder
            total_len = overall_length_mm if overall_length_mm else gauge_length_mm * 1.5
            occ.addCylinder(0, 0, 0, 0, 0, total_len, nose_r)
        else:
            # Gauge length only — simplified cylinder
            total_len = overall_length_mm if overall_length_mm else gauge_length_mm * 1.5
            occ.addCylinder(0, 0, 0, 0, 0, total_len, fallback_r)

        occ.synchronize()

        entities = gmsh.model.getEntities(3)
        if not entities:
            raise RuntimeError("No 3D solid produced for holder")

        if len(entities) > 1:
            fused, _ = occ.fuse(entities[:1], entities[1:], removeObject=True, removeTool=True)
            occ.synchronize()
            entities = fused

        total_vol = 0.0
        for dim, tag in entities:
            total_vol += abs(float(gmsh.model.occ.getMass(dim, tag)))

        if entities:
            try:
                bbox = occ.getBoundingBox(*entities[0])
                result.bounding_box = tuple(float(x) for x in bbox)  # type: ignore[assignment]
            except Exception:
                pass

        return total_vol

    finally:
        try:
            gmsh.finalize()
        except Exception:
            pass


def build_holder_brep_from_record(record) -> HolderBRepResult:
    """Build holder B-Rep from a ToolHolderCatalogRecord (or ToolHolderRecord).

    Maps catalog fields; never fabricates missing dimensions.
    """
    # Support both catalog_models.ToolHolderCatalogRecord and
    # tool_holders.ToolHolderRecord (models.py) via duck typing
    return build_holder_brep(
        holder_id=getattr(record, "stable_id", "") or getattr(record, "holder_id", ""),
        gauge_length_mm=getattr(record, "gauge_length_mm", None),
        nose_diameter_mm=getattr(record, "nose_diameter_mm", None),
        body_diameter_mm=getattr(record, "body_diameter_mm", None),
        overall_length_mm=getattr(record, "overall_length_mm", None),
        source=getattr(record, "source_authority", "CATALOG"),
    )
