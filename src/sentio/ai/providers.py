import json
import logging
import time
from abc import ABC, abstractmethod
from threading import BoundedSemaphore
from typing import Dict, Generator, List

from sentio.ai.streaming import current_schema, visible_text
from sentio.config import nlp_cfg
from sentio.jobs.control import WorkCancelled, checkpoint, current_control
from sentio.shared.exceptions import LLMServiceUnavailableError

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


# ── OpenAI Backend ─────────────────────────────


class OpenAIBackend(LLMBackend):
    """
    Uses the OpenAI Chat Completions API (gpt-4o-mini by default).
    Requires: pip install openai
    """

    def __init__(self, cfg=nlp_cfg):
        self.cfg = cfg
        self._client = None

    @property
    def name(self) -> str:
        return f"openai/{self.cfg.OPENAI_MODEL}"

    def load(self):
        try:
            from openai import OpenAI

            if not self.cfg.OPENAI_API_KEY:
                logger.warning(
                    "OPENAI_API_KEY is not set! "
                    "Set it with:  $env:OPENAI_API_KEY='sk-...'  (PowerShell) "
                    "or: set OPENAI_API_KEY=sk-...  (CMD). "
                    "The server will start but chat will fail until the key is set."
                )
            self._client = OpenAI(api_key=self.cfg.OPENAI_API_KEY)
            logger.info(f"OpenAI backend loaded: {self.cfg.OPENAI_MODEL}")
        except ImportError:
            raise ImportError("openai package not found. Run: pip install openai")

    def complete(
        self,
        system_prompt: str,
        history: List[Dict[str, str]],
        user_message: str,
        max_tokens: int = None,
        temperature: float = None,
    ) -> tuple[str, int]:
        max_tokens = max_tokens or self.cfg.OPENAI_MAX_TOKENS
        temperature = temperature or self.cfg.OPENAI_TEMPERATURE

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        try:
            response = self._client.chat.completions.create(
                model=self.cfg.OPENAI_MODEL,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"},  # Force JSON output
            )
            text = response.choices[0].message.content
            tokens = response.usage.total_tokens
            return text, tokens
        except Exception as e:
            raise LLMServiceUnavailableError("openai", str(e))

    def stream(
        self,
        system_prompt: str,
        history: List[Dict[str, str]],
        user_message: str,
    ) -> Generator[str, None, None]:
        """Stream response tokens as a generator."""
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        with self._client.chat.completions.create(
            model=self.cfg.OPENAI_MODEL,
            messages=messages,
            max_tokens=self.cfg.OPENAI_MAX_TOKENS,
            temperature=self.cfg.OPENAI_TEMPERATURE,
            stream=True,
        ) as stream:
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta


# ── HuggingFace Backend ────────────────────────


class HuggingFaceBackend(LLMBackend):
    """
    Local HuggingFace transformers model (phi-2 by default).
    Requires: pip install transformers accelerate
    """

    def __init__(self, cfg=nlp_cfg):
        self.cfg = cfg
        self._pipeline = None

    @property
    def name(self) -> str:
        return f"huggingface/{self.cfg.HF_MODEL_NAME}"

    def load(self):
        try:
            import torch
            from transformers import pipeline

            device = (
                0
                if (
                    self.cfg.HF_DEVICE == "cuda"
                    and hasattr(torch, "cuda")
                    and torch.cuda.is_available()
                )
                else -1
            )

            self._pipeline = pipeline(
                "text-generation",
                model=self.cfg.HF_MODEL_NAME,
                device=device,
                trust_remote_code=True,
            )
            logger.info(
                f"HuggingFace backend loaded: {self.cfg.HF_MODEL_NAME} "
                f"on {'GPU' if device == 0 else 'CPU'}"
            )
        except ImportError:
            raise ImportError("transformers not found. Run: pip install transformers accelerate")

    def complete(
        self,
        system_prompt: str,
        history: List[Dict[str, str]],
        user_message: str,
        max_tokens: int = None,
        temperature: float = None,
    ) -> tuple[str, int]:
        max_tokens = max_tokens or self.cfg.HF_MAX_NEW_TOKENS
        temperature = temperature or self.cfg.HF_TEMPERATURE

        # Build prompt in ChatML-style format
        prompt = self._format_prompt(system_prompt, history, user_message)

        try:
            outputs = self._pipeline(
                prompt,
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=True,
                pad_token_id=self._pipeline.tokenizer.eos_token_id,
                return_full_text=False,
            )
            text = outputs[0]["generated_text"].strip()
            tokens = len(text.split())  # Approximate
            return text, tokens
        except Exception as e:
            raise LLMServiceUnavailableError("huggingface", str(e))

    def _format_prompt(
        self, system_prompt: str, history: List[Dict[str, str]], user_message: str
    ) -> str:
        """Format for ChatML / Phi-2 style."""
        parts = [f"<|system|>\n{system_prompt}\n<|end|>"]
        for msg in history:
            role_tag = "<|user|>" if msg["role"] == "user" else "<|assistant|>"
            parts.append(f"{role_tag}\n{msg['content']}\n<|end|>")
        parts.append(f"<|user|>\n{user_message}\n<|end|>")
        parts.append("<|assistant|>")
        return "\n".join(parts)


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
            "keep_alive": "15m",
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
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
                current_schema().model_validate_json(raw)
            return raw, tokens
        except WorkCancelled:
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
