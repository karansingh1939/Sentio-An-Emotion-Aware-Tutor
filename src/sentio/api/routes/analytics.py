"""Analytics API routes."""

import logging

from fastapi import APIRouter, Depends

from sentio.api.dependencies import PREFIX, _verify_session_owner, agent
from sentio.auth.middleware import RoleRequired, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(PREFIX + "/sessions/{session_id}/analytics", tags=["Analytics"])
def get_analytics(session_id: str, user: dict = Depends(get_current_user)):
    """Live analytics for an active session (no session close required)."""
    _verify_session_owner(session_id, user)
    analytics = agent.get_analytics(session_id)
    return analytics.to_dict()


@router.get(PREFIX + "/sessions/{session_id}/summary", tags=["Analytics"])
def get_summary(session_id: str, user: dict = Depends(get_current_user)):
    """
    LLM-generated bullet-point summary of the session so far.
    Covers: topics covered, where the student struggled, next steps.
    """
    _verify_session_owner(session_id, user)
    summary_text = agent.summarize_session(session_id)
    return {
        "session_id": session_id,
        "summary": summary_text,
    }


@router.get(PREFIX + "/students/{student_id}/history", tags=["Analytics"])
def get_student_history(student_id: str, limit: int = 20, user: dict = Depends(get_current_user)):
    """Return past session summaries for a student."""
    student_id = user["student_id"]
    history = agent.get_student_history(student_id, limit=limit)
    return {"student_id": student_id, "sessions": history}


@router.get(PREFIX + "/diagnostics/session/{session_id}", tags=["Diagnostics"])
def get_session_diagnostics(session_id: str, user: dict = Depends(get_current_user)):
    """Retrieve detailed agent routing timeline, process memory footprint and latency metrics."""
    _verify_session_owner(session_id, user)
    traces = agent.sm.get_diagnostics(session_id)
    from sentio.ai.structured_parser import metrics as parser_metrics

    pm = parser_metrics.get_metrics()
    attention_summary = agent.sm.get_attention_summary(session_id)
    if not traces:
        return {
            "session_id": session_id,
            "message": "No diagnostics traces found for this session yet. Send chat messages to populate traces.",
            "traces": [],
            "structured_parser_metrics": pm,
            "telemetry_summary": attention_summary,
        }
    return {
        "session_id": session_id,
        "traces": traces,
        "latest": traces[-1],
        "structured_parser_metrics": pm,
        "telemetry_summary": attention_summary,
    }


@router.get(PREFIX + "/diagnostics/structured_parser", tags=["Diagnostics"])
def get_structured_parser_diagnostics(user: dict = Depends(RoleRequired("manage_users"))):
    """Retrieve performance and recovery statistics of the Structured Output Reliability Layer (D0)."""
    from sentio.ai.structured_parser import metrics as parser_metrics

    return parser_metrics.get_metrics()
