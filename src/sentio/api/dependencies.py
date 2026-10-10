"""Shared application services and resource ownership checks."""

import base64
import logging

import numpy as np
from fastapi import HTTPException, status

from sentio.config import PACKAGE_DIR, api_cfg
from sentio.flashcards.flashcard_service import FlashcardService
from sentio.quiz.quiz_service import QuizService
from sentio.tutor.tutor_agent import TutorAgent
from sentio.whiteboard.whiteboard_service import WhiteboardService

agent = TutorAgent()
PREFIX = api_cfg.API_PREFIX
STATIC_DIR = PACKAGE_DIR / "static"
quiz_service = QuizService(agent)
flashcard_service = FlashcardService(agent)
whiteboard_service = WhiteboardService(agent)

logger = logging.getLogger(__name__)


def _decode_frame(frame_b64):
    """
    Decode a base64 JPEG string to a BGR numpy array.
    Returns None on failure (never raises).
    """
    if not frame_b64:
        return None
    try:
        import cv2

        buf = np.frombuffer(base64.b64decode(frame_b64), dtype=np.uint8)
        frame = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        return frame
    except Exception as exc:
        logger.warning("Frame decode failed: %s", exc)
        return None


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
