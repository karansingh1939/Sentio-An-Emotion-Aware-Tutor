"""Whiteboards API routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from sentio.api.dependencies import (
    PREFIX,
    _verify_session_owner,
    _verify_student_owner,
    agent,
    whiteboard_service,
)
from sentio.api.schemas import ExportWhiteboardRequest, MermaidRequest, SaveWhiteboardRequest
from sentio.auth.middleware import get_current_user
from sentio.jobs.control import WorkCancelled

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(PREFIX + "/whiteboards/sessions", tags=["Whiteboard"])
def save_whiteboard_session(req: SaveWhiteboardRequest, user: dict = Depends(get_current_user)):
    """Save or sync the whiteboard drawing canvas state."""
    _verify_session_owner(req.session_id, user)
    existing = agent.sm.get_whiteboard(req.whiteboard_id)
    if existing:
        _verify_student_owner(existing["student_id"], user)
    # Force student_id from token
    req.student_id = user["student_id"]
    try:
        whiteboard_service.save_session(
            whiteboard_id=req.whiteboard_id,
            student_id=req.student_id,
            session_id=req.session_id,
            title=req.title,
            canvas_state=req.canvas_state,
            require_owner=True,
        )
        return {"saved": True, "whiteboard_id": req.whiteboard_id}
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except WorkCancelled as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            422, "Drawing exceeds its limits or contains invalid vector data."
        ) from exc
    except Exception as e:
        logger.exception("Failed to save whiteboard session")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(PREFIX + "/whiteboards/{whiteboard_id}", tags=["Whiteboard"])
def get_whiteboard_session(whiteboard_id: str, user: dict = Depends(get_current_user)):
    """Retrieve the drawing canvas state for a whiteboard."""
    try:
        wb = whiteboard_service.load_session(whiteboard_id)
        if not wb:
            raise HTTPException(status_code=404, detail="Whiteboard session not found")
        if wb.get("student_id") != user["student_id"]:
            raise HTTPException(status_code=403, detail="Access denied.")
        return wb
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to load whiteboard session")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(PREFIX + "/whiteboards/{whiteboard_id}/export", tags=["Whiteboard"])
def export_whiteboard_session(
    whiteboard_id: str, req: ExportWhiteboardRequest, user: dict = Depends(get_current_user)
):
    """Export the whiteboard state to a PNG or PDF binary stream."""
    get_whiteboard_session(whiteboard_id, user)
    from fastapi import Response

    try:
        content = whiteboard_service.export_canvas(whiteboard_id, req.format)
        media_type = "application/pdf" if req.format.lower() == "pdf" else "image/png"
        return Response(content=content, media_type=media_type)
    except ValueError as val_err:
        raise HTTPException(
            status_code=422, detail="Saved drawing cannot be exported in this format."
        ) from val_err
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(PREFIX + "/whiteboards/mermaid", tags=["Whiteboard"])
def parse_mermaid_diagram(req: MermaidRequest, user: dict = Depends(get_current_user)):
    """Parse a Mermaid flowchart string into canvas vector shapes."""
    try:
        shapes = whiteboard_service.parse_mermaid_to_shapes(req.mermaid_code)
        return {"shapes": shapes}
    except Exception as e:
        logger.exception("Failed to parse Mermaid flowchart")
        raise HTTPException(status_code=400, detail=str(e))
