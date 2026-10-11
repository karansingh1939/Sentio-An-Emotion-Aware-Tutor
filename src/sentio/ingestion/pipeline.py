import hashlib
import logging
import os
import time
import uuid
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional

from sentio.config import DATA_DIR, nlp_cfg
from sentio.jobs.control import WorkCancelled, checkpoint, publish
from sentio.rag.vector_db import QdrantVectorDB
from sentio.repositories.document_repository import DocumentRepository
from sentio.session.session_manager import SessionManager

logger = logging.getLogger(__name__)
_ingestion_lock = RLock()


class DocumentIngestionPipeline:
    """
    Intelligent document ingestion pipeline for Sentio.
    Supports PDF, DOCX, and TXT files. Handles incremental indexing,
    duplicate checksum detection, chunking with metadata, and Qdrant indexing.
    """

    def __init__(self, sm: Optional[SessionManager] = None, vdb: Optional[QdrantVectorDB] = None):
        self.sm = sm or SessionManager()
        self.vdb = vdb or QdrantVectorDB()
        self._embedding_model = None
        self.last_error = None

        # Ensure directories exist
        self.docs_root = DATA_DIR / "documents"
        self.categories = ["textbooks", "notes", "assignments", "reference", "uploaded"]
        for cat in self.categories:
            (self.docs_root / cat).mkdir(parents=True, exist_ok=True)

    def load(self):
        """Initialize DB engine and connect Qdrant."""
        self.sm.load()
        self.vdb.connect()
        self.vdb.create_collection_if_not_exists(vector_size=384)  # Standard for all-MiniLM-L6-v2

    def _lazy_load_embedding_model(self):
        """Lazy-load the sentence transformer model for indexing embeddings."""
        if self._embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._embedding_model = SentenceTransformer(
                    nlp_cfg.EMBEDDING_MODEL, device="cpu", local_files_only=True
                )
                logger.info(f"Loaded sentence transformer model: {nlp_cfg.EMBEDDING_MODEL}")
            except ImportError:
                logger.error(
                    "sentence-transformers not installed. Ingestion cannot index vector embeddings."
                )
                raise ImportError("Run 'pip install sentence-transformers' to enable indexing.")

    def compute_checksum(self, filepath: Path) -> str:
        """Compute MD5 checksum of a file to check for content modifications."""
        hasher = hashlib.md5()
        with open(filepath, "rb") as f:
            buf = f.read(65536)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(65536)
        return hasher.hexdigest()

    def parse_txt(self, filepath: Path) -> List[Dict[str, Any]]:
        """Parse raw text file. Returns list of parsed page/paragraph contents."""
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

        # Treat entire txt file as a single page (Page 1)
        return [{"page_number": 1, "text": text}]

    def parse_pdf(self, filepath: Path) -> List[Dict[str, Any]]:
        from sentio.ingestion.ocr import pdf_pages

        return pdf_pages(filepath)

    def parse_docx(self, filepath: Path) -> List[Dict[str, Any]]:
        """Parse Word DOCX document. Returns list of paragraph blocks."""
        import docx

        doc = docx.Document(filepath)
        parsed_blocks = []

        # docx has no strict pages, group paragraphs into pseudo-pages/chapters if needed
        # for simplicity, we parse paragraphs and treat them as sequential text blocks
        full_text = "\n".join([p.text for p in doc.paragraphs])
        parsed_blocks.append({"page_number": 1, "text": full_text})

        return parsed_blocks

    def chunk_text(self, text: str, chunk_size: int = 500, chunk_overlap: int = 100) -> List[str]:
        """Perform sliding character-window chunking on text."""
        chunks = []
        if not text.strip():
            return chunks

        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunks.append(text[start:end])
            if end == len(text):
                break
            start += chunk_size - chunk_overlap
        return chunks

    def process_file(
        self,
        filepath,
        category,
        subject=None,
        student_id=None,
        publisher=None,
        force=False,
    ):
        checkpoint("waiting for ingestion")
        while not _ingestion_lock.acquire(timeout=0.1):
            checkpoint()
        try:
            checkpoint()
            return self._process_file(filepath, category, subject, student_id, publisher, force)
        finally:
            _ingestion_lock.release()

    def _process_file(
        self,
        filepath: Path,
        category: str,
        subject: Optional[str] = None,
        student_id: Optional[str] = None,
        publisher=None,
        force=False,
    ) -> bool:
        """Parse, chunk, index, and save a document if it is new or modified."""
        filename = filepath.name
        self.last_error = None
        suffix = filepath.suffix.lower()
        checksum = self.compute_checksum(filepath)
        mtime = os.path.getmtime(filepath)
        # Use student_id in doc_id to make it unique per student
        doc_id = hashlib.md5(
            f"{student_id or 'stu_001'}::{category}::{filename}".encode()
        ).hexdigest()[:12]

        # Check if already registered
        existing_doc = self.sm.get_document_by_filename(
            filename, student_id=student_id or "stu_001", category=category
        )

        if existing_doc:
            if (
                not force
                and existing_doc["checksum"] == checksum
                and existing_doc["status"] == "indexed"
            ):
                logger.debug(f"Document {filename} is already indexed and unmodified. Skipping.")
                return False
            else:
                logger.info(f"Document {filename} modified or failed. Re-indexing.")

        # Register document as indexing
        doc_record = {
            "id": doc_id,
            "student_id": student_id or "stu_001",
            "filename": filename,
            "file_type": suffix[1:].upper(),
            "category": category,
            "subject": subject or "general",
            "upload_date": time.time(),
            "last_modified": mtime,
            "chunk_count": 0,
            "embedding_count": 0,
            "status": "indexing",
            "last_indexed": None,
            "checksum": checksum,
        }

        chunks_to_save = []
        try:
            checkpoint("extracting document text")
            # 1. Parse text based on format
            if suffix == ".txt":
                pages = self.parse_txt(filepath)
            elif suffix == ".pdf":
                pages = self.parse_pdf(filepath)
            elif suffix == ".docx":
                pages = self.parse_docx(filepath)
            elif suffix in [".png", ".jpg", ".jpeg"]:
                from sentio.ingestion.ocr import image_page

                pages = image_page(filepath)
            else:
                raise ValueError(f"Unsupported file format: {suffix}")

            if sum(len(p["text"]) for p in pages) > 2_000_000:
                raise ValueError(
                    "Extracted text exceeds 2 million characters. Split this document into smaller files."
                )
            methods = {p.get("extraction_method", "text") for p in pages}
            doc_record["extraction_method"] = (
                "mixed" if len(methods) > 1 else next(iter(methods), "text")
            )

            # 2. Chunk text and retain page numbers
            chunks_to_save = []
            chunk_texts = []
            chunk_metadata = []

            chunk_index = 0
            for page in pages:
                page_text = page["text"]
                page_chunks = self.chunk_text(page_text)
                for chunk_text in page_chunks:
                    checkpoint()
                    if chunk_index >= 2000:
                        raise ValueError(
                            "Document exceeds 2000 passages. Split it into smaller files."
                        )
                    hex_hash = hashlib.md5(
                        f"{doc_id}::{checksum}::p{page['page_number']}::c{chunk_index}".encode()
                    ).hexdigest()
                    chunk_id = str(uuid.UUID(hex=hex_hash))

                    chunks_to_save.append(
                        {
                            "chunk_id": chunk_id,
                            "document_id": doc_id,
                            "page_number": page["page_number"],
                            "chunk_index": chunk_index,
                            "text_content": chunk_text,
                        }
                    )

                    chunk_texts.append(chunk_text)
                    chunk_metadata.append(
                        {
                            "student_id": student_id or "stu_001",
                            "document_id": doc_id,
                            "document": filename,
                            "page": page["page_number"],
                            "chunk_id": chunk_id,
                            "subject": subject or "general",
                            "category": category,
                            "source_type": suffix[1:].upper(),
                        }
                    )
                    chunk_index += 1

            if not chunks_to_save:
                self.last_error = (
                    "No usable text found. Upload a readable document or clearer scan."
                )
                logger.warning(f"No text extracted from document {filename}.")
                doc_record["status"] = "failed"
                doc_record["last_indexed"] = time.time()
                if not existing_doc:
                    self.sm.register_document(doc_record)
                return False

            # Text is usable for BM25 even when the embedding provider is offline.
            embedding_count = 0
            try:
                checkpoint("preparing semantic index")
                self._lazy_load_embedding_model()
                embeddings = self._embedding_model.encode(
                    chunk_texts, batch_size=32, show_progress_bar=False
                ).tolist()
                checkpoint("staging document vectors")
                if self.vdb.index_chunks(
                    ids=[c["chunk_id"] for c in chunks_to_save],
                    vectors=embeddings,
                    payloads=chunk_metadata,
                ):
                    embedding_count = len(chunks_to_save)
            except WorkCancelled:
                raise
            except Exception as exc:
                logger.warning(
                    "Vector indexing unavailable for %s; using keyword search: %s", filename, exc
                )

            # Update document registry status to indexed
            doc_record["status"] = "indexed"
            doc_record["chunk_count"] = len(chunks_to_save)
            doc_record["embedding_count"] = embedding_count
            doc_record["last_indexed"] = time.time()
            checkpoint("saving document")
            repository = DocumentRepository(self.sm.persister)
            old_chunks = self.sm.get_document_chunks(doc_id) if existing_doc else []
            publish(
                lambda: (
                    publisher(doc_record, chunks_to_save, old_chunks)
                    if publisher
                    else repository.replace(doc_record, chunks_to_save)
                )
            )
            if not publisher:
                self.vdb.delete_chunk_points(
                    [
                        c["chunk_id"]
                        for c in old_chunks
                        if c["chunk_id"] not in {n["chunk_id"] for n in chunks_to_save}
                    ]
                )

            logger.info(f"Indexed document: {filename} ({len(chunks_to_save)} chunks)")
            return True

        except WorkCancelled:
            self._discard_staged(doc_id, chunks_to_save)
            raise
        except Exception as e:
            self._discard_staged(doc_id, chunks_to_save)
            self.last_error = str(e)
            logger.error(f"Failed to process document {filename}: {e}")
            doc_record["status"] = "failed"
            doc_record["last_indexed"] = time.time()
            if not existing_doc:
                self.sm.register_document(doc_record)
            return False

    def _discard_staged(self, document_id, chunks):
        from sqlalchemy import text

        try:
            with self.sm.persister._engine.connect() as connection:
                active = set(
                    connection.execute(
                        text("SELECT chunk_id FROM document_chunks WHERE document_id=:id"),
                        {"id": document_id},
                    ).scalars()
                )
            self.vdb.delete_chunk_points(
                [c["chunk_id"] for c in chunks if c["chunk_id"] not in active]
            )
        except Exception:
            logger.warning(
                "Inactive vector cleanup deferred; current SQL evidence remains authoritative."
            )

    def scan_and_sync(self, subject_map: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Scan document root folders, index new/modified files,
        and prune deleted files from the registry and vector store.
        """
        t_start = time.perf_counter()
        scanned_files = set()
        indexed_count = failed_count = skipped_count = deleted_count = 0
        # Support both legacy category folders and current owner/category folders.
        folders = [(self.docs_root / cat, cat, "stu_001") for cat in self.categories]
        if self.docs_root.exists():
            folders += [
                (owner / cat, cat, owner.name)
                for owner in self.docs_root.iterdir()
                if owner.is_dir() and owner.name not in self.categories
                for cat in self.categories
            ]
        for folder, category, owner in folders:
            if not folder.exists():
                continue
            for path in folder.iterdir():
                if not path.is_file() or path.suffix.lower() not in {".txt", ".pdf", ".docx"}:
                    continue
                scanned_files.add((owner, category, path.name))
                existing = self.sm.get_document_by_filename(path.name, owner, category)
                subject = (subject_map or {}).get(path.name) or (existing or {}).get("subject")
                if (
                    existing
                    and existing["status"] == "indexed"
                    and existing["checksum"] == self.compute_checksum(path)
                ):
                    skipped_count += 1
                elif self.process_file(path, category, subject, owner):
                    indexed_count += 1
                else:
                    failed_count += 1
        for doc in self.sm.list_documents():
            key = (doc.get("student_id") or "stu_001", doc["category"], doc["filename"])
            if key not in scanned_files:
                self.sm.delete_document(doc["id"])
                self.vdb.delete_document_points(doc["id"])
                deleted_count += 1

        duration = time.perf_counter() - t_start
        logger.info(
            f"Scan complete in {duration:.2f}s. Indexed: {indexed_count}, Skipped: {skipped_count}, Deleted: {deleted_count}, Failed: {failed_count}"
        )

        return {
            "indexed_count": indexed_count,
            "skipped_count": skipped_count,
            "deleted_count": deleted_count,
            "failed_count": failed_count,
            "duration_sec": round(duration, 3),
        }


if __name__ == "__main__":
    # Smoke test for Ingestion Pipeline
    logging.basicConfig(level=logging.INFO)
    pipeline = DocumentIngestionPipeline()
    pipeline.load()

    # Write a trial txt file
    cat_folder = DATA_DIR / "documents" / "notes"
    cat_folder.mkdir(parents=True, exist_ok=True)
    trial_txt = cat_folder / "test_notes.txt"
    with open(trial_txt, "w", encoding="utf-8") as f:
        f.write(
            "Calculus limits describe behavior of a function near a point. The limit of 1/x as x approaches infinity is 0."
        )

    print("Running document ingestion pipeline scan...")
    report = pipeline.scan_and_sync()
    print(f"Report: {report}")

    # Verify DB contains document
    docs = pipeline.sm.list_documents()
    print(f"Documents registered: {[d['filename'] for d in docs]}")
    assert any(d["filename"] == "test_notes.txt" for d in docs), "Document not registered"

    # Prune trial file
    os.remove(trial_txt)
    print("Running pruner sync scan...")
    report = pipeline.scan_and_sync()
    print(f"Sync Report: {report}")
    docs = pipeline.sm.list_documents()
    print(f"Documents registered after prune: {docs}")
    assert not any(d["filename"] == "test_notes.txt" for d in docs), "Pruning failed"
    print("Ingestion smoke test passed successfully!")
