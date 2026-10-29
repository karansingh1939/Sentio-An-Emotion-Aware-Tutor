"""Quizzes API routes."""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ValidationError

from sentio.api.dependencies import (
    PREFIX,
    _verify_session_owner,
    _verify_student_owner,
    agent,
    quiz_service,
)
from sentio.api.schemas import QuizGenerateRequest, QuizRequest, QuizSubmitRequest
from sentio.auth.middleware import get_current_user
from sentio.jobs.control import WorkCancelled
from sentio.shared.exceptions import LLMServiceUnavailableError

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(PREFIX + "/quizzes", tags=["Practice"])
def saved_quizzes(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    from sentio.repositories.practice import PracticeRepository

    return PracticeRepository(agent.sm.persister._engine).quizzes(user["student_id"], limit, offset)


@router.get(PREFIX + "/quizzes/{quiz_id}", tags=["Practice"])
def saved_quiz(quiz_id: str, user: dict = Depends(get_current_user)):
    quiz = agent.sm.get_quiz(quiz_id)
    if not quiz or quiz["student_id"] != user["student_id"]:
        raise HTTPException(404, "Quiz not found.")
    return quiz


class QuestionEdit(BaseModel):
    question_text: str = Field(min_length=1, max_length=2000)
    options: Optional[List[str]] = Field(None, max_length=8)
    correct_answer: str = Field(min_length=1, max_length=1000)
    explanation: str = Field("", max_length=5000)
    expected_revision: Optional[int] = Field(None, ge=0)


@router.put(PREFIX + "/quizzes/{quiz_id}/questions/{question_id}", tags=["Practice"])
def edit_question(
    quiz_id: str, question_id: str, body: QuestionEdit, user: dict = Depends(get_current_user)
):
    """Correct a saved question. Earlier results keep their grades; new answers use the edit."""
    from sentio.ai.structured_parser import QuizQuestion
    from sentio.repositories.quizzes import QuizRepository, RevisionConflict

    quiz = agent.sm.get_quiz(quiz_id)
    stored = quiz and next((q for q in quiz["questions"] if q["question_id"] == question_id), None)
    if not stored or quiz["student_id"] != user["student_id"]:
        raise HTTPException(404, "Question not found.")
    try:
        question = QuizQuestion(
            question_text=body.question_text.strip(),
            question_type=stored["question_type"],
            options=[o.strip() for o in body.options] if body.options else None,
            correct_answer=body.correct_answer.strip(),
            explanation=body.explanation.strip() or "No explanation provided.",
        )
    except ValidationError as exc:
        reason = exc.errors()[0]["msg"].removeprefix("Value error, ")
        raise HTTPException(422, reason) from exc
    if question.question_type not in ("multiple_choice", "true_false"):
        question.options = None
    try:
        revision = QuizRepository(agent.sm.persister).edit_question(
            user["student_id"],
            quiz_id,
            question_id,
            question.model_dump(
                include={"question_text", "options", "correct_answer", "explanation"}
            ),
            body.expected_revision,
        )
    except RevisionConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    if revision is None:
        raise HTTPException(404, "Question not found.")
    return {"saved": True, "quiz_id": quiz_id, "question_id": question_id, "revision": revision}


class AnswerCheck(BaseModel):
    answer: str = Field(min_length=1, max_length=1000)


@router.post(PREFIX + "/quizzes/{quiz_id}/questions/{question_id}/check", tags=["Practice"])
def check_answer(
    quiz_id: str, question_id: str, body: AnswerCheck, user: dict = Depends(get_current_user)
):
    """Instant feedback on one answer. Nothing is recorded until the quiz is submitted."""
    quiz = agent.sm.get_quiz(quiz_id)
    question = quiz and next(
        (q for q in quiz["questions"] if q["question_id"] == question_id), None
    )
    if not question or quiz["student_id"] != user["student_id"]:
        raise HTTPException(404, "Question not found.")
    is_correct, score = quiz_service.grade_answer(question, body.answer)
    return {
        "is_correct": is_correct,
        "score": score,
        "correct_answer": question["correct_answer"],
        "explanation": question["explanation"],
    }


@router.post(PREFIX + "/sessions/{session_id}/quiz", tags=["Tutoring"])
def submit_quiz(session_id: str, req: QuizRequest, user: dict = Depends(get_current_user)):
    """
    Record a standalone quiz answer (without sending a chat message).
    Triggers difficulty adaptation if streak thresholds are reached.
    """
    _verify_session_owner(session_id, user)
    agent.sm.record_quiz_attempt(
        session_id=session_id,
        correct=req.correct,
        response_time_sec=req.response_time_sec,
        question_preview=req.question_preview,
    )
    state = agent.sm.get_current_state(session_id)
    return {
        "recorded": True,
        "correct": req.correct,
        "consecutive_correct": state["consecutive_correct"],
        "consecutive_wrong": state["consecutive_wrong"],
        "current_difficulty": state["difficulty"],
        "quiz_accuracy": state["quiz_accuracy"],
    }


@router.post(PREFIX + "/quizzes/generate", tags=["Tutoring"])
def generate_quiz(req: QuizGenerateRequest, user: dict = Depends(get_current_user)):
    """
    Generate a customized quiz about a topic. Uses student memory and RAG context if available.
    """
    _verify_session_owner(req.session_id, user)
    # Force student_id from token
    req.student_id = user["student_id"]
    try:
        quiz = quiz_service.generate_quiz(
            student_id=req.student_id,
            session_id=req.session_id,
            subject=req.subject,
            topic=req.topic,
            difficulty=req.difficulty,
            num_questions=req.num_questions,
            require_owner=True,
        )
        return quiz
    except LLMServiceUnavailableError:
        raise
    except WorkCancelled as exc:
        raise HTTPException(409, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Quiz generation failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(PREFIX + "/quizzes/{quiz_id}/submit", tags=["Tutoring"])
def submit_quiz_scoring(
    quiz_id: str, req: QuizSubmitRequest, user: dict = Depends(get_current_user)
):
    """
    Submit quiz answers. Grades responses, updates student mastery via EMA, and records mistakes.
    """
    _verify_session_owner(req.session_id, user)
    quiz = agent.sm.get_quiz(quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found.")
    _verify_student_owner(quiz["student_id"], user)
    try:
        result = quiz_service.score_quiz(
            quiz_id=quiz_id, student_answers=req.answers, session_id=req.session_id
        )
        return result
    except LLMServiceUnavailableError:
        raise
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as val_err:
        raise HTTPException(status_code=404, detail=str(val_err))
    except Exception as exc:
        logger.exception("Quiz submission failed")
        raise HTTPException(status_code=500, detail=str(exc))
