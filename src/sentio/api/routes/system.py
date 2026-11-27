"""System API routes."""

import logging

from fastapi import APIRouter
from fastapi.responses import FileResponse

from sentio.api.dependencies import PREFIX, STATIC_DIR, agent
from sentio.maintenance.health_check import system_health_check
from sentio.maintenance.readiness import readiness

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(PREFIX + "/ready", tags=["System"])
def ready():
    """Capability readiness, independent of optional camera or generation."""
    return readiness(agent)


@router.get("/", include_in_schema=False)
def root():
    """Serve the frontend UI at http://localhost:8000"""
    index = STATIC_DIR / "index.html"
    if not index.exists():
        return {"message": "Frontend not found. Place index.html in the static/ folder."}
    return FileResponse(str(index), headers={"Cache-Control": "no-cache"})


@router.get(PREFIX + "/health", tags=["System"])
def health_check():
    """Installed packages, model files and the local AI. The camera (TensorFlow) is an
    optional extra, so its absence never makes the app degraded."""
    report = system_health_check()
    packages = report.get("optional_packages", {})
    ready = (
        packages.get("sentence-transformers") is not None
        and packages.get("sqlalchemy") is not None
        and str(report.get("ollama_status", "")).startswith("available")
    )
    return {
        "status": "ok" if ready else "degraded",
        "agent_loaded": agent._loaded,
        "report": report,
    }
