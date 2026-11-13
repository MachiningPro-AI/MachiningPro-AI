"""Missing Engineering Data Resolution (P0).

Provides a deterministic model and analysis pipeline for identifying missing
engineering metadata after CAD/drawing import and tracking provenance through
user confirmation.

HARD RULES (from task specification — verbatim):
  - UNKNOWN must remain UNKNOWN until supported by explicit file evidence
    or explicit user confirmation.
  - Never infer material, unit, tolerance, IT grade, Ra, Rz, hole depth,
    thread, datum, GD&T, heat treatment, or coating.
  - Do NOT silently apply defaults.
  - Every resolved engineering value must carry provenance.
  - USER_CONFIRMED data must never be reported as file-extracted data.
  - Do NOT overwrite original extraction results.
  - Do NOT enable automatic manufacturing action.

FABRICATED_DEFAULT_MATERIAL=NO
FABRICATED_DEFAULT_UNIT=NO
FABRICATED_DEFAULT_TOLERANCE=NO
AUTO_FILL_MISSING_DATA=NO
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class EngineeringFieldStatus(StrEnum):
    """Knowledge status of a single engineering field.

    KNOWN             — Value present in the file; provenance recorded.
    UNKNOWN           — Not found in file; may be resolvable by user.
    USER_CONFIRMED    — User explicitly provided or confirmed.
    CONFLICT          — File value and user value differ; requires review.
    NOT_APPLICABLE    — Field does not apply to this document type.
    """

    KNOWN = "KNOWN"
    UNKNOWN = "UNKNOWN"
    USER_CONFIRMED = "USER_CONFIRMED"
    CONFLICT = "CONFLICT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EngineeringFieldSource(StrEnum):
    """Where a resolved engineering field value came from."""

    CAD_GEOMETRY = "CAD_GEOMETRY"
    DRAWING_TEXT = "DRAWING_TEXT"
    TITLE_BLOCK = "TITLE_BLOCK"
    FILE_METADATA = "FILE_METADATA"
    USER_CONFIRMED = "USER_CONFIRMED"
    LIBRARY_RESOLUTION = "LIBRARY_RESOLUTION"


class FieldRequirementTier(StrEnum):
    """Which downstream stage requires this field."""

    REQUIRED_FOR_GEOMETRY = "REQUIRED_FOR_GEOMETRY"
    REQUIRED_FOR_PROCESS_PLANNING = "REQUIRED_FOR_PROCESS_PLANNING"
    REQUIRED_FOR_TOOL_SELECTION = "REQUIRED_FOR_TOOL_SELECTION"
    REQUIRED_FOR_CUTTING_DATA = "REQUIRED_FOR_CUTTING_DATA"
    REQUIRED_FOR_CAM = "REQUIRED_FOR_CAM"
    OPTIONAL = "OPTIONAL"


class ReadinessState(StrEnum):
    """Per-stage manufacturing readiness indicator.

    Replaces the previous binary PASS/FAIL with granular pipeline-stage states.
    A stage can only advance when all required fields for that stage are KNOWN
    or USER_CONFIRMED.
    """

    READY_FOR_GEOMETRY_ANALYSIS = "READY_FOR_GEOMETRY_ANALYSIS"
    READY_FOR_DRAWING_REVIEW = "READY_FOR_DRAWING_REVIEW"
    BLOCKED_FOR_PROCESS_PLANNING = "BLOCKED_FOR_PROCESS_PLANNING"
    READY_FOR_PROCESS_PLANNING = "READY_FOR_PROCESS_PLANNING"
    BLOCKED_FOR_CUTTING_DATA = "BLOCKED_FOR_CUTTING_DATA"
    READY_FOR_CUTTING_DATA = "READY_FOR_CUTTING_DATA"
    BLOCKED_FOR_CAM = "BLOCKED_FOR_CAM"
    READY_FOR_CAM = "READY_FOR_CAM"


# ---------------------------------------------------------------------------
# Field definition registry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FieldDefinition:
    field_name: str
    tier: FieldRequirementTier
    description_en: str
    description_tr: str
    auto_extractable: bool
    extract_note: str = ""


FIELD_DEFINITIONS: dict[str, FieldDefinition] = {
    "unit": FieldDefinition(
        field_name="unit",
        tier=FieldRequirementTier.REQUIRED_FOR_PROCESS_PLANNING,
        description_en="Drawing unit system (mm / inch)",
        description_tr="Çizim birim sistemi (mm / inç)",
        auto_extractable=True,
        extract_note="From DXF header INSUNITS; from IGES unit code",
    ),
    "material": FieldDefinition(
        field_name="material",
        tier=FieldRequirementTier.REQUIRED_FOR_PROCESS_PLANNING,
        description_en="Material grade or designation (e.g. 42CrMo4, C45)",
        description_tr="Malzeme cinsi veya kodu (ör. 42CrMo4, C45)",
        auto_extractable=False,
        extract_note=(
            "May be extractable from DXF title block MTEXT if explicit "
            "designation is present. Never auto-filled."
        ),
    ),
    "tolerance_general": FieldDefinition(
        field_name="tolerance_general",
        tier=FieldRequirementTier.REQUIRED_FOR_CUTTING_DATA,
        description_en="General tolerance specification (e.g. ISO 2768-m)",
        description_tr="Genel tolerans standardı (ör. ISO 2768-m)",
        auto_extractable=True,
        extract_note="From MTEXT general tolerance table or note field",
    ),
    "hole_depth": FieldDefinition(
        field_name="hole_depth",
        tier=FieldRequirementTier.REQUIRED_FOR_PROCESS_PLANNING,
        description_en="Hole depth (required for L/D DFM and tool reach)",
        description_tr="Delik derinliği (L/D DFM analizi ve takım erişimi için)",
        auto_extractable=False,
        extract_note="2D drawings do not carry depth; must be supplied by user",
    ),
    "surface_finish": FieldDefinition(
        field_name="surface_finish",
        tier=FieldRequirementTier.REQUIRED_FOR_CUTTING_DATA,
        description_en="Required surface finish Ra/Rz (µm)",
        description_tr="İstenen yüzey pürüzlülüğü Ra/Rz (µm)",
        auto_extractable=False,
    ),
    "topology": FieldDefinition(
        field_name="topology",
        tier=FieldRequirementTier.REQUIRED_FOR_CAM,
        description_en=(
            "3D topology (B-Rep bodies, shells, edges) — "
            "required to confirm machining feature types"
        ),
        description_tr=(
            "3B topoloji (B-Rep gövdeler, kabuklar, kenarlar) — "
            "işleme özellik tiplerinin doğrulanması için gerekli"
        ),
        auto_extractable=False,
        extract_note="IGES surfaces-only files lack topology; reconstruction required",
    ),
}


# ---------------------------------------------------------------------------
# Engineering field (provenance-aware value container)
# ---------------------------------------------------------------------------

@dataclass
class FieldChange:
    """Single audit entry in an EngineeringField's history."""

    timestamp: datetime
    previous_status: EngineeringFieldStatus
    previous_value: str | None
    new_value: str | None
    new_source: EngineeringFieldSource
    changed_by: str  # "file_parser" | "user" | "library"
    note: str = ""


