import json
import logging
import threading
import time
from abc import ABC, abstractmethod
from threading import BoundedSemaphore
from typing import Dict, List

from sentio.ai.stream_schema import current_schema, visible_text
from sentio.config import nlp_cfg
from sentio.jobs.control import WorkCancelled, checkpoint, current_control
from sentio.shared.exceptions import InvalidModelOutput, LLMServiceUnavailableError

logger = logging.getLogger(__name__)
_local_inference = BoundedSemaphore(1)


class LLMBackend(ABC):
    """Abstract base for all LLM backends."""

    @abstractmethod
    def load(self): ...

    @abstractmethod
    def complete(
        self,
        system_prompt: str,
        history: List[Dict[str, str]],
        user_message: str,
        max_tokens: int,
        temperature: float,
    ) -> tuple[str, int]:
        """
        Returns (response_text, tokens_used).
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str: ...


# ── Ollama Backend ─────────────────────────────


class OllamaBackend(LLMBackend):
    """
    Local Ollama server (llama3, mistral, etc.)
    Requires: ollama server running + pip install requests
    """

    def __init__(self, cfg=nlp_cfg):
        import requests

        self.cfg = cfg
        self._session = requests.Session()

    @property
    def name(self) -> str:
        return f"ollama/{self.cfg.OLLAMA_MODEL}"

    def load(self):
        try:
            r = self._session.get(f"{self.cfg.OLLAMA_BASE_URL}/api/tags", timeout=3)
            r.raise_for_status()
            logger.info(
                f"Ollama backend connected: {self.cfg.OLLAMA_BASE_URL} "
                f"(model: {self.cfg.OLLAMA_MODEL})"
            )
        except Exception as e:
            # Warn but do NOT crash the server.
            # Ollama errors will surface when the first chat message is sent.
            logger.warning(
                "Ollama server not reachable at %s. "
                "Start Ollama with: ollama serve  (then: ollama pull llama3). "
                "Error: %s",
                self.cfg.OLLAMA_BASE_URL,
                e,
            )
            return
        # Load the model now, in the background, so the first question does not wait
        # 10-35 s for 2-5 GB of weights to load from disk.
        threading.Thread(target=self.warm_up, name="ollama-warm-up", daemon=True).start()

    def _options(self, **options):
        if self.cfg.OLLAMA_NUM_THREAD:
            options["num_thread"] = self.cfg.OLLAMA_NUM_THREAD
        return options

    def warm_up(self):
        """Ask Ollama to load the model with the same options study requests use."""
        try:
            self._session.post(
                f"{self.cfg.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": self.cfg.OLLAMA_MODEL,
                    "keep_alive": self.cfg.OLLAMA_KEEP_ALIVE,
                    "options": self._options(),
                },
                timeout=180,
            ).raise_for_status()
            logger.info("Ollama model %s loaded and kept warm.", self.cfg.OLLAMA_MODEL)
        except Exception as error:
            logger.warning("Ollama warm-up did not finish: %s", error)

    def complete(
        self,
        system_prompt: str,
        history: List[Dict[str, str]],
        user_message: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> tuple[str, int]:
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": self.cfg.OLLAMA_MODEL,
            "messages": messages,
            "stream": True,
            "keep_alive": self.cfg.OLLAMA_KEEP_ALIVE,
            "options": self._options(temperature=temperature, num_predict=max_tokens),
            "format": current_schema().model_json_schema() if current_schema() else "json",
        }

        control = current_control()
        acquired = False
        response = None
        try:
            waiting = time.monotonic()
            checkpoint("waiting for local AI")
            while not _local_inference.acquire(timeout=0.1):
                checkpoint()
                if time.monotonic() - waiting > 180:
                    raise TimeoutError("Local AI is busy. Retry after current work finishes.")
            acquired = True
            checkpoint("generating answer")
            deadline = time.monotonic() + 180
            response = self._session.post(
                f"{self.cfg.OLLAMA_BASE_URL}/api/chat",
                json=payload,
                timeout=180,
                stream=True,
            )
            if control:
                with control.lock:
                    control.response = response
                    control.check()
            response.raise_for_status()
            raw = ""
            emitted = ""
            tokens = 0
            complete = False
            for line in response.iter_lines():
                checkpoint()
                if time.monotonic() > deadline:
                    raise TimeoutError(
                        "Local generation exceeded its time budget; retry a smaller request"
                    )
                if not line:
                    continue
                data = json.loads(line)
                if data.get("error"):
                    raise ValueError("Local model rejected the request")
                raw += data.get("message", {}).get("content", "")
                if len(raw) > 200000:
                    raise ValueError("Local model output exceeded the response limit")
                if control and control.emit and current_schema():
                    text = visible_text(raw)
                    if text.startswith(emitted) and len(text) > len(emitted):
                        control.emit("delta", {"text": text[len(emitted) :]})
                        emitted = text
                if data.get("done"):
                    if data.get("done_reason") == "length":
                        raise ValueError("Local model reached its output limit before finishing")
                    tokens = data.get("eval_count", len(raw.split()))
                    complete = True
                    break
            checkpoint()
            if not complete:
                raise ValueError("Local model disconnected before completing the answer")
            if current_schema():
                try:
                    current_schema().model_validate_json(raw)
                except ValueError as error:
                    raise InvalidModelOutput(raw, error) from error
            return raw, tokens
        except WorkCancelled:
            raise
        except InvalidModelOutput:
            if control:
                control.check()
            raise
        except Exception as e:
            if control:
                control.check()
            raise LLMServiceUnavailableError("ollama", str(e))
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    logger.debug("Model response could not close", exc_info=True)
            if control:
                with control.lock:
                    control.response = None
            if acquired:
                _local_inference.release()
