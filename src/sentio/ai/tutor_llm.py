import logging
from typing import Dict, Optional

from sentio.ai.conversation_history import ConversationHistory
from sentio.ai.prompts import PromptBuilder
from sentio.ai.providers import LLMBackend, OllamaBackend
from sentio.ai.response_parser import ResponseParser
from sentio.config import nlp_cfg

logger = logging.getLogger(__name__)


class NLPEngine:
    """
    Main NLP interface used by TutorAgent.

    Orchestrates: PromptBuilder → LLMBackend → ResponseParser
    """

    def __init__(
        self,
        cfg=nlp_cfg,
        prompt_builder: Optional[PromptBuilder] = None,
        parser: Optional[ResponseParser] = None,
    ):
        self.cfg = cfg
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.parser = parser or ResponseParser()
        self._backend: Optional[LLMBackend] = None
        self._history_store: Dict[str, ConversationHistory] = {}  # session_id → history

    # ── Setup ──────────────────────────────────

    def load(self):
        """Connect to the local Ollama model."""
        self._backend = OllamaBackend(self.cfg)
        self._backend.load()
        logger.info(f"NLPEngine ready. Backend: {self._backend.name}")

    # ── History Management ─────────────────────

    def _get_history(self, session_id: str) -> ConversationHistory:
        if session_id not in self._history_store:
            self._history_store[session_id] = ConversationHistory(
                max_turns=self.cfg.MAX_HISTORY_TURNS
            )
        return self._history_store[session_id]

    def clear_history(self, session_id: str):
        if session_id in self._history_store:
            self._history_store[session_id].clear()
            logger.info(f"Cleared history for session: {session_id}")