@dataclass
class EngineeringField:
    """Provenance-aware container for a single engineering value.

    Design invariants:
    - original_extracted_value is set once at parse time and never changed.
    - When a user provides a value, source becomes USER_CONFIRMED and
      confirmed_by_user becomes True.
    - When file evidence and user value differ, status becomes CONFLICT.
    - value=None means UNKNOWN — never use a string "unknown" for this.
    """

    field_name: str
    value: str | None
    status: EngineeringFieldStatus
    source: EngineeringFieldSource | None
    confidence: float | None
    confirmed_by_user: bool
    original_extracted_value: str | None
    history: list[FieldChange] = field(default_factory=list)
    library_resolved_id: str | None = None
    library_resolved_designation: str | None = None

    @classmethod
    def unknown(cls, field_name: str) -> "EngineeringField":
        """Construct a field with UNKNOWN status and no value."""
        return cls(
            field_name=field_name,
            value=None,
            status=EngineeringFieldStatus.UNKNOWN,
            source=None,
            confidence=None,
            confirmed_by_user=False,
            original_extracted_value=None,
        )

    @classmethod
    def known(
        cls,
        field_name: str,
        value: str,
        source: EngineeringFieldSource,
        confidence: float | None = None,
    ) -> "EngineeringField":
        """Construct a field with KNOWN status from file evidence."""
        return cls(
            field_name=field_name,
            value=value,
            status=EngineeringFieldStatus.KNOWN,
            source=source,
            confidence=confidence,
            confirmed_by_user=False,
            original_extracted_value=value,
        )

    @classmethod
    def not_applicable(cls, field_name: str) -> "EngineeringField":
        """Construct a field that does not apply to this document type."""
        return cls(
            field_name=field_name,
            value=None,
            status=EngineeringFieldStatus.NOT_APPLICABLE,
            source=None,
            confidence=None,
            confirmed_by_user=False,
            original_extracted_value=None,
        )

    def apply_user_confirmation(
        self,
        user_value: str,
        library_id: str | None = None,
        library_designation: str | None = None,
    ) -> "EngineeringField":
        """Return a new field with user-confirmed value.

        Does NOT overwrite original_extracted_value.
        If file_value and user_value differ, status becomes CONFLICT.
        """
        now = datetime.now(UTC)
        prev_status = self.status
        prev_value = self.value

        # Determine new status
        if (
            self.status is EngineeringFieldStatus.KNOWN
            and self.original_extracted_value is not None
            and self.original_extracted_value != user_value
        ):
            new_status = EngineeringFieldStatus.CONFLICT
        else:
            new_status = EngineeringFieldStatus.USER_CONFIRMED

        change = FieldChange(
            timestamp=now,
            previous_status=prev_status,
            previous_value=prev_value,
            new_value=user_value,
            new_source=EngineeringFieldSource.USER_CONFIRMED,
            changed_by="user",
        )
        new_history = list(self.history) + [change]

        return EngineeringField(
            field_name=self.field_name,
            value=user_value,
            status=new_status,
            source=EngineeringFieldSource.USER_CONFIRMED,
            confidence=1.0,
            confirmed_by_user=True,
            original_extracted_value=self.original_extracted_value,
            history=new_history,
            library_resolved_id=library_id,
            library_resolved_designation=library_designation,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "value": self.value,
            "status": self.status.value,
            "source": self.source.value if self.source else None,
            "confidence": self.confidence,
            "confirmed_by_user": self.confirmed_by_user,
            "original_extracted_value": self.original_extracted_value,
            "library_resolved_id": self.library_resolved_id,
            "library_resolved_designation": self.library_resolved_designation,
            "history_count": len(self.history),
        }

    @property
    def is_resolved(self) -> bool:
        """True when value is available or the field is not applicable."""
        return self.status in (
            EngineeringFieldStatus.KNOWN,
            EngineeringFieldStatus.USER_CONFIRMED,
            EngineeringFieldStatus.CONFLICT,
            EngineeringFieldStatus.NOT_APPLICABLE,
        )

    @property
    def is_blocking(self) -> bool:
        """True when the field is UNKNOWN (not resolved at all)."""
        return self.status is EngineeringFieldStatus.UNKNOWN


