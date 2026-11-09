"""Studying a lecture slide by slide: its slides, the slide being studied, and the study mood."""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from sentio.api.dependencies import PREFIX, _verify_session_owner, agent
from sentio.auth.middleware import get_current_user
from sentio.emotion import policy
from sentio.emotion.access import require_emotion_access
from sentio.repositories.slides import SlideRepository
from sentio.session.models import EmotionTimeline

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Slides"])

# Plain words for the mood chip; a fresh reading of any other state reads as calm, and no fresh
# reading has no label.
MOOD_LABELS = {
    "engaged": "focused",
    "curious": "focused",
    "struggling": "unsure",
    "frustrated": "unsure",
    "anxious": "unsure",
    "disengaged": "looking away",
}


class SlideChoice(BaseModel):
    number: int


def repository():
    return SlideRepository(agent.sm.persister._engine)


@router.get(PREFIX + "/documents/{document_id}/slides")
def document_slides(document_id: str, user: dict = Depends(get_current_user)):
    """A lecture slide by slide, each with its title, text and topic."""
    lecture = repository().slides(user["student_id"], document_id)
    if lecture is None:
        raise HTTPException(404, "Notes not found or not ready yet.")
    return lecture


@router.put(PREFIX + "/sessions/{session_id}/slide")
def set_session_slide(session_id: str, req: SlideChoice, user: dict = Depends(get_current_user)):
    """Record the slide the learner is studying, for sessions on one lecture."""
    session = _verify_session_owner(session_id, user)
    document_id = session.metadata.get("document_id")
    if (
        not isinstance(document_id, str)
        or document_id == "all"
        or document_id.startswith("course:")
    ):
        raise HTTPException(409, "Slides can be studied only in a session on one lecture.")
    if repository().slide(user["student_id"], document_id, req.number) is None:
        raise HTTPException(404, "Slide not found in these notes.")
    previous = session.metadata.get("slide")
    session.metadata["slide"] = req.number
    try:
        agent.sm.persister.save_session(session)
    except Exception as e:
        if previous is None:
            session.metadata.pop("slide", None)
        else:
            session.metadata["slide"] = previous
        logger.warning(f"Failed to persist the studied slide: {e}")
        raise HTTPException(503, "Slide change could not be saved. Retry.") from e
    return {"number": req.number}


@router.get(PREFIX + "/sessions/{session_id}/mood")
def session_mood(session_id: str, user: dict = Depends(get_current_user)):
    """The camera's guess at how the learner is doing, steadied over the last moments."""
    session = _verify_session_owner(session_id, user)
    require_emotion_access(agent.sm.persister, user["student_id"])
    events = session.emotion_timeline.recent(EmotionTimeline.MAX_EVENTS)
    mood = policy.study_mood(events, time.time())
    label = MOOD_LABELS.get(mood["learning_state"], "calm") if mood["fresh"] else None
    return {**mood, "label": label}
