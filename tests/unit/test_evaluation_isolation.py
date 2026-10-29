from pathlib import Path

from sentio.config import session_cfg
from sentio.evaluation.runner import KeywordOnly, isolated_runtime


def test_evaluation_uses_registered_owner_and_selected_documents(tmp_path):
    original = session_cfg.DB_URL
    source = tmp_path / "owned.txt"
    source.write_text("A capacitor stores electrical energy in an electric field.")
    with isolated_runtime(KeywordOnly()) as (sm, pipeline, kb, owner):
        assert session_cfg.DB_URL != original
        assert pipeline.process_file(source, "reference", "general", owner)
        document = sm.list_documents(owner)[0]
        result = kb.retrieve(
            "general",
            "evaluation",
            "beginner",
            "neutral",
            query="capacitor electrical energy",
            student_id=owner,
            document_id=[document["id"]],
        )
        assert result.source_citations[0]["filename"] == "owned.txt"
        foreign = sm.persister.auth_service.register_student(
            "foreign@example.test", "Evaluation-2026!"
        )
        denied = kb.retrieve(
            "general",
            "evaluation",
            "beginner",
            "neutral",
            query="capacitor electrical energy",
            student_id=foreign.student_id,
            document_id=[document["id"]],
        )
        assert not denied.source_citations
        database = Path(sm.persister._engine.url.database)
    assert session_cfg.DB_URL == original
    assert not database.exists()
