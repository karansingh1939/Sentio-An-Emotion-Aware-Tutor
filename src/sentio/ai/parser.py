import json
import logging
import re

from sentio.ai.models import TutorResponse

logger = logging.getLogger(__name__)


class ResponseParser:
    """
    Parses raw LLM output (expected JSON) into a TutorResponse.
    Handles malformed JSON gracefully.
    """

    def parse(
        self,
        raw: str,
        strategy: str,
        learning_state: str,
        tokens: int,
        latency_ms: float,
        backend_name: str,
    ) -> TutorResponse:
        """
        Attempt JSON parse → fall back to treating entire response as text.
        """
        data = self._extract_json(raw)

        return TutorResponse(
            text=data.get("text", raw),
            follow_up_question=data.get("follow_up_question"),
            suggested_topic=data.get("suggested_topic"),
            encouragement=data.get("encouragement"),
            strategy_used=strategy,
            learning_state=learning_state,
            tokens_used=tokens,
            latency_ms=latency_ms,
            backend_used=backend_name,
        )

    def _extract_json(self, raw: str) -> dict:
        """Try multiple strategies to extract valid JSON."""
        # 1. Direct parse
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # 2. Extract JSON from markdown code block
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 3. Extract first {...} block
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        # 4. Partial field recovery if JSON was cut off unclosed
        text_match = re.search(r'"text"\s*:\s*"((?:[^"\\]|\\.)*)', raw, re.DOTALL)
        if text_match:
            try:
                recovered_text = (
                    text_match.group(1).encode().decode("unicode_escape", errors="ignore")
                )
            except Exception:
                recovered_text = text_match.group(1)
            if len(recovered_text.strip()) > 10:
                logger.info("Recovered partial text field from unclosed JSON response.")
                return {"text": recovered_text.strip()}

        # 5. Full fallback — treat entire string as response text
        logger.warning("Could not parse JSON from LLM response. Using raw text.")
        return {"text": raw.strip()}