# ---------------------------------------------------------------------------
# Missing data analysis result
# ---------------------------------------------------------------------------

@dataclass
class MissingDataAnalysis:
    """Result of analyzing a CAD import result for missing engineering data.

    Provides a complete picture of what is known, unknown, and what is blocking
    each downstream manufacturing stage.

    Two-phase design:
    - RAW: analysis of the file as imported, without user input
    - POST_CONFIRMATION: analysis after user has supplied missing values
    """

    import_id: str
    document_format: str
    source_file_name: str | None

    # Field analysis
    fields: dict[str, EngineeringField]

    # Readiness states per stage
    readiness_states: dict[str, ReadinessState]

    # Computed summaries (derived from fields)
    known_field_names: list[str]
    unknown_field_names: list[str]
    required_missing_field_names: list[str]
    optional_missing_field_names: list[str]

    # Geometry status (not affected by metadata)
    geometry_ok: bool
    geometry_note: str

    # Blocking analysis
    blocking_stage_names: list[str]
    can_proceed_with_user_input: bool

    # Analysis metadata
    phase: str  # "RAW_FILE" | "AFTER_USER_CONFIRMATION"
    analyzed_at: datetime

    def as_dict(self) -> dict[str, Any]:
        return {
            "import_id": self.import_id,
            "document_format": self.document_format,
            "source_file_name": self.source_file_name,
            "phase": self.phase,
            "analyzed_at": self.analyzed_at.isoformat(),
            "geometry_ok": self.geometry_ok,
            "geometry_note": self.geometry_note,
            "known_fields": self.known_field_names,
            "unknown_fields": self.unknown_field_names,
            "required_missing_fields": self.required_missing_field_names,
            "optional_missing_fields": self.optional_missing_field_names,
            "blocking_stages": self.blocking_stage_names,
            "can_proceed_with_user_input": self.can_proceed_with_user_input,
            "readiness_states": {
                k: v.value for k, v in self.readiness_states.items()
            },
            "fields": {k: v.as_dict() for k, v in self.fields.items()},
        }


