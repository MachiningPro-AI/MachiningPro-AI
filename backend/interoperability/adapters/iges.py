"""Strict IGES 5.x geometry and topology adapter.

The adapter parses byte-accurate fixed records in pure Python and reaches
Level 2 only when the declared supported subset produces real canonical
geometry. Unsupported semantic dependencies are reported explicitly.
"""

from __future__ import annotations

from pathlib import Path

from backend.interoperability.adapter import FormatAdapter
from backend.interoperability.adapters._base import AdapterSession, make_uid
from backend.interoperability.enums import (
    AdapterCapability,
    AdapterLicense,
    CapabilityLevel,
    FidelityClass,
    FidelityReportCompleteness,
    FormatFamily,
)
from backend.interoperability.iges_mapping import map_iges_model
from backend.interoperability.iges_parser import IgesParseError, parse_iges_bytes
from backend.interoperability.models import (
    AdapterMetadata,
    CanonicalDocument,
    CanonicalEntityRef,
    EngineeringSource,
    FormatDescriptor,
)

__all__ = ["IGES_DESCRIPTOR", "IgesTokenAdapter"]

_ADAPTER_ID = "machinerypro-iges-token-v1"
_ADAPTER_VERSION = "2.0.0"

IGES_DESCRIPTOR = FormatDescriptor(
    format_id="IGES",
    canonical_name="IGES 5.x",
    family=FormatFamily.NEUTRAL_EXCHANGE,
    extensions=("igs", "iges"),
    media_types=("model/iges",),
    vendor="ANSI",
    is_open=True,
    is_proprietary=False,
    adapter_license=AdapterLicense.INTERNAL_PARSER,
    notes="ANSI/ASME Y14.26M — Initial Graphics Exchange Specification",
)

_IGES_ENTITY_NAMES: dict[int, str] = {
    100: "Circular Arc",
    102: "Composite Curve",
    104: "Conic Arc",
    106: "Copious Data",
    108: "Plane",
    110: "Line",
    112: "Parametric Spline Curve",
    114: "Parametric Spline Surface",
    116: "Point",
    118: "Ruled Surface",
    120: "Surface of Revolution",
    122: "Tabulated Cylinder",
    123: "Direction",
    124: "Transformation Matrix",
    126: "Rational B-Spline Curve",
    128: "Rational B-Spline Surface",
    130: "Offset Curve",
    140: "Offset Surface",
    141: "Boundary",
    142: "Curve on Parametric Surface",
    143: "Bounded Surface",
    144: "Trimmed Surface",
    186: "Manifold Solid B-Rep Object",
    190: "Plane Surface",
    192: "Right Circular Cylindrical Surface",
    194: "Right Circular Conical Surface",
    196: "Spherical Surface",
    198: "Toroidal Surface",
    212: "General Note",
    314: "Color Definition",
    320: "Attribute Table Instance",
    322: "Attribute Definition Table",
    402: "Associativity Instance",
    404: "Drawing",
    406: "Property",
    408: "Singular Subfigure Instance",
    410: "View",
    412: "Rectangular Array Subfigure Instance",
    414: "Circular Array Subfigure Instance",
    416: "External Reference",
    418: "Nodal Load/Constraint",
    420: "Network Subfigure Definition",
    422: "Attribute Table Definition",
    502: "Vertex List",
    504: "Edge List",
    508: "Loop",
    510: "Face",
    514: "Shell",
}


