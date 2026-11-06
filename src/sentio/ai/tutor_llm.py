import logging
import time
from typing import Dict, List, Optional

from sentio.ai.conversation_history import ConversationHistory
from sentio.ai.prompts import PromptBuilder
from sentio.ai.providers import LLMBackend, OllamaBackend
from sentio.ai.response_models import TutorResponse
from sentio.ai.response_parser import ResponseParser
from sentio.config import nlp_cfg, tutor_cfg
from sentio.shared.exceptions import LLMServiceUnavailableError

logger = logging.getLogger(__name__)


class NLPEngine:
    """
    Main NLP interface used by TutorAgent.

    Orchestrates: PromptBuilder → LLMBackend → ResponseParser
    """

    MAX_RETRIES = 3
    RETRY_DELAY_SEC = 1.5

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

    @property
    def is_ready(self) -> bool:
        return self._backend is not None

    # ── Core Respond ───────────────────────────

    def respond(
        self,
        student_message: str,
        subject: str,
        topic: str,
        difficulty: str,
        learning_state: str,
        emotion_confidence: float = 1.0,
        retrieved_content=None,  # RetrievedContent | None
        session_id: str = "default",
        tone_instruction: str = "",
    ) -> TutorResponse:
        """
        Generate an adaptive tutoring response.
        """
        if not self.is_ready:
            raise RuntimeError("NLPEngine not loaded. Call .load() first.")

        strategy = tutor_cfg.STRATEGY_MAP.get(learning_state, "standard")

        # Build prompts
        system_prompt, user_message = self.prompt_builder.build_study_messages(
            student_message=student_message,
            subject=subject,
            topic=topic,
            difficulty=difficulty,
            learning_state=learning_state,
            strategy=strategy,
            tone_instruction=tone_instruction,
            retrieved_content=retrieved_content,
        )

        # Get conversation history for this session
        history = self._get_history(session_id)

        # Call LLM with retry
        raw_text, tokens, latency = self._call_with_retry(
            system_prompt=system_prompt,
            history=history.to_list(),
            user_message=user_message,
        )

        # Parse response
        response = self.parser.parse(
            raw=raw_text,
            strategy=strategy,
            learning_state=learning_state,
            tokens=tokens,
            latency_ms=latency,
            backend_name=self._backend.name,
        )

        # Update conversation history
        history.add_user(student_message)  # Store clean message (no metadata)
        history.add_assistant(response.text)

        logger.info(
            f"Response generated | state={learning_state} strategy={strategy} "
            f"tokens={tokens} latency={latency:.0f}ms"
        )
        return response

    # ── Retry Logic ────────────────────────────

    def _call_with_retry(
        self,
        system_prompt: str,
        history: List[Dict[str, str]],
        user_message: str,
        max_tokens: int = 1024,
    ) -> tuple[str, int, float]:
        """
        Call backend with exponential-backoff retry.
        Returns (text, tokens, latency_ms).
        """
        last_error = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                t0 = time.perf_counter()
                text, tokens = self._backend.complete(
                    system_prompt=system_prompt,
                    history=history,
                    user_message=user_message,
                    max_tokens=max_tokens,
                    temperature=0.0,
                )
                latency = (time.perf_counter() - t0) * 1000
                return text, tokens, latency
            except Exception as e:
                last_error = e
                logger.warning(f"LLM call failed (attempt {attempt}/{self.MAX_RETRIES}): {e}")
                if attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_DELAY_SEC * attempt)

        # All retries exhausted → raise LLMServiceUnavailableError or fallback
        logger.error(f"All LLM retries failed. Last error: {last_error}")
        if isinstance(last_error, LLMServiceUnavailableError):
            raise last_error
        fallback = (
            '{"text": "I\'m having trouble connecting right now. '
            "Let's try again in a moment. Meanwhile, review your notes on this topic.\", "
            '"encouragement": "You\'re doing great — technical hiccups happen!", '
            '"follow_up_question": null, "suggested_topic": null}'
        )
        return fallback, 0, 0.0

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

    def get_history_length(self, session_id: str) -> int:
        return len(self._get_history(session_id))

    # ── Utility ────────────────────────────────

    def quick_ask(self, prompt: str, session_id: str = "quick") -> str:
        """
        Fire a raw prompt without emotion/curriculum context.
        Useful for one-off questions or testing.
        """
        if not self.is_ready:
            raise RuntimeError("NLPEngine not loaded.")
        text, _, _ = self._call_with_retry(
            system_prompt="You are a helpful AI tutor. Respond concisely.",
            history=[],
            user_message=prompt,
        )
        return text

    def summarize_session(self, session_id: str, subject: str, topic: str) -> str:
        """
        Generate a brief session summary for the student's records.
        """
        history = self._get_history(session_id)
        if len(history) == 0:
            return "No messages in this session yet."

        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content'][:200]}..." for m in history.to_list()
        )
        prompt = (
            f"Summarize this tutoring session on {subject} ({topic}) in 3 bullet points. "
            f"Focus on: what was covered, where the student struggled, and next steps.\n\n"
            f"Session transcript:\n{history_text}"
        )
        return self.quick_ask(prompt, session_id=f"{session_id}_summary")
