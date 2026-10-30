"""Courses: optional, owner-scoped folders for lecture notes."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from sentio.api.dependencies import PREFIX, agent
from sentio.auth.middleware import get_current_user
from sentio.repositories.courses import CourseConflict, CourseRepository

router = APIRouter(tags=["Courses"])


class CourseName(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def strip(cls, value):
        value = " ".join(value.split())
        if not value:
            raise ValueError("Course name must not be blank")
        return value


class CourseMove(BaseModel):
    course_id: Optional[str] = None


def repository():
    return CourseRepository(agent.sm.persister._engine)


@router.get(PREFIX + "/courses")
def list_courses(user: dict = Depends(get_current_user)):
    return {"courses": repository().list(user["student_id"])}


@router.post(PREFIX + "/courses", status_code=201)
def create_course(body: CourseName, user: dict = Depends(get_current_user)):
    try:
        return repository().create(user["student_id"], body.name)
    except CourseConflict as exc:
        raise HTTPException(409, str(exc)) from exc


@router.patch(PREFIX + "/courses/{course_id}")
def rename_course(course_id: str, body: CourseName, user: dict = Depends(get_current_user)):
    try:
        course = repository().rename(user["student_id"], course_id, body.name)
    except CourseConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    if course is None:
        raise HTTPException(404, "Course not found.")
    return course


@router.delete(PREFIX + "/courses/{course_id}")
def delete_course(course_id: str, user: dict = Depends(get_current_user)):
    """Delete a course. Its lectures are kept, outside any course."""
    if not repository().delete(user["student_id"], course_id):
        raise HTTPException(404, "Course not found.")
    return {"deleted": True}


@router.patch(PREFIX + "/documents/{document_id}/course")
def move_document(document_id: str, body: CourseMove, user: dict = Depends(get_current_user)):
    """Move a lecture into a course, or out of any course with course_id null."""
    if not repository().move_document(user["student_id"], document_id, body.course_id):
        raise HTTPException(404, "Notes or course not found.")
    return {"document_id": document_id, "course_id": body.course_id}
