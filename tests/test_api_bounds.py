from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from sentio.api.app import agent, app
from sentio.api.schemas import GenerateFlashcardsRequest, QuizGenerateRequest
from sentio.ingestion.pipeline import DocumentIngestionPipeline
from tests.helpers import login_student


@pytest.mark.parametrize(
    "model,body",
    [
        (
            QuizGenerateRequest,
            dict(
                student_id="a",
                session_id="s",
                subject="physics",
                topic="forces",
                num_questions=100000,
            ),
        ),
        (
            GenerateFlashcardsRequest,
            dict(student_id="a", deck_id="d", topic_id="forces", num_cards=100000),
        ),
    ],
)
def test_generation_counts_are_bounded(model, body):
    with pytest.raises(ValidationError):
        model(**body)


def test_upload_limit_preserves_previous_file(monkeypatch):
    from sentio.api.routes import documents

    agent.load()
    with TestClient(app) as client:
        sid = login_student(client)
        path = documents.BASE_DIR / "data/documents" / sid / "uploaded/notes.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"original")
        monkeypatch.setattr(documents, "MAX_UPLOAD_BYTES", 5, raising=False)
        response = client.post(
            "/api/v1/documents/upload", files={"file": ("notes.txt", b"oversized")}
        )
        assert response.status_code == 413
        assert path.read_bytes() == b"original"


def test_failed_upload_preserves_previous_file(monkeypatch):
    from sentio.api.routes import documents

    agent.load()
    with TestClient(app) as client:
        sid = login_student(client)
        path = documents.BASE_DIR / "data/documents" / sid / "uploaded/notes.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"original")
        monkeypatch.setattr(DocumentIngestionPipeline, "process_file", Mock(return_value=False))
        response = client.post(
            "/api/v1/documents/upload", files={"file": ("notes.txt", b"invalid replacement")}
        )
        assert response.status_code == 422
        assert path.read_bytes() == b"original"
