"""Intelligence API routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from sentio.api.dependencies import PREFIX, _verify_session_owner, agent
from sentio.auth.middleware import get_current_user

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
    student_id: str, subject: str = "mathematics", user: dict = Depends(get_current_user)
):
    """
    Retrieve the topologically sequenced learning path for the student.
    """
    student_id = user["student_id"]
    try:
        path = agent.intelligence.generate_learning_path(student_id, subject)
        return {"student_id": student_id, "subject": subject, "path": path}
    except Exception as e:
        logger.exception("Failed to generate learning path")
        raise HTTPException(status_code=500, detail=str(e))


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
