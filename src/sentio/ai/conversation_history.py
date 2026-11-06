from collections import deque
from typing import Dict, List, Optional

from sentio.ai.response_models import Message
from sentio.config import nlp_cfg


class ConversationHistory:
    """
    Maintains a sliding window of Message objects.
    Older messages beyond MAX_HISTORY_TURNS are dropped to stay
    within the LLM's context window.
    """

    def __init__(self, max_turns: int = nlp_cfg.MAX_HISTORY_TURNS):
        self.max_turns = max_turns
        # Each "turn" = 1 user + 1 assistant message = 2 Message objects
        self._messages: deque = deque(maxlen=max_turns * 2)

    def add_user(self, content: str):
        self._messages.append(Message(role="user", content=content))

    def add_assistant(self, content: str):
        self._messages.append(Message(role="assistant", content=content))

    def to_list(self) -> List[Dict[str, str]]:
        """Return as list of dicts for API calls."""
        return [m.to_dict() for m in self._messages]

    def clear(self):
        self._messages.clear()

    def __len__(self):
        return len(self._messages)

    def last_student_message(self) -> Optional[str]:
        for msg in reversed(list(self._messages)):
            if msg.role == "user":
                return msg.content
        return None