class IgesTokenAdapter(FormatAdapter):
    """Fail-closed IGES adapter for an explicitly supported Level 2 subset."""

    def metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            adapter_id=_ADAPTER_ID,
            adapter_name="MachineryPro IGES Canonical Adapter",
            adapter_version=_ADAPTER_VERSION,
            format_ids=("IGES",),
            capabilities=(
                AdapterCapability.RECOGNIZE,
                AdapterCapability.PARSE,
                AdapterCapability.NORMALIZE,
                AdapterCapability.EXTRACT_GEOMETRY,
                AdapterCapability.EXTRACT_TOPOLOGY,
            ),
            max_capability_level=CapabilityLevel.LEVEL_2_NORMALIZED,
            adapter_license=AdapterLicense.INTERNAL_PARSER,
            requires_external_dependency=False,
            notes=(
                "Strict fixed-record IGES parser with canonical geometry and "
                "B-Rep mapping for the declared supported subset."
            ),
        )

    def can_handle(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor | None = None,
    ) -> bool:
        if source.source_format_id == "IGES":
            return True
        if format_descriptor and format_descriptor.format_id == "IGES":
            return True
        if source.file_name:
            lower = source.file_name.lower()
            if lower.endswith((".igs", ".iges")):
                return True
        return False

    def ingest(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor,
    ) -> CanonicalDocument:
        if source.notes is None:
            return self._ingest_bytes(source, format_descriptor, None)
        try:
            content = source.notes.encode("ascii")
        except UnicodeEncodeError:
            content = source.notes.encode("utf-8")
        return self._ingest_bytes(source, format_descriptor, content)

    def ingest_file(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor,
        content_path: Path,
    ) -> CanonicalDocument:
        """Ingest the complete bounded upload from its staged path."""

        try:
            content = content_path.read_bytes()
        except OSError:
            session = AdapterSession(source, format_descriptor, self.metadata())
            session.mark_failed()
            session.record(
                FidelityClass.LOST,
                "Unable to read staged IGES content",
            )
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()
        return self._ingest_bytes(source, format_descriptor, content)

    def _ingest_bytes(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor,
        content: bytes | None,
    ) -> CanonicalDocument:
        session = AdapterSession(source, format_descriptor, self.metadata())
        if not content:
            session.mark_failed()
            session.record(FidelityClass.LOST, "No IGES content provided")
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()

        try:
            model = parse_iges_bytes(content)
        except IgesParseError as exc:
            session.mark_failed()
            session.record(FidelityClass.LOST, f"IGES parse error: {exc}")
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()

        session.mark_parsed()
        session.set_source_entity_count(len(model.entities))
        entity_counts: dict[int, int] = {}
        for entity in model.entities:
            entity_type = entity.directory.entity_type
            entity_counts[entity_type] = entity_counts.get(entity_type, 0) + 1

        # Build entity type distribution for metadata — only JSON-serializable values
        entity_type_named: dict[str, int] = {
            _IGES_ENTITY_NAMES.get(etype, f"type_{etype}"): cnt
            for etype, cnt in sorted(entity_counts.items())
        }

        # Determine unsupported entity types (not in our known-names dict)
        _KNOWN_ENTITY_TYPES = frozenset(_IGES_ENTITY_NAMES)
        unsupported_entity_types: list[str] = [
            f"type_{etype}"
            for etype in sorted(entity_counts)
            if etype not in _KNOWN_ENTITY_TYPES
        ][:20]

        # Convert Decimal fields to float for JSON serialisation
        def _to_float(val: object) -> float | None:
            if val is None:
                return None
            try:
                return float(val)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return None

        # Header entity ref metadata: all values must be str | int | float | bool | None
        header_meta: dict[str, object] = {
            "iges_version": model.global_section.version,
            "source_unit": model.global_section.unit_name,
            "model_scale": _to_float(model.global_section.model_scale),
            "minimum_resolution": _to_float(model.global_section.minimum_resolution),
            "source_file_name": model.global_section.file_name,
            "native_system_id": model.global_section.native_system_id,
            "preprocessor_version": model.global_section.preprocessor_version,
            "creation_timestamp": model.global_section.creation_timestamp,
            "modified_timestamp": model.global_section.modified_timestamp,
            "section_counts": str(dict(model.section_counts)),
            "entity_count": len(model.entities),
        }
        # Promote individual entity type counts as top-level keys
        for ename, cnt in entity_type_named.items():
            safe_key = "entity_" + ename.lower().replace(" ", "_")[:40]
            header_meta[safe_key] = cnt
        if unsupported_entity_types:
            header_meta["unsupported_entity_types"] = ", ".join(unsupported_entity_types[:10])

        session.add_entity_ref(
            CanonicalEntityRef(
                entity_id=make_uid("IGES-HEADER-"),
                entity_kind="IgesHeader",
                metadata=header_meta,
            )
        )

        # --- map_iges_model: isolated so its failure doesn't lose the Level-1 data ---
        try:
            mapping = map_iges_model(model)
        except Exception as exc:  # noqa: BLE001
            session.record(
                FidelityClass.PARTIALLY_PRESERVED,
                f"IGES geometry mapping failed (Level 1 parse preserved): {exc}",
            )
            session.mark_partial()
            session.set_fidelity_completeness(FidelityReportCompleteness.PARTIAL)
            return session.build()

        for ref in mapping.entity_refs:
            session.add_entity_ref(ref)
        if mapping.geometry is not None:
            session.set_geometry(mapping.geometry)
            session.mark_normalized()
        if mapping.topology is not None:
            session.set_topology(mapping.topology)

        refs_by_source = {
            ref.source_entity_id: ref
            for ref in mapping.entity_refs
            if ref.source_entity_id is not None
        }
        for issue in mapping.issues:
            description = (
                f"IGES DE={issue.de_pointer} type={issue.entity_type} "
                f"form={issue.form_number}: {issue.reason}"
            )
            if "unsupported" in issue.reason.lower():
                fidelity_class = FidelityClass.UNSUPPORTED
            elif issue.fatal:
                fidelity_class = FidelityClass.LOST
            else:
                fidelity_class = FidelityClass.PARTIALLY_PRESERVED
            session.record(
                fidelity_class,
                description,
                source_ref=refs_by_source.get(str(issue.de_pointer)),
            )

        invalid_fatal_issue = any(
            issue.fatal and "unsupported" not in issue.reason.lower()
            for issue in mapping.issues
        )
        unsupported_fatal_issue = any(
            issue.fatal and "unsupported" in issue.reason.lower()
            for issue in mapping.issues
        )
        if invalid_fatal_issue:
            session.mark_failed()
            session.set_fidelity_completeness(FidelityReportCompleteness.PARTIAL)
        elif unsupported_fatal_issue:
            session.mark_unsupported()
            session.set_fidelity_completeness(FidelityReportCompleteness.PARTIAL)
        elif mapping.issues:
            session.mark_partial()
            session.set_fidelity_completeness(FidelityReportCompleteness.PARTIAL)
        elif mapping.geometry is None:
            session.record_unsupported(
                "IGES file contains no supported geometry entities"
            )
            session.mark_partial()
            session.set_fidelity_completeness(FidelityReportCompleteness.PARTIAL)
        else:
            session.set_fidelity_completeness(FidelityReportCompleteness.COMPLETE)
        return session.build()
