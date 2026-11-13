"""Missing Engineering Data Resolution API (P0).

Provides endpoints for:
  - Analyzing a CAD import result for missing engineering metadata.
  - Accepting user confirmation of missing values.
  - Retrieving per-stage readiness states.

Endpoints:
  POST /api/missing-data/analyze
  POST /api/missing-data/confirm

Design invariants:
  - User-confirmed values are tagged USER_CONFIRMED — never FILE_EVIDENCE.
  - Original extraction results are never overwritten.
  - No downstream stage proceeds using unconfirmed defaults.
  - No CNC dispatch, no auto-approval, no automatic adaptation.

FABRICATED_DEFAULT_MATERIAL=NO
FABRICATED_DEFAULT_UNIT=NO
AUTO_CONFIRM=NO
CNC_DISPATCH=NO
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.api.auth import verify_token

router = APIRouter(prefix="/api/missing-data", tags=["missing-data"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    """Request body for /analyze.

    The import_id references a previous import run. The optional
    mtext_tokens list is used for title-block material extraction
    when available from the caller.
    """

    import_id: str
    document_format: str | None = None
    source_file_name: str | None = None
    mtext_tokens: list[str] = Field(default_factory=list)
    has_geometry: bool = False
    has_topology: bool = False
    unit_from_file: str | None = None
    material_from_file: str | None = None
    general_tolerance_from_file: str | None = None
    missing_inputs: list[str] = Field(default_factory=list)
    feature_count: int = 0


class FieldConfirmation(BaseModel):
    """Single field confirmation from the user."""

    value: str
    library_id: str | None = None
    library_designation: str | None = None


class ConfirmRequest(BaseModel):
    """Request body for /confirm.

    Provides user-supplied values for one or more missing fields.
    Blank strings are rejected — they remain UNKNOWN.

    WARNING: Values provided here will be tagged as USER_CONFIRMED.
    They will NOT be reported as file-extracted data.
    """

    import_id: str
    confirmations: dict[str, FieldConfirmation]
    raw_analysis: dict[str, Any] | None = None


class AnalyzeResponse(BaseModel):
    """Response from /analyze."""

    import_id: str
    document_format: str
    source_file_name: str | None
    phase: str
    geometry_ok: bool
    geometry_note: str
    known_fields: list[str]
    unknown_fields: list[str]
    required_missing_fields: list[str]
    optional_missing_fields: list[str]
    blocking_stages: list[str]
    can_proceed_with_user_input: bool
    readiness_states: dict[str, str]
    fields: dict[str, dict[str, Any]]
    ui_warning: str


class ConfirmResponse(BaseModel):
    """Response from /confirm."""

    import_id: str
    phase: str
    geometry_ok: bool
    known_fields: list[str]
    unknown_fields: list[str]
    required_missing_fields: list[str]
    blocking_stages: list[str]
    readiness_states: dict[str, str]
    fields: dict[str, dict[str, Any]]
    confirmed_field_names: list[str]
    conflict_field_names: list[str]
    ui_warning: str


_UI_WARNING = (
    "Values provided by the user are tagged USER_CONFIRMED and are never "
    "reported as file-extracted engineering data."
)

_UI_WARNING_TR = (
    "Kullanıcı tarafından girilen değerler USER_CONFIRMED olarak etiketlenir "
    "ve asla dosyadan çıkarılan mühendislik verisi olarak raporlanmaz."
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_missing_data(
    req: AnalyzeRequest,
    _: dict = Depends(verify_token),  # noqa: B008
) -> AnalyzeResponse:
    """Analyze missing engineering data for a CAD import result.

    Accepts structured information from the import pipeline and returns
    a complete missing-data analysis with per-stage readiness states.

    Does NOT require an active import result object — the caller supplies
    the structured metadata extracted from the import pipeline.

    Returns the RAW_FILE analysis phase.
    """

    from backend.interoperability.missing_data import (
        FIELD_DEFINITIONS,
        EngineeringField,
        EngineeringFieldSource,
        EngineeringFieldStatus,
        FieldRequirementTier,
        _compute_readiness,
    )

    # Build fields from structured request
    fields: dict[str, EngineeringField] = {}

    # --- UNIT ---
    if req.unit_from_file:
        fields["unit"] = EngineeringField.known(
            "unit",
            req.unit_from_file,
            EngineeringFieldSource.FILE_METADATA,
            confidence=0.95,
        )
    else:
        fields["unit"] = EngineeringField.unknown("unit")

    # --- MATERIAL ---
    if req.material_from_file:
        fields["material"] = EngineeringField.known(
            "material",
            req.material_from_file,
            EngineeringFieldSource.FILE_METADATA,
            confidence=0.80,
        )
    else:
        # Try title-block extraction
        from backend.interoperability.title_block_material import extract_title_block_material
        tb_material = None
        if req.mtext_tokens:
            tb_material = extract_title_block_material(req.mtext_tokens)
        fields["material"] = tb_material if tb_material else EngineeringField.unknown("material")

    # --- TOLERANCE_GENERAL ---
    if req.general_tolerance_from_file:
        fields["tolerance_general"] = EngineeringField.known(
            "tolerance_general",
            req.general_tolerance_from_file,
            EngineeringFieldSource.DRAWING_TEXT,
            confidence=0.85,
        )
    else:
        fields["tolerance_general"] = EngineeringField.unknown("tolerance_general")

    # --- HOLE_DEPTH ---
    is_2d = req.document_format in ("DXF",) if req.document_format else False
    fields["hole_depth"] = (
        EngineeringField.unknown("hole_depth")
        if is_2d
        else EngineeringField.not_applicable("hole_depth")
    )

    # --- SURFACE_FINISH ---
    fields["surface_finish"] = EngineeringField.unknown("surface_finish")

    # --- TOPOLOGY ---
    fmt = req.document_format or "UNKNOWN"
    is_3d = fmt in ("IGES", "STEP-GENERIC", "STEP-AP242", "STEP-AP214")
    if is_3d:
        if req.has_topology:
            fields["topology"] = EngineeringField.known(
                "topology", "present", EngineeringFieldSource.CAD_GEOMETRY, confidence=1.0
            )
        else:
            fields["topology"] = EngineeringField.unknown("topology")
    else:
        fields["topology"] = EngineeringField.not_applicable("topology")

    # Compute readiness
    readiness_states = _compute_readiness(
        fields, fmt, req.has_geometry, req.has_topology
    )

    # Classify
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

    blocking_stages = [
        stage for stage, state in readiness_states.items() if "BLOCKED" in state.value
    ]
    can_resolve = any(
        fname in ("unit", "material", "tolerance_general", "surface_finish")
        for fname in required_missing
    )

    geometry_note = (
        f"Geometry extracted ({fmt}). Features: {req.feature_count}"
        if req.has_geometry
        else "Geometry not available"
    )

    return AnalyzeResponse(
        import_id=req.import_id,
        document_format=fmt,
        source_file_name=req.source_file_name,
        phase="RAW_FILE",
        geometry_ok=req.has_geometry,
        geometry_note=geometry_note,
        known_fields=known_names,
        unknown_fields=unknown_names,
        required_missing_fields=required_missing,
        optional_missing_fields=optional_missing,
        blocking_stages=blocking_stages,
        can_proceed_with_user_input=can_resolve,
        readiness_states={k: v.value for k, v in readiness_states.items()},
        fields={k: v.as_dict() for k, v in fields.items()},
        ui_warning=_UI_WARNING,
    )


@router.post("/confirm", response_model=ConfirmResponse)
async def confirm_missing_data(
    req: ConfirmRequest,
    _: dict = Depends(verify_token),  # noqa: B008
) -> ConfirmResponse:
    """Accept user-confirmed values for missing engineering fields.

    Accepts user-supplied values for one or more missing fields.
    Returns the AFTER_USER_CONFIRMATION analysis phase.

    HARD RULE: User-confirmed values are tagged USER_CONFIRMED.
    They are NEVER reported as file-extracted data.

    Blank strings are rejected — the field remains UNKNOWN.
    """
    from backend.interoperability.missing_data import (
        FIELD_DEFINITIONS,
        EngineeringField,
        EngineeringFieldSource,
        EngineeringFieldStatus,
        FieldRequirementTier,
        _compute_readiness,
    )

    # Reconstruct fields from raw_analysis if provided
    raw_fields: dict[str, EngineeringField] = {}
    if req.raw_analysis and "fields" in req.raw_analysis:
        for fname, fdata in req.raw_analysis["fields"].items():
            status_str = fdata.get("status", "UNKNOWN")
            try:
                status = EngineeringFieldStatus(status_str)
            except ValueError:
                status = EngineeringFieldStatus.UNKNOWN

            source_str = fdata.get("source")
            source = None
            if source_str:
                try:
                    source = EngineeringFieldSource(source_str)
                except ValueError:
                    source = None

            raw_fields[fname] = EngineeringField(
                field_name=fname,
                value=fdata.get("value"),
                status=status,
                source=source,
                confidence=fdata.get("confidence"),
                confirmed_by_user=fdata.get("confirmed_by_user", False),
                original_extracted_value=fdata.get("original_extracted_value"),
            )
    else:
        # No previous analysis — start with all unknown
        for fname in FIELD_DEFINITIONS:
            raw_fields[fname] = EngineeringField.unknown(fname)

    # Apply confirmations
    confirmations_dict = {
        fname: {
            "value": fc.value,
            "library_id": fc.library_id,
            "library_designation": fc.library_designation,
        }
        for fname, fc in req.confirmations.items()
    }
    new_fields = dict(raw_fields)
    confirmed_names: list[str] = []
    conflict_names: list[str] = []

    for fname, conf_data in confirmations_dict.items():
        if fname not in new_fields:
            continue
        user_value = str(conf_data.get("value", "") or "").strip()
        if not user_value:
            continue

        updated = new_fields[fname].apply_user_confirmation(
            user_value,
            library_id=conf_data.get("library_id"),
            library_designation=conf_data.get("library_designation"),
        )
        new_fields[fname] = updated

        if updated.status == EngineeringFieldStatus.CONFLICT:
            conflict_names.append(fname)
        else:
            confirmed_names.append(fname)

    # Determine format and topology from fields
    # (use topology field's status to infer)
    has_topology = new_fields.get("topology", EngineeringField.unknown("topology")).is_resolved
    # Reconstruct geometry_ok from raw_analysis
    has_geometry = True
    fmt = "UNKNOWN"
    if req.raw_analysis:
        has_geometry = req.raw_analysis.get("geometry_ok", True)
        fmt = req.raw_analysis.get("document_format", "UNKNOWN")

    readiness_states = _compute_readiness(new_fields, fmt, has_geometry, has_topology)

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
        stage for stage, state in readiness_states.items() if "BLOCKED" in state.value
    ]

    return ConfirmResponse(
        import_id=req.import_id,
        phase="AFTER_USER_CONFIRMATION",
        geometry_ok=has_geometry,
        known_fields=known_names,
        unknown_fields=unknown_names,
        required_missing_fields=required_missing,
        blocking_stages=blocking_stages,
        readiness_states={k: v.value for k, v in readiness_states.items()},
        fields={k: v.as_dict() for k, v in new_fields.items()},
        confirmed_field_names=confirmed_names,
        conflict_field_names=conflict_names,
        ui_warning=_UI_WARNING,
    )
