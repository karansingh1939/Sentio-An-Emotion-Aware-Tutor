"""Tutoring API routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from sentio.api.dependencies import PREFIX, _verify_session_owner, agent
from sentio.api.schemas import ChatRequest
from sentio.auth.middleware import get_current_user
from sentio.emotion.access import decode_frame, require_emotion_access
from sentio.shared.exceptions import LLMServiceUnavailableError
from sentio.shared.text import sanitise_input

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(PREFIX + "/sessions/{session_id}/chat", tags=["Tutoring"])
def chat(session_id: str, req: ChatRequest, user: dict = Depends(get_current_user)):
    """
    Main tutoring endpoint.

    Send a student message + optional webcam frame.
    Returns an adaptive tutoring response including:
      - text, follow_up_question, encouragement, suggested_topic
      - detected emotion + learning state
      - current difficulty + strategy
      - engagement score
    """
    session = _verify_session_owner(session_id, user)
    if not session.is_active:
        raise HTTPException(
            status_code=409,
            detail="Session is not active (status=%s). Resume or create a new session."
            % session.status.value,
        )

    clean_msg = sanitise_input(req.message)
    if not clean_msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    frame = None
    if req.frame_b64:
        require_emotion_access(agent.sm.persister, user["student_id"])
        frame = decode_frame(req.frame_b64)
        if frame is None:
            raise HTTPException(422, "The camera frame is unreadable or too large.")

    try:
        response = agent.chat(
            session_id=session_id,
            student_message=clean_msg,
            frame=frame,
            quiz_correct=req.quiz_correct,
            response_time_sec=req.response_time_sec,
        )
    except LLMServiceUnavailableError:
        raise
    except Exception as exc:
        logger.exception("Chat error for session %s", session_id[:8])
        raise HTTPException(status_code=500, detail=str(exc))

    return response.to_dict()
