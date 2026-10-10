"""Tutoring API routes."""

import asyncio
import logging
import time

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)

from sentio.api.dependencies import PREFIX, _decode_frame, _verify_session_owner, agent
from sentio.api.schemas import ChatRequest, SwitchTopicRequest
from sentio.auth.middleware import authenticate_access_token, get_current_user
from sentio.shared.exceptions import LLMServiceUnavailableError
from sentio.shared.utils import sanitise_input

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(PREFIX + "/sessions/{session_id}/chat", tags=["Tutoring"])
def chat(session_id: str, req: ChatRequest, user: dict = Depends(get_current_user)):
    """
    Main tutoring endpoint.

    Send a student message + optional webcam frame.
    Returns an adaptive tutoring response including:
      - text, follow_up_question, encouragement, suggested_topic
      - detected emotion + learning state
      - current difficulty + strategy
      - engagement score
    """
    session = _verify_session_owner(session_id, user)
    if not session.is_active:
        raise HTTPException(
            status_code=409,
            detail="Session is not active (status=%s). Resume or create a new session."
            % session.status.value,
        )

    clean_msg = sanitise_input(req.message)
    if not clean_msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    frame = _decode_frame(req.frame_b64)

    try:
        response = agent.chat(
            session_id=session_id,
            student_message=clean_msg,
            frame=frame,
            quiz_correct=req.quiz_correct,
            response_time_sec=req.response_time_sec,
        )
    except LLMServiceUnavailableError:
        raise
    except Exception as exc:
        logger.exception("Chat error for session %s", session_id[:8])
        raise HTTPException(status_code=500, detail=str(exc))

    return response.to_dict()


@router.post(PREFIX + "/sessions/{session_id}/topic", tags=["Tutoring"])
def switch_topic(session_id: str, req: SwitchTopicRequest, user: dict = Depends(get_current_user)):
    """
    Switch the active topic mid-session.
    Clears conversation history so the LLM starts fresh on the new topic.
    """
    _verify_session_owner(session_id, user)
    updated_state = agent.switch_topic(
        session_id=session_id,
        new_topic=req.topic,
        new_difficulty=req.difficulty,
    )
    return {"switched": True, "state": updated_state}


@router.websocket(PREFIX + "/ws/{session_id}")
async def websocket_emotion_stream(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time emotion streaming.

    Client sends: JSON {"frame_b64": "<base64 JPEG>"}
    Server sends: JSON with detected emotion, learning_state, confidence,
                  all_scores, strategy, engagement_score

    The client (browser/app) captures webcam frames and pushes them here
    at ~10 fps. The server runs EmotionDetector on each frame and
    broadcasts the result back -- no full chat call needed.

    This powers the live emotion overlay in the UI.
    """
    # Browsers cannot set Authorization: send {"access_token": "..."} as
    # the first message instead. Never accept tokens in URLs or process frames
    # until authentication and session ownership have both succeeded.
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
    except (HTTPException, asyncio.TimeoutError, ValueError, WebSocketDisconnect):
        await websocket.close(code=1008)
        return
    if not accepted:
        await websocket.accept()
    logger.info("WebSocket connected: session=%s", session_id[:8])

    try:
        while True:
            data = await websocket.receive_json()
            # Long-lived connections must not outlive account deletion/token expiry.
            try:
                user = authenticate_access_token(agent.sm.persister, token)
                _verify_session_owner(session_id, user)
            except HTTPException:
                await websocket.close(code=1008)
                return
            frame_b64 = data.get("frame_b64")
            frame = _decode_frame(frame_b64)

            if frame is None:
                await websocket.send_json({"error": "Invalid or missing frame_b64"})
                continue

            # Run emotion detection
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

            # Record emotion into session (non-blocking)
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
