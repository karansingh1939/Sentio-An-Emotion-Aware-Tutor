"""Flashcard tags are bounded so structured output cannot run away."""

import pytest
from pydantic import ValidationError

from sentio.ai.structured_parser import FlashcardItem


def test_flashcard_tags_are_limited_in_the_schema_given_to_the_model():
    assert FlashcardItem.model_json_schema()["properties"]["tags"]["maxItems"] == 5
    with pytest.raises(ValidationError):
        FlashcardItem(front="a", back="b", tags=["t"] * 6)
