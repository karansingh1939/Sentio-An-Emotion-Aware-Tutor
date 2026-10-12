"""Documents API routes."""

import hashlib
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile

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


def _index_upload(filepath, category, subject, student_id, publisher=None, force=False):
    from sentio.ingestion.pipeline import DocumentIngestionPipeline

    pipeline = DocumentIngestionPipeline(sm=agent.sm, vdb=agent.kb.vdb)
    pipeline.load()
    existing = agent.sm.get_document_by_filename(
        filepath.name, student_id=student_id, category=category
    )
    checksum = pipeline.compute_checksum(filepath)
    if force or not (
        existing and existing["checksum"] == checksum and existing["status"] == "indexed"
    ):
        if not pipeline.process_file(
            filepath, category, subject, student_id=student_id, publisher=publisher, force=force
        ):
            raise HTTPException(
                status_code=422,
                detail=pipeline.last_error
                or "No usable text could be indexed. Upload a readable document.",
            )
    return agent.sm.get_document_by_filename(
        filepath.name, student_id=student_id, category=category
    )


def get_recovery(request):
    from sentio.ingestion.recovery import DocumentRecovery

    root = BASE_DIR / "data/documents"
    service = getattr(request.app.state, "documents", None)
    if (
        service is None
        or service.engine is not agent.sm.persister._engine
        or service.vectors is not agent.kb.vdb
        or service.root != root.resolve()
    ):
        service = DocumentRecovery(agent.sm.persister, agent.kb.vdb, root)
        request.app.state.documents = service
        service.recover()
    return service


async def stage_upload(request, file, category, subject, owner):
    from tempfile import TemporaryDirectory

    form = await request.form()
    category = request.query_params.get("category", form.get("category", category))
    subject = subject or form.get("subject")
    if category not in ["textbooks", "notes", "assignments", "reference", "uploaded"]:
        raise HTTPException(400, "Invalid document category.")
    filename = file.filename or ""
    reserved = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
    if (
        not filename
        or len(filename) > 180
        or any(ord(char) < 32 or char in '/\\:<>"|?*' for char in filename)
        or filename.endswith((".", " "))
        or filename.split(".")[0].upper() in reserved
    ):
        raise HTTPException(
            400, "Use a filename of up to 180 characters without paths or reserved characters."
        )
    if Path(file.filename).suffix.lower() not in [".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg"]:
        raise HTTPException(
            400, "Upload PDF, DOCX, TXT, PNG or JPEG. Scans and images require OCR."
        )
    for document in agent.sm.list_documents(student_id=owner):
        if (
            document["category"] == category
            and document["filename"].casefold() == filename.casefold()
            and document["filename"] != filename
        ):
            raise HTTPException(
                409,
                "A document with this filename already exists. Match its capitalization to replace it.",
            )
    dest_dir = BASE_DIR / "data/documents" / owner / category
    dest_dir.mkdir(parents=True, exist_ok=True)
    recovery = get_recovery(request)
    destination = recovery.path(dest_dir / file.filename, owner)
    temp = TemporaryDirectory(prefix=".pending-", dir=dest_dir)
    pending = Path(temp.name) / file.filename
    try:
        size = 0
        with pending.open("wb") as buffer:
            while chunk := await file.read(65536):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "Maximum upload size is 20 MB.")
                buffer.write(chunk)
        if await request.is_disconnected():
            raise HTTPException(499, "Upload was disconnected.")
    except Exception:
        temp.cleanup()
        raise
    return temp, pending, destination, category, subject, recovery


def ingest_staged(pending, destination, category, subject, owner, recovery):
    def publisher(document, chunks, old_chunks):
        recovery.replace(pending, destination, document, chunks, old_chunks)

    document = _index_upload(
        pending, category, subject, owner, publisher, force=not destination.exists()
    )
    return {
        "indexed": True,
        "filename": document["filename"],
        "category": category,
        "subject": document["subject"],
        "filepath": str(destination),
        "document_id": document["id"],
        "indexing_mode": "semantic" if document["embedding_count"] else "keyword",
        "extraction_method": document.get("extraction_method", "text"),
    }


@router.post(PREFIX + "/documents/upload", tags=["Documents"], status_code=201)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    category: str = "uploaded",
    subject: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    from starlette.concurrency import run_in_threadpool

    temp, pending, destination, category, subject, recovery = await stage_upload(
        request, file, category, subject, user["student_id"]
    )

    try:
        return await run_in_threadpool(
            ingest_staged, pending, destination, category, subject, user["student_id"], recovery
        )
    finally:
        temp.cleanup()


@router.post(PREFIX + "/documents/jobs", tags=["Documents"], status_code=202)
async def upload_job(
    request: Request,
    file: UploadFile = File(...),
    category: str = "uploaded",
    subject: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    from sentio.api.routes.jobs import fingerprint, get_jobs, submission_id
    from sentio.repositories.job_repository import JobConflict, JobExpired

    jobs = get_jobs(request)
    request_id = submission_id(request)
    temp, pending, destination, category, subject, recovery = await stage_upload(
        request, file, category, subject, user["student_id"]
    )

    def work(control):
        from sentio.jobs.control import WorkInputError

        try:
            return ingest_staged(
                pending, destination, category, subject, user["student_id"], recovery
            )
        except HTTPException as exc:
            if exc.status_code == 422:
                raise WorkInputError(str(exc.detail)) from exc
            raise

    try:
        return jobs.submit(
            user["student_id"],
            "ingestion",
            work,
            lane="ingestion",
            on_done=temp.cleanup,
            request_id=request_id,
            fingerprint=fingerprint(
                {
                    "filename": destination.name,
                    "category": category,
                    "subject": subject,
                    "checksum": hashlib.sha256(pending.read_bytes()).hexdigest(),
                }
            ),
        )
    except JobConflict as exc:
        temp.cleanup()
        raise HTTPException(409, str(exc)) from exc
    except JobExpired as exc:
        temp.cleanup()
        raise HTTPException(410, str(exc)) from exc
    except ValueError as exc:
        temp.cleanup()
        raise HTTPException(429, str(exc)) from exc
    except Exception:
        temp.cleanup()
        raise


@router.get(PREFIX + "/documents/{document_id}/preview", tags=["Documents"])
def preview(
    document_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    from sentio.repositories.document_repository import DocumentRepository

    result = DocumentRepository(agent.sm.persister).preview(
        document_id, user["student_id"], limit, offset
    )
    if result is None:
        raise HTTPException(404, "Document not found.")
    return result


@router.get(PREFIX + "/documents", tags=["Documents"])
def list_documents(user: dict = Depends(get_current_user)):
    """List all registered study materials and their indexing status."""
    docs = agent.sm.list_documents(student_id=user["student_id"])
    return {"documents": docs, "count": len(docs)}


@router.delete(PREFIX + "/documents/{doc_id}", tags=["Documents"])
def delete_document(doc_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Delete a document, its chunks, and its vector embeddings from Qdrant."""
    docs = agent.sm.list_documents(student_id=user["student_id"])
    doc = next((d for d in docs if d["id"] == doc_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found or access denied")

    filepath = BASE_DIR / "data/documents" / user["student_id"] / doc["category"] / doc["filename"]
    try:
        cleaned = get_recovery(request).delete(doc, filepath, agent.sm.get_document_chunks(doc_id))
    except Exception as exc:
        logger.exception("Document deletion failed")
        raise HTTPException(
            503, "Document deletion could not finish. Retry after local recovery."
        ) from exc
    return {"deleted": True, "document_id": doc_id, "cleanup_pending": not cleaned}


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
