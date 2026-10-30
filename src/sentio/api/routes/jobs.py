"""Owner-scoped durable work, additive to the synchronous practice API."""

import hashlib
import json
import re
from copy import deepcopy

from fastapi import APIRouter, Depends, HTTPException, Request

from sentio.api.dependencies import (
    PREFIX,
    _verify_session_owner,
    agent,
    flashcard_service,
    quiz_service,
)
from sentio.api.schemas import GenerateFlashcardsRequest, QuizGenerateRequest
from sentio.auth.middleware import get_current_user
from sentio.jobs.control import WorkCancelled
from sentio.repositories.jobs import JobConflict, JobExpired
from sentio.repositories.practice import PracticeRepository
from sentio.repositories.topics import TopicChanged

router = APIRouter()


def get_jobs(request: Request):
    manager = getattr(request.app.state, "jobs", None)
    if manager is None or manager.closed:
        raise HTTPException(503, "The local work queue is unavailable. Restart Sentio.")
    return manager


def submission_id(request):
    value = request.headers.get("Idempotency-Key")
    if value is not None and not re.fullmatch(r"[a-zA-Z0-9_-]{8,80}", value):
        raise HTTPException(
            422, "Use a submission ID of 8–80 letters, numbers, underscores or hyphens."
        )
    return value


def fingerprint(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def study_snapshot(service, session):
    try:
        return PracticeRepository(service.agent.sm.persister._engine).snapshot(session)
    except WorkCancelled as exc:
        raise HTTPException(409, str(exc)) from exc


def submit(manager, owner, kind, work, request_id=None, content=None):
    try:
        return manager.submit(
            owner,
            kind,
            work,
            request_id=request_id,
            fingerprint=fingerprint(content),
            study_context=content.get("context") if content else None,
        )
    except JobConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except JobExpired as exc:
        raise HTTPException(410, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(429, str(exc)) from exc


@router.get(PREFIX + "/jobs/{job_id}", tags=["Jobs"])
def status(job_id: str, jobs=Depends(get_jobs), user=Depends(get_current_user)):
    record = jobs.get(job_id, user["student_id"])
    if record is None:
        raise HTTPException(404, "Job not found.")
    return record


@router.post(PREFIX + "/jobs/{job_id}/cancel", tags=["Jobs"])
def cancel(job_id: str, jobs=Depends(get_jobs), user=Depends(get_current_user)):
    if jobs.get(job_id, user["student_id"]) is None:
        raise HTTPException(404, "Job not found.")
    accepted = jobs.cancel(job_id, user["student_id"])
    return {"accepted": accepted, "job": jobs.get(job_id, user["student_id"])}


@router.post(PREFIX + "/documents/{document_id}/overview/jobs", tags=["Jobs"], status_code=202)
def overview_job(
    document_id: str, request: Request, jobs=Depends(get_jobs), user=Depends(get_current_user)
):
    from sentio.repositories.documents import DocumentRepository
    from sentio.study.overview import generate_overview

    owner = user["student_id"]
    if DocumentRepository(agent.sm.persister).preview(document_id, owner, limit=1) is None:
        raise HTTPException(404, "Document not found.")
    return submit(
        jobs,
        owner,
        "overview",
        lambda control: generate_overview(agent, owner, document_id),
        request_id=submission_id(request),
        content={"request": {"document_id": document_id}},
    )


@router.post(PREFIX + "/quizzes/jobs", tags=["Jobs"], status_code=202)
def quiz_job(
    req: QuizGenerateRequest,
    request: Request,
    jobs=Depends(get_jobs),
    user=Depends(get_current_user),
):
    session = deepcopy(_verify_session_owner(req.session_id, user))
    # Freeze context at submission; mutable frontend fields are not a second authority.
    snapshot = study_snapshot(quiz_service, session)
    try:
        quiz_service.topic_focus(session)
    except TopicChanged as exc:
        raise HTTPException(409, str(exc)) from exc
    return submit(
        jobs,
        user["student_id"],
        "quiz",
        lambda control: quiz_service.generate_quiz(
            student_id=user["student_id"],
            session_id=session.session_id,
            subject=session.subject,
            topic=session.topic,
            difficulty=session.difficulty,
            num_questions=req.num_questions,
            study_session=session,
            source_snapshot=snapshot,
        ),
        request_id=submission_id(request),
        content={
            "request": req.model_dump(),
            "context": snapshot,
        },
    )


@router.post(PREFIX + "/flashcards/jobs", tags=["Jobs"], status_code=202)
def card_job(
    req: GenerateFlashcardsRequest,
    request: Request,
    jobs=Depends(get_jobs),
    user=Depends(get_current_user),
):
    if not req.session_id:
        raise HTTPException(422, "Choose an active study session before generating cards.")
    session = deepcopy(_verify_session_owner(req.session_id, user))
    snapshot = study_snapshot(flashcard_service, session)
    if not any(
        d["deck_id"] == req.deck_id for d in flashcard_service.list_decks(user["student_id"])
    ):
        raise HTTPException(403, "Access denied to this flashcard deck.")
    return submit(
        jobs,
        user["student_id"],
        "flashcards",
        lambda control: flashcard_service.generate_flashcards(
            student_id=user["student_id"],
            deck_id=req.deck_id,
            topic_id=session.topic,
            num_cards=req.num_cards,
            session_id=session.session_id,
            study_session=session,
            source_snapshot=snapshot,
        ),
        request_id=submission_id(request),
        content={
            "request": req.model_dump(),
            "context": snapshot,
        },
    )
