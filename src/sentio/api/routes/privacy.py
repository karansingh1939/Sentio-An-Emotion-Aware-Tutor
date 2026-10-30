"""Privacy API routes."""

import logging
import time

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)

from sentio.api.dependencies import PREFIX, _verify_student_owner, agent
from sentio.api.schemas import ConsentRequest
from sentio.auth.middleware import get_current_user
from sentio.config import BASE_DIR, session_cfg
from sentio.session.models import EmotionTimeline

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(PREFIX + "/student/{student_id}/export", tags=["Privacy"])
def export_student_data(student_id: str, user: dict = Depends(get_current_user)):
    """
    Export all stored learning data associated with the student.
    """
    _verify_student_owner(student_id, user)
    from sqlalchemy import text

    try:
        # Retrieve all student data from SQL tables
        persister = agent.sm.persister
        data = {}
        engine = persister._engine
        with engine.connect() as conn:
            data["account"] = (
                conn.execute(
                    text(
                        "SELECT student_id, email, role, created_at FROM student_accounts WHERE student_id = :sid"
                    ),
                    {"sid": student_id},
                )
                .mappings()
                .all()
            )
            data["sessions"] = (
                conn.execute(
                    text(
                        "SELECT session_id, subject, topic, difficulty, status, created_at, closed_at, duration_min, summary FROM sessions WHERE student_id = :sid"
                    ),
                    {"sid": student_id},
                )
                .mappings()
                .all()
            )
            data["student_knowledge"] = (
                conn.execute(
                    text(
                        "SELECT topic_id, mastery_score, attempts_count, consecutive_correct, last_attempt_at FROM student_knowledge WHERE student_id = :sid"
                    ),
                    {"sid": student_id},
                )
                .mappings()
                .all()
            )
            data["flashcards"] = (
                conn.execute(
                    text(
                        "SELECT card_id, topic_id, front_text, back_text, created_at, interval_days, repetition_count, ease_factor, stability, difficulty, last_review_at, next_review_at FROM flashcards WHERE student_id = :sid"
                    ),
                    {"sid": student_id},
                )
                .mappings()
                .all()
            )
            data["quiz_attempts"] = (
                conn.execute(
                    text(
                        "SELECT id, session_id, topic, question_text, student_answer, correct, score, response_time_sec, difficulty, timestamp FROM quiz_attempts WHERE student_id = :sid"
                    ),
                    {"sid": student_id},
                )
                .mappings()
                .all()
            )
            data["learning_goals"] = (
                conn.execute(
                    text(
                        "SELECT goal_id, topic_id, goal_text, target_date, status, created_at, completed_at FROM learning_goals WHERE student_id = :sid"
                    ),
                    {"sid": student_id},
                )
                .mappings()
                .all()
            )
            data["audit_logs"] = persister.auth_repo.get_audit_logs(student_id)
            data["consent_history"] = persister.auth_repo.get_consent_history(student_id)

        data.update(persister.auth_repo.export_study_artifacts(student_id))
        # Serialize database mappings to json-serializable list/dict structure
        serializable_data = {}
        for key, val in data.items():
            serializable_data[key] = [dict(row) for row in val]

        persister.auth_service.audit.log_event(
            student_id, "data_export", details="Exported all student profile logs"
        )
        return {"student_id": student_id, "data": serializable_data}
    except Exception as e:
        logger.exception("Data export failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(PREFIX + "/student/{student_id}/data", tags=["Privacy"])
def delete_student_data(student_id: str, request: Request, user: dict = Depends(get_current_user)):
    """
    Permanently delete all user profile and learning data records (GDPR compliance).
    """
    _verify_student_owner(student_id, user)
    jobs = getattr(request.app.state, "jobs", None)
    if jobs:
        jobs.cancel_owner(student_id)
    try:
        from sentio.maintenance.account_cleanup import AccountCleanup

        service = AccountCleanup(
            agent.sm.persister,
            agent.kb.vdb,
            BASE_DIR / "data/documents",
            session_cfg.SESSION_LOG_PATH,
            session_cfg.EMOTION_LOG_PATH,
        )
        documents = getattr(request.app.state, "documents", None)
        from contextlib import nullcontext

        with documents.lock if documents is not None else nullcontext():
            result = service.delete(student_id)
        for sid in result["session_ids"]:
            agent.sm._sessions.pop(sid, None)
            agent.sm._diagnostics.pop(sid, None)
            agent.detector.clear_session(sid)
            if hasattr(agent.nlp, "clear_history"):
                agent.nlp.clear_history(sid)
        return {
            "deleted": True,
            "student_id": student_id,
            "cleanup_pending": result["cleanup_pending"],
        }
    except Exception as e:
        if jobs and agent.sm.persister.auth_repo.get_account_by_student_id(student_id) is not None:
            jobs.resume_owner(student_id)
        logger.exception("Data deletion failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(PREFIX + "/student/{student_id}/telemetry", tags=["Privacy"])
def delete_student_telemetry(student_id: str, user: dict = Depends(get_current_user)):
    """
    Purge only webcam attention logs and emotional trace data.
    """
    _verify_student_owner(student_id, user)
    try:
        agent.sm.persister.auth_repo.delete_telemetry(student_id)
        for row in agent.sm.persister.list_sessions(student_id=student_id, limit=-1):
            sid = row["session_id"]
            session = agent.sm.get_session(sid)
            if session is not None:
                session.emotion_timeline = EmotionTimeline()
                session.summary = None
                agent.sm.persister.save_session(session)
            agent.sm._diagnostics.pop(sid, None)
            agent.detector.clear_session(sid)
            (session_cfg.EMOTION_LOG_PATH / f"{sid}_emotions.json").unlink(missing_ok=True)
        agent.sm.persister.auth_service.audit.log_event(
            student_id, "telemetry_deletion", details="Purged emotion events and webcam logs"
        )
        return {"telemetry_deleted": True, "student_id": student_id}
    except Exception as e:
        logger.exception("Telemetry deletion failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(PREFIX + "/student/{student_id}/consent", tags=["Privacy"])
def get_student_consent(student_id: str, user: dict = Depends(get_current_user)):
    """
    Retrieve consent history records.
    """
    _verify_student_owner(student_id, user)
    try:
        history = agent.sm.persister.auth_repo.get_consent_history(student_id)
        return {"student_id": student_id, "history": history}
    except Exception as e:
        logger.exception("Failed to fetch consent logs")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(PREFIX + "/student/{student_id}/consent", tags=["Privacy"])
def update_student_consent(
    student_id: str, req: ConsentRequest, user: dict = Depends(get_current_user)
):
    """
    Save or update tracking and preference consent settings.
    """
    _verify_student_owner(student_id, user)
    try:
        import json

        from sentio.auth.models import ConsentHistory

        consent = ConsentHistory(
            student_id=student_id,
            consent_version=req.consent_version,
            preferences_json=json.dumps(req.preferences),
            timestamp=time.time(),
        )
        agent.sm.persister.auth_repo.save_consent(consent)
        agent.sm.persister.auth_service.audit.log_event(
            student_id, "consent_update", details=f"Version {req.consent_version}"
        )
        return {"saved": True, "student_id": student_id}
    except Exception as e:
        logger.exception("Consent update failed")
        raise HTTPException(status_code=500, detail=str(e))
