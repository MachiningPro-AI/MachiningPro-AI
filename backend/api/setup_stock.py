"""Setup & Stock Definition API (P3-B / P4-B).

Endpoints:
  POST /api/setup-stock/                            — create session
  GET  /api/setup-stock/{session_id}                — retrieve session
  PUT  /api/setup-stock/{session_id}                — update stock or setup (or both)
  GET  /api/setup-stock/{session_id}/cam-status     — CAM prerequisite gate (P4-B)

Design invariants:
  - All dimension values come from the engineer — never inferred or defaulted.
  - material_grade must be non-empty when supplied.
  - No CNC dispatch, no auto-approval, no automatic adaptation.
  - provenance=USER_CONFIRMED on all stored values.

FABRICATED_STOCK_GEOMETRY=NO
AUTO_CONFIRM=NO
CNC_DISPATCH=NO
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from backend.manufacturing.cam_gate import check_cam_prerequisites_for_features
from backend.manufacturing.setup_stock import (
    SetupDefinition,
    SetupStockSession,
    StockDefinition,
    StockShape,
    create_setup_stock_session,
    validate_stock_dimensions,
)

router = APIRouter(prefix="/api/setup-stock", tags=["setup-stock"])

_SESSIONS: dict[str, SetupStockSession] = {}


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class StockRequest(BaseModel):
    shape: str
    material_grade: str = Field(..., min_length=1, max_length=64)
    length_mm: float | None = None
    width_mm: float | None = None
    height_mm: float | None = None
    outer_diameter_mm: float | None = None
    inner_diameter_mm: float | None = None
    stock_notes: str | None = Field(default=None, max_length=500)
    confirmed_by: str = Field(default="engineer")

    @field_validator("shape")
    @classmethod
    def _valid_shape(cls, v: str) -> str:
        try:
            StockShape(v)
        except ValueError as exc:
            raise ValueError(f"Unknown StockShape: {v!r}") from exc
        return v

    @field_validator("length_mm", "width_mm", "height_mm", "outer_diameter_mm", "inner_diameter_mm")
    @classmethod
    def _positive_dim(cls, v: float | None) -> float | None:
        if v is not None and v <= 0:
            raise ValueError("Dimension must be positive")
        return v


class SetupRequest(BaseModel):
    n_setups: int = Field(default=1, ge=1)
    datum_a: str | None = Field(default=None, max_length=256)
    datum_b: str | None = Field(default=None, max_length=256)
    datum_c: str | None = Field(default=None, max_length=256)
    orientation: str | None = Field(default=None, max_length=256)
    fixture_note: str | None = Field(default=None, max_length=500)
    confirmed_by: str = Field(default="engineer")


class CreateSessionRequest(BaseModel):
    cad_session_id: str | None = None
    stock: StockRequest | None = None
    setup: SetupRequest | None = None


class UpdateSessionRequest(BaseModel):
    stock: StockRequest | None = None
    setup: SetupRequest | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_session(session_id: str) -> SetupStockSession:
    sess = _SESSIONS.get(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="SetupStockSession not found")
    return sess


def _build_stock(req: StockRequest) -> StockDefinition:
    return StockDefinition(
        stock_id=str(uuid.uuid4()),
        shape=StockShape(req.shape),
        material_grade=req.material_grade,
        length_mm=req.length_mm,
        width_mm=req.width_mm,
        height_mm=req.height_mm,
        outer_diameter_mm=req.outer_diameter_mm,
        inner_diameter_mm=req.inner_diameter_mm,
        stock_notes=req.stock_notes,
        confirmed_by=req.confirmed_by,
    )


def _build_setup(req: SetupRequest) -> SetupDefinition:
    return SetupDefinition(
        setup_id=str(uuid.uuid4()),
        n_setups=req.n_setups,
        datum_a=req.datum_a,
        datum_b=req.datum_b,
        datum_c=req.datum_c,
        orientation=req.orientation,
        fixture_note=req.fixture_note,
        confirmed_by=req.confirmed_by,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/", summary="Create a setup/stock session")
async def create_session(req: CreateSessionRequest) -> dict:
    """Create a new SetupStockSession, optionally with initial stock and setup."""
    sess = create_setup_stock_session(req.cad_session_id)
    if req.stock:
        stock = _build_stock(req.stock)
        errors = validate_stock_dimensions(stock)
        if errors:
            raise HTTPException(
                status_code=422,
                detail={"stock_validation_errors": errors},
            )
        sess.stock = stock
    if req.setup:
        setup = _build_setup(req.setup)
        setup_errors = setup.validate()
        if setup_errors:
            raise HTTPException(
                status_code=422,
                detail={"setup_validation_errors": setup_errors},
            )
        sess.setup = setup

    _SESSIONS[sess.session_id] = sess
    return {
        "session_id": sess.session_id,
        "status": "CREATED",
        **sess.as_dict(),
        "disclaimer": "USER_CONFIRMED: all setup/stock values supplied by engineer",
    }


@router.get("/{session_id}", summary="Retrieve a setup/stock session")
async def get_session(session_id: str) -> dict:
    sess = _get_session(session_id)
    return sess.as_dict()


@router.put("/{session_id}", summary="Update stock or setup in a session")
async def update_session(session_id: str, req: UpdateSessionRequest) -> dict:
    """Update stock and/or setup in an existing session.

    Supplying stock replaces the existing stock definition.
    Supplying setup replaces the existing setup definition.
    Omitting a field leaves it unchanged.
    """
    sess = _get_session(session_id)

    if req.stock is not None:
        stock = _build_stock(req.stock)
        errors = validate_stock_dimensions(stock)
        if errors:
            raise HTTPException(
                status_code=422,
                detail={"stock_validation_errors": errors},
            )
        sess.stock = stock

    if req.setup is not None:
        setup = _build_setup(req.setup)
        setup_errors = setup.validate()
        if setup_errors:
            raise HTTPException(
                status_code=422,
                detail={"setup_validation_errors": setup_errors},
            )
        sess.setup = setup

    sess.updated_at = datetime.now(UTC)
    return {
        "session_id": sess.session_id,
        "status": "UPDATED",
        **sess.as_dict(),
        "disclaimer": "USER_CONFIRMED: all setup/stock values supplied by engineer",
    }


@router.get(
    "/{session_id}/cam-status",
    summary="CAM prerequisite gate — check readiness for offline CAM preparation (P4-B)",
)
async def get_cam_status(
    session_id: str,
    cad_session_id: str | None = Query(
        default=None,
        description="CAD feature session ID to retrieve confirmed features for gate check",
    ),
) -> dict:
    """Return per-requirement CAM readiness for all confirmed features in a session.

    CAM_READY=YES means offline CAM preparation may proceed.
    It does NOT mean: auto-dispatch, machine-start, or auto-approval.

    OFFLINE_ONLY=YES
    AUTO_APPROVE=NO
    CNC_DISPATCH=NO
    """
    sess = _get_session(session_id)

    confirmed_features = []
    if cad_session_id:
        from backend.api.cad_features import _SESSIONS as _CAD_SESSIONS
        cad_sess = _CAD_SESSIONS.get(cad_session_id)
        if cad_sess is None:
            raise HTTPException(status_code=404, detail=f"CAD session {cad_session_id!r} not found")
        confirmed_features = [
            f for f in cad_sess.recognition_result.features
            if f.feature_id in cad_sess.confirmed_feature_ids
        ]

    if not confirmed_features:
        return {
            "session_id": session_id,
            "cad_session_id": cad_session_id,
            "cam_ready_count": 0,
            "total_confirmed_features": 0,
            "feature_states": [],
            "overall_cam_ready": False,
            "first_blocker": "no_confirmed_features",
            "offline_only": True,
            "disclaimer": (
                "No confirmed features found. "
                "Engineer must confirm features via POST /confirm-with-dimension "
                "before CAM prerequisite gate can be evaluated."
            ),
        }

    states = check_cam_prerequisites_for_features(confirmed_features, sess)
    cam_ready_count = sum(1 for s in states.values() if s.cam_ready)
    first_blocker: str | None = None
    for s in states.values():
        if not s.cam_ready and s.first_blocker:
            first_blocker = s.first_blocker
            break

    return {
        "session_id": session_id,
        "cad_session_id": cad_session_id,
        "cam_ready_count": cam_ready_count,
        "total_confirmed_features": len(confirmed_features),
        "feature_states": [s.as_dict() for s in states.values()],
        "overall_cam_ready": cam_ready_count == len(confirmed_features),
        "first_blocker": first_blocker,
        "offline_only": True,
        "disclaimer": (
            "CAM_READY=YES authorises OFFLINE preparation only. "
            "AUTO_APPROVED=NO. CNC_DISPATCH=NO. "
            "Engineer sign-off required before production use."
        ),
    }
