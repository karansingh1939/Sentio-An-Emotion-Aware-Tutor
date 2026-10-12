from sqlalchemy import text

from sentio.config import session_cfg
from sentio.session.models import EmotionEvent
from tests.test_grounded_study_loop import study as study_fixture

study = study_fixture


def test_account_deletion_removes_study_artifacts_files_and_cached_sessions(study):
    s = study
    s.sm.save_quiz(
        "private-quiz",
        s.a,
        s.session_id,
        "Private quiz",
        [
            {
                "question_text": "Force?",
                "question_type": "short_answer",
                "correct_answer": "Net force",
                "explanation": "Newton",
                "difficulty": "beginner",
                "topic": "forces",
            }
        ],
    )
    s.sm.save_flashcard_deck("private-deck", s.a, "Private deck")
    s.sm.save_whiteboard("private-board", s.a, s.session_id, "Private", '{"shapes": []}')
    response = s.client.delete(s.prefix + f"/student/{s.a}/data", headers=s.headers)
    assert response.status_code == 200, response.text
    with s.sm.persister._engine.connect() as conn:
        for table in ["documents", "quizzes", "flashcard_decks", "whiteboards"]:
            assert (
                conn.execute(
                    text(f"SELECT COUNT(*) FROM {table} WHERE student_id = :id"), {"id": s.a}
                ).scalar_one()
                == 0
            )
        assert conn.execute(text("SELECT COUNT(*) FROM document_chunks")).scalar_one() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM quiz_questions")).scalar_one() == 0
    assert s.session_id not in s.sm._sessions
    assert not (s.tmp_path / "data/documents" / s.a).exists()
    assert s.sm.persister.auth_repo.get_account_by_student_id(s.b) is not None


def test_export_includes_document_and_study_artifact_inventory(study):
    s = study
    response = s.client.get(s.prefix + f"/student/{s.a}/export", headers=s.headers)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert {
        "documents",
        "document_chunks",
        "quizzes",
        "quiz_questions",
        "flashcard_decks",
        "whiteboards",
    } <= data.keys()
    assert len(data["documents"]) == 2
    assert "password_hash" not in data["account"][0]


def test_telemetry_deletion_clears_cached_and_exported_emotions(study):
    s = study
    session = s.sm.get_or_raise(s.session_id)
    session.emotion_timeline.record(EmotionEvent(1, "sad", "struggling", 0.8, "simplify"))
    s.sm.persister.save_session(session)
    s.sm._save_emotion_log(session)
    log = session_cfg.EMOTION_LOG_PATH / f"{s.session_id}_emotions.json"
    assert log.exists()
    response = s.client.delete(s.prefix + f"/student/{s.a}/telemetry", headers=s.headers)
    assert response.status_code == 200, response.text
    assert not log.exists()
    assert session.emotion_timeline.state_distribution() == {}
    assert s.sm.persister.load_session_data(s.session_id)["emotion_summary"]["distribution"] == {}


def test_failed_account_transaction_preserves_document_files_and_account(study, monkeypatch):
    s = study
    from unittest.mock import Mock

    before = {
        path: path.read_bytes() for path in (s.tmp_path / "data/documents" / s.a).rglob("*.txt")
    }
    monkeypatch.setattr(
        s.sm.persister.auth_repo, "delete_account", Mock(side_effect=RuntimeError("disk error"))
    )
    response = s.client.delete(s.prefix + f"/student/{s.a}/data", headers=s.headers)
    assert response.status_code == 500
    assert s.sm.persister.auth_repo.get_account_by_student_id(s.a) is not None
    assert all(path.exists() and path.read_bytes() == content for path, content in before.items())
    assert s.sm.list_documents(student_id=s.a)


def test_committed_account_cleanup_recovers_after_filesystem_failure(study):
    from unittest.mock import patch

    from sentio.maintenance.account_cleanup import AccountCleanup

    s = study
    with patch(
        "sentio.maintenance.account_cleanup.shutil.rmtree", side_effect=PermissionError("locked")
    ):
        response = s.client.delete(s.prefix + f"/student/{s.a}/data", headers=s.headers)
    assert response.status_code == 200, response.text
    assert response.json()["cleanup_pending"] is True
    assert s.sm.persister.auth_repo.get_account_by_student_id(s.a) is None
    assert s.session_id not in s.sm._sessions
    assert (s.tmp_path / "data/documents" / s.a).exists()
    service = AccountCleanup(
        s.sm.persister,
        s.kb.vdb,
        s.tmp_path / "data/documents",
        session_cfg.SESSION_LOG_PATH,
        session_cfg.EMOTION_LOG_PATH,
    )
    service.recover()
    assert not (s.tmp_path / "data/documents" / s.a).exists()
    assert s.sm.persister.auth_repo.get_account_by_student_id(s.b) is not None
    with s.sm.persister._engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM account_cleanup")).scalar() == 0
