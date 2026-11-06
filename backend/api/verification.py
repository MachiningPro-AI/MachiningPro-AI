"""
Level-11 Toolpath Verification and Simulation API.

Endpoints expose the verification engine from backend/verification/.
No G-code. No NC code. No fabricated results.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, status

from backend.api.auth import verify_token
from ..verification.models import SimulationRequest, SimulationResult
from ..verification.simulation import run_simulation
from ..verification.tolerance import DEFAULT_TOLERANCE

router = APIRouter(prefix="/api/verification", tags=["verification"])


def _require_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
        )
    token = authorization.removeprefix("Bearer ")
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return payload


@router.post("/simulate", response_model=SimulationResult)
def simulate(
    request: SimulationRequest,
    authorization: str | None = Header(default=None),
) -> SimulationResult:
    """
    Run all 12 verification check types against the given toolpath segments.

    Profile determines which checks are mandatory for VERIFIED state.
    Missing geometry → NOT_PERFORMED / INSUFFICIENT_DATA (never PASS).
    COMPLETED simulation != VERIFIED toolpath.
    """
    _require_user(authorization)
    return run_simulation(request, DEFAULT_TOLERANCE)


@router.post("/simulate/geometry-only", response_model=SimulationResult)
def simulate_geometry_only(
    request: SimulationRequest,
    authorization: str | None = Header(default=None),
) -> SimulationResult:
    """Convenience endpoint forcing GEOMETRY_ONLY profile."""
    from ..verification.enums import VerificationProfileEnum

    _require_user(authorization)
    request = request.model_copy(update={"profile": VerificationProfileEnum.GEOMETRY_ONLY})
    return run_simulation(request, DEFAULT_TOLERANCE)
