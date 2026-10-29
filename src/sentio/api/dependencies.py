"""Shared application services and resource ownership checks."""

import logging

from fastapi import HTTPException, status

from sentio.config import PACKAGE_DIR, api_cfg
from sentio.flashcards.service import FlashcardService
from sentio.quiz.service import QuizService
from sentio.tutor.agent import TutorAgent

agent = TutorAgent()
PREFIX = api_cfg.API_PREFIX
STATIC_DIR = PACKAGE_DIR / "static"
quiz_service = QuizService(agent)
flashcard_service = FlashcardService(agent)

logger = logging.getLogger(__name__)


def _get_session_or_404(session_id):
    """Get session from agent or raise 404."""
    session = agent.sm.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found: %s" % session_id,
        )
    return session


def _verify_student_owner(student_id: str, user: dict):
    if student_id != user["student_id"]:
        raise HTTPException(status_code=403, detail="Access denied to this student.")


def _verify_session_owner(session_id: str, user: dict):
    """Verify that the session exists and belongs to the authenticated user."""
    session = _get_session_or_404(session_id)
    if session.student_id != user["student_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this session."
        )
    return session
