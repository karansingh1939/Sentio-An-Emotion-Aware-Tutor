"""Telemetry API routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from sentio.api.dependencies import PREFIX, _verify_session_owner, agent
from sentio.api.schemas import TelemetryRequest
from sentio.auth.middleware import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(PREFIX + "/sessions/{session_id}/telemetry", tags=["Sessions"])
async def receive_telemetry(
    session_id: str,
    request: Request,
    payload: TelemetryRequest,
    user: dict = Depends(get_current_user),
):
    _verify_session_owner(session_id, user)

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            length = int(content_length)
            if length > 1000:
                logger.warning(f"Telemetry request payload size too large: {length} bytes")
                raise HTTPException(status_code=413, detail="Payload Too Large")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length Header")

    if (
        len(payload.emotion) > 50
        or "data:image" in payload.emotion
        or ";base64," in payload.emotion
    ):
        logger.warning("Telemetry validation failure: rejected potential base64 or image data")
        raise HTTPException(status_code=400, detail="Invalid telemetry payload contents")

    logger.debug("Telemetry payload validated for session %s", session_id[:8])
    agent.sm.save_attention_log(
        session_id=session_id,
        attention_score=payload.attention_score,
        focused=payload.focused,
        eye_openness=payload.eye_openness,
        head_pose_pitch=payload.head_pose_pitch,
        head_pose_yaw=payload.head_pose_yaw,
        emotion=payload.emotion,
    )
    return {"status": "success", "message": "Telemetry accepted, validated, and persisted"}
