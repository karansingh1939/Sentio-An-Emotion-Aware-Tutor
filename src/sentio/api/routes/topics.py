"""Topics inside lectures, their practice state, and course progress."""

from fastapi import APIRouter, Depends, HTTPException

from sentio.api.dependencies import PREFIX, agent
from sentio.api.routes.courses import CourseName
from sentio.auth.middleware import get_current_user
from sentio.repositories.topics import TopicRepository

router = APIRouter(tags=["Topics"])


def repository():
    return TopicRepository(agent.sm.persister._engine)


@router.get(PREFIX + "/documents/{document_id}/topics")
def document_topics(document_id: str, user: dict = Depends(get_current_user)):
    """A lecture's topics (page ranges) with each topic's practice state."""
    lecture = repository().document_topics(user["student_id"], document_id)
    if lecture is None:
        raise HTTPException(404, "Notes not found or not ready yet.")
    return lecture


@router.get(PREFIX + "/courses/{course_id}/progress")
def course_progress(course_id: str, user: dict = Depends(get_current_user)):
    """Topic states for every lecture in a course, with the weakest topics first."""
    progress = repository().course_progress(user["student_id"], course_id)
    if progress is None:
        raise HTTPException(404, "Course not found.")
    return progress


@router.get(PREFIX + "/topics/due")
def due_topics(user: dict = Depends(get_current_user)):
    """Topics due for review across all notes, least remembered first."""
    return {"topics": repository().due_topics(user["student_id"])}


@router.patch(PREFIX + "/topics/{topic_id}")
def rename_topic(topic_id: str, body: CourseName, user: dict = Depends(get_current_user)):
    if not repository().rename(user["student_id"], topic_id, body.name):
        raise HTTPException(404, "Topic not found.")
    return {"id": topic_id, "title": body.name}


@router.post(PREFIX + "/topics/{topic_id}/merge")
def merge_topic(topic_id: str, user: dict = Depends(get_current_user)):
    """Join a topic to the topic before it in the same lecture."""
    if not repository().merge_into_previous(user["student_id"], topic_id):
        raise HTTPException(404, "Topic not found, or it is the first topic.")
    return {"merged": True}
