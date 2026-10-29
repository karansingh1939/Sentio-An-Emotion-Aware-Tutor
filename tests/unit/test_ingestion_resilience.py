from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from sentio.ingestion.pipeline import DocumentIngestionPipeline
from sentio.rag.knowledge_base import KnowledgeBase
from sentio.repositories.documents import DocumentRepository
from sentio.session.manager import SessionManager


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    from sentio.config import session_cfg

    monkeypatch.setattr(
        session_cfg, "DB_URL", "sqlite:///" + (tmp_path / "ingestion.db").as_posix()
    )
    manager = SessionManager()
    manager.load()
    vectors = Mock()
    vectors.index_chunks.return_value = True
    pipeline = DocumentIngestionPipeline(sm=manager, vdb=vectors)
    pipeline._embedding_model = SimpleNamespace(
        encode=lambda texts, **kw: np.ones((len(texts), 384))
    )
    yield pipeline
    manager.persister._engine.dispose()


def test_same_filename_in_different_categories_is_indexed_independently(pipeline, tmp_path):
    path = tmp_path / "guide.txt"
    path.write_text("Newton's laws describe forces and motion.")
    assert pipeline.process_file(path, "notes", "physics", "owner")
    assert pipeline.process_file(path, "textbooks", "physics", "owner")
    assert len(pipeline.sm.list_documents(student_id="owner")) == 2


def test_embedding_failure_leaves_searchable_text(pipeline, tmp_path):
    path = tmp_path / "offline.txt"
    path.write_text("Newton's First Law describes uniform motion and external forces.")
    pipeline._embedding_model.encode = Mock(side_effect=RuntimeError("offline"))
    assert pipeline.process_file(path, "notes", "physics", "owner")
    document = pipeline.sm.list_documents(student_id="owner")[0]
    assert document["status"] == "indexed"
    assert document["embedding_count"] == 0
    assert pipeline.sm.get_document_chunks(document["id"])
    retriever = Mock(_model=None)
    kb = KnowledgeBase(
        doc_repo=DocumentRepository(pipeline.sm.persister), vdb=pipeline.vdb, retriever=retriever
    )
    retrieved = kb.retrieve(
        "physics",
        "Newton's First Law",
        "beginner",
        "neutral",
        query="Newton's First Law",
        student_id="owner",
        document_id=document["id"],
    )
    assert retrieved.is_rag
    retriever._load_model.assert_not_called()


def test_failed_replacement_keeps_original_document(pipeline, tmp_path):
    path = tmp_path / "guide.txt"
    path.write_text("An original explanation of Newton's laws.")
    assert pipeline.process_file(path, "notes", "physics", "owner")
    before = pipeline.sm.list_documents(student_id="owner")[0]
    chunks = pipeline.sm.get_document_chunks(before["id"])
    path.write_text("")
    assert not pipeline.process_file(path, "notes", "physics", "owner")
    assert pipeline.sm.list_documents(student_id="owner")[0] == before
    assert pipeline.sm.get_document_chunks(before["id"]) == chunks


def test_sync_scans_owned_directories_and_prunes_exact_identity(pipeline, tmp_path):
    pipeline.docs_root = tmp_path / "documents"
    for owner in ["alice", "bob"]:
        folder = pipeline.docs_root / owner / "notes"
        folder.mkdir(parents=True)
        (folder / "guide.txt").write_text("Newton describes forces and motion.")
    report = pipeline.scan_and_sync()
    assert report["indexed_count"] == 2
    assert len(pipeline.sm.list_documents(student_id="alice")) == 1
    assert len(pipeline.sm.list_documents(student_id="bob")) == 1

    (pipeline.docs_root / "alice" / "notes" / "guide.txt").unlink()
    report = pipeline.scan_and_sync()
    assert report["deleted_count"] == 1
    assert not pipeline.sm.list_documents(student_id="alice")
    assert len(pipeline.sm.list_documents(student_id="bob")) == 1


@pytest.mark.parametrize("suffix", [".png", ".jpg", ".jpeg", ".PNG"])
def test_sync_keeps_images_when_ocr_is_unavailable(pipeline, tmp_path, monkeypatch, suffix):
    from sentio.ingestion.ocr import ExtractionError

    pipeline.docs_root = tmp_path / "documents"
    path = pipeline.docs_root / "owner" / "notes" / ("scan" + suffix)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"original image fixture")
    monkeypatch.setattr(
        "sentio.ingestion.ocr.image_page",
        lambda _: [{"page_number": 1, "text": "Force changes motion.", "extraction_method": "ocr"}],
    )
    assert pipeline.process_file(path, "notes", "physics", "owner")
    document = pipeline.sm.list_documents(student_id="owner")[0]
    chunks = pipeline.sm.get_document_chunks(document["id"])

    def unavailable(_):
        raise ExtractionError("OCR unavailable")

    monkeypatch.setattr("sentio.ingestion.ocr.image_page", unavailable)
    report = pipeline.scan_and_sync()
    assert report["deleted_count"] == 0
    assert report["skipped_count"] == 1
    path.write_bytes(b"changed image fixture")
    report = pipeline.scan_and_sync()
    assert report["failed_count"] == 1
    assert report["deleted_count"] == 0
    assert pipeline.sm.list_documents(student_id="owner") == [document]
    assert pipeline.sm.get_document_chunks(document["id"]) == chunks
    pipeline.vdb.delete_document_points.assert_not_called()


def test_ocr_provenance_and_page_numbers_survive_persistence(pipeline, tmp_path, monkeypatch):
    path = tmp_path / "scan.pdf"
    path.write_bytes(b"fixture; extraction is injected")
    monkeypatch.setattr(
        pipeline,
        "parse_pdf",
        lambda _: [
            {
                "page_number": 1,
                "text": "A native text page about force.",
                "extraction_method": "text",
            },
            {
                "page_number": 2,
                "text": "An OCR page explaining acceleration.",
                "extraction_method": "ocr",
            },
        ],
    )
    assert pipeline.process_file(path, "notes", "physics", "owner")
    document = pipeline.sm.list_documents(student_id="owner")[0]
    assert document["extraction_method"] == "mixed"
    assert [c["page_number"] for c in pipeline.sm.get_document_chunks(document["id"])] == [1, 2]
