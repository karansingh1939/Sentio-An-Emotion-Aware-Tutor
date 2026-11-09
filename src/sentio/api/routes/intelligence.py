"""Intelligence API routes."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from sentio.api.dependencies import PREFIX, _verify_session_owner, agent
from sentio.auth.middleware import get_current_user
from sentio.repositories.topics import TopicRepository

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(PREFIX + "/student/{student_id}/profile", tags=["Intelligence"])
def get_student_profile(student_id: str, user: dict = Depends(get_current_user)):
    """
    Retrieve the multidimensional LearnerModel for the student.
    """
    student_id = user["student_id"]
    try:
        model = agent.intelligence.build_learner_model(student_id)
        return model.to_dict()
    except Exception as e:
        logger.exception("Failed to build student profile")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(PREFIX + "/student/{student_id}/recommendations", tags=["Intelligence"])
def get_student_recommendations(student_id: str, user: dict = Depends(get_current_user)):
    """
    Retrieve actionable, explained study recommendations for the student.
    """
    student_id = user["student_id"]
    try:
        recs = agent.intelligence.generate_recommendations(student_id)
        return [r.to_dict() for r in recs]
    except Exception as e:
        logger.exception("Failed to generate recommendations")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(PREFIX + "/student/{student_id}/learning_path", tags=["Intelligence"])
def get_student_learning_path(
    student_id: str, course_id: Optional[str] = None, user: dict = Depends(get_current_user)
):
    """
    What to study next, built from the learner's own lecture topics: due reviews first,
    then topics being practised, then new topics in lecture order. Optionally one course.
    """
    path = TopicRepository(agent.sm.persister._engine).learning_path(user["student_id"], course_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Course not found.")
    return {"student_id": user["student_id"], **path}


@router.get(PREFIX + "/session/{session_id}/summary", tags=["Intelligence"])
def get_session_summary(session_id: str, user: dict = Depends(get_current_user)):
    """
    Retrieve the pedagogical and emotional summary for a finished session.
    """
    _verify_session_owner(session_id, user)
    try:
        summary = agent.intelligence.generate_session_summary(session_id)
        return summary.to_dict()
    except KeyError as k_err:
        raise HTTPException(status_code=404, detail=str(k_err))
    except Exception as e:
        logger.exception("Failed to compile session summary")
        raise HTTPException(status_code=500, detail=str(e))
