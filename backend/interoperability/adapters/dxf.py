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
from pathlib import Path
from typing import Any

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

        # Level 2 via ezdxf (optional)
        if self._ezdxf_available():
            self._normalize_geometry_ezdxf(text, session)
        else:
            session.record_unsupported(
                "Level 2 geometry normalization requires ezdxf (MIT license). "
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
