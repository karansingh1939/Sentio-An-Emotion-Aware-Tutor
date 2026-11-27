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
