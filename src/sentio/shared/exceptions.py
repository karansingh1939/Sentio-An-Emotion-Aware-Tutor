"""
exceptions.py — Custom Exceptions for Sentio
=============================================
Defines standard exceptions for runtime error propagation and handling.
"""


class LLMServiceUnavailableError(Exception):
    """Raised when the LLM service is offline, unreachable, or has model loading issues."""

    def __init__(self, backend_name: str, message: str):
        self.backend_name = backend_name
        self.message = message
        super().__init__(f"LLM backend '{backend_name}' is currently unavailable: {message}")


class InvalidModelOutput(ValueError):
    """The model finished, but its output does not match the requested schema.

    Unlike LLMServiceUnavailableError the service is working, so callers may repair the
    raw output or ask the model to regenerate it.
    """

    def __init__(self, raw: str, error):
        self.raw = raw
        super().__init__(f"Model output did not match the requested format: {error}")
