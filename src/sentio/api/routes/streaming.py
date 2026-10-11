"""Authenticated POST event stream; disconnects cancel unfinished work."""

import asyncio
import json
from queue import Empty

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from sentio.api.dependencies import PREFIX, _verify_session_owner
from sentio.auth.middleware import get_current_user
from sentio.shared.utils import sanitise_input

router = APIRouter()


@router.get(PREFIX + "/sessions/{session_id}/turns", tags=["Tutoring"])
def turns(
    session_id: str,
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(get_current_user),
):
    _verify_session_owner(session_id, user)
    return {"turns": request.app.state.streams.turns(user["student_id"], session_id, limit, offset)}


class StreamRequest(BaseModel):
    request_id: str = Field(min_length=8, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    message: str = Field(min_length=1, max_length=10000)


@router.post(PREFIX + "/sessions/{session_id}/chat/stream", tags=["Tutoring"])
async def stream(
    session_id: str, body: StreamRequest, request: Request, user=Depends(get_current_user)
):
    session = _verify_session_owner(session_id, user)
    if not session.is_active:
        raise HTTPException(409, "Resume this session before asking the tutor.")
    message = sanitise_input(body.message)
    if not message:
        raise HTTPException(422, "Enter a question.")
    service = getattr(request.app.state, "streams", None)
    if service is None:
        raise HTTPException(503, "The tutor queue is unavailable. Restart Sentio.")
    try:
        events, job_id = service.begin(user["student_id"], session_id, body.request_id, message)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc

    async def response():
        try:
            yield (
                "event: status\ndata: " + json.dumps({"stage": "queued", "job_id": job_id}) + "\n\n"
            )
            while True:
                if await request.is_disconnected():
                    return
                try:
                    kind, data = events.get_nowait()
                except Empty:
                    await asyncio.sleep(0.04)
                    continue
                yield "event: " + kind + "\ndata: " + json.dumps(data) + "\n\n"
                if kind in ("complete", "cancelled", "error"):
                    return
        finally:
            service.cancel(user["student_id"], session_id, body.request_id)

    return StreamingResponse(
        response(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post(PREFIX + "/sessions/{session_id}/chat/{request_id}/cancel", tags=["Tutoring"])
def cancel(session_id: str, request_id: str, request: Request, user=Depends(get_current_user)):
    _verify_session_owner(session_id, user)
    service = getattr(request.app.state, "streams", None)
    return {
        "accepted": service.cancel(user["student_id"], session_id, request_id) if service else False
    }
