"""Memory API routes."""

import logging

from fastapi import APIRouter, Depends

from sentio.api.dependencies import PREFIX, _verify_student_owner, agent
from sentio.api.schemas import CreateGoalRequest
from sentio.auth.middleware import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(PREFIX + "/students/{student_id}/goals", tags=["Memory"], status_code=201)
def create_student_goal(
    student_id: str, req: CreateGoalRequest, user: dict = Depends(get_current_user)
):
    """Add a new learning goal for the student."""
    _verify_student_owner(student_id, user)
    goal_id = agent.sm.add_learning_goal(
        student_id=student_id,
        goal_text=req.goal_text,
        topic_id=req.topic_id,
        target_date=req.target_date,
    )
    return {"recorded": True, "goal_id": goal_id}


@router.get(PREFIX + "/students/{student_id}/goals", tags=["Memory"])
def get_student_goals(
    student_id: str, status: str = "active", user: dict = Depends(get_current_user)
):
    """List active learning goals for the student."""
    _verify_student_owner(student_id, user)
    goals = agent.sm.get_learning_goals(student_id, status=status)
    return {"student_id": student_id, "goals": goals, "count": len(goals)}


@router.get(PREFIX + "/students/{student_id}/memory", tags=["Memory"])
def get_student_memory(student_id: str, user: dict = Depends(get_current_user)):
    """Inspect the student profile, topic mastery, and mistake logs in memory."""
    _verify_student_owner(student_id, user)
    memory_context = agent.sm.get_student_memory_context(student_id)
    weak = agent.sm.get_weak_topics(student_id)
    strong = agent.sm.get_strong_topics(student_id)
    mistakes = agent.sm.get_student_mistake_metrics(student_id)
    return {
        "student_id": student_id,
        "formatted_memory_context": memory_context,
        "weak_topics": weak,
        "strong_topics": strong,
        "mistake_metrics": {
            "recent_mistakes": mistakes.get("recent_mistakes_list", []),
            "recurring_mistakes": mistakes.get("recurring_mistakes", []),
            "mistake_frequency": mistakes.get("mistake_frequency", {}),
        },
    }
