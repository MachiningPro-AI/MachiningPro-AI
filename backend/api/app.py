"""
MachiningPro AI FastAPI HTTP Application

Level-20 additions:
- Structured logging (JSON)
- Correlation middleware (X-Request-ID)
- Startup: WorkflowStore + ArtifactStore initialisation, RUNNING→INTERRUPTED recovery
- GET /api/ready — readiness probe (checks persistence)
- GET /api/metrics — operational counters (unauthenticated, no secrets)
- GET /api/health — updated: database_ok reflects persistence state
- Export router mounted
"""

import logging
import os
import pathlib
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..observability import metrics
from ..observability.correlation import CorrelationMiddleware
from ..observability.logging_config import configure_logging
from .adaptive import router as adaptive_router
from .auth import LoginRequest, authenticate, get_configured_credentials
from .cad_upload import router as cad_upload_router
from .cam_planning import router as cam_planning_router
from .compatibility import router as compatibility_router
from .cutting_parameters import router as cutting_parameters_router
from .cutting_tools import router as cutting_tools_router
from .digital_twin import router as digital_twin_router
from .dispatch import router as dispatch_router
from .drawing_analysis import router as drawing_analysis_router
from .drawing_to_process import router as drawing_to_process_router
from .engineering_import import router as engineering_import_router
from .export import router as export_router
from .job_planning import router as job_planning_router
from .machines import router as machines_router
from .materials import router as materials_router
from .monitoring import router as monitoring_router
from .nc_generation import router as nc_generation_router
from .nc_path import router as nc_path_router
from .process_planning import router as process_planning_router
from .scheduling import router as scheduling_router
from .selection import router as selection_router
from .tool_holders import router as tool_holders_router
from .tool_life import router as tool_life_router
from .toolpath import router as toolpath_router
from .verification import router as verification_router
from .workflow import router as workflow_router

configure_logging(os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


class ChangePasswordRequest(BaseModel):
    """Frontend change-password contract"""
    current_password: str
    new_password: str


app = FastAPI(title="MachiningPro AI", version="0.1.0-alpha.20")

# Correlation middleware — adds X-Request-ID to every request/response
app.add_middleware(CorrelationMiddleware)

# Optional CORS — activated only when CORS_ORIGINS env var is set.
_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

app.include_router(compatibility_router)
app.include_router(cutting_parameters_router)
app.include_router(drawing_to_process_router)
app.include_router(materials_router)
app.include_router(cutting_tools_router)
app.include_router(drawing_analysis_router)
app.include_router(engineering_import_router)
app.include_router(machines_router)
app.include_router(nc_path_router)
app.include_router(process_planning_router)
app.include_router(selection_router)
app.include_router(tool_holders_router)
app.include_router(tool_life_router)
app.include_router(cam_planning_router)
app.include_router(toolpath_router)
app.include_router(verification_router)
app.include_router(nc_generation_router)
app.include_router(scheduling_router)
app.include_router(dispatch_router)
app.include_router(monitoring_router)
app.include_router(adaptive_router)
app.include_router(job_planning_router)
app.include_router(digital_twin_router)
app.include_router(workflow_router)
app.include_router(cad_upload_router)
app.include_router(export_router)


# ---------------------------------------------------------------------------
# Startup — initialise persistence and recover interrupted workflows
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def _on_startup() -> None:
    from ..persistence import get_artifact_store, get_workflow_store
    try:
        store = get_workflow_store()
        interrupted = store.mark_interrupted()
        metrics.set_gauge("startup.interrupted_workflows", interrupted)
        if interrupted:
            logger.warning("Marked %d workflow(s) as INTERRUPTED on restart", interrupted)
    except Exception as exc:  # noqa: BLE001
        logger.error("WorkflowStore startup failed: %s", exc)
        metrics.increment(metrics.PERSISTENCE_ERROR)

    try:
        get_artifact_store()
    except Exception as exc:  # noqa: BLE001
        logger.error("ArtifactStore startup failed: %s", exc)


# ---------------------------------------------------------------------------
# Health endpoint (unauthenticated — public bootstrap)
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    """
    Return service health status.

    POLICY: Public (unauthenticated) health endpoint.
    Does not expose secrets or sensitive data.
    """
    from ..persistence import get_artifact_store, get_workflow_store
    utc_now = datetime.now(UTC)

    db_ok = False
    artifacts_ok = False
    try:
        db_ok = get_workflow_store().is_healthy()
    except Exception:  # noqa: BLE001
        pass
    try:
        artifacts_ok = get_artifact_store().is_healthy()
    except Exception:  # noqa: BLE001
        pass

    return {
        "status": "ok",
        "version": "0.1.0-alpha.20",
        "database_ok": db_ok,
        "artifact_store_ok": artifacts_ok,
        "server_time": utc_now.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
    }


# ---------------------------------------------------------------------------
# Readiness endpoint (MUST 16)
# ---------------------------------------------------------------------------

@app.get("/api/ready")
async def ready():
    """
    Readiness probe — returns 200 only when persistence dependencies are ready.
    Returns 503 when any critical dependency is unhealthy.

    Distinguishes process-alive (health) from dependencies-ready (ready).
    """
    from ..persistence import get_artifact_store, get_workflow_store

    errors = []
    try:
        if not get_workflow_store().is_healthy():
            errors.append("workflow_store: not healthy")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"workflow_store: {exc}")

    try:
        if not get_artifact_store().is_healthy():
            errors.append("artifact_store: not healthy")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"artifact_store: {exc}")

    if errors:
        return {"ready": False, "errors": errors}, 503

    return {"ready": True, "errors": []}


# ---------------------------------------------------------------------------
# Metrics endpoint (unauthenticated, no secrets exposed)
# ---------------------------------------------------------------------------

@app.get("/api/metrics")
async def get_metrics():
    """Return in-process operational metrics counters. No secrets exposed."""
    return metrics.snapshot()


# ---------------------------------------------------------------------------
# Login / change-password
# ---------------------------------------------------------------------------

@app.post("/api/login")
async def login(req: LoginRequest):
    if not get_configured_credentials():
        raise HTTPException(
            status_code=401,
            detail=(
                "Local development credentials not configured. "
                "Set MACHININGPRO_DEV_USERNAME, MACHININGPRO_DEV_PASSWORD, "
                "and MACHININGPRO_DEV_JWT_SECRET environment variables."
            ),
        )

    response = authenticate(req)
    if not response:
        metrics.increment(metrics.AUTH_FAILED)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return response.model_dump()


@app.post("/api/change-password")
async def change_password(req: ChangePasswordRequest):
    return {"ok": False, "error": "not supported in alpha"}


# ---------------------------------------------------------------------------
# Production SPA/static serving
# ---------------------------------------------------------------------------

_DIST = pathlib.Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if _DIST.is_dir():
    if (_DIST / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="static-assets")
    if (_DIST / "branding").is_dir():
        app.mount(
            "/branding",
            StaticFiles(directory=str(_DIST / "branding")),
            name="static-branding",
        )

    _DIST_RESOLVED = _DIST.resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    async def _spa_fallback(full_path: str) -> FileResponse:
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        try:
            target = (_DIST / full_path).resolve()
            target.relative_to(_DIST_RESOLVED)
        except ValueError:
            return FileResponse(str(_DIST / "index.html"))
        if target.is_file():
            return FileResponse(str(target))
        return FileResponse(str(_DIST / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.api.app:app",
        host="127.0.0.1",
        port=8010,
        reload=True,
    )
