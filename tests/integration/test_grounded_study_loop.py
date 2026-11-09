"""Real auth, upload parsing, scoped BM25 retrieval, grading and temporary SQLite.

Only ML/embedding and vector-service calls are replaced; captured prompts prove
which source content reaches generation, not the quality of a real LLM's output.
"""

import importlib
import json
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from sentio.config import api_cfg, mastery_cfg, session_cfg
from sentio.ingestion.pipeline import DocumentIngestionPipeline
from sentio.rag.knowledge_base import KnowledgeBase
from sentio.repositories.documents import DocumentRepository
from sentio.session.manager import SessionManager

FACT = "Newton's First Law states that an object remains at rest or in uniform motion unless acted upon by an external net force."
OTHER = "Newton's First Law private Document B marker: purple pineapple."
TOPIC = "Newton's First Law"


@pytest.fixture
def study(tmp_path, monkeypatch):
    with patch.dict(
        sys.modules,
        {"sentio.emotion.detector": SimpleNamespace(EmotionDetector=Mock(), EmotionResult=Mock())},
    ):
        with patch("sentio.api.app.setup_logging"):
            api = importlib.import_module("sentio.api.app")
    db_url = "sqlite:///" + (tmp_path / "study.db").as_posix()
    monkeypatch.setattr(session_cfg, "DB_URL", db_url)
    monkeypatch.setattr(session_cfg, "SESSION_LOG_PATH", tmp_path / "sessions")
    monkeypatch.setattr(session_cfg, "EMOTION_LOG_PATH", tmp_path / "emotions")
    monkeypatch.setattr(api_cfg, "API_SECRET", "grounding-test-only-secret-123456789")
    monkeypatch.setattr("sentio.api.routes.documents.BASE_DIR", tmp_path)
    monkeypatch.setattr("sentio.api.routes.privacy.BASE_DIR", tmp_path)
    monkeypatch.setattr("sentio.ingestion.pipeline.DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(api.RateLimiter, "allow", lambda self: True)
    sm = SessionManager()
    sm.load()
    vdb = Mock()
    vdb.is_available.return_value = False
    vdb.index_chunks.return_value = True
    retriever = Mock(_model=None)
    kb = KnowledgeBase(doc_repo=DocumentRepository(sm.persister), vdb=vdb, retriever=retriever)
    backend = Mock()
    question = dict(
        question_text="What changes an object's uniform motion?",
        question_type="multiple_choice",
        options=["An external net force", "Its color", "Nothing", "Its name"],
        correct_answer="An external net force",
        explanation=FACT,
        difficulty="beginner",
        topic="model invented topic",
    )
    backend.complete.return_value = (
        json.dumps({"title": "Newton quiz", "questions": [question]}),
        50,
    )
    monkeypatch.setattr(api.agent, "sm", sm)
    monkeypatch.setattr(api.agent, "kb", kb)
    monkeypatch.setattr(api.agent, "nlp", SimpleNamespace(_backend=backend, clear_history=Mock()))
    monkeypatch.setattr(api.agent, "_loaded", True)
    monkeypatch.setattr(
        DocumentIngestionPipeline,
        "_lazy_load_embedding_model",
        lambda self: setattr(
            self,
            "_embedding_model",
            SimpleNamespace(encode=lambda texts, **kwargs: np.ones((len(texts), 384))),
        ),
    )
    client = TestClient(api.app)
    prefix = api.PREFIX

    def register(name):
        body = {"email": name + "@example.com", "password": "StrongPassword123!"}
        response = client.post(prefix + "/auth/register", json=body)
        assert response.status_code == 201, response.text
        sid = response.json()["student_id"]
        response = client.post(prefix + "/auth/login", json=body)
        assert response.status_code == 200, response.text
        return sid, {"Authorization": "Bearer " + response.json()["access_token"]}

    a, headers = register("a")
    b, headers_b = register("b")

    def upload(filename, content):
        response = client.post(
            prefix + "/documents/upload?subject=physics",
            headers=headers,
            files={"file": (filename, content.encode(), "text/plain")},
        )
        assert response.status_code == 201, response.text
        return sm.get_document_by_filename(filename, student_id=a)["id"]

    doc_a = upload("newton.txt", FACT)
    doc_b = upload("other.txt", OTHER)
    response = client.post(
        prefix + "/sessions",
        headers=headers,
        json={
            "student_id": a,
            "subject": "physics",
            "topic": TOPIC,
            "difficulty": "beginner",
            "metadata": {"document_id": doc_a},
        },
    )
    assert response.status_code == 201, response.text
    session_id = response.json()["session_id"]

    def generate(**overrides):
        body = dict(
            student_id=b,
            session_id=session_id,
            subject="physics",
            topic=TOPIC,
            difficulty="beginner",
            num_questions=1,
        )
        body.update(overrides)
        return client.post(prefix + "/quizzes/generate", headers=headers, json=body)

    yield SimpleNamespace(**locals())
    client.close()
    sm.persister._engine.dispose()


def test_selected_document_reaches_generation_without_other_document(study):
    s = study
    s.sm.record_quiz_attempt(
        s.session_id, correct=False, topic="other topic", question_preview=OTHER
    )
    response = s.generate()
    assert response.status_code == 200, response.text
    prompt = s.backend.complete.call_args.kwargs["system_prompt"]
    assert FACT in prompt
    assert OTHER not in prompt
    quiz = s.sm.get_quiz(response.json()["quiz_id"])
    assert quiz["student_id"] == s.a  # forged body identity is ignored
    assert quiz["questions"][0]["topic"] == TOPIC


def test_switching_document_changes_generation_context(study):
    s = study
    response = s.client.post(
        s.prefix + f"/sessions/{s.session_id}/grounding",
        headers=s.headers,
        json={"document_id": s.doc_b},
    )
    assert response.status_code == 200
    study.client.app.state.agent.nlp.clear_history.assert_called_once_with(study.session_id)
    assert s.generate().status_code == 200
    prompt = s.backend.complete.call_args.kwargs["system_prompt"]
    assert OTHER in prompt
    assert FACT not in prompt


def test_student_cannot_select_or_generate_from_another_students_document(study):
    s = study
    response = s.client.post(
        s.prefix + "/sessions",
        headers=s.headers_b,
        json={
            "student_id": s.b,
            "subject": "physics",
            "topic": TOPIC,
            "metadata": {"document_id": s.doc_a},
        },
    )
    assert response.status_code == 403
    session_b = s.sm.create_session(s.b, "physics", TOPIC, metadata={"document_id": s.doc_a})
    # Also reject stale/invalid scope already stored in a session.
    response = s.client.post(
        s.prefix + "/quizzes/generate",
        headers=s.headers_b,
        json={
            "student_id": s.a,
            "session_id": session_b.session_id,
            "subject": "physics",
            "topic": TOPIC,
        },
    )
    assert response.status_code == 403
    s.backend.complete.assert_not_called()


@pytest.mark.parametrize(
    "question_type,answer,options",
    [
        (
            "multiple_choice",
            "An external net force",
            ["An external net force", "Nothing", "Color", "Name"],
        ),
        ("true_false", "True", ["True", "False"]),
        ("fill_in_the_blank", "force", None),
        ("short_answer", "An external net force", None),
    ],
)
def test_answer_grading_topic_mastery_persists_and_is_readable(
    study, question_type, answer, options
):
    s = study
    s.question.update(question_type=question_type, correct_answer=answer, options=options)
    s.backend.complete.return_value = (
        json.dumps({"title": "Newton quiz", "questions": [s.question]}),
        50,
    )
    generated = s.generate(difficulty="advanced")
    assert generated.status_code == 200, generated.text
    s.backend.complete.return_value = ("Good work.", 3)
    response = s.client.post(
        s.prefix + f"/quizzes/{generated.json()['quiz_id']}/submit",
        headers=s.headers,
        json={"session_id": s.session_id, "answers": {"0": answer}},
    )
    assert response.status_code == 200, response.text
    assert response.json()["total_score"] == 1.0
    # Read with a separate DB connection, not the in-memory session tracker.
    engine = create_engine(s.db_url)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT topic_id, mastery_score, attempts_count FROM student_knowledge WHERE student_id=:sid"
                ),
                {"sid": s.a},
            ).one()
            assert row.topic_id == TOPIC
            assert row.mastery_score == pytest.approx(
                mastery_cfg.SMOOTHING_FACTOR * mastery_cfg.DIFFICULTY_WEIGHTS["advanced"]
            )
            assert row.attempts_count == 1
            assert (
                conn.execute(
                    text("SELECT correct FROM quiz_attempts WHERE student_id=:sid"), {"sid": s.a}
                ).scalar_one()
                == 1
            )
    finally:
        engine.dispose()
    memory = s.client.get(s.prefix + f"/students/{s.a}/memory", headers=s.headers)
    assert memory.status_code == 200
    assert any(
        t["topic_id"] == TOPIC and t["mastery_score"] == row.mastery_score
        for t in memory.json()["weak_topics"]
    )


