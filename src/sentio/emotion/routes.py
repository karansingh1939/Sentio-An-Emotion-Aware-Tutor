"""Emotion side-feature routes: browser attention telemetry and live emotion frames."""

import asyncio
import logging
import time
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect

from sentio.api.dependencies import PREFIX, _verify_session_owner, agent
from sentio.api.schemas import TelemetryRequest
from sentio.auth.middleware import authenticate_access_token, get_current_user
from sentio.config import tutor_cfg
from sentio.emotion.access import decode_frame, require_emotion_access

logger = logging.getLogger(__name__)
router = APIRouter()

FRAME_INTERVAL_SEC = 1.0  # The shortest time between frames the server will analyse.


@router.post(PREFIX + "/sessions/{session_id}/telemetry", tags=["Emotion"])
async def receive_telemetry(
    session_id: str,
    request: Request,
    payload: TelemetryRequest,
    user: dict = Depends(get_current_user),
):
    session = _verify_session_owner(session_id, user)
    require_emotion_access(agent.sm.persister, user["student_id"])

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
    confidence = min(1.0, max(0.0, round(1 - payload.attention_score, 2)))
    if not payload.focused and confidence >= tutor_cfg.EMOTION_CONFIDENCE_THRESHOLD:
        # Clearly looking away is a reading of its own, as confident as attention is low.
        # Weaker signs are not recorded: the latest reading also sets the session strategy.
        # Looking at the screen records nothing, so the server model's readings decide.
        agent.sm.record_emotion(
            session_id,
            SimpleNamespace(
                emotion="looking_away", learning_state="disengaged", confidence=confidence
            ),
            strategy_active=session.current_strategy,
        )
    return {"status": "success", "message": "Telemetry accepted, validated, and persisted"}


@router.websocket(PREFIX + "/ws/{session_id}")
async def websocket_emotion_stream(websocket: WebSocket, session_id: str):
    """
    Live emotion stream. The client sends {"frame_b64": "<base64 JPEG>"} and receives
    the detected emotion, learning state, confidence and current tutoring strategy.
    """
    # Browsers cannot set Authorization: send {"access_token": "..."} as
    # the first message instead. Never accept tokens in URLs or process frames
    # until authentication, session ownership and camera consent have succeeded.
    authorization = websocket.headers.get("authorization", "")
    token = authorization[7:] if authorization.lower().startswith("bearer ") else None
    accepted = False
    try:
        if not token:
            await websocket.accept()
            accepted = True
            credentials = await asyncio.wait_for(websocket.receive_json(), timeout=10)
            token = credentials.get("access_token") if isinstance(credentials, dict) else None
        if not isinstance(token, str) or not token:
            raise HTTPException(status_code=401, detail="Access token required.")
        user = authenticate_access_token(agent.sm.persister, token)
        session = _verify_session_owner(session_id, user)
        require_emotion_access(agent.sm.persister, user["student_id"])
    except (HTTPException, asyncio.TimeoutError, ValueError, WebSocketDisconnect):
        await websocket.close(code=1008)
        return
    if not accepted:
        await websocket.accept()
    logger.info("WebSocket connected: session=%s", session_id[:8])

    last_frame = None
    try:
        while True:
            data = await websocket.receive_json()
            # The model runs at most once a second per connection, whatever the client sends.
            now = time.monotonic()
            if last_frame is not None and now - last_frame < FRAME_INTERVAL_SEC:
                await websocket.send_json({"error": "Too many frames"})
                continue
            last_frame = now
            # Long-lived connections must not outlive account deletion, token expiry
            # or withdrawn consent.
            try:
                user = authenticate_access_token(agent.sm.persister, token)
                _verify_session_owner(session_id, user)
                require_emotion_access(agent.sm.persister, user["student_id"])
            except HTTPException:
                await websocket.close(code=1008)
                return
            frame = decode_frame(data.get("frame_b64"))

            if frame is None:
                await websocket.send_json({"error": "Invalid, oversized or missing frame_b64"})
                continue

            from starlette.concurrency import run_in_threadpool

            result = await run_in_threadpool(
                agent.detector.detect_from_frame, frame, session_id=session_id
            )
            if result is None:
                await websocket.send_json(
                    {
                        "emotion": "unknown",
                        "learning_state": "neutral",
                        "confidence": 0.0,
                        "all_scores": {},
                        "strategy": "standard",
                        "engagement_score": 0.5,
                        "face_detected": False,
                    }
                )
                continue

            agent.sm.record_emotion(
                session_id,
                result,
                strategy_active=session.current_strategy,
            )

            state = agent.sm.get_current_state(session_id)

            await websocket.send_json(
                {
                    "emotion": result.emotion,
                    "learning_state": result.learning_state,
                    "confidence": round(result.confidence, 3),
                    "all_scores": {k: round(v, 3) for k, v in result.all_scores.items()},
                    "strategy": state["strategy"],
                    "engagement_score": round(state["engagement_score"], 3),
                    "difficulty": state["difficulty"],
                    "face_detected": True,
                    "timestamp": time.time(),
                }
            )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: session=%s", session_id[:8])
    except Exception as exc:
        logger.exception("WebSocket error: %s", exc)
        await websocket.close()
