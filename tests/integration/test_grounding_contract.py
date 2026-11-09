from types import SimpleNamespace

import pytest

from sentio.ai.grounding import GROUNDING_RULES, validate_references
from sentio.ai.prompts import PromptBuilder


def test_grounded_prompt_explicitly_requires_abstention_and_treats_source_as_data():
    source = SimpleNamespace(
        has_content=lambda: True,
        is_rag=True,
        rag_context="[notes.txt Page 1]\nNet force changes motion.",
    )
    prompt = PromptBuilder().build_system_prompt(
        "physics", "motion", "beginner", "neutral", "standard", "clear", source
    )
    assert GROUNDING_RULES in prompt
    assert "do not contain enough information" in prompt
    assert "untrusted data" in prompt


def test_citation_references_must_be_from_actual_retrieved_passages():
    source = SimpleNamespace(is_rag=True, source_citations=[{"filename": "notes.txt", "page": 1}])
    validate_references("Net force changes motion [notes.txt Page 1].", source)
    validate_references(
        "These notes do not contain enough information to answer that question.", source
    )
    with pytest.raises(ValueError, match="outside"):
        validate_references("A claim [secret.txt Page 2].", source)
    with pytest.raises(ValueError, match="cite"):
        validate_references("An explanation without a source.", source)


def test_generic_words_and_weak_semantic_match_are_not_evidence():
    from sentio.rag.evidence_policy import has_relevance_signal

    assert not has_relevance_signal(
        "What is the boiling point of ethanol?", "The law is about motion of an object.", 0.1
    )
    assert has_relevance_signal(
        "What changes uniform motion?", "An external force changes uniform motion.", 0.1
    )
    assert has_relevance_signal(
        "Which influence alters a moving body's velocity?",
        "A net force changes uniform motion.",
        0.65,
    )


def test_selected_notes_without_relevant_evidence_do_not_call_provider(monkeypatch):
    from fastapi.testclient import TestClient

    from sentio.api.app import agent, app
    from tests.helpers import login_student

    with TestClient(app) as client:
        login_student(client)
        uploaded = client.post(
            "/api/v1/documents/upload",
            files={"file": ("motion.txt", b"The law is about motion of an object.", "text/plain")},
        )
        assert uploaded.status_code == 201, uploaded.text
        sid = client.post(
            "/api/v1/sessions",
            json={
                "student_id": "ignored",
                "subject": "physics",
                "topic": "motion",
                "difficulty": "beginner",
                "metadata": {"document_id": uploaded.json()["document_id"]},
            },
        ).json()["session_id"]
        monkeypatch.setattr(agent.kb.vdb, "search", lambda *args, **kwargs: [])

        def forbidden(**kwargs):
            raise AssertionError("Insufficient selected notes must not call generation")

        monkeypatch.setattr(agent.nlp._backend, "complete", forbidden)
        result = client.post(
            f"/api/v1/sessions/{sid}/chat/stream",
            json={
                "message": "What is the boiling point of ethanol?",
                "request_id": "unsupported-test",
            },
        )
        assert "event: complete" in result.text, result.text
        assert "notes don't cover that question" in result.text
        assert "78.37" not in result.text
