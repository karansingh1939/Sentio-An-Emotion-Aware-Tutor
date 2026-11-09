"""Constrain each generated batch to the count the learner requested.

Local models on a laptop CPU write about 6 tokens a second, so a whole quiz takes a
minute or more. When one item in a batch is invalid, keep the valid items and ask the
model only for the missing ones, instead of throwing the batch away and starting again.
"""

import json
import logging
from functools import lru_cache
from typing import get_args

from pydantic import Field, ValidationError, create_model

from sentio.ai.structured_parser import (
    FlashcardPayloadSchema,
    QuizPayloadSchema,
    extract_json_block,
    normalize_keys,
    parse_structured_output,
    repair_json_string,
)

logger = logging.getLogger(__name__)

KINDS = {
    "quiz": (QuizPayloadSchema, "questions", 20, "title"),
    "flashcards": (FlashcardPayloadSchema, "cards", 30, "deck_name"),
}


@lru_cache(maxsize=50)
def practice_schema(kind, count):
    base, field, limit, _ = KINDS[kind]
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


def salvage(raw, kind):
    """Return (heading, valid items) from a reply that failed as a whole."""
    base, field, _, heading_field = KINDS[kind]
    item_model = get_args(base.model_fields[field].annotation)[0]
    data = None
    for attempt in (lambda: extract_json_block(raw or ""), lambda: repair_json_string(raw or "")):
        try:
            data = normalize_keys(json.loads(attempt()))
            break
        except (ValueError, TypeError):
            continue
    if not isinstance(data, dict) or not isinstance(data.get(field), list):
        return None, []
    kept = []
    for item in data[field]:
        try:
            kept.append(item_model.model_validate(item).model_dump())
        except (ValidationError, TypeError, ValueError):
            continue
    heading = data.get(heading_field)
    return (heading if isinstance(heading, str) and heading.strip() else None), kept


def _call(backend, schema, system_prompt, user_message, temperature):
    from sentio.ai.stream_schema import output_schema
    from sentio.shared.exceptions import InvalidModelOutput

    with output_schema(schema):
        try:
            return backend.complete(
                system_prompt=system_prompt,
                history=[],
                user_message=user_message,
                max_tokens=1024,
                temperature=temperature,
            )[0]
        except InvalidModelOutput as invalid:
            return invalid.raw


def generate_practice(backend, kind, count, system_prompt, user_message, temperature=0.7):
    """Generate `count` valid items, regenerating only the items that were invalid.

    Raises ValueError or LLMServiceUnavailableError when no valid batch is possible,
    so callers can fall back to source recall.
    """
    schema = practice_schema(kind, count)
    _, field, _, heading_field = KINDS[kind]
    raw = _call(backend, schema, system_prompt, user_message, temperature)
    try:
        return parse_structured_output(raw, schema, max_regenerations=0)
    except (ValueError, ValidationError) as error:
        heading, kept = salvage(raw, kind)
        logger.warning(
            "Practice batch invalid (%s); kept %d of %d items",
            type(error).__name__,
            len(kept),
            count,
        )

    def key(item):
        return (item.get("question_text") or item.get("front") or "").strip().lower()

    unique = {}
    for item in kept:
        unique.setdefault(key(item), item)
    noun = "questions" if kind == "quiz" else "cards"
    for _ in range(2):  # at most two more model calls, each asking only for what is missing
        missing = count - len(unique)
        if missing <= 0:
            break
        retry_message = (
            f"{user_message}\nReturn exactly {missing} {noun} in this reply, each with every "
            "required field filled. Do not repeat these existing items: " + json.dumps(list(unique))
        )
        raw = _call(
            backend, practice_schema(kind, missing), system_prompt, retry_message, temperature
        )
        more_heading, extra = salvage(raw, kind)
        heading = heading or more_heading
        for item in extra:
            unique.setdefault(key(item), item)
    if len(unique) < count:
        raise ValueError(f"Only {len(unique)} of {count} generated {noun} were valid.")
    items = list(unique.values())[:count]
    return schema.model_validate({heading_field: heading or "Practice", field: items})
