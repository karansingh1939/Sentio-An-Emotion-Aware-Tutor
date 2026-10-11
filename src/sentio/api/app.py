"""FastAPI composition root. Run with `uv run sentio`."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from sentio.api.dependencies import PREFIX as PREFIX
from sentio.api.dependencies import STATIC_DIR
from sentio.api.dependencies import agent as agent
from sentio.api.dependencies import quiz_service as quiz_service
from sentio.api.dependencies import whiteboard_service as whiteboard_service
from sentio.api.middleware import RateLimitMiddleware
from sentio.api.routes import (
    analytics,
    auth,
    documents,
    flashcards,
    intelligence,
    jobs,
    memory,
    privacy,
    quizzes,
    sessions,
    streaming,
    system,
    telemetry,
    tutoring,
    whiteboards,
)
from sentio.config import api_cfg
from sentio.shared.exceptions import LLMServiceUnavailableError
from sentio.shared.utils import RateLimiter as RateLimiter
from sentio.shared.utils import print_health_report, setup_logging, system_health_check

setup_logging(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    """Load all subsystems on startup; graceful shutdown on exit."""
    logger.info("Starting Emotion-Aware AI Tutor API...")
    from sentio.config import validate_security_config

    validate_security_config()
    agent.load()
    from sentio.jobs.service import JobManager

    app.state.jobs = JobManager(agent.sm.persister._engine)
    from sentio.tutor.stream_service import StreamService

    app.state.streams = StreamService(agent, app.state.jobs)
    report = system_health_check()
    print_health_report(report)
    logger.info("API ready on %s:%d", api_cfg.HOST, api_cfg.PORT)
    try:
        yield
    finally:
        logger.info("Shutting down...")
        app.state.jobs.close()
        agent.shutdown()


app = FastAPI(title="Sentio", version="2.0.0-rc1", lifespan=lifespan)
app.state.agent = agent


@app.exception_handler(LLMServiceUnavailableError)
async def llm_service_unavailable_handler(request: Request, exc: LLMServiceUnavailableError):
    logger.error("LLM Service Unavailable: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": (
                f"The AI tutoring service ({exc.backend_name}) is currently unavailable or unreachable. "
                f"Please ensure your LLM provider/server is running and has the model loaded."
            )
        },
    )


app.add_middleware(RateLimitMiddleware, rate=1.0, burst=60.0)
app.add_middleware(
    CORSMiddleware,
    allow_origins=api_cfg.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(system.router)
app.include_router(sessions.router)
app.include_router(telemetry.router)
app.include_router(tutoring.router)
app.include_router(quizzes.router)
app.include_router(flashcards.router)
app.include_router(whiteboards.router)
app.include_router(auth.router)
app.include_router(privacy.router)
app.include_router(intelligence.router)
app.include_router(analytics.router)
app.include_router(documents.router)
app.include_router(memory.router)
app.include_router(jobs.router)
app.include_router(streaming.router)
