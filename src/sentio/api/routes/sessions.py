"""Sessions API routes."""

import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from sentio.api.dependencies import PREFIX, _verify_session_owner, agent
from sentio.api.schemas import CreateSessionRequest, GroundingRequest, SessionGoalRequest
from sentio.auth.middleware import get_current_user
from sentio.config import tutor_cfg
from sentio.repositories.planning import active_goal

logger = logging.getLogger(__name__)
router = APIRouter()


def _owned_source(owner, source):
    """Notes a session studies from: "all", a course, a document id or a list of them."""
    from sentio.repositories.courses import COURSE_PREFIX, CourseRepository

    if source in (None, "none", "all"):
        return
    if isinstance(source, str) and source.startswith(COURSE_PREFIX):
        course = source[len(COURSE_PREFIX) :]
        if not CourseRepository(agent.sm.persister._engine).get(owner, course):
            raise HTTPException(status_code=403, detail="Access denied or course not found.")
        return
    selected = source if isinstance(source, list) else [source]
    owned = {doc["id"] for doc in agent.sm.list_documents(student_id=owner)}
    if any(not isinstance(doc_id, str) or doc_id not in owned for doc_id in selected):
        raise HTTPException(status_code=403, detail="Access denied or document not found.")


def _owned_topics(owner, metadata):
    """Topics a session practises: the student's own, inside the session's notes."""
    from sentio.repositories.courses import expand_source
    from sentio.repositories.topics import TopicRepository
    from sentio.study.topics import MAX_PRACTICE_TOPICS

    topic_ids = metadata.get("topic_ids")
    if topic_ids is None:
        return
    if (
        not isinstance(topic_ids, list)
        or not 1 <= len(topic_ids) <= MAX_PRACTICE_TOPICS
        or not all(isinstance(topic_id, str) for topic_id in topic_ids)
        or len(set(topic_ids)) != len(topic_ids)
    ):
        raise HTTPException(422, f"Choose 1 to {MAX_PRACTICE_TOPICS} different topics.")
    engine = agent.sm.persister._engine
    topics = TopicRepository(engine).passages(owner, topic_ids)
    with engine.connect() as connection:
        source = expand_source(connection, owner, metadata.get("document_id"))
    selected = source if isinstance(source, list) else [source]
    if topics is None or (
        source != "all" and any(topic["document_id"] not in selected for topic in topics)
    ):
        raise HTTPException(404, "Topic not found in these notes.")


def _owned_mode(owner, metadata):
    """How a session studies: the default, or "slides" on one lecture the student owns."""
    mode = metadata.get("mode")
    if mode is None:
        return
    document_id = metadata.get("document_id")
    owned = {doc["id"] for doc in agent.sm.list_documents(student_id=owner)}
    if mode != "slides" or not isinstance(document_id, str) or document_id not in owned:
        raise HTTPException(
            422, "Studying slides needs the mode 'slides' and one of your lectures."
        )


@router.post(PREFIX + "/sessions", tags=["Sessions"], status_code=201)
def create_session(req: CreateSessionRequest, user: dict = Depends(get_current_user)):
    """
    Create a new tutoring session.

    Returns the session_id to use in all subsequent calls.
    """
    if req.difficulty not in tutor_cfg.DIFFICULTY_LEVELS:
        raise HTTPException(
            status_code=400,
            detail="Invalid difficulty '%s'. Choose: %s"
            % (req.difficulty, tutor_cfg.DIFFICULTY_LEVELS),
        )

    # Force student_id from authenticated token payload
    req.student_id = user["student_id"]
    _owned_mode(req.student_id, req.metadata or {})
    _owned_source(req.student_id, (req.metadata or {}).get("document_id"))
    _owned_topics(req.student_id, req.metadata or {})
    _owned_goal(req.student_id, (req.metadata or {}).get("goal_id"))

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
    from sentio.repositories.practice import PracticeRepository

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
    _owned_source(user["student_id"], req.document_id)
    streams = getattr(request.app.state, "streams", None)
    if streams:
        streams.cancel_session(user["student_id"], session_id)
    previous = session.metadata.get("document_id")
    topics = session.metadata.pop("topic_ids", None)  # Chosen from the previous notes.
    slide = session.metadata.pop("slide", None)  # So is the slide, and studying by slides.
    mode = session.metadata.pop("mode", None)
    session.metadata["document_id"] = req.document_id
    try:
        agent.sm.persister.save_session(session)
    except Exception as e:
        session.metadata["document_id"] = previous
        if topics:
            session.metadata["topic_ids"] = topics
        if slide is not None:
            session.metadata["slide"] = slide
        if mode is not None:
            session.metadata["mode"] = mode
        logger.warning(f"Failed to persist updated session grounding state: {e}")
        raise HTTPException(503, "Source change could not be saved. Retry.") from e
    agent.nlp.clear_history(session_id)
    return {"success": True, "document_id": req.document_id}


def _owned_goal(owner, goal_id):
    if goal_id is None:
        return None
    with agent.sm.persister._engine.connect() as connection:
        goal = active_goal(connection, owner, goal_id)
    if goal is None:
        raise HTTPException(404, "Goal not found or no longer active.")
    return goal


class DifficultyChoice(BaseModel):
    difficulty: Literal["beginner", "intermediate", "advanced"]


@router.post(PREFIX + "/sessions/{session_id}/difficulty", tags=["Sessions"])
def choose_difficulty(
    session_id: str, req: DifficultyChoice, user: dict = Depends(get_current_user)
):
    """Set the level the learner chose and pin it: quiz streaks stop moving it until the
    learner asks for a change in chat. Used by Undo after an automatic change."""
    session = _verify_session_owner(session_id, user)
    previous = (
        session.difficulty,
        session.metadata.get("difficulty_pinned"),
        list(session.difficulty_log),
    )
    session.update_difficulty(req.difficulty, "learner_choice")
    session.metadata["difficulty_pinned"] = True
    try:
        agent.sm.persister.save_session(session)
    except Exception as e:
        session.difficulty, session.metadata["difficulty_pinned"], session.difficulty_log = previous
        logger.warning(f"Failed to persist chosen difficulty: {e}")
        raise HTTPException(503, "Difficulty could not be saved. Retry.") from e
    return {"difficulty": session.difficulty, "pinned": True}


@router.post(PREFIX + "/sessions/{session_id}/goal", tags=["Sessions"])
def set_session_goal(
    session_id: str,
    req: SessionGoalRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """Bind one of the owner's active goals to this session, or clear it with null."""
    session = _verify_session_owner(session_id, user)
    goal = _owned_goal(user["student_id"], req.goal_id)
    streams = getattr(request.app.state, "streams", None)
    if streams:
        streams.cancel_session(user["student_id"], session_id)
    previous = session.metadata.get("goal_id")
    session.metadata["goal_id"] = req.goal_id
    try:
        agent.sm.persister.save_session(session)
    except Exception as e:
        session.metadata["goal_id"] = previous
        logger.warning(f"Failed to persist updated session goal: {e}")
        raise HTTPException(503, "Goal change could not be saved. Retry.") from e
    return {"success": True, "goal": goal}


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
    return agent.sm.persister.session_page(student_id, active_only, limit, offset)
