"""DXF R12–R2024 format adapter (Stage 4C — CAD_IMPORT_LEVEL_1).

Capability roadmap
------------------
Pure Python (no external dependencies):
    Level 0 — RECOGNIZED  (extension / group-code-0 detection)
    Level 1 — PARSED      (section inventory, layer names, entity type histogram,
                           bounding box, units)

With ``ezdxf`` installed:
    Level 2 — NORMALIZED  (CanonicalGeometry populated from DXF entities)

References
----------
AutoCAD DXF Reference — Autodesk (public, annually updated)
DXF R12 fixed-format specification (public domain)
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any

from backend.domain.units import Quantity, Unit
from backend.interoperability.adapter import FormatAdapter
from backend.interoperability.adapters._base import (
    AdapterSession,
    make_uid,
)
from backend.interoperability.enums import (
    AdapterCapability,
    AdapterLicense,
    CapabilityLevel,
    FidelityClass,
    FidelityReportCompleteness,
    FormatFamily,
)
from backend.interoperability.geometry import (
    BoundingBox3D,
    CanonicalCurve,
    CanonicalCurveType,
    CanonicalGeometry,
    CanonicalPoint3D,
)
from backend.interoperability.models import (
    AdapterMetadata,
    CanonicalDocument,
    CanonicalEntityRef,
    EngineeringSource,
    FormatDescriptor,
)

__all__ = ["DxfTokenAdapter"]

_ADAPTER_ID = "machinerypro-dxf-token-v1"
_ADAPTER_VERSION = "2.0.0"

DXF_DESCRIPTOR = FormatDescriptor(
    format_id="DXF",
    canonical_name="AutoCAD DXF",
    family=FormatFamily.DRAWING,
    extensions=("dxf",),
    media_types=("image/vnd.dxf", "application/dxf"),
    vendor="Autodesk",
    is_open=True,
    is_proprietary=False,
    adapter_license=AdapterLicense.INTERNAL_PARSER,
    notes=(
        "Drawing Exchange Format, R12–R2024. "
        "Level 2 geometry normalization requires ezdxf (MIT license)."
    ),
)

# Known DXF section names
_KNOWN_SECTIONS = frozenset(
    {"HEADER", "CLASSES", "TABLES", "BLOCKS", "ENTITIES", "OBJECTS", "THUMBNAILIMAGE"}
)

# DXF entity types that map to geometry
_GEOMETRY_ENTITY_TYPES = frozenset(
    {
        "LINE", "CIRCLE", "ARC", "ELLIPSE", "SPLINE", "LWPOLYLINE",
        "POLYLINE", "VERTEX", "POINT", "3DFACE", "SOLID", "TRACE",
        "XLINE", "RAY", "MLINE", "HELIX",
    }
)

# All entity types we recognize
_ALL_ENTITY_TYPES = _GEOMETRY_ENTITY_TYPES | frozenset(
    {"TEXT", "MTEXT", "INSERT", "BLOCK", "ENDBLK", "ATTDEF", "ATTRIB",
     "DIMENSION", "LEADER", "VIEWPORT", "HATCH", "IMAGE", "WIPEOUT",
     "BODY", "REGION", "ACIS", "TOLERANCE", "SHAPE"}
)

# $INSUNITS mapping (group code 70 value → unit name)
_DXF_INSUNITS_TO_MM: dict[int, float] = {
    0:  1.0,           # Unitless — treat as mm
    1:  25.4,          # Inches
    2:  304.8,         # Feet
    3:  1_609_344.0,   # Miles
    4:  1.0,           # Millimeters
    5:  10.0,          # Centimeters
    6:  1_000.0,       # Meters
    7:  1_000_000.0,   # Kilometers
    8:  0.0000254,     # Microinches
    9:  0.0254,        # Mils
    10: 914.4,         # Yards
    11: 1e-7,          # Angstroms
    12: 1e-6,          # Nanometers
    13: 0.001,         # Microns
    14: 100.0,         # Decimeters
    15: 10_000.0,      # Decameters
    16: 100_000.0,     # Hectometers
    17: 1e12,          # Gigameters
    18: 1.495978707e14, # Astronomical Units
    19: 9.4607304725e18, # Light Years
    20: 3.08567758e19,  # Parsecs
}

_DXF_INSUNITS: dict[int, str] = {
    0:  "Unitless",
    1:  "Inches",
    2:  "Feet",
    3:  "Miles",
    4:  "Millimeters",
    5:  "Centimeters",
    6:  "Meters",
    7:  "Kilometers",
    8:  "Microinches",
    9:  "Mils",
    10: "Yards",
    11: "Angstroms",
    12: "Nanometers",
    13: "Microns",
    14: "Decimeters",
    15: "Decameters",
    16: "Hectometers",
    17: "Gigameters",
    18: "Astronomical Units",
    19: "Light Years",
    20: "Parsecs",
}


def _safe_float(s: str) -> float | None:
    try:
        return float(s.strip())
    except (ValueError, AttributeError):
        return None


def _collect_dxf_geometry(
    text: str,
    insunits_code: int,
) -> tuple[list[CanonicalCurve], list[CanonicalPoint3D], list[str]]:
    """Second pass: extract CanonicalCurve/Point3D from DXF geometry entities.

    Returns (curves, standalone_points, warnings).
    Only entities with sufficient coordinate data are produced.
    Invalid/unsupported entities are silently skipped with a warning appended.
    """
    mm_per_unit = Decimal(str(_DXF_INSUNITS_TO_MM.get(insunits_code, 1.0)))

    def _q(val: float) -> Quantity:
        return Quantity(Decimal(str(val)) * mm_per_unit, Unit.MM)

    def _pt(x: float, y: float, z: float, ref: str | None = None) -> CanonicalPoint3D:
        return CanonicalPoint3D(
            x=_q(x), y=_q(y), z=_q(z),
            source_entity_ref=ref,
        )

    curves: list[CanonicalCurve] = []
    standalone_points: list[CanonicalPoint3D] = []
    warnings: list[str] = []

    lines = text.splitlines()
    n = len(lines)
    i = 0
    in_geometry_section = False
    current_entity: str | None = None
    entity_index = 0
    coords: dict[int, float] = {}
    handle: str | None = None
    layer: str | None = None
    # LWPOLYLINE vertex accumulation
    lw_vertices: list[tuple[float, float]] = []
    lw_pending_x: float | None = None

    def flush() -> None:
        nonlocal current_entity, entity_index, handle, layer, lw_vertices, lw_pending_x
        etype = current_entity
        if etype is None:
            return
        idx = entity_index
        entity_index += 1
        cur_handle = handle or f"dxf-{etype.lower()}-{idx:06d}"

        try:
            import math

            if etype == "LINE":
                x0 = coords.get(10, 0.0)
                y0 = coords.get(20, 0.0)
                z0 = coords.get(30, 0.0)
                x1 = coords.get(11, x0)
                y1 = coords.get(21, y0)
                z1 = coords.get(31, z0)
                origin = _pt(x0, y0, z0, cur_handle)
                end_pt = _pt(x1, y1, z1, cur_handle)
                curves.append(CanonicalCurve(
                    curve_id=f"dxf-line-{idx:06d}",
                    curve_type=CanonicalCurveType.LINE,
                    source_entity_ref=cur_handle,
                    origin=origin,
                    metadata={"end_point": end_pt, "layer": layer or ""},
                ))

            elif etype == "CIRCLE":
                cx, cy, cz = coords.get(10, 0.0), coords.get(20, 0.0), coords.get(30, 0.0)
                r = coords.get(40)
                if r is None or r <= 0.0:
                    warnings.append(f"CIRCLE {cur_handle}: invalid radius {r}")
                    return
                curves.append(CanonicalCurve(
                    curve_id=f"dxf-circle-{idx:06d}",
                    curve_type=CanonicalCurveType.CIRCLE,
                    source_entity_ref=cur_handle,
                    center=_pt(cx, cy, cz, cur_handle),
                    radius=_q(r),
                    metadata={"layer": layer or ""},
                ))

            elif etype == "ARC":
                cx, cy, cz = coords.get(10, 0.0), coords.get(20, 0.0), coords.get(30, 0.0)
                r = coords.get(40)
                if r is None or r <= 0.0:
                    warnings.append(f"ARC {cur_handle}: invalid radius {r}")
                    return
                curves.append(CanonicalCurve(
                    curve_id=f"dxf-arc-{idx:06d}",
                    curve_type=CanonicalCurveType.ARC,
                    source_entity_ref=cur_handle,
                    center=_pt(cx, cy, cz, cur_handle),
                    radius=_q(r),
                    metadata={
                        "start_angle_deg": coords.get(50, 0.0),
                        "end_angle_deg": coords.get(51, 360.0),
                        "layer": layer or "",
                    },
                ))

            elif etype == "POINT":
                px = coords.get(10, 0.0)
                py = coords.get(20, 0.0)
                pz = coords.get(30, 0.0)
                standalone_points.append(CanonicalPoint3D(
                    x=_q(px), y=_q(py), z=_q(pz),
                    point_id=f"dxf-point-{idx:06d}",
                    source_entity_ref=cur_handle,
                    metadata={"layer": layer or ""},
                ))

            elif etype == "LWPOLYLINE":
                if lw_pending_x is not None:
                    lw_vertices.append((lw_pending_x, 0.0))
                    lw_pending_x = None
                if len(lw_vertices) >= 2:
                    cps = tuple(
                        CanonicalPoint3D(
                            x=_q(vx), y=_q(vy),
                            z=Quantity(Decimal("0"), Unit.MM),
                            source_entity_ref=cur_handle,
                        )
                        for vx, vy in lw_vertices
                    )
                    curves.append(CanonicalCurve(
                        curve_id=f"dxf-polyline-{idx:06d}",
                        curve_type=CanonicalCurveType.POLYLINE,
                        source_entity_ref=cur_handle,
                        control_points=cps,
                        metadata={"layer": layer or "", "vertex_count": len(lw_vertices)},
                    ))

            elif etype == "ELLIPSE":
                cx, cy, cz = coords.get(10, 0.0), coords.get(20, 0.0), coords.get(30, 0.0)
                ex = coords.get(11, 1.0)
                ey = coords.get(21, 0.0)
                ez = coords.get(31, 0.0)
                ratio = coords.get(40, 1.0)
                major = math.hypot(ex, ey, ez)
                if major <= 0.0 or ratio <= 0.0:
                    warnings.append(f"ELLIPSE {cur_handle}: invalid major axis or ratio")
                    return
                major_r = _q(major)
                minor_val = major_r.value * Decimal(str(ratio))
                if minor_val <= 0:
                    warnings.append(f"ELLIPSE {cur_handle}: computed minor radius ≤ 0")
                    return
                curves.append(CanonicalCurve(
                    curve_id=f"dxf-ellipse-{idx:06d}",
                    curve_type=CanonicalCurveType.ELLIPSE,
                    source_entity_ref=cur_handle,
                    center=_pt(cx, cy, cz, cur_handle),
                    major_radius=major_r,
                    minor_radius=Quantity(minor_val, Unit.MM),
                    metadata={"layer": layer or "", "ratio": ratio},
                ))

        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{etype} {cur_handle}: geometry extraction failed: {exc}")

        current_entity = None
        handle = None
        layer = None
        coords.clear()
        lw_vertices = []
        lw_pending_x = None

    while i < n - 1:
        try:
            gc_raw = lines[i].strip()
            value = lines[i + 1].strip()
        except IndexError:
            break
        i += 2

        try:
            gc = int(gc_raw)
        except ValueError:
            continue

        if gc == 0 and value == "SECTION":
            flush()
            current_entity = None
            if i < n - 1 and lines[i].strip() == "2":
                sname = lines[i + 1].strip().upper()
                in_geometry_section = sname in ("ENTITIES", "BLOCKS")
                i += 2
            else:
                in_geometry_section = False
        elif gc == 0 and value in ("ENDSEC", "EOF"):
            flush()
            current_entity = None
            in_geometry_section = False
        elif gc == 0 and in_geometry_section:
            flush()
            if value in _GEOMETRY_ENTITY_TYPES:
                current_entity = value
                handle = None
                layer = None
                coords = {}
                lw_vertices = []
                lw_pending_x = None
        elif current_entity is not None:
            if gc == 5:
                handle = value or None
            elif gc == 8:
                layer = value
            elif current_entity == "LWPOLYLINE" and gc == 10:
                f = _safe_float(value)
                if f is not None:
                    lw_pending_x = f
            elif current_entity == "LWPOLYLINE" and gc == 20:
                f = _safe_float(value)
                if f is not None and lw_pending_x is not None:
                    lw_vertices.append((lw_pending_x, f))
                    lw_pending_x = None
            elif gc in (10, 11, 20, 21, 30, 31, 40, 50, 51):
                if current_entity != "LWPOLYLINE":
                    f = _safe_float(value)
                    if f is not None:
                        coords[gc] = f

    flush()
    return curves, standalone_points, warnings


def _build_dxf_canonical_geometry(
    curves: list[CanonicalCurve],
    standalone_points: list[CanonicalPoint3D],
) -> CanonicalGeometry | None:
    """Assemble CanonicalGeometry with bounding box from DXF-extracted primitives."""
    if not curves and not standalone_points:
        return None

    # Compute bounding box from all known coordinate samples
    coord_samples: list[tuple[Decimal, Decimal, Decimal]] = []
    for pt in standalone_points:
        coord_samples.append((pt.x.value, pt.y.value, pt.z.value))
    for c in curves:
        if c.origin is not None:
            coord_samples.append((c.origin.x.value, c.origin.y.value, c.origin.z.value))
        if c.center is not None:
            coord_samples.append((c.center.x.value, c.center.y.value, c.center.z.value))
            if c.radius is not None:
                r = c.radius.value
                cx, cy, cz = c.center.x.value, c.center.y.value, c.center.z.value
                coord_samples.extend([
                    (cx + r, cy, cz), (cx - r, cy, cz),
                    (cx, cy + r, cz), (cx, cy - r, cz),
                ])
        for cp in c.control_points:
            coord_samples.append((cp.x.value, cp.y.value, cp.z.value))
        if c.metadata:
            ep = c.metadata.get("end_point")
            if isinstance(ep, CanonicalPoint3D):
                coord_samples.append((ep.x.value, ep.y.value, ep.z.value))

    bounding_box: BoundingBox3D | None = None
    if coord_samples:
        xs = [s[0] for s in coord_samples]
        ys = [s[1] for s in coord_samples]
        zs = [s[2] for s in coord_samples]
        try:
            bounding_box = BoundingBox3D(
                min_point=CanonicalPoint3D(
                    x=Quantity(min(xs), Unit.MM),
                    y=Quantity(min(ys), Unit.MM),
                    z=Quantity(min(zs), Unit.MM),
                ),
                max_point=CanonicalPoint3D(
                    x=Quantity(max(xs), Unit.MM),
                    y=Quantity(max(ys), Unit.MM),
                    z=Quantity(max(zs), Unit.MM),
                ),
            )
        except Exception:  # noqa: BLE001
            bounding_box = None

    return CanonicalGeometry(
        geometry_id="geometry-dxf",
        curves=tuple(curves),
        bounding_box=bounding_box,
        metadata={
            "standalone_points": tuple(standalone_points),
        },
    )


def _parse_dxf_text(text: str) -> dict[str, Any]:
    """Tokenize a text DXF file into section/entity metadata.

    Returns:
        sections, entity_counts, layers, dxf_version, units, bounds, valid,
        unsupported_entities, warnings
    """
    result: dict[str, Any] = {
        "sections": [],
        "entity_counts": {},
        "layers": set(),
        "dxf_version": None,
        "units": None,
        "bounds": None,
        "valid": False,
        "unsupported_entities": [],
        "warnings": [],
    }

    lines = text.splitlines()
    i = 0
    n = len(lines)
    sections: list[str] = []
    entity_types: list[str] = []
    layers: set[str] = set()
    unsupported: list[str] = []

    # Bounds tracking
    xs: list[float] = []
    ys: list[float] = []

    # Current entity context
    current_entity: str | None = None
    coords: dict[int, float] = {}  # group_code → float value

    def flush_entity_coords() -> None:
        """Extract bound-relevant coordinates from the buffered entity."""
        if current_entity is None:
            return
        # LINE: (10,20) start, (11,21) end
        if current_entity in ("LINE",):
            for xc, yc in ((10, 20), (11, 21)):
                x, y = coords.get(xc), coords.get(yc)
                if x is not None and y is not None:
                    xs.append(x)
                    ys.append(y)
        # CIRCLE/ARC: center ± radius
        elif current_entity in ("CIRCLE", "ARC"):
            cx, cy, r = coords.get(10), coords.get(20), coords.get(40)
            if cx is not None and cy is not None:
                xs.append(cx)
                ys.append(cy)
                if r is not None and r > 0:
                    xs.extend([cx + r, cx - r])
                    ys.extend([cy + r, cy - r])
        # POINT: (10,20)
        elif current_entity == "POINT":
            x, y = coords.get(10), coords.get(20)
            if x is not None and y is not None:
                xs.append(x)
                ys.append(y)
        # ELLIPSE: center + major-axis endpoint + ratio → approximate
        elif current_entity == "ELLIPSE":
            cx, cy = coords.get(10), coords.get(20)
            ex, ey = coords.get(11), coords.get(21)
            if cx is not None and cy is not None and ex is not None and ey is not None:
                import math
                major = math.hypot(ex, ey)
                xs.extend([cx - major, cx + major])
                ys.extend([cy - major, cy + major])
        coords.clear()

    insect_in_header = False
    in_header = False

    while i < n - 1:
        try:
            group_code_raw = lines[i].strip()
            value = lines[i + 1].strip()
        except IndexError:
            break
        i += 2

        try:
            gc = int(group_code_raw)
        except ValueError:
            continue

        # Section tracking
        if gc == 0 and value == "SECTION":
            flush_entity_coords()
            current_entity = None
            if i < n - 1 and lines[i].strip() == "2":
                section_name = lines[i + 1].strip().upper()
                sections.append(section_name)
                in_header = (section_name == "HEADER")
                i += 2

        elif gc == 0 and value == "ENDSEC":
            flush_entity_coords()
            current_entity = None
            in_header = False

        # DXF version from HEADER
        elif gc == 9 and value == "$ACADVER" and in_header:
            if i < n - 1 and lines[i].strip() == "1":
                result["dxf_version"] = lines[i + 1].strip()
                i += 2

        # Units from HEADER ($INSUNITS)
        elif gc == 9 and value == "$INSUNITS" and in_header:
            insect_in_header = True

        elif gc == 70 and insect_in_header:
            insect_in_header = False
            try:
                unit_code = int(value)
                result["units"] = _DXF_INSUNITS.get(unit_code, f"unit_{unit_code}")
            except ValueError:
                pass

        # Entity tracking in ENTITIES/BLOCKS sections
        elif gc == 0:
            flush_entity_coords()
            if value in _ALL_ENTITY_TYPES:
                entity_types.append(value)
                current_entity = value
                coords = {}
            elif value in ("EOF", "SECTION", "ENDSEC", "TABLE", "ENDTAB",
                            "LAYER", "LTYPE", "VIEW", "UCS", "APPID",
                            "DIMSTYLE", "VPORT", "BLOCK_RECORD"):
                flush_entity_coords()
                current_entity = None
            elif value not in ("", "EOF"):
                # Unknown entity type
                if value not in unsupported:
                    unsupported.append(value)
                flush_entity_coords()
                current_entity = None

        # Layer name (group code 8)
        elif gc == 8 and value:
            layers.add(value)

        # Coordinate values for bounds
        elif gc in (10, 11, 20, 21) and current_entity is not None:
            f = _safe_float(value)
            if f is not None:
                coords[gc] = f

        # Radius (CIRCLE/ARC)
        elif gc == 40 and current_entity in ("CIRCLE", "ARC", "ELLIPSE"):
            f = _safe_float(value)
            if f is not None:
                coords[40] = f

        # Ellipse major axis endpoint components
        elif gc in (11, 21) and current_entity == "ELLIPSE":
            f = _safe_float(value)
            if f is not None:
                coords[gc] = f

        # LWPOLYLINE vertex accumulation (group codes 10/20 repeat for each vertex)
        # handled by the generic 10/20 branch above

    flush_entity_coords()

    result["sections"] = sections
    result["entity_counts"] = dict(Counter(entity_types))
    result["layers"] = layers
    result["valid"] = "ENTITIES" in sections or "HEADER" in sections

    # Compute bounds
    if xs and ys:
        result["bounds"] = {
            "xmin": min(xs),
            "xmax": max(xs),
            "ymin": min(ys),
            "ymax": max(ys),
            "zmin": 0.0,
            "zmax": 0.0,
        }

    # Filter unsupported to only really unknown ones (not DXF structural tokens)
    _STRUCTURAL = frozenset({
        "EOF", "SECTION", "ENDSEC", "ENDBLK", "TABLE", "ENDTAB", "SEQEND",
        "LAYER", "LTYPE", "VIEW", "UCS", "APPID", "DIMSTYLE", "VPORT",
        "BLOCK_RECORD", "STYLE", "IDBUFFER", "GROUP", "MLINESTYLE", "ACDBDICTIONARYWDFLT",
        "ACDBPLACEHOLDER", "XRECORD", "DICTIONARY", "IMAGEDEF", "IMAGEDEF_REACTOR",
        "MATERIAL", "VISUALSTYLE", "SCALE", "MLEADERSTYLE", "WIPEOUTVARIABLES",
        "DBCOLOR", "ACAD_TABLE", "ACAD_PROXY_ENTITY",
    })
    result["unsupported_entities"] = [
        e for e in unsupported
        if e not in _STRUCTURAL and e not in _ALL_ENTITY_TYPES
    ][:20]  # cap at 20

    return result


class DxfTokenAdapter(FormatAdapter):
    """DXF format adapter (Level 0–1 pure Python, Level 2 with ezdxf)."""

    @staticmethod
    def _ezdxf_available() -> bool:
        try:
            import ezdxf  # noqa: F401
            return True
        except ImportError:
            return False

    def metadata(self) -> AdapterMetadata:
        caps = [
            AdapterCapability.RECOGNIZE,
            AdapterCapability.PARSE,
            AdapterCapability.NORMALIZE,
            AdapterCapability.EXTRACT_DRAWING,
        ]
        if self._ezdxf_available():
            caps.append(AdapterCapability.EXTRACT_GEOMETRY)
        return AdapterMetadata(
            adapter_id=_ADAPTER_ID,
            adapter_name="MachineryPro DXF Token Adapter",
            adapter_version=_ADAPTER_VERSION,
            format_ids=("DXF",),
            capabilities=tuple(caps),
            max_capability_level=(
                CapabilityLevel.LEVEL_2_NORMALIZED
                if self._ezdxf_available()
                else CapabilityLevel.LEVEL_1_PARSED
            ),
            adapter_license=AdapterLicense.INTERNAL_PARSER,
            requires_external_dependency=True,
            external_dependency_name="ezdxf (optional; Level 2 geometry)",
            notes=(
                "Pure-Python DXF parser reaches Level 1. "
                "Level 2 requires ezdxf (MIT): pip install ezdxf"
            ),
        )

    def can_handle(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor | None = None,
    ) -> bool:
        if source.source_format_id == "DXF":
            return True
        if format_descriptor and format_descriptor.format_id == "DXF":
            return True
        if source.file_name and source.file_name.lower().endswith(".dxf"):
            return True
        return False

    def ingest(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor,
    ) -> CanonicalDocument:
        return self._ingest_text(source, format_descriptor, source.notes)

    def ingest_file(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor,
        content_path: Path,
    ) -> CanonicalDocument:
        """Ingest the complete bounded upload from its staged path."""
        text = content_path.read_text(encoding="utf-8", errors="replace")
        return self._ingest_text(source, format_descriptor, text)

    def _ingest_text(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor,
        text: str | None,
    ) -> CanonicalDocument:
        session = AdapterSession(source, format_descriptor, self.metadata())

        if not text:
            session.mark_failed()
            session.record(FidelityClass.LOST, "No DXF content provided")
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()

        # Level 0 check: group-code pattern
        lines = text.splitlines()[:10]
        has_group0 = any(
            i < len(lines) - 1 and lines[i].strip() == "0"
            for i in range(len(lines))
        )
        if not has_group0:
            session.mark_failed()
            session.record(
                FidelityClass.LOST,
                "Content does not match DXF group-code format",
            )
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()

        # Parse
        try:
            meta = _parse_dxf_text(text)
        except Exception as exc:  # noqa: BLE001
            session.mark_failed()
            session.record(FidelityClass.LOST, f"DXF parse error: {exc}")
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()

        session.mark_parsed()
        entity_counts: dict[str, int] = meta["entity_counts"]
        total_entities = sum(entity_counts.values())
        session.set_source_entity_count(total_entities)

        bounds = meta.get("bounds")  # dict or None

        # Build a flat, JSON-serializable metadata dict
        header_meta: dict[str, Any] = {
            "dxf_version": meta.get("dxf_version") or "unknown",
            "sections": ", ".join(meta["sections"]) if meta["sections"] else "",
            "entity_count": total_entities,
            "layer_count": len(meta["layers"]),
            "layers": ", ".join(sorted(meta["layers"]))[:500] if meta["layers"] else "",
        }
        if meta.get("units"):
            header_meta["units"] = meta["units"]
        if bounds:
            header_meta["xmin"] = bounds["xmin"]
            header_meta["xmax"] = bounds["xmax"]
            header_meta["ymin"] = bounds["ymin"]
            header_meta["ymax"] = bounds["ymax"]
        if meta.get("unsupported_entities"):
            header_meta["unsupported_entities"] = ", ".join(meta["unsupported_entities"][:10])

        # Promote entity_type_summary as individual keys for API serialization
        for etype, cnt in entity_counts.items():
            header_meta[f"entity_{etype.lower()}"] = cnt

        header_ref = CanonicalEntityRef(
            entity_id=make_uid("DXF-HEADER-"),
            entity_kind="DxfHeader",
            metadata=header_meta,
        )
        session.add_entity_ref(header_ref)

        if not meta["valid"]:
            session.record_partial(
                "DXF file may be incomplete; no HEADER or ENTITIES section found"
            )

        for etype in meta.get("unsupported_entities", []):
            session.record_unsupported(f"Unsupported DXF entity type: {etype}")

        # Level 2 geometry extraction — pure Python (no external deps)
        insunits_code = 0
        raw_units = meta.get("units")
        if raw_units is not None:
            for code, name in _DXF_INSUNITS.items():
                if name == raw_units:
                    insunits_code = code
                    break
        geo_curves, geo_points, geo_warnings = _collect_dxf_geometry(text, insunits_code)
        for w in geo_warnings:
            session.record_partial(f"DXF geometry: {w}")
        geometry = _build_dxf_canonical_geometry(geo_curves, geo_points)
        if geometry is not None:
            session.set_geometry(geometry)
            session.mark_geometry()

        # Level 2 full normalization via ezdxf (optional — upgrades to LEVEL_2_NORMALIZED)
        if self._ezdxf_available():
            self._normalize_geometry_ezdxf(text, session)
        else:
            session.record_unsupported(
                "Full ezdxf geometry normalization not available (MIT license). "
                "Install via: pip install ezdxf"
            )
            session.set_fidelity_completeness(FidelityReportCompleteness.PARTIAL)
            return session.build()

        session.mark_normalized()
        session.set_fidelity_completeness(FidelityReportCompleteness.COMPLETE)
        return session.build()

    @staticmethod
    def _normalize_geometry_ezdxf(text: str, session: AdapterSession) -> None:
        try:
            import io

            import ezdxf

            doc = ezdxf.read(io.StringIO(text))
            msp = doc.modelspace()

            geometry_entities = []
            for entity in msp:
                dxftype = entity.dxftype()
                entity_ref = CanonicalEntityRef(
                    entity_id=make_uid("DXF-ENT-"),
                    entity_kind=f"DxfEntity_{dxftype}",
                    source_entity_id=(
                        str(entity.dxf.handle) if hasattr(entity.dxf, "handle") else None
                    ),
                    metadata={"dxftype": dxftype},
                )
                session.add_entity_ref(entity_ref)
                if dxftype in _GEOMETRY_ENTITY_TYPES:
                    geometry_entities.append(entity_ref)

            if not geometry_entities:
                session.record_unsupported(
                    "DXF modelspace contains no recognized geometry entities"
                )
            else:
                # Full CanonicalGeometry mapping deferred to Stage 4C-c
                session.record_partial(
                    f"ezdxf read {len(geometry_entities)} geometry entity(ies); "
                    "entity → CER mapping deferred to Stage 4C-c DXFGeometryBridge"
                )

        except Exception as exc:  # noqa: BLE001
            session.mark_partial()
            session.record_lost(f"ezdxf geometry normalization failed: {exc}")
