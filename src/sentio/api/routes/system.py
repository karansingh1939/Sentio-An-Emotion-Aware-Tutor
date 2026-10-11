"""System API routes."""

import logging

from fastapi import APIRouter
from fastapi.responses import FileResponse

from sentio.api.dependencies import PREFIX, STATIC_DIR, agent
from sentio.config import tutor_cfg
from sentio.maintenance.readiness import readiness
from sentio.shared.utils import system_health_check

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
    return FileResponse(str(index))


@router.get(PREFIX + "/health", tags=["System"])
def health_check():
    """System health -- TensorFlow, GPU, model file, webcam, packages."""
    report = system_health_check()
    ready = report.get("tensorflow") is not None and report.get("opencv") is not None
    return {
        "status": "ok" if ready else "degraded",
        "agent_loaded": agent._loaded,
        "report": report,
    }


@router.get(PREFIX + "/subjects", tags=["Curriculum"])
def list_subjects():
    """List all supported subjects and their available topics."""
    result = {}
    for subject in tutor_cfg.SUBJECTS:
        topics = agent.kb.list_topics(subject)
        result[subject] = topics
    return {"subjects": result}
