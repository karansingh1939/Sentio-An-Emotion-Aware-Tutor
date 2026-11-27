from dataclasses import dataclass
from typing import Optional


@dataclass
class Message:
    """Single turn in a conversation."""

    role: str  # "system" | "user" | "assistant"
    content: str

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


@dataclass
class TutorResponse:
    """
    Structured response from the NLP engine.
    The TutorAgent uses this to build the final reply to the student.
    """

    text: str  # Main tutoring response
    follow_up_question: Optional[str] = None  # Comprehension check
    suggested_topic: Optional[str] = None  # Next topic to explore
    encouragement: Optional[str] = None  # Emotional support line
    strategy_used: str = "standard"
    learning_state: str = "neutral"
    tokens_used: int = 0
    latency_ms: float = 0.0
    backend_used: str = ""
    # answered | partial | not_in_notes | unverified (see sentio.ai.answer_check).
    answer_status: str = ""
