"""Constrain each generated batch to the count the learner requested."""

from functools import lru_cache

from pydantic import Field, create_model

from sentio.ai.structured_parser import FlashcardPayloadSchema, QuizPayloadSchema


@lru_cache(maxsize=50)
def practice_schema(kind, count):
    base, field, limit = {
        "quiz": (QuizPayloadSchema, "questions", 20),
        "flashcards": (FlashcardPayloadSchema, "cards", 30),
    }[kind]
    if type(count) is not int or not 1 <= count <= limit:
        raise ValueError("Practice batch count is outside its bounds")
    return create_model(
        f"{base.__name__}{count}",
        __base__=base,
        **{
            field: (
                base.model_fields[field].annotation,
                Field(..., min_length=count, max_length=count),
            )
        },
    )
