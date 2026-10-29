"""Flashcards API routes."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from sentio.api.dependencies import PREFIX, _verify_session_owner, agent, flashcard_service
from sentio.api.schemas import CreateDeckRequest, GenerateFlashcardsRequest, ReviewCardRequest
from sentio.auth.middleware import get_current_user
from sentio.jobs.control import WorkCancelled
from sentio.repositories.practice import PracticeRepository, ReviewConflict
from sentio.shared.exceptions import LLMServiceUnavailableError

logger = logging.getLogger(__name__)
router = APIRouter()


class CardEdit(BaseModel):
    front_text: str = Field(min_length=1, max_length=2000)
    back_text: str = Field(min_length=1, max_length=5000)


@router.patch(PREFIX + "/flashcards/{card_id}", tags=["Flashcards"])
def edit_card(card_id: str, body: CardEdit, user: dict = Depends(get_current_user)):
    if not body.front_text.strip() or not body.back_text.strip():
        raise HTTPException(422, "Both sides of the card must contain text.")
    repository = PracticeRepository(agent.sm.persister._engine)
    if not repository.edit_card(
        user["student_id"], card_id, body.front_text.strip(), body.back_text.strip()
    ):
        raise HTTPException(404, "Flashcard not found.")
    return {"saved": True, "card_id": card_id}


@router.post(PREFIX + "/flashcards/decks", tags=["Flashcards"], status_code=201)
def create_flashcard_deck(req: CreateDeckRequest, user: dict = Depends(get_current_user)):
    """Create a new flashcard deck for grouping cards."""
    # Force student_id from token
    req.student_id = user["student_id"]
    try:
        deck_id = flashcard_service.create_deck(req.student_id, req.deck_name)
        return {"deck_id": deck_id, "deck_name": req.deck_name}
    except Exception as e:
        logger.exception("Failed to create flashcard deck")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(PREFIX + "/flashcards/decks", tags=["Flashcards"])
def list_flashcard_decks(student_id: str, user: dict = Depends(get_current_user)):
    """Retrieve all flashcard decks for a student."""
    # Force student_id from token
    student_id = user["student_id"]
    try:
        decks = flashcard_service.list_decks(student_id)
        return {"decks": decks, "count": len(decks)}
    except Exception as e:
        logger.exception("Failed to list flashcard decks")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(PREFIX + "/flashcards/generate", tags=["Flashcards"])
def generate_flashcards(req: GenerateFlashcardsRequest, user: dict = Depends(get_current_user)):
    """Extract and save term/definition flashcards from context."""
    # Force student_id from token
    req.student_id = user["student_id"]

    if req.session_id:
        _verify_session_owner(req.session_id, user)
    # Verify deck ownership under zero-trust rules
    decks = flashcard_service.list_decks(req.student_id)
    if not any(d["deck_id"] == req.deck_id for d in decks):
        raise HTTPException(status_code=403, detail="Access denied to this flashcard deck.")

    try:
        cards = flashcard_service.generate_flashcards(
            student_id=req.student_id,
            deck_id=req.deck_id,
            topic_id=req.topic_id,
            num_cards=req.num_cards,
            session_id=req.session_id,
            require_owner=True,
        )
        return cards
    except LLMServiceUnavailableError:
        raise
    except WorkCancelled as exc:
        raise HTTPException(409, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as e:
        logger.exception("Failed to generate flashcards")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(PREFIX + "/flashcards/reviews/due", tags=["Flashcards"])
def get_due_reviews(
    student_id: str, deck_id: Optional[str] = None, user: dict = Depends(get_current_user)
):
    """Retrieve all flashcards currently due for spaced repetition review."""
    # Force student_id from token
    student_id = user["student_id"]
    try:
        due_cards = flashcard_service.get_due_reviews(student_id, deck_id)
        return {"student_id": student_id, "due_count": len(due_cards), "cards": due_cards}
    except Exception as e:
        logger.exception("Failed to fetch due flashcards")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(PREFIX + "/flashcards/{card_id}/reviews/{request_id}", tags=["Flashcards"])
def get_review_receipt(
    card_id: str,
    request_id: str = Path(min_length=8, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$"),
    user: dict = Depends(get_current_user),
):
    receipt = PracticeRepository(agent.sm.persister._engine).review_receipt(
        user["student_id"], card_id, request_id
    )
    if receipt is None:
        raise HTTPException(404, "Review receipt not found.")
    return receipt


@router.post(PREFIX + "/flashcards/{card_id}/review", tags=["Flashcards"])
def review_flashcard(card_id: str, req: ReviewCardRequest, user: dict = Depends(get_current_user)):
    """Record review rating (0-5) and schedule the next review with FSRS."""
    card = agent.sm.get_flashcard(card_id)
    if not card or card.get("student_id") != user["student_id"]:
        raise HTTPException(status_code=403, detail="Access denied or flashcard not found.")
    try:
        result = flashcard_service.review_card(
            card_id, req.quality_score, user["student_id"], req.request_id
        )
        return result
    except ReviewConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as val_err:
        raise HTTPException(status_code=404, detail=str(val_err))
    except Exception as e:
        logger.exception("Failed to review flashcard")
        raise HTTPException(
            status_code=503, detail="Review could not be saved. Retry the same rating."
        ) from e
