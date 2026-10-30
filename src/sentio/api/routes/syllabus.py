"""A course's syllabus: add it once, then see how much of it is ready."""

import tempfile
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, model_validator

from sentio.api.dependencies import PREFIX, agent
from sentio.auth.middleware import get_current_user
from sentio.repositories.syllabus import SyllabusRepository
from sentio.study.syllabus import parse_syllabus

router = APIRouter(tags=["Syllabus"])
MAX_SYLLABUS_BYTES = 5 * 1024 * 1024
MAX_SYLLABUS_CHARS = 50_000
READERS = {".txt": "parse_txt", ".pdf": "parse_pdf", ".docx": "parse_docx", ".pptx": "parse_pptx"}


class LinkChoice(BaseModel):
    mode: Literal["auto", "manual", "none"]
    topic_id: Optional[str] = None

    @model_validator(mode="after")
    def manual_needs_topic(self):
        if (self.mode == "manual") != bool(self.topic_id):
            raise ValueError("Choose a topic for a manual link, and only then.")
        return self


def repository():
    return SyllabusRepository(agent.sm.persister._engine)


async def _file_text(upload):
    from sentio.ingestion.pipeline import DocumentIngestionPipeline

    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in READERS:
        raise HTTPException(400, "Upload the syllabus as PDF, DOCX, PPTX or TXT, or paste it.")
    content = await upload.read(MAX_SYLLABUS_BYTES + 1)
    if len(content) > MAX_SYLLABUS_BYTES:
        raise HTTPException(413, "Syllabus files are limited to 5 MB.")
    with tempfile.TemporaryDirectory(prefix="sentio-syllabus-") as folder:
        path = Path(folder) / ("syllabus" + suffix)
        path.write_bytes(content)
        try:
            # The readers are plain parsers; no pipeline state (database, index) is needed.
            pages = getattr(DocumentIngestionPipeline, READERS[suffix])(None, path)
        except Exception as exc:
            raise HTTPException(422, "The syllabus file could not be read.") from exc
    return "\n".join(page["text"] for page in pages)


@router.put(PREFIX + "/courses/{course_id}/syllabus")
async def save_syllabus(
    course_id: str,
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    user: dict = Depends(get_current_user),
):
    """Replace the course syllabus with pasted text or an uploaded file."""
    content = await _file_text(file) if file is not None else (text or "")
    items = parse_syllabus(content[:MAX_SYLLABUS_CHARS])
    if not items:
        raise HTTPException(422, "No syllabus topics were found. Paste one topic per line.")
    if not repository().replace(user["student_id"], course_id, items):
        raise HTTPException(404, "Course not found.")
    return repository().progress(user["student_id"], course_id)


@router.get(PREFIX + "/courses/{course_id}/syllabus")
def syllabus_progress(course_id: str, user: dict = Depends(get_current_user)):
    """Syllabus topics with their matched lecture topics, status and percentage ready."""
    progress = repository().progress(user["student_id"], course_id)
    if progress is None:
        raise HTTPException(404, "Course not found.")
    return progress


@router.delete(PREFIX + "/courses/{course_id}/syllabus")
def delete_syllabus(course_id: str, user: dict = Depends(get_current_user)):
    if not repository().delete(user["student_id"], course_id):
        raise HTTPException(404, "Course not found.")
    return {"deleted": True}


@router.patch(PREFIX + "/syllabus/{item_id}")
def correct_match(item_id: str, body: LinkChoice, user: dict = Depends(get_current_user)):
    """Correct a match: link one lecture topic, mark as not in the notes, or reset to auto."""
    if not repository().set_link(user["student_id"], item_id, body.mode, body.topic_id):
        raise HTTPException(404, "Syllabus topic not found.")
    return {"id": item_id, "mode": body.mode, "topic_id": body.topic_id}