def test_no_match_does_not_call_model_or_save_quiz(study):
    s = study
    response = s.generate(topic="photosynthesis chlorophyll")
    assert response.status_code == 422, response.text
    assert "relevant" in response.json()["detail"].lower()
    s.backend.complete.assert_not_called()
    with s.sm.persister._engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM quizzes")).scalar_one() == 0


@pytest.mark.parametrize("scope", ["all", "list"])
def test_vector_scope_and_keyword_scope_preserve_student(study, scope):
    s = study
    selected = "all" if scope == "all" else [s.doc_a]
    s.sm.get_or_raise(s.session_id).metadata["document_id"] = selected
    s.sm.persister.save_session(s.sm.get_or_raise(s.session_id))
    s.retriever._model = SimpleNamespace(encode=lambda *args, **kwargs: np.ones((1, 384)))
    s.vdb.is_available.return_value = True
    s.vdb.search.return_value = []
    assert s.generate().status_code == 200
    expected = {"student_id": s.a}
    if scope == "list":
        expected["document_id"] = [s.doc_a]
    assert s.vdb.search.call_args.kwargs["filter_payload"] == expected
    prompt = s.backend.complete.call_args.kwargs["system_prompt"]
    assert FACT in prompt
    assert (OTHER in prompt) == (scope == "all")


def test_sessions_without_notes_cannot_make_ungrounded_quizzes(study):
    s = study
    s.sm.get_or_raise(s.session_id).metadata["document_id"] = "none"
    s.sm.persister.save_session(s.sm.get_or_raise(s.session_id))
    response = s.generate()
    assert response.status_code in (400, 422), response.text
    assert "Choose notes" in response.text
    s.backend.complete.assert_not_called()
