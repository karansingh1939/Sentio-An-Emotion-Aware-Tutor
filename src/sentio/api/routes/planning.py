"""Owner-scoped deterministic planning API."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from sentio.api.dependencies import PREFIX, _verify_student_owner, agent
from sentio.auth.middleware import get_current_user
from sentio.study.planning import PlanningService

router = APIRouter(tags=["Study planning"])


class Preferences(BaseModel):
    daily_minutes: int = Field(ge=5, le=240)


class Completion(BaseModel):
    completed: bool


class GoalUpdate(BaseModel):
    goal_text: str | None = Field(default=None, min_length=1, max_length=500)
    target_date: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    status: Literal["active", "completed", "cancelled"] | None = None

    @model_validator(mode="after")
    def reject_empty(self):
        if "goal_text" in self.model_fields_set and not (self.goal_text or "").strip():
            raise ValueError("Goal text must not be blank")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("Status must not be null")
        return self


def service():
    return PlanningService(agent.sm.persister._engine)


@router.get(PREFIX + "/study/preferences")
def preferences(user: dict = Depends(get_current_user)):
    return service().repository.preferences(user["student_id"])


@router.put(PREFIX + "/study/preferences")
def save_preferences(body: Preferences, user: dict = Depends(get_current_user)):
    return service().repository.save_preferences(user["student_id"], body.daily_minutes)


@router.get(PREFIX + "/study/daily-plan")
def daily_plan(day: date | None = None, user: dict = Depends(get_current_user)):
    return service().daily_plan(user["student_id"], day)


@router.patch(PREFIX + "/study/daily-plan/{day}/tasks/{task_id}")
def complete_task(
    day: date, task_id: str, body: Completion, user: dict = Depends(get_current_user)
):
    result = service().repository.complete(user["student_id"], day, task_id, body.completed)
    if result is None:
        raise HTTPException(404, "Study task not found.")
    return result


@router.get(PREFIX + "/study/feedback")
def feedback(user: dict = Depends(get_current_user)):
    return service().feedback(user["student_id"])


@router.patch(PREFIX + "/students/{student_id}/goals/{goal_id}")
def update_goal(
    student_id: str, goal_id: str, body: GoalUpdate, user: dict = Depends(get_current_user)
):
    _verify_student_owner(student_id, user)
    result = service().repository.update_goal(
        student_id, goal_id, body.model_dump(exclude_unset=True)
    )
    if result is None:
        raise HTTPException(404, "Goal not found.")
    return {"goal": result}