# ---------------------------------------------------------------------------
# Readiness computation
# ---------------------------------------------------------------------------

def _compute_readiness(
    fields: dict[str, EngineeringField],
    document_format: str,
    has_geometry: bool,
    has_topology: bool,
) -> dict[str, ReadinessState]:
    """Compute per-stage readiness from resolved fields.

    Returns a dict mapping stage name → ReadinessState.
    """
    def _field_ok(name: str) -> bool:
        f = fields.get(name)
        if f is None:
            return True  # field not applicable — don't block
        return f.status in (
            EngineeringFieldStatus.KNOWN,
            EngineeringFieldStatus.USER_CONFIRMED,
            EngineeringFieldStatus.NOT_APPLICABLE,
        )

    states: dict[str, ReadinessState] = {}

    # Geometry: always ready when import succeeded
    states["GEOMETRY"] = (
        ReadinessState.READY_FOR_GEOMETRY_ANALYSIS
        if has_geometry
        else ReadinessState.BLOCKED_FOR_PROCESS_PLANNING
    )

    # Drawing review: ready when geometry ok (annotation pipeline is separate)
    states["DRAWING_REVIEW"] = (
        ReadinessState.READY_FOR_DRAWING_REVIEW
        if has_geometry
        else ReadinessState.BLOCKED_FOR_PROCESS_PLANNING
    )

    # Process planning: requires unit + material
    pp_ok = has_geometry and _field_ok("unit") and _field_ok("material")
    states["PROCESS_PLANNING"] = (
        ReadinessState.READY_FOR_PROCESS_PLANNING
        if pp_ok
        else ReadinessState.BLOCKED_FOR_PROCESS_PLANNING
    )

    # Cutting data: requires process planning + tolerance_general + surface_finish
    cd_ok = (
        pp_ok
        and _field_ok("tolerance_general")
        and _field_ok("surface_finish")
    )
    states["CUTTING_DATA"] = (
        ReadinessState.READY_FOR_CUTTING_DATA
        if cd_ok
        else ReadinessState.BLOCKED_FOR_CUTTING_DATA
    )

    # CAM: requires process planning + topology (for 3D) or 2D-only flag
    is_3d = document_format in ("IGES", "STEP-GENERIC", "STEP-AP242", "STEP-AP214")
    cam_ok = pp_ok and (not is_3d or has_topology)
    states["CAM"] = (
        ReadinessState.READY_FOR_CAM
        if cam_ok
        else ReadinessState.BLOCKED_FOR_CAM
    )

    return states


# ---------------------------------------------------------------------------
# Main analysis function
# ---------------------------------------------------------------------------

