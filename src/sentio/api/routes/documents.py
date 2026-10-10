"""Documents API routes."""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from sentio.api.dependencies import PREFIX, agent
from sentio.auth.middleware import RoleRequired, get_current_user
from sentio.config import BASE_DIR

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


@router.get(PREFIX + "/documents/capabilities", tags=["Documents"])
def document_capabilities(user: dict = Depends(get_current_user)):
    from sentio.ingestion.ocr import ExtractionError, require_ocr

    try:
        require_ocr(pdf=True)
        return {"ocr_available": True, "ocr_language": "eng", "max_ocr_pages": 20}
    except ExtractionError as exc:
        return {"ocr_available": False, "ocr_setup": str(exc), "max_ocr_pages": 20}


def _index_upload(filepath, category, subject, student_id):
    from sentio.ingestion.pipeline import DocumentIngestionPipeline

    pipeline = DocumentIngestionPipeline(sm=agent.sm, vdb=agent.kb.vdb)
    pipeline.load()
    existing = agent.sm.get_document_by_filename(
        filepath.name, student_id=student_id, category=category
    )
    checksum = pipeline.compute_checksum(filepath)
    if not (existing and existing["checksum"] == checksum and existing["status"] == "indexed"):
        if not pipeline.process_file(filepath, category, subject, student_id=student_id):
            raise HTTPException(
                status_code=422,
                detail=pipeline.last_error
                or "No usable text could be indexed. Upload a readable document.",
            )
    return agent.sm.get_document_by_filename(
        filepath.name, student_id=student_id, category=category
    )


@router.post(PREFIX + "/documents/upload", tags=["Documents"], status_code=201)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    category: str = "uploaded",
    subject: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """Stage a bounded upload; replace the original only after successful indexing."""
    from tempfile import TemporaryDirectory

    from starlette.concurrency import run_in_threadpool

    form = await request.form()
    category = request.query_params.get("category", form.get("category", category))
    subject = subject or form.get("subject")
    if category not in ["textbooks", "notes", "assignments", "reference", "uploaded"]:
        raise HTTPException(status_code=400, detail="Invalid document category.")
    if not file.filename or any(char in file.filename for char in ("/", "\\", ":")):
        raise HTTPException(status_code=400, detail="Filename must not contain a path.")
    if Path(file.filename).suffix.lower() not in [".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg"]:
        raise HTTPException(
            status_code=400,
            detail="Upload PDF, DOCX, TXT, PNG or JPEG. Scans and images require OCR.",
        )
    dest_dir = BASE_DIR / "data/documents" / user["student_id"] / category
    dest_dir.mkdir(parents=True, exist_ok=True)
    filepath = dest_dir / file.filename
    if not filepath.resolve().is_relative_to(dest_dir.resolve()):
        raise HTTPException(status_code=400, detail="File must remain in the student directory.")
    with TemporaryDirectory(dir=dest_dir) as staging:
        pending = Path(staging) / file.filename
        size = 0
        with pending.open("wb") as buffer:
            while chunk := await file.read(65536):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Maximum upload size is 20 MB.")
                buffer.write(chunk)
        document = await run_in_threadpool(
            _index_upload, pending, category, subject, user["student_id"]
        )
        pending.replace(filepath)
    await run_in_threadpool(agent.kb.load)
    return {
        "indexed": True,
        "filename": file.filename,
        "category": category,
        "subject": subject or "general",
        "filepath": str(filepath),
        "document_id": document["id"],
        "indexing_mode": "semantic" if document["embedding_count"] else "keyword",
        "extraction_method": document.get("extraction_method", "text"),
    }


@router.get(PREFIX + "/documents", tags=["Documents"])
def list_documents(user: dict = Depends(get_current_user)):
    """List all registered study materials and their indexing status."""
    docs = agent.sm.list_documents(student_id=user["student_id"])
    return {"documents": docs, "count": len(docs)}


@router.delete(PREFIX + "/documents/{doc_id}", tags=["Documents"])
def delete_document(doc_id: str, user: dict = Depends(get_current_user)):
    """Delete a document, its chunks, and its vector embeddings from Qdrant."""
    docs = agent.sm.list_documents(student_id=user["student_id"])
    doc = next((d for d in docs if d["id"] == doc_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found or access denied")

    # Delete from disk if it exists
    cat = doc.get("category", "uploaded")
    filename = doc["filename"]
    filepath = BASE_DIR / "data" / "documents" / user["student_id"] / cat / filename
    if filepath.exists():
        try:
            filepath.unlink()
        except Exception as e:
            logger.warning(f"Failed to delete file {filepath}: {e}")

    # Delete from DB and Qdrant
    agent.sm.delete_document(doc_id)
    agent.kb.vdb.delete_document_points(doc_id)
    return {"deleted": True, "document_id": doc_id}


@router.post(PREFIX + "/documents/sync", tags=["Documents"])
def sync_documents(user: dict = Depends(RoleRequired("manage_users"))):
    """Scan the data/documents/ folders and sync with database/Qdrant."""
    from sentio.ingestion.pipeline import DocumentIngestionPipeline

    pipeline = DocumentIngestionPipeline(sm=agent.sm, vdb=agent.kb.vdb)
    pipeline.load()
    report = pipeline.scan_and_sync()

    # Reload knowledge base
    agent.kb.load()
    return {"synced": True, "report": report}
