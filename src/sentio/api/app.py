"""FastAPI composition root. Run with `uv run sentio`."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from sentio.api.dependencies import PREFIX as PREFIX
from sentio.api.dependencies import STATIC_DIR
from sentio.api.dependencies import agent as agent
from sentio.api.dependencies import quiz_service as quiz_service
from sentio.api.dependencies import whiteboard_service as whiteboard_service
from sentio.api.middleware import (
    BodyLimitMiddleware,
    RateLimitMiddleware,
    ResponseHeadersMiddleware,
)
from sentio.api.routes import (
    analytics,
    auth,
    documents,
    flashcards,
    intelligence,
    jobs,
    memory,
    planning,
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
async def application_lifespan(app):
    """Load all subsystems on startup; graceful shutdown on exit."""
    logger.info("Starting Emotion-Aware AI Tutor API...")
    from sentio.config import validate_security_config

    validate_security_config()
    agent.load()
    from sentio.jobs.service import JobManager

    app.state.jobs = JobManager(agent.sm.persister._engine)
    from sentio.tutor.stream_service import StreamService

    app.state.streams = StreamService(agent, app.state.jobs)
    from sentio.ingestion.recovery import DocumentRecovery

    app.state.documents = DocumentRecovery(
        agent.sm.persister, agent.kb.vdb, documents.BASE_DIR / "data/documents"
    )
    app.state.documents.recover()
    from sentio.config import session_cfg
    from sentio.maintenance.account_cleanup import AccountCleanup

    AccountCleanup(
        agent.sm.persister,
        agent.kb.vdb,
        documents.BASE_DIR / "data/documents",
        session_cfg.SESSION_LOG_PATH,
        session_cfg.EMOTION_LOG_PATH,
    ).recover()
    report = system_health_check()
    print_health_report(report)
    logger.info("API ready on %s:%d", api_cfg.HOST, api_cfg.PORT)
    try:
        yield
    finally:
        logger.info("Shutting down...")
        app.state.jobs.close()
        agent.shutdown()


@asynccontextmanager
async def lifespan(app):
    from sentio.config import session_cfg
    from sentio.maintenance.storage_lease import storage_lease

    with storage_lease(session_cfg.DB_URL):
        async with application_lifespan(app):
            yield


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


@app.exception_handler(StarletteHTTPException)
async def http_failure(request, exc):
    detail = (
        "The operation failed. Retry, or check local diagnostics if it persists."
        if exc.status_code == 500
        else exc.detail
    )
    return JSONResponse(
        status_code=exc.status_code, content={"detail": detail}, headers=exc.headers
    )


@app.exception_handler(Exception)
async def unhandled_failure(request, exc):
    logger.error("Unhandled request failure (%s)", type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "The operation failed. Retry, or check local diagnostics if it persists."
        },
    )


app.add_middleware(BodyLimitMiddleware)
app.add_middleware(RateLimitMiddleware, rate=1.0, burst=60.0)
app.add_middleware(ResponseHeadersMiddleware)
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
app.include_router(planning.router)
app.include_router(jobs.router)
app.include_router(streaming.router)