def analyze_import_missing_data(
    import_result: Any,
    document_format: str | None = None,
    title_block_fields: dict[str, EngineeringField] | None = None,
) -> MissingDataAnalysis:
    """Analyze a CAD import result for missing engineering data.

    Args:
        import_result:       An ImportResult from the orchestrator.
        document_format:     Override for format detection (optional).
        title_block_fields:  Pre-extracted title-block fields (from
                             title_block_material.extract_title_block_fields).

    Returns:
        MissingDataAnalysis for the RAW_FILE phase.
    """
    from backend.interoperability.orchestrator import ImportResult, ImportStatus

    doc = import_result.document if isinstance(import_result, ImportResult) else None
    import_id = getattr(import_result, "import_id", "unknown")

    # Format detection
    fmt = document_format or (
        doc.format_descriptor.format_id if doc else "UNKNOWN"
    )
    file_name = doc.source.file_name if doc else None

    # Geometry status
    has_geometry = (
        doc is not None
        and doc.geometry is not None
        and import_result.status not in (
            ImportStatus.FAILED,
            ImportStatus.UNSUPPORTED,
        )
    )

    # Topology status
    has_topology = doc is not None and doc.topology is not None

    # --- Build field set ---
    fields: dict[str, EngineeringField] = {}

    # --- UNIT ---
    unit_field = _extract_unit_from_doc(doc, fmt)
    # Title-block may override
    if title_block_fields and "unit" in title_block_fields:
        unit_field = title_block_fields["unit"]
    fields["unit"] = unit_field

    # --- MATERIAL ---
    material_field = _extract_material_from_doc(doc)
    # Title-block may supply
    if title_block_fields and "material" in title_block_fields:
        tb_mat = title_block_fields["material"]
        if material_field.status is EngineeringFieldStatus.UNKNOWN:
            material_field = tb_mat
        elif tb_mat.value and tb_mat.value != material_field.value:
            material_field = EngineeringField(
                field_name="material",
                value=material_field.value,
                status=EngineeringFieldStatus.CONFLICT,
                source=material_field.source,
                confidence=material_field.confidence,
                confirmed_by_user=False,
                original_extracted_value=material_field.original_extracted_value,
            )
    fields["material"] = material_field

    # --- TOLERANCE_GENERAL ---
    tol_field = _extract_tolerance_from_doc(doc)
    if title_block_fields and "tolerance_general" in title_block_fields:
        tol_field = title_block_fields["tolerance_general"]
    fields["tolerance_general"] = tol_field

    # --- HOLE_DEPTH ---
    # 2D DXF files cannot carry hole depth — NOT_APPLICABLE for drawing-only files
    is_2d_drawing = fmt in ("DXF",)
    fields["hole_depth"] = (
        EngineeringField.not_applicable("hole_depth")
        if not is_2d_drawing
        else EngineeringField.unknown("hole_depth")
    )

    # --- SURFACE_FINISH ---
    sf_field = _extract_surface_finish_from_doc(doc)
    fields["surface_finish"] = sf_field

    # --- TOPOLOGY ---
    if fmt in ("IGES", "STEP-GENERIC", "STEP-AP242", "STEP-AP214"):
        if has_topology:
            fields["topology"] = EngineeringField.known(
                "topology",
                "present",
                EngineeringFieldSource.CAD_GEOMETRY,
                confidence=1.0,
            )
        else:
            fields["topology"] = EngineeringField.unknown("topology")
    else:
        fields["topology"] = EngineeringField.not_applicable("topology")

    # --- Compute readiness ---
    readiness_states = _compute_readiness(fields, fmt, has_geometry, has_topology)

    # --- Classify fields ---
    known_names: list[str] = []
    unknown_names: list[str] = []
    required_missing: list[str] = []
    optional_missing: list[str] = []

    for fname, fobj in fields.items():
        defn = FIELD_DEFINITIONS.get(fname)
        if fobj.status in (
            EngineeringFieldStatus.KNOWN,
            EngineeringFieldStatus.USER_CONFIRMED,
            EngineeringFieldStatus.NOT_APPLICABLE,
        ):
            known_names.append(fname)
        else:
            unknown_names.append(fname)
            if defn and defn.tier not in (
                FieldRequirementTier.OPTIONAL,
                FieldRequirementTier.REQUIRED_FOR_CAM,
            ):
                required_missing.append(fname)
            else:
                optional_missing.append(fname)

    # Blocking stages
    blocking_stages = [
        stage
        for stage, state in readiness_states.items()
        if "BLOCKED" in state.value
    ]

    # Can user resolve?
    can_resolve = any(
        fname in ("unit", "material", "tolerance_general", "surface_finish")
        for fname in required_missing
    )

    # Geometry note
    if has_geometry:
        feat_count = 0
        if doc and doc.features:
            features_obj = doc.features
            if hasattr(features_obj, "features"):
                feat_count = len(features_obj.features)
        geometry_note = f"Geometry extracted ({fmt}). Features: {feat_count}"
    else:
        geometry_note = "Geometry not available (import failed or unsupported format)"

    return MissingDataAnalysis(
        import_id=import_id,
        document_format=fmt,
        source_file_name=file_name,
        fields=fields,
        readiness_states=readiness_states,
        known_field_names=known_names,
        unknown_field_names=unknown_names,
        required_missing_field_names=required_missing,
        optional_missing_field_names=optional_missing,
        geometry_ok=has_geometry,
        geometry_note=geometry_note,
        blocking_stage_names=blocking_stages,
        can_proceed_with_user_input=can_resolve,
        phase="RAW_FILE",
        analyzed_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Apply user confirmations
# ---------------------------------------------------------------------------

def apply_user_confirmations(
    analysis: MissingDataAnalysis,
    confirmations: dict[str, Any],
) -> MissingDataAnalysis:
    """Apply a dict of user-supplied field values to an existing analysis.

    Args:
        analysis:      The RAW_FILE analysis to build on.
        confirmations: Mapping of field_name → value (string) or dict with
                       {"value": str, "library_id": str | None}.

    Returns:
        A new MissingDataAnalysis with phase="AFTER_USER_CONFIRMATION".

    Design invariants:
    - Original extracted values are preserved.
    - Blank / whitespace values are rejected — they remain UNKNOWN.
    - Each confirmed field is tagged source=USER_CONFIRMED, confirmed_by_user=True.
    - Conflict detection: if file value != user value → status=CONFLICT.
    """
    new_fields = dict(analysis.fields)

    for fname, raw_input in confirmations.items():
        if fname not in new_fields:
            continue

        # Normalize input
        if isinstance(raw_input, dict):
            user_value = str(raw_input.get("value", "") or "").strip()
            library_id = raw_input.get("library_id")
            library_desig = raw_input.get("library_designation")
        else:
            user_value = str(raw_input or "").strip()
            library_id = None
            library_desig = None

        # Reject empty / blank input — remains UNKNOWN
        if not user_value:
            continue

        new_fields[fname] = new_fields[fname].apply_user_confirmation(
            user_value,
            library_id=library_id,
            library_designation=library_desig,
        )

    # Recompute readiness with updated fields
    has_topology = new_fields.get("topology", EngineeringField.unknown("topology")).is_resolved
    new_readiness = _compute_readiness(
        new_fields,
        analysis.document_format,
        analysis.geometry_ok,
        has_topology,
    )

    # Reclassify
    known_names: list[str] = []
    unknown_names: list[str] = []
    required_missing: list[str] = []
    optional_missing: list[str] = []

    for fname, fobj in new_fields.items():
        defn = FIELD_DEFINITIONS.get(fname)
        if fobj.status in (
            EngineeringFieldStatus.KNOWN,
            EngineeringFieldStatus.USER_CONFIRMED,
            EngineeringFieldStatus.NOT_APPLICABLE,
        ):
            known_names.append(fname)
        else:
            unknown_names.append(fname)
            if defn and defn.tier not in (
                FieldRequirementTier.OPTIONAL,
                FieldRequirementTier.REQUIRED_FOR_CAM,
            ):
                required_missing.append(fname)
            else:
                optional_missing.append(fname)

    blocking_stages = [
        stage
        for stage, state in new_readiness.items()
        if "BLOCKED" in state.value
    ]
    can_resolve = any(
        fname in ("unit", "material", "tolerance_general", "surface_finish")
        for fname in required_missing
    )

    return MissingDataAnalysis(
        import_id=analysis.import_id,
        document_format=analysis.document_format,
        source_file_name=analysis.source_file_name,
        fields=new_fields,
        readiness_states=new_readiness,
        known_field_names=known_names,
        unknown_field_names=unknown_names,
        required_missing_field_names=required_missing,
        optional_missing_field_names=optional_missing,
        geometry_ok=analysis.geometry_ok,
        geometry_note=analysis.geometry_note,
        blocking_stage_names=blocking_stages,
        can_proceed_with_user_input=can_resolve,
        phase="AFTER_USER_CONFIRMATION",
        analyzed_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Private extraction helpers
# ---------------------------------------------------------------------------

def _extract_unit_from_doc(
    doc: Any,
    fmt: str,
) -> EngineeringField:
    """Extract unit from a CanonicalDocument's entity_refs (DxfHeader)."""
    if doc is None:
        return EngineeringField.unknown("unit")

    # Scan entity_refs for DxfHeader
    for ref in (doc.entity_refs or ()):
        kind = getattr(ref, "entity_kind", "") or ""
        metadata = getattr(ref, "metadata", {}) or {}
        if kind == "DxfHeader":
            raw_units = metadata.get("units") or metadata.get("drawing_units")
            if raw_units:
                return EngineeringField.known(
                    "unit",
                    str(raw_units),
                    EngineeringFieldSource.FILE_METADATA,
                    confidence=0.95,
                )

    # IGES files declare units in header
    if fmt in ("IGES",):
        for ref in (doc.entity_refs or ()):
            kind = getattr(ref, "entity_kind", "") or ""
            metadata = getattr(ref, "metadata", {}) or {}
            if "unit" in str(kind).lower() or "header" in str(kind).lower():
                raw_units = metadata.get("unit") or metadata.get("units")
                if raw_units:
                    return EngineeringField.known(
                        "unit",
                        str(raw_units),
                        EngineeringFieldSource.FILE_METADATA,
                        confidence=0.90,
                    )

    return EngineeringField.unknown("unit")


def _extract_material_from_doc(doc: Any) -> EngineeringField:
    """Check document process_intelligence for any material evidence.

    Material is NEVER auto-inferred from part number, drawing number, or
    any non-explicit source. Only explicit material designations from the
    file are reported here.
    """
    if doc is None:
        return EngineeringField.unknown("material")

    pi = doc.process_intelligence
    if pi is None:
        return EngineeringField.unknown("material")

    # Check if process_intelligence carries a resolved material
    missing_inputs = getattr(pi, "missing_inputs", None)
    if missing_inputs and any(
        "material" in str(m).lower() for m in missing_inputs
    ):
        return EngineeringField.unknown("material")

    # If the PI has an explicit material designation
    material_id = getattr(pi, "material_id", None)
    if material_id and str(material_id).strip():
        return EngineeringField.known(
            "material",
            str(material_id),
            EngineeringFieldSource.CAD_GEOMETRY,
            confidence=0.80,
        )

    return EngineeringField.unknown("material")


def _extract_tolerance_from_doc(doc: Any) -> EngineeringField:
    """Check for general tolerance from MTEXT or notes in entity_refs."""
    if doc is None:
        return EngineeringField.unknown("tolerance_general")

    for ref in (doc.entity_refs or ()):
        metadata = getattr(ref, "metadata", {}) or {}
        tol = metadata.get("general_tolerance") or metadata.get("tolerance_standard")
        if tol:
            return EngineeringField.known(
                "tolerance_general",
                str(tol),
                EngineeringFieldSource.DRAWING_TEXT,
                confidence=0.85,
            )

    return EngineeringField.unknown("tolerance_general")


def _extract_surface_finish_from_doc(doc: Any) -> EngineeringField:
    """Check for surface finish specification in entity_refs."""
    if doc is None:
        return EngineeringField.unknown("surface_finish")

    for ref in (doc.entity_refs or ()):
        metadata = getattr(ref, "metadata", {}) or {}
        sf = metadata.get("surface_finish") or metadata.get("ra_value") or metadata.get("rz_value")
        if sf:
            return EngineeringField.known(
                "surface_finish",
                str(sf),
                EngineeringFieldSource.DRAWING_TEXT,
                confidence=0.80,
            )

    return EngineeringField.unknown("surface_finish")
