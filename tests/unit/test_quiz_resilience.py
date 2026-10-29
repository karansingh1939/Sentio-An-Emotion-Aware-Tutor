"""Quiz results survive provider outages and retries without corrupting progress."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError
from sqlalchemy import text

from sentio.ai.structured_parser import QuizQuestion
from sentio.config import api_cfg, session_cfg
from sentio.quiz.service import QuizService
from sentio.repositories.quizzes import QuizRepository
from sentio.session.manager import SessionManager
from sentio.shared.exceptions import LLMServiceUnavailableError


@pytest.fixture
def quiz(tmp_path, monkeypatch):
    monkeypatch.setattr(session_cfg, "DB_URL", "sqlite:///" + (tmp_path / "quiz.db").as_posix())
    monkeypatch.setattr(session_cfg, "SESSION_LOG_PATH", tmp_path / "sessions")
    monkeypatch.setattr(api_cfg, "API_SECRET", "quiz-regression-only-secret-123456789")
    sm = SessionManager()
    sm.load()
    sm.ensure_student_exists("quiz-student")
    session = sm.create_session("quiz-student", "physics", "forces", "beginner")
    question = dict(
        question_text="What changes uniform motion?",
        question_type="multiple_choice",
        options=["Net force", "Color", "Name", "Nothing"],
        correct_answer="Net force",
        explanation="An external net force changes motion.",
        difficulty="beginner",
        topic="forces",
    )
    sm.save_quiz("quiz-1", session.student_id, session.session_id, "Forces quiz", [question])
    backend = Mock()
    backend.complete.return_value = ("Great work understanding forces!", 12)
    service = QuizService(SimpleNamespace(sm=sm, nlp=SimpleNamespace(_backend=backend)))
    yield SimpleNamespace(
        sm=sm, session=session, backend=backend, service=service, question=question
    )
    sm.persister._engine.dispose()


def progress(quiz):
    with quiz.sm.persister._engine.connect() as conn:
        attempts = conn.execute(text("SELECT COUNT(*) FROM quiz_attempts")).scalar_one()
        mastery = conn.execute(
            text(
                "SELECT mastery_score FROM student_knowledge "
                "WHERE student_id = :student AND topic_id = :topic"
            ),
            {"student": quiz.session.student_id, "topic": "forces"},
        ).scalar_one_or_none()
    return attempts, mastery


def test_summary_provider_failure_still_returns_saved_quiz_grade(quiz):
    quiz.backend.complete.side_effect = RuntimeError("Provider unavailable")

    result = quiz.service.score_quiz("quiz-1", {0: "Net force"}, quiz.session.session_id)

    assert result["total_score"] == 1.0
    assert result["feedback"][0]["is_correct"] is True
    assert result["summary"].strip()
    assert progress(quiz)[0] == 1


def test_repeated_submission_does_not_duplicate_attempts_or_mastery(quiz):
    first = quiz.service.score_quiz("quiz-1", {0: "Net force"}, quiz.session.session_id)
    first_progress = progress(quiz)

    repeated = quiz.service.score_quiz("quiz-1", {0: "Net force"}, quiz.session.session_id)

    assert repeated == first
    assert progress(quiz) == first_progress


def test_committed_result_preserves_session_progress_after_restart(quiz):
    first = quiz.service.score_quiz("quiz-1", {0: "Net force"}, quiz.session.session_id)
    quiz.sm._sessions.clear()
    restored = quiz.sm.get_or_raise(quiz.session.session_id)
    assert restored.quiz_tracker.total_attempts == 1
    assert quiz.service.score_quiz("quiz-1", {0: "Net force"}, restored.session_id) == first
    assert progress(quiz)[0] == 1


def test_failed_commit_rolls_back_progress_and_can_be_retried(quiz, monkeypatch):
    original = QuizRepository.save_results
    monkeypatch.setattr(
        QuizRepository, "save_results", Mock(side_effect=RuntimeError("Disk error"))
    )
    with pytest.raises(RuntimeError, match="Disk error"):
        quiz.service.score_quiz("quiz-1", {0: "Net force"}, quiz.session.session_id)
    assert progress(quiz) == (0, None)
    assert quiz.session.quiz_tracker.total_attempts == 0
    monkeypatch.setattr(QuizRepository, "save_results", original)
    quiz.service.score_quiz("quiz-1", {0: "Net force"}, quiz.session.session_id)
    assert progress(quiz)[0] == 1


def test_short_answer_provider_failure_does_not_guess_a_grade(quiz):
    quiz.backend.complete.side_effect = RuntimeError("Offline")
    with pytest.raises(LLMServiceUnavailableError):
        quiz.service._grade_short_answer("What changes motion?", "Net force", "Not net force")


def test_short_answer_provider_cannot_return_out_of_range_score(quiz):
    quiz.backend.complete.return_value = ('{"is_correct": "false", "score": 9}', 5)
    with pytest.raises(LLMServiceUnavailableError):
        quiz.service._grade_short_answer("What changes motion?", "Net force", "Gravity")


def test_question_schema_rejects_null_correct_answer(quiz):
    with pytest.raises(ValidationError):
        QuizQuestion(**dict(quiz.question, correct_answer=None))


@pytest.mark.parametrize(
    "options,answer",
    [
        (None, "Net force"),
        (["Net force"], "Net force"),
        (["Color", "Name", "Nothing", "Mass"], "Net force"),
    ],
)
def test_question_schema_rejects_unusable_multiple_choice_options(quiz, options, answer):
    with pytest.raises(ValidationError):
        QuizQuestion(**dict(quiz.question, options=options, correct_answer=answer))
