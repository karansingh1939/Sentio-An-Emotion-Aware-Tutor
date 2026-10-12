"""Sessions API routes."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from sentio.api.dependencies import PREFIX, _verify_session_owner, agent
from sentio.api.schemas import CreateSessionRequest, GroundingRequest
from sentio.auth.middleware import get_current_user
from sentio.config import tutor_cfg

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(PREFIX + "/sessions", tags=["Sessions"], status_code=201)
def create_session(req: CreateSessionRequest, user: dict = Depends(get_current_user)):
    """
    Create a new tutoring session.

    Returns the session_id to use in all subsequent calls.
    """
    if req.subject not in tutor_cfg.SUBJECTS:
        raise HTTPException(
            status_code=400,
            detail="Unknown subject '%s'. Available: %s" % (req.subject, tutor_cfg.SUBJECTS),
        )
    if req.difficulty not in tutor_cfg.DIFFICULTY_LEVELS:
        raise HTTPException(
            status_code=400,
            detail="Invalid difficulty '%s'. Choose: %s"
            % (req.difficulty, tutor_cfg.DIFFICULTY_LEVELS),
        )

    # Force student_id from authenticated token payload
    req.student_id = user["student_id"]
    document_id = (req.metadata or {}).get("document_id")
    if document_id not in (None, "none", "all"):
        selected = document_id if isinstance(document_id, list) else [document_id]
        owned = {doc["id"] for doc in agent.sm.list_documents(student_id=req.student_id)}
        if any(not isinstance(doc_id, str) or doc_id not in owned for doc_id in selected):
            raise HTTPException(status_code=403, detail="Access denied or document not found.")

    session = agent.start_session(
        student_id=req.student_id,
        subject=req.subject,
        topic=req.topic,
        difficulty=req.difficulty,
        metadata=req.metadata,
    )
    return {
        "session_id": session.session_id,
        "student_id": session.student_id,
        "subject": session.subject,
        "topic": session.topic,
        "difficulty": session.difficulty,
        "status": session.status.value,
        "created_at": session.created_at,
    }


@router.get(PREFIX + "/sessions/{session_id}", tags=["Sessions"])
def get_session(session_id: str, user: dict = Depends(get_current_user)):
    """Get the current live state of a session."""
    _verify_session_owner(session_id, user)
    return agent.sm.get_current_state(session_id)


@router.get(PREFIX + "/sessions/{session_id}/context", tags=["Sessions"])
def get_study_context(session_id: str, user: dict = Depends(get_current_user)):
    from sentio.jobs.control import WorkCancelled
    from sentio.repositories.practice_repository import PracticeRepository

    session = _verify_session_owner(session_id, user)
    try:
        return PracticeRepository(agent.sm.persister._engine).snapshot(session)
    except WorkCancelled as exc:
        raise HTTPException(409, str(exc)) from exc


@router.delete(PREFIX + "/sessions/{session_id}", tags=["Sessions"])
def close_session(session_id: str, user: dict = Depends(get_current_user)):
    """
    Close a session gracefully.
    Returns the final SessionAnalytics report.
    """
    _verify_session_owner(session_id, user)
    analytics = agent.end_session(session_id)
    return analytics.to_dict()


@router.post(PREFIX + "/sessions/{session_id}/pause", tags=["Sessions"])
def pause_session(session_id: str, user: dict = Depends(get_current_user)):
    _verify_session_owner(session_id, user)
    agent.pause_session(session_id)
    return {"status": "paused", "session_id": session_id}


@router.post(PREFIX + "/sessions/{session_id}/resume", tags=["Sessions"])
def resume_session(session_id: str, user: dict = Depends(get_current_user)):
    _verify_session_owner(session_id, user)
    try:
        agent.resume_session(session_id)
    except PermissionError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"status": "active", "session_id": session_id}


@router.post(PREFIX + "/sessions/{session_id}/grounding", tags=["Sessions"])
def set_session_grounding(
    session_id: str, req: GroundingRequest, request: Request, user: dict = Depends(get_current_user)
):
    """Update active document grounding source mid-session."""
    session = _verify_session_owner(session_id, user)
    if req.document_id not in ["none", "all"]:
        docs = agent.sm.list_documents(student_id=user["student_id"])
        if not any(d["id"] == req.document_id for d in docs):
            raise HTTPException(status_code=403, detail="Access denied or document not found.")
    streams = getattr(request.app.state, "streams", None)
    if streams:
        streams.cancel_session(user["student_id"], session_id)
    previous = session.metadata.get("document_id")
    session.metadata["document_id"] = req.document_id
    if agent.sm.persister._use_db:
        try:
            agent.sm.persister.save_session(session)
        except Exception as e:
            session.metadata["document_id"] = previous
            logger.warning(f"Failed to persist updated session grounding state: {e}")
            raise HTTPException(503, "Source change could not be saved. Retry.") from e
    agent.nlp.clear_history(session_id)
    agent.kb.reset_session(session_id)
    return {"success": True, "document_id": req.document_id}


@router.get(PREFIX + "/sessions", tags=["Sessions"])
def list_sessions(
    student_id: Optional[str] = None,
    active_only: bool = False,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    """List all sessions, optionally filtered by student or active status."""
    student_id = user["student_id"]
    if agent.sm.persister._use_db:
        return agent.sm.persister.session_page(student_id, active_only, limit, offset)
    sessions = agent.list_sessions(student_id=student_id, active_only=active_only)
    sessions.sort(key=lambda row: (row.get("created_at", 0), row["session_id"]), reverse=True)
    total = len(sessions)
    page = sessions[offset : offset + limit]
    return {
        "sessions": page,
        "count": len(page),
        "total": total,
        "offset": offset,
        "next_offset": offset + len(page) if offset + len(page) < total else None,
    }
